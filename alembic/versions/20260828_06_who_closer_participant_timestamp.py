"""Add missing participant timestamp.

Revision ID: 20260828_06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260828_06"
down_revision: str | None = "20260828_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "who_closer_participants",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("who_closer_participants", "created_at")

