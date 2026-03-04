from django.test import TestCase
from .models import Product


class ProductModelTest(TestCase):
    def setUp(self):
        Product.objects.create(name="Тестовый продукт", price=99.99)

    def test_product_str(self):
        product = Product.objects.get(name="Тестовый продукт")
        self.assertEqual(str(product), "Тестовый продукт")