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
    client_id: Mapped[str] = mapped_column(String(64), index=True)  # 数据隔离作用域
    name: Mapped[str] = mapped_column(String(80))  # 同一客户端内唯一的展示名称
    system_prompt: Mapped[str] = mapped_column(Text)  # Agent 的身份和行为指令
    runtime: Mapped[str] = mapped_column(
        String(32), default="native", server_default="native"
    )  # Runtime Adapter 注册名
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 可选模型覆盖
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
