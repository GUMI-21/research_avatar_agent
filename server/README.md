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
  run_avatar_server.py  environment-aware server startup entrypoint
  requirements.txt    Python runtime dependencies for local development
  config/
    config_example.yaml  tracked template for local environment configs
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
/tmp/avatar_agent_log/server.log
```

The `server/logs/` directory is reserved for logging utility code such as logger
configuration helpers, formatters, file handler setup, request ID helpers, and
future LangGraph run logging integration.

Logs rotate at 10 MB, are compressed with gzip, and are retained for 30 days by
default. See the [English](../docs/en/logging.md) and
[Chinese](../docs/zh/logging.md) logging documents for configuration and usage.

## Configuration

The server loads its complete runtime configuration from `config/debug.yaml` or
`config/prod.yaml`. Both local files are ignored by Git; `config/config_example.yaml`
is the tracked template.

```bash
cp config/config_example.yaml config/debug.yaml
cp config/config_example.yaml config/prod.yaml
```

The current local files use `DEBUG` logging with reload enabled for `debug`, and
`INFO` logging with reload disabled for `prod`.

## Local Startup

Install dependencies in a virtual environment, then start the API server from
the `server/` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_avatar_server.py --env debug
```

Production-mode configuration:

```bash
python run_avatar_server.py --env prod
```

Health check:

```bash
curl http://127.0.0.1:8000/ping
```

Run the logging tests from the `server/` directory:

```bash
python -m unittest discover -s tests -v
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
