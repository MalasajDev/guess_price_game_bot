from pathlib import Path


def test_followup_migration_adds_participant_timestamp():
    migration = Path("alembic/versions/20260828_06_who_closer_participant_timestamp.py")
    assert migration.exists()
    assert "created_at" in migration.read_text(encoding="utf-8")
