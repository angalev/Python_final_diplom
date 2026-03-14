from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import URLValidator, validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from requests import get
from yaml import load as load_yaml, Loader
from datetime import timedelta
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.generics import get_object_or_404

from .models import (
    User, Shop, Category, Product, ProductInfo,
    Order, OrderItem, Parameter, ProductParameter, ConfirmEmailToken
)
from .serializers import (
    UserSerializer, ContactSerializer, ShopSerializer,
    CategorySerializer, ProductInfoSerializer, OrderSerializer
)

User = get_user_model()


# =================== РЕГИСТРАЦИЯ ПОЛЬЗОВАТЕЛЯ ===================
class RegisterAccount(APIView):
    """
    Регистрация пользователя → создаёт неактивного юзера + токен
    POST /api/user/register/
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

        user = User.objects.filter(email=email).first()

        # Проверяем, существует ли неактивный пользователь
        if user and not user.is_active:
            # Проверяем, прошла ли минута с последней попытки
            last_token = ConfirmEmailToken.objects.filter(user=user).order_by('-created_at').first()
            if last_token and timezone.now() < last_token.created_at + timedelta(minutes=1):
                return Response(
                    {'Status': False, 'Errors': 'Повторная отправка возможна не чаще 1 раза в минуту'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Удаляем старый токен — будем создавать новый
            ConfirmEmailToken.objects.filter(user=user).delete()

        elif user and user.is_active:
            return Response(
                {'Status': False, 'Errors': 'Пользователь с таким email уже активирован'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Создаём неактивного пользователя (если ещё нет)
        if not user:
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

        # Создаём токен подтверждения
        token, created = ConfirmEmailToken.objects.get_or_create(user_id=user.id)
        confirm_url = f"http://localhost:8000/api/user/confirm/?token={token.key}"

        # Отправляем письмо
        try:
            send_mail(
                subject='Подтвердите ваш email',
                message=f'Чтобы активировать аккаунт, перейдите по ссылке:\n\n{confirm_url}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as e:
            # 🔥 Если письмо не отправилось — удаляем токен
            token.delete()
            return Response(
                {
                    'Status': False,
                    'Errors': 'Не удалось отправить письмо. Попробуйте позже.',
                    'Detail': str(e) if settings.DEBUG else None
                },
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({
            'Status': True,
            'Message': 'Регистрация успешна! Проверьте почту для подтверждения.'
        }, status=status.HTTP_201_CREATED)


# =================== ПОДТВЕРЖДЕНИЕ EMAIL ===================
class ConfirmAccount(APIView):
    """
    Активация аккаунта по токену
    GET /api/user/confirm/?token=abc123
    """
    permission_classes = [AllowAny]

    def get(self, request):
        token_key = request.query_params.get('token')

        if not token_key:
            return Response(
                {'Status': False, 'Errors': 'Токен обязателен в ссылке'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ищем токен
        token = get_object_or_404(ConfirmEmailToken, key=token_key)

        # Получаем пользователя
        user = token.user

        # Если уже активирован — удаляем токен и сообщаем
        if user.is_active:
            token.delete()
            return Response({'Status': True, 'Message': 'Аккаунт уже активирован'})

        # Активируем
        user.is_active = True
        user.save()

        # Создаём DRF-токен для авторизации
        Token.objects.get_or_create(user=user)

        # Удаляем токен подтверждения (одноразовый!)
        token.delete()

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

        added_count = 0
        errors = []

        with transaction.atomic():

            basket, _ = Order.objects.get_or_create(user=request.user, state='basket')

            for item in items:
                product_info_id = item.get('product_info')
                quantity = item.get('quantity', 1)

                if not product_info_id:
                    errors.append(f"Отсутствует product_info_id в элементе: {item}")
                    continue

                if not isinstance(quantity, int) or quantity < 1:
                    errors.append(f"Некорректное количество '{quantity}' для product_info_id={product_info_id}")
                    continue

                try:
                    product_info = ProductInfo.objects.get(id=product_info_id)
                except ProductInfo.DoesNotExist:
                    errors.append(f"Товар с product_info_id={product_info_id} не найден")
                    continue

                order_item, created = OrderItem.objects.get_or_create(
                    order=basket,
                    product_info=product_info,
                    defaults={'quantity': quantity}
                )
                if not created:
                    order_item.quantity += quantity
                    order_item.save()

                added_count += 1

        if added_count == 0:
            return Response({
                'Status': False,
                'Errors': 'Не удалось добавить ни один товар',
                'Details': errors
            }, status=status.HTTP_400_BAD_REQUEST)

        if errors:
            return Response({
                'Status': True,
                'Message': f'Добавлено товаров: {added_count}',
                'Warnings': errors
            })

        return Response({'Status': True})

    def put(self, request):
        items = request.data.get('items')
        if not items:
            return Response(
                {'Status': False, 'Errors': 'Не указаны товары'},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_count = 0
        errors = []

        with transaction.atomic():

            basket, _ = Order.objects.get_or_create(user=request.user, state='basket')

            for item in items:
                product_info_id = item.get('product_info')
                quantity = item.get('quantity')

                if not product_info_id or not isinstance(quantity, int) or quantity < 1:
                    errors.append(f"Некорректные данные: {item}")
                    continue

                order_item = basket.ordered_items.filter(product_info_id=product_info_id).first()
                if not order_item:
                    errors.append(f"Товар с product_info_id={product_info_id} не найден в корзине")
                    continue

                order_item.quantity = quantity
                order_item.save()
                updated_count += 1

        if errors:
            return Response({
                'Status': True,
                'Message': f'Обновлено: {updated_count}',
                'Warnings': errors
            })

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
                {'Status': False, 'Errors': 'Корзина пуста или не существует'},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted_count = 0
        errors = []

        with transaction.atomic():
            for item in items:
                product_info_id = item.get('product_info')
                if not product_info_id:
                    errors.append("Отсутствует product_info_id")
                    continue

                deleted, _ = basket.ordered_items.filter(product_info_id=product_info_id).delete()
                deleted_count += deleted

        return Response({
            'Status': True,
            'Message': f'Удалено позиций: {deleted_count}',
            'Warnings': errors if errors else None
        })


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

        if not isinstance(state, bool):
            return Response(
                {'Status': False, 'Errors': 'Поле "state" должно быть булевым значением (true/false)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop = getattr(request.user, 'shop', None)
        if not shop:
            return Response(
                {'Status': False, 'Errors': 'Магазин не найден'},
                status=status.HTTP_400_BAD_REQUEST
            )

        shop.state = state
        shop.save()

        return Response({'Status': True})

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