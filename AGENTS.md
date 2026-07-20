# Project Collaboration Rules

- Plan the overall architecture before implementation, then deliver one coherent change at a time.
- Keep each implementation batch around 100 changed lines unless the user explicitly requests a different pace.
- Test code does not count toward the implementation line guideline. Codex owns adding and running the tests needed for each batch.
- Before editing, explain the goal and affected files. After editing, report test results and pause for user review before starting the next batch.
- At the end of every batch, explicitly state whether any planned code changes still remain.
- Communicate concisely in Chinese. Explain unfamiliar Python or FastAPI behavior with common server-side or Go comparisons when useful.

# Research Direction

- Working topic: an LLM- and emotion-model-based 3D avatar educational support system.
- Research focus: supplement LLM text with consistent nonverbal expression, including facial expression, gaze, motion, and voice, for a more natural virtual teacher.
- Proposed evaluation compares four conditions: text-only LLM teacher, 3D avatar teacher without an emotion model, 3D avatar teacher with an independent emotion model, and a human teacher.
- Planned evaluation dimensions include learning effectiveness, engagement/presence, and perceived naturalness.

# Target Architecture

- FastAPI is the central service boundary connecting Unity, web, cloud/local LLM adapters, the emotion model, agent functions, and future voice modules.
- Intended dialogue flow: analyze the user message/dialogue state with the emotion model; send that analysis plus the message to the LLM; analyze the generated reply into final emotion parameters; let Unity render text, expression, scripted motion, and eventually voice.
- The web client will manage teaching scripts and agent/workspace functions. The voice module will own speech recognition and speech generation. Unity remains the 3D/Web/VR presentation client.
- Keep memory/context management and LangGraph as placeholders until the Unity demo is complete. Do not couple Unity protocols to a specific LLM or emotion model.

# Current Baseline And Priorities

- As of the July 21, 2026 presentation baseline, FastAPI exposes `/api/v1/llm/providers`, `/api/v1/llm/config`, and `/api/v1/unity/chat`; Unity loads VRM 1.0 models and calls the Chat API.
- Unity -> Server -> Mock LLM and Server -> Gemini real API have been verified. Direct Unity -> Gemini verification remains a required demo check.
- Near-term order: finish the Unity demo UI and Windows build; add agent memory/context; research and integrate the independent emotion model; add voice interaction; then extend the Unity client toward Web and VR use.
- API keys must stay outside Git, documentation, logs, and project memory.
