"""contracts.duplicate_of_id: rânduri repetate ale aceluiași contract (asocieri, loturi)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("duplicate_of_id", sa.Integer(), nullable=True))
    op.add_column(
        "contracts",
        sa.Column("repeat_same_company", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_contracts_duplicate_of", "contracts", "contracts", ["duplicate_of_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_contracts_duplicate_of_id", "contracts", ["duplicate_of_id"])


def downgrade() -> None:
    op.drop_index("ix_contracts_duplicate_of_id", table_name="contracts")
    op.drop_constraint("fk_contracts_duplicate_of", "contracts", type_="foreignkey")
    op.drop_column("contracts", "repeat_same_company")
    op.drop_column("contracts", "duplicate_of_id")
