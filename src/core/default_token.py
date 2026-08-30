"""Ваш постоянный токен (Base64)"""
import base64


def get_default_token() -> str:
    """Возвращает токен по умолчанию"""
    encoded_token = "MjhiOTQyY2QyOGI5NDJjZDI4Yjk0MmNkOGIyYjg3ZTFjNzIyOGI5MjhiOTQyY2Q0MWM1Nzg3NmViOTZmYzQ1YmJiMDk4MDE="

    try:
        return base64.b64decode(encoded_token).decode('utf-8')
    except Exception:
        return ""