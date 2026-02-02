# -*- coding: utf-8 -*-
"""Кастомный логгер с поддержкой вывода в GUI"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import queue


class QueueHandler(logging.Handler):
    """Обработчик для передачи логов в очередь (для потокобезопасности)"""

    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put_nowait(record)


class GuiLogger:
    """Основной класс логгера приложения"""

    def __init__(self, app_name: str = "VK Collector"):
        self.app_name = app_name
        self.log_queue = queue.Queue()
        self._setup_logging()

    def _setup_logging(self):
        """Настройка логирования в файл + очередь для GUI"""
        # Создаём директорию для логов
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Имя файла с датой
        log_file = log_dir / f"vk_collector_{datetime.now().strftime('%Y%m%d')}.log"

        # Основной логгер
        self.logger = logging.getLogger(self.app_name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()  # Очищаем дублирующиеся хендлеры

        # Форматтер
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Хендлер для файла
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Хендлер для консоли (только ошибки)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Хендлер для очереди (для GUI)
        queue_handler = QueueHandler(self.log_queue)
        queue_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(queue_handler)

    def get_logger(self) -> logging.Logger:
        return self.logger

    def get_queue(self) -> queue.Queue:
        return self.log_queue

    # Удобные методы для логирования
    def info(self, msg: str, **kwargs):
        self.logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self.logger.error(msg, **kwargs)

    def success(self, msg: str, **kwargs):
        """Кастомный уровень 'успех' (зелёный в GUI)"""
        self.logger.info(f"✅ {msg}", **kwargs)