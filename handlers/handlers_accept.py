from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramForbiddenError
from aiogram.fsm.context import FSMContext

from db import SessionLocal
from repo.requests_repo import (
    try_accept_request,
    try_decline_request,
    try_mark_in_progress,
    get_by_external_id,
    mark_decision,
)
from repo.permitted_users_repo import is_user_permitted
from repo.audit_repo import add_audit_log
from services.bot_functions import (
    render_executor_confirm_text,
    render_in_progress_text,
    accept_keyboard,
    executor_keyboard,
    after_in_progress_keyboard,
    render_request_text,
)

from config import settings
from states import DecisionStates

from services.send_onef_in_progress import send_in_progress_to_1f
from services.send_onef_approved import send_ka_result_to_1f

logger = logging.getLogger("ka_bot")
router = Router()


def _parse_external_id(data: str) -> int | None:
    try:
        return int(data.split(":", 1)[1])
    except Exception:
        return None


# ---------------------- ACCEPT (GROUP) ----------------------
@router.callback_query(F.data.startswith("ka_accept:"))
async def ka_accept_callback(call: CallbackQuery, state: FSMContext):
    if call.from_user is None:
        await call.answer("Ошибка пользователя", show_alert=True)
        return

    user_id = call.from_user.id

    async with SessionLocal() as session:
        permitted = await is_user_permitted(session, user_id)

    if not permitted:
        await call.answer(
            "⛔ У вас нет доступа принимать заявки.\n"
            f"Ваш ID: {user_id}",
            show_alert=True,
        )
        return

    external_id = _parse_external_id(call.data)
    if external_id is None:
        await call.answer("Неверный ID", show_alert=True)
        return

    executor_username = call.from_user.username

    async with SessionLocal() as session:
        accepted, req = await try_accept_request(
            session=session,
            external_id=external_id,
            executor_tg_id=user_id,
            executor_username=executor_username,
        )

    if not accepted or req is None:
        await call.answer("Эта заявка уже в работе у другого сотрудника.", show_alert=True)
        return

    async with SessionLocal() as session:
        await add_audit_log(
            session,
            action="ACCEPT",
            entity="request",
            entity_id=str(external_id),
            actor_tg_id=user_id,
            payload={
                "assigned_to_username": executor_username,
                "group_message_id": req.group_message_id,
            },
        )

    # 1) обновить сообщение в группе
    try:
        original_text = call.message.text if call.message and call.message.text else f"Заявка #{external_id}"
        new_text = render_in_progress_text(original_text, executor_username, user_id)
        await call.message.edit_text(new_text, reply_markup=None)
    except Exception:
        logger.exception("Failed to edit group message after accept external_id=%s", external_id)

    # 2) отправить личку исполнителю
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

        await call.bot.send_message(
            chat_id=user_id,
            text=render_executor_confirm_text(
                external_id=req.external_id,
                full_name=req.user_full_name,
                phone=req.user_phone,
                car=car,
            ),
            reply_markup=executor_keyboard(req.external_id),
        )
    except TelegramForbiddenError:
        await call.answer("Открой бота в личке и нажми /start.", show_alert=True)
        return
    except Exception:
        logger.exception("Failed to send private message after accept external_id=%s", external_id)

    await call.answer("Заявка принята ✅")


# ---------------------- IN_PROGRESS (PRIVATE) ----------------------
@router.callback_query(F.data.startswith("ka_in_progress:"))
async def ka_in_progress_callback(call: CallbackQuery, state: FSMContext):
    if call.from_user is None:
        await call.answer("Ошибка пользователя", show_alert=True)
        return

    user_id = call.from_user.id
    external_id = _parse_external_id(call.data)
    if external_id is None:
        await call.answer("Неверный ID", show_alert=True)
        return

    # 1) Проверка по БД (истина)
    async with SessionLocal() as session:
        req = await get_by_external_id(session, external_id)

    if req is None:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if req.assigned_to_tg_id != user_id:
        await call.answer("⛔ Нельзя: заявка не у вас.", show_alert=True)
        return

    if req.status != "ASSIGNED":
        await call.answer(f"⚠️ Нельзя перевести в процесс: статус {req.status}", show_alert=True)
        return

    # 2) Меняем статус в БД: ASSIGNED -> IN_PROGRESS
    async with SessionLocal() as session:
        ok, req2 = await try_mark_in_progress(
            session=session,
            external_id=external_id,
            executor_tg_id=user_id,
        )

    if not ok or req2 is None:
        await call.answer("Не удалось перевести в процесс (статус изменён).", show_alert=True)
        return

    async with SessionLocal() as session:
        await add_audit_log(
            session,
            action="IN_PROGRESS",
            entity="request",
            entity_id=str(external_id),
            actor_tg_id=user_id,
            payload={"group_message_id": req2.group_message_id},
        )

    # 3) Обновить сообщение в группе (если есть message_id)
    try:
        if req2.group_message_id:
            executor_username = call.from_user.username
            executor = f"@{executor_username}" if executor_username else f"ID:{user_id}"

            group_text = (
                f"🆕 Заявка #{req2.external_id}\n"
                f"👤 Клиент: {req2.user_full_name}\n"
                f"📞 Телефон: {req2.user_phone}\n\n"
                f"🚗 Авто: {req2.car_brand} {req2.car_model}\n"
                f"📅 Год: {req2.car_year}\n"
                f"🎨 Цвет: {req2.car_color}\n"
                f"🛠 Двигатель: {req2.car_motor}\n"
                f"💰 Цена: {req2.car_price} {req2.car_currency}\n"
                f"\n⏳ В процессе: {executor}"
            )

            await call.bot.edit_message_text(
                chat_id=int(settings.group_chat_id),
                message_id=req2.group_message_id,
                text=group_text,
                reply_markup=None,
            )
    except Exception:
        logger.exception("Failed to edit group message after IN_PROGRESS external_id=%s", external_id)

    # 4) Обновить сообщение в личке + новые кнопки
    try:
        executor_username = call.from_user.username
        executor = f"@{executor_username}" if executor_username else f"ID:{user_id}"

        private_text = (
            f"✅ Статус обновлён: В Процессе\n\n"
            f"Заявка #{req2.external_id}\n"
            f"👤 Клиент: {req2.user_full_name}\n"
            f"📞 Телефон: {req2.user_phone}\n\n"
            f"🚗 Авто: {req2.car_brand} {req2.car_model}\n"
            f"📅 Год: {req2.car_year}\n"
            f"🎨 Цвет: {req2.car_color}\n"
            f"🛠 Двигатель: {req2.car_motor}\n"
            f"💰 Цена: {req2.car_price} {req2.car_currency}\n\n"
            f"После завершения нажмите 'Передать АЛ' или 'Отклонить'.\n"
            f"Исполнитель: {executor}\n"
        )

        await call.message.edit_text(private_text, reply_markup=after_in_progress_keyboard(req2.external_id))

        # ✅ ВАЖНО: сохраняем идентификатор этого сообщения (с кнопками)
        await state.update_data(
            external_id=external_id,
            origin_chat_id=call.message.chat.id,
            origin_message_id=call.message.message_id,
        )
        await state.set_state(DecisionStates.in_progress)

    except Exception:
        logger.exception("Failed to edit private message after IN_PROGRESS external_id=%s", external_id)

    await call.answer("Статус: В процессе ✅")


# ---------------------- DECLINE (PRIVATE) ----------------------
@router.callback_query(F.data.startswith("ka_decline:"))
async def ka_decline_callback(call: CallbackQuery, state: FSMContext):
    if call.from_user is None:
        await call.answer("Ошибка пользователя", show_alert=True)
        return

    user_id = call.from_user.id
    external_id = _parse_external_id(call.data)
    if external_id is None:
        await call.answer("Неверный ID", show_alert=True)
        return

    async with SessionLocal() as session:
        req = await get_by_external_id(session, external_id)

    if req is None:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if req.assigned_to_tg_id != user_id:
        await call.answer("⛔ Нельзя: заявка не у вас.", show_alert=True)
        return

    # ASSIGNED -> вернуть в очередь (в группу)
    if req.status == "ASSIGNED":
        async with SessionLocal() as session:
            declined, req2 = await try_decline_request(session, external_id, user_id)

        if not declined or req2 is None:
            await call.answer("Не удалось отказаться (статус изменён).", show_alert=True)
            return

        async with SessionLocal() as session:
            await add_audit_log(
                session,
                action="DECLINE_ASSIGNED",
                entity="request",
                entity_id=str(external_id),
                actor_tg_id=user_id,
                payload={
                    "prev_status": "ASSIGNED",
                    "new_status": "NEW",
                    "group_message_id": req2.group_message_id,
                },
            )

        # вернуть кнопку Accept в группу
        try:
            if req2.group_message_id:
                text = (
                    f"🆕 Заявка #{req2.external_id}\n"
                    f"👤 Клиент: {req2.user_full_name}\n"
                    f"📞 Телефон: {req2.user_phone}\n\n"
                    f"🚗 Авто: {req2.car_brand} {req2.car_model}\n"
                    f"📅 Год: {req2.car_year}\n"
                    f"🎨 Цвет: {req2.car_color}\n"
                    f"🛠 Двигатель: {req2.car_motor}\n"
                    f"💰 Цена: {req2.car_price} {req2.car_currency}\n"
                )
                await call.bot.edit_message_text(
                    chat_id=int(settings.group_chat_id),
                    message_id=req2.group_message_id,
                    text=text,
                    reply_markup=accept_keyboard(req2.external_id),
                )
        except Exception:
            logger.exception("Failed to edit group message after decline external_id=%s", external_id)

        # личка: подтверждение
        try:
            await call.message.edit_text(
                f"❌ Вы отказались от заявки #{external_id}.\n\n"
                "Заявка возвращена в очередь и доступна другим сотрудникам.",
                reply_markup=None,
            )
        except Exception:
            logger.exception("Failed to edit private message after decline external_id=%s", external_id)

        await state.clear()
        await call.answer("Заявка возвращена в очередь ✅")
        return

    # IN_PROGRESS -> это REJECT (просим комментарий)
    if req.status == "IN_PROGRESS":
        await state.update_data(
            external_id=external_id,
            decision="REJECTED",
            origin_chat_id=call.message.chat.id,
            origin_message_id=call.message.message_id,
        )
        await state.set_state(DecisionStates.waiting_comment_reject)
        await call.message.answer("Введите комментарий для отклонения (REJECTED):")
        await call.answer()
        return

    await call.answer(f"⚠️ Нельзя отклонить на статусе {req.status}", show_alert=True)


# ---------------------- SEND (PRIVATE) -> APPROVE требует комментарий ----------------------
@router.callback_query(F.data.startswith("ka_send_onef:"))
async def ka_send_onef_callback(call: CallbackQuery, state: FSMContext):
    if call.from_user is None:
        await call.answer("Ошибка пользователя", show_alert=True)
        return

    user_id = call.from_user.id
    external_id = _parse_external_id(call.data)
    if external_id is None:
        await call.answer("Неверный ID", show_alert=True)
        return

    async with SessionLocal() as session:
        req = await get_by_external_id(session, external_id)

    if req is None:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    if req.assigned_to_tg_id != user_id:
        await call.answer("⛔ Нельзя: заявка не у вас.", show_alert=True)
        return

    if req.status != "IN_PROGRESS":
        await call.answer(f"⚠️ Нельзя: статус {req.status}", show_alert=True)
        return

    await state.update_data(
        external_id=external_id,
        decision="APPROVED",
        origin_chat_id=call.message.chat.id,
        origin_message_id=call.message.message_id,
    )
    await state.set_state(DecisionStates.waiting_comment_approve)

    await call.message.answer("Введите комментарий для одобрения (APPROVED):")
    await call.answer()


# ---------------------- COMMENT HANDLERS ----------------------
@router.message(DecisionStates.waiting_comment_approve)
async def approve_comment_handler(message: Message, state: FSMContext):
    await _handle_decision_comment(message, state, expected_decision="APPROVED")


@router.message(DecisionStates.waiting_comment_reject)
async def reject_comment_handler(message: Message, state: FSMContext):
    await _handle_decision_comment(message, state, expected_decision="REJECTED")


async def _handle_decision_comment(message: Message, state: FSMContext, expected_decision: str):
    if message.from_user is None:
        return

    user_id = message.from_user.id
    comment = (message.text or "").strip()

    if not comment:
        await message.answer("Комментарий не может быть пустым. Введите комментарий:")
        return

    data = await state.get_data()
    external_id = int(data.get("external_id", 0))
    decision = str(data.get("decision", "")).strip()

    origin_chat_id = data.get("origin_chat_id")
    origin_message_id = data.get("origin_message_id")

    if external_id <= 0 or decision != expected_decision:
        await message.answer("⚠️ Этап неверный. Нажмите кнопку заново.")
        await state.clear()
        return

    # 1) Сохраняем решение в БД
    async with SessionLocal() as session:
        ok = await mark_decision(
            session=session,
            external_id=external_id,
            executor_tg_id=user_id,
            decision_status=decision,
            comment=comment,
        )

    if not ok:
        await message.answer("❌ Не удалось сохранить решение. Проверьте статус заявки.")
        await state.clear()
        return

    # 2) Читаем req
    async with SessionLocal() as session:
        req = await get_by_external_id(session, external_id)

    if req is None:
        await message.answer("Заявка не найдена.")
        await state.clear()
        return

    # 3) Отправка в 1F (после успешного mark_decision)
    await send_ka_result_to_1f(
        request_id=external_id,
        ka_status=decision,
        employee_tg_id=user_id,
        comment=comment,
    )

    car = {
        "Brand": req.car_brand,
        "Model": req.car_model,
        "Year": req.car_year,
        "Color": req.car_color,
        "Motor": req.car_motor,
        "Price": req.car_price,
        "Currency": req.car_currency,
    }

    executor_username = message.from_user.username
    executor = f"@{executor_username}" if executor_username else f"ID:{user_id}"

    base_text = render_request_text(
        external_id=req.external_id,
        full_name=req.user_full_name,
        phone=req.user_phone,
        car=car,
    )

    # 4) audit log
    async with SessionLocal() as session:
        await add_audit_log(
            session,
            action="DECISION",
            entity="request",
            entity_id=str(external_id),
            actor_tg_id=user_id,
            payload={
                "decision": decision,
                "comment": comment,
            },
        )

    status_line = (
            f"✅ Заявка #{external_id} статус: передана АЛ."
            if decision == "APPROVED"
            else f"❌ Заявка #{external_id} статус: Отклонена."
        )
    
    final_text = (
        f"{base_text}\n"
        f"{status_line}\n"
        f"Решение: {decision}\n"
        f"Комментарий: {comment}\n"
        f"Исполнитель: {executor}\n"
    )

    # 5) Редактируем то сообщение, где были кнопки, и убираем кнопки
    if origin_chat_id and origin_message_id:
        await message.bot.edit_message_text(
            chat_id=origin_chat_id,
            message_id=origin_message_id,
            text=final_text,
            reply_markup=None,
        )
    else:
        await message.answer(final_text)

    await state.clear()
