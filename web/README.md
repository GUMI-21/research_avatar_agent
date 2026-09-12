# Personal Agent Workspace Web

## Technology choices

- React 19 and TypeScript for a typed, component-based workspace UI.
- Vite 8 for local HMR and production bundling.
- TanStack Query for REST server state, cache invalidation, loading, and errors.
- Native WebSocket for streamed Run events, cancellation, reconnect, and replay.
- Zustand is reserved for cross-page UI/run state; the current resource slice
  uses component state because Agent and Session data belongs in Query cache.
- Tailwind CSS is available for tokens and utilities; shared workspace styling
  currently stays in `src/styles.css` so the visual system remains easy to audit.

The interface is conversation-first. It borrows the dense usage hierarchy of
CC Switch and the visible Agent/run/memory concepts of Octopus, while keeping
the first milestone focused on one usable chat workspace.

## Local development on Windows

Use Node.js 22.12 or newer. From the repository root:

```powershell
cd web
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Start the backend separately from `server/` after applying Alembic migrations.
Vite proxies `/api` and `/ws` to `http://127.0.0.1:8000`, so browser requests
remain same-origin during development.

`.env.local` selects the local client scope:

```text
VITE_CLIENT_ID=local-demo
```

`VITE_CLIENT_ID` is only the initial local username. The Workspace settings dialog
can open or create another user ID; the browser stores it locally and uses it for
all REST and WebSocket requests.

`X-Client-ID` is a development scope header and is not authentication.

Agents can be created and edited with their own provider and model. Selecting a
cloud provider may require its API key after each Server restart because provider
credentials are kept only in process memory.

## Validation and delivery

Run the same checks locally and in CI:

```powershell
npm ci
npm run typecheck
npm run test
npm run build
```

The production artifact is `web/dist/`. A deployment serves that directory as
static files and reverse-proxies `/api` and `/ws` to FastAPI. The local-first
demo can run both processes on one machine; the first public deployment should
add TLS and real authentication before exposing workspace APIs.

Small reviewed commits stay on the feature branch. Milestone CI runs frontend
checks plus the backend unittest suite, then the feature branch is pushed and
squash-merged through a pull request when explicitly requested.
