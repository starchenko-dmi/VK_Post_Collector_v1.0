"""Ваш постоянный токен с базовой обфускацией"""
import base64


def get_default_token() -> str:
    """Возвращает токен по умолчанию"""
    # СЮДА ВСТАВЬТЕ ТОЛЬКО BASE64-КОДИРОВАННУЮ СТРОКУ (без кавычек реального токена!)
    encoded_token = "MjhiOTQyY2QyOGI5NDJjZDI4Yjk0MmNkOGIyYjg3ZTFjNzIyOGI5MjhiOTQyY2Q0MWM1Nzg3NmViOTZmYzQ1YmJiMDk4MDE="

    try:
        decoded = base64.b64decode(encoded_token).decode('utf-8')
        return decoded
    except:
        return ""