import os
import tempfile

import pytest

# Must run before any backend import: data paths are resolved at import time,
# and without this the suite reads and writes the repo's real data/ directory.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="llm-council-test-")


@pytest.fixture(autouse=True)
def _auth_disabled_by_default(monkeypatch):
    """Most tests exercise endpoint logic, not auth; test_auth_required re-enables it."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
