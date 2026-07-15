"""Provider-independent LLM client contracts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import SecretStr

from app.schemas.llm import LLMProvider


@dataclass(frozen=True)
class LLMRequest:
    """Internal text generation request."""

    request_id: str
    session_id: str
    message: str


@dataclass(frozen=True)
class LLMResult:
    """Normalized text result returned by every provider adapter."""

    text: str
    provider: LLMProvider
    model: str


@dataclass(frozen=True)
class LLMClientConfig:
    """Resolved runtime values required by one provider adapter."""

    provider: LLMProvider
    model: str
    base_url: str
    api_key: SecretStr | None
    timeout_seconds: float
    max_output_tokens: int


class LLMClient(ABC):
    """Abstract provider boundary used by ChatService."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResult:
        """Generate one normalized text result."""
