"""Live integration test against a running LLM Council server.

Runs against http://localhost:8001 by default (override with COUNCIL_URL env var).
Authenticates via /api/auth/login if AUTH_ENABLED, then exercises the full
council deliberation flow: list councils → create conversation → send message
→ verify 3-stage response → delete conversation.
"""

import os
import sys
import json

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("COUNCIL_URL", "http://localhost:8001")
ADMIN_USER = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin")
TIMEOUT = float(os.getenv("TEST_TIMEOUT", "300"))  # 5 min default for full deliberation

# Expected council configuration
EXPECTED_COUNCIL_ID = "cognitive-strategy"
EXPECTED_MODELS = [
    "local/antigravity@red-team-reasoning",
    "custom/gemini-3-6-flash@red-team-reasoning",
    "local/qwen3.6-27b@first-principles",
    "local/qwen3.8-27b@deep-research",
]

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    results.append((name, passed, detail))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def step1_auth(client: httpx.Client) -> str | None:
    """Authenticate and return a Bearer token, or None if auth is disabled."""
    try:
        resp = client.get(f"{BASE_URL}/api/auth/status", timeout=10)
    except httpx.ConnectError:
        print(f"ERROR: Cannot connect to {BASE_URL}. Is the server running?")
        sys.exit(1)

    if resp.status_code == 401:
        # Auth not required but endpoint still returned 401 — try without auth
        record("auth_status_check", False, f"got {resp.status_code} but no auth header issue")
        return None

    info = resp.json()
    auth_enabled = info.get("auth_enabled", False)

    if not auth_enabled:
        record("auth_disabled", True, "AUTH_ENABLED=false, skipping login")
        return None

    # Login
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=10,
    )
    if resp.status_code != 200:
        record("login", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    token = resp.json()["token"]
    record("login", True, f"token obtained for user {resp.json()['username']}")
    return token


def step2_check_councils(client: httpx.Client, token: str | None) -> bool:
    """Verify cognitive-strategy council exists and has expected models."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = client.get(f"{BASE_URL}/api/councils", headers=headers, timeout=10)

    if resp.status_code != 200:
        record("councils_endpoint", False, f"HTTP {resp.status_code}")
        return False

    data = resp.json()
    councils = data.get("councils", [])

    # Find the target council
    target = None
    for c in councils:
        if c["id"] == EXPECTED_COUNCIL_ID:
            target = c
            break

    if target is None:
        ids = [c["id"] for c in councils]
        record("council_exists", False, f"'{EXPECTED_COUNCIL_ID}' not found. Available: {ids}")
        return False

    record("council_exists", True, f"'{EXPECTED_COUNCIL_ID}' found with {len(target.get('council_models', []))} models")

    # Check model count
    actual_models = target.get("council_models", [])
    model_count_ok = len(actual_models) == 4
    record(
        "council_model_count",
        model_count_ok,
        f"expected 4 models, got {len(actual_models)}",
    )

    # Check each expected model
    all_models_match = True
    for expected in EXPECTED_MODELS:
        found = expected in actual_models
        if not found:
            all_models_match = False
        record(
            f"model_{expected}",
            found,
            f"{'present' if found else 'MISSING — actual: ' + str(actual_models)}",
        )

    return True


def step3_create_conversation(client: httpx.Client, token: str | None) -> str | None:
    """Create a test conversation and return its ID."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = client.post(
        f"{BASE_URL}/api/conversations",
        headers=headers,
        json={"council_id": EXPECTED_COUNCIL_ID, "conversation_type": "deliberation"},
        timeout=10,
    )

    if resp.status_code not in (201, 200):
        record("create_conversation", False, f"HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    conv_id = resp.json()["id"]
    record("create_conversation", True, f"id={conv_id}")
    return conv_id


def step4_send_message(client: httpx.Client, token: str | None, conv_id: str) -> bool:
    """Send a fast test message and verify the 3-stage response."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = client.post(
        f"{BASE_URL}/api/conversations/{conv_id}/message",
        headers=headers,
        json={"content": "What is 2+2?"},
        timeout=TIMEOUT,
    )

    if resp.status_code not in (200, 201):
        record("send_message", False, f"HTTP {resp.status_code}: {resp.text[:300]}")
        return False

    body = resp.json()

    # Check for stage1
    has_stage1 = "stage1" in body and body["stage1"]
    record("response_has_stage1", has_stage1, f"{'present' if has_stage1 else 'missing or empty'}")

    # Check for stage2
    has_stage2 = "stage2" in body and body["stage2"]
    record("response_has_stage2", has_stage2, f"{'present' if has_stage2 else 'missing or empty'}")

    # Check for stage3
    has_stage3 = "stage3" in body and body["stage3"]
    record("response_has_stage3", has_stage3, f"{'present' if has_stage3 else 'missing or empty'}")

    return has_stage1 and has_stage2 and has_stage3


def step5_cleanup(client: httpx.Client, token: str | None, conv_id: str) -> None:
    """Delete the test conversation."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    resp = client.delete(
        f"{BASE_URL}/api/conversations/{conv_id}",
        headers=headers,
        timeout=10,
    )
    record("cleanup_delete", resp.status_code == 200, f"HTTP {resp.status_code}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"LLM Council Live Test — target {BASE_URL}")
    print("=" * 60)

    with httpx.Client(base_url=BASE_URL, follow_redirects=True) as client:
        # Step 1 — Auth
        token = step1_auth(client)
        if token is None and not (
            client.get(f"{BASE_URL}/api/auth/status", timeout=10).status_code == 200
            and not client.get(f"{BASE_URL}/api/auth/status", timeout=10).json().get("auth_enabled")
        ):
            # If login failed and auth is required, abort
            auth_resp = client.get(f"{BASE_URL}/api/auth/status", timeout=10)
            if auth_resp.status_code == 200 and auth_resp.json().get("auth_enabled"):
                print("\nFATAL: Login failed and auth is required. Check ADMIN_PASSWORD.")
                _print_summary()
                return 1

        # Step 2 — Council check
        step2_check_councils(client, token)

        # Step 3 — Create conversation
        conv_id = step3_create_conversation(client, token)
        if not conv_id:
            print("\nABORT: Could not create conversation. Skipping message test.")
            _print_summary()
            return 1

        try:
            # Step 4 — Send message
            step4_send_message(client, token, conv_id)
        except httpx.TimeoutException:
            record("send_message", False, f"timeout after {TIMEOUT}s")
        except Exception as e:
            record("send_message", False, f"exception: {e}")

        # Step 5 — Cleanup
        step5_cleanup(client, token, conv_id)

    _print_summary()
    return 0 if all(r[1] for r in results) else 1


def _print_summary() -> None:
    passed = sum(1 for _, ok, _ in results if ok)
    failed = sum(1 for _, ok, _ in results if not ok)
    print("=" * 60)
    print(f"Summary: {passed} passed, {failed} failed, {len(results)} total")
    if failed:
        print("\nFailures:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")


if __name__ == "__main__":
    sys.exit(main())
