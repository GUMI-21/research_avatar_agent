# Avatar 集成计划（后置）

本文保留早期启动计划中的长期设计，替代已过时的日历排期，不作为当前开发待办。
近期优先级以 [Workspace 路线图](internship_agent_workspace_plan.md) 为准；
研究假设、对照条件和评估指标见 [研究计划](research_plan.md)。

## 系统边界

- Web Workspace 是 Agent、会话、记忆和工具的操作中心。
- FastAPI 连接 Web、Unity、LLM、情绪模块及未来语音模块。
- LangGraph 只协调状态转移，各模块保留独立服务与适配器边界。
- Unity/VRM 是可选呈现端；教学脚本界面与当前个人 Workspace 分开。
- 情绪状态采用结构化契约，不绑定某个 LLM；语音模块负责识别与合成。

## 目标流程（未实现）

```text
用户输入 → 读取对话/记忆/教学上下文 → 分析学生状态
  → LLM 生成回复 → 分析回复情绪 → 生成 Avatar 控制参数
  → Unity 显示文本、表情、视线、动作与后续语音
```

情绪模块可从 PAD/VAD 加规则或 LLM 估计开始，再通过研究评估选择模型。
不要求先训练独立模型，也不把提示词风格当作完整情绪状态管理。

## 候选数据契约

以下只是未来模块设计，不替换现有 Unity API：

```json
{
  "student_state": {
    "valence": 0.1, "arousal": 0.4,
    "confidence": 0.3, "confusion": 0.6
  },
  "assistant_affect": {
    "valence": 0.6, "arousal": 0.35,
    "stance": "encouraging", "intent": "clarify_and_support"
  },
  "avatar_control": {
    "expression": "gentle_smile", "gaze": "attentive",
    "gesture": "small_nod", "motion_intensity": 0.35,
    "voice_style": "calm"
  }
}
```

## 恢复研究后的顺序与验收

1. 固化情绪输入/输出契约与状态管理，补充模块测试。
2. 将情绪状态映射为 Avatar 参数，提供无 Unity 的状态预览。
3. 接入现有 Unity/VRM 客户端，验证表情、视线与脚本动作。
4. 按需接入语音，再设计教学场景和研究对照实验。

验收关注：同一对话能生成可解释的状态与呈现结果；模型失败有明确降级；
API 保持兼容；记录模块延迟并按研究计划评估自然度、参与度和学习效果。
