"""WebSocket entrypoint for streamed Personal Agent Runs."""

from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.adapters.agent import RuntimeEventType
from app.core.database import Database
from app.schemas.run_stream import (
    WORKSPACE_COMMAND_ADAPTER,
    ReplayCompleteFrame,
    ResumeRunCommand,
    RunEventFrame,
    WebSocketErrorFrame,
)
from app.services import (
    RunEventService,
    RunExecutionParentNotFoundError,
    RunExecutionService,
)
from app.services.runtime_registry import RuntimeNotFoundError, RuntimeRegistry
from logs import log

router = APIRouter()


# websocket接口
@router.websocket("/ws")
async def workspace_socket(
    websocket: WebSocket,
    client_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> None:
    await websocket.accept()
    database: Database = websocket.app.state.database
    registry: RuntimeRegistry = websocket.app.state.runtime_registry
    log.info("websocket_connected business=agent_workspace client_id={}", client_id)
    try:
        while True:
            try:
                # 暂停当前协程，收到客户端消息后继续；不会阻塞事件循环
                command = WORKSPACE_COMMAND_ADAPTER.validate_python(
                    await websocket.receive_json()
                )
            except (ValidationError, ValueError):
                await _send_error(
                    websocket,
                    "invalid_command",
                    "Expected a valid send_message command",
                )
                continue

            if isinstance(command, ResumeRunCommand):
                try:
                    await _replay_run(websocket, database, client_id, command)
                except WebSocketDisconnect:
                    raise
                except Exception as error:
                    log.warning(
                        "websocket_replay_failed business=agent_workspace "
                        "client_id={} run_id={} error_type={}",
                        client_id,
                        command.run_id,
                        type(error).__name__,
                    )
                    await _send_error(
                        websocket,
                        "replay_failed",
                        "Run event replay failed",
                    )
                continue

            try:
                async with database.session() as session:
                    # 消费 Agent Run 事件流，并将允许公开的事件发送给客户端
                    service = RunExecutionService(session, registry)
                    async for item in service.stream(
                        client_id,
                        command.session_id,
                        command.content,
                    ):
                        frame = RunEventFrame(
                            type=item.event.type,
                            run_id=item.run_id,
                            sequence=item.sequence,
                            payload=dict(item.event.payload),
                        )
                        # 转换为只包含 JSON 兼容值的字典
                        await websocket.send_json(frame.model_dump(mode="json"))
            except WebSocketDisconnect:
                # 继续抛给外层统一记录断开日志
                raise
            except RunExecutionParentNotFoundError:
                await _send_error(websocket, "not_found", "Session not found")
            except RuntimeNotFoundError:
                await _send_error(
                    websocket,
                    "runtime_not_found",
                    "Agent runtime is unavailable",
                )
            except Exception as error:
                log.warning(
                    "websocket_run_failed business=agent_workspace client_id={} "
                    "session_id={} error_type={}",
                    client_id,
                    command.session_id,
                    type(error).__name__,
                )
                await _send_error(websocket, "run_failed", "Agent run failed")
    except WebSocketDisconnect:
        log.info(
            "websocket_disconnected business=agent_workspace client_id={}",
            client_id,
        )


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
) -> None:
    frame = WebSocketErrorFrame(code=code, message=message)
    await websocket.send_json(frame.model_dump(mode="json"))


# webSocket断线补发
async def _replay_run(
    websocket: WebSocket,
    database: Database,
    client_id: str,
    command: ResumeRunCommand,
) -> None:
    async with database.session() as session:
        records = list(
            await RunEventService(session).replay(
                client_id,
                command.run_id,
                after_sequence=command.after_sequence,
                limit=command.limit + 1,
            )
        )
    has_more = len(records) > command.limit
    records = records[: command.limit]
    for record in records:
        frame = RunEventFrame(
            type=RuntimeEventType(record.event_type),
            run_id=record.run_id,
            sequence=record.sequence,
            payload=record.payload,
        )
        await websocket.send_json(frame.model_dump(mode="json"))
    complete = ReplayCompleteFrame(
        run_id=command.run_id,
        last_sequence=(records[-1].sequence if records else command.after_sequence),
        count=len(records),
        has_more=has_more,
    )
    await websocket.send_json(complete.model_dump(mode="json"))
