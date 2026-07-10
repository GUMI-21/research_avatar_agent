# Server

This directory contains the backend service for the personal AI workspace and
emotion-aware avatar assistant.

The backend is planned as a FastAPI service boundary around a LangGraph agent
workflow. FastAPI owns service infrastructure such as HTTP routes, validation,
streaming, health checks, and future connectors. LangGraph owns the agent
workflow, including project context retrieval, memory lookup, task planning,
assistant response generation, emotion state update, and avatar payload
generation.

## Directory Layout

```text
server/
  app/
    api/              FastAPI route layer
    core/             settings, dependency wiring, shared runtime config
    graph/            LangGraph state, graph builder, nodes, and edges
    schemas/          request/response and internal data contracts
    services/         application services used by routes and graph nodes
    repositories/     persistence boundaries for memory, context, and runs
    adapters/         external adapters such as LLM, avatar, and connectors
    observability/    logging, tracing, and run diagnostics
  data/
    seed/             seed project context, seed memories, and demo fixtures
  logs/               logging utility code; runtime output goes elsewhere
  scripts/            local development and demo scripts
  tests/              backend tests
```

## Logging

Runtime log files should be written outside the repository. The planned default
log directory is:

```text
/var/logs/avatar_agent
```

The `server/logs/` directory is reserved for logging utility code such as logger
configuration helpers, formatters, file handler setup, request ID helpers, and
future LangGraph run logging integration.

## First Backend Slice

The first LangGraph flow should be:

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

## Documentation Policy

Project documents should be maintained in both English and Chinese under
`docs/en/` and `docs/zh/`.
