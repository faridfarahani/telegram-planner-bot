from aiogram.fsm.state import State, StatesGroup


class CreatePlanState(StatesGroup):
    waiting_name = State()
    choosing_ticks = State()
    choosing_days = State()


class EditPlanState(StatesGroup):
    waiting_name = State()
    choosing_days = State()
