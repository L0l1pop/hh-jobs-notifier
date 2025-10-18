from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from database.models import User, Subscription
from bot.keyboards.main_kb import get_main_keyboard, get_cancel_keyboard
from bot.states.subscription_states import SubscriptionStates
from parser.hh_client import HHClient

router = Router()


@router.message(F.text == "➕ Добавить подписку")
async def start_subscription(message: Message, state: FSMContext):
    """Начало создания подписки"""
    await state.set_state(SubscriptionStates.waiting_for_keywords)
    await message.answer(
        "🔍 <b>Шаг 1 из 4: Ключевые слова</b>\n\n"
        "Введите ключевые слова для поиска вакансий.\n"
        "Например: <code>python developer</code> или <code>backend fastapi</code>\n\n"
        "💡 Можно указать несколько слов через пробел",
        reply_markup=get_cancel_keyboard()
    )


@router.message(SubscriptionStates.waiting_for_keywords)
async def process_keywords(message: Message, state: FSMContext):
    """Обработка ключевых слов"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer(
            "❌ Создание подписки отменено",
            reply_markup=get_main_keyboard()
        )
        return
    
    await state.update_data(keywords=message.text)
    
    await state.set_state(SubscriptionStates.waiting_for_city)
    await message.answer(
        "🏙 <b>Шаг 2 из 4: Город</b>\n\n"
        "Введите название города для поиска.\n"
        "Например: <code>Москва</code>, <code>Санкт-Петербург</code>, <code>Казань</code>\n\n"
        "Или отправьте <code>-</code> чтобы искать по всей России",
        reply_markup=get_cancel_keyboard()
    )


@router.message(SubscriptionStates.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Обработка города"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer(
            "❌ Создание подписки отменено",
            reply_markup=get_main_keyboard()
        )
        return
    
    city = None if message.text.strip() == "-" else message.text
    await state.update_data(city=city)
    
    await state.set_state(SubscriptionStates.waiting_for_experience)
    
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    experience_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Без опыта")],
            [KeyboardButton(text="От 1 года")],
            [KeyboardButton(text="От 3 лет")],
            [KeyboardButton(text="От 6 лет")],
            [KeyboardButton(text="-")],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "💼 <b>Шаг 3 из 4: Опыт работы</b>\n\n"
        "Выберите требуемый опыт работы или отправьте <code>-</code> для пропуска:",
        reply_markup=experience_kb
    )


@router.message(SubscriptionStates.waiting_for_experience)
async def process_experience(message: Message, state: FSMContext):
    """Обработка опыта работы"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer(
            "❌ Создание подписки отменено",
            reply_markup=get_main_keyboard()
        )
        return
    
    experience_map = {
        "Без опыта": "noExperience",
        "От 1 года": "between1And3",
        "От 3 лет": "between3And6",
        "От 6 лет": "moreThan6",
        "-": None
    }
    
    experience = experience_map.get(message.text, None)
    await state.update_data(experience=experience)
    
    await state.set_state(SubscriptionStates.waiting_for_salary)
    await message.answer(
        "💰 <b>Шаг 4 из 4: Зарплата</b>\n\n"
        "Введите минимальную желаемую зарплату в рублях.\n"
        "Например: <code>100000</code>\n\n"
        "Или отправьте <code>-</code> для пропуска",
        reply_markup=get_cancel_keyboard()
    )


@router.message(SubscriptionStates.waiting_for_salary)
async def process_salary(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка зарплаты и сохранение подписки"""
    if message.text == "❌ Отменить":
        await state.clear()
        await message.answer(
            "❌ Создание подписки отменено",
            reply_markup=get_main_keyboard()
        )
        return
    
    salary_from = None
    if message.text.strip() != "-":
        try:
            salary_from = int(message.text.strip())
            if salary_from <= 0:
                await message.answer(
                    "❌ Зарплата должна быть положительным числом. Попробуйте снова:"
                )
                return
        except ValueError:
            await message.answer(
                "❌ Некорректное значение. Введите число или <code>-</code> для пропуска:"
            )
            return
    
    data = await state.get_data()
    
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one()
    
    subscription = Subscription(
        user_id=user.id,
        keywords=data['keywords'],
        city=data.get('city'),
        experience=data.get('experience'),
        salary_from=salary_from,
        is_active=True
    )
    
    session.add(subscription)
    await session.commit()
    
    await state.clear()
    
    confirmation = (
        "✅ <b>Подписка успешно создана!</b>\n\n"
        f"🔍 Ключевые слова: <code>{data['keywords']}</code>\n"
    )
    
    if data.get('city'):
        confirmation += f"🏙 Город: <code>{data['city']}</code>\n"
    
    experience_text = {
        "noExperience": "Без опыта",
        "between1And3": "От 1 года до 3 лет",
        "between3And6": "От 3 до 6 лет",
        "moreThan6": "Более 6 лет"
    }
    if data.get('experience'):
        confirmation += f"💼 Опыт: <code>{experience_text.get(data['experience'], data['experience'])}</code>\n"
    
    if salary_from:
        confirmation += f"💰 Зарплата от: <code>{salary_from:,} ₽</code>\n"
    
    confirmation += "\n📬 Теперь вы будете получать уведомления о новых вакансиях!"
    
    await message.answer(
        confirmation,
        reply_markup=get_main_keyboard()
    )


@router.message(F.text == "📋 Мои подписки")
async def show_subscriptions(message: Message, session: AsyncSession):
    """Показать все подписки пользователя"""
    
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.is_active == True
        )
    )
    subscriptions = result.scalars().all()
    
    if not subscriptions:
        await message.answer(
            "📭 У вас пока нет активных подписок.\n\n"
            "Нажмите <b>➕ Добавить подписку</b> чтобы создать первую!",
            reply_markup=get_main_keyboard()
        )
        return
    
    response = f"📋 <b>Ваши подписки ({len(subscriptions)}):</b>\n\n"
    
    experience_text = {
        "noExperience": "Без опыта",
        "between1And3": "1-3 года",
        "between3And6": "3-6 лет",
        "moreThan6": "Более 6 лет"
    }
    
    for i, sub in enumerate(subscriptions, 1):
        response += f"<b>{i}.</b> 🔍 <code>{sub.keywords}</code>\n"
        
        if sub.city:
            response += f"   🏙 {sub.city}\n"
        
        if sub.experience:
            response += f"   💼 {experience_text.get(sub.experience, sub.experience)}\n"
        
        if sub.salary_from:
            response += f"   💰 От {sub.salary_from:,} ₽\n"
        
        response += "\n"
    
    response += "💡 Для управления подписками используйте кнопки ниже каждой подписки"
    
    await message.answer(response, reply_markup=get_main_keyboard())


@router.message(F.text == "🔍 Тест поиска")
async def test_search(message: Message, session: AsyncSession):
    """Тестовый поиск вакансий по первой подписке"""
    
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.is_active == True
        ).limit(1)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        await message.answer("❌ У вас нет активных подписок")
        return
    
    await message.answer("🔄 Ищу вакансии...")
    
    async with HHClient() as client:
        vacancies = await client.search_vacancies(
            text=subscription.keywords,
            area=subscription.city,
            experience=subscription.experience,
            salary=subscription.salary_from,
            per_page=5
        )
        
        if not vacancies.get('items'):
            await message.answer(
                "😔 Вакансий по вашим критериям не найдено.\n"
                "Попробуйте изменить параметры подписки."
            )
            return
        
        total_found = vacancies.get('found', 0)
        await message.answer(
            f"✅ Найдено вакансий: <b>{total_found}</b>\n"
            f"Показываю первые {len(vacancies['items'])}:\n"
        )
        
        for vacancy in vacancies['items']:
            formatted_vacancy = client.format_vacancy(vacancy)
            await message.answer(formatted_vacancy)
            await asyncio.sleep(0.5) 
