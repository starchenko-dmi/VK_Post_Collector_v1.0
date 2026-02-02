# -*- coding: utf-8 -*-
"""Точка входа в приложение VK Post Collector (с отладкой)"""
import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import traceback
from pathlib import Path

# Отладка: выводим информацию об окружении
print("=" * 60)
print("VK Post Collector — Отладочная информация")
print("=" * 60)
print(f"Python: {sys.version}")
print(f"Рабочая директория: {os.getcwd()}")
print(f"Путь к скрипту: {__file__}")
print(f"Аргументы командной строки: {sys.argv}")
print("=" * 60)

# Настройка путей для корректной работы
if getattr(sys, 'frozen', False):
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).parent.parent

print(f"Корневая директория проекта: {application_path}")
print("=" * 60)

# Устанавливаем кодировку для консоли Windows (чтобы не было кракозябр)
if sys.platform == "win32":
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except:
        pass


def main():
    """Основная функция запуска приложения"""
    root = None
    try:
        print("Создаём главное окно Tkinter...")
        root = tk.Tk()
        root.title("VK Post Collector")
        root.geometry("900x700")
        root.minsize(800, 600)

        # Настройка стиля
        style = ttk.Style()
        if sys.platform == "win32":
            available_themes = style.theme_names()
            print(f"Доступные темы Tkinter: {available_themes}")
            if 'vista' in available_themes:
                style.theme_use('vista')
                print("Используем тему: vista")
            elif 'clam' in available_themes:
                style.theme_use('clam')
                print("Используем тему: clam")

        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

        # Импорт приложения
        print("Импортируем VKCollectorApp...")
        from src.gui.app import VKCollectorApp

        print("Создаём экземпляр приложения...")
        app = VKCollectorApp(root)

        # Обработчик закрытия
        def on_closing():
            if hasattr(app, 'is_collecting') and app.is_collecting:
                if messagebox.askokcancel("Подтверждение", "Сбор данных ещё идёт. Закрыть приложение?"):
                    app.is_collecting = False
                    root.destroy()
            else:
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        print("\n✅ Приложение успешно инициализировано!")
        print("Запускаем главный цикл Tkinter...\n")
        print("=" * 60)
        print("ОКНО ПРИЛОЖЕНИЯ ДОЛЖНО ПОЯВИТЬСЯ СЕЙЧАС")
        print("=" * 60)

        root.mainloop()

    except Exception as e:
        error_msg = f"КРИТИЧЕСКАЯ ОШИБКА:\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        print("\n" + "=" * 60)
        print(error_msg)
        print("=" * 60)

        # Показываем ошибку в GUI, если возможно
        try:
            if root is None:
                root = tk.Tk()
                root.withdraw()
            messagebox.showerror("Ошибка запуска", error_msg)
            if root:
                root.destroy()
        except:
            # Если и это не сработало — выводим в консоль
            print("\nНЕВОЗМОЖНО ОТОБРАЗИТЬ ОКНО ОШИБКИ. СКОПИРУЙТЕ ТЕКСТ ВЫШЕ.")

        sys.exit(1)


if __name__ == "__main__":
    main()