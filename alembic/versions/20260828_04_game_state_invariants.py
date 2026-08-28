"""Enforce one active game and one pending round per session.

Revision ID: 20260828_04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260828_04"
down_revision: str | None = "20260827_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def close_duplicate_active_games() -> None:
    op.execute(
        "WITH ranked AS ("
        " SELECT id, ROW_NUMBER() OVER (PARTITION BY chat_id ORDER BY created_at DESC, id DESC) AS position"
        " FROM game_sessions WHERE status = 'active'"
        ") UPDATE game_sessions AS game"
        " SET status = 'stopped'"
        " FROM ranked"
        " WHERE game.id = ranked.id AND ranked.position > 1"
    )


def close_duplicate_pending_rounds() -> None:
    op.execute(
        "WITH ranked AS ("
        " SELECT id, ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY created_at DESC, id DESC) AS position"
        " FROM rounds WHERE resolved_at IS NULL"
        ") UPDATE rounds AS round"
        " SET resolved_at = CURRENT_TIMESTAMP, correct = FALSE, answer = 'migration duplicate cleanup'"
        " FROM ranked"
        " WHERE round.id = ranked.id AND ranked.position > 1"
    )


def upgrade() -> None:
    close_duplicate_active_games()
    close_duplicate_pending_rounds()
    op.execute(
        "CREATE UNIQUE INDEX uq_game_sessions_one_active_chat "
        "ON game_sessions (chat_id) WHERE status = 'active'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_rounds_one_pending_session "
        "ON rounds (session_id) WHERE resolved_at IS NULL"
    )


def downgrade() -> None:
    op.drop_index("uq_rounds_one_pending_session", table_name="rounds")
    op.drop_index("uq_game_sessions_one_active_chat", table_name="game_sessions")
