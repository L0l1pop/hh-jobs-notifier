from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from bot.keyboards.main_kb import get_main_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """Обработчик команды /start"""
    
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        session.add(user)
        await session.commit()
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я помогу тебе отслеживать новые вакансии на hh.ru.\n\n"
        "Создай подписку с нужными параметрами, и я буду присылать "
        "уведомления о новых вакансиях!\n\n"
        "Используй кнопки ниже для управления подписками 👇",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "🤖 <b>Как пользоваться ботом:</b>\n\n"
        
        "<b>➕ Добавить подписку</b>\n"
        "Создайте подписку, указав:\n"
        "• Ключевые слова (например: python developer)\n"
        "• Город (необязательно)\n"
        "• Требуемый опыт работы\n"
        "• Минимальную зарплату\n\n"
        
        "<b>📋 Мои подписки</b>\n"
        "Посмотрите все активные подписки.\n"
        "Можно удалить или приостановить любую.\n\n"
        
        "<b>🔍 Просмотр вакансий</b>\n"
        "Выберите подписку и просмотрите вакансии.\n"
        "Показываются по 5 штук с возможностью загрузить ещё.\n\n"
        
        "<b>📊 Статистика</b>\n"
        "Узнайте сколько вакансий найдено за последнее время.\n\n"
        
        "<b>🔔 Уведомления</b>\n"
        "Бот автоматически присылает новые вакансии каждые 15 минут.\n"
        "Вы получите уведомление только о новых вакансиях!\n\n"
        
        "❓ Вопросы? Напишите /start для перезапуска"
    )
    await message.answer(help_text, parse_mode="HTML")

