"""Add indexes for hot game queries.

Revision ID: 20260827_03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260827_03"
down_revision: str | None = "20260827_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_game_sessions_chat_status",
        "game_sessions",
        ["chat_id", "status"],
    )
    op.create_index(
        "ix_game_sessions_user_status",
        "game_sessions",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_rounds_session_resolved_created",
        "rounds",
        ["session_id", "resolved_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rounds_session_resolved_created", table_name="rounds")
    op.drop_index("ix_game_sessions_user_status", table_name="game_sessions")
    op.drop_index("ix_game_sessions_chat_status", table_name="game_sessions")
