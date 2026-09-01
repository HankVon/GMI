"""标讯后台管理 API — 录入/编辑/审核/发布/下架/统计。

生命周期状态机(status 列):
  draft →(submit)→ pending →(review approve)→ approved →(publish)→ published
                             →(review reject)→ rejected (编辑后重提)
  published →(offline)→ offline →(restore)→ published
  已发布/下架标讯再次编辑 → 回 draft 重新走审核

所有写操作落 audit_log + bid_review_record(审核/发布流水), 编辑写 field_change_history。
"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.bid_notice import (
    BidNotice,
    BID_STATUS_DRAFT, BID_STATUS_PENDING, BID_STATUS_APPROVED,
    BID_STATUS_REJECTED, BID_STATUS_PUBLISHED, BID_STATUS_OFFLINE,
)
from app.models.bid_review_record import BidReviewRecord
from app.models.user_entity_action import UserEntityAction
from app.schemas.bid_admin import (
    BidCreatePayload, BidUpdatePayload, ReviewPayload, OfflinePayload, BatchPayload,
)
from app.services.audit_service import log_action, track_field_changes

router = APIRouter(prefix="/admin/bids", tags=["标讯后台管理"])

# 允许直接发布的状态(无需审核即可上线, 用于「来源采集直接可见」的兼容路径)
_DIRECT_PUBLISHABLE = {BID_STATUS_DRAFT, BID_STATUS_PENDING, BID_STATUS_APPROVED}

# 简单列白名单(后台可直接覆盖的 bid_notice 独立列)
_SCALAR_COLS = (
    "title", "url", "notice_type", "category", "industry", "region",
    "purchaser", "purchaser_company_id", "agency",
    "source_id", "source_name", "purchase_way", "price_type",
    "budget_min", "budget_max",
)


def _get_bid_or_404(db: Session, bid_id: int) -> BidNotice:
    bn = db.get(BidNotice, bid_id)
    if not bn or bn.is_deleted:
        raise HTTPException(status_code=404, detail="标讯不存在")
    return bn


def _get_meta(bn: BidNotice) -> dict:
    return dict(bn.meta) if isinstance(bn.meta, dict) else {}


def _merge_payload(bn: BidNotice, data: dict) -> None:
    """把 payload 字段合并进模型列 + meta 结构化分组(只覆盖传入的键)。"""
    meta = _get_meta(bn)
    for key in _SCALAR_COLS:
        if key in data and data[key] is not None:
            setattr(bn, key, data[key])
    if "published_at" in data and data["published_at"] is not None:
        bn.published_at = data["published_at"]

    def _merge_group(meta_key: str, group_data: dict | None) -> None:
        if group_data is None:
            return
        cur = dict(meta.get(meta_key) or {})
        for k, v in group_data.items():
            if v is not None:
                cur[k] = v
        meta[meta_key] = cur

    if data.get("project"):
        _merge_group("project_info", data["project"])
    if data.get("finance"):
        _merge_group("finance", data["finance"])
    if data.get("evaluation"):
        _merge_group("evaluation", data["evaluation"])
    if data.get("requirements"):
        _merge_group("requirements", data["requirements"])
    if data.get("keywords") is not None:
        meta["keywords"] = data["keywords"]
    if data.get("timeline") is not None:
        meta["timeline"] = [t.model_dump() if hasattr(t, "model_dump") else t for t in data["timeline"]]
    if data.get("suppliers") is not None:
        meta["suppliers"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in data["suppliers"]]
    if data.get("body") is not None:
        meta["body"] = data["body"]
    if data.get("industry"):
        meta["industry"] = data["industry"]
    if data.get("agency"):
        meta["agency"] = data["agency"]
    bn.meta = meta


def _add_record(
    db: Session, bid_id: int, action: str, user: dict,
    comment: Optional[str] = None, from_status: Optional[str] = None,
    to_status: Optional[str] = None,
) -> None:
    db.add(BidReviewRecord(
        bid_id=bid_id, action=action,
        reviewer_id=user.get("user_id"),
        reviewer_name=user.get("username") or user.get("display_name") or "",
        comment=comment, from_status=from_status, to_status=to_status,
    ))


def _audit(db: Session, user: dict, action: str, bn: BidNotice, detail: Optional[dict] = None) -> None:
    log_action(
        db, user.get("user_id"), user.get("username") or user.get("display_name"),
        action, "bid", bn.id, bn.title, detail,
    )


def _interact_counts(db: Session, bid_ids: list[int]) -> dict[int, dict]:
    """批量取监控/收藏计数: {bid_id: {monitored, collected}}"""
    if not bid_ids:
        return {}
    rows = db.execute(
        select(UserEntityAction.entity_id, UserEntityAction.monitored, UserEntityAction.collected)
        .where(
            UserEntityAction.entity_type == "bid",
            UserEntityAction.entity_id.in_(bid_ids),
            UserEntityAction.is_deleted == False,  # noqa: E712
        )
    ).all()
    out: dict[int, dict] = {}
    for bid_id, monitored, collected in rows:
        item = out.setdefault(bid_id, {"monitored": 0, "collected": 0})
        item["monitored"] += int(bool(monitored))
        item["collected"] += int(bool(collected))
    return out


def _bn_admin_dict(bn: BidNotice) -> dict:
    meta = _get_meta(bn)
    suppliers = meta.get("suppliers") or []
    matched = bool(bn.purchaser_company_id) or any(
        bool(s.get("supplier_company_id")) for s in suppliers if isinstance(s, dict)
    )
    return {
        "id": bn.id,
        "title": bn.title,
        "url": bn.url,
        "notice_type": bn.notice_type,
        "category": bn.category,
        "industry": bn.industry or meta.get("industry"),
        "region": bn.region,
        "purchaser": bn.purchaser,
        "purchaser_company_id": bn.purchaser_company_id,
        "agency": bn.agency,
        "source_id": bn.source_id,
        "source_name": bn.source_name,
        "purchase_way": bn.purchase_way,
        "price_type": bn.price_type,
        "budget_min": bn.budget_min,
        "budget_max": bn.budget_max,
        "budget_display": (meta.get("finance") or {}).get("budget"),
        "published_at": bn.published_at.strftime("%Y-%m-%d %H:%M") if bn.published_at else "",
        "status": bn.status,
        "supplier_count": len([s for s in suppliers if isinstance(s, dict)]),
        "matched": matched,
        "created_by": bn.created_by,
        "created_at": bn.created_at.strftime("%Y-%m-%d %H:%M") if bn.created_at else "",
        "updated_at": bn.updated_at.strftime("%Y-%m-%d %H:%M") if bn.updated_at else "",
    }


def _bn_admin_detail(bn: BidNotice) -> dict:
    meta = _get_meta(bn)
    project = meta.get("project_info") or {}
    finance = meta.get("finance") or {}
    evaluation = meta.get("evaluation") or {}
    requirements = meta.get("requirements") or {}
    timeline = meta.get("timeline") or []
    if isinstance(timeline, dict):
        timeline = [{"label": k, "value": v} for k, v in timeline.items()]
    out = _bn_admin_dict(bn)
    out.update({
        "project_code": project.get("code"),
        "project": {
            "code": project.get("code"),
            "type": project.get("type"), "scale": project.get("scale"),
            "scope": project.get("scope"), "duration": project.get("duration"),
            "method": project.get("method"),
            "registration_deadline": project.get("registration_deadline"),
            "document_deadline": project.get("document_deadline"),
            "bid_deadline": project.get("bid_deadline"),
            "opening_time": project.get("opening_time"),
        },
        "finance": {
            "budget": finance.get("budget"), "source": finance.get("source"),
        },
        "evaluation": {"method": evaluation.get("method")},
        "requirements": {
            "qualification": requirements.get("qualification"),
            "consortium": requirements.get("consortium"),
        },
        "keywords": meta.get("keywords") or [],
        "timeline": [
            {
                "label": t.get("label") or t.get("name") or "时间节点",
                "date": t.get("date") or t.get("value"),
                "summary": t.get("summary"),
            }
            for t in timeline if isinstance(t, dict)
        ],
        "suppliers": [
            {
                "supplier": s.get("supplier"), "supplier_company_id": s.get("supplier_company_id"),
                "amount": s.get("amount"), "address": s.get("address"),
            }
            for s in (meta.get("suppliers") or []) if isinstance(s, dict)
        ],
        "body": meta.get("body") or meta.get("content") or "",
        "review_comment": bn.review_comment,
        "reviewed_at": bn.reviewed_at.strftime("%Y-%m-%d %H:%M") if bn.reviewed_at else "",
        "publish_at": bn.publish_at.strftime("%Y-%m-%d %H:%M") if bn.publish_at else "",
    })
    return out


def _scope_cond(db: Session, user: dict):
    """数据范围过滤条件(复用 bids.py 同款逻辑)。"""
    from app.services.data_scope_service import resolve_scope, scope_filter
    scope = resolve_scope(db, user, "bid")
    return scope_filter(scope, BidNotice, "bid", user_id=user.get("user_id"))


def _apply_status(db: Session, bn: BidNotice, to_status: str, action: str,
                  user: dict, comment: Optional[str] = None) -> None:
    """状态转移 + 留痕。"""
    from_status = bn.status
    bn.status = to_status
    if to_status == BID_STATUS_PUBLISHED:
        bn.publish_at = datetime.datetime.now()
        bn.publish_by = user.get("user_id")
    if action == "submit":
        bn.submitted_by = user.get("user_id")
        bn.submitted_at = datetime.datetime.now()
    if action in ("approve", "reject"):
        bn.reviewed_by = user.get("user_id")
        bn.reviewed_at = datetime.datetime.now()
        bn.review_comment = comment
    _add_record(db, bn.id, action, user, comment, from_status, to_status)
    _audit(db, user, f"bid_{action}", bn, {"from_status": from_status, "to_status": to_status})


# =============================================================
# 静态路径优先(避免被 /{bid_id} 拦截)
# =============================================================
@router.get("/stats")
async def bid_stats(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """数据看板: 各状态计数 + 时间趋势 + 类型/行业/地域分布。"""
    base = select(BidNotice).where(BidNotice.is_deleted == False)  # noqa: E712
    cond = _scope_cond(db, user)
    if cond is not None:
        base = base.where(cond)

    status_rows = db.execute(
        select(BidNotice.status, func.count())
        .where(BidNotice.is_deleted == False)  # noqa: E712
        .group_by(BidNotice.status)
    ).all()
    status_map = {s or "draft": c for s, c in status_rows}
    total = sum(status_map.values())

    now = datetime.datetime.now()
    def _count_since(days: int) -> int:
        cutoff = now - datetime.timedelta(days=days)
        return db.execute(
            select(func.count())
            .where(
                BidNotice.is_deleted == False,  # noqa: E712
                BidNotice.created_at >= cutoff,
            )
        ).scalar() or 0

    def _top(column, limit: int = 10):
        rows = db.execute(
            select(column, func.count())
            .where(BidNotice.is_deleted == False, column.isnot(None))  # noqa: E712
            .group_by(column)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        return [{"name": r[0], "count": r[1]} for r in rows]

    return {
        "success": True,
        "data": {
            "total": total,
            "by_status": status_map,
            "today": _count_since(1),
            "last_7d": _count_since(7),
            "last_30d": _count_since(30),
            "type_dist": _top(BidNotice.notice_type),
            "industry_dist": _top(BidNotice.industry),
            "region_dist": _top(BidNotice.region),
        },
    }


@router.get("/review-queue")
async def review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_review")),
):
    """待审核队列(status=pending)。"""
    stmt = select(BidNotice).where(
        BidNotice.is_deleted == False,  # noqa: E712
        BidNotice.status == BID_STATUS_PENDING,
    )
    cond = _scope_cond(db, user)
    if cond is not None:
        stmt = stmt.where(cond)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(BidNotice.submitted_at.is_(None), BidNotice.submitted_at.desc(), BidNotice.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    counts = _interact_counts(db, [r.id for r in rows])
    items = []
    for r in rows:
        d = _bn_admin_dict(r)
        d["monitored"] = counts.get(r.id, {}).get("monitored", 0)
        d["collected"] = counts.get(r.id, {}).get("collected", 0)
        d["submitted_by"] = r.submitted_by
        d["submitted_at"] = r.submitted_at.strftime("%Y-%m-%d %H:%M") if r.submitted_at else ""
        items.append(d)
    return {"success": True, "total": total, "items": items}


@router.get("")
async def list_bids(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="标题模糊"),
    notice_type: Optional[str] = Query(None, description="公告类型"),
    category: Optional[str] = Query(None, description="项目分类"),
    industry: Optional[str] = Query(None, description="行业"),
    region: Optional[str] = Query(None, description="地区"),
    purchaser_keyword: Optional[str] = Query(None, description="采购人模糊"),
    status: Optional[str] = Query(None, description="生命周期状态"),
    matched: Optional[bool] = Query(None, description="只看已匹配单位"),
    date_from: Optional[str] = Query(None, description="发布时间起"),
    date_to: Optional[str] = Query(None, description="发布时间止"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """后台标讯列表(多条件筛选)。"""
    stmt = select(BidNotice).where(BidNotice.is_deleted == False)  # noqa: E712
    cond = _scope_cond(db, user)
    if cond is not None:
        stmt = stmt.where(cond)
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(keyword))
    if notice_type:
        stmt = stmt.where(BidNotice.notice_type.contains(notice_type))
    if category:
        stmt = stmt.where(BidNotice.category == category)
    if industry:
        stmt = stmt.where(BidNotice.industry == industry)
    if region:
        stmt = stmt.where(BidNotice.region.contains(region))
    if purchaser_keyword:
        stmt = stmt.where(BidNotice.purchaser.contains(purchaser_keyword))
    if status:
        stmt = stmt.where(BidNotice.status == status)
    if matched is not None:
        cond_match = or_(
            BidNotice.purchaser_company_id.isnot(None),
            BidNotice.meta.cast(str).contains("supplier_company_id"),
        )
        stmt = stmt.where(cond_match if matched else ~cond_match)
    if date_from:
        stmt = stmt.where(BidNotice.published_at >= date_from)
    if date_to:
        stmt = stmt.where(BidNotice.published_at < f"{date_to} 23:59:59")
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(BidNotice.published_at.is_(None), BidNotice.published_at.desc(), BidNotice.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    counts = _interact_counts(db, [r.id for r in rows])
    items = []
    for r in rows:
        d = _bn_admin_dict(r)
        d["monitored"] = counts.get(r.id, {}).get("monitored", 0)
        d["collected"] = counts.get(r.id, {}).get("collected", 0)
        items.append(d)
    return {"success": True, "total": total, "items": items}


# ────────────────────────────── 订阅管理 ──────────────────────────────
# 订阅任务(前台「我的订阅」落库数据)管理: 列表 / 启停 / 手动触发匹配
# 注意: 静态路径必须放在 /{bid_id} 参数路由之前, 避免被 int 校验拦截


@router.get("/subscriptions")
async def admin_list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="订阅名称/用户关键词"),
    product_type: Optional[str] = Query(None, description="tender/opportunity"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """订阅任务管理列表(含用户名)。"""
    from app.models.subscription_task import SubscriptionTask
    from app.models.rbac import SysUser
    stmt = select(SubscriptionTask, SysUser.username).join(
        SysUser, SysUser.id == SubscriptionTask.user_id
    ).where(SubscriptionTask.is_deleted == False)  # noqa: E712
    if keyword:
        stmt = stmt.where(or_(
            SubscriptionTask.name.contains(keyword),
            SysUser.username.contains(keyword),
        ))
    if product_type:
        stmt = stmt.where(SubscriptionTask.product_type == product_type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(SubscriptionTask.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = [{
        "id": t.id, "user_id": t.user_id, "username": username or "",
        "name": t.name, "condition_snapshot": t.condition_snapshot,
        "enabled": t.enabled, "product_type": t.product_type,
        "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
        "last_match_count": t.last_match_count,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    } for t, username in rows]
    return {"success": True, "total": total, "items": items}


@router.post("/subscriptions/{sub_id}/toggle")
async def admin_toggle_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_publish")),
):
    """启用/停用订阅任务。"""
    from app.models.subscription_task import SubscriptionTask
    task = db.execute(select(SubscriptionTask).where(
        SubscriptionTask.id == sub_id, SubscriptionTask.is_deleted == False  # noqa: E712
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="订阅不存在")
    task.enabled = not task.enabled
    db.commit()
    return {"success": True, "data": {"id": task.id, "enabled": task.enabled}}


@router.post("/subscriptions/{sub_id}/run")
async def admin_run_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_publish")),
):
    """手动触发订阅匹配(仅匹配已发布标讯, 返回匹配数)。"""
    from app.models.subscription_task import SubscriptionTask
    task = db.execute(select(SubscriptionTask).where(
        SubscriptionTask.id == sub_id, SubscriptionTask.is_deleted == False  # noqa: E712
    )).scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="订阅不存在")
    snapshot = task.condition_snapshot if isinstance(task.condition_snapshot, dict) else {}
    stmt = select(BidNotice).where(
        BidNotice.is_deleted == False,  # noqa: E712
        BidNotice.status == BID_STATUS_PUBLISHED,
    )
    keyword = str(snapshot.get("keyword") or "").strip()
    notice_type = str(snapshot.get("notice_type") or "").strip()
    province = str(snapshot.get("province") or "").strip()
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(keyword))
    if notice_type:
        stmt = stmt.where(BidNotice.notice_type.contains(notice_type))
    if province:
        stmt = stmt.where(BidNotice.region.contains(province))
    matched = db.execute(stmt.limit(100)).scalars().all()
    task.last_match_count = len(matched)
    task.last_run_at = datetime.datetime.now()
    db.commit()
    return {"success": True, "data": {"id": task.id, "matched": len(matched), "last_run_at": task.last_run_at}}


# ────────────────────────────── 用户互动明细 ──────────────────────────────
@router.get("/interactions")
async def list_interactions(
    action: Optional[str] = Query(None, description="monitor/collect"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """监控/收藏明细: 谁在关注哪些标讯。"""
    stmt = select(UserEntityAction, BidNotice.title, BidNotice.published_at).join(
        BidNotice, BidNotice.id == UserEntityAction.entity_id
    ).where(
        UserEntityAction.entity_type == "bid",
        UserEntityAction.is_deleted == False,  # noqa: E712
        BidNotice.is_deleted == False,  # noqa: E712
    )
    if action == "monitor":
        stmt = stmt.where(UserEntityAction.monitored == True)  # noqa: E712
    elif action == "collect":
        stmt = stmt.where(UserEntityAction.collected == True)  # noqa: E712
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(UserEntityAction.updated_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for action_row, title, pub_at in rows:
        monitored = bool(action_row.monitored)
        collected = bool(action_row.collected)
        if action == "monitor" and not monitored:
            continue
        if action == "collect" and not collected:
            continue
        items.append({
            "id": action_row.id,
            "user_id": action_row.user_id,
            "bid_id": action_row.entity_id,
            "title": title,
            "published_at": pub_at.strftime("%Y-%m-%d") if pub_at else "",
            "monitored": monitored,
            "collected": collected,
            "updated_at": action_row.updated_at.strftime("%Y-%m-%d %H:%M") if action_row.updated_at else "",
        })
    return {"success": True, "total": total, "items": items}


# ────────────────────────────── CSV 导出 ──────────────────────────────
def _csv_cell(v) -> str:
    s = "" if v is None else str(v).replace("\r", " ").replace("\n", " ").strip()
    if any(c in s for c in (",", '"', "\u200b")):
        return f'"{s.replace(chr(34), chr(34) * 2)}"'
    return s


@router.get("/export")
async def export_bids(
    keyword: Optional[str] = Query(None),
    notice_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """标讯列表 CSV 导出(与后台筛选字段对齐)。"""
    stmt = select(BidNotice).where(BidNotice.is_deleted == False)  # noqa: E712
    cond = _scope_cond(db, user)
    if cond is not None:
        stmt = stmt.where(cond)
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(keyword))
    if notice_type:
        stmt = stmt.where(BidNotice.notice_type.contains(notice_type))
    if category:
        stmt = stmt.where(BidNotice.category == category)
    if industry:
        stmt = stmt.where(BidNotice.industry == industry)
    if region:
        stmt = stmt.where(BidNotice.region.contains(region))
    if status:
        stmt = stmt.where(BidNotice.status == status)
    if date_from:
        stmt = stmt.where(BidNotice.published_at >= date_from)
    if date_to:
        stmt = stmt.where(BidNotice.published_at < f"{date_to} 23:59:59")
    rows = db.execute(
        stmt.order_by(BidNotice.published_at.is_(None), BidNotice.published_at.desc(), BidNotice.id.desc())
        .limit(limit)
    ).scalars().all()

    header = ["ID", "标题", "公告类型", "分类", "行业", "地区", "招标单位",
              "招标代理", "采购方式", "预算下限(万)", "预算上限(万)", "发布时间", "状态"]
    status_cn = {"draft": "草稿", "pending": "待审核", "approved": "已通过",
                 "rejected": "已驳回", "published": "已发布", "offline": "已下架"}
    body = [
        ",".join([
            _csv_cell(r.id), _csv_cell(r.title), _csv_cell(r.notice_type),
            _csv_cell(r.category), _csv_cell(r.industry), _csv_cell(r.region),
            _csv_cell(r.purchaser), _csv_cell(r.agency), _csv_cell(r.purchase_way),
            _csv_cell(r.budget_min), _csv_cell(r.budget_max),
            _csv_cell(r.published_at.strftime("%Y-%m-%d") if r.published_at else ""),
            _csv_cell(status_cn.get(r.status, r.status)),
        ])
        for r in rows
    ]
    csv_text = "\uFEFF" + ",".join(header) + "\r\n" + "\r\n".join(body)
    filename = f"bid_export_{datetime.date.today().isoformat()}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ────────────────────────────── 从线索导入 ──────────────────────────────


@router.post("/import-from-clues")
async def admin_import_from_clues(
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_create")),
):
    """从已接受线索(web_clue.status=accepted)批量生成标讯草稿。

    请求: {clue_ids: [..]} 或 {source_id: int} 或 {} 全部已接受线索。
    按 title 去重(已存在的跳过), 生成草稿并落审核流水; 生成后线索置为 imported。
    """
    from app.models.web_clue import WebClue
    clue_ids = payload.get("clue_ids")
    source_id = payload.get("source_id")
    stmt = select(WebClue).where(
        WebClue.is_deleted == False,  # noqa: E712
        WebClue.status == "accepted",
    )
    if clue_ids:
        stmt = stmt.where(WebClue.id.in_(clue_ids))
    elif source_id:
        stmt = stmt.where(WebClue.source_id == source_id)
    clues = db.execute(stmt.limit(500)).scalars().all()
    imported = skipped = 0
    for c in clues:
        exists = db.execute(select(func.count(BidNotice.id)).where(
            BidNotice.title == c.title, BidNotice.is_deleted == False  # noqa: E712
        )).scalar() or 0
        if exists:
            skipped += 1
            continue
        meta = c.meta if isinstance(c.meta, dict) else {}
        bn = BidNotice(
            clue_id=c.id,
            title=c.title,
            url=c.url,
            purchaser=meta.get("purchaser") or None,
            region=c.region or meta.get("regionName") or None,
            notice_type="招标",
            source_name=c.source_name or None,
            published_at=c.published_at,
            meta=meta,
            status=BID_STATUS_DRAFT,
            created_by=user.get("user_id"),
            updated_by=user.get("user_id"),
        )
        db.add(bn)
        db.flush()
        _add_record(db, bn.id, "create", user, to_status=BID_STATUS_DRAFT)
        c.status = "imported"
        imported += 1
    db.commit()
    return {"success": True, "data": {"imported": imported, "skipped": skipped}}


@router.get("/unmatched")
async def list_unmatched(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, description="采购人/供应商名称模糊"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_match")),
):
    """未匹配实体列表: 采购人未匹配 或 供应商未匹配的标讯。"""
    stmt = select(BidNotice).where(BidNotice.is_deleted == False)  # noqa: E712
    stmt = stmt.where(
        or_(
            BidNotice.purchaser_company_id.is_(None),
            BidNotice.meta.isnot(None),
        )
    )
    if keyword:
        stmt = stmt.where(or_(
            BidNotice.purchaser.contains(keyword),
            BidNotice.title.contains(keyword),
        ))
    rows = db.execute(
        stmt.order_by(BidNotice.published_at.is_(None), BidNotice.published_at.desc(), BidNotice.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    items = []
    for bn in rows:
        meta = _get_meta(bn)
        suppliers = [s for s in (meta.get("suppliers") or []) if isinstance(s, dict) and s.get("supplier")]
        unmatched_suppliers = [s.get("supplier") for s in suppliers if not s.get("supplier_company_id")]
        purchaser_unmatched = not bn.purchaser_company_id
        if not purchaser_unmatched and not unmatched_suppliers:
            continue
        items.append({
            "id": bn.id,
            "title": bn.title,
            "purchaser": bn.purchaser,
            "purchaser_company_id": bn.purchaser_company_id,
            "agency": bn.agency,
            "region": bn.region,
            "notice_type": bn.notice_type,
            "purchaser_unmatched": purchaser_unmatched,
            "unmatched_suppliers": unmatched_suppliers,
        })
    return {"success": True, "items": items}


@router.post("/match/auto")
async def auto_match_entities(
    payload: Optional[dict] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_match")),
):
    """全量自动名称匹配(精确匹配 company.name, 不创建新实体)。"""
    from app.services.real_project_import import _find_company

    bid_ids = (payload or {}).get("bid_ids") or None
    stmt = select(BidNotice).where(
        BidNotice.is_deleted == False,  # noqa: E712
        BidNotice.purchaser_company_id.is_(None),
    )
    if bid_ids:
        stmt = stmt.where(BidNotice.id.in_([int(x) for x in bid_ids]))
    bids = db.execute(stmt.limit(300)).scalars().all()
    matched = 0
    for bn in bids:
        if not bn.purchaser:
            continue
        company = _find_company(db, bn.purchaser)
        if company:
            bn.purchaser_company_id = company.id
            matched += 1
    db.flush()
    log_action(db, user.get("user_id"), user.get("username") or user.get("display_name"),
               "bid_match_auto", "bid", 0, f"auto matched {matched} / {len(bids)}")
    db.commit()
    return {"success": True, "data": {"scanned": len(bids), "matched": matched}}


@router.get("/{bid_id}")
async def get_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """后台标讯详情(编辑表单回显)。"""
    bn = _get_bid_or_404(db, bid_id)
    data = _bn_admin_detail(bn)
    counts = _interact_counts(db, [bid_id])
    data["monitored"] = counts.get(bid_id, {}).get("monitored", 0)
    data["collected"] = counts.get(bid_id, {}).get("collected", 0)
    # 审核历史
    recs = db.execute(
        select(BidReviewRecord).where(BidReviewRecord.bid_id == bid_id)
        .order_by(BidReviewRecord.id.desc())
    ).scalars().all()
    data["review_history"] = [
        {
            "action": r.action, "reviewer_name": r.reviewer_name,
            "comment": r.comment, "from_status": r.from_status, "to_status": r.to_status,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        }
        for r in recs
    ]
    return {"success": True, "data": data}


@router.get("/{bid_id}/review-history")
async def bid_review_history(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_review")),
):
    """标讯审核流水(独立查询入口)。"""
    _get_bid_or_404(db, bid_id)
    recs = db.execute(
        select(BidReviewRecord).where(BidReviewRecord.bid_id == bid_id)
        .order_by(BidReviewRecord.id.desc())
    ).scalars().all()
    return {
        "success": True,
        "items": [
            {
                "id": r.id, "action": r.action, "reviewer_name": r.reviewer_name,
                "comment": r.comment, "from_status": r.from_status, "to_status": r.to_status,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
            }
            for r in recs
        ],
    }


# =============================================================
# 写操作
# =============================================================
@router.post("")
async def create_bid(
    payload: BidCreatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_create")),
):
    """录入标讯(默认草稿, 走审核流程)。"""
    data = payload.model_dump(exclude_unset=True)
    bn = BidNotice(
        status=BID_STATUS_DRAFT,
        created_by=user.get("user_id"),
        updated_by=user.get("user_id"),
    )
    _merge_payload(bn, data)
    db.add(bn)
    db.flush()
    _audit(db, user, "bid_create", bn)
    db.commit()
    db.refresh(bn)
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.put("/{bid_id}")
async def update_bid(
    bid_id: int,
    payload: BidUpdatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_edit")),
):
    """编辑标讯。已发布/下架 → 回草稿重新走审核。"""
    bn = _get_bid_or_404(db, bid_id)
    old = {
        "title": bn.title, "purchaser": bn.purchaser,
        "notice_type": bn.notice_type, "region": bn.region,
        "status": bn.status,
    }
    data = payload.model_dump(exclude_unset=True)
    _merge_payload(bn, data)
    if bn.status in (BID_STATUS_PUBLISHED, BID_STATUS_OFFLINE):
        bn.status = BID_STATUS_DRAFT
    bn.updated_by = user.get("user_id")
    changes = []
    labels = {"title": "标题", "purchaser": "招标单位", "notice_type": "公告类型", "region": "地区"}
    for key, label in labels.items():
        new_val = getattr(bn, key)
        if old.get(key) != new_val:
            changes.append({"field_key": key, "field_label": label,
                            "old_value": old.get(key), "new_value": new_val})
    if changes:
        track_field_changes(db, "bid", bn.id, user.get("user_id"), changes)
    _audit(db, user, "bid_update", bn, {"status_changed": old["status"] != bn.status})
    db.commit()
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.delete("/{bid_id}")
async def delete_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_edit")),
):
    """软删除标讯。"""
    bn = _get_bid_or_404(db, bid_id)
    bn.is_deleted = True
    _add_record(db, bn.id, "delete", user, None, bn.status, "deleted")
    _audit(db, user, "bid_delete", bn)
    db.commit()
    return {"success": True}


# ── 状态机操作 ──
@router.post("/{bid_id}/submit")
async def submit_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_edit")),
):
    """提交审核: draft/rejected → pending。"""
    bn = _get_bid_or_404(db, bid_id)
    if bn.status not in (BID_STATUS_DRAFT, BID_STATUS_REJECTED):
        raise HTTPException(status_code=400, detail=f"当前状态 {bn.status} 不可提交审核")
    if not bn.title or not bn.notice_type:
        raise HTTPException(status_code=422, detail="标题与公告类型为必填, 请先补全")
    _apply_status(db, bn, BID_STATUS_PENDING, "submit", user)
    db.commit()
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.post("/{bid_id}/review")
async def review_bid(
    bid_id: int,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_review")),
):
    """审核: pending → approved / rejected。"""
    bn = _get_bid_or_404(db, bid_id)
    if bn.status != BID_STATUS_PENDING:
        raise HTTPException(status_code=400, detail=f"当前状态 {bn.status} 不可审核")
    to_status = BID_STATUS_APPROVED if payload.approve else BID_STATUS_REJECTED
    _apply_status(db, bn, to_status, "approve" if payload.approve else "reject",
                  user, payload.comment)
    db.commit()
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.post("/{bid_id}/publish")
async def publish_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_publish")),
):
    """发布: approved(或草稿/待审核, 兼容直接发布路径) → published。"""
    bn = _get_bid_or_404(db, bid_id)
    if bn.status not in _DIRECT_PUBLISHABLE:
        raise HTTPException(status_code=400, detail=f"当前状态 {bn.status} 不可发布")
    _apply_status(db, bn, BID_STATUS_PUBLISHED, "publish", user)
    db.commit()
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.post("/{bid_id}/offline")
async def offline_bid(
    bid_id: int,
    payload: OfflinePayload | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_publish")),
):
    """下架: published → offline。"""
    bn = _get_bid_or_404(db, bid_id)
    if bn.status != BID_STATUS_PUBLISHED:
        raise HTTPException(status_code=400, detail=f"当前状态 {bn.status} 不可下架")
    _apply_status(db, bn, BID_STATUS_OFFLINE, "offline", user,
                  payload.reason if payload else None)
    db.commit()
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.post("/{bid_id}/restore")
async def restore_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_publish")),
):
    """恢复上线: offline → published。"""
    bn = _get_bid_or_404(db, bid_id)
    if bn.status != BID_STATUS_OFFLINE:
        raise HTTPException(status_code=400, detail=f"当前状态 {bn.status} 不可恢复")
    _apply_status(db, bn, BID_STATUS_PUBLISHED, "restore", user)
    db.commit()
    return {"success": True, "data": {"id": bn.id, "status": bn.status}}


@router.post("/batch")
async def batch_bids(
    payload: BatchPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_edit")),
):
    """批量操作: delete/publish/offline/submit。"""
    action = payload.action
    allowed = {"delete", "publish", "offline", "submit"}
    if action not in allowed:
        raise HTTPException(status_code=422, detail=f"action 必须是 {'/'.join(allowed)}")
    affected = 0
    for bid_id in payload.ids:
        bn = db.get(BidNotice, bid_id)
        if not bn or bn.is_deleted:
            continue
        if action == "delete":
            bn.is_deleted = True
            _add_record(db, bn.id, "delete", user, None, bn.status, "deleted")
            affected += 1
        elif action == "submit" and bn.status in (BID_STATUS_DRAFT, BID_STATUS_REJECTED):
            _apply_status(db, bn, BID_STATUS_PENDING, "submit", user)
            affected += 1
        elif action == "publish" and bn.status in _DIRECT_PUBLISHABLE:
            _apply_status(db, bn, BID_STATUS_PUBLISHED, "publish", user)
            affected += 1
        elif action == "offline" and bn.status == BID_STATUS_PUBLISHED:
            _apply_status(db, bn, BID_STATUS_OFFLINE, "offline", user)
            affected += 1
    db.commit()
    return {"success": True, "data": {"affected": affected}}


# =============================================================
# 实体匹配(采购人/供应商 → company)
# =============================================================
@router.post("/{bid_id}/match")
async def match_entities(
    bid_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_match")),
):
    """确认实体匹配: {purchaser_company_id?, suppliers: [{supplier, company_id}]}。"""
    bn = _get_bid_or_404(db, bid_id)
    meta = _get_meta(bn)
    if payload.get("purchaser_company_id") is not None:
        bn.purchaser_company_id = payload["purchaser_company_id"]
    new_suppliers = []
    for s in (payload.get("suppliers") or []):
        new_suppliers.append({
            "supplier": s.get("supplier"),
            "supplier_company_id": s.get("company_id"),
            "amount": s.get("amount"),
            "address": s.get("address"),
        })
    if new_suppliers:
        meta["suppliers"] = new_suppliers
        bn.meta = meta
    _audit(db, user, "bid_match", bn, {"purchaser_company_id": bn.purchaser_company_id,
                                        "suppliers": len(new_suppliers)})
    db.commit()
    return {"success": True, "data": {"id": bn.id, "purchaser_company_id": bn.purchaser_company_id}}


# =============================================================
# 标讯标签(单条打标)
# =============================================================
@router.get("/{bid_id}/tags")
async def get_bid_tags(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_view")),
):
    """查询标讯已打的标签。"""
    from app.models.bid_tag import BidTagDef, BidNoticeTag
    rows = db.execute(
        select(BidTagDef)
        .join(BidNoticeTag, BidNoticeTag.tag_id == BidTagDef.id)
        .where(BidNoticeTag.bid_id == bid_id, BidTagDef.is_deleted == False)  # noqa: E712
        .order_by(BidTagDef.sort_order, BidTagDef.id.desc())
    ).scalars().all()
    return {"success": True, "items": [
        {"id": t.id, "label": t.label, "kind": t.kind, "sort_order": t.sort_order} for t in rows
    ]}


@router.post("/{bid_id}/tags")
async def apply_bid_tags(
    bid_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("bid_tag_manage")),
):
    """全量设置标讯标签: {tag_ids: []} 覆盖旧关联。"""
    from app.models.bid_tag import BidTagDef, BidNoticeTag
    bn = _get_bid_or_404(db, bid_id)
    tag_ids = [int(x) for x in (payload.get("tag_ids") or [])]
    if tag_ids:
        existing = set(db.execute(
            select(BidTagDef.id).where(BidTagDef.id.in_(tag_ids), BidTagDef.is_deleted == False)  # noqa: E712
        ).scalars().all())
        tag_ids = [x for x in tag_ids if x in existing]
    db.execute(BidNoticeTag.__table__.delete().where(BidNoticeTag.bid_id == bid_id))
    for tag_id in dict.fromkeys(tag_ids):
        db.add(BidNoticeTag(bid_id=bid_id, tag_id=tag_id, created_by=user.get("user_id")))
    db.flush()
    _audit(db, user, "bid_tag_apply", bn, {"tag_ids": tag_ids})
    db.commit()
    return {"success": True, "data": {"tag_ids": tag_ids}}
