"""Native Personal Agent runtime backed by the configured LLM API."""

from collections.abc import AsyncIterator

from app.adapters.agent.base import (
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)
from app.adapters.llm import LLMClient, LLMRequest

# 符合 AgentRuntimeAdapter 协议的具体实现
class NativeAgentRuntime:
    """Normalize one provider call into auditable Agent Runtime events."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    # 实现 AgentRuntimeAdapter 约定的 stream 接口
    async def stream(
        self,
        request: RuntimeRequest,
    ) -> AsyncIterator[RuntimeEvent]:
        # 外部每调用一次 anext()，执行到下一个 yield
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.AGENT_STARTED,
            payload={"agent_id": request.agent_id, "runtime": "native"},
        )
        provider: str | None = None
        model: str | None = None
        emitted_text = False
        try:
            async for chunk in self._llm_client.stream(
                LLMRequest(
                    request_id=request.run_id,
                    session_id=request.session_id,
                    message=request.message,
                )
            ):
                provider = chunk.provider.value
                model = chunk.model
                if chunk.text:
                    emitted_text = True
                    yield RuntimeEvent(
                        type=RuntimeEventType.ASSISTANT_DELTA,
                        payload={"text": chunk.text},
                    )
            if not emitted_text:
                raise RuntimeError("LLM stream ended without text")
        except Exception as error:
            yield RuntimeEvent(
                type=RuntimeEventType.RUN_FAILED,
                payload={"error_type": type(error).__name__},
            )
            raise

        yield RuntimeEvent(
            type=RuntimeEventType.USAGE_UPDATED,
            payload={
                "provider": provider,
                "model": model,
                "cost_status": "unavailable",
            },
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)
