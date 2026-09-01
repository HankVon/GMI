"""项目商机工作台 API: 策展数据集搜索 / 详情 / 版本追踪 / 订阅。"""
from typing import Optional, List
import datetime
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.opportunity import Opportunity
from app.models.opportunity_tag import OpportunityTag, OpportunityTagDef
from app.models.opportunity_version import OpportunityVersion
from app.models.owner import Owner
from app.models.intent_notice import IntentNotice

router = APIRouter(prefix="/opportunities", tags=["商机工作台"])


# ─────────────── 版本号管理(人工更新自动 bump) ───────────────
_VERSION_RE = re.compile(r"^V(\d+)(?:\.(\d+))?(?:\.(\d+))?$")

_FIELD_LABELS = {
    "project_name": "项目名称",
    "owner_name": "业主名称",
    "owner_type": "业主类型",
    "owner_scale": "业主规模",
    "amount_wan": "投资金额",
    "stage": "项目阶段",
    "region_province": "省份",
    "region_city": "城市",
    "project_type": "项目类型",
    "unit_role": "我方角色",
    "unit_name": "我方单位",
}


def _next_version(current: Optional[str]) -> str:
    """人工更新后的下一版本号: 按最后一段递增。

    V1.0   → V1.0.1   (无 patch 段时补 .1)
    V2.0.3 → V2.0.4
    V3.2   → V3.2.1
    空 / 非法 → V1.0   (新商机首版)
    """
    if not current:
        return "V1.0"
    m = _VERSION_RE.match(current.strip().upper())
    if not m:
        return "V1.0"
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    if m.group(3) is None:
        return f"V{major}.{minor}.1"
    return f"V{major}.{minor}.{patch + 1}"


def _summarize_changes(old: Opportunity, new: dict, explicit_summary: Optional[str]) -> str:
    """基于字段 diff 自动生成版本变更摘要; 也可由调用方显式指定。

    例: "投资额从 8000 万修正为 9500 万" / "新增关键联系人信息"
    """
    if explicit_summary and explicit_summary.strip():
        return explicit_summary.strip()
    parts: list[str] = []
    for field, label in _FIELD_LABELS.items():
        if field not in new or new[field] is None:
            continue  # 未提交该字段则不参与摘要
        ov = getattr(old, field)
        nv = new[field]
        if ov == nv:
            continue
        if field == "amount_wan":
            parts.append(f"投资额从 {ov or 0} 万修正为 {nv or 0} 万")
        else:
            parts.append(f"{label}: {ov or '空'} → {nv or '空'}")
    if "contact_summary" in new and new["contact_summary"] != old.contact_summary:
        parts.append("更新关键联系人信息")
    if "followup_log" in new and new["followup_log"] != old.followup_log:
        parts.append("新增跟进记录")
    return "；".join(parts) or "人工更新商机信息"


def _sync_owner(db: Session, op: Opportunity) -> None:
    """按业主名同步 owner 聚合统计(机会数/累计投资), 供业主概览看板使用。"""
    if not op.owner_name:
        return
    owner = db.execute(select(Owner).where(Owner.name == op.owner_name)).scalar_one_or_none()
    if not owner:
        return
    owner.opportunity_count = db.execute(
        select(func.count(Opportunity.id)).where(
            Opportunity.owner_name == op.owner_name, Opportunity.is_deleted == 0
        )
    ).scalar() or 0
    owner.total_amount_wan = db.execute(
        select(func.coalesce(func.sum(Opportunity.amount_wan), 0)).where(
            Opportunity.owner_name == op.owner_name, Opportunity.is_deleted == 0
        )
    ).scalar() or 0


# ─────────────── 意向→商机 建档同步(幂等: 按 source 去重) ───────────────
def _intent_stage(status: Optional[str]) -> Optional[str]:
    """意向状态映射为商机阶段(列表/详情可读)。"""
    return {
        "new": "意向征集",
        "qualified": "已匹配",
        "matched": "已匹配",
        "skip": "已跳过",
        "expired": "已过期",
    }.get(status or "", None)


@router.post("/sync-from-intents")
async def sync_from_intents(db: Session = Depends(get_db),
                             user: dict = Depends(require_permission("api_opportunity_crud"))):
    """把意向公告(intent_notice)同步建档为商机(幂等)。

    - 已存在的商机(source='intent-notice-{id}')跳过
    - 新增商机: dataset_type='project', 自动建 V1.0 版本记录
    """
    intents = db.execute(
        select(IntentNotice).where(IntentNotice.is_deleted == False)
    ).scalars().all()
    created = skipped = updated = 0
    now = datetime.datetime.now()
    for it in intents:
        source = f"intent-notice-{it.id}"
        existing = db.execute(
            select(Opportunity).where(Opportunity.source == source)
        ).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        op = Opportunity(
            project_name=(it.title or "")[:255],
            owner_name=it.dept or "未披露",
            owner_type=None,
            owner_scale=None,
            amount_wan=int(it.amount) if it.amount is not None else None,
            stage=_intent_stage(it.status),
            region_province=it.province,
            region_city=it.city or it.county,
            project_type=it.project_type,
            body_excerpt=(it.raw_text or "")[:6000] or None,
            contact_summary=(it.contact or "")[:500] or None,
            current_version="V1.0",
            dataset_type="project",
            source=source,
            published_at=it.published_at,
            updated_at=it.published_at or now,
        )
        db.add(op)
        db.flush()
        db.add(OpportunityVersion(
            opportunity_id=op.id,
            version="V1.0",
            change_summary="由意向公告自动建档(人工调研物料)",
            operator="system",
            released_at=it.published_at or now,
        ))
        created += 1
    db.commit()
    return {
        "success": True,
        "data": {
            "scanned": len(intents),
            "created": created,
            "skipped": skipped,
            "updated": updated,
        },
    }


# ─────────────── 策展标签字典(前端筛选区复用) ───────────────
@router.get("/tags")
async def list_tag_defs(db: Session = Depends(get_db),
                         user: dict = Depends(get_current_user)):
    rows = db.execute(select(OpportunityTagDef).order_by(OpportunityTagDef.kind, OpportunityTagDef.sort_order)).scalars().all()
    return {
        "success": True,
        "data": [
            {"id": r.id, "code": r.code, "label": r.label, "kind": r.kind,
             "isNew": bool(r.is_new), "sortOrder": r.sort_order}
            for r in rows
        ],
    }


class TagDefPayload(BaseModel):
    code: str
    label: str
    kind: str = "hot_project"
    is_new: bool = True
    sort_order: int = 0


@router.post("/tags")
async def create_tag_def(payload: TagDefPayload,
                         db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_opportunity_crud"))):
    """新增策展标签(热点领域/热门项目)。"""
    kind = payload.kind if payload.kind in ("hot_field", "hot_project") else "hot_project"
    row = db.execute(
        select(OpportunityTagDef).where(OpportunityTagDef.code == payload.code)
    ).scalar_one_or_none()
    if row:
        raise HTTPException(status_code=409, detail="标签编码已存在")
    tag = OpportunityTagDef(
        code=payload.code.strip(),
        label=payload.label.strip(),
        kind=kind,
        is_new=payload.is_new,
        sort_order=payload.sort_order,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"success": True, "data": {"id": tag.id, "code": tag.code, "label": tag.label}}


class TagDefUpdatePayload(BaseModel):
    label: Optional[str] = None
    kind: Optional[str] = None
    is_new: Optional[bool] = None
    sort_order: Optional[int] = None


@router.put("/tags/{tag_id}")
async def update_tag_def(tag_id: int,
                         payload: TagDefUpdatePayload,
                         db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_opportunity_crud"))):
    """更新策展标签(名称/热区/排序/NEW 角标)。"""
    row = db.get(OpportunityTagDef, tag_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="标签不存在")
    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.kind is not None and payload.kind in ("hot_field", "hot_project"):
        row.kind = payload.kind
    if payload.is_new is not None:
        row.is_new = payload.is_new
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    db.commit()
    return {"success": True, "data": {"id": row.id, "label": row.label}}


@router.delete("/tags/{tag_id}")
async def delete_tag_def(tag_id: int,
                         db: Session = Depends(get_db),
                         user: dict = Depends(require_permission("api_opportunity_crud"))):
    """软删标签, 并清除其与商机的关联(保留历史版本引用一致性)。"""
    row = db.get(OpportunityTagDef, tag_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=404, detail="标签不存在")
    row.is_deleted = True
    db.execute(delete(OpportunityTag).where(OpportunityTag.tag_id == tag_id))
    db.commit()
    return {"success": True, "data": {"id": tag_id}}


# ─────────────── 商机建档(创建/更新/删除, 版本号自动管理) ───────────────
class OpportunityCreatePayload(BaseModel):
    project_name: str
    owner_name: str
    owner_type: Optional[str] = None
    owner_scale: Optional[str] = None
    amount_wan: Optional[int] = None
    stage: Optional[str] = None
    region_province: Optional[str] = None
    region_city: Optional[str] = None
    project_type: Optional[str] = None
    unit_role: Optional[str] = None
    unit_name: Optional[str] = None
    body_excerpt: Optional[str] = None
    contact_summary: Optional[str] = None
    followup_log: Optional[str] = None
    dataset_type: str = Field(default="project", description="project/proposed/landtrade")
    tag_ids: Optional[List[int]] = Field(default=None, description="初始策展标签 id")
    change_summary: Optional[str] = Field(default=None, description="首版变更摘要, 默认'首版立项信息录入'")


@router.post("")
async def create_opportunity(
    payload: OpportunityCreatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_opportunity_crud")),
):
    """人工调研建档: 自动生成 V1.0 版本记录并同步业主聚合统计。"""
    ds = (payload.dataset_type or "project").lower()
    if ds not in ("project", "proposed", "landtrade"):
        ds = "project"
    op = Opportunity(
        project_name=payload.project_name.strip()[:255],
        owner_name=payload.owner_name.strip()[:255],
        owner_type=payload.owner_type,
        owner_scale=payload.owner_scale,
        amount_wan=payload.amount_wan,
        stage=payload.stage,
        region_province=payload.region_province,
        region_city=payload.region_city,
        project_type=payload.project_type,
        unit_role=payload.unit_role,
        unit_name=payload.unit_name,
        body_excerpt=payload.body_excerpt,
        contact_summary=payload.contact_summary,
        followup_log=payload.followup_log,
        current_version="V1.0",
        dataset_type=ds,
        source="人工调研",
        published_at=datetime.datetime.now(),
    )
    db.add(op)
    db.flush()
    db.add(OpportunityVersion(
        opportunity_id=op.id,
        version="V1.0",
        change_summary=payload.change_summary or "首版立项信息录入",
        operator=user.get("username") or "system",
        released_at=datetime.datetime.now(),
    ))
    if payload.tag_ids:
        valid_ids = db.execute(
            select(OpportunityTagDef.id).where(
                OpportunityTagDef.id.in_(payload.tag_ids), OpportunityTagDef.is_deleted == 0
            )
        ).scalars().all()
        for tid in valid_ids:
            db.add(OpportunityTag(opportunity_id=op.id, tag_id=tid, tag_kind="hot_project"))
    db.flush()
    _sync_owner(db, op)
    db.commit()
    return {"success": True, "data": {"id": op.id, "currentVersion": op.current_version}}


class OpportunityUpdatePayload(BaseModel):
    project_name: Optional[str] = None
    owner_name: Optional[str] = None
    owner_type: Optional[str] = None
    owner_scale: Optional[str] = None
    amount_wan: Optional[int] = None
    stage: Optional[str] = None
    region_province: Optional[str] = None
    region_city: Optional[str] = None
    project_type: Optional[str] = None
    unit_role: Optional[str] = None
    unit_name: Optional[str] = None
    body_excerpt: Optional[str] = None
    contact_summary: Optional[str] = None
    followup_log: Optional[str] = None
    dataset_type: Optional[str] = None
    change_summary: Optional[str] = Field(default=None, description="变更摘要, 缺省由字段 diff 自动生成")


@router.put("/{opportunity_id}")
async def update_opportunity(
    opportunity_id: int,
    payload: OpportunityUpdatePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_opportunity_crud")),
):
    """人工更新商机: 自动 bump 版本号 + 写入版本历史(变更摘要), 并同步业主聚合。"""
    op = db.get(Opportunity, opportunity_id)
    if not op or op.is_deleted:
        raise HTTPException(status_code=404, detail="商机不存在")
    changes = payload.model_dump(exclude_unset=True, exclude={"change_summary"})
    summary = _summarize_changes(op, changes, payload.change_summary)
    for field, value in changes.items():
        if field == "dataset_type":
            ds = (value or "project").lower()
            if ds not in ("project", "proposed", "landtrade"):
                ds = "project"
            op.dataset_type = ds
            continue
        setattr(op, field, value)
    op.current_version = _next_version(op.current_version)
    db.add(OpportunityVersion(
        opportunity_id=op.id,
        version=op.current_version,
        change_summary=summary,
        operator=user.get("username") or "system",
        released_at=datetime.datetime.now(),
    ))
    db.flush()
    _sync_owner(db, op)
    db.commit()
    return {
        "success": True,
        "data": {"id": op.id, "currentVersion": op.current_version, "changeSummary": summary},
    }


@router.delete("/{opportunity_id}")
async def delete_opportunity(
    opportunity_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_opportunity_crud")),
):
    """软删除商机(仅标记 is_deleted, 保留版本历史可供审计)。"""
    op = db.get(Opportunity, opportunity_id)
    if not op or op.is_deleted:
        raise HTTPException(status_code=404, detail="商机不存在")
    op.is_deleted = True
    db.flush()
    _sync_owner(db, op)
    db.commit()
    return {"success": True, "data": {"id": opportunity_id}}


# ─────────────── 主搜索 ───────────────
class SearchPayload(BaseModel):
    tags: Optional[List[int]] = Field(default=None, description="策展标签 id 数组, OR 并集")
    region_province: Optional[str] = None
    region_city: Optional[str] = None
    amount_min: Optional[int] = None
    amount_max: Optional[int] = None
    stage: Optional[str] = None
    unit_role: Optional[str] = None
    unit_name: Optional[str] = None
    owner_type: Optional[str] = None
    owner_name: Optional[str] = Field(default=None, description="业主名称模糊匹配")
    update_start: Optional[str] = None
    update_end: Optional[str] = None
    project_name: Optional[str] = Field(default=None, description="空格分隔多关键词 AND 匹配")
    project_type: Optional[str] = None
    dataset_type: Optional[str] = Field(default="project", description="project/proposed/landtrade")
    datasetType: Optional[str] = Field(default=None, description="camelCase 别名(需求字段对齐), 与 dataset_type 等价")
    page: int = 1
    page_size: int = 20


@router.post("/search")
async def search_opportunities(payload: SearchPayload, db: Session = Depends(get_db),
                               user: dict = Depends(get_current_user)):
    # 数据集过滤: 不同 datasetType 映射到不同 dataset_type 字段(snake/camel 双兼容)
    ds = (payload.dataset_type or payload.datasetType or "project").lower()
    if ds not in ("project", "proposed", "landtrade"):
        ds = "project"
    stmt = select(Opportunity).where(Opportunity.is_deleted == 0, Opportunity.dataset_type == ds)

    if payload.region_province:
        stmt = stmt.where(Opportunity.region_province == payload.region_province)
    if payload.region_city:
        stmt = stmt.where(Opportunity.region_city == payload.region_city)
    if payload.amount_min is not None:
        stmt = stmt.where(Opportunity.amount_wan >= payload.amount_min)
    if payload.amount_max is not None:
        stmt = stmt.where(Opportunity.amount_wan <= payload.amount_max)
    if payload.stage:
        stmt = stmt.where(Opportunity.stage == payload.stage)
    if payload.unit_role:
        stmt = stmt.where(Opportunity.unit_role == payload.unit_role)
    if payload.unit_name:
        stmt = stmt.where(Opportunity.unit_name.like(f"%{payload.unit_name}%"))
    if payload.owner_type:
        stmt = stmt.where(Opportunity.owner_type == payload.owner_type)
    if payload.owner_name:
        stmt = stmt.where(Opportunity.owner_name.like(f"%{payload.owner_name}%"))
    if payload.project_type:
        stmt = stmt.where(Opportunity.project_type == payload.project_type)
    if payload.update_start:
        try:
            stmt = stmt.where(Opportunity.updated_at >= datetime.datetime.fromisoformat(payload.update_start))
        except ValueError:
            pass
    if payload.update_end:
        try:
            stmt = stmt.where(Opportunity.updated_at <= datetime.datetime.fromisoformat(payload.update_end))
        except ValueError:
            pass
    # 项目名称: 空格分隔多关键词 AND
    if payload.project_name:
        for kw in payload.project_name.split():
            kw = kw.strip()
            if kw:
                stmt = stmt.where(Opportunity.project_name.like(f"%{kw}%"))

    # 标签 OR 并集: 任一标签命中即返回
    if payload.tags:
        opp_ids_subq = select(OpportunityTag.opportunity_id).where(OpportunityTag.tag_id.in_(payload.tags)).distinct()
        stmt = stmt.where(Opportunity.id.in_(opp_ids_subq))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(Opportunity.updated_at.desc())
        .offset(max(0, (payload.page - 1) * payload.page_size))
        .limit(payload.page_size)
    ).scalars().all()

    # 批量取关联标签(避免 N+1)
    ids = [r.id for r in rows]
    tag_map: dict[int, list] = {i: [] for i in ids}
    if ids:
        link_rows = db.execute(
            select(OpportunityTag.opportunity_id, OpportunityTagDef.label, OpportunityTagDef.code)
            .join(OpportunityTagDef, OpportunityTagDef.id == OpportunityTag.tag_id)
            .where(OpportunityTag.opportunity_id.in_(ids))
        ).all()
        for oid, label, code in link_rows:
            tag_map.setdefault(oid, []).append({"label": label, "code": code})

    items = [
        {
            "id": r.id,
            "projectName": r.project_name,
            "ownerName": r.owner_name,
            "ownerType": r.owner_type,
            "ownerScale": r.owner_scale,
            "amountWan": r.amount_wan,
            "stage": r.stage,
            "regionProvince": r.region_province,
            "regionCity": r.region_city,
            "projectType": r.project_type,
            "currentVersion": r.current_version,
            "datasetType": r.dataset_type,
            "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
            "tags": tag_map.get(r.id, []),
            # 意向关联 id(情报动态页点击跳回意向详情)
            "intentId": int(r.source.split("-")[-1]) if r.source and r.source.startswith("intent-notice-") else None,
        }
        for r in rows
    ]
    return {"success": True, "data": {"total": total, "items": items, "page": payload.page, "page_size": payload.page_size}}


# ─────────────── 商机导出(VIP 闸口由前端/权限层拦截) ───────────────
def _csv_cell(v) -> str:
    s = "" if v is None else str(v).replace("\r", " ").replace("\n", " ").strip()
    if any(c in s for c in (",", '"', "\u200b")):
        return f'"{s.replace(chr(34), chr(34) * 2)}"'
    return s


@router.get("/export")
async def export_opportunities(
    dataset_type: Optional[str] = Query(default="project"),
    owner_type: Optional[str] = Query(default=None),
    owner_name: Optional[str] = Query(default=None),
    project_name: Optional[str] = Query(default=None),
    stage: Optional[str] = Query(default=None),
    region_province: Optional[str] = Query(default=None),
    project_type: Optional[str] = Query(default=None),
    unit_name: Optional[str] = Query(default=None),
    unit_role: Optional[str] = Query(default=None),
    amount_min: Optional[float] = Query(default=None),
    amount_max: Optional[float] = Query(default=None),
    tags: Optional[str] = Query(default=None, description="逗号分隔标签 id, OR 并集"),
    update_start: Optional[str] = Query(default=None),
    update_end: Optional[str] = Query(default=None),
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """商机导出 CSV(当前筛选子集, 与搜索字段映射一致)。"""
    ds = (dataset_type or "project").lower()
    if ds not in ("project", "proposed", "landtrade"):
        ds = "project"
    stmt = select(Opportunity).where(Opportunity.is_deleted == 0, Opportunity.dataset_type == ds)
    if owner_type:
        stmt = stmt.where(Opportunity.owner_type == owner_type)
    if owner_name:
        stmt = stmt.where(Opportunity.owner_name.like(f"%{owner_name}%"))
    if region_province:
        # 前缀匹配, 与公开搜索接口一致(兼容 "四川"/"四川省")
        stmt = stmt.where(Opportunity.region_province.like(f"{region_province}%"))
    if stage:
        stmt = stmt.where(Opportunity.stage == stage)
    if project_type:
        stmt = stmt.where(Opportunity.project_type == project_type)
    if unit_name:
        # 空格分词 AND(与搜索一致)
        for kw in unit_name.split():
            if kw.strip():
                stmt = stmt.where(Opportunity.unit_name.like(f"%{kw.strip()}%"))
    if unit_role:
        stmt = stmt.where(Opportunity.unit_role == unit_role)
    if amount_min is not None:
        stmt = stmt.where(Opportunity.amount_wan >= amount_min)
    if amount_max is not None:
        stmt = stmt.where(Opportunity.amount_wan <= amount_max)
    if update_start:
        try:
            stmt = stmt.where(Opportunity.updated_at >= datetime.datetime.fromisoformat(update_start))
        except ValueError:
            pass
    if update_end:
        try:
            end_dt = datetime.datetime.fromisoformat(update_end)
            if len(update_end) <= 10:  # 纯日期含当天全天
                end_dt = end_dt + datetime.timedelta(days=1)
            stmt = stmt.where(Opportunity.updated_at <= end_dt)
        except ValueError:
            pass
    if tags:
        tag_ids = [int(t) for t in tags.split(",") if t.strip().isdigit()]
        if tag_ids:
            opp_ids_subq = select(OpportunityTag.opportunity_id).where(OpportunityTag.tag_id.in_(tag_ids)).distinct()
            stmt = stmt.where(Opportunity.id.in_(opp_ids_subq))
    rows = db.execute(stmt.order_by(Opportunity.updated_at.desc()).limit(limit)).scalars().all()

    header = ["项目名称", "业主名称", "业主类型", "业主规模", "投资金额(万元)", "项目阶段",
              "省份", "城市", "项目类型", "当前版本", "数据集", "更新时间"]
    body = [
        ",".join([
            _csv_cell(r.project_name), _csv_cell(r.owner_name), _csv_cell(r.owner_type),
            _csv_cell(r.owner_scale), _csv_cell(r.amount_wan), _csv_cell(r.stage),
            _csv_cell(r.region_province), _csv_cell(r.region_city), _csv_cell(r.project_type),
            _csv_cell(r.current_version), _csv_cell(r.dataset_type),
            _csv_cell(r.updated_at.strftime("%Y-%m-%d %H:%M:%S") if r.updated_at else ""),
        ])
        for r in rows
    ]
    csv_text = "\uFEFF" + ",".join(header) + "\r\n" + "\r\n".join(body)
    filename = f"opportunity_{ds}_{datetime.date.today().isoformat()}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────── 商机订阅(product_type=opportunity) ───────────────
class OpportunitySubscribePayload(BaseModel):
    name: str
    condition: dict


@router.post("/subscriptions")
async def create_opportunity_subscription(payload: OpportunitySubscribePayload,
                                          db: Session = Depends(get_db),
                                          user: dict = Depends(get_current_user)):
    from app.models.subscription_task import SubscriptionTask
    import datetime
    uid = int(user.get("user_id", 0))
    if uid <= 0:
        raise HTTPException(status_code=401, detail="无法识别用户身份, 请重新登录")
    task = SubscriptionTask(
        user_id=uid,
        name=payload.name,
        condition_snapshot=payload.condition or {},
        product_type="opportunity",
        enabled=True,
        is_deleted=False,
        last_match_count=0,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"success": True, "data": {"id": task.id, "name": task.name}}


@router.get("/subscriptions")
async def list_opportunity_subscriptions(db: Session = Depends(get_db),
                                         user: dict = Depends(get_current_user)):
    """当前用户的商机订阅列表(按最近更新倒序)。"""
    from app.models.subscription_task import SubscriptionTask
    uid = int(user.get("user_id", 0))
    rows = db.execute(
        select(SubscriptionTask)
        .where(SubscriptionTask.user_id == uid,
               SubscriptionTask.product_type == "opportunity",
               SubscriptionTask.is_deleted == 0)
        .order_by(SubscriptionTask.updated_at.desc())
    ).scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "condition": r.condition_snapshot,
                "enabled": bool(r.enabled),
                "lastRunAt": r.last_run_at.isoformat() if r.last_run_at else None,
                "lastMatchCount": r.last_match_count,
                "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


class OpportunitySubscriptionTogglePayload(BaseModel):
    enabled: bool


@router.put("/subscriptions/{subscription_id}")
async def toggle_opportunity_subscription(
    subscription_id: int,
    payload: OpportunitySubscriptionTogglePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """启停订阅(仅本人可操作)。"""
    from app.models.subscription_task import SubscriptionTask
    uid = int(user.get("user_id", 0))
    row = db.execute(
        select(SubscriptionTask).where(
            SubscriptionTask.id == subscription_id,
            SubscriptionTask.user_id == uid,
            SubscriptionTask.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="订阅不存在")
    row.enabled = payload.enabled
    db.commit()
    return {"success": True, "data": {"id": row.id, "enabled": bool(row.enabled)}}


@router.delete("/subscriptions/{subscription_id}")
async def delete_opportunity_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """删除订阅(软删除, 仅本人可操作)。"""
    from app.models.subscription_task import SubscriptionTask
    uid = int(user.get("user_id", 0))
    row = db.execute(
        select(SubscriptionTask).where(
            SubscriptionTask.id == subscription_id,
            SubscriptionTask.user_id == uid,
            SubscriptionTask.is_deleted == 0,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="订阅不存在")
    row.is_deleted = True
    db.commit()
    return {"success": True, "data": {"id": subscription_id}}


# ─────────────── 详情 + 版本(动态路由放末尾, 避免与 /subscriptions 静态路由冲突) ───────────────
@router.get("/{opportunity_id}")
async def get_opportunity_detail(opportunity_id: int, db: Session = Depends(get_db),
                                  user: dict = Depends(get_current_user)):
    op = db.get(Opportunity, opportunity_id)
    if not op or op.is_deleted:
        raise HTTPException(status_code=404, detail="商机不存在")
    tag_rows = db.execute(
        select(OpportunityTagDef.label, OpportunityTagDef.code)
        .join(OpportunityTag, OpportunityTag.tag_id == OpportunityTagDef.id)
        .where(OpportunityTag.opportunity_id == opportunity_id)
    ).all()
    return {
        "success": True,
        "data": {
            "id": op.id,
            "projectName": op.project_name,
            "ownerName": op.owner_name,
            "ownerType": op.owner_type,
            "ownerScale": op.owner_scale,
            "amountWan": op.amount_wan,
            "stage": op.stage,
            "regionProvince": op.region_province,
            "regionCity": op.region_city,
            "projectType": op.project_type,
            "unitRole": op.unit_role,
            "unitName": op.unit_name,
            "bodyExcerpt": op.body_excerpt,
            "currentVersion": op.current_version,
            "datasetType": op.dataset_type,
            "source": op.source,
            "updatedAt": op.updated_at.isoformat() if op.updated_at else None,
            "publishedAt": op.published_at.isoformat() if op.published_at else None,
            "tags": [{"label": l, "code": c} for l, c in tag_rows],
            # 整体设闸: 关键联系人/跟进记录仅 VIP 可见(前端与 VIP 拦截器对齐)
            "vipOnly": {
                "contactSummary": op.contact_summary,
                "followupLog": op.followup_log,
            },
        },
    }


@router.get("/{opportunity_id}/versions")
async def list_versions(opportunity_id: int, db: Session = Depends(get_db),
                        user: dict = Depends(get_current_user)):
    rows = db.execute(
        select(OpportunityVersion)
        .where(OpportunityVersion.opportunity_id == opportunity_id)
        .order_by(OpportunityVersion.released_at.desc())
    ).scalars().all()
    return {
        "success": True,
        "data": [
            {"id": v.id, "version": v.version, "changeSummary": v.change_summary,
             "operator": v.operator, "releasedAt": v.released_at.isoformat() if v.released_at else None}
            for v in rows
        ],
    }