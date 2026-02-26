from django.db import models
from users.models import User


class Category(models.Model):
    name = models.CharField('Название', max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name


class Shop(models.Model):
    name = models.CharField('Название магазина', max_length=100)
    url = models.URLField('Ссылка на прайс', blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    state = models.BooleanField('Статус приёма заказов', default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField('Наименование', max_length=200)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    model = models.CharField('Модель', max_length=100, blank=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='info')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='product_infos')
    external_id = models.PositiveIntegerField('Внешний ID')
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField('Количество')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop', 'external_id'], name='unique_product_info')
        ]


class Parameter(models.Model):
    name = models.CharField('Название параметра', max_length=100)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, related_name='product_parameters')
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE)
    value = models.CharField('Значение', max_length=100)

    class Meta:
        verbose_name = 'Параметр товара'
        verbose_name_plural = 'Параметры товаров'