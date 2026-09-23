# CLAUDE.md — LLM Council

Multi-model deliberation app: FastAPI backend (`backend/`, port 8001) + React/Vite frontend
(`frontend/`, port 5173) + FastMCP server (`mcp/`). This file holds only what the code
doesn't tell you. Per-feature detail (SSE event lists, props, endpoints) lives in
`docs/ARCHITECTURE.md`, `docs/BACKEND_GUIDE.md`, `docs/FRONTEND_GUIDE.md`,
`docs/API_REFERENCE.md` — or read the module directly.

## Two chat modes

- **Council Deliberation** (`council.py`): Stage 1 parallel answers → Stage 2 anonymized
  peer ranking → Stage 3 chairman synthesis. Optional layers: dynamic routing, escalation,
  CoT, weighted consensus, early consensus exit, multi-chairman, refinement, adversary.
  Debate (`debate.py`) and decomposition (`decompose.py`) are *alternative flows* that
  bypass the 3 stages; semantic cache (`cache.py`) runs before everything.
- **Round Table** (`roundtable.py`): group chat, no chairman, `@mention` routing and
  multi-hop peer chains. Prompts use an anchored sliding window (turn 0 + last 6 turns).

Councils / chat rosters (`councils.py`, `data/councils.json`) bind seat models, chairman
and skills; `providers.py` registers custom OpenAI-compatible endpoints (Ollama, vLLM,
Groq…). `research.py` backs `/api/research/scout`.

## Invariants — don't break these

- **Auth is deny-by-default.** `require_auth` is a global FastAPI dependency; only paths in
  `PUBLIC_PATHS` (`backend/main.py`) are open. Never re-add per-route auth. New public
  route → add to `PUBLIC_PATHS` deliberately. `backend/tests/test_auth_required.py`
  sweeps every route. Frontend must call through `apiFetch` (`frontend/src/api.js`),
  which attaches the bearer token; a bare `fetch` gets 401. MCP tools send
  `_get_mcp_auth_headers()`.
- **All data paths derive from `DATA_ROOT`** (`DATA_DIR` env, default `data`) in
  `config.py`. Tests set it to a temp dir in `conftest.py` before importing backend —
  never run probes from the repo root or they write into the real `data/`.
- **Conversation writes are atomic** (temp file + `os.replace` in `storage.py`).
- **Stage 2 anonymity:** models see "Response A/B/C"; `label_to_model` de-anonymizes
  client-side only. The ranking prompt's strict `FINAL RANKING:` format is what the
  parser depends on — change both together.
- **Graceful degradation:** one failing model never fails the request.
- Metadata (label_to_model, aggregate rankings, costs) is returned via API/SSE but not
  persisted in conversation JSON.
- Backend uses relative imports; run as `python -m backend.main` from repo root.

## Running & deploying

- Local: `./setup.sh`, or `uv run python -m backend.main` + `cd frontend && npm run dev`.
- Tests: `uv run pytest backend/tests` (dev group). Frontend lint: `cd frontend && npm run lint`.
- Docker: `infra/docker-compose.yml`. `council-backend` bind-mounts `backend/` but has
  **no auto-reload — restart the container after backend changes**. Data lives in the
  `infra_council-data` volume. Frontend container hot-reloads `src/`.
- Frontend hits `http://${location.hostname}:8001`.
- The MCP server has a second clone at `dev-agent-kit/mcp-infra/llm-council-mcp`
  (submodule of dev-agent-kit, same remote). After pushing, fast-forward that clone and
  bump the submodule pointer in dev-agent-kit.
- Key env: `OPENROUTER_API_KEY`, `AUTH_ENABLED`, `JWT_SECRET`, `ADMIN_USERNAME`,
  `ADMIN_PASSWORD`, `DATA_DIR`, `*_SHIM_BASE_URL` / `*_SHIM_SECRET`, `GITHUB_TOKEN`.

## UI

Obey `design/DESIGN-DNA.md` (obsidian + brass, Syne / Plus Jakarta Sans / JetBrains Mono,
CSS variables as the single source of truth). Wrap all ReactMarkdown output in
`<div className="markdown-content">`.
