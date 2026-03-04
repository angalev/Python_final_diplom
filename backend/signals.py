# Пример: обработка сигналов (например, после создания продукта)
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product


@receiver(post_save, sender=Product)
def log_product_creation(sender, instance, created, **kwargs):
    if created:
        print(f"Новый продукт создан: {instance.name}")