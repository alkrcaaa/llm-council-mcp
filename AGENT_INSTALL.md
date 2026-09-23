# LLM Council — guide for AI coding agents

This file is written for an AI coding agent (Claude Code, Antigravity, Codex, Cursor, ...)
acting on behalf of a user. It covers **installing** the project, **reporting problems**, and
**contributing** changes back. Humans can follow it too.

Paste-ready prompt for the user to give their agent:

> Clone https://github.com/alkrcaaa/llm-council-mcp and install it by following
> `AGENT_INSTALL.md` in the repo. Ask me before any step that needs my input.

---

## Rules (apply to every section)

- **Never ask the user to paste an API key, password or secret into the chat.** Secrets live
  in `.env`, which the user edits themselves. Never print `.env` except the specific lines
  named below, and never paste `.env` contents, tokens or `data/` files into issues or commits.
- Configuration changes go in `.env`. Do not edit `infra/docker-compose.yml`, the Dockerfiles
  or source code just to "make the install work"; if something is broken, that's a bug to
  report (see [Reporting problems](#reporting-problems)).
- Do not set `AUTH_ENABLED=false` or `*_BIND_HOST=0.0.0.0` unless the user explicitly asks.
- Do not run `sudo` yourself; tell the user the exact command and why.
- Report each step's outcome in one or two lines. On failure show the exact error and use the
  [troubleshooting table](#troubleshooting) before improvising.

---

## Installation

### Step 1 — Prerequisites

```bash
docker --version
docker compose version     # must be Compose v2
docker info > /dev/null && echo docker-ok
curl --version | head -1
git --version
```

- Docker missing → tell the user to install it (https://docs.docker.com/get-docker/) and stop.
- `docker info` permission error on Linux → user runs `sudo usermod -aG docker $USER`,
  then logs out and back in.
- Ports 5173 and 8001 must be free:
  `ss -ltn | grep -E ':(5173|8001)\b'` (macOS: `lsof -iTCP:5173 -iTCP:8001 -sTCP:LISTEN`).
  If taken, report which process holds them and ask the user.

### Step 2 — Clone

Skip if you're already inside this repository.

```bash
git clone https://github.com/alkrcaaa/llm-council-mcp.git llm-council
cd llm-council
```

If the user plans to contribute, clone their fork instead (see [Contributing](#contributing)).

### Step 3 — First run

```bash
./setup.sh
```

Without a terminal the script skips the API-key prompt. It creates `.env` (mode 600),
generates `ADMIN_PASSWORD` and `JWT_SECRET`, builds the images (first build takes a few
minutes) and starts the stack. Success ends with `LLM Council is running.`

### Step 4 — OpenRouter key (needs the user)

```bash
grep -q '^OPENROUTER_API_KEY=.\+' .env && echo key-set || echo key-missing
```

If `key-missing`, ask the user to create a key at https://openrouter.ai/keys (free models
cost $0), put it in `.env` as `OPENROUTER_API_KEY=...` with their editor, and tell you when
done. Then run `./setup.sh` again (safe to re-run; existing secrets are kept).

### Step 5 — Verify

```bash
curl -fs http://127.0.0.1:8001/          # expect {"status":"ok",...}
docker compose --env-file .env -f infra/docker-compose.yml ps
grep -E '^ADMIN_(USERNAME|PASSWORD)=' .env
```

Give the user **http://localhost:5173** and the username/password, and tell them to change the
password in the UI after the first login.

### Step 6 — Models (ask the user which apply)

The built-in council boards were built on the author's machine and use four kinds of seats.
On a fresh install none of them answer yet. Ask the user which of these they have, then do
only those:

| Seat | Needs | How |
| :--- | :--- | :--- |
| `local/claude-code` | Claude Code CLI installed and logged in (`claude`) | Step 7 |
| `local/antigravity` | Antigravity CLI installed and logged in (`agy`) | Step 7 |
| `local/qwen3.6-27b` | Any OpenAI-compatible local server (vLLM, Ollama, LM Studio) | Set `QWEN_BASE_URL` / `QWEN_MODEL_ID` in `.env` (examples in README), re-run `./setup.sh` |
| `custom/gemini-3-6-flash`, `custom/groq` | Gemini / Groq API keys | User adds them in the UI: **Configure Models → Model Studio & Providers**, friendly names exactly `Gemini 3.6 Flash` and `Groq` |

If the user has none of these, tell them to create their own council under **Configure
Models** with OpenRouter model IDs (at least 2 seats), e.g. `google/gemma-4-31b-it:free`,
`nvidia/nemotron-3-super-120b-a12b:free`. Current free models:
https://openrouter.ai/models?q=free. Free models are rate-limited; occasional `429`s on a
single seat are normal.

Ollama on Linux listens on 127.0.0.1 by default, which containers can't reach: the user must
start it with `OLLAMA_HOST=0.0.0.0` (e.g. `sudo systemctl edit ollama` →
`Environment=OLLAMA_HOST=0.0.0.0`). Use `QWEN_BASE_URL=http://host.docker.internal:11434/v1`.

### Step 7 — CLI shims (only if the user has `claude` and/or `agy`)

Confirm the CLI works first: `claude --version` / `agy --version`. It must already be logged
in; if not, the user logs in interactively themselves (you can't do it for them).

```bash
./setup.sh shims
```

Expected output: one `ok` (systemd) or `run` (manual) line per CLI found, then a backend
restart.

- `ok` lines: user services are running. Check with
  `systemctl --user status llm-council-claude-code-shim` and
  `journalctl --user -u llm-council-claude-code-shim -n 20`.
- `run` lines (macOS, WSL without systemd): the shim must run in a terminal that stays
  open. Give the user the printed command; don't background it in your own session, because
  it dies when your session ends.
- `skip ... belongs to another checkout`: a shim service from another clone of this repo
  exists. Ask the user before removing it.

Verify from the backend's point of view (401 means reachable and enforcing auth):

```bash
docker exec council-backend python -c "import urllib.request as u; \
  r=u.Request('http://host.docker.internal:8600/v1/chat/completions', data=b'{}', method='POST'); \
  u.urlopen(r)" 2>&1 | grep -o 'HTTP Error 401' || echo 'shim not reachable'
```

Use port 8601 for Antigravity. Each shim call spends the user's own Claude/Antigravity quota.

### Step 8 — MCP server (optional)

Only if the user wants their agent to consult the council. Requires Python 3.10+.

```bash
bash mcp/install.sh
```

- **Claude Code:**
  `claude mcp add llm-council -s user -- "$PWD/mcp/.venv/bin/python" "$PWD/mcp/server.py"`
- **Other MCP clients:** stdio server, command `<repo>/mcp/.venv/bin/python`, args
  `["<repo>/mcp/server.py"]`, timeout ≥ 420 s (council runs take minutes).

The MCP server reads `JWT_SECRET` from the repo's `.env` by itself. After the client
restarts, verify with the `list_councils` tool. `ask_council` needs a council with working
seats (Step 6).

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `backend did not come up` | `./setup.sh logs`, read the backend error |
| `JWT_SECRET is not set` | Value missing in `.env`; re-run `./setup.sh` (fills empty secrets) |
| `port is already allocated` | Another process uses 5173/8001; report it to the user |
| Login fails | `ADMIN_USERNAME` / `ADMIN_PASSWORD` in `.env`, unless changed in the UI since |
| Every seat errors | Expected before Step 6 |
| Claude/Antigravity seat errors | Step 7 verification; then `journalctl --user -u llm-council-<name>-shim -n 50` |
| Qwen/Ollama seat errors | `curl $QWEN_BASE_URL/models` from the host; on Linux check `OLLAMA_HOST=0.0.0.0` |
| UI unreachable from another device | By design (127.0.0.1). Only if asked: both `*_BIND_HOST=0.0.0.0` in `.env`, keep auth on, re-run `./setup.sh` |
| Changes to `.env` not applied | Re-run `./setup.sh` |

---

## Reporting problems

If a step fails and the troubleshooting table doesn't fix it, help the user open a GitHub
issue at https://github.com/alkrcaaa/llm-council-mcp/issues.

1. Collect context and **redact before showing it to anyone**. Remove API keys (`sk-or-...`,
   `gsk_...`, `AIza...`), `*_SECRET`, `ADMIN_PASSWORD`, JWTs (`eyJ...`), and home paths or
   hostnames the user wouldn't want public:
   ```bash
   git rev-parse --short HEAD
   uname -sm; docker --version; docker compose version
   docker compose --env-file .env -f infra/docker-compose.yml logs --no-color --tail 80
   ```
2. Search existing issues for the error message first.
3. Draft the issue with: **what you ran**, **what you expected**, **what happened** (exact
   error), **environment** (the commands above), and **what you already tried**.
4. Show the draft to the user and file it only after they approve. With the GitHub CLI:
   `gh issue create --repo alkrcaaa/llm-council-mcp --title "..." --body-file issue.md`.
   Without `gh`, give the user the text to paste in the web form.

---

## Contributing

The user has no push access to this repository: all changes go through a fork and a pull
request. Never push to `alkrcaaa/llm-council-mcp` directly and never force-push to anyone's
`main`.

### Setup (once)

```bash
gh repo fork alkrcaaa/llm-council-mcp --clone --remote   # creates origin=fork, upstream=this repo
# without gh: fork in the web UI, clone the fork, then
git remote add upstream https://github.com/alkrcaaa/llm-council-mcp.git
```

### For each change

```bash
git fetch upstream
git switch -c <type>/<short-topic> upstream/main    # e.g. fix/shim-timeout, feat/ollama-preset
# ... make the change ...
```

- **One topic per branch and per PR.** Keep diffs small and match the surrounding code style.
- **Before committing**, run the checks for what you touched:
  ```bash
  uv run --with pytest --with pytest-asyncio python -m pytest -q backend/tests   # backend
  (cd frontend && npm run build)                                                # frontend
  shellcheck setup.sh                                                           # scripts
  ```
  Add or update a test under `backend/tests/` when you change backend behaviour.
- **Check what you're committing**: `git status` and `git diff --cached`. `.env`, `data/`,
  `skills/`, `skills-imported/` and `test-results*/` are gitignored; never force-add them. Grep the staged diff
  for secrets and personal paths before every commit.
- Commit messages: imperative subject ≤ 72 chars (`Fix shim bind address on macOS`), body
  explaining *why*.
- Push to the fork and open the PR against `alkrcaaa/llm-council-mcp:main`:
  ```bash
  git push -u origin HEAD
  gh pr create --repo alkrcaaa/llm-council-mcp --base main --fill
  ```
  In the description say what changed, why, and how you tested it. Show the PR text to the
  user before creating it.

### Staying up to date

```bash
git switch main && git pull --ff-only upstream main && git push origin main
./setup.sh      # rebuilds and restarts with the new code; your .env and data are kept
```

If `git pull --ff-only` fails, the user has local commits on `main`: move them to a branch
instead of merging or resetting, and ask the user before discarding anything.

Architecture notes for contributors: [`CLAUDE.md`](CLAUDE.md) (module-by-module reference)
and [`docs/`](docs/).
