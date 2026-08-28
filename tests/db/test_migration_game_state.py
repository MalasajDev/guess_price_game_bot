import importlib.util
from pathlib import Path


def load_migration():
    path = Path("alembic/versions/20260828_04_game_state_invariants.py")
    spec = importlib.util.spec_from_file_location("game_state_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_closes_duplicate_pending_rounds_before_unique_index(monkeypatch):
    migration = load_migration()
    statements = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.close_duplicate_pending_rounds()

    assert len(statements) == 1
    assert "ROW_NUMBER()" in statements[0]
    assert "resolved_at" in statements[0]
