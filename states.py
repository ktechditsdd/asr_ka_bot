from aiogram.fsm.state import StatesGroup, State


class DecisionStates(StatesGroup):

    new = State()                
    assigned = State()           
    in_progress = State()        

    # Диалог ожидания комментария
    waiting_comment_approve = State()
    waiting_comment_reject = State()
