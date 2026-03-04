from django.contrib import admin
from .models import User, Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Order, OrderItem, Contact


# Вспомогательный класс для отображения параметров внутри ProductInfo
class ProductParameterInline(admin.TabularInline):
    model = ProductParameter
    extra = 1  # Сколько пустых строк показывать


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    list_display = ('product', 'shop', 'quantity', 'price')
    inlines = [ProductParameterInline]


admin.site.register(User)
admin.site.register(Shop)
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Parameter)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Contact)