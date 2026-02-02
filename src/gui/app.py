# -*- coding: utf-8 -*-
"""Главное окно приложения с вкладками и лог-панелью"""
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime, timedelta
from pathlib import Path
import queue
import threading
from ..utils.config import AppConfig
from ..utils.logger import GuiLogger
from ..core.vk_client import VKClient
from ..utils.security import hash_token_for_display
from ..core.excel_exporter import ExcelExporter


class VKCollectorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VK Post Collector")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        # Иконка (опционально)
        try:
            icon_path = Path(__file__).parent.parent.parent / "resources" / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass  # Иконка не критична

        # Инициализация конфига и логгера
        self.config = AppConfig()
        self.gui_logger = GuiLogger()
        self.logger = self.gui_logger.get_logger()

        # Очередь для потокобезопасного логирования
        self.log_queue = self.gui_logger.get_queue()

        # Токен и клиент ВК
        self.vk_token = self.config.get_token() or ""
        self.vk_client = None

        # Состояние сбора
        self.collection_thread = None
        self.is_collecting = False

        # Создаём интерфейс
        self._create_widgets()
        self._load_saved_settings()

        # Запускаем обработчик очереди логов
        self.root.after(100, self._process_log_queue)

    def _create_widgets(self):
        """Создание всех виджетов интерфейса"""
        # Верхняя панель статуса
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 5))

        # Основной контейнер с вкладками
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка 1: Настройки
        self.settings_frame = ttk.Frame(notebook)
        notebook.add(self.settings_frame, text="Настройки")
        self._create_settings_tab()

        # Вкладка 2: Запуск
        self.run_frame = ttk.Frame(notebook)
        notebook.add(self.run_frame, text="Запуск")
        self._create_run_tab()

    def _create_settings_tab(self):
        """Создание вкладки 'Настройки'"""
        # Токен
        token_frame = ttk.LabelFrame(self.settings_frame, text="Токен доступа ВКонтакте", padding=10)
        token_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(token_frame, text="User Access Token:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.token_entry = ttk.Entry(token_frame, width=50, show="•")
        self.token_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)

        # Контекстное меню для вставки (решение проблемы с маскировкой)
        token_menu = tk.Menu(self.token_entry, tearoff=0)
        token_menu.add_command(label="Вставить", command=lambda: self.token_entry.event_generate("<<Paste>>"))
        token_menu.add_command(label="Копировать", command=lambda: self.token_entry.event_generate("<<Copy>>"))
        token_menu.add_command(label="Вырезать", command=lambda: self.token_entry.event_generate("<<Cut>>"))

        def show_token_menu(event):
            token_menu.tk_popup(event.x_root, event.y_root)

        self.token_entry.bind("<Button-3>", show_token_menu)  # ПКМ на Windows
        self.token_entry.bind("<Button-2>", show_token_menu)  # Средняя кнопка на Linux

        ttk.Button(token_frame, text="Проверить токен", command=self._verify_token).grid(row=0, column=2, padx=5,
                                                                                         pady=5)

        self.remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(token_frame, text="Запомнить токен (в защищённом хранилище)", variable=self.remember_var).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, pady=5
        )

        token_frame.columnconfigure(1, weight=1)

        # Группы
        groups_frame = ttk.LabelFrame(self.settings_frame, text="Список групп (до 30)", padding=10)
        groups_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(groups_frame,
                  text="Введите группы (по одной на строку):\nМожно использовать цифровые ID (-123456789) или короткие имена (example_group)").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=5
        )

        self.groups_text = tk.Text(groups_frame, height=8, width=60)
        self.groups_text.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        # Контекстное меню для поля групп
        groups_menu = tk.Menu(self.groups_text, tearoff=0)
        groups_menu.add_command(label="Вставить", command=lambda: self.groups_text.event_generate("<<Paste>>"))
        groups_menu.add_command(label="Копировать", command=lambda: self.groups_text.event_generate("<<Copy>>"))
        groups_menu.add_command(label="Вырезать", command=lambda: self.groups_text.event_generate("<<Cut>>"))

        def show_groups_menu(event):
            groups_menu.tk_popup(event.x_root, event.y_root)

        self.groups_text.bind("<Button-3>", show_groups_menu)  # ПКМ на Windows
        self.groups_text.bind("<Button-2>", show_groups_menu)  # Средняя кнопка на Linux

        ttk.Button(groups_frame, text="Загрузить из файла", command=self._load_groups_from_file).grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=5
        )
        ttk.Button(groups_frame, text="Очистить", command=lambda: self.groups_text.delete("1.0", tk.END)).grid(
            row=2, column=1, sticky=tk.E, padx=5, pady=5
        )

        groups_frame.columnconfigure(0, weight=1)
        groups_frame.columnconfigure(1, weight=1)
        groups_frame.rowconfigure(1, weight=1)

        # Период и директория
        bottom_frame = ttk.Frame(self.settings_frame)
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)

        # Даты
        date_frame = ttk.LabelFrame(bottom_frame, text="Период сбора", padding=10)
        date_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Label(date_frame, text="С:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.date_from = DateEntry(date_frame, width=12, background='darkblue', foreground='white', borderwidth=2,
                                   date_pattern='dd.mm.yyyy')
        self.date_from.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text="По:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.date_to = DateEntry(date_frame, width=12, background='darkblue', foreground='white', borderwidth=2,
                                 date_pattern='dd.mm.yyyy')
        self.date_to.grid(row=1, column=1, padx=5, pady=5)

        # Директория
        dir_frame = ttk.LabelFrame(bottom_frame, text="Директория сохранения", padding=10)
        dir_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.output_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True,
                                                                              padx=(0, 5))
        ttk.Button(dir_frame, text="Выбрать...", command=self._select_output_dir).pack(side=tk.LEFT)

    def _create_run_tab(self):
        """Создание вкладки 'Запуск'"""
        # Кнопка запуска
        control_frame = ttk.Frame(self.run_frame)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_btn = ttk.Button(control_frame, text="▶️ Старт сбора", command=self._start_collection,
                                    style="Accent.TButton")
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(control_frame, text="⏹️ Остановить", command=self._stop_collection,
                                   state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="📁 Открыть папку с результатами", command=self._open_output_dir).pack(
            side=tk.RIGHT, padx=5)

        # Прогресс-бар
        progress_frame = ttk.Frame(self.run_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, expand=True)

        self.progress_label = ttk.Label(progress_frame, text="Готов к сбору")
        self.progress_label.pack(anchor=tk.W, pady=(5, 0))

        # Лог-панель
        log_frame = ttk.LabelFrame(self.run_frame, text="Лог процесса", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Стилизация текста в логе
        self.log_text = tk.Text(log_frame, height=15, width=80, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # Теги для цветового выделения
        self.log_text.tag_configure("success", foreground="green", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("warning", foreground="orange", font=("Consolas", 9))
        self.log_text.tag_configure("error", foreground="red", font=("Consolas", 9, "bold"))
        self.log_text.tag_configure("info", foreground="black", font=("Consolas", 9))
        self.log_text.tag_configure("debug", foreground="gray", font=("Consolas", 9))

        # Запрет редактирования
        self.log_text.configure(state=tk.DISABLED)

    def _load_saved_settings(self):
        """Загрузка сохранённых настроек из конфига"""
        # Токен (только хеш для отображения)
        if self.vk_token:
            self.token_entry.delete(0, tk.END)
            self.token_entry.insert(0, "•" * 32)
            self.gui_logger.info(f"Загружен сохранённый токен (хеш: {hash_token_for_display(self.vk_token)})")

        # Группы
        last_groups = self.config.get_last_groups()
        if last_groups:
            self.groups_text.delete("1.0", tk.END)
            self.groups_text.insert("1.0", "\n".join(last_groups))

        # Директория
        last_dir = self.config.get_last_output_dir()
        self.output_dir_var.set(last_dir)

        # Даты (по умолчанию: последние 7 дней)
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        self.date_from.set_date(week_ago)
        self.date_to.set_date(today)

    def _verify_token(self):
        """Проверка токена через API ВК"""
        token = self.token_entry.get().strip().replace("•", "")
        if not token:
            messagebox.showwarning("Внимание", "Введите токен для проверки")
            return

        try:
            # Создаём временный клиент
            temp_client = VKClient(token)
            user_info = temp_client.get_user_info()

            if user_info:
                self.vk_token = token
                if self.remember_var.get():
                    self.config.save_token(token, remember=True)
                    self.gui_logger.success(f"Токен сохранён для пользователя {user_info}")
                else:
                    self.config.save_token(token, remember=False)
                    self.gui_logger.info(f"Токен проверен для пользователя {user_info} (не сохранён)")

                messagebox.showinfo("Успех", f"Токен действителен!\nПользователь: {user_info}")
                # Маскируем токен в поле ввода
                self.token_entry.delete(0, tk.END)
                self.token_entry.insert(0, "•" * len(token))
            else:
                raise Exception("Не удалось получить данные пользователя")

        except Exception as e:
            self.gui_logger.error(f"Ошибка проверки токена: {e}")
            messagebox.showerror("Ошибка", f"Неверный токен или недостаточно прав:\n{e}")

    def _load_groups_from_file(self):
        """Загрузка списка групп из файла"""
        file_path = filedialog.askopenfilename(
            title="Выберите файл со списком групп",
            filetypes=[("Текстовые файлы", "*.txt"), ("Все файлы", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    groups = [line.strip() for line in f if line.strip()]
                self.groups_text.delete("1.0", tk.END)
                self.groups_text.insert("1.0", "\n".join(groups[:30]))  # Ограничение 30 групп
                self.gui_logger.success(f"Загружено {len(groups)} групп из файла {Path(file_path).name}")
            except Exception as e:
                self.gui_logger.error(f"Ошибка загрузки файла: {e}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{e}")

    def _select_output_dir(self):
        """Выбор директории для сохранения результатов"""
        dir_path = filedialog.askdirectory(title="Выберите папку для сохранения отчётов")
        if dir_path:
            self.output_dir_var.set(dir_path)
            self.config.save_last_output_dir(dir_path)

    def _open_output_dir(self):
        """Открытие директории с результатами в проводнике Windows"""
        output_dir = self.output_dir_var.get().strip()
        if not output_dir or not Path(output_dir).exists():
            output_dir = self.config.get_last_output_dir()

        try:
            import os
            os.startfile(output_dir)  # Только для Windows
        except Exception as e:
            self.gui_logger.warning(f"Не удалось открыть папку: {e}")
            messagebox.showinfo("Информация", f"Папка: {output_dir}")

    def _start_collection(self):
        """Запуск сбора постов в отдельном потоке"""
        # Валидация входных данных
        if not self.vk_token:
            messagebox.showwarning("Внимание", "Сначала проверьте и сохраните токен!")
            return

        groups_raw = self.groups_text.get("1.0", tk.END).strip().splitlines()
        groups = [g.strip() for g in groups_raw if g.strip()]

        if not groups:
            messagebox.showwarning("Внимание", "Введите хотя бы одну группу для сбора!")
            return

        if len(groups) > 30:
            if not messagebox.askyesno("Подтверждение",
                                       f"Указано {len(groups)} групп (макс. 30). Обработать только первые 30?"):
                return
            groups = groups[:30]

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            output_dir = self.config.get_last_output_dir()
            self.output_dir_var.set(output_dir)

        try:
            date_from = self.date_from.get_date()
            date_to = self.date_to.get_date()
            if date_from > date_to:
                raise ValueError("Дата 'С' не может быть позже даты 'По'")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Неверный период:\n{e}")
            return

        # Сохраняем настройки
        self.config.save_last_groups(groups)
        self.config.save_last_output_dir(output_dir)

        # Блокируем интерфейс
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("Сбор данных...")
        self.progress_var.set(0.0)
        self.progress_label.config(text="Начинаем сбор...")

        # Запускаем поток сбора
        self.is_collecting = True
        self.collection_thread = threading.Thread(
            target=self._collection_worker,
            args=(groups, date_from, date_to, output_dir),
            daemon=True
        )
        self.collection_thread.start()

    def _collection_worker(self, groups: list, date_from: datetime, date_to: datetime, output_dir: str):
        """Рабочая функция сбора данных (выполняется в отдельном потоке)"""
        all_posts = []  # Собираем все посты для единого экспорта

        try:
            # Инициализируем клиент ВК
            self.vk_client = VKClient(self.vk_token)
            total_groups = len(groups)

            for idx, group in enumerate(groups, 1):
                if not self.is_collecting:
                    self.gui_logger.warning("Сбор остановлен пользователем")
                    return

                # Обновляем прогресс
                progress = (idx - 1) / total_groups * 100
                self.root.after(0, lambda p=progress, g=group: self._update_progress(p,
                                                                                     f"Обработка группы {g} ({idx}/{total_groups})"))

                try:
                    self.gui_logger.info(f"Начинаем сбор постов из группы: {group}")
                    posts = self.vk_client.get_posts_from_group(
                        group_id=group,
                        date_from=date_from,
                        date_to=date_to
                    )
                    self.gui_logger.success(f"Получено {len(posts)} постов из группы {group}")
                    all_posts.extend(posts)  # Добавляем посты в общий список

                except Exception as e:
                    self.gui_logger.error(f"Ошибка при сборе группы {group}: {e}")
                    continue

            # Экспорт в Excel после сбора всех групп
            if all_posts and self.is_collecting:
                self.gui_logger.info(f"Экспортируем {len(all_posts)} постов в Excel...")
                exporter = ExcelExporter(output_dir, self.gui_logger)
                excel_path = exporter.export_posts(all_posts)
                self.gui_logger.success(f"✅ Данные сохранены в: {excel_path}")

            # Завершение
            if self.is_collecting:
                self.root.after(0, lambda: self._finish_collection(success=True, posts_count=len(all_posts)))
            else:
                self.root.after(0, lambda: self._finish_collection(success=False, cancelled=True))

        except Exception as e:
            self.gui_logger.error(f"Критическая ошибка сбора: {e}")
            self.root.after(0, lambda: self._finish_collection(success=False, error=str(e)))

    def _update_progress(self, value: float, label: str):
        """Обновление прогресс-бара и метки (вызывается из основного потока)"""
        self.progress_var.set(value)
        self.progress_label.config(text=label)

    def _finish_collection(self, success: bool, cancelled: bool = False, error: str = None, posts_count: int = 0):
        """Завершение сбора и разблокировка интерфейса"""
        self.is_collecting = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        if cancelled:
            self.status_var.set("Сбор остановлен пользователем")
            self.gui_logger.warning("Сбор данных прерван пользователем")
        elif success:
            self.status_var.set(f"Сбор завершён! Сохранено {posts_count} постов")
            self.gui_logger.success(f"✅ Сбор данных завершён успешно! Сохранено {posts_count} постов")
            self.progress_var.set(100.0)
            self.progress_label.config(text="Готово!")
        else:
            self.status_var.set(f"Ошибка: {error}")
            self.gui_logger.error(f"❌ Сбор завершился с ошибкой: {error}")

    def _stop_collection(self):
        """Остановка сбора по нажатию кнопки"""
        self.is_collecting = False
        self.status_var.set("Остановка сбора...")
        self.gui_logger.warning("Пользователь запросил остановку сбора")

    def _process_log_queue(self):
        """Обработка очереди логов для вывода в GUI (вызывается периодически)"""
        # Обрабатываем все сообщения в очереди
        while not self.log_queue.empty():
            try:
                record = self.log_queue.get_nowait()
                msg = self._format_log_record(record)

                # Определяем тег для цвета
                tag = "info"
                if record.levelno >= logging.ERROR:
                    tag = "error"
                elif record.levelno >= logging.WARNING:
                    tag = "warning"
                elif "✅" in msg or "успешно" in msg.lower():
                    tag = "success"

                # Выводим в текстовое поле
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.insert(tk.END, msg + "\n", tag)
                self.log_text.see(tk.END)  # Прокрутка вниз
                self.log_text.configure(state=tk.DISABLED)

            except queue.Empty:
                break
            except Exception as e:
                print(f"Ошибка вывода лога: {e}")

        # Планируем следующую проверку
        self.root.after(100, self._process_log_queue)

    def _format_log_record(self, record: logging.LogRecord) -> str:
        """Форматирование записи лога для отображения в GUI"""
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        level = record.levelname[0]  # 'I', 'W', 'E'
        return f"[{timestamp}] [{level}] {record.getMessage()}"