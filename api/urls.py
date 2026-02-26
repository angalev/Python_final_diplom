from django.urls import path, include
from rest_framework.routers import DefaultRouter
from products.views import ProductViewSet, ShopViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'shops', ShopViewSet)

urlpatterns = [
    path('', include(router.urls)),
]