"""WebSocket entrypoint for streamed Personal Agent Runs."""

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError

from app.adapters.agent import RuntimeEventType
from app.adapters.knowledge import EmbeddingClient
from app.core.database import Database
from app.schemas.run_stream import (
    WORKSPACE_COMMAND_ADAPTER,
    CancelRunCommand,
    PingCommand,
    PongFrame,
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


@dataclass
class ActiveRun:
    task: asyncio.Task[None] | None = None
    # 当前 Agent 执行记录的 ID，由 RunExecutionService 创建
    run_id: str | None = None


# websocket接口
@router.websocket("/ws")
async def workspace_socket(
    websocket: WebSocket,
    client_id: Annotated[str, Query(min_length=1, max_length=64)],
) -> None:
    await websocket.accept()
    database: Database = websocket.app.state.database
    registry: RuntimeRegistry = websocket.app.state.runtime_registry
    embedding_client: EmbeddingClient = websocket.app.state.embedding_client
    log.info("websocket_connected business=agent_workspace client_id={}", client_id)
    # 异步协程锁，保证发送消息不冲突
    send_lock = asyncio.Lock()
    # 当前连接的活跃 Run 状态
    active_run = ActiveRun()
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
                    send_lock,
                    "invalid_command",
                    "Expected a valid workspace command",
                )
                continue
            # 客户端应用层心跳；isinstance 检查命令的实际类型
            if isinstance(command, PingCommand):
                await _send_frame(
                    websocket,
                    send_lock,
                    PongFrame(request_id=command.request_id),
                )
                continue
            # 终止当前连接中正在执行的 Agent Run
            if isinstance(command, CancelRunCommand):
                task = active_run.task
                if (
                    task is None
                    or task.done()
                    or active_run.run_id != command.run_id
                ):
                    await _send_error(
                        websocket,
                        send_lock,
                        "run_not_active",
                        "Run is not active on this connection",
                    )
                    continue
                # 取消正在执行的task
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                continue
            # 客户端重连后，通过 ResumeRunCommand 请求补发事件
            if isinstance(command, ResumeRunCommand):
                try:
                    await _replay_run(
                        websocket,
                        send_lock,
                        database,
                        client_id,
                        command,
                    )
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
                        send_lock,
                        "replay_failed",
                        "Run event replay failed",
                    )
                continue
            # 当前连接已有活跃 Run 时，拒绝启动第二个 Run
            if active_run.task is not None and not active_run.task.done():
                await _send_error(
                    websocket,
                    send_lock,
                    "run_in_progress",
                    "This connection already has an active Run",
                )
                continue
            active_run.run_id = None
            active_run.task = asyncio.create_task(
                _stream_run(
                    websocket,
                    send_lock,
                    database,
                    registry,
                    embedding_client,
                    client_id,
                    command.session_id,
                    command.content,
                    active_run,
                )
            )
    # WebSocket 接收消息时检测到断连
    except WebSocketDisconnect:
        log.info(
            "websocket_disconnected business=agent_workspace client_id={}",
            client_id,
        )
    finally:
        if active_run.task is not None and not active_run.task.done():
            active_run.task.cancel()
            # 调用cancel，CancelledError是预期结果，等待任务资源关闭
            with suppress(asyncio.CancelledError):
                await active_run.task


async def _send_error(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    code: str,
    message: str,
) -> None:
    frame = WebSocketErrorFrame(code=code, message=message)
    await _send_frame(websocket, send_lock, frame)


async def _send_frame(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    frame: BaseModel,
) -> None:
    async with send_lock:
        await websocket.send_json(frame.model_dump(mode="json"))


async def _stream_run(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    database: Database,
    registry: RuntimeRegistry,
    embedding_client: EmbeddingClient,
    client_id: str,
    session_id: str,
    content: str,
    active_run: ActiveRun,
) -> None:
    try:
        async with database.session() as session:
            service = RunExecutionService(session, registry, embedding_client)
            # 异步消费已经拆分好的 Agent 执行事件
            async for item in service.stream(client_id, session_id, content):
                if active_run.run_id is None:
                    active_run.run_id = item.run_id
                await _send_frame(
                    websocket,
                    send_lock,
                    RunEventFrame(
                        type=item.event.type,
                        run_id=item.run_id,
                        sequence=item.sequence,
                        payload=dict(item.event.payload),
                    ),
                )
    # 发送消息时检测到断连
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        raise
    except RunExecutionParentNotFoundError:
        await _send_error(websocket, send_lock, "not_found", "Session not found")
    except RuntimeNotFoundError:
        await _send_error(
            websocket,
            send_lock,
            "runtime_not_found",
            "Agent runtime is unavailable",
        )
    except Exception as error:
        log.warning(
            "websocket_run_failed business=agent_workspace client_id={} "
            "session_id={} error_type={}",
            client_id,
            session_id,
            type(error).__name__,
        )
        await _send_error(websocket, send_lock, "run_failed", "Agent run failed")


# webSocket断线补发
async def _replay_run(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
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
        await _send_frame(websocket, send_lock, frame)
    complete = ReplayCompleteFrame(
        run_id=command.run_id,
        last_sequence=(records[-1].sequence if records else command.after_sequence),
        count=len(records),
        has_more=has_more,
    )
    await _send_frame(websocket, send_lock, complete)
