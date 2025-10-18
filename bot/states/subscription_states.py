from aiogram.fsm.state import State, StatesGroup


class SubscriptionStates(StatesGroup):
    waiting_for_keywords = State()
    waiting_for_city = State()
    waiting_for_experience = State()
    waiting_for_salary = State()