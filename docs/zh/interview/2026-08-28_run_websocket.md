# 2026-08-28 面试复盘：Agent Run 与 WebSocket 事件流

## 1. 一次 Agent 请求在项目中的完整调用链是什么？

客户端通过 WebSocket 发送 `send_message`，路由解析命令并创建后台 Task。`RunExecutionService` 查询 Session 和 Agent，通过 `RuntimeRegistry` 创建对应 Runtime，随后创建 Run、保存用户消息并消费 Runtime 的异步事件。

每个事件经过 Run 状态更新和事件持久化策略处理，再由 WebSocket 返回客户端。正常结束后，拼接 `assistant_delta` 并保存 assistant Message。

```text
workspace_socket -> _stream_run -> RunExecutionService.stream
-> RuntimeRegistry.create -> NativeAgentRuntime.stream
-> LLMRuntime.generate -> RuntimeEvent
-> RunExecutionService._process -> websocket.send_json
```

## 2. Run、Message 和 RunEvent 分别解决什么问题？

- `Run`：一次 Agent 执行记录，保存执行状态、Runtime、模型和耗时等摘要。
- `Message`：用户最终可见的对话历史，一个 Run 通常关联一条用户消息和一条助手消息。
- `RunEvent`：执行过程中的可审计事件，例如开始、检索、工具调用、handoff、结束或取消。

三者不能合并：Message 面向对话，Run 面向执行生命周期，RunEvent 面向过程追踪和断线恢复。

## 3. 为什么 Run 需要状态机，而不是直接修改 status？

状态机限制合法转换：例如 `pending -> running -> completed`，终态不能重新变为 running。这样可以避免重复结束、完成后又取消等无效状态，并将规则集中在 Service 层。

当前状态转换由 `RunService.transition()` 校验，Repository 只负责执行数据库修改。

## 4. Repository 和 Service 的事务职责如何划分？

Repository 负责 SQL 和 `flush()`，Service 负责业务边界上的 `commit()` 与 `rollback()`。

Repository 不应擅自提交，因为一个业务动作以后可能包含多次数据库操作。Service 知道什么时候整个动作完成，因此更适合决定事务结果。这类似 Go 中 Repository 接收 transaction，而 Usecase 决定提交或回滚。

## 5. 为什么 Runtime 使用异步生成器返回事件？

Agent 执行不是只有一个最终结果，中间还有开始、检索、工具、文本增量和结束等事件。异步生成器可以在同一个执行过程中多次 `yield`，调用方通过 `async for` 逐个消费，而不必等待所有步骤结束。

```python
async def stream(...):
    yield run_started
    result = await llm.generate(...)
    yield assistant_delta
    yield run_finished
```

`stream()` 返回异步迭代器；每次 `anext()` 推进到下一个 `yield`。

## 6. `yield` 和 `await` 在 Runtime 中分别负责什么？

- `yield`：向上游交付一个事件并暂停生成器，等待下一次迭代。
- `await`：等待 I/O 时把执行权交还事件循环，使线程能够处理其他连接。

因此 `yield` 解决“分段输出”，`await` 解决“I/O 等待期间不阻塞线程”，两者作用不同。

## 7. `AgentRuntimeAdapter(Protocol)` 在哪里实例化？

它不会实例化。`Protocol` 类似 Go interface，只声明 Runtime 必须提供 `stream()`。真正创建的是 `NativeAgentRuntime`，以后也可以是 `CodexAgentRuntime` 或 `ClaudeAgentRuntime`。

Python 支持结构化类型：具体类不需要显式继承 Protocol，只要方法签名兼容，静态类型检查就会把它视为 `AgentRuntimeAdapter`。

## 8. 为什么 Registry 注册 Factory，而不是 Runtime 对象？

Factory 是 `Callable[[], AgentRuntimeAdapter]`，保存“如何创建 Runtime”。每次 Run 调用 `factory()` 获得独立对象，避免多个执行共享取消状态、子进程句柄或临时上下文。

```python
registry.register("native", lambda: NativeAgentRuntime(llm_runtime))
```

这里的 lambda 是匿名工厂函数；注册时不创建 Runtime，`RuntimeRegistry.create("native")` 时才创建。

## 9. 为什么 WebSocket 路由把 Run 放入 `asyncio.create_task()`？

如果直接在接收循环中 `await` 完整 Run，连接只能等 Agent 执行结束，期间无法处理 ping、取消或恢复命令。创建后台 Task 后，接收循环和 Run 流可以并发推进。

当前约束是一个 WebSocket 连接最多运行一个活跃 Run，避免同一对话入口产生难以解释的并发执行。

## 10. 为什么多个协程发送 WebSocket 时需要 `asyncio.Lock`？

后台 Run 会发送事件，主接收循环也可能发送 pong、错误或补发事件。如果多个协程同时调用 `send_json()`，帧的发送顺序可能混乱，底层 WebSocket 实现也不保证并发发送安全。

`send_lock` 只序列化“发送操作”，不会阻止 LLM 调用或客户端消息接收。

## 11. 应用层 ping/pong 和 WebSocket 协议心跳有什么区别？

协议层 ping/pong 通常由 WebSocket Server、代理或客户端库处理，用于判断传输连接是否存活。项目的 `PingCommand/PongFrame` 是应用层 JSON 消息，可以携带 `request_id`，方便浏览器测量延迟并确认业务事件循环仍能响应。

生产环境通常还需要客户端超时、服务端 idle timeout 和反向代理配置，不能只依赖应用层 pong。

## 12. 客户端断开后，服务端如何感知？

FastAPI/Starlette 在下一次 `receive_json()` 或 `send_json()` 时发现底层连接关闭，并抛出 `WebSocketDisconnect`。这不是业务代码持续轮询连接状态。

如果网络进入半开状态，发现时间取决于 TCP、协议心跳和代理超时，因此实际部署仍需要合理的 heartbeat 与 timeout。

## 13. WebSocket 断线补发为什么使用 RunEvent.sequence，而不是表主键？

`sequence` 表示某个 Run 内事件的业务顺序，从 1 连续增长。客户端只需提交 `run_id + after_sequence`，就可以补发之后的事件。

数据库 ID 只保证记录身份，可能是 UUID，也可能跨 Run 交错，不能清晰表达单个 Run 内的顺序。业务协议不应依赖数据库主键实现细节。

## 14. 为什么 `assistant_delta` 不持久化，但终态事件需要持久化？

大量文本增量会显著增加数据库写入次数，重连后也通常可以通过最终 Message 恢复完整回答，因此当前将其设为“实时发送但不持久化”。

Run 开始、工具调用、handoff、完成、失败和取消等事件数量少且具有审计价值，需要持久化。事件策略通过 `stream/persist` 两个维度显式表达。

## 15. 主动取消 Run 的执行链是什么？

客户端发送 `cancel_run + run_id`。WebSocket 校验该 ID 是否属于当前连接的活跃 Task，然后调用 `task.cancel()`。

取消会在协程下一个可取消等待点注入 `CancelledError`。`RunExecutionService` 捕获后将 Run 改为 `cancelled`、持久化 `run_cancelled`、向客户端发送该事件，然后重新抛出取消异常完成 Task 退出。

## 16. 调用 `task.cancel()` 后为什么还要 `await task`？

`cancel()` 只是发出取消请求，不代表协程已经结束。继续 `await task` 才能等待它执行异常处理、数据库状态更新和 `finally` 资源清理。

```python
task.cancel()
with suppress(asyncio.CancelledError):
    await task
```

`suppress()` 只忽略预期的 `CancelledError`，其他异常仍然会暴露。

## 17. 为什么取消命令必须携带 run_id？

只发送 `cancel` 容易因网络延迟误取消已经替换的新任务。带 `run_id` 后，服务端可以确认客户端要取消的就是当前活跃 Run。

当前实现只允许取消同一 WebSocket 连接创建的 Run。未来若需要跨连接取消，应增加进程级 Run Manager，并处理多进程部署下的任务定位问题。

## 18. 当前所谓“流式输出”有什么限制？

WebSocket 和 RuntimeEvent 已经是流式的，但 Native Runtime 当前调用的是一次性 `LLMClient.generate()`，所以只会返回一整个 `assistant_delta`，还不是逐 Token 输出。

下一步应给 LLM Adapter 增加真正的 provider streaming，在收到每个文本 chunk 时产生 `assistant_delta`。WebSocket 和 RunExecutionService 基本可以复用，无需重新设计传输协议。

## 19. 如何接入 Codex 或 Claude，而不修改 WebSocket 主流程？

实现符合 `AgentRuntimeAdapter` 的 Runtime，将 Codex/Claude 的专有输出转换为统一 `RuntimeEvent`，然后注册 Factory：

```python
registry.register("codex", lambda: CodexAgentRuntime(codex_client))
```

Agent 表的 `runtime` 保存 `codex`。执行时 Registry 根据该字段创建 Runtime，上层仍然只消费 `RuntimeEvent`。这体现了依赖倒置和 Adapter 模式。

## 20. 当前实现有哪些明确的 MVP 边界？

- 单个连接最多一个活跃 Run。
- 活跃 Task 只保存在当前进程和连接内。
- `assistant_delta` 尚非 Provider Token 流。
- SQLite 的 RunEvent sequence 使用 `MAX + 1`，适合当前低并发演示，不适合高并发写入。
- client_id 目前是演示隔离边界，正式环境应来自认证信息。

面试时主动说明边界，比声称系统已经支持生产级分布式并发更可信。

## 快速自测

1. 为什么 Message、Run 和 RunEvent 不能合并成一张表？
2. `yield` 与 `await` 分别解决什么问题？
3. `Protocol` 为什么不需要实例化？
4. 为什么要把 Agent Run 放到后台 Task？
5. `task.cancel()` 后为什么还必须 `await task`？
6. 断线补发为什么使用业务 sequence，而不是数据库 ID？
7. 当前 WebSocket 流式输出与真正 Token streaming 有什么差距？
8. 如何在不修改 RunExecutionService 的情况下接入 Codex Runtime？
