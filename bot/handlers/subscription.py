from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from database.models import User, Subscription
from bot.keyboards.main_kb import get_main_keyboard, get_cancel_keyboard, get_subscription_actions
from bot.states.subscription_states import SubscriptionStates
from parser.hh_client import HHClient
from bot.states.vacancy_view_states import VacancyViewStates

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
    
    experience_text = {
        "noExperience": "Без опыта",
        "between1And3": "1-3 года",
        "between3And6": "3-6 лет",
        "moreThan6": "Более 6 лет"
    }
    
    for i, sub in enumerate(subscriptions, 1):
        response = f"<b>{i}.</b> 🔍 <code>{sub.keywords}</code>\n"
        
        if sub.city:
            response += f"   🏙 {sub.city}\n"
        
        if sub.experience:
            response += f"   💼 {experience_text.get(sub.experience, sub.experience)}\n"
        
        if sub.salary_from:
            response += f"   💰 От {sub.salary_from:,} руб.\n"
        
        await message.answer(
            response,
            reply_markup=get_subscription_actions(sub.id)
        )


@router.message(F.text == "🔍 Тест поиска")
async def choose_subscription_for_view(message: Message, session: AsyncSession, state: FSMContext):
    """Выбор подписки для просмотра вакансий"""
    
    # Получаем пользователя
    result = await session.execute(
        select(User).where(User.telegram_id == message.from_user.id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    # Получаем все активные подписки
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.is_active == True
        )
    )
    subscriptions = result.scalars().all()
    
    if not subscriptions:
        await message.answer("❌ У вас нет активных подписок")
        return
    
    # Создаём inline-кнопки для выбора подписки
    buttons = []
    for sub in subscriptions:
        buttons.append([
            InlineKeyboardButton(
                text=f"🔍 {sub.keywords}",
                callback_data=f"view_sub_{sub.id}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "📋 Выберите подписку для просмотра вакансий:",
        reply_markup=keyboard
    )
    await state.set_state(VacancyViewStates.choosing_subscription)


@router.callback_query(F.data.startswith("view_sub_"))
async def view_subscription_vacancies(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Просмотр вакансий по выбранной подписке"""
    
    subscription_id = int(callback.data.split("_")[-1])
    
    # Получаем подписку
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        await callback.answer("❌ Подписка не найдена")
        return
    
    # Сохраняем ID подписки и текущую страницу в состояние
    await state.update_data(
        subscription_id=subscription_id,
        current_page=0
    )
    await state.set_state(VacancyViewStates.viewing_vacancies)
    
    await callback.message.edit_text(
        f"🔄 Ищу вакансии по запросу:\n<code>{subscription.keywords}</code>",
        parse_mode="HTML"
    )
    
    # Показываем первые 5 вакансий
    await show_vacancies_page(callback.message, session, state, subscription)


async def show_vacancies_page(message, session: AsyncSession, state: FSMContext, subscription: Subscription):
    """Показать страницу с 5 вакансиями"""
    
    data = await state.get_data()
    current_page = data.get('current_page', 0)
    
    # Получаем вакансии из HH API
    async with HHClient() as client:
        vacancies_data = await client.search_vacancies(
            text=subscription.keywords,
            area=subscription.city,
            experience=subscription.experience,
            salary=subscription.salary_from,
            per_page=5,
            page=current_page
        )
    
    items = vacancies_data.get('items', [])
    total_found = vacancies_data.get('found', 0)
    
    if not items:
        await message.answer(
            "😔 Вакансий не найдено или закончились результаты.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Отправляем информацию о количестве
    await message.answer(
        f"📊 Найдено: <b>{total_found}</b> вакансий\n"
        f"Страница {current_page + 1}, показываю {len(items)} вакансий:",
        parse_mode="HTML"
    )
    
    # Отправляем каждую вакансию
    for vacancy in items:
        formatted = HHClient.format_vacancy(vacancy)
        await message.answer(formatted, disable_web_page_preview=True)
        await asyncio.sleep(0.3)
    
    # Кнопки для навигации
    buttons = []
    
    # Проверяем, есть ли ещё страницы
    pages_available = (current_page + 1) * 5 < total_found
    
    if pages_available:
        buttons.append([
            InlineKeyboardButton(
                text="➡️ Показать ещё 5",
                callback_data=f"next_page_{subscription.id}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="✅ Завершить просмотр",
            callback_data="finish_viewing"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "Выберите действие:",
        reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("next_page_"))
async def show_next_page(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Показать следующие 5 вакансий"""
    
    subscription_id = int(callback.data.split("_")[-1])
    
    # Получаем подписку
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        await callback.answer("❌ Подписка не найдена")
        return
    
    # Увеличиваем номер страницы
    data = await state.get_data()
    current_page = data.get('current_page', 0) + 1
    await state.update_data(current_page=current_page)
    
    await callback.answer("🔄 Загружаю следующие вакансии...")
    
    # Показываем следующую страницу
    await show_vacancies_page(callback.message, session, state, subscription)


@router.callback_query(F.data == "finish_viewing")
async def finish_viewing(callback: CallbackQuery, state: FSMContext):
    """Завершить просмотр вакансий"""
    
    await state.clear()
    await callback.message.edit_text(
        "✅ Просмотр завершён"
    )
    await callback.answer("До новых встреч!")


@router.callback_query(F.data.startswith("delete_sub_"))
async def delete_subscription(callback: CallbackQuery, session: AsyncSession):
    """Удаление подписки"""
    subscription_id = int(callback.data.split("_")[-1])
    
    # Получаем подписку
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        await callback.answer("❌ Подписка не найдена")
        return
    
    # Помечаем как неактивную
    await session.delete(subscription)
    await session.commit()
    
    await callback.message.edit_text(
        f"🗑 Подписка удалена:\n\n"
        f"🔍 <code>{subscription.keywords}</code>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Подписка удалена")


@router.callback_query(F.data.startswith("pause_sub_"))
async def pause_subscription(callback: CallbackQuery, session: AsyncSession):
    """Приостановка подписки"""
    subscription_id = int(callback.data.split("_")[-1])
    
    result = await session.execute(
        select(Subscription).where(Subscription.id == subscription_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        await callback.answer("❌ Подписка не найдена")
        return
    
    subscription.is_active = False
    await session.commit()
    
    await callback.message.edit_text(
        f"⏸ Подписка приостановлена:\n\n"
        f"🔍 <code>{subscription.keywords}</code>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Подписка приостановлена")