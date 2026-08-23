"""Persistent configuration for one Personal Agent instance."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRecord(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="uq_agents_client_name"),
    )
    # Mapped[str] 映射为字符串
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(80))
    system_prompt: Mapped[str] = mapped_column(Text)
    runtime: Mapped[str] = mapped_column(
        String(32), default="native", server_default="native"
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
