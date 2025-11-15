from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Vacancy
from parser.hh_client import HHClient
import logging

logger = logging.getLogger(__name__)


class VacancyService:
    """Сервис для работы с вакансиями"""
    
    @staticmethod
    async def save_vacancy(session: AsyncSession, vacancy_data: dict) -> Optional[Vacancy]:
        hh_id = str(vacancy_data.get('id'))

        # Проверка дубликатов
        result = await session.execute(
            select(Vacancy).where(Vacancy.hh_id == hh_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return None

        # Зарплата (как у тебя)
        salary_data = vacancy_data.get('salary')
        if salary_data:
            salary_from = salary_data.get('from')
            salary_to = salary_data.get('to')
            currency = salary_data.get('currency', 'RUR')
            currency_map = {"RUR": "руб.", "RUB": "руб.", "USD": "$", "EUR": "€"}
            cur = currency_map.get(currency, currency)

            if salary_from and salary_to:
                salary = f"{salary_from:,} - {salary_to:,} {cur}"
            elif salary_from:
                salary = f"от {salary_from:,} {cur}"
            elif salary_to:
                salary = f"до {salary_to:,} {cur}"
            else:
                salary = "Не указана"
        else:
            salary = "Не указана"

        # Парсинг даты публицации
        published_at_str = vacancy_data.get('published_at', '')
        published_at = datetime.utcnow()  # fallback
        try:
            # HH может вернуть ISO с Z или с оффсетом, пример: 2025-11-12T21:53:07+0300 или ...Z
            iso = published_at_str
            if iso.endswith('Z'):
                # привести к aware-UTC
                dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
            else:
                # fromisoformat понимает +03:00, но не +0300 → нормализуем
                if len(iso) >= 5 and (iso[-5] in ['+', '-']) and iso[-3] != ':':
                    # превратить +0300 в +03:00
                    iso = iso[:-2] + ':' + iso[-2:]
                dt = datetime.fromisoformat(iso)

            # Приводим к UTC и делаем naive (без tzinfo), чтобы совпадало с TIMESTAMP WITHOUT TIME ZONE
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            published_at = dt
        except Exception:
            # Оставляем fallback = utcnow()
            published_at = datetime.utcnow()

        vacancy = Vacancy(
            hh_id=hh_id,
            title=vacancy_data.get('name', 'Без названия'),
            company=vacancy_data.get('employer', {}).get('name', 'Не указано'),
            salary=salary,
            url=vacancy_data.get('alternate_url', ''),
            published_at=published_at,  # naive UTC
        )

        try:
            session.add(vacancy)
            await session.commit()
            await session.refresh(vacancy)
            return vacancy
        except Exception:
            # критично: чистим транзакцию, чтобы сессия была рабочей дальше
            await session.rollback()
            return None
    
    @staticmethod
    async def get_new_vacancies_count(session: AsyncSession, since: datetime) -> int:
        """
        Получить количество новых вакансий с определённой даты
        
        :param session: Сессия БД
        :param since: Дата, с которой считать вакансии новыми
        :return: Количество вакансий
        """
        from sqlalchemy import func
        
        result = await session.execute(
            select(func.count(Vacancy.id)).where(Vacancy.published_at >= since)
        )
        return result.scalar()
