from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Request


async def get_by_external_id(session: AsyncSession, external_id: int) -> Request | None:
    res = await session.execute(select(Request).where(Request.external_id == external_id))
    return res.scalar_one_or_none()


async def create_if_not_exists(
    session: AsyncSession,
    external_id: int,
    user_full_name: str,
    user_phone: str,
    car: dict,
) -> tuple[Request, bool]:
    """
    Возвращает (request, created_flag)
    created_flag=True если создали, False если уже была (идемпотентность).
    """
    existing = await get_by_external_id(session, external_id)
    if existing:
        return existing, False

    req = Request(
        external_id=external_id,
        status="NEW",
        user_full_name=user_full_name,
        user_phone=user_phone,
        car_brand=car.get("Brand", ""),
        car_model=car.get("Model", ""),
        car_year=int(car.get("Year", 0) or 0),
        car_color=car.get("Color", ""),
        car_motor=car.get("Motor", ""),
        car_price=str(car.get("Price", "")),
        car_currency=str(car.get("Currency", "")),
    )
    session.add(req)
    await session.commit()
    await session.refresh(req)
    return req, True


async def set_group_message_id(session: AsyncSession, external_id: int, message_id: int) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(group_message_id=message_id)
    )
    await session.commit()


async def try_accept_request(
    session: AsyncSession,
    external_id: int,
    executor_tg_id: int,
    executor_username: str | None,
) -> tuple[bool, Request | None]:
    """
    Атомарный accept:
    - срабатывает только если status == NEW
    - возвращает (accepted, request)
    """
    now = datetime.now()
    result = await session.execute(
        update(Request)
        .where(Request.external_id == external_id, Request.status == "NEW")
        .values(
            status="ASSIGNED",
            assigned_to_tg_id=executor_tg_id,
            assigned_to_username=executor_username,
            assigned_at=now,
        )
    )
    await session.commit()

    accepted = (result.rowcount or 0) == 1
    req = await get_by_external_id(session, external_id)
    return accepted, req


async def try_decline_request(session: AsyncSession, external_id: int, executor_tg_id: int) -> tuple[bool, Request | None]:
    """
    Сброс заявки обратно в NEW.
    Разрешаем decline только тому, кто сейчас назначен.
    """
    result = await session.execute(
        update(Request)
        .where(
            Request.external_id == external_id,
            Request.status == "ASSIGNED",
            Request.assigned_to_tg_id == executor_tg_id,
        )
        .values(
            status="NEW",
            assigned_to_tg_id=None,
            assigned_to_username=None,
            assigned_at=None,
        )
    )
    await session.commit()

    changed = (result.rowcount or 0) == 1
    req = await get_by_external_id(session, external_id)
    return changed, req


async def try_mark_in_progress(session: AsyncSession, external_id: int, executor_tg_id: int) -> tuple[bool, Request | None]:
    """
    Текущий внутренний шаг (не из ТЗ): перевод ASSIGNED -> IN_PROGRESS.
    """
    result = await session.execute(
        update(Request)
        .where(
            Request.external_id == external_id,
            Request.status == "ASSIGNED",
            Request.assigned_to_tg_id == executor_tg_id,
        )
        .values(status="IN_PROGRESS")
    )
    await session.commit()

    changed = (result.rowcount or 0) == 1
    req = await get_by_external_id(session, external_id)
    return changed, req


async def get_unsent_requests(session: AsyncSession, limit: int = 50) -> list[Request]:
    res = await session.execute(
        select(Request)
        .where(Request.is_sent_to_group == False)
        .order_by(Request.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def mark_sent_to_group(session: AsyncSession, external_id: int) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(is_sent_to_group=True, last_group_error=None)
    )
    await session.commit()


async def mark_send_failed(session: AsyncSession, external_id: int, error: str) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(is_sent_to_group=False, last_group_error=error[:255])
    )
    await session.commit()


async def get_error_requests(session: AsyncSession, limit: int = 50) -> list[Request]:
    res = await session.execute(
        select(Request)
        .where(Request.status == "ERROR_GROUP")
        .order_by(Request.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def mark_group_sent(session: AsyncSession, external_id: int, message_id: int) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(
            group_message_id=message_id,
            is_sent_to_group=True,
            last_group_error=None,
            status="NEW",
        )
    )
    await session.commit()


async def mark_group_failed(session: AsyncSession, external_id: int, error: str) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(
            is_sent_to_group=False,
            last_group_error=error[:255],
            status="ERROR_GROUP",
        )
    )
    await session.commit()


async def get_group_error_requests(session: AsyncSession, limit: int = 50) -> list[Request]:
    res = await session.execute(
        select(Request)
        .where(Request.status == "ERROR_GROUP")
        .order_by(Request.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def mark_onef_sent_done(session: AsyncSession, external_id: int) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(
            is_sent_to_1f=True,
            last_1f_error=None,
        )
    )
    await session.commit()


async def mark_onef_failed(session: AsyncSession, external_id: int, error: str) -> None:
    await session.execute(
        update(Request)
        .where(Request.external_id == external_id)
        .values(
            is_sent_to_1f=False,
            last_1f_error=error[:255],
            status="ERROR_ONEF",
        )
    )
    await session.commit()


async def get_onef_error_requests(session: AsyncSession, limit: int = 50) -> list[Request]:
    res = await session.execute(
        select(Request)
        .where(Request.status == "ERROR_ONEF")
        .order_by(Request.created_at.asc())
        .limit(limit)
    )
    return list(res.scalars().all())


async def mark_decision(
    session: AsyncSession,
    external_id: int,
    executor_tg_id: int,
    decision_status: str,  # "APPROVED" | "REJECTED"
    comment: str,
) -> bool:
    # Решение только назначенному исполнителю и только из IN_PROGRESS
    result = await session.execute(
        update(Request)
        .where(
            Request.external_id == external_id,
            Request.status == "IN_PROGRESS",
            Request.assigned_to_tg_id == executor_tg_id,
        )
        .values(
            status=decision_status,            
            decided_at=datetime.now(),
            decision_comment=comment,
            is_sent_to_1f=False,
            last_1f_error=None,
        )
    )
    await session.commit()
    return (result.rowcount or 0) == 1
