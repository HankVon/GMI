"""add credit_level column to company

Revision ID: 0007_company_credit_level
Revises: 0006_assoc_progress
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007_company_credit_level'
down_revision: Union[str, None] = '0006_assoc_progress'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "company",
        sa.Column("credit_level", sa.String(32), nullable=True, comment="信用等级"),
    )


def downgrade() -> None:
    op.drop_column("company", "credit_level")
