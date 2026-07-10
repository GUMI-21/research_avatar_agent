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
  requirements.txt    Python runtime dependencies for local development
  app/
    main.py           FastAPI application entrypoint
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

## Local Startup

Install dependencies in a virtual environment, then start the API server from
the `server/` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/ping
```

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
