"""LLM calls: the tokens written to the prompt cache.

The calls made before this column existed get them back from their cost, which pi computed
with its Haiku 5.5 prices (per million tokens: 0.10 input, 0.01 cache read, 0.125 cache write,
0.50 output): the remainder of the cost is the cache writes. A new column is filled, no
recorded value changes.

Revision ID: 07cf76de2b64
Revises: 51c28e2e58a0
Create Date: 2026-11-26 11:22:56.072397

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "07cf76de2b64"
down_revision: str | Sequence[str] | None = "51c28e2e58a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("llm_calls", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("cache_write_tokens", sa.Integer(), server_default="0", nullable=False)
        )

    op.execute(
        """
        UPDATE llm_calls SET cache_write_tokens = CAST(ROUND(MAX(0,
            (cost_usd - input_tokens * 0.10e-6 - cached_tokens * 0.01e-6
             - output_tokens * 0.50e-6) / 0.125e-6)) AS INTEGER)
        WHERE model LIKE '%haiku-5-5%' OR model LIKE '%haiku-5.5%'
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("llm_calls", schema=None) as batch_op:
        batch_op.drop_column("cache_write_tokens")
