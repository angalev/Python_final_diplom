from django.http import HttpResponse


def index(request):
    """
    Простая приветственная страница
    """
    html = """
    <h1>🛍️ Добро пожаловать в интернет-магазин!</h1>
    <p>Проект на Django + DRF. Готов к работе.</p>
    <ul>
        <li><a href="/api/">👉 Перейти к API</a></li>
        <li><a href="/admin/">👉 Админка</a></li>
    </ul>
    <hr>
    <small>Финальный дипломный проект • 2026</small>
    """
    return HttpResponse(html)