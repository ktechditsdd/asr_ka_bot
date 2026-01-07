from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from db import Base



class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ID from 1F
    external_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    #Statuses: NEW, ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)

    # User info
    user_full_name: Mapped[str] = mapped_column(String(255))
    user_phone: Mapped[str] = mapped_column(String(32))

    #Car info
    car_brand: Mapped[str] = mapped_column(String(128))
    car_model: Mapped[str] = mapped_column(String(128))
    car_year: Mapped[int] = mapped_column(Integer)
    car_color: Mapped[str] = mapped_column(String(64))
    car_motor: Mapped[str] = mapped_column(String(64))
    car_price: Mapped[str] = mapped_column(String(64))
    car_currency: Mapped[str] = mapped_column(String(8))

    # Telegram
    group_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Accept (executor) info
    assigned_to_tg_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    assigned_to_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(), onupdate=datetime.now())

    # Telegram group delivery
    is_sent_to_group: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_group_error: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 1F delivery
    is_sent_to_1f: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_1f_error: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Decision info
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    callback_attempts: Mapped[int] = mapped_column(Integer, default=0, index=True)



class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_tg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())


class PermittedUser(Base):
    """
    Пользователи, которые имеют право нажимать Accept в группе.
    """
    __tablename__ = "permitted_users"

    tg_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    added_by_tg_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())
