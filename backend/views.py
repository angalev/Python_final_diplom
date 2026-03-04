from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import URLValidator
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from requests import get
from yaml import load as load_yaml, Loader

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from .models import (
    User, Shop, Category, Product, ProductInfo,
    Order, OrderItem, Parameter, ProductParameter
)
from .serializers import (
    UserSerializer, ContactSerializer, ShopSerializer,
    CategorySerializer, ProductInfoSerializer, OrderSerializer
)

User = get_user_model()


# =================== РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ===================
class RegisterAccount(APIView):
    """
    Регистрация покупателей и магазинов
    """
    permission_classes = [AllowAny]

    def post(self, request):
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if not required_fields.issubset(request.data):
            return JsonResponse({'Status': False, 'Errors': 'Не хватает данных'})

        try:
            validate_password(request.data['password'])
        except ValidationError as e:
            return JsonResponse({'Status': False, 'Errors': e.messages})

        user = User.objects.create_user(
            email=request.data['email'],
            password=request.data['password'],
            first_name=request.data['first_name'],
            last_name=request.data['last_name'],
            company=request.data['company'],
            position=request.data['position'],
            type=request.data.get('type', 'buyer'),
            is_active=False
        )
        send_mail(
            subject='Регистрация завершена',
            message='Вы успешно зарегистрировались. Подтвердите email, чтобы войти.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return JsonResponse({'Status': True})


# =================== ПОДТВЕРЖДЕНИЕ EMAIL ===================
class ConfirmAccount(APIView):
    """
    Подтверждение email через токен
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        token = request.data.get('token')
        if not email or not token:
            return JsonResponse({'Status': False, 'Errors': 'Email и токен обязательны'})

        try:
            user = User.objects.get(email=email)
            user.is_active = True
            user.save()
            user.confirm_email_tokens.all().delete()
            return JsonResponse({'Status': True})
        except User.DoesNotExist:
            return JsonResponse({'Status': False, 'Errors': 'Пользователь не найден'})


# =================== ВХОД В СИСТЕМУ ===================
class LoginAccount(APIView):
    """
    Аутентификация пользователя
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return JsonResponse({'Status': False, 'Errors': 'Требуются email и пароль'})

        user = authenticate(email=email, password=password)
        if user is None:
            return JsonResponse({'Status': False, 'Errors': 'Неверные учётные данные'})

        if not user.is_active:
            return JsonResponse({'Status': False, 'Errors': 'Почта не подтверждена'})

        return JsonResponse({'Status': True, 'Token': user.auth_token.key})


# =================== КОРЗИНА ===================
class BasketView(APIView):
    """
    Просмотр и редактирование корзины
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return JsonResponse({'Status': False, 'Errors': 'Корзина пуста'})
        serializer = OrderSerializer(basket)
        return JsonResponse(serializer.data)

    def post(self, request):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары'})

        with transaction.atomic():
            basket, _ = Order.objects.get_or_create(user=request.user, state='basket')
            for item in items:
                product_info_id = item.get('product_info')
                quantity = item.get('quantity')
                if not product_info_id or not quantity:
                    continue
                order_item, created = OrderItem.objects.get_or_create(
                    order=basket,
                    product_info_id=product_info_id,
                    defaults={'quantity': quantity}
                )
                if not created:
                    order_item.quantity += quantity
                    order_item.save()

        return JsonResponse({'Status': True})

    def put(self, request):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары'})

        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return JsonResponse({'Status': False, 'Errors': 'Корзина не найдена'})

        with transaction.atomic():
            for item in items:
                order_item = basket.ordered_items.filter(product_info_id=item.get('product_info')).first()
                if order_item:
                    order_item.quantity = item.get('quantity', 1)
                    order_item.save()

        return JsonResponse({'Status': True})

    def delete(self, request):
        items = request.data.get('items')
        if not items:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны товары'})

        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return JsonResponse({'Status': False, 'Errors': 'Корзина не найдена'})

        with transaction.atomic():
            for item in items:
                basket.ordered_items.filter(product_info_id=item.get('product_info')).delete()

        return JsonResponse({'Status': True})


# =================== ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ===================
class AccountDetails(APIView):
    """
    Получение и изменение данных пользователя
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return JsonResponse(serializer.data)

    def post(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': serializer.errors})


# =================== КОНТАКТЫ ===================
class ContactView(APIView):
    """
    Управление контактами
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contacts = request.user.contacts.all()
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid():
            contact = serializer.save(user=request.user)

            # Отправить email
            send_mail(
                subject='Адрес доставки добавлен',
                message=f'Адрес {contact.city}, {contact.street} успешно добавлен.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )

            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': serializer.errors})

    def put(self, request):
        contact_id = request.data.get('id')
        if not contact_id:
            return JsonResponse({'Status': False, 'Errors': 'ID контакта обязателен'})

        contact = request.user.contacts.filter(id=contact_id).first()
        if not contact:
            return JsonResponse({'Status': False, 'Errors': 'Контакт не найден'})

        serializer = ContactSerializer(contact, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': serializer.errors})

    def delete(self, request):
        contact_id = request.data.get('id')
        if not contact_id:
            return JsonResponse({'Status': False, 'Errors': 'ID контакта обязателен'})

        request.user.contacts.filter(id=contact_id).delete()
        return JsonResponse({'Status': True})


# =================== ЗАКАЗЫ ===================
class OrderView(APIView):
    """
    Просмотр истории заказов и оформление
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(user=request.user).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__shop',
            'ordered_items__product_info__product_parameters__parameter',
            'contact'
        )
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        contact_id = request.data.get('contact')
        if not contact_id:
            return JsonResponse({'Status': False, 'Errors': 'Контакт обязателен'})

        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket or not basket.ordered_items.exists():
            return JsonResponse({'Status': False, 'Errors': 'Корзина пуста'})

        basket.contact_id = contact_id
        basket.state = 'new'
        basket.save()

        # Отправить email о подтверждении заказа
        send_mail(
            subject='Заказ подтверждён',
            message=f'Ваш заказ №{basket.id} успешно оформлен. Спасибо за покупку!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False,
        )

        return JsonResponse({'Status': True})


# =================== МАГАЗИНЫ И КАТЕГОРИИ ===================
class ShopView(viewsets.ReadOnlyModelViewSet):
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer
    permission_classes = [AllowAny]


class CategoryView(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


# =================== ТОВАРЫ ===================
class ProductInfoView(APIView):
    """
    Поиск товаров по магазину и категории
    """
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = ProductInfo.objects.select_related('product', 'shop', 'product__category')
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)

        serializer = ProductInfoSerializer(queryset, many=True)
        return Response(serializer.data)


# =================== PARTNER VIEWS ===================
class PartnerUpdate(APIView):
    """
    Обновление прайса от поставщика
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if not url:
            return JsonResponse({'Status': False, 'Errors': 'URL обязателен'})

        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return JsonResponse({'Status': False, 'Error': str(e)})

        stream = get(url).content
        data = load_yaml(stream, Loader=Loader)

        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)

        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(
                id=category['id'], name=category['name']
            )
            category_object.shops.add(shop.id)
            category_object.save()

        ProductInfo.objects.filter(shop_id=shop.id).delete()

        for item in data['goods']:
            product, _ = Product.objects.get_or_create(
                name=item['name'],
                category_id=item['category']
            )

            product_info = ProductInfo.objects.create(
                product_id=product.id,
                external_id=item['id'],
                model=item['model'],
                price=item['price'],
                price_rrc=item['price_rrc'],
                quantity=item['quantity'],
                shop_id=shop.id
            )

            for name, value in item['parameters'].items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(
                    product_info_id=product_info.id,
                    parameter_id=parameter_object.id,
                    value=value
                )

        return JsonResponse({'Status': True})


class PartnerState(APIView):
    """
    Управление статусом получения заказов магазином
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Errors': 'Только для магазинов'})

        shop = getattr(request.user, 'shop', None)
        if not shop:
            return JsonResponse({'Status': False, 'Errors': 'Магазин не найден'})

        return JsonResponse({'name': shop.name, 'state': shop.state})

    def post(self, request):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Errors': 'Только для магазинов'})

        state = request.data.get('state')
        if state not in ('true', 'false'):
            return JsonResponse({'Status': False, 'Errors': 'Неверное значение'})

        shop = getattr(request.user, 'shop', None)
        if shop:
            shop.state = state == 'true'
            shop.save()
            return JsonResponse({'Status': True})
        return JsonResponse({'Status': False, 'Errors': 'Магазин не найден'})


class PartnerOrders(APIView):
    """
    Просмотр заказов, связанных с магазином
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Errors': 'Только для магазинов'})

        shop = getattr(request.user, 'shop', None)
        if not shop:
            return JsonResponse({'Status': False, 'Errors': 'Магазин не найден'})

        orders = Order.objects.filter(
            ordered_items__product_info__shop=shop
        ).exclude(state='basket').distinct()

        result = []
        for order in orders:
            items = []
            total = 0
            for item in order.ordered_items.all():
                if item.product_info.shop == shop:
                    sum_item = item.product_info.price * item.quantity
                    total += sum_item
                    items.append({
                        'product': item.product_info.product.name,
                        'quantity': item.quantity,
                        'price': item.product_info.price,
                        'total': sum_item
                    })
            result.append({
                'order_id': order.id,
                'status': order.state,
                'total': total,
                'items': items
            })

        return Response(result)