"""External runtime thread bindings for resumable Agent sessions."""

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import new_id, utc_now


class RuntimeThreadRecord(Base):
    __tablename__ = "runtime_threads"
    __table_args__ = (
        UniqueConstraint(
            "client_id", "session_id", "agent_id", "runtime",
            name="uq_runtime_threads_scope",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE")
    )
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE")
    )
    runtime: Mapped[str] = mapped_column(String(64))
    external_thread_id: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
