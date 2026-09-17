"""Encrypted per-workspace Google OAuth credentials."""

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import utc_now


class GoogleOAuthCredentialRecord(Base):
    __tablename__ = "google_oauth_credentials"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    scopes_json: Mapped[str] = mapped_column(Text)
    refresh_token_ciphertext: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)