# Tool、MCP 与 Skill 开发计划

## 目标

Native Agent 需要在统一的安全边界中读取和修改 Server 文件、访问浏览器、连接 Gmail 和 Google Calendar，并通过 Skill 组合这些能力。Codex Runtime 继续由 Codex 自己管理工具，本计划主要扩展 Native Runtime。

## 三层职责

- Tool Registry 统一名称、描述、输入 schema、执行函数、客户端上下文和风险等级。
- MCP Client 把远程或本地 MCP Server 的 tools/list 与 tools/call 映射到 Tool Registry。
- Skill 是版本化的 Markdown 指令与资源包，声明适用场景和推荐工具，不持有绕过 Registry 的执行权限。

Runtime 只依赖 Tool Registry。内置文件工具与 MCP 工具使用相同的 LLMToolDefinition 和 ToolResult，因此 LangGraph、WebSocket 和前端审计事件无需识别每个厂商协议。

## 风险与审批

| 风险 | 示例 | 默认策略 |
| --- | --- | --- |
| read_only | 读取 Server 进程有权限访问的文件 | 可自动执行 |
| local_write | 修改或创建 Server 文件 | 每次审批 |
| external_read | 读取网页、邮件或日程 | 首版每次审批，后续允许用户配置 |
| external_write | 发邮件、创建日程、提交网页表单 | 每次审批 |

所有参数先经过 Pydantic 严格校验。Native 文件工具继承 Server 进程的操作系统权限，可使用任意盘符的绝对路径；相对路径以 Server 启动目录为基准。部署时应使用权限受限的专用系统账号。工具事件只记录工具名、风险、状态、耗时和安全摘要，不记录密钥、邮件正文或完整文件内容。

MCP 返回内容与网页、邮件内容都视为不可信数据。它们只作为工具结果提供给模型，不能改变系统指令、审批策略或工具白名单。

## 执行流程

1. 根据 Agent 工具策略生成允许工具的 schema。
2. LLM 返回工具调用。
3. Registry 校验名称、参数、客户端上下文与风险。
4. 需要审批时产生 approval_required 并暂停 LangGraph run。
5. 批准后执行工具，产生 tool_started 和 tool_finished。
6. 把经过长度限制的工具结果作为 tool message 送回 LLM。
7. 重复直到生成最终回答，并限制每个 Run 的工具步数。

## 集成选择

- Server 文件：内置 Python 工具。首版提供目录列表、UTF-8 文本读取和受控文本修改。
- 浏览器：优先使用 Playwright MCP，保留浏览器域名允许列表、超时和下载禁用策略。
- Gmail：优先连接 Google 官方 Gmail Remote MCP Server。它当前属于 Developer Preview；不可用时使用 Gmail REST API 兼容实现。
- Calendar：优先连接 Google 官方 Calendar Remote MCP Server。它当前属于 Developer Preview；不可用时使用 Calendar REST API 兼容实现。
- Google OAuth：按 client_id 隔离令牌，Server 加密保存 refresh token；前端只处理授权跳转和状态，不接触持久凭据。
- Skill：从管理员允许目录加载 SKILL.md，限制文件大小和引用范围，记录 Skill ID 与版本哈希。

## 开发批次

1. 已完成：工具契约、注册表、严格参数校验和风险审批拦截。
2. 已完成：Server 文件只读工具与 Native Agent 多轮工具循环。
3. 已完成：Markdown 修改工具、当前连接内 Run 暂停恢复与前端批准/拒绝。跨进程恢复后续补充。
4. 已完成：工具发现、JSON Schema 校验、Registry 注册、调用与错误归一化，并用官方 SDK 接入 stdio、Streamable HTTP Transport 和应用生命周期。
5. Playwright MCP 浏览器连接与域名策略。
6. Google OAuth，以及 Gmail/Calendar 只读工具。
7. Gmail 草稿/发送与 Calendar 创建/修改工具的审批流程。
8. Skill 发现、启用、上下文注入和审计展示。

## 验收标准

- Native Agent 能读写允许目录，路径或软链接不能越界。
- 每个副作用工具都能在执行前暂停并由当前 client 批准或拒绝。
- MCP 断连、超时和错误不会使 Run 卡死。
- Gmail 和 Calendar 凭据、数据及工具结果按 client_id 隔离。
- 前端能看到工具名称、审批、状态和安全结果摘要。
- Skill 只能组合 Agent 已获准的工具，不能扩大权限。
