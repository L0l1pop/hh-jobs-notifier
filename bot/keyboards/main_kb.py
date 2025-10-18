from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура бота"""
    keyboard = [
        [KeyboardButton(text="➕ Добавить подписку")],
        [KeyboardButton(text="📋 Мои подписки")],
        [KeyboardButton(text="ℹ️ Помощь")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для отмены действия"""
    keyboard = [[KeyboardButton(text="❌ Отменить")]]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


def get_subscription_actions(subscription_id: int) -> InlineKeyboardMarkup:
    """Inline клавиатура для управления подпиской"""
    buttons = [
        [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_sub_{subscription_id}")],
        [InlineKeyboardButton(text="⏸ Приостановить", callback_data=f"pause_sub_{subscription_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
