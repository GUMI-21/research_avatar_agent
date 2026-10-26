"""Collect one existing teaching Run into a non-streaming HTTP result."""

from contextlib import aclosing

from pydantic import ValidationError

from app.adapters.agent import RuntimeEventType
from app.schemas.teaching import TeachingChatRequest, TeachingChatResponse
from app.services.run_execution import RunExecutionService
from app.services.teaching_output import TeachingOutputError


class TeachingChatService:
    def __init__(self, execution: RunExecutionService) -> None:
        self._execution = execution

    async def respond(self, client_id: str, request: TeachingChatRequest) -> TeachingChatResponse:
        run_id = None
        reply: list[str] = []
        presentation = None
        # 绑定校验和守卫都在执行服务内；这里不能重复占锁或直接调用 LLM。
        async with aclosing(self._execution.stream(
            client_id, request.session_id, request.message, require_teaching=True,
        )) as events:
            async for item in events:
                run_id = item.run_id
                if item.event.type is RuntimeEventType.ASSISTANT_DELTA:
                    text = item.event.payload.get("text")
                    if isinstance(text, str):
                        reply.append(text)
                if item.event.type is RuntimeEventType.RUN_FINISHED:
                    presentation = item.event.payload.get("teaching")
        if run_id is None or not isinstance(presentation, dict):
            raise TeachingOutputError("missing_completed_turn")
        try:
            return TeachingChatResponse.model_validate({
                **presentation, "session_id": request.session_id,
                "run_id": run_id, "reply": "".join(reply),
            })
        except ValidationError:
            raise TeachingOutputError("invalid_runtime_result") from None
