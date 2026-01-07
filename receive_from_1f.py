from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from db import init_db, SessionLocal
from bot_instance import bot
from services.bot_functions import send_request_to_ka_group
from repo.requests_repo import create_if_not_exists, mark_group_sent, set_group_message_id , mark_sent_to_group,  mark_send_failed, mark_group_failed

Currency = Literal["TJS", "USD", "EUR", "RUB"]


class CreateRequestIn(BaseModel):
    """
    Структура payload -> took from ТЗ
    JSON:
    {
        "ID": int,
        "User": {
            "FullName": str,
            "DateOfBirth": date,
            "Phonenumber": str  // формат +992XXXXXXXXX
        },
        "Car": {
            "CarId": int,
            "Brand": str,
            "Model": str,
            "Motor": str,
            "Price": str,
            "Currency": str,    // рекомендуемый enum: TJS|USD|EUR|RUB
            "Year": int,
            "Color": str
        }
    }
    """
    ID: int
    User: Dict[str, Any]
    Car: Dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/api/v1/ka-bot/requests")
async def create_request(payload: CreateRequestIn, authorization: Optional[str] = Header(default=None)):
    # TODO(1F): добавить проверку authorization (Bearer/HMAC) согласно ТЗ
    print("Received request:", payload)
    # User - info with verification
    full_name = str(payload.User.get("FullName", "")).strip()
    phone = str(payload.User.get("Phonenumber", "")).strip()

    if not phone.startswith("+992"):
        raise HTTPException(status_code=422, detail="Phone number must start with +992")

    # ID - info
    external_id = payload.ID

    # Car - info
    car_dict = payload.Car

    async with SessionLocal() as session:  
        req, created = await create_if_not_exists(
            session=session,
            external_id=external_id,
            user_full_name=full_name,
            user_phone=phone,
            car=car_dict,
        )

        # Если уже существует и УЖЕ отправлено в группу — просто вернем текущие данные
        if not created and getattr(req, "is_sent_to_group", False) and req.group_message_id is not None:
            return {
                "ok": True,
                "request_id": external_id,
                "status": req.status,
                "group_message_id": req.group_message_id,
                "sent_to_group": True,
            }

        # Пытаемся отправить в группу КА
        try:
            group_message_id = await send_request_to_ka_group(
                bot=bot,
                external_id=external_id,
                full_name=full_name,
                phone=phone,
                car=car_dict,
            )

            # ✅ помечаем, что отправка успешна
            await mark_group_sent(session, external_id, group_message_id)

            return {
                "ok": True,
                "request_id": external_id,
                "status": req.status,
                "group_message_id": group_message_id,
                "sent_to_group": True,
            }

        except Exception as e:

            await mark_group_failed(session, external_id, str(e))
            
            return {
                "ok": True,
                "request_id": external_id,
                "status": "ERROR_GROUP",
                "group_message_id": None,
                "sent_to_group": False,
                "error": "Failed to send to group. Will retry.",
            }
