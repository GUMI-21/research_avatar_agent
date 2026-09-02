# Personal Agent Workspace

## 阶段目标

在 7 到 9 天内完成一个可在本机稳定演示、可写入简历、可用于 AI Agent 实习面试的个人 Agent Workspace。

项目重点展示：

- FastAPI 异步服务、WebSocket 事件流和持久化设计。
- 面向 Obsidian/Markdown 的中文个人知识库 RAG。
- 自研 Personal Agent Runtime 和基于 LangGraph 的多 Agent 编排。
- 同一对话内的多 Agent handoff，以及 Codex/Claude 专业执行 Agent。
- 上下文、引用、Token、费用、延迟和调用频率的可观测性。

本阶段前端不负责 Avatar 教学脚本。Avatar、情绪模型、语音和 Unity 开发暂时暂停，但现有 Unity API 保持兼容。

## 候选人定位

- 主要投递方向：AI Agent 实习。
- 补充优势：两年 Go 后端经验，熟悉服务端分层、协议、并发和可观测性。
- Agent 编排采用 Python 生态；工程边界使用 Go 后端常见的 handler/service/repository/adapter 思路。
- 本阶段不增加 Go 微服务，避免在短周期内维护两套运行时。

## 核心演示

1. 用户注册一个本地演示客户端并创建 Personal、Researcher、Coder Agent。
2. 用户导入一个 Obsidian Vault 或 Markdown 目录。
3. 系统增量索引笔记，并记录 Obsidian 图片引用关系。
4. 用户在 Web 对话中提出与个人知识库相关的问题。
5. Personal Agent 检索笔记并展示引用和实际注入的上下文。
6. Personal Agent 根据显式策略将部分任务交给 Researcher 或 Coder。
7. 原生 Agent 使用云端 LLM；Coder 可将 Codex 或 Claude 作为可选专业执行 Agent。
8. 所有 Agent 的消息、handoff 和运行状态显示在同一对话中。
9. Usage 页面展示调用次数、Token、费用、耗时和错误。

## 总体架构

```text
React Web
  ├── REST: Agent / Session / Knowledge / Usage CRUD
  └── WebSocket: message / retrieval / handoff / tool / result events
          |
          v
FastAPI
  ├── API and WebSocket routes
  ├── Session and Run Manager
  ├── Personal Agent Runtime
  │      └── LangGraph Orchestrator
  ├── Knowledge Base / RAG Service
  ├── Usage and Context Inspector
  ├── Repository interfaces
  └── Runtime Gateway
         ├── existing cloud LLM adapters
         ├── ACP Adapter: Codex / Claude
         └── direct CLI adapters (fallback)
          |
          v
SQLite WAL + FTS5 + Qdrant Local vector index
```

FastAPI 是服务边界。LangGraph 只负责一次 Agent run 内的状态转移，不直接负责 API、数据库、文件扫描或 CLI 子进程生命周期。

## 通信协议

### REST

REST 用于短生命周期、容易重试的资源操作：

- Agent CRUD。
- Session 创建、列表和归档。
- Knowledge source 导入、同步和状态查询。
- Usage 汇总查询。
- Demo client 初始化。

### WebSocket

WebSocket 用于长时间运行且需要双向控制的 Agent turn：

```json
{"type":"send_message","session_id":"...","content":"..."}
{"type":"cancel_run","run_id":"..."}
```

服务端事件尽量兼容 AG-UI，并补充项目特有的上下文、handoff 和 usage 事件：

```text
run_started
retrieval_started / retrieval_result
agent_started / agent_status
assistant_delta
tool_started / tool_finished
handoff_started / handoff_finished
usage_updated
run_finished / run_failed
```

前端展示可审计进度，例如“正在检索知识库”“正在调用 Coder”“工具执行完成”。不保存或展示模型隐藏的原始思维链。若运行时明确提供 reasoning summary，则作为独立、可标记来源的摘要事件处理。

## 客户端隔离

从第一版开始，以下资源都包含 `client_id`：

- agents
- sessions
- messages
- runs and run_events
- delegations
- knowledge_sources, documents and chunks
- usage_events

所有 Repository 方法必须显式接收 `client_id`，查询条件不能只使用资源 ID。第一版可以通过本地 Bearer Token 映射到固定 client；后续再增加完整注册和登录。

系统只面向个位数演示客户端：

- 单 FastAPI 进程。
- SQLite WAL。
- 进程内 run manager。
- 每客户端和每会话设置小型并发上限。
- 暂不引入 Redis、Kafka、Celery 或 Kubernetes。

公开展示时使用受限 Demo Client：只允许访问 seed 数据，关闭本地文件路径和危险 CLI 工具，设置调用额度。

## Obsidian 与中文 RAG

### 输入范围

- UTF-8 Markdown。
- YAML frontmatter。
- `[[note]]` 内部链接。
- `![[image.png]]` Obsidian 图片嵌入。
- `![alt](relative/path.png)` 标准 Markdown 图片。
- 中文为主，保留英文和日文原文。

### 图片策略

MVP 不直接对全部图片做 OCR：

- 解析图片引用并关联原笔记、相对路径和附近文本。
- 通过受控资产 API 在知识详情页预览图片。
- 防止 `..` 路径穿越，不能读取 Vault 根目录之外的文件。
- 检索结果命中笔记时可携带相关图片元数据。

OCR、图片 embedding 和多模态问答在文本 RAG 稳定后再实现。

### 检索流程

```text
scan files
  -> parse metadata, links and assets
  -> chunk by Markdown structure
  -> keyword index + vector index
  -> retrieve both channels
  -> rank and deduplicate
  -> apply client/source filters
  -> build cited context
```

中文 embedding 模型保持可替换。Batch 3 开始前在目标 Mac 上比较小型多语言模型与 BGE 系列的安装体积、速度和检索质量，再冻结默认值。

## 多 Agent 模型

- 原生 Personal Agent 是入口和协调者，负责意图判断、检索、上下文组装、路由和结果汇总；没有 Codex/Claude 时也必须独立运行。
- Agent 是持久配置：名称、Prompt、Runtime、Model、工具策略和知识库范围。
- Session 属于一个入口 Agent。
- Message 带 `agent_id`，因此一个聊天窗口可以显示多个 Agent。
- Delegation 保存父 run、目标 Agent、任务摘要、状态和结果。
- 手动 handoff 使用 `@agent-name`。
- 自动 handoff 使用受控的 `delegate_to_agent` 工具。
- 子 Agent 默认只接收任务摘要、显式引用和必要上下文，不复制完整父会话。
- MVP 最大 handoff 深度为 2，并检测循环。
- MVP 先实现单链路流式 handoff；并行和后台委派后置。

## Runtime Gateway

所有运行时输出统一为 `RuntimeEvent`：

- text delta
- status
- tool call and result
- usage
- result
- error

运行时包括：

- 当前 OpenAI、Gemini、DeepSeek、Mock API adapter。
- 优先通过 ACP 接入 Codex 和 Claude。
- 直接 Codex/Claude CLI adapter 仅作为兼容回退。

CLI adapter 必须限制工作目录、超时、允许工具和环境变量；密钥、完整 Prompt 和敏感笔记内容不得写入普通日志。

## 用量与上下文管理

每次 run 记录：

- client、session、agent、runtime、provider 和 model。
- 输入、输出和缓存 Token（运行时可提供时）。
- reported / estimated / unavailable 计费状态。
- duration、time to first token 和错误类型。
- RAG 命中的 chunk 和最终注入上下文。
- handoff 和工具执行次数。

Usage 页面优先保证数据诚实，不把估算费用表示成账单实际费用。

## 开发批次

### 当前实现状态（2026-08-31）

- 已完成 Agent、Session、Message、Run 和 RunEvent 数据基础与客户端隔离。
- 已完成 Native Runtime、三家 LLM 流式输出、WebSocket 取消/重连，以及用量、成本、延迟的记录与查询。
- Web 前端确定为 React 19、TypeScript、Vite、TanStack Query、Zustand 和 Tailwind CSS。
- Workspace 采用 Agent/Session 侧栏、对话事件流和 Context/Run/Usage Inspector 三栏布局。
- Web Shell 已完成并暂停扩展；Usage API 完成后优先进入 Obsidian RAG 与 LangGraph 编排。
- Obsidian RAG 已开始建设 KnowledgeSource 与 KnowledgeDocument 数据基础。
- KnowledgeSource 已具备客户端隔离的 Repository、事务服务和本地目录安全校验。
- KnowledgeSource REST API 支持注册、列表和详情查询；目录扫描通过后续同步操作显式触发。
- Vault 扫描器可安全发现 Markdown、计算内容哈希，并忽略隐藏目录和越界软链接。
- Markdown 解析器可提取 frontmatter、标题、Obsidian 双链及图片引用。
- KnowledgeSource 同步服务可增量创建、更新和删除文档元数据，并记录同步状态。
- Web 客户端可通过 KnowledgeSource 同步 API 主动导入 Vault 并查看增量统计。
- KnowledgeDocument API 支持按路径游标分页和客户端隔离的详情查询。
- Markdown 标题分块保留标题路径、原文件行号和内容哈希，Chunk 表提供持久化基础。
- KnowledgeSource 增量同步会原子化重建变化文档的 Chunk，并跳过已索引文档。

### Batch 0：架构与规则

- 固化本文档、协作规则和按需面试复盘机制。
- 确认 Python、Node、Codex 和 Claude 开发环境。

### Batch 1：数据基础

- SQLite、迁移、client isolation。
- Agent、Session 和 Message Repository/API。

### Batch 2：WebSocket 纵向切片

- React Web Shell。
- REST Agent/Session 列表。
- WebSocket Mock Chat 和标准事件流。

### Batch 3：Obsidian RAG

- Vault 导入、Markdown/asset 解析、增量同步。
- 中文混合检索、引用和 Context Inspector。

### Batch 4：Agent 编排

- LangGraph run、checkpoint 和 trace。
- 手动/自动 handoff。

### Batch 5：外部 Agent Runtime

- ACP 兼容性验证和 Codex/Claude Adapter；必要时增加直接 CLI 回退。
- 运行取消、超时和事件归一化。

### Batch 6：面试打包

- Usage Dashboard。
- Demo mode、安全收口和错误处理。
- README、测试、演示视频和面试讲解。

每批核心实现约 100 行，完成后测试并暂停 Review。

## 完成标准

- 新环境能够按照 README 启动。
- 可以创建 Agent 和 Session。
- WebSocket 可以稳定流式输出运行事件和回复。
- 可以导入真实 Obsidian 笔记并回答带引用的问题。
- 自研 Personal Agent 在没有 Codex/Claude CLI 时也可以独立检索、编排并回答。
- 可以在同一对话中将任务交给另一个 Agent。
- Codex 和 Claude 至少完成受控的真实运行验证。
- 客户端之间无法通过资源 ID 读取彼此的数据。
- 页面可以解释一次回答使用了哪些上下文、模型、Token、费用和时间。
- 有可重复的两分钟演示脚本，并可按需生成项目面试题。
