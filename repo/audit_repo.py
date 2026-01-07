import json
from sqlalchemy.ext.asyncio import AsyncSession
from models import AuditLog

async def add_audit_log(
    session: AsyncSession,
    *,
    action: str,
    entity: str,
    entity_id: str,
    actor_tg_id: int | None,
    payload: dict | None = None,
) -> None:
    row = AuditLog(
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        actor_tg_id=actor_tg_id,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
    )
    session.add(row)
    await session.commit()
