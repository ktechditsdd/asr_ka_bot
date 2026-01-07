from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message


class ChatTypeMiddleware(BaseMiddleware):
    """
    Пропускаем message-handlers только в private чате.
    (CallbackQuery сюда не попадает, поэтому на Accept это не влияет.)
    generated/
    """
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.chat.type != "private":
            return None
        return await handler(event, data)
