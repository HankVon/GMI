"""数据范围(Data Scope)服务 — 「分发权限」的数据级授权统一入口。

设计原则:
  1. **默认不启用**: 用户与角色均未配置 data_scope_rule 时视为「未启用数据范围」,
     业务接口保持现有行为(存量状态零干扰); 仅显式配置后过滤才生效。
  2. **admin 恒为全量(ALL)**, 不过滤。
  3. **规则与实体适配**:
     - 部门级范围(DEPT_TREE / DEPT_ONLY) 只对带 department_id 列的实体生效;
     - 对象级授权(CUSTOM 的 sys_data_grant) 对任意实体生效(company/bid 等无部门列实体
       仅能通过对象级授权过滤);
     - OWN 仅对传入 owner_id_col 的实体生效(当前实体表无 owner 列, 保留机制)。
  4. 解析结果随权限缓存(auth_service)一起缓存, 授权变更时 invalidate_user_permissions 即可。
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select, or_, update
from sqlalchemy.orm import Session

from app.models.rbac import SysUser, SysRole, SysDataGrant, SysDepartment

# 数据范围规则常量
SCOPE_ALL = "ALL"          # 全量可见
SCOPE_DEPT_TREE = "DEPT_TREE"  # 本部门及子部门
SCOPE_DEPT_ONLY = "DEPT_ONLY"  # 仅本部门
SCOPE_OWN = "OWN"          # 仅本人创建/负责
SCOPE_CUSTOM = "CUSTOM"    # 自定义(部门 + 对象级授权)

SCOPE_RULES = (SCOPE_ALL, SCOPE_DEPT_TREE, SCOPE_DEPT_ONLY, SCOPE_OWN, SCOPE_CUSTOM)

# 范围「宽→窄」排序, 多角色取最宽者
_SCOPE_RANK = {
    SCOPE_ALL: 5,
    SCOPE_CUSTOM: 4,
    SCOPE_DEPT_TREE: 3,
    SCOPE_DEPT_ONLY: 2,
    SCOPE_OWN: 1,
}


class DataScope:
    """解析后的生效数据范围。enabled=False 表示未启用(业务层保持现状)。"""

    __slots__ = ("enabled", "rule", "dept_ids", "grants")

    def __init__(self, enabled: bool = False, rule: str = "",
                 dept_ids: Optional[list[int]] = None,
                 grants: Optional[dict[str, list[int]]] = None):
        self.enabled = enabled
        self.rule = rule
        self.dept_ids = dept_ids or []
        self.grants = grants or {}

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "rule": self.rule,
            "dept_ids": self.dept_ids,
            "grants": self.grants,
        }

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "DataScope":
        if not d or not d.get("enabled"):
            return cls(enabled=False)
        return cls(
            enabled=True,
            rule=d.get("rule", ""),
            dept_ids=d.get("dept_ids") or [],
            grants=d.get("grants") or {},
        )


# ── 部门树展开 ──
def dept_tree_ids(db: Session, dept_ids: list[int]) -> list[int]:
    """把部门ID列表展开为「包含所有子部门」的ID列表(利用 sys_department.path 前缀)。

    path 形如 /1/3/15: 子部门的 path 以父 path + '/' 开头。
    """
    dept_ids = [d for d in dept_ids or [] if d]
    if not dept_ids:
        return []
    rows = db.execute(
        select(SysDepartment.id, SysDepartment.path).where(
            SysDepartment.id.in_(dept_ids), SysDepartment.is_deleted == False  # noqa: E712
        )
    ).all()
    result: set[int] = set()
    for did, path in rows:
        result.add(did)
        if path:
            subs = db.execute(
                select(SysDepartment.id).where(
                    SysDepartment.path.like(path + "/%"),
                    SysDepartment.is_deleted == False,  # noqa: E712
                )
            ).scalars().all()
            result.update(subs)
    return sorted(result)


# ── 对象级授权查询 ──
def object_grants(db: Session, user_id: int) -> dict[str, list[int]]:
    """用户未过期的对象级授权: {entity_type: [entity_id, ...]}。"""
    now = datetime.datetime.now()
    rows = db.execute(
        select(SysDataGrant.entity_type, SysDataGrant.entity_id).where(
            SysDataGrant.user_id == user_id,
            SysDataGrant.is_deleted == False,  # noqa: E712
            or_(
                SysDataGrant.expire_at.is_(None),
                SysDataGrant.expire_at > now,
            ),
        )
    ).all()
    grants: dict[str, list[int]] = {}
    for entity_type, entity_id in rows:
        grants.setdefault(entity_type, []).append(entity_id)
    return grants


def clean_expired_grants(db: Session) -> int:
    """软删过期的对象级授权记录(幂等)。启动时调用。

    Neo4j 授权边带 expire_at, 图谱查询处也会过滤过期边;
    此处只清理 MySQL 数据源, 避免授权记录无限堆积。
    """
    now = datetime.datetime.now()
    rows = db.execute(
        select(SysDataGrant.id).where(
            SysDataGrant.expire_at.isnot(None),
            SysDataGrant.expire_at <= now,
            SysDataGrant.is_deleted == False,  # noqa: E712
        )
    ).scalars().all()
    if rows:
        db.execute(
            update(SysDataGrant)
            .where(SysDataGrant.id.in_(rows))
            .values(is_deleted=True)
        )
        db.commit()
    return len(rows)


def _role_scopes(db: Session, user_id: int) -> list[SysRole]:
    """用户拥有的已启用数据范围的角色。"""
    from app.models.rbac import SysUserRole
    return list(db.execute(
        select(SysRole).join(SysUserRole, SysUserRole.role_id == SysRole.id).where(
            SysUserRole.user_id == user_id,
            SysRole.is_deleted == False,  # noqa: E712
            SysRole.data_scope_rule.isnot(None),
            SysRole.data_scope_rule != "",
        )
    ).scalars().all())


def build_data_scope(db: Session, user_id: int, roles: Optional[list[str]] = None) -> DataScope:
    """从 DB 计算用户生效的数据范围(供权限缓存使用)。

    roles: 角色 code 列表, 用于快速判定 admin; 不传则查询 DB。
    """
    if roles and "admin" in roles:
        return DataScope(enabled=True, rule=SCOPE_ALL)

    su = db.execute(
        select(SysUser).where(SysUser.id == user_id, SysUser.is_deleted == False)  # noqa: E712
    ).scalar_one_or_none()
    if not su:
        return DataScope(enabled=False)

    # 用户级配置优先
    user_rule = (su.data_scope_rule or "").strip().upper()
    if user_rule:
        if user_rule not in SCOPE_RULES:
            user_rule = ""
        else:
            rule = user_rule
            dept_ids = dept_tree_ids(db, su.scope_dept_ids or []) \
                if rule in (SCOPE_DEPT_TREE, SCOPE_DEPT_ONLY, SCOPE_CUSTOM) else []
            grants = object_grants(db, user_id)
            return DataScope(enabled=True, rule=rule, dept_ids=dept_ids, grants=grants)

    # 用户级未配置 → 汇总角色配置(取最宽规则; 部门ID与对象授权合并)
    role_rows = _role_scopes(db, user_id)
    if not role_rows:
        return DataScope(enabled=False)

    best_rule = ""
    best_rank = -1
    all_dept: set[int] = set()
    for r in role_rows:
        rk = _SCOPE_RANK.get((r.data_scope_rule or "").upper(), -1)
        if rk > best_rank:
            best_rank = rk
            best_rule = (r.data_scope_rule or "").upper()
        if r.scope_dept_ids:
            all_dept.update(dept_tree_ids(db, r.scope_dept_ids))
    if best_rule not in SCOPE_RULES:
        return DataScope(enabled=False)
    grants = object_grants(db, user_id)
    return DataScope(enabled=True, rule=best_rule, dept_ids=sorted(all_dept), grants=grants)


def resolve_scope(db: Session, user: dict, entity_type: str = "") -> DataScope:
    """从当前用户(缓存 dict)解析生效数据范围。

    user dict 来自权限缓存; 旧缓存无 data_scope 字段时回退 DB 计算。
    """
    if "admin" in (user.get("roles") or []):
        return DataScope(enabled=True, rule=SCOPE_ALL)

    cached = user.get("data_scope")
    if cached is not None:
        return DataScope.from_dict(cached)

    scope = build_data_scope(db, int(user["user_id"]), roles=user.get("roles"))
    return scope


def scope_filter(scope: DataScope, entity, entity_type: str,
                 dept_id_col=None, owner_id_col=None, user_id: Optional[int] = None):
    """生成数据范围过滤条件(SQLAlchemy)。返回 None 表示不过滤。

    Args:
        scope: 解析后的数据范围
        entity: 实体模型类(须有 id 主键列)
        entity_type: 实体类型字符串(project/company/bid...)
        dept_id_col: 实体部门列(如 Project.department_id); 无部门列的实体传 None
        owner_id_col: 实体 owner 列(OWN 规则用); 不支持的实体传 None
        user_id: 当前用户ID(OWN 规则判断归属人)
    """
    if not scope.enabled or scope.rule == SCOPE_ALL:
        return None

    conds = []

    # 部门范围: 仅对带部门列的实体生效
    if scope.dept_ids and dept_id_col is not None:
        conds.append(dept_id_col.in_(scope.dept_ids))

    # 对象级授权: 任意实体生效
    obj_ids = scope.grants.get(entity_type) or []
    if obj_ids:
        conds.append(entity.id.in_(obj_ids))

    # 本人范围: 仅对带 owner 列的实体生效
    if scope.rule == SCOPE_OWN and owner_id_col is not None and user_id:
        conds.append(owner_id_col == user_id)

    if not conds:
        # 有启用配置但无任何可用条件(如对无部门列实体配置了纯部门范围) →
        # 保持现状(不过滤), 避免误伤。由调用方决定是否需要更严格处理。
        return None

    return or_(*conds)
