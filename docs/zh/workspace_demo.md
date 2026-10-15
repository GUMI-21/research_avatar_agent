# Workspace 演示与交接

Workspace 已具备会话、Native 执行、LangGraph 转交、文本 RAG、记忆、工具审批和 Run/Usage 展示。
本次收尾修复终态审批卡片残留与跨平台路径断言，保留已有功能供后续 Avatar 后端复用。
Google 真实账号联调和云模型自主选择工具验收后置，不作为已通过的演示能力。

## 启动与验证

环境、迁移、测试和 MCP 命令以 [Server README](../../server/README.md) 为准；
前端以 [Web README](../../web/README.md) 为准。macOS 使用 `.venv/bin/python`，
Windows 使用 `.venv/Scripts/python.exe`。前端与 Server 启动后，使用独立演示用户。

密钥只通过本地设置页或环境变量配置。笔记、工具输出及演示页面使用公开测试内容，
不要录制凭据或私人邮件。费用展示标明估算或缺失状态。

## 无模型 Key 的基础演示

1. 创建 Mock Native Agent 和一个对话，发送文字，展示 WebSocket 回复及 Run 终态。
2. 查看消息历史和 Run/Usage 页，说明 Token 与费用缺失会如实显示。
3. 展示 Agent 配置、记忆、知识库与 Skill 设置，说明它们分别管理什么。

这一模式展示资源和传输链路。Mock 只回显，不能演示自主工具选择、知识理解或记忆推理。

## 真实 Native 工具演示（需要模型配置）

准备一个支持工具调用的 Native 模型、一份公开 Markdown 文件，以及文件路径和可选 Playwright MCP。
先用相同配置完整排练，再进行约两分钟的展示：

1. 展示 Agent 模型及系统指令，请它读取测试笔记并总结；查看工具事件及回答。
2. 请它将总结写入测试 `.md` 文件，展示审批摘要；先拒绝，再用新任务批准写入。
3. 在另一次待审批任务中点击停止，确认 Run 已取消且审批卡片消失。
4. 查看 Run 的模型、Token、估算费用和耗时；按需要展示一次 Agent 转交。

写入演示要求 Demo mode 未禁用写入；保持演示范围为专用测试文件。
浏览器读取可以替代第一步，但外部读取同样需审批。服务器重启后的继续执行尚未实现；
当前断连会取消 Run，重连恢复的是持久事件展示。

## 已有验收证据的范围

- 真实 Playwright MCP 与隔离 Chrome 已验证本地页面导航、快照、审批和域名过滤。
- 模型替身与真实 MCP 测试子进程已验证批准、拒绝、超时、断连、取消及结果回填。
- 真实 WebSocket 已验证断连取消与事件补发；实际 Web 界面已验证审批、回答及 Usage。
- 后端全量 unittest、前端测试、类型检查和构建用于确认当前代码基线。

模型替身与本地测试页面不证明真实模型决策或第三方网站任务质量。
正式认证、目录沙箱、Google 实账号联调和完整外部异常验收仍需后续工作。

## Avatar 接续边界

复用现有 Agent、Session、上下文、Runtime Adapter、LangGraph、工具和审计服务。
教学策略、学生状态、情绪估计与 Avatar 控制应保留独立模块。
当前 Unity 调用旧的单轮 ChatService，返回固定 neutral/idle；尚未接入新的 Native 链路。
下一阶段先接入会话与执行链，再完成参数到 VRM 表情、视线和动作的映射；
候选契约与研究指标见 [Avatar 集成计划](avatar_integration_plan.md)。
