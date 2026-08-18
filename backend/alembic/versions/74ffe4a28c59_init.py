"""init — baseline migration after init_ddl.sql

Revision ID: 74ffe4a28c59
Revises:
Create Date: 2026-07-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '74ffe4a28c59'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tables already created by sql/init_ddl.sql. This migration stamps the baseline."""
    pass


def downgrade() -> None:
    pass
