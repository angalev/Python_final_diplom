# backend/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterAccount,
    LoginAccount,
    CategoryView,
    ShopView,
    ProductInfoView,
    BasketView,
    AccountDetails,
    ContactView,
    OrderView,
    PartnerUpdate,
    PartnerState,
    PartnerOrders,
    ConfirmAccount,
)
from django_rest_passwordreset.views import reset_password_request_token, reset_password_confirm

app_name = 'backend'

# Роутер только для категорий и магазинов
router = DefaultRouter()
router.register(r'categories', CategoryView, basename='categories')
router.register(r'shops', ShopView, basename='shops')

urlpatterns = [
    # Работа с пользователем
    path('user/register', RegisterAccount.as_view(), name='user-register'),
    path('user/register/confirm', ConfirmAccount.as_view(), name='user-register-confirm'),
    path('user/login', LoginAccount.as_view(), name='user-login'),
    path('user/details', AccountDetails.as_view(), name='user-details'),
    path('user/contact', ContactView.as_view(), name='user-contact'),

    # Сброс пароля
    path('user/password_reset', reset_password_request_token, name='password-reset'),
    path('user/password_reset/confirm', reset_password_confirm, name='password-reset-confirm'),

    # Поиск товаров (вместо ProductViewSet)
    path('products', ProductInfoView.as_view(), name='product-info'),

    # Корзина
    path('basket', BasketView.as_view(), name='basket'),

    # Заказы
    path('order', OrderView.as_view(), name='order'),

    # Партнёр
    path('partner/update', PartnerUpdate.as_view(), name='partner-update'),
    path('partner/state', PartnerState.as_view(), name='partner-state'),
    path('partner/orders', PartnerOrders.as_view(), name='partner-orders'),
]

# Добавляем маршруты из роутера
urlpatterns += router.urls