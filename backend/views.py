from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import URLValidator, validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from requests import get
from yaml import load as load_yaml, Loader

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import get_object_or_404

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
    Регистрация пользователя (создаёт неактивного юзера)
    POST /api/user/register
    """
    permission_classes = [AllowAny]

    def post(self, request):
        required_fields = {'first_name', 'last_name', 'email', 'password', 'company', 'position'}
        if not all(field in request.data for field in required_fields):
            missing = required_fields - set(request.data.keys())
            return Response(
                {'Status': False, 'Errors': f'Не хватает полей: {", ".join(missing)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = request.data['email'].strip()

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {'Status': False, 'Errors': 'Некорректный email'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=email).exists():
            return Response(
                {'Status': False, 'Errors': 'Пользователь с таким email уже существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаём неактивного пользователя
        user = User.objects.create_user(
            email=email,
            password=request.data['password'],
            first_name=request.data['first_name'].strip(),
            last_name=request.data['last_name'].strip(),
            company=request.data['company'].strip(),
            position=request.data['position'].strip(),
            is_active=False,
            type=request.data.get('type', 'buyer')
        )

        # Инструкция для активации (не ссылка!)
        message = (
            'Вы зарегистрировались на нашем сайте.\n\n'
            'Чтобы активировать аккаунт, нажмите кнопку "Подтвердить" в приложении.\n\n'
            'Или отправьте POST-запрос:\n'
            'POST /api/user/register/confirm/\n'
            'Content-Type: application/json\n\n'
            f'{{"email": "{email}"}}'
        )

        # Отправляем письмо
        send_mail(
            subject='Подтвердите ваш email',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response({
            'Status': True,
            'Message': 'Регистрация успешна! Проверьте почту для подтверждения.'
        }, status=status.HTTP_201_CREATED)


# =================== ПОДТВЕРЖДЕНИЕ EMAIL ===================
class ConfirmAccount(APIView):
    """
    Активация пользователя через POST
    POST /api/user/register/confirm/
    """
    permission_classes = [AllowAny]  # ← исправлено: вне метода

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response(
                {'Status': False, 'Errors': 'Email обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'Status': False, 'Errors': 'Пользователь не найден'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.is_active:
            return Response({'Status': True, 'Message': 'Аккаунт уже активирован'})

        user.is_active = True
        user.save()

        Token.objects.get_or_create(user=user)

        return Response({'Status': True, 'Message': 'Аккаунт успешно активирован!'})


# =================== ВХОД В СИСТЕМУ ===================
class LoginAccount(APIView):
    """
    Аутентификация пользователя → получение токена
    POST /api/user/login
    """
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response(
                {'Status': False, 'Errors': 'Email и пароль обязательны'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=email, password=password)
        if user is None:
            return Response(
                {'Status': False, 'Errors': 'Неверные учётные данные'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_active:
            return Response(
                {'Status': False, 'Errors': 'Почта не подтверждена'},
                status=status.HTTP_400_BAD_REQUEST
            )

        token, _ = Token.objects.get_or_create(user=user)
        return Response({'Status': True, 'Token': token.key})


# =================== ДАННЫЕ ПОЛЬЗОВАТЕЛЯ ===================
class AccountDetails(APIView):
    """
    Получение и изменение профиля
    GET, PATCH /api/user/details/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': True}, status=status.HTTP_200_OK)
        return Response(
            {'Status': False, 'Errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


# =================== КОНТАКТЫ ===================
class ContactView(APIView):
    """
    Управление контактами доставки
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
            send_mail(
                subject='Адрес доставки добавлен',
                message=f'Адрес {contact.city}, {contact.street} успешно добавлен.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request.user.email],
                fail_silently=False,
            )
            return Response({'Status': True})
        return Response({'Status': False, 'Errors': serializer.errors})

    def put(self, request):
        contact_id = request.data.get('id')
        if not contact_id:
            return Response(
                {'Status': False, 'Errors': 'ID контакта обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        contact = get_object_or_404(request.user.contacts, id=contact_id)
        serializer = ContactSerializer(contact, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'Status': True})
        return Response({'Status': False, 'Errors': serializer.errors})

    def delete(self, request):
        contact_id = request.data.get('id')
        if not contact_id:
            return Response(
                {'Status': False, 'Errors': 'ID контакта обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        request.user.contacts.filter(id=contact_id).delete()
        return Response({'Status': True})


# =================== КОРЗИНА ===================
class BasketView(APIView):
    """
    Управление корзиной
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        basket = Order.objects.filter(user=request.user, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__shop'
        ).first()
        if not basket:
            return Response({'Status': False, 'Errors': 'Корзина пуста'})
        serializer = OrderSerializer(basket)
        return Response(serializer.data)

    def post(self, request):
        items = request.data.get('items')
        if not items:
            return Response(
                {'Status': False, 'Errors': 'Не указаны товары'},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        return Response({'Status': True})

    def put(self, request):
        items = request.data.get('items')
        if not items:
            return Response(
                {'Status': False, 'Errors': 'Не указаны товары'},
                status=status.HTTP_400_BAD_REQUEST
            )

        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return Response(
                {'Status': False, 'Errors': 'Корзина не найдена'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            for item in items:
                order_item = basket.ordered_items.filter(product_info_id=item.get('product_info')).first()
                if order_item:
                    order_item.quantity = item.get('quantity', 1)
                    order_item.save()

        return Response({'Status': True})

    def delete(self, request):
        items = request.data.get('items')
        if not items:
            return Response(
                {'Status': False, 'Errors': 'Не указаны товары'},
                status=status.HTTP_400_BAD_REQUEST
            )

        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket:
            return Response(
                {'Status': False, 'Errors': 'Корзина не найдена'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            for item in items:
                basket.ordered_items.filter(product_info_id=item.get('product_info')).delete()

        return Response({'Status': True})


# =================== ЗАКАЗЫ ===================
class OrderView(APIView):
    """
    Просмотр и оформление заказов
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
            return Response(
                {'Status': False, 'Errors': 'Контакт обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket or not basket.ordered_items.exists():
            return Response(
                {'Status': False, 'Errors': 'Корзина пуста'},
                status=status.HTTP_400_BAD_REQUEST
            )
        basket.contact_id = contact_id
        basket.state = 'new'
        basket.save()
        send_mail(
            subject='Заказ подтверждён',
            message=f'Ваш заказ №{basket.id} успешно оформлен. Спасибо за покупку!',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
        return Response({'Status': True})


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
    Поиск товаров
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
    Обновление прайса
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.type != 'shop':
            return Response(
                {'Status': False, 'Error': 'Только для магазинов'},
                status=status.HTTP_403_FORBIDDEN
            )
        url = request.data.get('url')
        if not url:
            return Response(
                {'Status': False, 'Errors': 'URL обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return Response(
                {'Status': False, 'Error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        stream = get(url).content
        data = load_yaml(stream, Loader=Loader)
        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=request.user.id)
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
            category_object.shops.add(shop.id)
            category_object.save()
        ProductInfo.objects.filter(shop_id=shop.id).delete()
        for item in data['goods']:
            product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
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
        return Response({'Status': True})


class PartnerState(APIView):
    """
    Управление статусом получения заказов
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.type != 'shop':
            return Response(
                {'Status': False, 'Errors': 'Только для магазинов'},
                status=status.HTTP_403_FORBIDDEN
            )
        shop = getattr(request.user, 'shop', None)
        if not shop:
            return Response(
                {'Status': False, 'Errors': 'Магазин не найден'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({'name': shop.name, 'state': shop.state})

    def post(self, request):
        if request.user.type != 'shop':
            return Response(
                {'Status': False, 'Errors': 'Только для магазинов'},
                status=status.HTTP_403_FORBIDDEN
            )
        state = request.data.get('state')
        if state not in ('true', 'false'):
            return Response(
                {'Status': False, 'Errors': 'Неверное значение'},
                status=status.HTTP_400_BAD_REQUEST
            )
        shop = getattr(request.user, 'shop', None)
        if shop:
            shop.state = state == 'true'
            shop.save()
            return Response({'Status': True})
        return Response(
            {'Status': False, 'Errors': 'Магазин не найден'},
            status=status.HTTP_400_BAD_REQUEST
        )


class PartnerOrders(APIView):
    """
    Просмотр заказов магазина
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.type != 'shop':
            return Response(
                {'Status': False, 'Errors': 'Только для магазинов'},
                status=status.HTTP_403_FORBIDDEN
            )
        shop = getattr(request.user, 'shop', None)
        if not shop:
            return Response(
                {'Status': False, 'Errors': 'Магазин не найден'},
                status=status.HTTP_400_BAD_REQUEST
            )
        orders = Order.objects.filter(ordered_items__product_info__shop=shop).exclude(state='basket').distinct()
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