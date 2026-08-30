# -*- coding: utf-8 -*-
"""Обфускация токена (простой Base64 - работает на любом компьютере)"""
import base64
import hashlib


def obfuscate_token(token: str) -> str:
    """Обфускация токена через Base64"""
    try:
        return base64.b64encode(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def deobfuscate_token(obfuscated: str) -> str | None:
    """Восстановление токена из Base64"""
    try:
        if not obfuscated:
            return None
        return base64.b64decode(obfuscated).decode("utf-8")
    except Exception:
        return None


def hash_token_for_display(token: str) -> str:
    """Хеширование токена для отображения в логах (первые 8 символов)"""
    try:
        return hashlib.sha256(token.encode()).hexdigest()[:8] + "..."
    except Exception:
        return "unknown..."