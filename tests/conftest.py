from __future__ import annotations

from pathlib import Path

import pytest

from servicepilot.seed import seed_database


@pytest.fixture()
def seeded_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "servicepilot-test.db"
    monkeypatch.setenv("SERVICEPILOT_MODEL_MODE", "mock")
    monkeypatch.setenv("SERVICEPILOT_DB_PATH", str(db_path))
    monkeypatch.setenv("SERVICEPILOT_CHECKPOINT_PATH", str(tmp_path / "checkpoints.db"))
    monkeypatch.setenv("SERVICEPILOT_CHECKPOINT_MODE", "sqlite")
    seed_database(db_path, force=True)
    return db_path
