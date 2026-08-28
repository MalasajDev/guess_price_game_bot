"""Initial game tables.

Revision ID: 20260826_01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("category", sa.String(32)),
        sa.Column("currency", sa.String(3)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_game_sessions_user_id", "game_sessions", ["user_id"])
    op.create_index("ix_game_sessions_status", "game_sessions", ["status"])

    op.create_table(
        "rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("source_listing_id", sa.String(255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.Text(), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("translated_title", sa.Text(), nullable=False),
        sa.Column("translated_description", sa.Text(), nullable=False),
        sa.Column("source_price", sa.Numeric(20, 4), nullable=False),
        sa.Column("source_currency", sa.String(3), nullable=False),
        sa.Column("conversion_rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("displayed_price", sa.Numeric(20, 2), nullable=False),
        sa.Column("displayed_currency", sa.String(3), nullable=False),
        sa.Column("threshold", sa.Numeric(20, 2)),
        sa.Column("answer", sa.Text()),
        sa.Column("correct", sa.Boolean()),
        sa.Column("provider_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rate_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_rounds_session_id", "rounds", ["session_id"])

    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("target_currency", sa.String(3), nullable=False, unique=True),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("provider_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
    op.drop_index("ix_rounds_session_id", table_name="rounds")
    op.drop_table("rounds")
    op.drop_index("ix_game_sessions_status", table_name="game_sessions")
    op.drop_index("ix_game_sessions_user_id", table_name="game_sessions")
    op.drop_table("game_sessions")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
