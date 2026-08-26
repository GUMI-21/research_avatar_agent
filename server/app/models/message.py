"""Persistent visible message within one conversation Session."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import new_id, utc_now


class MessageRecord(Base):
    __tablename__ = "messages"
    __table_args__ = (
        # 限制字段值是否合法
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="ck_messages_role",
        ),
        # 数据不重复
        UniqueConstraint(
            "session_id",
            "sequence",
            name="uq_messages_session_sequence",
        ),
        Index(
            "ix_messages_client_session_sequence",
            "client_id",
            "session_id",
            "sequence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE")
    )
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer)  # 对话顺序编号
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
