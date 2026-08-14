# 2026-08-14 面试复盘：Agent Workspace 架构

## 1. 为什么同时使用 REST 和 WebSocket？

REST 适合 Agent、Session、Knowledge Source 这类短生命周期、幂等或容易重试的资源操作。Agent run 会持续较长时间，期间既要向浏览器推送文本和工具事件，也要接收取消、审批或回答，因此使用 WebSocket。

对应 Go 服务，可以理解为 REST handler 管理资源，WebSocket connection 持续订阅 run manager 的事件总线。两者最终调用同一 application service，而不是各自实现一套业务逻辑。

## 2. 为什么不用 SSE？

SSE 对服务端单向推送更简单。如果只需要 Token streaming，SSE 足够。本项目还计划支持取消 run、工具审批和 Agent 提问，因此双向 WebSocket 更自然。代价是需要处理连接恢复、心跳、重复事件和慢客户端。

## 3. “思考中”是否等于展示模型思维链？

不是。产品应展示可审计的系统事件，例如正在检索、调用哪个 Agent、执行哪个工具、等待审批和生成回复。隐藏的模型 chain-of-thought 不应被保存或展示。若 Provider 明确返回 reasoning summary，应把它作为有来源标记的摘要事件，而不是假设它等于模型内部完整推理。

## 4. 为什么选择 LangGraph，而不是只使用 LangChain Agent？

LangChain 提供模型、工具和文档组件；LangGraph更适合显式状态、条件路由、checkpoint、恢复和多 Agent handoff。项目需要在 UI 中解释每一步状态，因此显式 Graph 比隐藏在单个 Agent loop 中更容易测试和观测。

同时不让 LangGraph直接操作数据库和 CLI。Graph node 调用 service interface，这样未来替换编排框架时不会重写整个系统。

## 5. 如何实现多客户端数据隔离？

所有持久资源都有 `client_id`，Repository 查询必须同时包含 `client_id` 和资源 ID。不能先按 ID 查询资源，再在 Python 中检查归属，因为那容易在新增接口时漏掉检查。

更严格的生产方案可以使用 PostgreSQL Row Level Security；当前个位数客户端的演示系统使用 SQLite，并通过 Repository contract 和隔离测试保证约束。

## 6. 为什么演示项目仍然从第一版加入 client_id？

如果后期才增加租户字段，所有表、唯一索引、缓存键、文件路径和查询方法都需要迁移。现在加入字段成本很低，也能在面试中说明系统的安全边界，但不会因此提前引入完整 IAM 或分布式架构。

## 7. Obsidian 图片引用如何处理？

解析器同时识别 `![[image.png]]` 和 `![alt](path)`，将图片作为 asset 元数据关联到原笔记和附近 chunk。资产读取必须先解析真实路径，并验证它仍位于 Vault 根目录内，防止 `../` 路径穿越。

第一版不批量 OCR，因为图片处理会扩大依赖、索引时间和噪声。先保证文字检索、引用和图片预览，再用真实笔记评估是否需要多模态检索。

## 8. 为什么先使用 SQLite？

这是本地优先、个位数客户端的作品集阶段。SQLite WAL 能提供足够的并发读写和非常低的部署成本，Octopus 也采用了相近路线。代码仍通过 Repository 隔离持久化细节，后续可迁移 PostgreSQL。

不使用 Redis、Kafka 或 Celery 不是因为不了解它们，而是当前负载和可靠性目标没有证明这些组件的必要性。

## 9. 这个项目如何体现 Go 后端经验？

虽然 Agent 生态选择 Python，但系统仍强调 Go 后端常见能力：明确 DTO、接口隔离、context/cancellation、进程生命周期、幂等事件、租户作用域、错误分类、指标和测试。面试重点应放在这些工程决策，而不是语言语法。

## 10. Skills 和 MCP 分别是什么？

Skill 是一组可复用的任务说明、领域知识和执行流程，帮助 Agent 在特定任务中采用稳定做法。MCP 是 Agent 与外部工具或数据源交互的协议边界。

本项目后续可以把“检索个人知识库”做成内部工具，再通过 MCP 暴露给 Codex/Claude；把“项目面试复盘”整理成 Skill。实现这些功能时，需要继续补充鉴权、工具 schema、超时、幂等和恶意工具输出等面试知识点。
