"""Persistent execution summary for one Agent run."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import new_id, utc_now

# Agent 单次执行的持久化状态与用量摘要，用于查询、审计和断线恢复
class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (
        # 限制字段
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_runs_status",
        ),
        # websocket状态
        CheckConstraint(
            "cost_status IN ('reported', 'estimated', 'unavailable')",
            name="ck_runs_cost_status",
        ),
        Index("ix_runs_client_session_created", "client_id", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE")
    )
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    runtime: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending"
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    cost_status: Mapped[str] = mapped_column(
        String(16), default="unavailable", server_default="unavailable"
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_to_first_token_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
