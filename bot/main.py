import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.handlers import start
from database.database import create_tables, async_session_maker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Создаём таблицы в БД
    await create_tables()
    
    # Инициализируем бот и диспетчер
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрируем роутеры
    dp.include_router(start.router)
    
    # Добавляем session в middleware
    @dp.update.outer_middleware()
    async def db_session_middleware(handler, event, data):
        async with async_session_maker() as session:
            data['session'] = session
            return await handler(event, data)
    
    # Запускаем бота
    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
