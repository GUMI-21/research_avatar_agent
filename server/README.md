# Server

This directory contains the backend service for the personal AI workspace and
emotion-aware avatar assistant.

FastAPI currently owns REST/WebSocket routes, native Agent runs, usage recording,
and Markdown retrieval backed by SQLite. Services, repositories, and runtime
adapters remain separate. Workspace runs now pass through LangGraph with a shared
in-memory checkpointer. Manual handoff and OpenAI tool-driven automatic handoff
share the same streamed event protocol; automatic routing is client-scoped,
rejects cycles, and allows at most two delegations. Native runs also receive the
latest 12 conversation messages within a 6,000-character budget. Durable
checkpoints, multi-Agent usage aggregation, and long-term memory remain planned. See
the [active workspace roadmap](../docs/zh/internship_agent_workspace_plan.md).

## Directory Layout

```text
server/
  run_avatar_server.py  environment-aware server startup entrypoint
  requirements.txt    Python runtime dependencies for local development
  config/
    config_example.yaml  tracked template for local environment configs
  docs/               concise English backend documentation
  app/
    main.py           FastAPI application entrypoint
    api/              FastAPI route layer
    core/             settings, dependency wiring, shared runtime config
    orchestration/    LangGraph run state, routing nodes, and handoff loop
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

The template uses the Unix temporary log path below. Windows development uses
the Git-ignored `server/runtime/logs/` directory instead:

```text
/tmp/avatar_agent_log/server.log
```

The `server/logs/` directory is reserved for logging utility code such as logger
configuration helpers, formatters, file handler setup, request ID helpers, and
future LangGraph run logging integration.

Logs rotate at 10 MB, are compressed with gzip, and are retained for 30 days by
default. See the [logging document](docs/logging.md) for configuration and usage.

The public JSON protocol is documented in the [API design](docs/api.md).

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

The tracked template also defines provider-independent LLM timeout and output
limits plus default models and base URLs for OpenAI, Gemini, and DeepSeek. API
keys are not stored in YAML. Set `OPENAI_API_KEY`, `GOOGLE_API_KEY` or
`GEMINI_API_KEY`, and `DEEPSEEK_API_KEY` in the server environment, or send a
key to a local runtime configuration endpoint.

## Local Startup

### Windows PowerShell

From the repository root, use Python 3.11 and the project virtual environment.
Calling its interpreter directly avoids PowerShell activation-policy changes:

```powershell
cd server
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path config/debug.yaml)) {
    Copy-Item config/config_example.yaml config/debug.yaml
}
```

In `config/debug.yaml`, set `logging.directory` to `./runtime/logs` on Windows.
Keep `database.url: sqlite+aiosqlite:///data/personal_agent.db` and the default
`mock` provider. Existing configs must also include the template's database and
embedding sections. The local YAML, database, models, and runtime logs are ignored
by Git. No cloud API key is needed for Mock chat.

```powershell
New-Item -ItemType Directory -Force data | Out-Null
$env:APP_ENV = "debug"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run_avatar_server.py --env debug
```

In another terminal, run `Invoke-RestMethod http://127.0.0.1:8000/ping`.
API documentation is at `http://127.0.0.1:8000/docs`. Register a lowercase local
username through `/api/v1/workspaces`, then send it as `X-Client-ID`; this is
workspace scoping rather than authentication.
Run commands from `server/` because the database path is relative to that directory.
Codex Agents additionally require `codex` on `PATH` and a working Codex/CC Switch login; the server never reads or stores Codex credentials.
Set `codex.workspace_root` to the only directory tree Codex Agents may use; each Agent may select that root or one of its descendant project directories.
The web settings page reads `GET /api/v1/codex/status` once per minute to show the Server host login mode, plan, and Codex rate-limit windows without exposing account identity or credentials.
The first server startup downloads the embedding model into `data/models/fastembed`;
ordinary unit tests use substitutes and do not validate model download or quality.
The real symlink-escape test skips on Windows error 1314 when the current user
lacks symlink privileges; run it with Developer Mode or appropriate privileges
to cover that filesystem case.

The current backend baseline is 149 tests passing with one optional Windows
symlink test skipped. OpenAI Responses supports the structured
`delegate_to_agent` tool. Gemini and DeepSeek continue to support normal streamed
chat, while their automatic handoff wire formats are deferred until after the
first usable workspace.

### Playwright MCP on Windows

Install Node.js 20 or newer and make `npx.cmd` available on `PATH`. Add a
stdio server to the ignored `config/debug.yaml`; keep the domain list and
blocked tools appropriate for the machine:

```yaml
mcp:
  stdio_servers:
    - name: playwright
      command: npx.cmd
      args: [-y, "@playwright/mcp@latest", "--headless", "--isolated", "--browser=chrome", "--image-responses=omit"]
      timeout_seconds: 60
      allowed_domains: [localhost, 127.0.0.1, demo.playwright.dev]
      blocked_tools: [browser_run_code_unsafe, browser_file_upload, browser_evaluate, browser_webmcp_call]
  http_servers: []
```

Verify the real MCP handshake, tool discovery, browser launch, and navigation
from `server/`:

```powershell
.\.venv\Scripts\python.exe scripts\check_mcp.py --env debug --server playwright
.\.venv\Scripts\python.exe scripts\check_mcp.py --env debug --server playwright --navigate https://demo.playwright.dev/todomvc/
```

The URL filter protects direct `url` arguments sent through this MCP client.
It does not inspect redirects or every subresource request, so retain Playwright
network policy and host-level network restrictions for untrusted sites.
### macOS / Linux

Install dependencies in a virtual environment, then start the API server from
the `server/` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
APP_ENV=debug python -m alembic upgrade head
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

## Docker Startup

Docker is an optional alternative to the local virtual environment. Start the
server from this directory:

```bash
docker compose up --build
```

The API is available at `http://127.0.0.1:8000`. Runtime logs are stored under
`runtime/docker-logs/`, which is ignored by Git. Stop the service with:

```bash
docker compose down
```

Cloud provider keys remain optional because the default provider is `mock`.
Set them in the shell before starting Compose when needed; they are passed as
environment variables and are not copied into the image.

Chat placeholder:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/unity/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"unity-demo","message":"Hello"}'
```

Select the active provider with its configured defaults:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/llm/config \
  -H "Content-Type: application/json" \
  -d '{"provider":"openai"}'
```

Unity and web clients use this shared endpoint. Submitted provider keys are
scoped by `client_id + provider`, encrypted before SQLite persistence, and
never returned by the API. The local Fernet master key is generated at
`runtime/credential.key`; keep that ignored runtime file when retaining the
database, because losing it makes stored provider keys unreadable. Environment
variable keys remain outside the database. See the [API design](docs/api.md)
for explicit-key examples and security constraints.

Run the backend tests from the `server/` directory:

```bash
python -m unittest discover -s tests -v
```

## Deferred Avatar Workflow

The future teaching workflow below is separate from the current Workspace milestone:

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

Research and project-level documents are maintained in both English and Chinese
under `docs/en/` and `docs/zh/`. Backend technical documents are concise English
documents under `server/docs/`.
