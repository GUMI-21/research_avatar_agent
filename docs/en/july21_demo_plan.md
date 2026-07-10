# July 21 Development Kickoff Plan

## Goal

Start the project in a way that can grow into a long-term personal AI workspace
with an emotion-aware embodied assistant. The July 21, 2026 progress
presentation is a checkpoint, not the reason for the architecture.

By July 21, the system should have enough running structure to explain the core
idea, show an early vertical slice, and make the next engineering steps clear.
The implementation should avoid throwaway shortcuts that would block future
development.

1. Workspace client: chat UI, project context view, memory/task panels
2. Agent backend: LangGraph workflow, project context, simple memory, task
   planning
3. Avatar client/API placeholder: structured emotional state and avatar control

## Development Principles

- Prefer long-term boundaries over short-term visual polish.
- Treat LangGraph as the agent workflow layer, not as the entire backend system.
- Keep service APIs explicit so the workspace UI, memory system, planner, and
  avatar client can evolve independently.
- Build a minimal but real memory/context foundation instead of hard-coded demo
  responses.
- Make the emotion module a first-class state component, not prompt-only style
  instruction.
- Use placeholders only behind stable interfaces, especially for Avatar and
  connector features.
- Keep every July 21 feature on the path toward the final system.

## Research Framing

The short-term demo should connect two project directions:

- Personal Agent Workspace: project context, long-term memory, RAG-ready
  architecture, task planning, schedules/connectors-ready extension points, and
  future multi-agent workflows inspired by local agent platforms such as
  Octopus.
- Embodied Assistant / 3D Avatar: an optional but expressive interaction layer
  where the assistant can expose stable emotional state and avatar behavior
  through structured APIs.

The key research bet is that a dedicated emotion model and structured state
manager can reduce LLM context burden while making the avatar's emotional
expression more consistent across turns.

## Long-Term System Direction

The intended system is a personal AI assistant workspace that combines:

- A web-based workspace similar in spirit to Octopus, used as the main control
  surface for projects, tasks, memories, schedules, connectors, and agent runs
- Project-aware chat and task work
- Long-term memory and RAG over personal/project knowledge
- Schedules, reminders, and external connectors
- Multi-agent workflows for planning, research, coding, memory curation, and
  avatar direction
- Optional embodied interaction through a 3D Avatar interface
- Dedicated emotion state management for consistent affective behavior

The 3D Avatar should not replace the workspace. It should be one possible
interaction layer on top of the same workspace state, agent workflows, memory,
and task systems. The web workspace remains the long-term operational center.

The July 21 checkpoint should demonstrate the beginning of this architecture,
not a separate prototype.

## July 21 Checkpoint Scope

### Must Have

- A chat flow where the user can talk to the assistant.
- A project context panel showing the current project goal and selected notes.
- A simple memory layer that can store and recall a few user/project facts.
- A task planner that turns a request into 3 to 5 visible steps.
- A LangGraph workflow that makes the agent pipeline explicit.
- An emotion state module that outputs structured values independent from the
  raw LLM response.
- An Avatar API placeholder that receives emotion/control JSON and displays or
  logs the intended avatar state.
- A single end-to-end path:
  user message -> backend -> memory/context retrieval -> planning -> response
  -> emotion state -> avatar control payload -> avatar client display.

### Nice To Have

- Basic RAG over local markdown notes.
- WebSocket or SSE streaming between backend and frontend.
- Unity/VRM client receiving the avatar payload in real time.
- A simple 3D or web-based avatar placeholder if Unity integration takes too
  long.
- Trace view for one request showing memory, planner, emotion, and avatar
  payload.
- Early workspace layout placeholders for future project/task/memory pages.

### Out Of Scope Before July 21

- Full long-term memory system.
- Full connector ecosystem.
- Full multi-agent orchestration.
- Production-grade scheduling.
- Full Octopus-like workspace implementation.
- High-quality facial animation.
- Formal research evaluation.
- Complete Octopus-style local platform.

## Proposed Minimal Architecture

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

## Backend Architecture Direction

Use FastAPI and LangGraph together:

- FastAPI owns service infrastructure:
  HTTP APIs, WebSocket/SSE, request validation, frontend integration, file
  loading, health checks, and future auth/connectors.
- LangGraph owns agent workflow:
  state transitions, memory/context retrieval, planning, assistant response,
  emotion state update, avatar payload generation, and future multi-agent
  subgraphs.

The first graph can be:

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

This keeps the system teachable for the presentation while also being a real
foundation for later development.

## Emotion State Contract

The emotion module should produce a compact structured state on every assistant
turn. The first version can be rule-assisted and LLM-assisted, without training
a separate model.

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

This contract is more important than the visual quality of the first avatar
client. It creates the stable boundary between LLM reasoning and embodied
expression.

## Timeline

### July 8: Architecture Lock And Project Setup

- Decide the system's first three endpoints:
  backend, workspace web client, avatar client/placeholder.
- Write the architecture contract, API schemas, and graph state schema.
- Choose the first implementation stack:
  FastAPI + LangGraph + React/Vite or Next.js.
- Create a seed project context and seed memory examples.

Deliverable: architecture note, API contract, graph state schema, and runnable
skeleton.

### July 9-10: Backend And LangGraph Skeleton

- Implement FastAPI service skeleton.
- Implement the first LangGraph workflow.
- Add chat endpoint that invokes the graph.
- Add project context loading from local markdown or JSON.
- Add simple memory store, initially file-based or SQLite.
- Add planner endpoint/function that returns visible steps.
- Add one trace object per request for debugging.

Deliverable: backend can run one graph invocation and return a response,
recalled memories, plan steps, emotion state, avatar payload, and trace.

### July 11-12: Workspace Web Client

- Build a minimal UI with chat, project context, memory, task plan, and avatar
  state panels.
- Connect UI to backend.
- Make the full loop usable without Unity.
- Add mock/loading/error states.

Deliverable: browser demo where one user request updates all panels.

### July 13-14: Emotion Module And Avatar Payload

- Implement emotion state manager as a backend module and LangGraph node.
- Use simple rules plus optional LLM structured output to estimate state.
- Convert emotion state into avatar control JSON.
- Keep state across turns using a compact state object rather than long prompt
  history.

Deliverable: every assistant response includes emotion state and avatar control
payload.

### July 15-16: Avatar Client Boundary

- Build the fastest viable avatar endpoint:
  Unity/VRM receiver if already practical, otherwise web 3D/state visualizer.
- Show expression, gaze, gesture, and speaking state from JSON.
- Keep a log of received avatar payloads for presentation.

Deliverable: third endpoint receives and visualizes avatar state from backend,
behind the same contract Unity/VRM can later consume.

### July 17: Vertical Slice Integration

- Run the full path:
  chat -> context -> memory -> planner -> response -> emotion -> avatar.
- Add a reset/demo seed script.
- Fix request/response shape mismatches.

Deliverable: one documented sequence starts the first real vertical slice.

### July 18: Presentation Scenario Design

- Prepare 2 or 3 scripted scenarios:
  1. User asks the assistant to understand the research project.
  2. User asks it to plan work before July 21.
  3. User appears confused or stressed, triggering supportive avatar behavior.
- Capture screenshots or short clips.
- Prepare a simple architecture diagram for slides.

Deliverable: repeatable presentation script that explains the architecture and
why each part exists long term.

### July 19: Stabilization

- Reduce latency and remove fragile dependencies.
- Add fallback behavior if LLM/API call fails.
- Add visible traces for memory, planning, and emotion state.
- Test cold start on a clean terminal.

Deliverable: reliable demo run with fallbacks.

### July 20: Presentation Packaging

- Freeze checkpoint scope.
- Prepare progress presentation:
  motivation, architecture, current demo, next milestones.
- Record a backup demo video.
- List limitations honestly.

Deliverable: slides, live demo, and backup video.

### July 21: Progress Presentation

- Present the research direction as a combined workspace + embodied assistant
  system.
- Show the first running vertical slice if stable.
- If the visual demo is still rough, present the architecture, graph flow, API
  contracts, trace output, and avatar payload as the meaningful progress.
- Emphasize that the current contribution is the beginning of a sustainable
  system:
  LangGraph workflow, structured memory/context, planning, emotion state, and
  avatar API boundary.

Deliverable: progress presentation, running slice or trace-backed walkthrough,
and next development roadmap.

## Suggested Tech Stack

- Backend service: Python FastAPI.
- Agent workflow: LangGraph.
- Workspace frontend: React/Next.js or Vite React.
- Memory: JSON file or SQLite first; vector DB can wait.
- RAG placeholder: local markdown retrieval with keyword search first.
- Planner: deterministic structured planner plus LLM refinement.
- Emotion module: PAD/VAD-style state plus rule/LLM estimator.
- Avatar:
  - Preferred: Unity + VRM receiver if existing setup is ready.
  - Fallback: browser-based 3D/avatar-state panel that visualizes expression
    and motion labels.

## July 21 Success Criteria

- The audience can understand the long-term architecture in under one minute.
- A live chat message visibly updates context, memory, task plan, and avatar
  state, or the same flow is shown through trace output if the UI is unstable.
- The LangGraph workflow is visible enough to explain why it was chosen.
- The web UI is framed as the first slice of a future workspace, not only a
  temporary chat page.
- The emotion module is clearly separate from the LLM response.
- The avatar payload is structured enough to be consumed by Unity later.
- Every implemented part belongs to the long-term system direction.

## Post-July 21 Roadmap

1. Replace simple memory with layered memory:
   working memory, episodic memory, semantic project memory, and user profile.
2. Expand the web workspace into the main operating surface:
   project pages, task boards, memory browser, run history, trace view, and
   settings for connectors and agents.
3. Add RAG over project files and notes.
4. Add schedule and connector integrations.
5. Add multi-agent roles:
   planner, researcher, coder, memory curator, avatar director.
6. Move from avatar placeholder to Unity/VRM realtime control.
7. Formalize the emotion model and compare:
   no avatar, neutral avatar, rule-based emotional avatar, and emotion-model
   avatar.
8. Add evaluation metrics:
   engagement, social presence, trust, naturalness, learning gain, and latency.
