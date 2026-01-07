from __future__ import annotations

import logging

from services.onef_utils import decision_at_iso_plus5
import requests
from config import settings

logger = logging.getLogger("ka_bot")


async def send_in_progress_to_1f(
    *,
    request_id: int,
    employee_tg_id: int,
    employee_username: str | None,
) -> None:
    """
    Отправка статуса IN_PROGRESS (для теста).
    По ТЗ callback нужен после Approve/Reject, поэтому этот метод потом
    либо удалится, либо будет отключён.
    """

    # url = "http://192.168.1.47/app/v1.2/api/publications/action/asrpoststatus" # dev
    # # url = "http://192.168.1.38//app/v1.2/api/publications/action/asrpoststatus"  # main

    # payload = {
    #     "ID": request_id,
    #     "KAStatus": "IN_PROGRESS",
    #     "KAEmployee": {
    #         "TelegramUserId": employee_tg_id,
    #         "TelegramUsername": employee_username,
    #     },
    #     "DecisionAt": decision_at_iso_plus5(),
    # }

    # try:
    #     response = requests.post(url, json=payload)
    #     print(response)
    #     response.raise_for_status()
    #     logger.info("TODO(1F) send_in_progress_to_1f payload=%s", payload)

    # except requests.RequestException as e:
    #     logger.error("Failed to send IN_PROGRESS to 1F: %s", e)
    #     return

    logger.info("TODO(1F) send_in_progress_to_1f request_id=%s", request_id)