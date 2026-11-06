import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def no_viewer_respawn(monkeypatch):
    # Mutating commands must not spawn viewers behind the tests' backs.
    monkeypatch.setenv("CONSTRUCT_NO_VIEWER", "1")
