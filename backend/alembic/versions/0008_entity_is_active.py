"""add is_active column to person and project

Revision ID: 0008_entity_is_active
Revises: 0007_company_credit_level
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008_entity_is_active'
down_revision: Union[str, None] = '0007_company_credit_level'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "person",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
    )
    op.add_column(
        "project",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否启用"),
    )


def downgrade() -> None:
    op.drop_column("project", "is_active")
    op.drop_column("person", "is_active")
