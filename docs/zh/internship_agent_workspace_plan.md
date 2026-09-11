# Personal Agent Workspace

## 阶段目标

完成一个可在本机稳定演示、可写入简历、可用于 AI Agent 实习面试的个人 Agent Workspace。

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

以上为目标架构。2026-09-09 代码使用 SQLite 保存向量并执行精确余弦检索，尚未接入
Qdrant；也尚未配置 WAL。RunExecutionService 已通过 LangGraph 状态图协调运行。

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
context_prepared
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

### Markdown Chunk 策略

问题：知识库的 Chunk 是如何切分的，是否根据目录区分？

目录不直接决定 Chunk 边界。一个注册目录对应一个 `KnowledgeSource`，目录中的每个
Markdown 文件对应一个 `KnowledgeDocument`；`source_id` 和 `relative_path` 用于限定
检索范围及生成引用。每个文件再独立执行以下分块流程：

1. 跳过 YAML frontmatter，不把配置元数据混入正文向量。
2. 识别一级到六级 Markdown 标题，并保存当前 `heading_path`；标题用于定位上下文，
   不直接重复写入正文 Chunk。
3. 同一标题下按完整文本行累积，默认上限为 1200 个字符；加入下一行会超限时切块。
4. 单行超过上限时进行硬切分；代码块中的 `#` 不被误判为标题。
5. 排除内嵌 Base64 图片数据；普通图片引用目前由解析器提取，持久化关联表后续实现。
6. 每个 Chunk 保存文档内顺序、原文件起止行号和内容 SHA-256，支持引用跳转与增量重建。

例如 `notes/AI/RAG.md` 的目录 `AI/` 只是路径元数据；文件内的“检索”“重排”两个标题
会形成不同的标题上下文，并在内容过长时继续拆成多个 Chunk。当前没有重叠窗口，也不
按 Token 精确切分；完成真实检索评测后，再根据召回质量决定是否增加 overlap 或改为
Token 上限。

中文 embedding 模型保持可替换。

### Embedding 模型选择（2026-09-03）

问题：为什么当前选择 `paraphrase-multilingual-MiniLM-L12-v2`，而不是其他模型？

当前阶段以 Windows/macOS 本地运行、快速形成面试 Demo 为优先，因此默认使用 FastEmbed 的
ONNX 版本：约 0.22 GB、384 维、支持约 50 种语言，不需要 API Key，也不会把私人
笔记发送到云端。它的检索质量不是最终结论，但足以低成本验证完整 RAG 链路。

| 候选模型 | 优点 | 当前未选择的原因 |
| --- | --- | --- |
| multilingual MiniLM（当前） | 轻量、多语言、本地 ONNX 推理 | 更偏语义相似度，后续仍需用真实问题评估召回质量 |
| BGE-small-zh-v1.5 | 更小且针对中文 | 不符合笔记中英文、日文混合的长期需求 |
| multilingual-e5-large | 1024 维、多语言、面向检索 | FastEmbed 模型约 2.24 GB，本阶段部署和推理成本偏高 |
| BGE-M3 | 100+ 语言、8192 Token，支持 dense、sparse 和 ColBERT | 能力更完整，但模型及检索链路更复杂，留作质量升级候选 |
| 云端 Embedding API | 无需在本地加载模型 | 有网络、费用和私人笔记外发问题 |

冻结策略：接口与数据表不绑定模型。先用当前模型完成向量召回与混合检索，再从真实
笔记整理一组查询及相关 Chunk，对 MiniLM 和 BGE-M3 做速度、内存与 Recall@K 对比；
只有评测显示明显收益时才更换默认模型，更换后通过 `model + content_hash` 重建向量。

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

首版在每条 Assistant 回复对应的 Run 详情中展示 Provider、Model、输入/输出/缓存 Token、
估算费用、首 Token 延迟、总耗时和错误；会话详情汇总该 Session 下的 Runs。Usage 页面
优先保证数据诚实，不把估算费用表示成账单实际费用。CC Switch 风格的时间曲线及按
Provider/Model 聚合属于后续增强，不阻塞可用 Workspace。

## 开发批次

### 当前实现状态（2026-09-11）

Native Agent 聊天执行链已接入其绑定知识库的混合检索，并在 6000 字符预算内注入带
引用上下文；缺少 Embedding Client 的轻量执行仍可回退到关键词检索。运行事件会记录
检索策略、每个知识库的候选 Chunk 与预算后实际选中的 Chunk，但不持久化笔记正文。
文本 RAG 基础链路到此暂缓；真实 Vault 调优、图片关系和完整 Context Inspector 延后。
当前优先完成 LangGraph、handoff 和可正常使用的 Web Workspace。Windows 环境步骤见
[Server README](../../server/README.md)。

LangGraph 第二批已将生产 `RunExecutionService` 和 WebSocket 执行链路切换到状态图。
第三批为 `send_message` 增加显式 `target_agent_id`，不同于 Session 入口 Agent 时执行
`prepare -> handoff -> agent`，并持久化可重放的 handoff 事件。checkpoint 不包含消息、
Prompt 或 RAG 正文；持久化 checkpoint 仍待后续阶段。

LangGraph 第四批开始建设自动 handoff：LLM 与 Runtime 已有 provider-neutral 的工具定义、
工具调用和候选 Agent 契约。Native Runtime 仅接受白名单内、非当前 Agent、单次且任务摘要
不超过 2,000 字符的 `delegate_to_agent` 请求。OpenAI Responses API 已能发送该工具并将流式
函数调用还原为统一事件。生产执行服务会按 `client_id` 提供除当前 Agent 外的候选，并向
Native Runtime 注入最近 12 条、最多 6,000 字符的会话上下文。LangGraph 收到自动 handoff
后会携任务摘要切换目标 Runtime，最多连续转交两次并拒绝循环，最终回复归属实际响应 Agent。

- 已完成 Agent、Session、Message、Run 和 RunEvent 数据基础与客户端隔离。
- 已完成 Native Runtime、三家 LLM 流式输出、WebSocket 取消/重连，以及用量、成本、延迟的记录与查询。
- Web 前端确定为 React 19、TypeScript、Vite、TanStack Query、Zustand 和 Tailwind CSS。
- Workspace 采用 Agent/Session 侧栏、对话事件流和 Agent/Memory/Run/Usage Inspector 三栏布局。
- Web 第一批已接入真实 Agent、Session 和 Message REST API，支持创建 Agent、创建会话、
  读取历史消息及资源加载/错误/空状态。第二批已接入 WebSocket 消息发送、流式回复、
  Run/handoff/usage 事件、取消运行及断线后的持久化事件补发。
- Web 第三批将持久化 Run 与 Usage API 接入右侧 Inspector，可按当前会话查看模型、状态、
  输入/输出 Token、估算费用、总耗时、首 Token 延迟和错误，并展示 Workspace 用量汇总。
- 长期记忆第一批已提供按 `client_id + agent_id` 隔离的 Memory 创建、列表、启停和删除 API；
  Native Runtime 按 4,000 字符预算注入启用项，handoff 使用目标 Agent 记忆，并只在 Run 事件中审计 Memory ID。
- Web Memory Inspector 已直接接入上述 API，支持查看、新增、启停和删除当前 Agent 的长期记忆。
- Web 模型设置直接使用 Server 的 Provider Catalog 与 LLM Runtime 配置接口，可读取当前安全摘要、
  切换 Provider/Model，并选择临时提交 API Key 或使用环境变量；页面不持久化或回显密钥。
- 会话标题区提供真实 Session 历史下拉选择；创建 Agent 时从当前 Workspace Provider Catalog
  选择默认模型。Agent 模型会随 RuntimeRequest 进入实际 LLM 调用，handoff 后改用目标 Agent 模型。
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
- SQLite FTS5 trigram 索引提供中文关键词召回、BM25 排序和短词回退查询。
- Knowledge Search API 返回可审计 Citation，包括文档路径、标题层级、原文行号和检索分数。
- Embedding 接口区分查询与文档编码，向量记录可按模型和内容哈希增量更新。
- Embedding 索引服务按 Chunk 内容哈希跳过未变化数据，并以批次调用模型。
- 本地 FastEmbed 使用多语言 MiniLM ONNX 模型，推理放在线程中避免阻塞事件循环。
- Knowledge Embedding API 可按客户端和知识库触发首次或增量向量化。
- 检索 API 支持关键词或向量策略；向量模式以归一化向量点积完成精确余弦排序。
- 支持以 RRF 融合关键词与向量排名的混合检索，避免直接比较 BM25 和余弦分数。
- 检索结果按文件、标题与原文行号组装为有字符预算的上下文，并将笔记标注为不可信参考资料。
- Agent 可显式绑定多个同客户端知识库，为运行时 RAG 限定检索范围。
- Agent system prompt 通过统一 LLM 请求传递，并映射为各厂商原生 system instruction。
- Native Agent Run 使用绑定知识库构造引用上下文，并持久化可重放的上下文选择元数据。
- Native Agent Run 默认使用混合检索，并在无 Embedding Client 时回退到关键词检索。

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
- 中文混合检索、引用和运行时上下文注入已完成；其余完善暂缓。

### Batch 4：Agent 编排（当前最高优先级）

- 用 LangGraph 管理 run state、节点推进、checkpoint 和可审计 trace。
- 后端已支持按目标 ID 手动 handoff，以及最多两层、拒绝循环的自动 handoff 连续执行；前端发送区可为单次请求选择目标 Agent，并以 Agent 名称展示手动或自动转交事件。

### Batch 5：可用 Web Workspace

- 接入真实 Agent/Session CRUD、消息历史、流式运行、取消和重连。
- 展示 Agent 状态、handoff、工具事件和错误；在每个回复的 Run 详情及会话详情展示 Usage。
- 增加可查看、添加、禁用和删除的轻量长期记忆，并按预算注入 Agent 上下文。

### Batch 6：Usage 与面试版本

- 若核心工作流完成后仍有时间，Usage Dashboard 参考 [CC Switch Usage Statistics](https://cc-switch.dev/docs/local-routing/usage-statistics/)：用时间、Provider、Model 筛选驱动请求数、标准化 Token、缓存命中率、估算费用和成功率汇总，并提供趋势和运行明细。
- Demo mode、安全收口和错误处理。
- README、测试、演示视频和面试讲解。

### Batch 7：投递后增强

- 恢复真实 Vault 验证、完整 Context Inspector、图片关系与安全预览。
- ACP 兼容性验证和 Codex/Claude Adapter；必要时增加直接 CLI 回退。
- OCR、多模态检索和更复杂的自动 handoff 策略。

每批核心实现约 100 行，完成后测试并暂停 Review。

## 完成标准

- 新环境能够按照 README 启动。
- 可以创建 Agent 和 Session。
- WebSocket 可以稳定流式输出运行事件和回复。
- 已有文本 RAG 能力不阻塞首个可投递版本；真实 Vault 调优列入投递后增强。
- 自研 Personal Agent 在没有 Codex/Claude CLI 时也可以独立检索、编排并回答。
- 可以在同一对话中将任务交给另一个 Agent。
- Codex 和 Claude 的真实运行验证不阻塞原生 Personal Agent 首版。
- 客户端之间无法通过资源 ID 读取彼此的数据。
- 页面可以解释一次回答使用了哪些上下文、模型、Token、费用和时间。
- 有可重复的两分钟演示脚本，并可按需生成项目面试题。
