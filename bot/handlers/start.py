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
        "1️⃣ Нажми <b>➕ Добавить подписку</b>\n"
        "2️⃣ Укажи ключевые слова (например: python developer)\n"
        "3️⃣ Выбери город или пропусти\n"
        "4️⃣ Укажи требуемый опыт\n"
        "5️⃣ Укажи минимальную зарплату\n\n"
        "✅ Готово! Бот начнёт присылать подходящие вакансии\n\n"
        "📋 <b>Мои подписки</b> - посмотреть все активные подписки\n"
        "🗑 Удалить подписку можно через список подписок"
    )
    await message.answer(help_text)
