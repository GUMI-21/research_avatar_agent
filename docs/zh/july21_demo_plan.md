# 7 月 21 日开发启动计划

## 目标

以能够长期演进为个人 AI Workspace 和情绪感知 embodied assistant 的方式正式启动项目。2026 年 7 月 21 日的进度发表是一个检查点，而不是架构设计的根本目标。

到 7 月 21 日，系统应该具备足够的运行结构，能够解释核心想法、展示早期 vertical slice，并让下一步工程路线变得清楚。实现上应避免会阻碍后续开发的一次性捷径。

1. Workspace 客户端：聊天界面、项目上下文视图、记忆/任务面板。
2. Agent 后端：LangGraph 工作流、项目上下文、简单记忆、任务规划。
3. Avatar 客户端/API 占位：结构化情绪状态和 Avatar 控制。

## 开发原则

- 优先保证长期边界，而不是短期视觉效果。
- 将 LangGraph 视为 Agent 工作流层，而不是整个后端系统。
- 保持服务 API 明确，让 workspace UI、记忆系统、planner 和 avatar 客户端可以独立演进。
- 构建最小但真实的 memory/context 基础，而不是硬编码演示回复。
- 将情绪模块作为一等的状态组件，而不是只放在 prompt 里的风格指令。
- 只在稳定接口之后使用占位实现，尤其是 Avatar 和 connector 相关功能。
- 7 月 21 日前实现的每个功能都应位于最终系统的演进路径上。

## 研究定位

短期检查点应连接两个项目方向：

- Personal Agent Workspace：项目上下文、长期记忆、RAG-ready 架构、任务规划、schedules/connectors-ready 扩展点，以及未来参考 Octopus 等本地 Agent 平台的多 Agent 工作流。
- Embodied Assistant / 3D Avatar：一个可选但具有表达力的交互层，让助手能够通过结构化 API 暴露稳定的情绪状态和 Avatar 行为。

核心研究假设是：专用情绪模型和结构化状态管理可以降低 LLM 上下文负担，同时提升 3D Avatar 情感表达的一致性。

## 长期系统方向

目标系统是一个个人 AI 助手 workspace，包含：

- 一个类似 Octopus 的 Web workspace，作为项目、任务、记忆、日程、connectors 和 agent runs 的主控制界面。
- 项目感知的聊天和任务工作。
- 面向个人/项目知识的长期记忆和 RAG。
- 日程、提醒和外部 connectors。
- 面向规划、研究、编码、记忆整理和 Avatar 导演的多 Agent 工作流。
- 通过 3D Avatar interface 实现的可选 embodied interaction。
- 面向一致情感行为的专用情绪状态管理。

3D Avatar 不应该取代 workspace。它应该是建立在同一套 workspace state、agent workflows、memory 和 task systems 之上的一种交互层。Web workspace 仍然是长期的操作中心。

7 月 21 日检查点应该展示这个架构的开始，而不是一个独立的原型。

## 7 月 21 日检查点范围

### 必须具备

- 用户可以与助手聊天。
- 项目上下文面板展示当前项目目标和选中的 notes。
- 简单记忆层可以存储并召回少量用户/项目事实。
- 任务 planner 可以将请求转化为 3 到 5 个可见步骤。
- LangGraph 工作流能清晰展示 agent pipeline。
- 情绪状态模块输出独立于原始 LLM 回复的结构化值。
- Avatar API 占位可以接收 emotion/control JSON，并显示或记录预期的 Avatar 状态。
- 一条单一端到端路径：
  user message -> backend -> memory/context retrieval -> planning -> response
  -> emotion state -> avatar control payload -> avatar client display。

### 可以争取

- 基于本地 Markdown notes 的基础 RAG。
- 后端和前端之间的 WebSocket 或 SSE streaming。
- Unity/VRM 客户端实时接收 avatar payload。
- 如果 Unity 集成耗时过长，则使用简单的 3D 或 Web avatar 占位。
- 展示一次请求中 memory、planner、emotion 和 avatar payload 的 trace view。
- 为未来 project/task/memory 页面预留早期 workspace layout 占位。

### 7 月 21 日前不做

- 完整长期记忆系统。
- 完整 connector 生态。
- 完整多 Agent 编排。
- 生产级 scheduling。
- 完整 Octopus-like workspace 实现。
- 高质量面部动画。
- 正式研究评估。
- 完整 Octopus-style 本地平台。

## 拟定最小架构

```text
Workspace Web Client
  - Chat
  - Project context panel
  - Memory/task panels
  - Avatar state preview

        |
        | HTTP/SSE or WebSocket
        v

Agent Backend
  - FastAPI service boundary
  - LangGraph workflow runtime
  - Project context manager
  - Memory repository
  - Task planner node
  - Emotion state node
  - Avatar control adapter

        |
        | JSON payload
        v

Avatar Client / Placeholder
  - Unity + VRM if ready
  - Otherwise web 3D or simple state visualizer
  - Displays expression, gaze, gesture, and speaking state
```

## 后端架构方向

FastAPI 和 LangGraph 配合使用：

- FastAPI 负责服务基础设施：
  HTTP APIs、WebSocket/SSE、请求校验、前端集成、文件加载、health checks，以及未来的 auth/connectors。
- LangGraph 负责 Agent 工作流：
  状态转移、memory/context retrieval、planning、assistant response、emotion state update、avatar payload generation，以及未来的多 Agent subgraphs。

第一版 graph 可以是：

```text
user_input
  -> load_project_context
  -> retrieve_memory
  -> plan_task
  -> generate_response
  -> update_emotion_state
  -> build_avatar_control
  -> return_workspace_state
```

这能让系统在发表时容易讲清楚，同时也是后续开发的真实基础。

## 情绪状态契约

情绪模块应该在每个 assistant turn 生成紧凑的结构化状态。第一版可以使用规则辅助和 LLM 辅助，不需要训练独立模型。

```json
{
  "student_state": {
    "valence": 0.1,
    "arousal": 0.4,
    "confidence": 0.3,
    "confusion": 0.6
  },
  "assistant_affect": {
    "valence": 0.6,
    "arousal": 0.35,
    "stance": "encouraging",
    "intent": "clarify_and_support"
  },
  "avatar_control": {
    "expression": "gentle_smile",
    "gaze": "attentive",
    "gesture": "small_nod",
    "motion_intensity": 0.35,
    "voice_style": "calm"
  }
}
```

这个契约比第一版 Avatar 客户端的视觉质量更重要。它建立了 LLM 推理和 embodied expression 之间稳定的边界。

## 时间线

### 7 月 8 日：架构锁定与项目设置

- 决定系统第一版的三个端点：
  backend、workspace web client、avatar client/placeholder。
- 编写 architecture contract、API schemas 和 graph state schema。
- 选择第一版实现技术栈：
  FastAPI + LangGraph + React/Vite 或 Next.js。
- 创建 seed project context 和 seed memory examples。

交付物：architecture note、API contract、graph state schema 和可运行 skeleton。

### 7 月 9-10 日：后端与 LangGraph Skeleton

- 实现 FastAPI service skeleton。
- 实现第一版 LangGraph workflow。
- 添加调用 graph 的 chat endpoint。
- 从本地 Markdown 或 JSON 加载 project context。
- 添加简单 memory store，初期可使用文件或 SQLite。
- 添加返回可见步骤的 planner endpoint/function。
- 为每次请求添加一个 trace object，方便调试。

交付物：后端可以运行一次 graph invocation，并返回 response、recalled memories、plan steps、emotion state、avatar payload 和 trace。

### 7 月 11-12 日：Workspace Web Client

- 构建最小 UI，包含 chat、project context、memory、task plan 和 avatar state panels。
- 将 UI 连接到后端。
- 在不依赖 Unity 的情况下跑通完整链路。
- 添加 mock/loading/error states。

交付物：浏览器 demo 中，一条用户请求可以更新所有面板。

### 7 月 13-14 日：Emotion Module And Avatar Payload

- 将 emotion state manager 实现为后端模块和 LangGraph node。
- 使用简单规则加可选 LLM structured output 来估计状态。
- 将 emotion state 转换为 avatar control JSON。
- 使用紧凑 state object 跨 turn 保存状态，而不是依赖很长的 prompt history。

交付物：每次 assistant response 都包含 emotion state 和 avatar control payload。

### 7 月 15-16 日：Avatar Client Boundary

- 构建最快可行的 avatar endpoint：
  如果 Unity/VRM receiver 已经可行就使用它，否则使用 Web 3D/state visualizer。
- 从 JSON 展示 expression、gaze、gesture 和 speaking state。
- 保留收到的 avatar payload 日志，供发表展示。

交付物：第三端可以接收并可视化后端 avatar state，且使用未来 Unity/VRM 也能消费的同一契约。

### 7 月 17 日：Vertical Slice Integration

- 跑通完整路径：
  chat -> context -> memory -> planner -> response -> emotion -> avatar。
- 添加 reset/demo seed script。
- 修复 request/response shape 不一致的问题。

交付物：一套文档化步骤可以启动第一个真实 vertical slice。

### 7 月 18 日：发表场景设计

- 准备 2 到 3 个脚本化场景：
  1. 用户要求助手理解研究项目。
  2. 用户要求助手规划 7 月 21 日前的工作。
  3. 用户表现出困惑或压力，从而触发支持性的 Avatar 行为。
- 截图或录制短视频。
- 为 slides 准备简单架构图。

交付物：可重复执行的发表脚本，能够解释架构以及每个部分的长期意义。

### 7 月 19 日：稳定化

- 降低延迟，移除脆弱依赖。
- 如果 LLM/API 调用失败，添加 fallback behavior。
- 添加可见 trace，展示 memory、planning 和 emotion state。
- 在干净终端中测试 cold start。

交付物：具有 fallback 的可靠运行版本。

### 7 月 20 日：发表打包

- 冻结 checkpoint scope。
- 准备进度发表材料：
  motivation、architecture、current demo、next milestones。
- 录制 backup demo video。
- 诚实列出 limitations。

交付物：slides、live demo 和 backup video。

### 7 月 21 日：进度发表

- 将研究方向呈现为 combined workspace + embodied assistant system。
- 如果稳定，则展示第一条 running vertical slice。
- 如果视觉 demo 仍然粗糙，则展示 architecture、graph flow、API contracts、trace output 和 avatar payload，这些也是有意义的进展。
- 强调当前贡献是可持续系统的开始：
  LangGraph workflow、structured memory/context、planning、emotion state 和 avatar API boundary。

交付物：进度发表、running slice 或 trace-backed walkthrough，以及下一步开发 roadmap。

## 建议技术栈

- 后端服务：Python FastAPI。
- Agent workflow：LangGraph。
- Workspace 前端：React/Next.js 或 Vite React。
- Memory：先用 JSON file 或 SQLite；vector DB 可以后置。
- RAG 占位：先用本地 Markdown keyword retrieval。
- Planner：deterministic structured planner 加 LLM refinement。
- Emotion module：PAD/VAD-style state 加 rule/LLM estimator。
- Avatar：
  - 优先：如果已有条件成熟，使用 Unity + VRM receiver。
  - 备选：使用 browser-based 3D/avatar-state panel，可视化 expression 和 motion labels。

## 7 月 21 日成功标准

- 听众能在一分钟内理解长期架构。
- 一条 live chat message 可以明显更新 context、memory、task plan 和 avatar state；如果 UI 不稳定，则通过 trace output 展示同一流程。
- LangGraph workflow 足够可见，能够解释为什么选择它。
- Web UI 被定位为未来 workspace 的第一块切片，而不是临时聊天页面。
- Emotion module 明确独立于 LLM response。
- Avatar payload 足够结构化，后续可以被 Unity 消费。
- 已实现的每个部分都属于长期系统方向。

## 7 月 21 日之后的路线图

1. 将简单 memory 替换为分层 memory：
   working memory、episodic memory、semantic project memory 和 user profile。
2. 将 Web workspace 扩展为主操作界面：
   project pages、task boards、memory browser、run history、trace view，以及 connectors 和 agents 的 settings。
3. 添加面向项目文件和 notes 的 RAG。
4. 添加 schedule 和 connector 集成。
5. 添加多 Agent 角色：
   planner、researcher、coder、memory curator、avatar director。
6. 从 avatar placeholder 迁移到 Unity/VRM realtime control。
7. 正式化 emotion model，并比较：
   no avatar、neutral avatar、rule-based emotional avatar 和 emotion-model avatar。
8. 添加评估指标：
   engagement、social presence、trust、naturalness、learning gain 和 latency。

