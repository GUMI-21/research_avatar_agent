"""Registered local workspace identity."""

from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import utc_now


class WorkspaceRecord(Base):
    __tablename__ = "workspaces"

    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
