from __future__ import annotations

from datetime import datetime, timedelta, timezone


def decision_at_iso_plus5(dt: datetime | None = None) -> str:
    """
    ТЗ: YYYY-MM-DDTHH:MM:SS+05:00
    Формируем корректный timezone-aware timestamp.
    """
    plus5 = timezone(timedelta(hours=5))
    dt = dt or datetime.now(plus5)
    dt = dt.astimezone(plus5).replace(microsecond=0)
    
    return dt.isoformat()
