"""Provider-independent LLM client contracts."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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
class LLMUsage:
    """Provider-reported token usage normalized across adapters."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


@dataclass(frozen=True)
class LLMStreamChunk:
    """One normalized text or usage chunk returned by a provider."""

    text: str
    provider: LLMProvider
    model: str
    usage: LLMUsage | None = None


@dataclass(frozen=True)
class LLMClientConfig:
    """Resolved runtime values required by one provider adapter."""

    provider: LLMProvider
    model: str
    base_url: str
    api_key: SecretStr | None
    timeout_seconds: float
    max_output_tokens: int

# LLMClient 只定义统一接口，不负责真正调用模型。
class LLMClient(ABC):
    """Abstract provider boundary used by ChatService."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResult:
        """Generate one normalized text result."""

    # LLM流式输出，不支持流式走下面的默认方法包装为chunk; 子类没有定义stream的话走默认方法
    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        """Wrap non-streaming providers as a single compatible chunk."""
        result = await self.generate(request)
        yield LLMStreamChunk(
            text=result.text,
            provider=result.provider,
            model=result.model,
        )
