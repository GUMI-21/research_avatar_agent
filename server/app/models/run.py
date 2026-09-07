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

# Agent 单次执行的持久化状态与用量摘要，用于查询、审计和断线恢复；每次 Agent 执行任务一条 Run
class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (
        # 限制一次执行允许出现的生命周期状态
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_runs_status",
        ),
        # 区分费用是厂商报告、系统估算还是无法获得
        CheckConstraint(
            "cost_status IN ('reported', 'estimated', 'unavailable')",
            name="ck_runs_cost_status",
        ),
        Index("ix_runs_client_session_created", "client_id", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE")
    )  # 本次执行所属对话框
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))  # 实际执行任务的 Agent
    runtime: Mapped[str] = mapped_column(String(64))  # 执行时的 Adapter 快照
    provider: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )  # Runtime 报告的模型厂商
    model: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # 执行时的模型快照
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending"
    )  # 当前执行生命周期状态
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 输入 Token
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 输出 Token
    cache_read_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Provider 报告的缓存读取 Token
    cache_write_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # Provider 报告的缓存写入 Token
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )  # 本次执行的美元成本
    cost_status: Mapped[str] = mapped_column(
        String(16), default="unavailable", server_default="unavailable"
    )  # 成本数值的可信来源状态
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 总执行耗时，单位毫秒
    time_to_first_token_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 首个输出 Token 延迟，单位毫秒
    error_type: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )  # 可聚合统计的错误分类
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # 截断、脱敏后的错误摘要
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
