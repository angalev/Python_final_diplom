from rest_framework import serializers
from .models import (
    User, Contact, Shop, Category, Product,
    ProductInfo, ProductParameter, Parameter,
    Order, OrderItem
)


class UserSerializer(serializers.ModelSerializer):
    """
    Сериализатор пользователя
    """
    class Meta:
        model = User
        fields = (
            'id', 'first_name', 'last_name', 'email',
            'company', 'position', 'type', 'is_active'
        )
        read_only_fields = ('id', 'is_active')


class ContactSerializer(serializers.ModelSerializer):
    """
    Сериализатор контактов
    """
    class Meta:
        model = Contact
        fields = (
            'id', 'city', 'street', 'house', 'structure',
            'building', 'apartment', 'phone'
        )


class ShopSerializer(serializers.ModelSerializer):
    """
    Сериализатор магазина
    """
    class Meta:
        model = Shop
        fields = ('id', 'name', 'url', 'state')


class CategorySerializer(serializers.ModelSerializer):
    """
    Сериализатор категории
    """
    class Meta:
        model = Category
        fields = ('id', 'name')


class ParameterSerializer(serializers.ModelSerializer):
    """
    Сериализатор параметра
    """
    class Meta:
        model = Parameter
        fields = ('id', 'name')


class ProductSerializer(serializers.ModelSerializer):
    """
    Сериализатор продукта
    """
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ('id', 'name', 'category')


class ProductParameterSerializer(serializers.ModelSerializer):
    """
    Сериализатор параметра продукта
    """
    parameter = ParameterSerializer(read_only=True)

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value')


class ProductInfoSerializer(serializers.ModelSerializer):
    """
    Сериализатор информации о продукте (с магазином)
    """
    product = ProductSerializer(read_only=True)
    shop = ShopSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = (
            'id', 'model', 'external_id', 'product', 'shop',
            'quantity', 'price', 'price_rrc', 'product_parameters'
        )


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Сериализатор позиции заказа
    """
    product_info = ProductInfoSerializer(read_only=True)
    total_cost = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ('id', 'product_info', 'quantity', 'total_cost')

    def get_total_cost(self, obj):
        return obj.quantity * obj.product_info.price


class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор заказа
    """
    ordered_items = OrderItemSerializer(many=True, read_only=True)
    contact = ContactSerializer(read_only=True)
    total_amount = serializers.SerializerMethodField()
    status = serializers.CharField(source='get_state_display')

    class Meta:
        model = Order
        fields = ('id', 'dt', 'status', 'contact', 'total_amount', 'ordered_items')
        read_only_fields = ('id', 'dt')

    def get_total_amount(self, obj):
        return sum(item.quantity * item.product_info.price for item in obj.ordered_items.all())