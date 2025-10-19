import asyncio
from typing import List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from database.database import async_session_maker
from database.models import Subscription, User, Vacancy
from parser.hh_client import HHClient
from parser.vacancy_service import VacancyService
from bot.config import settings

import logging
from aiogram import Bot

logger = logging.getLogger(__name__)


@celery_app.task(name='tasks.vacancy_checker.check_new_vacancies')
def check_new_vacancies():
    """
    Периодическая задача для проверки новых вакансий
    """
    logger.info("Starting vacancy check task...")
    
    # Запускаем асинхронную функцию
    asyncio.run(process_all_subscriptions())
    
    logger.info("Vacancy check task completed")


async def process_all_subscriptions():
    """
    Обработка всех активных подписок
    """
    async with async_session_maker() as session:
        # Получаем все активные подписки
        result = await session.execute(
            select(Subscription).where(Subscription.is_active == True)
        )
        subscriptions = result.scalars().all()
        
        if not subscriptions:
            logger.info("No active subscriptions found")
            return
        
        logger.info(f"Processing {len(subscriptions)} subscriptions")
        
        # Инициализируем бота для отправки уведомлений
        bot = Bot(token=settings.BOT_TOKEN)
        
        try:
            async with HHClient() as hh_client:
                for subscription in subscriptions:
                    await process_subscription(session, bot, hh_client, subscription)
        finally:
            await bot.session.close()


async def process_subscription(
    session: AsyncSession,
    bot: Bot,
    hh_client: HHClient,
    subscription: Subscription
):
    """
    Обработка одной подписки
    
    :param session: Сессия БД
    :param bot: Экземпляр бота
    :param hh_client: Клиент HH API
    :param subscription: Подписка для обработки
    """
    try:
        logger.info(f"Processing subscription {subscription.id}: {subscription.keywords}")
        
        # Ищем вакансии
        vacancies_data = await hh_client.search_vacancies(
            text=subscription.keywords,
            area=subscription.city,
            experience=subscription.experience,
            salary=subscription.salary_from,
            per_page=50  # Получаем до 50 вакансий за раз
        )
        
        new_vacancies_count = 0
        
        for vacancy_data in vacancies_data.get('items', []):
            # Пытаемся сохранить вакансию
            vacancy = await VacancyService.save_vacancy(session, vacancy_data)
            
            # Если вакансия новая (успешно сохранена)
            if vacancy:
                new_vacancies_count += 1
                
                # Отправляем уведомление пользователю
                await send_vacancy_notification(
                    session, bot, subscription.user_id, vacancy_data
                )
                
                # Небольшая задержка между отправками
                await asyncio.sleep(0.5)
        
        logger.info(
            f"Subscription {subscription.id}: found {new_vacancies_count} new vacancies"
        )
        
    except Exception as e:
        logger.error(f"Error processing subscription {subscription.id}: {e}")


async def send_vacancy_notification(
    session: AsyncSession,
    bot: Bot,
    user_id: int,
    vacancy_data: dict
):
    """
    Отправка уведомления о новой вакансии пользователю
    
    :param session: Сессия БД
    :param bot: Экземпляр бота
    :param user_id: ID пользователя в БД
    :param vacancy_data: Данные вакансии
    """
    try:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            logger.warning(f"User {user_id} not found or inactive")
            return
        
        # Форматируем вакансию
        message = HHClient.format_vacancy(vacancy_data)
        
        # Добавляем заголовок о новой вакансии
        notification = f"🆕 <b>Новая вакансия!</b>\n\n{message}"
        
        # Отправляем уведомление
        await bot.send_message(
            chat_id=user.telegram_id,
            text=notification,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        logger.info(f"Sent vacancy notification to user {user.telegram_id}")
        
    except Exception as e:
        # Если бот заблокирован пользователем
        if "bot was blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
            logger.warning(f"Bot blocked by user {user_id}, marking as inactive")
            user.is_active = False
            await session.commit()
        else:
            logger.error(f"Error sending notification to user {user_id}: {e}")
