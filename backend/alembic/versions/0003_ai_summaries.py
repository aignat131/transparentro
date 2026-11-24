"""ai_summaries: rezumate AI pentru firme/ONG-uri și instituții

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_summaries",
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("ref", sa.String(40), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_summaries")
