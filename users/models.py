from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField('Email', unique=True)
    company = models.CharField('Компания', max_length=100, blank=True)
    position = models.CharField('Должность', max_length=100, blank=True)

    TYPE_CHOICES = (
        ('client', 'Клиент'),
        ('shop', 'Поставщик'),
    )
    type = models.CharField('Тип пользователя', choices=TYPE_CHOICES, max_length=10, default='client')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email