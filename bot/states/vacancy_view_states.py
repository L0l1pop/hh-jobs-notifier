from aiogram.fsm.state import State, StatesGroup

class VacancyViewStates(StatesGroup):
    choosing_subscription = State()
    viewing_vacancies = State()
