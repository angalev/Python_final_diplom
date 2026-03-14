# Интернет-магазин на Django

Это REST API интернет-магазина, реализованный на **Django**
Поддерживает регистрацию пользователей с подтверждением email, авторизацию по токену, управление профилем, корзиной, заказами и функционал для поставщиков.


---

##  Основные возможности

-  **Регистрация и подтверждение email** через одноразовый токен
-  **Авторизация по токену** (`TokenAuthentication`)
-  Управление профилем: просмотр и обновление данных
-  Контакты доставки: добавление, редактирование, удаление
-  Корзина: добавление, изменение количества, удаление товаров
-  Оформление заказа с указанием контакта
-  Панель поставщика:
  - Загрузка прайса из YAML-файла
  - Управление статусом приёма заказов
  - Просмотр всех заказов своего магазина
-  Просмотр категорий и магазинов
-  Поиск товаров по магазину и категории

---

## Технологии

- **Python 3.12**
- **Django**
- **Django REST Framework**
- **SQLite**
- **PyYAML** 
- **requests** 
- **python-dotenv** 
- **Django Token Authentication**

---

## Установка и запуск

### 1. Клонируйте репозиторий
```
git clone https://github.com/angalev/Python_final_diplom.git && cd python_final_diplom
```

### 2. Создайте и активируйте виртуальное окружение
```
python -m venv venv 
venv\Scripts\activate
```
### 3. Установите зависимости
```
pip install -r requirements.txt 
 ```
### 4. Настройте переменные окружения

Создайте файл `.env` в корне проекта:
```
SECRET_KEY=ваш_секретный_ключ
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```
## Настройки почты (пример для сервиса MailYandex)
```
EMAIL_HOST_USER=your_mail@yandex.ru
EMAIL_HOST_PASSWORD=ваш_пароль_почты
EMAIL_HOST=smtp.yandex.ru 
EMAIL_PORT=465 
EMAIL_USE_SSL=True
DEFAULT_FROM_EMAIL=your_mail@yandex.ru
```

#### Для Yandex: используйте **пароль приложения**, а не основной пароль аккаунта.

---

### 5. Выполните миграции
```
python manage.py makemigrations
python manage.py migrate
```
### 6. (Опционально) Создайте суперпользователя
```
python manage.py createsuperuser
```
Доступ по адресу: http://localhost:8000/admin/

### 7. Запустите сервер
```
python manage.py runserver
```
API будет доступно по адресу:  
 [http://localhost:8000/api/](http://localhost:8000/api/)

---

##  Основные эндпоинты API

| №  | Метод | Эндпоинт | Описание |
|----|-------|---------|--------|
| 1  | POST | `/api/user/register/` | Регистрация нового пользователя |
| 2  | GET | `/api/user/confirm/?token=...` | Подтверждение email (одноразовый токен) |
| 3  | POST | `/api/user/login/` | Вход → получение токена |
| 4  | GET/PATCH | `/api/user/details/` | Получение и обновление профиля |
| 5  | GET/POST/PUT/DELETE | `/api/user/contact/` | Управление контактами доставки |
| 6  | GET/POST/PUT/DELETE | `/api/basket/` | Работа с корзиной |
| 7  | GET/POST | `/api/order/` | Просмотр и оформление заказа |
| 8  | POST | `/api/partner/update/` | Обновление прайса поставщика (YAML) |
| 9  | GET/POST | `/api/partner/state/` | Управление статусом приёма заказов |
| 10 | GET | `/api/partner/orders/` | Просмотр заказов магазина |
| 11 | GET | `/api/categories/` | Список категорий |
| 12 | GET | `/api/shops/` | Список магазинов |
| 13 | GET | `/api/products/` | Поиск товаров (по shop_id, category_id) |

---

##  Безопасность подтверждения email

При регистрации:
1. Пользователь получает **одноразовый токен** (`ConfirmEmailToken`)
2. Ссылка: `http://localhost:8000/api/user/confirm/?token=abc123...`
3. После перехода:
   - Аккаунт активируется
   - Токен **удаляется из базы**
   - Повторное использование невозможно (`404 Not Found`)



---

##  Примеры запросов

### 1. Регистрация
```
POST /api/user/register/ Content-Type: application/json
{ "first_name": "Анна", "last_name": "Петрова", "email": "anna@example.com",
"password": "secure123", "company": "Торговый дом", "position": "Закупщик" }
```
### 2. Активация (из письма)
```
GET /api/user/confirm/?token=abc123def456...
```
### 3. Вход
```
POST /api/user/login/ Content-Type: application/json
{ "email": "anna@example.com", "password": "secure123" }
```
**Ответ:**
```
json { "Status": true, "Token": "9f4a3b2c1d0e8f7a6b5c4d3e2f1a0b9c8d7e6f5a" }
```
### 4. Получение профиля
```
GET /api/user/details/ Authorization: Token
9f4a3b2c1d0e8f7a6b5c4d3e2f1a0b9c8d7e6f5a
```
### 5. Управление статусом магазина
```
POST /api/partner/state/ Authorization: Token
9f4a3b2c1d0e8f7a6b5c4d3e2f1a0b9c8d7e6f5a Content-Type: application/json
{ "state": true }
```
---

##  Структура проекта
```
Python_final_diplom/
├── Python_final_diplom/
│   ├── data/
│   │   └── shop1.yaml
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   └── wsgi.py
├── backend/
│   ├── migrations/
│   │   └── __init__.py
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── serializers.py
│   ├── signals.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── README.md
├── manage.py
└── requirements.txt
```
Автор: **Михаил Ангалев**  
Email: miha-angalev@yandex.ru  
Дата завершения: март 2026  
Название курса: Финальный дипломный проект по Python