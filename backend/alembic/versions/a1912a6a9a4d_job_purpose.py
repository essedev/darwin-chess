"""job purpose

Revision ID: a1912a6a9a4d
Revises: 07cf76de2b64
Create Date: 2026-11-28 11:39:50.308151

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1912a6a9a4d"
down_revision: str | Sequence[str] | None = "07cf76de2b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purpose", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("purpose")
