"""add company + project_company tables + person.company_id

Revision ID: 0005_company_base
Revises: add_person_id_v1
Create Date: 2026-07-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005_company_base'
down_revision: Union[str, None] = 'add_person_id_v1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # company table
    op.create_table('company',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('code', sa.String(64), nullable=False, comment='单位编码'),
        sa.Column('name', sa.String(256), nullable=False, comment='单位名称'),
        sa.Column('short_name', sa.String(128), nullable=True, comment='简称'),
        sa.Column('company_type', sa.String(64), nullable=True, comment='单位类型(关联 option_set:company_type)'),
        sa.Column('province', sa.String(64), nullable=True, comment='省份'),
        sa.Column('city', sa.String(64), nullable=True, comment='城市'),
        sa.Column('industry', sa.String(128), nullable=True, comment='行业'),
        sa.Column('credit_code', sa.String(64), nullable=True, unique=True, comment='统一社会信用代码'),
        sa.Column('website', sa.String(512), nullable=True, comment='官网'),
        sa.Column('address', sa.String(512), nullable=True, comment='地址'),
        sa.Column('ext_attrs', sa.JSON(), nullable=True, comment='动态扩展字段'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0'), comment='软删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('credit_code'),
    )

    # person.company_id
    op.add_column('person', sa.Column('company_id', sa.BigInteger(), nullable=True, comment='所属单位ID'))
    op.create_index('idx_person_company_id', 'person', ['company_id'])

    # project_company association table
    op.create_table('project_company',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('project_id', sa.BigInteger(), nullable=False, comment='项目ID'),
        sa.Column('company_id', sa.BigInteger(), nullable=False, comment='单位ID'),
        sa.Column('role', sa.String(64), nullable=False, comment='角色(关联 option_set:project_company_role)'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, comment='参与时间'),
        sa.Column('left_at', sa.DateTime(), nullable=True, comment='退出时间'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1'), comment='是否参与中'),
        sa.Column('ext_attrs', sa.JSON(), nullable=True, comment='动态扩展字段'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0'), comment='软删除'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_project_company_active', 'project_id', 'company_id', 'is_active'),
        sa.Index('idx_company_timeline', 'company_id', 'joined_at', 'left_at'),
    )

    # seed option sets
    op.execute("""
        INSERT INTO option_set (code, name, description, created_at, updated_at, is_deleted) VALUES
        ('company_type', '单位类型', '业主/设计院/监理/施工/政府/供应商/合作伙伴', NOW(), NOW(), 0),
        ('project_company_role', '项目单位角色', '业主/设计/监理/施工/合作伙伴', NOW(), NOW(), 0)
        ON DUPLICATE KEY UPDATE name=VALUES(name)
    """)
    op.execute("""
        INSERT INTO option_item (option_set_id, value, label, sort_order, color, created_at, updated_at, is_deleted)
        SELECT os.id, v, l, s, c, NOW(), NOW(), 0 FROM (
            SELECT '业主' as v, '业主' as l, 1 as s, '#1890ff' as c UNION ALL
            SELECT '设计院', '设计院', 2, '#52c41a' UNION ALL
            SELECT '监理', '监理', 3, '#faad14' UNION ALL
            SELECT '施工', '施工', 4, '#722ed1' UNION ALL
            SELECT '政府', '政府', 5, '#ff4d4f' UNION ALL
            SELECT '供应商', '供应商', 6, '#13c2c2' UNION ALL
            SELECT '合作伙伴', '合作伙伴', 7, '#fa8c16'
        ) t, option_set os WHERE os.code='company_type'
        AND NOT EXISTS (SELECT 1 FROM option_item oi WHERE oi.option_set_id=os.id AND oi.value=t.v)
    """)
    op.execute("""
        INSERT INTO option_item (option_set_id, value, label, sort_order, color, created_at, updated_at, is_deleted)
        SELECT os.id, v, l, s, c, NOW(), NOW(), 0 FROM (
            SELECT 'owner' as v, '业主' as l, 1 as s, '#1890ff' as c UNION ALL
            SELECT 'designer', '设计', 2, '#52c41a' UNION ALL
            SELECT 'supervisor', '监理', 3, '#faad14' UNION ALL
            SELECT 'constructor', '施工', 4, '#722ed1' UNION ALL
            SELECT 'partner', '合作伙伴', 5, '#13c2c2'
        ) t, option_set os WHERE os.code='project_company_role'
        AND NOT EXISTS (SELECT 1 FROM option_item oi WHERE oi.option_set_id=os.id AND oi.value=t.v)
    """)

    # seed api_company_crud permission
    op.execute("""
        INSERT INTO sys_permission (code, name, resource_type, resource_value, parent_id, sort_order, created_at, updated_at, is_deleted)
        SELECT 'api_company_crud', '单位CRUD', 'api', '/api/v1/companies/*', NULL, 17, NOW(), NOW(), 0
        WHERE NOT EXISTS (SELECT 1 FROM sys_permission WHERE code='api_company_crud')
    """)
    op.execute("""
        INSERT INTO sys_role_permission (role_id, permission_id, created_at)
        SELECT 1, id, NOW() FROM sys_permission WHERE code='api_company_crud'
        AND NOT EXISTS (SELECT 1 FROM sys_role_permission WHERE role_id=1 AND permission_id=(
            SELECT id FROM sys_permission WHERE code='api_company_crud'))
    """)


def downgrade() -> None:
    op.drop_table('project_company')
    op.drop_index('idx_person_company_id', table_name='person')
    op.drop_column('person', 'company_id')
    op.drop_table('company')
