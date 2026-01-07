from __future__ import annotations

import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.chat_action import ChatActionMiddleware

from bot_instance import bot
from db import SessionLocal, init_db
from handlers.handlers_accept import router as handlers_accept_router
from handlers.handlers_admin import router as handlers_admin_router
from handlers.handlers_test import router as handlers_test_router
from middleware import ChatTypeMiddleware
from repo.requests_repo import (
    get_group_error_requests,
    get_onef_error_requests,
    mark_group_failed,
    mark_group_sent,
    mark_onef_failed,
    mark_onef_sent_done,
)
from services.bot_functions import send_request_to_ka_group
from services.send_onef_in_progress import send_in_progress_to_1f

logger = logging.getLogger("ka_bot")


async def retry_group_errors_periodically() -> None:
    while True:
        await asyncio.sleep(300)
        logger.info("[Retry-GROUP] checking ERROR_GROUP...")

        async with SessionLocal() as session:
            items = await get_group_error_requests(session, limit=50)

        if not items:
            continue

        for req in items:
            try:
                car = {
                    "Brand": req.car_brand,
                    "Model": req.car_model,
                    "Year": req.car_year,
                    "Color": req.car_color,
                    "Motor": req.car_motor,
                    "Price": req.car_price,
                    "Currency": req.car_currency,
                }

                msg_id = await send_request_to_ka_group(
                    bot=bot,
                    external_id=req.external_id,
                    full_name=req.user_full_name,
                    phone=req.user_phone,
                    car=car,
                )

                async with SessionLocal() as session:
                    await mark_group_sent(session, req.external_id, msg_id)

                logger.info("[Retry-GROUP] sent #%s msg_id=%s", req.external_id, msg_id)

            except Exception as e:
                async with SessionLocal() as session:
                    await mark_group_failed(session, req.external_id, str(e))
                logger.exception("[Retry-GROUP] failed #%s", req.external_id)


async def retry_onef_errors_periodically() -> None:
    while True:
        await asyncio.sleep(300)
        logger.info("[Retry-1F] checking ERROR_ONEF...")

        async with SessionLocal() as session:
            items = await get_onef_error_requests(session, limit=50)

        if not items:
            continue

        for req in items:
            try:

                await send_in_progress_to_1f(
                    request_id=req.external_id,
                    employee_tg_id=req.assigned_to_tg_id or 0,
                    employee_username=req.assigned_to_username,
                )

                async with SessionLocal() as session:
                    await mark_onef_sent_done(session, req.external_id)

                logger.info("[Retry-1F] sent #%s", req.external_id)

            except Exception as e:
                async with SessionLocal() as session:
                    await mark_onef_failed(session, req.external_id, str(e))
                logger.exception("[Retry-1F] failed #%s", req.external_id)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    await init_db()

    dp = Dispatcher(storage=MemoryStorage())

    # message handlers only in private chat
    dp.message.outer_middleware(ChatTypeMiddleware())
    dp.message.middleware(ChatActionMiddleware())

    dp.include_router(handlers_accept_router)
    dp.include_router(handlers_test_router)
    dp.include_router(handlers_admin_router)

    asyncio.create_task(retry_group_errors_periodically())
    asyncio.create_task(retry_onef_errors_periodically())

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
