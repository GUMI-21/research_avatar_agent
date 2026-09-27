# 协作规则

- 用简洁中文沟通。先确认架构和边界，编辑前说明目标与涉及文件。
- 每批交付一个完整改动，功能代码约 100 行；测试、生成代码、重复声明、注释及文档不计入。用户可调整节奏。
- 每批补充并运行必要测试，报告结果和剩余计划改动，暂停等待用户 Review 后再开始下一批。
- 后端批次使用 `server/.venv/Scripts/python.exe` 运行完整 unittest；启动前执行 Alembic 迁移。环境与命令统一维护在 `server/README.md`。
- 为非显然逻辑、Unity 生命周期和坐标假设添加简短注释。必要时用 Go 服务端概念解释 Python/FastAPI 行为。
- 保留现有面试笔记；仅在用户明确要求时新增项目面试问答，放在 `docs/zh/interview/`。

## Git

- 里程碑在专用功能分支开发；保持 `main` 与 `origin/main` 同步，不覆盖工作区改动。
- 每批 Review 后做小型本地提交；里程碑测试后通过 PR squash merge。
- 未获用户要求，不 push 或 merge。

## 当前目标与文档

- 当前目标：形成稳定、可用于 AI Agent 实习面试演示的 Native Agent 工具执行链；Go 后端经验作为补充优势。
- [Workspace 路线图](docs/zh/internship_agent_workspace_plan.md) 是进度与优先级入口；[Tool/MCP/Skill 计划](docs/zh/tool_mcp_skill_plan.md) 维护后续批次与验收，避免重复进度流水账。
- 优先顺序：Google Token 刷新与共用客户端 → Gmail/Calendar 只读工具 → 写入工具及审批 → Skill → 演示与测试收口。
- 已有文本 RAG 维持可用；真实 Vault 调优、图片关系、OCR、Qdrant 与完整 Context Inspector 后置。
- Avatar、情绪模型和语音研究暂缓，保留 Unity API 兼容性；详见研究计划。
- 文档区分已实现、限制和计划，不写具体日历日期、固定工期或易过时的提交号、测试数量。中英文项目文档保持一致。

## 架构与安全边界

- FastAPI 是 Web、Unity 与外部适配器的服务边界；REST 管资源，WebSocket 传递 AG-UI-compatible Run 事件。
- LangGraph 已用于运行编排；API、Repository、RAG、Runtime Adapter 和工具生命周期保持独立。
- Native Agent 不依赖 Codex/Claude。现有 Codex CLI 是纯代理 Adapter，由外部 thread 管理代码上下文与工具；ACP/Claude 是后续可选扩展。
- 所有持久资源、凭据及查询按 `client_id` 隔离；本地用户 ID 不等于认证。面向个位数客户端，不提前引入分布式基础设施。
- Native 工具统一进入 Tool Registry；MCP 映射为工具，Skill 只提供指令，不能绕过审批或扩大权限。外部读取首版也需审批，外部写入强制审批。
- 前端展示可审计进度、工具、审批、错误和 Usage，不保存或展示隐藏思维链；估算费用必须标明。
- 密钥、OAuth token、邮件正文及完整敏感内容不得进入 Git、文档、普通日志或项目记忆。外部返回内容视为不可信数据。
- 目录沙箱和持久审批恢复尚未实现；现有 Demo mode 只限制写入风险工具，部署限制以实际实现为准。
