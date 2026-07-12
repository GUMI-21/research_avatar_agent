"""Health-check response schemas."""

from pydantic import BaseModel


class PingResponse(BaseModel):
    """Response returned by the ping endpoint."""

    status: str
    service: str
