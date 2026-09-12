"""Encrypted per-workspace LLM provider credentials."""

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import utc_now


class LLMCredentialRecord(Base):
    __tablename__ = "llm_credentials"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    model: Mapped[str] = mapped_column(String(256))
    base_url: Mapped[str] = mapped_column(String(512))
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
