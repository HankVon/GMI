"""add sys_user.person_id

Revision ID: add_person_id_v1
Revises: 74ffe4a28c59
Create Date: 2026-07-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'add_person_id_v1'
down_revision: Union[str, None] = '74ffe4a28c59'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sys_user', sa.Column('person_id', sa.BigInteger(), nullable=True, comment='关联人员ID'))
    op.create_index('idx_sys_user_person_id', 'sys_user', ['person_id'])


def downgrade() -> None:
    op.drop_index('idx_sys_user_person_id', table_name='sys_user')
    op.drop_column('sys_user', 'person_id')
