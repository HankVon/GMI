"""add project_member + project_progress tables

Revision ID: 0006_assoc_progress
Revises: 0005_company_base
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0006_assoc_progress'
down_revision: Union[str, None] = '0005_company_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'project_member',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='primary key'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False, comment='create time'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False, comment='update time'),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False, comment='soft delete flag'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='项目ID'),
        sa.Column('person_id', sa.BigInteger(), nullable=False, comment='人员ID'),
        sa.Column('role', sa.String(64), nullable=False, comment='项目角色'),
        sa.Column('responsibility', sa.String(512), nullable=True, comment='职责描述'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, comment='加入时间'),
        sa.Column('left_at', sa.DateTime(), nullable=True, comment='退出时间'),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False, comment='是否在职'),
        sa.Column('ext_attrs', sa.JSON(), nullable=True, comment='动态扩展字段'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_pm_project', 'project_id'),
        sa.Index('idx_pm_person', 'person_id'),
        sa.Index('idx_pm_active', 'is_active'),
        comment='项目-人员关联表',
    )

    op.create_table(
        'project_progress',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='primary key'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False, comment='create time'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False, comment='update time'),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.false(), nullable=False, comment='soft delete flag'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='项目ID'),
        sa.Column('title', sa.String(256), nullable=False, comment='进展标题'),
        sa.Column('content', sa.Text(), nullable=True, comment='进展详情'),
        sa.Column('progress_date', sa.DateTime(), nullable=False, comment='进展日期'),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False, comment='排序权重(越小越靠前)'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_pp_project', 'project_id'),
        sa.Index('idx_pp_date', 'progress_date'),
        comment='项目进展记录表',
    )


def downgrade() -> None:
    op.drop_table('project_progress')
    op.drop_table('project_member')
