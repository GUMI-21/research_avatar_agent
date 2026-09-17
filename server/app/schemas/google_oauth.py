"""Public contracts for Google OAuth connection setup."""

from pydantic import BaseModel


class GoogleOAuthStartResponse(BaseModel):
    authorization_url: str


class GoogleOAuthCallbackResponse(BaseModel):
    connected: bool = True