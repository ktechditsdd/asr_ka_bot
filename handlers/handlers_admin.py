from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from db import SessionLocal
from repo.permitted_users_repo import upsert_permitted_user, deactivate_permitted_user, list_permitted_users


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in set(settings.admin_id_list())


@router.message(Command("start"))
async def start_cmd(message: Message):
    if message.from_user is None:
        return

    if is_admin(message.from_user.id):
        await message.answer(
            "✅ Admin panel\n\n"
            "Доступные команды:\n"
            "/add tg_id — добавить/активировать пользователя для Accept\n"
            "/remove tg_id — отключить пользователя (is_active=false)\n"
            "/list — показать список разрешённых пользователей\n"
        )
    else:
        await message.answer("Привет. Доступ к управлению ограничен.")


@router.message(Command("add"))
async def add_cmd(message: Message):
    if message.from_user is None:
        return

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недостаточно прав.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /add tg_id")
        return

    try:
        tg_id = int(parts[1])
    except ValueError:
        await message.answer("tg_id должен быть числом.")
        return

    async with SessionLocal() as session:
        await upsert_permitted_user(
            session=session,
            tg_id=tg_id,
            username=None,  # можно обновлять позже, если нужно
            added_by_tg_id=message.from_user.id,
        )

    await message.answer(f"✅ Пользователь {tg_id} добавлен/активирован.")


@router.message(Command("remove"))
async def remove_cmd(message: Message):
    if message.from_user is None:
        return

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недостаточно прав.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /remove tg_id")
        return

    try:
        tg_id = int(parts[1])
    except ValueError:
        await message.answer("tg_id должен быть числом.")
        return

    async with SessionLocal() as session:
        ok = await deactivate_permitted_user(session, tg_id)

    if ok:
        await message.answer(f"✅ Пользователь {tg_id} отключён (is_active=false).")
    else:
        await message.answer(f"⚠️ Пользователь {tg_id} не найден.")

@router.message(Command("list"))
async def list_cmd(message: Message):
    if message.from_user is None:
        return

    if not is_admin(message.from_user.id):
        await message.answer("⛔ Недостаточно прав.")
        return

    async with SessionLocal() as session:
        users = await list_permitted_users(session)

    if not users:
        await message.answer("Список пуст.")
        return

    lines = ["📋 permitted_users:"]
    for u in users:
        status = "✅ active" if u.is_active else "⛔ inactive"
        lines.append(f"- {u.tg_id} — {status}")

    # чтобы не упереться в лимит телеграма, если вдруг список большой
    text = "\n".join(lines)
    if len(text) > 3800:
        text = text[:3800] + "\n...\n(обрезано)"

    await message.answer(text)
