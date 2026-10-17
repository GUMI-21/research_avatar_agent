# Avatar Integration Plan (Deferred)

This preserves the long-term design from the original kickoff plan without its
obsolete calendar schedule. It is not the active backlog: follow the
[Workspace roadmap](internship_agent_workspace_plan.md). Research questions,
baselines and metrics belong in the [research plan](research_plan.md).

## Boundaries

- Web Workspace manages Agents, conversations, memory and tools.
- FastAPI connects Web, Unity, LLMs, emotion and future voice modules.
- LangGraph coordinates state transitions; modules retain independent service/adapter boundaries.
- Unity/VRM is an optional presentation client. Teaching-script UI is separate from the personal Workspace.
- Structured emotion contracts do not depend on one LLM; voice owns recognition and synthesis.

## Target flow (not implemented)

```text
User input → conversation/memory/teaching context → student-state analysis
  → LLM reply → reply-emotion analysis → avatar control parameters
  → Unity text, expressions, gaze, motion and eventually voice
```

Start with PAD/VAD plus rules or LLM estimation, then evaluate alternatives.
A trained standalone model is not required initially, and prompt style alone is
not a complete emotion-state system.

## Candidate contract

This future design does not replace the existing Unity API:

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

## Sequence and acceptance when research resumes

1. Define emotion input/output contracts and state management with module tests.
2. Map emotion to avatar parameters and provide a preview without Unity.
3. Integrate the existing Unity/VRM client for expressions, gaze and scripted motion.
4. Add voice as needed, then design teaching scenarios and controlled studies.

Acceptance: a conversation produces interpretable state and presentation results;
model failure has explicit fallback behavior; APIs stay compatible; module latency
and research metrics cover naturalness, engagement and learning outcomes.
