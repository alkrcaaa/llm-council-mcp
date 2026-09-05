# LLM Council MCP

![llmcouncil](header.jpg)

> **Fork & Provenance:**  
> This project is an advanced, production-hardened fork of [Andrej Karpathy's llm-council](https://github.com/karpathy/llm-council) (extended from [az9713/llm-council](https://github.com/az9713/llm-council)). It evolves Karpathy's original multi-LLM peer-review concept into an enterprise deliberation engine and a native **Model Context Protocol (MCP) oracle** for autonomous AI coding agents (Claude Code, Google Antigravity, and Qwen).

---

## What is LLM Council MCP?

Instead of relying on a single AI model's blind spots for critical architectural and strategic decisions, LLM Council orchestrates multiple frontier and local models in a 3-stage consensus process:

1. **Stage 1 (Independent Perspectives):** Council models independently answer the problem without seeing each other's responses.
2. **Stage 2 (Blind Peer Review):** Council members read anonymized responses from other seats and critically rank them on correctness, technical depth, and trade-offs.
3. **Stage 3 (Synthesis & ADR):** A designated Chairman model synthesizes the debate into a decisive, structured **Architectural Decision Record (ADR)** bounded strictly to ≤150 words.

### Key Enhancements in this Fork

- 🔌 **Native FastMCP Server (`mcp/`):** Exposes `ask_council` and `list_councils` to Claude Code and Antigravity with millisecond fast-rejection for trivial queries and automated peer-chairman rotation.
- 🧠 **5 Specialized Council Boards:**
  - `cognitive-strategy`: High-stakes architectural & strategic decisions.
  - `code-craft`: Deep refactoring, diff-risk minimization & surgical simplicity.
  - `deep-tech`: Protocols, RFCs, and dependency evaluations.
  - `sec-ops`: Hardening, OWASP audit, and SRE resilience.
  - `frontend-craft`: Distinctive UI/UX, design DNA, and client workflows.
- 💻 **Hybrid Local & Cloud Model Execution:** Run OpenRouter cloud models alongside local vLLM instances (`local/qwen3.6-27b`) and headless CLI shims (`local/claude-code`, `local/antigravity`).
- 🎯 **Skill & Role Prompt Injection:** Models can be decorated with domain skills (e.g. `@red-team-reasoning`, `@first-principles`, `@karpathy-guidelines`).
- 🐳 **12-Factor Docker Setup:** Fully containerized backend and frontend with `.env` parameterization and zero leaked host credentials.

---

## Quick Setup

### 1. Configure Environment

Copy the example environment template and configure your keys and endpoints:

```bash
cp .env.example .env
```

Edit `.env` to configure your OpenRouter API key (if using cloud models) or local endpoints:
```bash
# Optional if using local models exclusively:
OPENROUTER_API_KEY=sk-or-v1-...

# Local vLLM / OpenAI-compatible endpoint:
QWEN_BASE_URL=http://host.docker.internal:8002/v1
```

---

### 2. Run with Docker Compose (Recommended)

Start the full stack (FastAPI backend + React frontend) in background:

```bash
docker compose -f infra/docker-compose.yml up -d
```

- **Web UI:** http://localhost:5173
- **Backend API:** http://localhost:8001 (Health check: `curl http://localhost:8001/`)

To stop:
```bash
docker compose -f infra/docker-compose.yml down
```

---

### 3. Run Manually with UV & NPM

If you prefer running without Docker:

```bash
# 1. Install dependencies
uv sync
cd frontend && npm install && cd ..

# 2. Start Backend (Terminal 1)
uv run python -m backend.main

# 3. Start Frontend (Terminal 2)
cd frontend && npm run dev
```

---

## Connecting as an MCP Server (Claude Code & Antigravity)

The `mcp/` folder contains a standalone FastMCP server that connects your agent directly to the council backend.

### 1. Install MCP Environment

```bash
cd mcp
bash install.sh
cd ..
```

### 2. Register with Claude Code (`~/.claude.json`)

Add the following under `mcpServers`:

```json
{
  "mcpServers": {
    "llm-council": {
      "command": "/absolute/path/to/llm-council-mcp/mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/llm-council-mcp/mcp/server.py"
      ],
      "timeout": 140000
    }
  }
}
```

### 3. Register with Antigravity (`~/.gemini/config/mcp_config.json`)

```json
{
  "mcpServers": {
    "llm-council": {
      "command": "/absolute/path/to/llm-council-mcp/mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/llm-council-mcp/mcp/server.py"
      ],
      "timeout": 140000
    }
  }
}
```

### MCP Gating Rule (Agent Guardrail)

To prevent models from lazily delegating trivial questions, `ask_council` enforces a strict gating checklist:
1. **Type-1 Decision:** Must be irreversible or have a high rollback cost (justified via `type1_rationale`).
2. **Genuine Deadlock:** Must have hit real disagreement or uncertainty through solo reasoning first.
3. **High Cost of Error:** Getting it wrong costs significantly more than ~35s + deliberation token spend.
4. **User has not already decided:** Council informs open decisions; it never overrides an explicit user choice.

*Trivial or unjustified queries are rejected in milliseconds with `Verdict: Gating Rejection` without triggering backend model calls.*

---

## Tech Stack

- **Backend:** FastAPI, Async HTTPX, Pydantic, uv
- **Protocol:** FastMCP (Model Context Protocol stdio)
- **Frontend:** React, Vite, Tailwind CSS, react-markdown
- **Containerization:** Docker & Docker Compose
- **Orchestration:** Multi-model consensus, early-exit detection, and peer ranking

---

## Acknowledgments & Upstream

- Original idea and implementation by **[Andrej Karpathy](https://github.com/karpathy/llm-council)**
- Extended feature set contributions by **[az9713](https://github.com/az9713/llm-council)**
- Licensed under MIT.
