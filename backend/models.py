
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
import secrets

# Статусы заказа
STATE_CHOICES = (
    ('basket', 'Статус корзины'),
    ('new', 'Новый'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

# Тип пользователя
USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель'),
)


# =================== МЕНЕДЖЕР ПОЛЬЗОВАТЕЛЕЙ ===================
class UserManager(BaseUserManager):
    """
    Кастомный менеджер для создания пользователей с email как логином.
    """
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email обязателен')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(email, password, **extra_fields)


# =================== ПОЛЬЗОВАТЕЛЬ ===================
class User(AbstractUser):
    """
    Кастомная модель пользователя с email как логином.
    """
    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    email = models.EmailField(_('email address'), unique=True)
    company = models.CharField(verbose_name='Компания', max_length=40, blank=True)
    position = models.CharField(verbose_name='Должность', max_length=40, blank=True)
    username = models.CharField(
        _('username'),
        max_length=150,
        help_text=_('Required. 150 characters or fewer.'),
        validators=[UnicodeUsernameValidator()],
        error_messages={'unique': _("Пользователь с таким именем уже существует.")},
        blank=True  # Чтобы можно было оставить пустым
    )
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_('Указывает, активен ли пользователь. Вместо удаления — отключайте.')
    )
    type = models.CharField(
        verbose_name='Тип пользователя',
        choices=USER_TYPE_CHOICES,
        max_length=5,
        default='buyer'
    )

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Список пользователей'
        ordering = ('email',)


# =================== МАГАЗИН ===================
class Shop(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название')
    url = models.URLField(verbose_name='Ссылка', null=True, blank=True)
    user = models.OneToOneField(
        User,
        verbose_name='Пользователь',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='shop'
    )
    state = models.BooleanField(verbose_name='Статус получения заказов', default=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Список магазинов'
        ordering = ('-name',)

    def __str__(self):
        return self.name


# =================== КАТЕГОРИЯ ===================
class Category(models.Model):
    name = models.CharField(max_length=40, verbose_name='Название')
    shops = models.ManyToManyField(
        Shop,
        verbose_name='Магазины',
        related_name='categories',
        blank=True
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Список категорий'
        ordering = ('-name',)

    def __str__(self):
        return self.name


# =================== ПРОДУКТ ===================
class Product(models.Model):
    name = models.CharField(max_length=80, verbose_name='Название')
    category = models.ForeignKey(
        Category,
        verbose_name='Категория',
        related_name='products',
        blank=True,
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Список продуктов'
        ordering = ('-name',)

    def __str__(self):
        return self.name


# =================== ИНФОРМАЦИЯ О ПРОДУКТЕ (по магазину) ===================
class ProductInfo(models.Model):
    model = models.CharField(max_length=80, verbose_name='Модель', blank=True)
    external_id = models.PositiveIntegerField(verbose_name='Внешний ID')
    product = models.ForeignKey(
        Product,
        verbose_name='Продукт',
        related_name='product_infos',
        blank=True,
        on_delete=models.CASCADE
    )
    shop = models.ForeignKey(
        Shop,
        verbose_name='Магазин',
        related_name='product_infos',
        blank=True,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    price = models.DecimalField(
        verbose_name='Цена',
        max_digits=10,
        decimal_places=2
    )
    price_rrc = models.DecimalField(
        verbose_name='Рекомендуемая розничная цена',
        max_digits=10,
        decimal_places=2
    )

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = 'Информационный список о продуктах'
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'shop', 'external_id'],
                name='unique_product_info'
            )
        ]

    def __str__(self):
        return f"{self.product.name} ({self.shop.name})"


# =================== ПАРАМЕТР (характеристика) ===================
class Parameter(models.Model):
    name = models.CharField(max_length=40, verbose_name='Название')

    class Meta:
        verbose_name = 'Имя параметра'
        verbose_name_plural = 'Список имён параметров'
        ordering = ('-name',)

    def __str__(self):
        return self.name


# =================== ЗНАЧЕНИЕ ПАРАМЕТРА ===================
class ProductParameter(models.Model):
    product_info = models.ForeignKey(
        ProductInfo,
        verbose_name='Информация о продукте',
        related_name='product_parameters',
        blank=True,
        on_delete=models.CASCADE
    )
    parameter = models.ForeignKey(
        Parameter,
        verbose_name='Параметр',
        related_name='product_parameters',
        blank=True,
        on_delete=models.CASCADE
    )
    value = models.CharField(verbose_name='Значение', max_length=100)

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Список параметров'
        constraints = [
            models.UniqueConstraint(
                fields=['product_info', 'parameter'],
                name='unique_product_parameter'
            )
        ]

    def __str__(self):
        return f"{self.parameter.name}: {self.value}"


# =================== КОНТАКТ ПОЛЬЗОВАТЕЛЯ ===================
class Contact(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        related_name='contacts',
        blank=True,
        on_delete=models.CASCADE
    )
    city = models.CharField(max_length=50, verbose_name='Город')
    street = models.CharField(max_length=100, verbose_name='Улица')
    house = models.CharField(max_length=15, verbose_name='Дом', blank=True)
    structure = models.CharField(max_length=15, verbose_name='Корпус', blank=True)
    building = models.CharField(max_length=15, verbose_name='Строение', blank=True)
    apartment = models.CharField(max_length=15, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон')

    class Meta:
        verbose_name = 'Контакт пользователя'
        verbose_name_plural = 'Список контактов пользователя'

    def __str__(self):
        return f'{self.city}, {self.street}, {self.house}'


# =================== ЗАКАЗ ===================
class Order(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name='Пользователь',
        related_name='orders',
        blank=True,
        on_delete=models.CASCADE
    )
    dt = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    state = models.CharField(
        verbose_name='Статус',
        choices=STATE_CHOICES,
        max_length=15
    )
    contact = models.ForeignKey(
        Contact,
        verbose_name='Контакт',
        blank=True,
        null=True,
        on_delete=models.CASCADE
    )

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Список заказов'
        ordering = ('-dt',)

    def __str__(self):
        return f'Заказ #{self.id} — {self.state}'


# =================== ПОЗИЦИЯ В ЗАКАЗЕ ===================
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name='Заказ',
        related_name='ordered_items',
        blank=True,
        on_delete=models.CASCADE
    )
    product_info = models.ForeignKey(
        ProductInfo,
        verbose_name='Информация о продукте',
        related_name='ordered_items',
        blank=True,
        on_delete=models.CASCADE
    )
    quantity = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        verbose_name = 'Заказанная позиция'
        verbose_name_plural = 'Список заказанных позиций'
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'product_info'],
                name='unique_order_item'
            )
        ]

    def __str__(self):
        return f'{self.quantity} × {self.product_info.product.name}'


# =================== ТОКЕН ПОДТВЕРЖДЕНИЯ EMAIL ===================
class ConfirmEmailToken(models.Model):
    """
    Модель для хранения токенов подтверждения email
    """
    class Meta:
        verbose_name = 'Токен подтверждения Email'
        verbose_name_plural = 'Токены подтверждения Email'

    @staticmethod
    def generate_key():
        """
        Генерирует URL-безопасный токен длиной 32 байта
        """
        return secrets.token_urlsafe(32)

    user = models.ForeignKey(
        User,
        related_name='confirm_email_tokens',
        on_delete=models.CASCADE,
        verbose_name="Пользователь"
    )
    key = models.CharField(
        _("Key"),
        max_length=64,
        db_index=True,
        unique=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        # Защита от ручного изменения ключа
        if 'key' in kwargs.get('update_fields', []):
            raise ValueError("Нельзя изменять ключ токена вручную.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Токен для {self.user.email}"