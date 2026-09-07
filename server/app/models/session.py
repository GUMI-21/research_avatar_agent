"""Persistent identity for one client-scoped Agent conversation."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import new_id, utc_now


class SessionRecord(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_client_created", "client_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
    )  # 对话入口和默认 Agent
    title: Mapped[str] = mapped_column(
        String(160),
        default="New conversation",
        server_default="New conversation",
    )  # Web 对话框展示标题
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
