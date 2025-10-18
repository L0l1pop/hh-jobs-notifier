from typing import List, Optional
from datetime import datetime
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
        """
        Сохранить вакансию в БД
        
        :param session: Сессия БД
        :param vacancy_data: Данные вакансии из HH API
        :return: Объект Vacancy или None
        """
        hh_id = str(vacancy_data.get('id'))
        
        result = await session.execute(
            select(Vacancy).where(Vacancy.hh_id == hh_id)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.debug(f"Vacancy {hh_id} already exists")
            return None
        
        salary_data = vacancy_data.get('salary')
        if salary_data:
            salary_from = salary_data.get('from')
            salary_to = salary_data.get('to')
            currency = salary_data.get('currency', 'RUR')
            
            if salary_from and salary_to:
                salary = f"{salary_from:,} - {salary_to:,} {currency}"
            elif salary_from:
                salary = f"от {salary_from:,} {currency}"
            elif salary_to:
                salary = f"до {salary_to:,} {currency}"
            else:
                salary = "Не указана"
        else:
            salary = "Не указана"
        
        # Парсим дату публикации
        published_at_str = vacancy_data.get('published_at', '')
        try:
            published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
        except:
            published_at = datetime.utcnow()
        
        # Создаём новую вакансию
        vacancy = Vacancy(
            hh_id=hh_id,
            title=vacancy_data.get('name', 'Без названия'),
            company=vacancy_data.get('employer', {}).get('name', 'Не указано'),
            salary=salary,
            url=vacancy_data.get('alternate_url', ''),
            published_at=published_at
        )
        
        session.add(vacancy)
        await session.commit()
        await session.refresh(vacancy)
        
        logger.info(f"Saved new vacancy: {vacancy.title}")
        return vacancy
    
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
