# Fix: caller can end up consulting itself as a "panelist"

## Problem

`ask_council` (`mcp/server.py`) already avoids the caller judging its own
answer as **chairman**:

```python
# mcp/server.py:154-155
caller_is_claude = bool(os.getenv("CLAUDE_PROJECT_DIR") or os.getenv("CLAUDE_CODE") or "claude" in sys.argv[0].lower())
chairman_override = "local/antigravity" if caller_is_claude else "local/claude-code"
```

But this only overrides `chairman_model`. It never touches the **panelist
list** (`council_models`), and every built-in board (`backend/councils.py`)
hardcodes a `local/*` host-CLI shim as one of its 2-3 panelists:

```python
# backend/councils.py — cognitive-strategy board
"council_models": [
    "local/antigravity@red-team-reasoning",
    "local/qwen3.6-27b@first-principles",
    "local/qwen3.6-27b@deep-research",
],
"chairman_model": "local/claude-code",
```

If **Antigravity** is the one calling `ask_council` with this board, the
panel still includes `local/antigravity@red-team-reasoning` — the caller's
own CLI shim, invoked as if it were an independent second opinion. It isn't:
it's the calling agent grading its own homework under a different skill
prompt. (Claude callers are currently safe by accident, because no built-in
board lists `local/claude-code` as a *panelist* — only as a default
chairman, which the override already replaces.)

Confirmed by reading:
- `mcp/server.py` (chairman override logic, lines ~144-181)
- `backend/councils.py` (`BUILTIN_COUNCILS`, all 6 boards)
- `backend/main.py:741-778` — `active_council_models` is taken verbatim from
  the council/conversation record; nothing filters it by caller identity.
- `backend/main.py:122-144` (`SendMessageRequest`) — there is no field to
  override `council_models` per-message today, only `chairman_model`.

## Fix

Generalize the existing chairman-override pattern to the panelist list too,
end to end:

1. **`mcp/server.py`** — replace the boolean `caller_is_claude` with an
   explicit `caller_model_id`:
   ```python
   if os.getenv("CLAUDE_PROJECT_DIR") or os.getenv("CLAUDE_CODE") or "claude" in sys.argv[0].lower():
       caller_model_id = "local/claude-code"
   elif os.getenv("ANTIGRAVITY_SESSION") or "antigravity" in sys.argv[0].lower():  # confirm actual env var Antigravity sets
       caller_model_id = "local/antigravity"
   else:
       caller_model_id = None
   chairman_override = "local/antigravity" if caller_model_id == "local/claude-code" else "local/claude-code"
   ```
   (Check `infra/local-models/antigravity_shim.py` / Antigravity's own env
   for the right signal — `agy` may not set an equivalent of
   `CLAUDE_PROJECT_DIR`. If no reliable signal exists, log a TODO rather than
   guessing.)

2. **Fetch the resolved panel before sending the message.** After creating
   the conversation (`POST /api/conversations`), the response already
   includes `council_models` (see `Conversation` model, `backend/main.py:200`
   and `create_conversation`, `backend/main.py:221-234`). In `ask_council`,
   read `conv_data["council_models"]`, strip any entry whose model id
   (before the `@skill` suffix) equals `caller_model_id`, and — only if that
   changed the list — pass the filtered list explicitly in the message
   payload's new `council_models` field (see step 3).

3. **`backend/main.py`** — add an optional override field to
   `SendMessageRequest` (next to the existing `chairman_model` override at
   line 128):
   ```python
   council_models: Optional[List[str]] = None  # Optional panelist-list override for this deliberation
   ```
   Thread it through the same way `chairman_model` already is, at both
   places that resolve `active_council_models` (`backend/main.py:741-749`
   and the equivalent streaming path around `:944-947`):
   ```python
   active_council_models = request.council_models or (list(c_target["council_models"]) if c_target and c_target.get("council_models") else ...)
   ```

4. **Guard against an empty panel.** If filtering leaves fewer than 2
   panelists (a 2-seat board where the caller's shim was one of them),
   `ask_council` should fail closed with a clear ADR-shaped error
   ("## Verdict: Council Misconfigured for This Caller") rather than sending
   a degenerate 1-model "council" — mirrors the existing gating-rejection
   style already used for the Type-1 checklist and recursion guard in
   `mcp/server.py`.

## Acceptance check

- Unit test (or manual call) simulating an Antigravity-originated
  `ask_council("...", council_id="cognitive-strategy")`: assert the outgoing
  `council_models` sent to `/message` no longer contains
  `local/antigravity@*`, and `chairman_model` is `local/claude-code` as
  before.
- Same call simulated as Claude-originated: behavior unchanged from today
  (no built-in board lists `local/claude-code` as a panelist, so nothing
  should be stripped) — this is a regression check, not a new assertion.
- A board artificially edited to have only 2 panelists, one of which is the
  caller's own shim: `ask_council` returns the "Council Misconfigured for
  This Caller" verdict instead of silently running with 1 panelist.

## Non-goals (do not do these while fixing this)

- Do not touch the OpenRouter / `COUNCIL_MODELS` / `CHAIRMAN_MODEL` config in
  `backend/config.py` — that's a separate, currently-unused code path
  (`OPENROUTER_API_KEY` is unset), unrelated to this bug.
- Do not change any of the 6 `BUILTIN_COUNCILS` panelist compositions —
  the fix is caller-side filtering, not board redesign.
