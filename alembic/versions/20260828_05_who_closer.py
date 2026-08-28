"""Add who-closer state and card reply tracking.

Revision ID: 20260828_05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260828_05"
down_revision: str | None = "20260828_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("has_private_chat", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("game_sessions", sa.Column("registration_deadline", sa.DateTime(timezone=True)))
    op.add_column("game_sessions", sa.Column("answer_deadline", sa.DateTime(timezone=True)))
    op.add_column("rounds", sa.Column("card_message_id", sa.Integer()))
    op.create_table(
        "who_closer_participants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("added_time", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("session_id", "user_id", name="uq_who_closer_participant"),
    )
    op.create_table(
        "who_closer_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "round_id",
            sa.String(36),
            sa.ForeignKey("rounds.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("price", sa.Numeric(20, 2), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("round_id", "user_id", name="uq_who_closer_answer_user"),
        sa.UniqueConstraint("round_id", "price", name="uq_who_closer_answer_price"),
    )


def downgrade() -> None:
    op.drop_table("who_closer_answers")
    op.drop_table("who_closer_participants")
    op.drop_column("rounds", "card_message_id")
    op.drop_column("game_sessions", "answer_deadline")
    op.drop_column("game_sessions", "registration_deadline")
    op.drop_column("users", "has_private_chat")
