"""Native Personal Agent runtime backed by the configured LLM API."""

from collections.abc import AsyncIterator

from app.adapters.agent.base import (
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)
from app.adapters.llm import LLMClient, LLMRequest


class NativeAgentRuntime:
    """Normalize one provider call into auditable Agent Runtime events."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    # 返回异步迭代器
    async def stream(
        self,
        request: RuntimeRequest,
    ) -> AsyncIterator[RuntimeEvent]:
        # 每次调用前进一次
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.AGENT_STARTED,
            payload={"agent_id": request.agent_id, "runtime": "native"},
        )
        try:
            # 获取llm msg
            result = await self._llm_client.generate(
                LLMRequest(
                    request_id=request.run_id,
                    session_id=request.session_id,
                    message=request.message,
                )
            )
        except Exception as error:
            yield RuntimeEvent(
                type=RuntimeEventType.RUN_FAILED,
                payload={"error_type": type(error).__name__},
            )
            raise

        yield RuntimeEvent(
            type=RuntimeEventType.ASSISTANT_DELTA,
            payload={"text": result.text},
        )
        yield RuntimeEvent(
            type=RuntimeEventType.USAGE_UPDATED,
            payload={
                "provider": result.provider.value,
                "model": result.model,
                "cost_status": "unavailable",
            },
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)
