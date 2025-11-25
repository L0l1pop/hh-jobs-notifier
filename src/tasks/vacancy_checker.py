import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from celery_app import celery_app
from database.models import Subscription, User
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
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(process_all_subscriptions())
        logger.info("Vacancy check task completed successfully")
    except Exception as e:
        logger.error(f"Error in vacancy check task: {e}", exc_info=True)
        raise
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


async def process_all_subscriptions():
    """
    Обработка всех активных подписок
    """
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,                                                                           
    )
    
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    bot = None
    
    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(Subscription).where(Subscription.is_active == True)
            )
            subscriptions = result.scalars().all()
            
            if not subscriptions:
                logger.info("No active subscriptions found")
                return
            
            logger.info(f"Processing {len(subscriptions)} subscriptions")
            bot = Bot(token=settings.BOT_TOKEN)
            
            try:
                async with HHClient() as hh_client:
                    for subscription in subscriptions:
                        try:
                            await process_subscription(session, bot, hh_client, subscription)
                        except Exception as e:
                            logger.error(f"Error processing subscription {subscription.id}: {e}", exc_info=True)
                            await session.rollback()
                            continue
            finally:
                if bot:
                    await bot.session.close()
                    
    except Exception as e:
        logger.error(f"Error in process_all_subscriptions: {e}", exc_info=True)
        raise
    finally:
        await engine.dispose()


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
        
        vacancies_data = await hh_client.search_vacancies(
            text=subscription.keywords,
            area=subscription.city,
            experience=subscription.experience,
            salary=subscription.salary_from,
            per_page=50
        )
        
        new_vacancies_count = 0
        
        for vacancy_data in vacancies_data.get('items', []):
            if new_vacancies_count == 5:
                break
            try:
                vacancy = await VacancyService.save_vacancy(session, vacancy_data)
                
                if vacancy:
                    new_vacancies_count += 1
                    await send_vacancy_notification(
                        session, bot, subscription.user_id, vacancy_data
                    )
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error processing vacancy {vacancy_data.get('id')}: {e}", exc_info=True)
                await session.rollback()
                continue
        
        logger.info(
            f"Subscription {subscription.id}: found {new_vacancies_count} new vacancies"
        )
        
    except Exception as e:
        logger.error(f"Error processing subscription {subscription.id}: {e}", exc_info=True)
        await session.rollback()


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
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            logger.warning(f"User {user_id} not found or inactive")
            return
        
        message = HHClient.format_vacancy(vacancy_data)  
        notification = f"🆕 <b>Новая вакансия!</b>\n\n{message}"
        
        await bot.send_message(
            chat_id=user.telegram_id,
            text=notification,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        logger.info(f"Sent vacancy notification to user {user.telegram_id}")
        
    except Exception as e:
        error_str = str(e).lower()
        if "bot was blocked" in error_str or "user is deactivated" in error_str or "chat not found" in error_str:
            logger.warning(f"Bot blocked by user {user_id}, marking as inactive")
            try:
                user.is_active = False
                await session.commit()
            except Exception as commit_error:
                logger.error(f"Error updating user status: {commit_error}")
                await session.rollback()
        else:
            logger.error(f"Error sending notification to user {user_id}: {e}", exc_info=True)
