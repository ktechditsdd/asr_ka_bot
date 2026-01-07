from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot_instance import bot
from config import settings

router = Router()

@router.message(Command("test_group"))
async def test_group(message: Message):
    # ограничим команду только админам
    if message.from_user is None or message.from_user.id not in set(settings.admin_id_list()):
        await message.answer("⛔ Нет доступа.")
        return

    chat_id = settings.group_chat_id

    # простое тестовое сообщение
    sent = await bot.send_message(
        chat_id=chat_id,
        text="✅ Тест: бот может отправлять сообщения в группу КА."
    )

    await message.answer(f"Отправлено в группу. message_id={sent.message_id}")
