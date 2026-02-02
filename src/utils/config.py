# -*- coding: utf-8 -*-
"""Работа с конфигурацией в защищённой директории пользователя"""
import json
import os
import sys
from pathlib import Path
from typing import Optional, List
from .security import obfuscate_token, deobfuscate_token, hash_token_for_display

class AppConfig:
    def __init__(self):
        # Путь к защищённой директории в AppData/Roaming (Windows)
        self.config_dir = Path(os.getenv("APPDATA", "~")) / ".vk_collector"
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()
        self.data = self._load_config()


    def _ensure_config_dir(self):
        """Создаём директорию с правами только для текущего пользователя (с защитой от пробелов)"""
        # Используем AppData/Roaming — стандартное место для конфигов в Windows
        appdata = os.getenv("APPDATA")
        if not appdata:
            # Резервный вариант для не-Windows систем
            appdata = os.path.expanduser("~")

        # Критически важно: путь без пробелов в имени папки!
        self.config_dir = Path(appdata) / "VK_Collector_Config"  # ← Без точки в начале!
        self.config_file = self.config_dir / "config.json"

        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Конфигурация сохраняется в: {self.config_dir}")
        except Exception as e:
            print(f"⚠️  Ошибка создания директории конфига: {e}")
            # Резервный путь — рядом с проектом (не идеально, но работает)
            fallback_dir = Path.cwd() / ".vk_collector_safe"
            fallback_dir.mkdir(exist_ok=True)
            self.config_dir = fallback_dir
            self.config_file = self.config_dir / "config.json"
            print(f"→ Используем резервную директорию: {self.config_dir}")

    def _load_config(self) -> dict:
        """Загрузка конфига или создание пустого"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_config(self):
        """Сохранение конфига"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def save_token(self, token: str, remember: bool = True):
        """Сохранение токена (если выбрана опция 'Запомнить')"""
        if remember:
            self.data["obfuscated_token"] = obfuscate_token(token)
            self.data["token_hash"] = hash_token_for_display(token)
            self._save_config()

    def get_token(self) -> Optional[str]:
        """Получение токена из конфига"""
        obfuscated = self.data.get("obfuscated_token")
        if obfuscated:
            return deobfuscate_token(obfuscated)
        return None

    def save_last_groups(self, groups: List[str]):
        """Сохранение последних использованных групп"""
        self.data["last_groups"] = groups[:30]  # Ограничение 30 групп
        self._save_config()

    def get_last_groups(self) -> List[str]:
        """Получение последних групп"""
        return self.data.get("last_groups", [])

    def save_last_output_dir(self, path: str):
        """Сохранение последней директории вывода"""
        self.data["last_output_dir"] = path
        self._save_config()

    def get_last_output_dir(self) -> str:
        """Получение последней директории вывода"""
        return self.data.get("last_output_dir", str(Path.home() / "Desktop"))