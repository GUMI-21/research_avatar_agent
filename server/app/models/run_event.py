"""Durable auditable event emitted during one Agent Run."""

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import new_id, utc_now


class RunEventRecord(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_run_events_run_sequence",
        ),
        Index(
            "ix_run_events_client_run_sequence",
            "client_id",
            "run_id",
            "sequence",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE")
    )  # 产生事件的 Agent 执行
    event_type: Mapped[str] = mapped_column(String(64))  # 归一化事件类型
    payload: Mapped[dict[str, object]] = mapped_column(JSON)  # 不含隐藏思维链的事件数据
    sequence: Mapped[int] = mapped_column(Integer)  # Run 内的事件顺序和重连游标
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

"""
RunEvent：
1. run_started
2. retrieval_started
3. retrieval_result
4. tool_started
5. tool_finished
6. usage_updated
7. run_finished
"""
