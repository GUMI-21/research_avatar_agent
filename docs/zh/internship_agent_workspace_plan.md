# Personal Agent Workspace 路线图

## 当前目标

把现有功能串成稳定、可用于 AI Agent 实习面试演示的 Native Agent 工具执行链：

> 自然语言任务 → 模型选择工具（内置或 MCP，可由 Skill 指导）→ 必要时审批 →
> 执行文件、浏览器、邮件或日程操作 → 返回结果 → 前端展示完整审计记录。

邮件、日程工具与 Skill 已接入，真实账号联调尚待完成。以 Python Agent 生态和清晰的服务端边界展示工程能力，
Go 后端经验作为补充；本阶段不增加 Go 微服务。Avatar 教学、情绪和语音暂缓，保留 Unity API。

## 已实现基线

| 能力 | 当前实现 |
| --- | --- |
| Workspace | Agent、用户、Session、消息、Provider/Model 设置与持久化，按 `client_id` 隔离 |
| Native Runtime | OpenAI、Gemini、DeepSeek 的流式工具选择与多轮执行，短期上下文与可管理的长期记忆；Mock 仅固定回显 |
| 编排 | LangGraph 状态图、手动及自动 handoff，最多两次转交并拒绝循环 |
| Web | 真实 REST/WebSocket 流程，取消、重连与持久事件补发 |
| Codex | CLI 纯代理 Adapter，隔离的 thread 绑定、项目目录约束、事件和 Usage 归一化 |
| 工具与审批 | 文件列表、UTF-8 读取、Markdown 写入，工具风险分级及批准/拒绝后的继续执行 |
| MCP | 工具发现、schema 校验、stdio/Streamable HTTP，Playwright 接入与 URL 域名过滤 |
| Google OAuth | state/PKCE 授权、refresh token 加密存储、连接状态和远程撤销 |
| Google 工具 | 自动刷新 access token，Gmail/Calendar 读写工具经 Registry 审批执行 |
| Skills | 发现 `SKILL.md`、按 Agent 启用、Native 上下文注入、Run 版本记录和前端设置 |
| Demo mode | 可配置地禁用本地与外部写入风险工具，并在前端提示 |
| 可观测性 | Run、工具事件、Provider/Model、Token、估算费用、耗时和错误展示 |
| 文本 RAG | Markdown 增量索引、FTS5 与向量混合检索、引用、Agent 知识库绑定及上下文注入 |

## 当前架构

```text
React / TypeScript / Vite
  ├─ REST：Agent、Session、Memory、Knowledge、配置、Usage
  └─ WebSocket：流式回复、handoff、工具、审批、取消与事件重放
        ↓
FastAPI → Services → Repositories → SQLite
  └─ RunExecutionService / LangGraph
       ├─ Native Runtime → LLM adapters
       │    ├─ 短期上下文、长期记忆、RAG
       │    └─ Tool Registry → 文件工具 / MCP / Gmail / Calendar
       └─ Codex CLI Adapter → 外部 thread
Google OAuth → 按 client_id 加密保存凭据 → 共用 API Client
```

FastAPI 管服务边界；LangGraph 管 Run 状态转移，不接管 API、数据库或子进程生命周期。
Native Agent 无需 Codex/Claude 即可运行。Codex 只接收本轮任务，工具、代码上下文与压缩由
外部 thread 管理；ACP/Claude 属于后续可选扩展。

REST 管资源，WebSocket 传递 AG-UI-compatible 运行事件与项目扩展。持久查询必须包含
`client_id`；本地用户名与 `X-Client-ID` 是数据作用域，不是认证。当前面向个位数本地客户端，
不引入 Redis、队列或分布式服务。

## 已知边界

- LangGraph checkpoint 与待审批状态保存在进程内；事件重放不等于跨进程继续执行。
- OpenAI、Gemini、DeepSeek 已接入工具 schema 和调用解析；真实账号端到端验证仍待完成。Mock 不具备模型工具选择能力。
- Native 文件工具继承 Server 系统权限，并未限制在知识库或 Codex 允许目录中。
- MCP 域名过滤检查工具 URL 参数，不覆盖重定向和所有子资源；空列表不启用过滤。
- Google 工具和 Skill 已实现，但尚未使用授权测试账号完成真实外部链路验收。
- 向量存于 SQLite 并做精确余弦检索；未接入 Qdrant，也未配置 WAL。
- Demo mode 已限制写入风险工具；目录沙箱、自动重连和完整异常路径验收仍待完成。Token/费用缺失应如实标记，
  估算费用不代表账单；审计不能包含凭据、完整敏感正文或隐藏思维链。

## 后续优先级

详细范围和验收只维护在 [Tool/MCP/Skill 计划](tool_mcp_skill_plan.md)：

1. 用授权测试账号验证 Google 读写、审批、撤销和权限不足链路。
2. 验证真实 MCP 断连、超时与前端状态；根据结果修复异常路径。
3. 更新启动说明、架构与演示材料，完成里程碑验收。

这是剩余验收方向，不是固定批次数或工期承诺。按约 100 行功能代码拆分实现，
后端与前端可分别成批；每批测试并 Review。

## 保留与后置

文本 RAG 保持现状：按 Markdown 标题及行切块，保存引用行号与内容哈希；使用本地 FastEmbed
多语言 MiniLM，FTS5 与向量结果经 RRF 融合。上下文有字符预算，无 Embedding Client 时回退关键词。
图片引用已解析，但持久资产关系和安全预览未完成。

真实 Vault 评测、模型升级、OCR、图片关系、Qdrant、完整 Context Inspector、Usage 趋势图、
ACP/Claude 和复杂并行委派均不阻塞当前工具链。研究方向见 [研究计划](research_plan.md)。

## 里程碑验收

- 能按 [Server README](../../server/README.md) 与 [Web README](../../web/README.md) 在新环境启动。
- Native Agent 独立完成工具选择、审批、调用、结果回填及回答；外部写入在批准前无副作用。
- 拒绝、超时、撤销授权和 MCP 断连均能结束或恢复 Run，并在前端显示可理解的错误。
- 资源 ID 不能绕过 client 作用域；Google 凭据与结果也保持隔离。
- 同一会话能演示 handoff，并查看工具、审批、模型、Token、费用状态和耗时。
- 后端全量测试、前端测试/类型检查/构建通过；具备可重复的两分钟演示。
- 项目亮点、取舍和简历描述在收口阶段整理；面试问答仅在明确请求时新增。
