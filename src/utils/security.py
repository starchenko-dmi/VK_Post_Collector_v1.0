# -*- coding: utf-8 -*-
"""Базовая обфускация токена (защита от случайного просмотра)"""
import base64
import os
import getpass
import hashlib

def _get_salt() -> str:
    """Генерация соли из уникальных данных пользователя Windows"""
    computer = os.environ.get("COMPUTERNAME", "DEFAULT_PC")
    user = getpass.getuser()
    static_salt = "VK_COLLECTOR_2026_SECRET_SALT"
    return f"{computer}_{user}_{static_salt}"

def obfuscate_token(token: str) -> str:
    """Простая обфускация токена через base64 + соль"""
    salt = _get_salt()
    # Добавляем соль в начало и конец для усложнения реверса
    obfuscated = f"{salt[:8]}{token}{salt[-8:]}"
    return base64.b64encode(obfuscated.encode("utf-8")).decode("utf-8")

def deobfuscate_token(obfuscated: str) -> str | None:
    """Восстановление токена из обфусцированной строки"""
    try:
        salt = _get_salt()
        decoded = base64.b64decode(obfuscated).decode("utf-8")
        # Удаляем соль с обеих сторон
        if decoded.startswith(salt[:8]) and decoded.endswith(salt[-8:]):
            return decoded[len(salt[:8]):-len(salt[-8:])]
        return None
    except Exception:
        return None

def hash_token_for_display(token: str) -> str:
    """Хеширование токена для отображения в логах (первые 8 символов)"""
    return hashlib.sha256(token.encode()).hexdigest()[:8] + "..."