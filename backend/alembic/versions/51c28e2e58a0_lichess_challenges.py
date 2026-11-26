"""Lichess challenges: what the bot sent, counted against the daily cap.

Revision ID: 51c28e2e58a0
Revises: 4480c273f208
Create Date: 2026-11-26 09:28:06.043413

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "51c28e2e58a0"
down_revision: str | Sequence[str] | None = "4480c273f208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lichess_challenges",
        sa.Column("opponent", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lichess_challenges", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_lichess_challenges_created_at"), ["created_at"], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("lichess_challenges", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lichess_challenges_created_at"))

    op.drop_table("lichess_challenges")
