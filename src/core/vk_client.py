# -*- coding: utf-8 -*-
"""Клиент для работы с ВКонтакте API"""
import time
import re
from datetime import datetime, timezone, date as date_type
import logging
import vk_api
from vk_api.exceptions import ApiError


class VKClient:
    def __init__(self, token: str):
        self.token = token
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.last_request_time = 0
        self.rate_limit_delay = 0.25  # 0.25 сек = 4 запроса/сек (безопасный лимит)

        # Инициализация внутреннего логгера
        self.logger = logging.getLogger(__name__)

    def _respect_rate_limit(self):
        """Соблюдение рейт-лимита ВКонтакте"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def get_user_info(self) -> str:
        """Получение информации о пользователе для проверки токена"""
        self._respect_rate_limit()
        try:
            response = self.vk.users.get()
            if response and len(response) > 0:
                user = response[0]
                return f"{user.get('first_name', '')} {user.get('last_name', '')} (id{user.get('id', '')})"
            return "Неизвестный пользователь"
        except Exception as e:
            raise Exception(f"Ошибка получения данных пользователя: {e}")

    def resolve_group_id(self, group_identifier: str) -> int:
        """Преобразование короткого имени группы в цифровой ID"""
        self._respect_rate_limit()
        try:
            # Если уже цифровой ID (с минусом для групп)
            if group_identifier.lstrip('-').isdigit():
                return int(group_identifier)

            # Иначе — поиск через группы
            response = self.vk.groups.getById(group_id=group_identifier)
            if response and len(response) > 0:
                return -response[0]['id']  # Группы имеют отрицательные ID
            raise ValueError(f"Группа '{group_identifier}' не найдена")
        except ApiError as e:
            if e.code == 15:  # Доступ запрещён (приватная группа)
                raise Exception(f"Группа '{group_identifier}' приватная или недоступна")
            elif e.code == -1113:  # Неверный идентификатор сообщества
                raise Exception(f"Группа '{group_identifier}' не существует")
            raise Exception(f"Ошибка ВКонтакте ({e.code}): {e}")
        except Exception as e:
            raise Exception(f"Ошибка определения группы: {e}")

    def get_posts_from_group(
            self,
            group_id: str,
            date_from: date_type,
            date_to: date_type
    ) -> list:
        """
        Получение постов из группы за период с пагинацией.

        Возвращает список постов в формате:
        {
            'group_id': int,
            'group_name': str,
            'post_id': str,  # owner_id_post_id
            'date': datetime,
            'text': str,     # Полный текст с обработкой репостов
            'likes': int,
            'reposts': int,
            'comments': int,
            'post_url': str
        }
        """
        # Преобразуем идентификатор в цифровой ID
        resolved_id = self.resolve_group_id(group_id)
        owner_id = resolved_id

        # Получаем информацию о группе для названия
        self._respect_rate_limit()
        group_info = self.vk.groups.getById(group_id=abs(owner_id))[0]
        group_name = group_info.get('name', f'group_{abs(owner_id)}')

        # Преобразуем даты в datetime с временной зоной UTC
        from datetime import datetime as dt
        date_from_dt = dt.combine(date_from, dt.min.time(), tzinfo=timezone.utc)
        date_to_dt = dt.combine(date_to, dt.max.time(), tzinfo=timezone.utc)

        ts_from = int(date_from_dt.timestamp())
        ts_to = int(date_to_dt.timestamp())

        posts = []
        offset = 0
        max_posts_per_request = 100
        max_total_posts = 5000  # Ограничение ВК на 5000 постов в методе

        while offset < max_total_posts:
            self._respect_rate_limit()

            try:
                response = self.vk.wall.get(
                    owner_id=owner_id,
                    count=max_posts_per_request,
                    offset=offset,
                    extended=0
                )

                items = response.get('items', [])
                if not items:
                    break

                for item in items:
                    post_date = item.get('date', 0)

                    # Проверка попадания в период
                    if post_date < ts_from:
                        # Посты идут от новых к старым — можно прервать
                        return posts

                    if post_date > ts_to:
                        continue  # Пропускаем посты вне периода

                    # Обработка полного текста (включая репосты)
                    full_text = self._extract_full_text(item)

                    post_data = {
                        'group_id': owner_id,
                        'group_name': group_name,
                        'post_id': f"{owner_id}_{item.get('id')}",
                        'date': datetime.fromtimestamp(post_date, tz=timezone.utc),
                        'text': full_text,
                        'likes': item.get('likes', {}).get('count', 0),
                        'reposts': item.get('reposts', {}).get('count', 0),
                        'comments': item.get('comments', {}).get('count', 0),
                        'post_url': f"https://vk.com/wall{owner_id}_{item.get('id')}"
                    }
                    posts.append(post_data)

                # Проверка на достижение конца списка
                if len(items) < max_posts_per_request:
                    break

                offset += max_posts_per_request

                # Защита от превышения лимита
                if len(posts) >= max_total_posts:
                    self.logger.warning(f"Достигнут лимит постов (5000) для группы {group_id}")
                    break

            except ApiError as e:
                if e.code == 6:  # Too many requests per second
                    self.logger.warning("Достигнут рейт-лимит ВК, пауза 1.5 сек...")
                    time.sleep(1.5)
                    continue
                elif e.code in (15, 18):  # Доступ запрещён / Страница удалена
                    # НЕ используем переменную item здесь — она может быть не определена!
                    self.logger.warning(f"Пропущена группа {group_id} из-за ограничений доступа (код {e.code})")
                    break
                else:
                    raise Exception(f"Ошибка ВКонтакте ({e.code}): {e}")
            except Exception as e:
                raise Exception(f"Ошибка получения постов: {e}")

        return posts

    def _extract_full_text(self, post: dict) -> str:
        """Извлечение полного текста поста с обработкой репостов и упоминаний"""
        parts = []

        # Основной текст
        main_text = post.get('text', '').strip()
        if main_text:
            parts.append(self._clean_vk_links(main_text))

        # Обработка репостов (copy_history)
        copy_history = post.get('copy_history')
        if copy_history and len(copy_history) > 0:
            original = copy_history[0]
            orig_text = original.get('text', '').strip()
            if orig_text:
                # Добавляем префикс репоста
                prefix = "🔁 [Репост] "
                parts.append(prefix + self._clean_vk_links(orig_text))

        return "\n\n".join(parts) if parts else ""

    def _clean_vk_links(self, text: str) -> str:
        """Очистка ссылок вида [id123|Имя Фамилия] → Имя Фамилия"""
        # Заменяем упоминания пользователей и групп
        text = re.sub(r'\[id\d+\|([^\]]+)\]', r'\1', text)  # [id123|Имя] → Имя
        text = re.sub(r'\[club\d+\|([^\]]+)\]', r'\1', text)  # [club123|Группа] → Группа
        text = re.sub(r'\[public\d+\|([^\]]+)\]', r'\1', text)  # [public123|Паблик] → Паблик
        return text