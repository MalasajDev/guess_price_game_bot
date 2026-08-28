"""Add chat-scoped games and group membership.

Revision ID: 20260827_02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_02"
down_revision: str | None = "20260826_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("game_sessions", sa.Column("chat_id", sa.BigInteger(), nullable=True))
    op.execute(
        "UPDATE game_sessions SET chat_id = users.telegram_id "
        "FROM users WHERE users.id = game_sessions.user_id"
    )
    with op.batch_alter_table("game_sessions") as batch_op:
        batch_op.alter_column("chat_id", nullable=False)
    op.create_index("ix_game_sessions_chat_id", "game_sessions", ["chat_id"])

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("chat_id", "user_id", name="uq_group_member"),
    )
    op.create_index("ix_group_members_chat_id", "group_members", ["chat_id"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_group_members_user_id", table_name="group_members")
    op.drop_index("ix_group_members_chat_id", table_name="group_members")
    op.drop_table("group_members")
    op.drop_index("ix_game_sessions_chat_id", table_name="game_sessions")
    op.drop_column("game_sessions", "chat_id")
