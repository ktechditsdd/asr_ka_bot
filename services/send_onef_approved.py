from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from services.onef_utils import decision_at_iso_plus5
import requests
import logging
import asyncio

from db import SessionLocal
from repo.requests_repo import mark_onef_sent_done, mark_onef_failed


KAStatus = Literal["APPROVED", "REJECTED"]
logger = logging.getLogger("ka_bot")

@dataclass
class OneFCallbackPayload:
    ID: int
    KAStatus: KAStatus
    TelegramUserId: int
    Comment: Optional[str]
    DecisionAt: str  # ISO строка с +05:00


async def send_ka_result_to_1f(
    *,
    request_id: int,
    ka_status: KAStatus,
    employee_tg_id: int,
    comment: str | None = None,
) -> None:
    """
    Отправка результата KA в 1F.
    По ТЗ вызывается после Approve/Reject, не после Accept.
    """
    
    payload = {
        "ID": request_id,
        "KAStatus": ka_status,
        "KAEmployee": {
            "TelegramUserId": employee_tg_id
        },
        "Comment": comment or "",
        "DecisionAt": decision_at_iso_plus5(),
    }

    url = "http://192.168.1.47/app/v1.2/api/publications/action/asrpoststatus" # dev
    # url = "http://192.168.1.38//app/v1.2/api/publications/action/asrpoststatus"  # main

    def _do_post():
        return requests.post(url, json=payload, timeout=10)
    
    try:
        resp = await asyncio.to_thread(_do_post)
        resp.raise_for_status()
        async with SessionLocal() as session:
            await mark_onef_sent_done(session, request_id)

        logger.info("TODO(1F) send_ka_result_to_1f payload=%s", payload)

    except requests.RequestException as e:
        logger.error("Failed to send KA result to 1F: %s", e)
        
        async with SessionLocal() as session:
            await mark_onef_failed(session, request_id, str(e))
        
        logger.exception("Exception in send_ka_result_to_1f function request_id=%s", request_id)
        raise

    print("TODO(1F) send_ka_result_to_1f payload:", payload)
