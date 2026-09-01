from typing import Optional
import datetime
from sqlalchemy import String, BigInteger, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel
from app.database import Base


class SysUser(BaseModel):
    """系统用户表"""
    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False, comment="密码哈希")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="显示名")
    email: Mapped[Optional[str]] = mapped_column(String(256), default=None, comment="邮箱")
    phone: Mapped[Optional[str]] = mapped_column(String(32), default=None, comment="手机号")
    department_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="部门ID")
    person_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="关联人员ID")
    data_scope_rule: Mapped[Optional[str]] = mapped_column(
        String(16), default=None, comment="用户级数据范围:ALL/DEPT_TREE/DEPT_ONLY/OWN/CUSTOM, NULL=继承角色"
    )
    scope_dept_ids: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="用户级部门范围ID列表"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="启用状态")


class SysRole(BaseModel):
    """角色表"""
    __tablename__ = "sys_role"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="角色编码")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="角色名称")
    description: Mapped[Optional[str]] = mapped_column(String(512), default=None, comment="角色描述")
    data_scope_rule: Mapped[Optional[str]] = mapped_column(
        String(16), default=None, comment="角色默认数据范围:ALL/DEPT_TREE/DEPT_ONLY/OWN/CUSTOM, NULL=未启用"
    )
    scope_dept_ids: Mapped[Optional[list]] = mapped_column(
        JSON, default=None, comment="角色级部门范围ID列表"
    )


class SysPermission(BaseModel):
    """权限表"""
    __tablename__ = "sys_permission"

    code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, comment="权限编码")
    name: Mapped[str] = mapped_column(String(256), nullable=False, comment="权限名称")
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="资源类型:menu/button/api")
    resource_value: Mapped[str] = mapped_column(String(512), nullable=False, comment="资源标识")
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="父权限ID")
    sort_order: Mapped[int] = mapped_column(default=0, comment="排序")


class SysUserRole(Base):
    """用户-角色关联(DDL 中只有 id/user_id/role_id/created_at)"""
    __tablename__ = "sys_user_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户ID")
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="角色ID")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="创建时间")


class SysRolePermission(Base):
    """角色-权限关联(DDL 中只有 id/role_id/permission_id/created_at)"""
    __tablename__ = "sys_role_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="角色ID")
    permission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="权限ID")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now, comment="创建时间")


class SysDepartment(BaseModel):
    """部门表"""
    __tablename__ = "sys_department"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, comment="部门编码")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="部门名称")
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="父部门ID")
    path: Mapped[Optional[str]] = mapped_column(String(1024), default=None, comment="层级路径")
    sort_order: Mapped[int] = mapped_column(default=0, comment="排序")


class SysDataGrant(Base):
    """对象级数据授权 — 「分发权限」的数据维度(与 sys_data_grant 表对应)"""
    __tablename__ = "sys_data_grant"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="被授权用户ID")
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="实体类型:project/company/bid")
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="实体ID")
    grant_type: Mapped[str] = mapped_column(String(16), default="view", comment="授权类型:view查看/own负责")
    expire_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, default=None, comment="过期时间")
    granted_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="授权人用户ID")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="创建时间"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="软删除:0-否,1-是")


class SysUserPermission(Base):
    """用户级功能直授 — 绕过角色, 直接给用户挂功能权限(例外/临时授权)"""
    __tablename__ = "sys_user_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户ID")
    permission_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="权限ID")
    granted_by: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment="授权人用户ID")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now, comment="创建时间"
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="软删除:0-否,1-是")

