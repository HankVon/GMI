"""情报中心后台管理 API — 意向情报的录入/编辑/审核/发布/下架 + 分类/联系人/附件/AI研判管理。

权限说明:
  - 读取类接口: 登录即可(get_current_user)
  - 写操作类接口: 需拥有 menu_intel_intents 或 intel_intelligence_* 任一权限(兼容老角色)
  - 权限种子见 sql/017_intent_admin.sql (新权限点注册 + admin 角色全量挂载)

与前台公开接口(/public/intelligence)契约匹配:
  - 前台只返回 wf_status='published'(兼容历史 NULL) 的数据
  - 后台返回全部 wf_status(含草稿/待审核/已下架)
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.intent_notice import IntentNotice
from app.models.intent_attachment import IntentAttachment
from app.models.intent_ai_cache import IntentAiCache
from app.models.intent_contact import IntentContact
from app.models.intelligence_category import IntelligenceCategory
from app.models.web_source import WebSource
from app.models.opportunity import Opportunity
from app.config import settings
from app.utils.upload_paths import upload_root
from app.services.intent_quality import apply_quality, can_publish, quality_of

# 情报中心后台访问权限: 拥有任一情报/数据源/看板菜单权限即可访问(读写统一门槛)。
# 兼容老角色保底 menu_intel_intents, 新权限点 intel_intelligence_* 亦覆盖。
_INTEL_ACCESS_PERMS = (
    "menu_intel_intents",        # 情报管理(老角色保底)
    "menu_workspace_web_clues",  # 数据源中心
    "menu_dashboard",            # 情报看板
    "intel_intelligence_view",   # 情报查看
    "intel_intelligence_edit",   # 情报编辑
    "intel_intelligence_create", # 情报录入
)


def _require_intel_access(user: dict = Depends(get_current_user)) -> dict:
    perms = set(user.get("permissions", []))
    if not perms.intersection(_INTEL_ACCESS_PERMS):
        raise HTTPException(status_code=403, detail="无情报中心后台权限")
    return user


router = APIRouter(
    prefix="/admin/intelligence",
    tags=["情报中心后台管理"],
    dependencies=[Depends(_require_intel_access)],
)

# 意向写操作兼容权限(新权限点 seed 后亦生效; 老角色保底 menu_intel_intents)
_INTEL_WRITE_PERMS = ("menu_intel_intents", "intel_intelligence_edit", "intel_intelligence_create")


def _require_intel_op(user: dict) -> dict:
    perms = set(user.get("permissions", []))
    if not perms.intersection(_INTEL_WRITE_PERMS):
        raise HTTPException(status_code=403, detail="无情报管理权限")
    return user


_WF_LABELS = {
    "draft": "草稿", "pending": "待审核", "approved": "审核通过",
    "published": "已发布", "offline": "已下架", "rejected": "已驳回",
}


def _can_contact(user: dict) -> bool:
    """是否可查看真实联系方式(字段级权限: intel_contact_view 或情报管理员)。"""
    perms = set(user.get("permissions", []))
    return bool(perms & {"intel_contact_view", "menu_intel_admin", "menu_intel_intents"})


def _parse_matched(raw: Optional[str]):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


def _src_map(db: Session, ids: set[int]) -> dict:
    if not ids:
        return {}
    rows = db.execute(select(WebSource).where(WebSource.id.in_(ids))).scalars().all()
    return {r.id: r.name for r in rows}


def _it_vo(it: IntentNotice, src_name: str = "", can_contact: bool = True) -> dict:
    """后台管理列表/详情序列化(返回真实数据, 供后台管理界面)。

    can_contact=False 时(用户无 intel_contact_view 权限)联系方式与业主匹配信息脱敏。
    """
    attrs = it.ext_attrs if isinstance(it.ext_attrs, dict) else {}
    return {
        "id": it.id,
        "title": it.title,
        "url": it.url,
        "dept": it.dept,
        "project_type": it.project_type,
        "industry": it.industry,
        "amount": float(it.amount) if it.amount is not None else None,
        "region": it.region,
        "province": it.province,
        "city": it.city,
        "county": it.county,
        "contact": it.contact if can_contact else ("***" if it.contact else None),
        "start_date": str(it.start_date) if it.start_date else None,
        "published_at": str(it.published_at) if it.published_at else None,
        "status": it.status,
        "wf_status": it.wf_status,
        "wf_label": _WF_LABELS.get(it.wf_status, it.wf_status),
        "review_comment": it.review_comment,
        "reviewer_id": it.reviewer_id,
        "reviewed_at": str(it.reviewed_at) if it.reviewed_at else None,
        "publisher_id": it.publisher_id,
        "offline_at": str(it.offline_at) if it.offline_at else None,
        "stage": it.stage,
        "dataset_type": it.dataset_type,
        "ext_attrs": attrs,
        "keywords": (it.keywords or "").split(",") if it.keywords else [],
        "matched_entity": _parse_matched(it.matched_entity) if can_contact else None,
        "raw_text": it.raw_text or "",
        "source_name": src_name,
        "created_by": it.created_by,
        "created_at": str(it.created_at) if it.created_at else None,
        "updated_at": str(it.updated_at) if it.updated_at else None,
        # 字段体检(完整度 + 缺什么, 供后台审核与批量发布把关)
        "quality": quality_of(it),
        # 商机联动
        "opp_id": None,
        "opp_version": None,
    }


# ─────────────────────────────────────────────────────────
# 情报 CRUD
# ─────────────────────────────────────────────────────────
@router.get("/list")
async def admin_intent_list(
    keyword: Optional[str] = Query(None, description="标题/部门/业主 模糊"),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    industry: Optional[str] = Query(None, description="行业"),
    project_type: Optional[str] = Query(None),
    stage: Optional[str] = Query(None, description="项目阶段"),
    wf_status: Optional[str] = Query(None, description="流转状态 draft/pending/approved/published/offline/rejected"),
    status: Optional[str] = Query(None, description="业务状态 new/qualified/skip/expired"),
    dataset_type: Optional[str] = Query(None, description="数据集 project/proposed/landTrade"),
    quality_level: Optional[str] = Query(None, description="字段体检等级 ok/warn/poor"),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None, description="发布日期起 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="发布日期止 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(IntentNotice).where(IntentNotice.is_deleted == False)
    if keyword:
        stmt = stmt.where(or_(
            IntentNotice.title.contains(keyword),
            IntentNotice.dept.contains(keyword),
        ))
    if province:
        stmt = stmt.where(IntentNotice.province == province)
    if city:
        stmt = stmt.where(IntentNotice.city == city)
    if county:
        stmt = stmt.where(IntentNotice.county == county)
    if industry:
        stmt = stmt.where(IntentNotice.industry == industry)
    if project_type:
        stmt = stmt.where(IntentNotice.project_type == project_type)
    if stage:
        stmt = stmt.where(IntentNotice.stage == stage)
    if wf_status:
        stmt = stmt.where(IntentNotice.wf_status == wf_status)
    if status:
        stmt = stmt.where(IntentNotice.status == status)
    if dataset_type:
        stmt = stmt.where(IntentNotice.dataset_type == dataset_type)
    if quality_level:
        # 体检等级存于 ext_attrs.quality.level(JSON), 用 JSON 表达式下推到 SQL 保证分页准确
        # (未跑过体检的历史数据无该键, 不会被 poor/warn 命中, 需先执行「批量重检」)
        try:
            stmt = stmt.where(
                IntentNotice.ext_attrs["quality"]["level"].as_string() == quality_level
            )
        except Exception:  # noqa: BLE001 - 数据库不支持 JSON 函数时降级为不过滤
            pass
    if min_amount is not None:
        stmt = stmt.where(IntentNotice.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(IntentNotice.amount <= max_amount)
    if date_from:
        try:
            stmt = stmt.where(IntentNotice.published_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            stmt = stmt.where(IntentNotice.published_at <= datetime.strptime(date_to, "%Y-%m-%d"))
        except ValueError:
            pass

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(IntentNotice.updated_at.desc(), IntentNotice.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    src_map = _src_map(db, {r.source_id for r in rows if r.source_id})
    # 商机联动(发布后)
    opp_map: dict[int, dict] = {}
    if rows:
        for o in db.execute(
            select(Opportunity).where(
                Opportunity.source.in_([f"intent-notice-{r.id}" for r in rows])
            )
        ).scalars().all():
            try:
                iid = int(str(o.source).rsplit("-", 1)[-1])
            except (ValueError, AttributeError):
                continue
            opp_map[iid] = {"opp_id": o.id, "opp_version": o.current_version}

    items = []
    cc = _can_contact(user)
    for r in rows:
        vo = _it_vo(r, src_map.get(r.source_id, ""), cc)
        link = opp_map.get(r.id)
        if link:
            vo["opp_id"] = link["opp_id"]
            vo["opp_version"] = link["opp_version"]
        items.append(vo)
    return {"success": True, "total": total, "items": items}


@router.get("/review-queue")
async def admin_review_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """待审核队列: 优先待审核, 其次驳回/草稿(便于连续处理)。"""
    stmt = select(IntentNotice).where(
        IntentNotice.is_deleted == False,
        IntentNotice.wf_status.in_(["pending", "rejected"]),
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(
            IntentNotice.wf_status == "pending",  # pending 优先
            IntentNotice.updated_at.desc(),
        ).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    src_map = _src_map(db, {r.source_id for r in rows if r.source_id})
    cc = _can_contact(user)
    items = [_it_vo(r, src_map.get(r.source_id, ""), cc) for r in rows]
    return {"success": True, "total": total, "items": items}


@router.get("/stats")
async def admin_intent_stats(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """情报中心看板统计: 按流转状态 + 行业/地域 Top。"""
    base = select(IntentNotice).where(IntentNotice.is_deleted == False)
    wf_rows = db.execute(
        select(IntentNotice.wf_status, func.count()).where(
            IntentNotice.is_deleted == False
        ).group_by(IntentNotice.wf_status)
    ).all()
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0
    industry_rows = db.execute(
        select(IntentNotice.industry, func.count()).where(
            IntentNotice.is_deleted == False, IntentNotice.industry.isnot(None)
        ).group_by(IntentNotice.industry).order_by(func.count().desc()).limit(10)
    ).all()
    region_rows = db.execute(
        select(IntentNotice.province, func.count()).where(
            IntentNotice.is_deleted == False, IntentNotice.province.isnot(None)
        ).group_by(IntentNotice.province).order_by(func.count().desc()).limit(10)
    ).all()
    # 近 12 个月发布趋势
    months: list[str] = []
    now = datetime.now()
    for i in range(11, -1, -1):
        months.append((now.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m"))
    from sqlalchemy import text as _text
    trend_rows = db.execute(_text(
        "SELECT DATE_FORMAT(published_at, '%Y-%m') AS m, COUNT(*) AS cnt "
        "FROM intent_notice WHERE is_deleted=0 AND published_at IS NOT NULL GROUP BY m"
    )).all()
    trend_map = {r[0]: int(r[1]) for r in trend_rows}
    monthly_trend = [{"month": m, "count": trend_map.get(m, 0)} for m in months]
    # 来源 Top(按 web_source)
    src_rows = db.execute(
        select(IntentNotice.source_id, func.count())
        .where(IntentNotice.is_deleted == False, IntentNotice.source_id.isnot(None))
        .group_by(IntentNotice.source_id).order_by(func.count().desc()).limit(10)
    ).all()
    src_map = _src_map(db, {r[0] for r in src_rows})
    source_top = [{"name": src_map.get(r[0], f"来源#{r[0]}"), "count": r[1]} for r in src_rows]
    # 联系人/附件统计
    contact_cnt = db.execute(
        select(func.count()).select_from(select(IntentContact.id).where(
            IntentContact.is_deleted == False).subquery())
    ).scalar() or 0
    return {
        "success": True,
        "total": total,
        "wf_status": {r[0]: r[1] for r in wf_rows},
        "industry_top": [{"name": r[0], "count": r[1]} for r in industry_rows],
        "region_top": [{"name": r[0], "count": r[1]} for r in region_rows],
        "monthly_trend": monthly_trend,
        "source_top": source_top,
        "contact_count": contact_cnt,
    }


@router.get("/{intent_id:int}")
async def admin_intent_detail(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    src_name = ""
    if it.source_id:
        src = db.get(WebSource, it.source_id)
        src_name = src.name if src else ""
    vo = _it_vo(it, src_name, _can_contact(user))
    opp = db.execute(
        select(Opportunity).where(Opportunity.source == f"intent-notice-{it.id}")
    ).scalar_one_or_none()
    if opp:
        vo["opp_id"] = opp.id
        vo["opp_version"] = opp.current_version
    return {"success": True, "data": vo}


class IntentCreatePayload(BaseModel):
    title: str = Field(..., min_length=2, max_length=512)
    url: Optional[str] = Field(None, max_length=1024)
    dept: Optional[str] = Field(None, max_length=256)
    project_type: Optional[str] = Field(None, max_length=128)
    industry: Optional[str] = Field(None, max_length=128)
    amount: Optional[float] = None
    region: Optional[str] = Field(None, max_length=128)
    province: Optional[str] = Field(None, max_length=64)
    city: Optional[str] = Field(None, max_length=64)
    county: Optional[str] = Field(None, max_length=64)
    contact: Optional[str] = Field(None, max_length=256)
    start_date: Optional[str] = None
    published_at: Optional[str] = None
    status: str = "new"
    keywords: Optional[list[str]] = None
    raw_text: Optional[str] = None
    stage: Optional[str] = Field(None, max_length=64)
    dataset_type: str = "project"
    ext_attrs: Optional[dict] = None


class IntentUpdatePayload(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=512)
    url: Optional[str] = Field(None, max_length=1024)
    dept: Optional[str] = Field(None, max_length=256)
    project_type: Optional[str] = Field(None, max_length=128)
    industry: Optional[str] = Field(None, max_length=128)
    amount: Optional[float] = None
    region: Optional[str] = Field(None, max_length=128)
    province: Optional[str] = Field(None, max_length=64)
    city: Optional[str] = Field(None, max_length=64)
    county: Optional[str] = Field(None, max_length=64)
    contact: Optional[str] = Field(None, max_length=256)
    start_date: Optional[str] = None
    published_at: Optional[str] = None
    status: Optional[str] = None
    keywords: Optional[list[str]] = None
    raw_text: Optional[str] = None
    stage: Optional[str] = Field(None, max_length=64)
    dataset_type: Optional[str] = None
    ext_attrs: Optional[dict] = None


def _apply_payload(it: IntentNotice, p: BaseModel) -> None:
    data = p.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in data.items():
        if k == "keywords" and isinstance(v, list):
            setattr(it, "keywords", ",".join(v))
        elif k == "ext_attrs":
            setattr(it, "ext_attrs", v if v else None)
        elif k in ("start_date", "published_at") and isinstance(v, str):
            try:
                setattr(it, k, datetime.strptime(v, "%Y-%m-%d"))
            except ValueError:
                setattr(it, k, None)
        elif k == "amount" and v is not None:
            it.amount = round(float(v), 2)
        else:
            setattr(it, k, v)


@router.post("")
async def admin_create_intent(
    payload: IntentCreatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = IntentNotice(
        title=payload.title,
        wf_status="draft",
        dataset_type=payload.dataset_type,
        created_by=user.get("user_id"),
    )
    _apply_payload(it, payload)
    db.add(it)
    db.commit()
    db.refresh(it)
    return {"success": True, "data": {"id": it.id, "wf_status": "draft"}}


@router.put("/{intent_id:int}")
async def admin_update_intent(
    intent_id: int,
    payload: IntentUpdatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    # 已发布内容被编辑 → 回草稿重新走审核
    if it.wf_status in ("published", "approved"):
        it.wf_status = "draft"
        it.review_comment = None
        it.reviewer_id = None
        it.reviewed_at = None
    _apply_payload(it, payload)
    db.commit()
    return {"success": True, "data": {"id": it.id, "wf_status": it.wf_status}}


@router.delete("/{intent_id:int}")
async def admin_delete_intent(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    it.is_deleted = True
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────────────────
# 字段体检 + 批量审核
# (批量路由 /batch/* 声明在 /{intent_id}/* 之前, 避免与路径参数路由混淆)
# ─────────────────────────────────────────────────────────
class BatchIdsPayload(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)


class BatchReviewPayload(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=500)
    approve: bool = True
    comment: Optional[str] = Field(None, max_length=512)


def _load_batch(db: Session, ids: list[int]) -> list[IntentNotice]:
    """按 id 批量取未删除的情报(去重, 保持传入顺序)。"""
    out: list[IntentNotice] = []
    seen: set[int] = set()
    for iid in ids:
        if iid in seen:
            continue
        seen.add(iid)
        it = db.get(IntentNotice, iid)
        if it and not it.is_deleted:
            out.append(it)
    return out


@router.post("/batch/recheck")
async def admin_batch_recheck(
    payload: BatchIdsPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """批量重跑字段体检(历史数据首次启用 / 调整规则后执行)。"""
    _require_intel_op(user)
    items = []
    for it in _load_batch(db, payload.ids):
        items.append({"id": it.id, "quality": apply_quality(it)})
    db.commit()
    return {"success": True, "message": f"已重检 {len(items)} 条", "data": {"items": items}}


class RecheckAllPayload(BaseModel):
    wf_status: Optional[str] = None
    limit: int = Field(2000, ge=1, le=20000)


@router.post("/batch/recheck-all")
async def admin_recheck_all(
    payload: RecheckAllPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """按条件全量重检(历史数据首次启用字段体检时执行)。

    存量情报入库时未做体检(无 ext_attrs.quality), 列表会显示"未检测", 且
    按 poor/warn 筛选不会命中。执行一次即可为存量数据补齐体检结果。
    """
    _require_intel_op(user)
    stmt = select(IntentNotice).where(IntentNotice.is_deleted == False)
    if payload.wf_status:
        stmt = stmt.where(IntentNotice.wf_status == payload.wf_status)
    rows = db.execute(stmt.order_by(IntentNotice.id.desc()).limit(payload.limit)).scalars().all()
    for it in rows:
        apply_quality(it)
    db.commit()
    return {"success": True, "message": f"已重检 {len(rows)} 条", "data": {"count": len(rows)}}


@router.post("/batch/submit")
async def admin_batch_submit(
    payload: BatchIdsPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """批量提交审核(仅 draft/rejected 可提交)。"""
    _require_intel_op(user)
    done: list[int] = []
    skipped: list[dict] = []
    for it in _load_batch(db, payload.ids):
        if it.wf_status not in ("draft", "rejected"):
            skipped.append({"id": it.id, "reason": f"当前状态({it.wf_status})不可提交"})
            continue
        it.wf_status = "pending"
        it.review_comment = None
        done.append(it.id)
    db.commit()
    return {"success": True, "message": f"已提交 {len(done)} 条, 跳过 {len(skipped)} 条",
            "data": {"done": done, "skipped": skipped}}


@router.post("/batch/review")
async def admin_batch_review(
    payload: BatchReviewPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """批量审核(通过/驳回), 仅 pending 状态可审核。驳回建议填原因。"""
    _require_intel_op(user)
    done: list[int] = []
    skipped: list[dict] = []
    for it in _load_batch(db, payload.ids):
        if it.wf_status != "pending":
            skipped.append({"id": it.id, "reason": f"当前状态({it.wf_status})不可审核"})
            continue
        it.wf_status = "approved" if payload.approve else "rejected"
        it.review_comment = payload.comment
        it.reviewer_id = user.get("user_id")
        it.reviewed_at = datetime.now()
        done.append(it.id)
    db.commit()
    return {"success": True, "message": f"已审核 {len(done)} 条, 跳过 {len(skipped)} 条",
            "data": {"done": done, "skipped": skipped}}


@router.post("/batch/publish")
async def admin_batch_publish(
    payload: BatchIdsPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """批量发布(带发布闸门)。

    核心必填缺失 → 跳过, 在 blocked 中给出需补字段; 仅缺加分项 → 放行,
    并在 published.missing_optional 返回缺失标签供前端提示。
    """
    _require_intel_op(user)
    published: list[dict] = []
    blocked: list[dict] = []
    for it in _load_batch(db, payload.ids):
        if it.wf_status != "approved":
            blocked.append({"id": it.id, "title": (it.title or "")[:40],
                            "reason": f"当前状态({it.wf_status})不可发布"})
            continue
        allow, reason, missing_opt = can_publish(it)
        if not allow:
            blocked.append({"id": it.id, "title": (it.title or "")[:40], "reason": reason})
            continue
        it.wf_status = "published"
        it.publisher_id = user.get("user_id")
        it.offline_at = None
        if it.published_at is None:
            it.published_at = datetime.now()
        published.append({"id": it.id, "title": (it.title or "")[:40],
                          "missing_optional": missing_opt})
    db.commit()
    # 商机联动(逐条, 内部自兜底, 失败不影响已发布结果)
    for p in published:
        it = db.get(IntentNotice, p["id"])
        if it:
            _sync_opportunity(db, it)
    return {"success": True, "message": f"已发布 {len(published)} 条, 跳过 {len(blocked)} 条",
            "data": {"published": published, "blocked": blocked}}


@router.post("/batch/reject")
async def admin_batch_reject(
    payload: BatchReviewPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """批量驳回(需填原因), 仅 pending 状态可驳回。"""
    _require_intel_op(user)
    done: list[int] = []
    skipped: list[dict] = []
    for it in _load_batch(db, payload.ids):
        if it.wf_status != "pending":
            skipped.append({"id": it.id, "reason": f"当前状态({it.wf_status})不可驳回"})
            continue
        it.wf_status = "rejected"
        it.review_comment = payload.comment
        it.reviewer_id = user.get("user_id")
        it.reviewed_at = datetime.now()
        done.append(it.id)
    db.commit()
    return {"success": True, "message": f"已驳回 {len(done)} 条, 跳过 {len(skipped)} 条",
            "data": {"done": done, "skipped": skipped}}


@router.post("/{intent_id}/recheck")
async def admin_recheck_intent(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单条重跑字段体检(编辑补全字段后刷新完整度)。"""
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    q = apply_quality(it)
    db.commit()
    return {"success": True, "data": q}


# ─────────────────────────────────────────────────────────
# 审核发布状态机
# ─────────────────────────────────────────────────────────
@router.post("/{intent_id}/submit")
async def admin_submit_intent(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    if it.wf_status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail=f"当前状态({it.wf_status})不可提交审核")
    it.wf_status = "pending"
    it.review_comment = None
    db.commit()
    return {"success": True, "data": {"id": it.id, "wf_status": "pending"}}


class ReviewPayload(BaseModel):
    approve: bool = True
    comment: Optional[str] = Field(None, max_length=512)


@router.post("/{intent_id}/review")
async def admin_review_intent(
    intent_id: int,
    payload: ReviewPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    if it.wf_status != "pending":
        raise HTTPException(status_code=400, detail="仅待审核状态可审核")
    it.wf_status = "approved" if payload.approve else "rejected"
    it.review_comment = payload.comment
    it.reviewer_id = user.get("user_id")
    it.reviewed_at = datetime.now()
    db.commit()
    return {"success": True, "data": {"id": it.id, "wf_status": it.wf_status}}


@router.post("/{intent_id}/publish")
async def admin_publish_intent(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    if it.wf_status != "approved":
        raise HTTPException(status_code=400, detail="仅审核通过状态可发布")
    # 发布闸门: 核心必填缺失 → 阻断; 仅缺加分项 → 放行并在返回中提示缺失标签
    allow, reason, missing_opt = can_publish(it)
    if not allow:
        raise HTTPException(status_code=400, detail=reason)
    it.wf_status = "published"
    it.publisher_id = user.get("user_id")
    it.offline_at = None
    if it.published_at is None:
        it.published_at = datetime.now()
    db.commit()
    _sync_opportunity(db, it)
    return {"success": True, "data": {"id": it.id, "wf_status": "published",
                                      "missing_optional": missing_opt}}


@router.post("/{intent_id}/offline")
async def admin_offline_intent(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    if it.wf_status != "published":
        raise HTTPException(status_code=400, detail="仅已发布状态可下架")
    it.wf_status = "offline"
    it.offline_at = datetime.now()
    db.commit()
    return {"success": True, "data": {"id": it.id, "wf_status": "offline"}}


@router.post("/{intent_id}/restore")
async def admin_restore_intent(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    if it.wf_status != "offline":
        raise HTTPException(status_code=400, detail="仅已下架状态可恢复")
    # 恢复等同重新发布, 同样过发布闸门
    allow, reason, missing_opt = can_publish(it)
    if not allow:
        raise HTTPException(status_code=400, detail=reason)
    it.wf_status = "published"
    it.offline_at = None
    db.commit()
    _sync_opportunity(db, it)
    return {"success": True, "data": {"id": it.id, "wf_status": "published",
                                      "missing_optional": missing_opt}}


def _bump_version(current: Optional[str]) -> str:
    """商机版本号升级: V1.0 → V1.1 → V1.2 ...(小版本 +0.1)。"""
    try:
        major, minor = (current or "V1.0").lstrip("V").split(".")
        return f"V{int(major)}.{int(minor) + 1}"
    except (ValueError, AttributeError):
        return "V1.1"


def _sync_opportunity(db: Session, it: IntentNotice) -> None:
    """发布/恢复时联动商机表: 已建档则更新并记版本快照, 未建档则创建(V1.0)。"""
    from app.models.opportunity_version import OpportunityVersion
    try:
        src = f"intent-notice-{it.id}"
        opp = db.execute(
            select(Opportunity).where(Opportunity.source == src)
        ).scalar_one_or_none()
        if opp is None:
            opp = Opportunity(
                project_name=it.title or f"意向#{it.id}",
                owner_name=it.dept or "待确认业主",
                amount_wan=int(float(it.amount)) if it.amount is not None else None,
                stage=it.stage,
                region_province=it.province,
                region_city=it.city,
                project_type=it.project_type,
                body_excerpt=(it.raw_text or "")[:2000] or None,
                dataset_type=it.dataset_type,
                source=src,
                current_version="V1.0",
                published_at=datetime.now(),
            )
            db.add(opp)
            db.flush()  # 取 opp.id
            db.add(OpportunityVersion(
                opportunity_id=opp.id, version="V1.0",
                change_summary=f"情报发布建档: {it.title}",
                operator="系统", released_at=datetime.now(),
            ))
        else:
            # 记录旧快照(变更前)
            db.add(OpportunityVersion(
                opportunity_id=opp.id,
                version=opp.current_version or "V1.0",
                change_summary=f"更新前快照(情报#{it.id}): "
                               f"标题「{opp.project_name or ''}」 金额 {opp.amount_wan or '-'}万 "
                               f"阶段 {opp.stage or '-'}",
                operator="系统", released_at=datetime.now(),
            ))
            opp.project_name = it.title or opp.project_name
            opp.owner_name = it.dept or opp.owner_name
            opp.amount_wan = int(float(it.amount)) if it.amount is not None else opp.amount_wan
            opp.stage = it.stage or opp.stage
            opp.region_province = it.province or opp.region_province
            opp.region_city = it.city or opp.region_city
            opp.project_type = it.project_type or opp.project_type
            opp.body_excerpt = (it.raw_text or "")[:2000] or opp.body_excerpt
            opp.current_version = _bump_version(opp.current_version)
            db.add(OpportunityVersion(
                opportunity_id=opp.id, version=opp.current_version,
                change_summary=f"情报更新发布(情报#{it.id}): 金额 {opp.amount_wan or '-'}万 阶段 {opp.stage or '-'}",
                operator="系统", released_at=datetime.now(),
            ))
        db.commit()
    except Exception:  # noqa: BLE001 - 商机联动失败不影响主流程
        db.rollback()


# ─────────────────────────────────────────────────────────
# 分类管理
# ─────────────────────────────────────────────────────────
@router.get("/categories")
async def admin_list_categories(
    category: Optional[str] = Query(None, description="industry/project_type/stage/dataset"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(IntelligenceCategory).where(IntelligenceCategory.is_deleted == False)
    if category:
        stmt = stmt.where(IntelligenceCategory.category == category)
    rows = db.execute(stmt.order_by(IntelligenceCategory.category, IntelligenceCategory.sort_order, IntelligenceCategory.id)).scalars().all()
    return {"success": True, "items": [
        {"id": r.id, "category": r.category, "code": r.code, "label": r.label,
         "parent_id": r.parent_id, "sort_order": r.sort_order, "enabled": r.enabled}
        for r in rows
    ]}


class CategoryPayload(BaseModel):
    category: str = Field(..., max_length=32)
    code: str = Field(..., max_length=64)
    label: str = Field(..., max_length=128)
    parent_id: Optional[int] = None
    sort_order: int = 0
    enabled: int = 1


@router.post("/categories")
async def admin_create_category(
    payload: CategoryPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    exists = db.execute(
        select(IntelligenceCategory.id).where(
            IntelligenceCategory.category == payload.category,
            IntelligenceCategory.code == payload.code,
            IntelligenceCategory.is_deleted == False,
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="该分类编码已存在")
    row = IntelligenceCategory(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": {"id": row.id}}


@router.put("/categories/{cat_id}")
async def admin_update_category(
    cat_id: int,
    payload: CategoryPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = db.get(IntelligenceCategory, cat_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="分类不存在")
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    db.commit()
    return {"success": True}


@router.delete("/categories/{cat_id}")
async def admin_delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = db.get(IntelligenceCategory, cat_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="分类不存在")
    row.is_deleted = True
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────────────────
# 联系人管理
# ─────────────────────────────────────────────────────────
@router.get("/{intent_id}/contacts")
async def admin_list_contacts(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rows = db.execute(
        select(IntentContact).where(
            IntentContact.intent_id == intent_id,
            IntentContact.is_deleted == False,
        ).order_by(IntentContact.group, IntentContact.sort_order, IntentContact.id)
    ).scalars().all()
    return {"success": True, "items": [
        {"id": r.id, "group": r.group, "name": r.name, "role": r.role,
         "department": r.department, "position": r.position, "phone": r.phone,
         "mobile": r.mobile, "address": r.address, "remark": r.remark,
         "sort_order": r.sort_order}
        for r in rows
    ]}


class ContactPayload(BaseModel):
    group: str = "甲方"
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    remark: Optional[str] = None
    sort_order: int = 0


@router.post("/{intent_id}/contacts")
async def admin_create_contact(
    intent_id: int,
    payload: ContactPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = IntentContact(intent_id=intent_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": {"id": row.id}}


@router.put("/contacts/{contact_id}")
async def admin_update_contact(
    contact_id: int,
    payload: ContactPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = db.get(IntentContact, contact_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="联系人不存在")
    for k, v in payload.model_dump().items():
        setattr(row, k, v)
    db.commit()
    return {"success": True}


@router.delete("/contacts/{contact_id}")
async def admin_delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = db.get(IntentContact, contact_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="联系人不存在")
    row.is_deleted = True
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────────────────
# 附件管理
# ─────────────────────────────────────────────────────────
@router.get("/{intent_id}/attachments")
async def admin_list_attachments(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rows = db.execute(
        select(IntentAttachment).where(
            IntentAttachment.intent_id == intent_id,
            IntentAttachment.is_deleted == False,
        ).order_by(IntentAttachment.id.desc())
    ).scalars().all()
    return {"success": True, "items": [
        {"id": r.id, "file_name": r.file_name, "local_path": r.local_path,
         "remote_url": r.remote_url, "file_size": r.file_size,
         "download_url": f"/api/v1/public/intent/{intent_id}/attachments/{r.id}/download",
         "preview_url": f"/api/v1/public/intent/{intent_id}/attachments/{r.id}/preview"}
        for r in rows
    ]}


_UPLOAD_BASE = upload_root() / "intent_attachments"


@router.post("/{intent_id}/attachments")
async def admin_upload_attachment(
    intent_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    fname = file.filename or f"file-{uuid.uuid4().hex[:8]}"
    size = 0
    try:
        save_dir = _UPLOAD_BASE / str(intent_id)
        save_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex[:10]}-{Path(fname).name}"
        target = save_dir / safe_name
        with target.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        size = target.stat().st_size
        rel_path = f"intent_attachments/{intent_id}/{safe_name}"
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"附件保存失败: {e}") from e
    finally:
        file.file.close()
    row = IntentAttachment(
        intent_id=intent_id, file_name=fname,
        local_path=rel_path, remote_url=None, file_size=size,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"success": True, "data": {"id": row.id, "file_name": fname, "file_size": size}}


@router.delete("/{intent_id}/attachments/{attachment_id}")
async def admin_delete_attachment(
    intent_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = db.execute(
        select(IntentAttachment).where(
            IntentAttachment.id == attachment_id,
            IntentAttachment.intent_id == intent_id,
            IntentAttachment.is_deleted == False,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="附件不存在")
    row.is_deleted = True
    db.commit()
    return {"success": True}


# ─────────────────────────────────────────────────────────
# AI 研判管理(后台版, 允许输出真实单位/人员名)
# ─────────────────────────────────────────────────────────
@router.post("/{intent_id}/ai")
async def admin_trigger_ai(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """触发后台 LLM 深度研判(登录态可展示真实单位/人员名), 结果落缓存供前台复用。"""
    it = db.get(IntentNotice, intent_id)
    if not it or it.is_deleted:
        raise HTTPException(status_code=404, detail="情报不存在")
    from app.api.v1.intent import _llm_intent_analysis_backend
    from app.models.business_network import TenderMatch

    rels = db.execute(
        select(TenderMatch).where(
            TenderMatch.intent_id == intent_id,
            TenderMatch.is_deleted == False,
            TenderMatch.is_expired == False,
        ).order_by(TenderMatch.score.desc())
    ).scalars().all()
    related = [{"entity_type": r.entity_type, "entity_id": r.entity_id,
                "entity_name": r.entity_name} for r in rels]
    analysis = await _llm_intent_analysis_backend(it, related)
    if analysis:
        data = {
            "source": "llm", "model": settings.OLLAMA_MODEL,
            "analysis": analysis,
            "note": "由本地大模型基于真实意向数据生成（后台授权环境，含真实单位/人员信息）。",
        }
    else:
        data = {
            "source": "rule",
            "analysis": {
                "summary": f"基于规则引擎的研判（{it.region or '当地'}{it.industry or '相关'}类意向）。",
                "heat": 55, "coop_prob": 50,
                "parties": [r["entity_name"] for r in related[:6]],
                "advice": [f"核实「{it.region or '当地'}」{it.industry or '相关'}类意向的决策链与业主单位。",
                           "通过平台人脉关系图谱定位可触达的桥接人。"],
            },
            "note": "本地大模型暂不可用，已回退至规则引擎分析。",
        }
    _save_ai_cache(db, intent_id, data)
    return {"success": True, "data": data}


@router.get("/{intent_id}/versions")
async def admin_get_opp_versions(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """商机版本历史(opportunity_version): 情报每次发布/更新产生的版本快照。"""
    from app.models.opportunity_version import OpportunityVersion
    opp = db.execute(
        select(Opportunity).where(Opportunity.source == f"intent-notice-{intent_id}")
    ).scalar_one_or_none()
    if not opp:
        return {"success": True, "items": []}
    rows = db.execute(
        select(OpportunityVersion).where(
            OpportunityVersion.opportunity_id == opp.id,
            OpportunityVersion.is_deleted == False,
        ).order_by(OpportunityVersion.released_at.desc(), OpportunityVersion.id.desc())
    ).scalars().all()
    return {"success": True, "items": [
        {"id": r.id, "version": r.version, "change_summary": r.change_summary,
         "operator": r.operator,
         "released_at": str(r.released_at) if r.released_at else None}
        for r in rows
    ]}


@router.get("/{intent_id}/ai")
async def admin_get_ai(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    row = db.execute(
        select(IntentAiCache).where(IntentAiCache.intent_id == intent_id)
    ).scalar_one_or_none()
    if not row or not row.analysis:
        return {"success": True, "found": False}
    try:
        analysis = json.loads(row.analysis)
    except Exception:  # noqa: BLE001
        return {"success": True, "found": False}
    return {"success": True, "found": True, "data": {
        "source": row.source, "model": row.model, "analysis": analysis,
        "note": row.note or "",
        "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M") if row.updated_at else None,
    }}


@router.delete("/{intent_id}/ai")
async def admin_clear_ai(
    intent_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    row = db.execute(
        select(IntentAiCache).where(IntentAiCache.intent_id == intent_id)
    ).scalar_one_or_none()
    if row:
        db.delete(row)
        db.commit()
    return {"success": True}


def _save_ai_cache(db: Session, intent_id: int, data: dict) -> None:
    """写入 AI 研判缓存(与前台公开接口共用 intent_ai_cache 表)。"""
    try:
        row = db.execute(
            select(IntentAiCache).where(IntentAiCache.intent_id == intent_id)
        ).scalar_one_or_none()
        payload = json.dumps(data.get("analysis"), ensure_ascii=False)
        if row is None:
            db.add(IntentAiCache(
                intent_id=intent_id,
                source=data.get("source", "llm"),
                model=data.get("model"),
                analysis=payload,
                note=data.get("note"),
            ))
        else:
            row.source = data.get("source", "llm")
            row.model = data.get("model")
            row.analysis = payload
            row.note = data.get("note")
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


# ─────────────────────────────────────────────────────────
# 来源管理(web_source) — 情报采集数据源 CRUD + 手动触发爬取
# ─────────────────────────────────────────────────────────
def _src_vo(s: WebSource) -> dict:
    return {
        "id": s.id, "name": s.name, "url": s.url, "description": s.description,
        "allow_domains": (s.allow_domains or "").split(",") if s.allow_domains else [],
        "keywords": (s.keywords or "").split(",") if s.keywords else [],
        "exclude_keywords": (s.exclude_keywords or "").split(",") if s.exclude_keywords else [],
        "regions": (s.regions or "").split(",") if s.regions else [],
        "scrape_mode": s.scrape_mode, "max_depth": s.max_depth, "max_pages": s.max_pages,
        "llm_enhance": s.llm_enhance, "enabled": s.enabled,
        "last_run_at": str(s.last_run_at) if s.last_run_at else None,
        "last_run_result": s.last_run_result,
        "last_error": s.last_error,
    }


@router.get("/sources")
async def admin_list_sources(
    enabled: Optional[bool] = Query(None, description="是否启用过滤"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    stmt = select(WebSource).where(WebSource.is_deleted == False)
    if enabled is not None:
        stmt = stmt.where(WebSource.enabled == enabled)
    rows = db.execute(stmt.order_by(WebSource.id.desc())).scalars().all()
    return {"success": True, "items": [_src_vo(r) for r in rows]}


class SourcePayload(BaseModel):
    name: str = Field(..., max_length=128)
    url: str = Field(..., max_length=1024)
    description: Optional[str] = Field(None, max_length=512)
    allow_domains: Optional[list[str]] = None
    keywords: Optional[list[str]] = None
    exclude_keywords: Optional[list[str]] = None
    regions: Optional[list[str]] = None
    scrape_mode: str = "crawl"
    max_depth: int = 1
    max_pages: int = 50
    llm_enhance: str = "filter"
    enabled: bool = True


def _apply_source(p: SourcePayload, s: WebSource) -> None:
    for k, v in p.model_dump(exclude_unset=True).items():
        if k in ("allow_domains", "keywords", "exclude_keywords", "regions") and isinstance(v, list):
            setattr(s, k, ",".join(v))
        else:
            setattr(s, k, v)


@router.post("/sources")
async def admin_create_source(
    payload: SourcePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    s = WebSource(**{k: (",".join(v) if isinstance(v, list) else v)
                     for k, v in payload.model_dump().items()})
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"success": True, "data": {"id": s.id}}


@router.put("/sources/{sid}")
async def admin_update_source(
    sid: int,
    payload: SourcePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    s = db.get(WebSource, sid)
    if not s or s.is_deleted:
        raise HTTPException(status_code=404, detail="来源不存在")
    _apply_source(payload, s)
    db.commit()
    return {"success": True}


@router.delete("/sources/{sid}")
async def admin_delete_source(
    sid: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _require_intel_op(user)
    s = db.get(WebSource, sid)
    if not s or s.is_deleted:
        raise HTTPException(status_code=404, detail="来源不存在")
    s.is_deleted = True
    db.commit()
    return {"success": True}


@router.post("/sources/{sid}/crawl")
async def admin_crawl_source(
    sid: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """手动触发单来源爬取(复用意向爬虫)。"""
    _require_intel_op(user)
    from app.services.intent_crawler import crawl_intent_source
    src = db.get(WebSource, sid)
    if not src or src.is_deleted:
        raise HTTPException(status_code=404, detail="来源不存在")
    try:
        result = crawl_intent_source(db, src)
        return {"success": True, "data": result}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)[:200]}") from e


# ─────────────────────────────────────────────────────────
# 情报导出(CSV)
# ─────────────────────────────────────────────────────────
@router.get("/export")
async def admin_export_intents(
    keyword: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    county: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    project_type: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    wf_status: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    dataset_type: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """按当前筛选条件导出情报列表为 CSV(utf-8-sig, Excel 直接打开不乱码)。"""
    perms = set(user.get("permissions", []))
    if not perms.intersection({"intel_export", "menu_intel_intents"}):
        raise HTTPException(status_code=403, detail="无导出权限")
    stmt = select(IntentNotice).where(IntentNotice.is_deleted == False)
    if keyword:
        stmt = stmt.where(or_(
            IntentNotice.title.contains(keyword),
            IntentNotice.dept.contains(keyword),
        ))
    for attr, val in (("province", province), ("city", city), ("county", county)):
        if val:
            stmt = stmt.where(getattr(IntentNotice, attr) == val)
    if industry:
        stmt = stmt.where(IntentNotice.industry == industry)
    if project_type:
        stmt = stmt.where(IntentNotice.project_type == project_type)
    if stage:
        stmt = stmt.where(IntentNotice.stage == stage)
    if wf_status:
        stmt = stmt.where(IntentNotice.wf_status == wf_status)
    if status:
        stmt = stmt.where(IntentNotice.status == status)
    if dataset_type:
        stmt = stmt.where(IntentNotice.dataset_type == dataset_type)
    if min_amount is not None:
        stmt = stmt.where(IntentNotice.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(IntentNotice.amount <= max_amount)
    if date_from:
        try:
            stmt = stmt.where(IntentNotice.published_at >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            pass
    if date_to:
        try:
            stmt = stmt.where(IntentNotice.published_at <= datetime.strptime(date_to, "%Y-%m-%d"))
        except ValueError:
            pass
    rows = db.execute(
        stmt.order_by(IntentNotice.published_at.is_(None), IntentNotice.published_at.desc(), IntentNotice.id.desc())
    ).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "标题", "流转状态", "业务状态", "行业", "项目类型", "金额(万元)",
                     "省份", "市", "区县", "项目阶段", "发布部门", "发布时间", "更新时间"])
    for r in rows:
        writer.writerow([
            r.id, r.title, _WF_LABELS.get(r.wf_status, r.wf_status), r.status,
            r.industry or "", r.project_type or "",
            r.amount if r.amount is not None else "",
            r.province or "", r.city or "", r.county or "",
            r.stage or "", r.dept or "",
            r.published_at.strftime("%Y-%m-%d %H:%M") if r.published_at else "",
            r.updated_at.strftime("%Y-%m-%d %H:%M") if r.updated_at else "",
        ])
    content = "\ufeff" + buf.getvalue()  # BOM: Excel 中文不乱码
    filename = f"intelligence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
