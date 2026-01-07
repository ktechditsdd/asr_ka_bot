from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from models import PermittedUser
from datetime import datetime
from config import settings

async def is_user_permitted(session: AsyncSession, tg_id: int) -> bool:
    if tg_id in settings.admin_id_list():
        return True
    
    res = await session.execute(
        select(PermittedUser).where(
            PermittedUser.tg_id == tg_id, 
            PermittedUser.is_active == True
        )
    )
    return res.scalar_one_or_none() is not None


async def upsert_permitted_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None,
    added_by_tg_id: int | None,
) -> None:
    res = await session.execute(select(PermittedUser).where(PermittedUser.tg_id == tg_id))
    user = res.scalar_one_or_none()

    if user is None:
        session.add(
            PermittedUser(
                tg_id=tg_id,
                username=username,
                is_active=True,
                added_by_tg_id=added_by_tg_id,
                created_at=datetime.now(),
            )
        )
    else:
        user.username = username
        user.is_active = True
        user.added_by_tg_id = added_by_tg_id

    await session.commit()

async def deactivate_permitted_user(session: AsyncSession, tg_id: int) -> bool:
    result = await session.execute(
        update(PermittedUser).where(PermittedUser.tg_id == tg_id).values(is_active=False)
    )
    await session.commit()
    return (result.rowcount or 0) > 0

async def list_permitted_users(session: AsyncSession) -> list[PermittedUser]:
    res = await session.execute(select(PermittedUser).order_by(PermittedUser.tg_id.asc()))
    return list(res.scalars().all())
