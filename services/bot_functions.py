from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings

def accept_keyboard(external_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Accept", callback_data=f"ka_accept:{external_id}")]
    ])

def render_request_text(external_id: int, full_name: str, phone: str, car: dict) -> str:
    return (
        f"🆕 Заявка #{external_id}\n"
        f"👤 Клиент: {full_name}\n"
        f"📞 Телефон: {phone}\n\n"
        f"🚗 Авто: {car.get('Brand')} {car.get('Model')}\n"
        f"📅 Год: {car.get('Year')}\n"
        f"🎨 Цвет: {car.get('Color')}\n"
        f"🛠 Двигатель: {car.get('Motor')}\n"
        f"💰 Цена: {car.get('Price')} {car.get('Currency')}\n"
    )

async def send_request_to_ka_group(
    bot: Bot,
    external_id: int,
    full_name: str,
    phone: str,
    car: dict
) -> int:
    
    chat_id = int(settings.group_chat_id)

    if chat_id == 0:
        raise RuntimeError("KA_GROUP_CHAT_ID / ka_group_chat_id is not set in .env")

    msg = await bot.send_message(
        chat_id=chat_id,
        text=render_request_text(external_id, full_name, phone, car),
        reply_markup=accept_keyboard(external_id),
    )
    return msg.message_id


def render_in_progress_text(original_text: str, executor_username: str | None, executor_tg_id: int) -> str:
    executor = f"@{executor_username}" if executor_username else f"ID:{executor_tg_id}"
    return original_text + f"\n\n✅ В работе: {executor}"


def decline_keyboard(external_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Decline", callback_data=f"ka_decline:{external_id}")]
    ])

def executor_keyboard(external_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Принять заявку", callback_data=f"ka_in_progress:{external_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"ka_decline:{external_id}")
        ]
    ])

def render_in_progress_stage_text(original_text: str, executor_username: str | None, executor_tg_id: int) -> str:
    executor = f"@{executor_username}" if executor_username else f"ID:{executor_tg_id}"
    return original_text + f"\n\n⏳ В процессе: {executor}"

def render_executor_confirm_text(external_id: int, full_name: str, phone: str, car: dict) -> str:
    return (
        f"Вы подтверждаете работу с заявкой #{external_id}?\n\n"
        f"👤 Клиент: {full_name}\n"
        f"📞 Телефон: {phone}\n\n"
        f"🚗 Авто: {car.get('Brand')} {car.get('Model')}\n"
        f"📅 Год: {car.get('Year')}\n"
        f"🎨 Цвет: {car.get('Color')}\n"
        f"🛠 Двигатель: {car.get('Motor')}\n"
        f"💰 Цена: {car.get('Price')} {car.get('Currency')}\n"
    )


def after_in_progress_keyboard(external_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Передать АЛ", callback_data=f"ka_send_onef:{external_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"ka_decline:{external_id}"),
        ]
    ])
