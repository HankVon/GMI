"""中标公告与关联分析 API — 需求2: 人脉网络 / 关联查询。"""
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.company import Company
from app.models.bid_notice import BidNotice
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/bids", tags=["中标公告"])


def _bn_dict(bn: BidNotice) -> dict:
    return {
        "id": bn.id,
        "clue_id": bn.clue_id,
        "title": bn.title,
        "url": bn.url,
        "purchaser": bn.purchaser,
        "purchaser_company_id": bn.purchaser_company_id,
        "region": bn.region,
        "notice_type": bn.notice_type,
        "source_name": bn.source_name,
        "published_at": bn.published_at.strftime("%Y-%m-%d") if bn.published_at else "",
        "suppliers": (bn.meta or {}).get("suppliers") or [],
    }


@router.post("/rebuild")
async def rebuild_bids(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_bid_crud")),
):
    """重新解析 web_clue 中标公告 → 写 bid_notice → 同步 Neo4j 图谱。"""
    from app.services.bid_network import rebuild
    result = rebuild(db)
    return {"success": True, "data": result}


@router.get("", response_model=PaginatedResponse)
async def list_bids(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    region: Optional[str] = None,
    province: Optional[str] = Query(None, description="省过滤(核心词: 四川/西藏/新疆)"),
    only_matched: bool = Query(False, description="只看已匹配内部公司"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """中标公告列表(支持 关键词/地域/省/仅匹配 筛选)。"""
    from app.services.china_regions import province_core
    stmt = select(BidNotice).where(BidNotice.is_deleted == False)
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(keyword))
    if region:
        # region 可能是省名(四川/四川省)或核心词 → 归一化匹配
        pc = province_core(region) or region
        stmt = stmt.where(BidNotice.region.in_([pc, f"{pc}省", f"{pc}自治区", f"{pc}维吾尔自治区"]))
    if province:
        pc = province_core(province) or province
        stmt = stmt.where(BidNotice.region.in_([pc, f"{pc}省", f"{pc}自治区", f"{pc}维吾尔自治区"]))
    if only_matched:
        # 采购人或任一供应商已匹配内部公司
        stmt = stmt.where(
            or_(
                BidNotice.purchaser_company_id.isnot(None),
                BidNotice.meta.cast(str).contains("supplier_company_id"),
            )
        )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    # MySQL 8 不支持 NULLS LAST, 用 IS NULL 控制空值排序
    stmt = stmt.order_by(BidNotice.published_at.is_(None), BidNotice.published_at.desc(), BidNotice.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = [_bn_dict(bn) for bn in db.execute(stmt).scalars().all()]
    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/company/{company_id}")
async def company_bids(
    company_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """某公司的中标关联: 作为采购人(业主)发起的 / 作为供应商中标 / 潜在业主推荐。

    返回:
      as_purchaser: 该公司作为采购人的公告列表
      as_winner: 该公司作为中标供应商的公告列表
      potential_owners: 潜在业主推荐(与该公司同场竞标或同一采购人的其他采购人)
    """
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="单位不存在")

    as_purchaser = []
    as_winner = []

    # 作为采购人
    bns = db.execute(
        select(BidNotice).where(
            BidNotice.purchaser_company_id == company_id, BidNotice.is_deleted == False
        ).order_by(BidNotice.published_at.is_(None), BidNotice.published_at.desc())
    ).scalars().all()
    as_purchaser = [_bn_dict(bn) for bn in bns]

    # 作为中标供应商
    all_bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all()
    for bn in all_bids:
        for sp in (bn.meta or {}).get("suppliers") or []:
            if sp.get("supplier_company_id") == company_id:
                as_winner.append(_bn_dict(bn))
                break

    # 潜在业主推荐: 该公司中标的公告的采购人(去重, 排除自己), 按中标次数排序
    owner_counter: dict = {}
    for bn in as_winner:
        pid = bn["purchaser_company_id"]
        if pid and pid != company_id:
            owner_counter[pid] = owner_counter.get(pid, 0) + 1
    potential_owners = []
    if owner_counter:
        comps = db.execute(
            select(Company).where(Company.id.in_(list(owner_counter.keys())), Company.is_deleted == False)
        ).scalars().all()
        for c in comps:
            potential_owners.append({
                "company_id": c.id,
                "name": c.name,
                "company_type": c.company_type or "",
                "province": c.province or "",
                "bid_count": owner_counter.get(c.id, 0),
            })
        potential_owners.sort(key=lambda x: -x["bid_count"])

    # 公司内部人员参与的中标关联: 内部人员 → 任职公司 → 中标 → 采购人
    # (供「内部人员的人脉」使用)
    return {
        "company_id": company_id,
        "company_name": company.name,
        "as_purchaser": as_purchaser,
        "as_winner": as_winner,
        "potential_owners": potential_owners,
        "stats": {
            "as_purchaser": len(as_purchaser),
            "as_winner": len(as_winner),
            "potential_owners": len(potential_owners),
        },
    }


@router.get("/network/company/{company_id}")
async def company_network(
    company_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """基于中标数据的人脉网络: 内部公司 → 中标 → 采购人(潜在业主) / 供应商(潜在合作) /
    竞对(同场竞标其他供应商)。"""
    company = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="单位不存在")

    # 该公司参与的 Bid 节点(bid_id 集合): 作为供应商中标
    winner_bids: set = set()
    # 该公司作为采购人发起的 Bid
    purchaser_bids: set = set()
    all_bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all()
    for bn in all_bids:
        for sp in (bn.meta or {}).get("suppliers") or []:
            if sp.get("supplier_company_id") == company_id:
                winner_bids.add(bn.id)
        if bn.purchaser_company_id == company_id:
            purchaser_bids.add(bn.id)

    # 采购人(该公司中标了谁的标) → 潜在业主
    owners: dict = {}
    for bn in all_bids:
        if bn.id in winner_bids and bn.purchaser_company_id:
            owners[bn.purchaser_company_id] = owners.get(bn.purchaser_company_id, 0) + 1

    # 同场竞标对手(与该公司共同竞标某采购人项目的其他中标供应商)
    competitors: dict = {}
    for bn in all_bids:
        if bn.id not in winner_bids:
            continue
        for sp in (bn.meta or {}).get("suppliers") or []:
            scid = sp.get("supplier_company_id")
            if scid and scid != company_id:
                competitors[scid] = competitors.get(scid, 0) + 1

    # 该公司作为采购人时, 中标给它的供应商 → 潜在合作方
    suppliers: dict = {}
    for bn in all_bids:
        if bn.id not in purchaser_bids:
            continue
        for sp in (bn.meta or {}).get("suppliers") or []:
            scid = sp.get("supplier_company_id")
            if scid and scid != company_id:
                suppliers[scid] = suppliers.get(scid, 0) + 1

    def _comp_list(counter: dict, limit: int = 50) -> list:
        if not counter:
            return []
        comps = db.execute(
            select(Company).where(Company.id.in_(list(counter.keys())), Company.is_deleted == False)
        ).scalars().all()
        rows = [{
            "company_id": c.id, "name": c.name,
            "company_type": c.company_type or "", "province": c.province or "",
            "bid_count": counter.get(c.id, 0),
        } for c in comps]
        rows.sort(key=lambda x: -x["bid_count"])
        return rows[:limit]

    # ── 弱关联推荐: 地域 + 行业 提示(内部公司无同名中标时仍能发现潜在业主) ──
    # 地域: 公司省份/城市核心词 → 匹配同地域公告采购人(即使未入库公司, 也是潜在业主线索)
    region_words = []
    for w in (company.province or "", company.city or ""):
        core = w.replace("省", "").replace("市", "").replace("自治区", "").replace("地区", "").replace("县", "").replace("回族自治州", "")
        if core:
            region_words.append(core)
    region_owners: dict = {}  # {purchaser_name: {count, company_id|None}}
    for bn in all_bids:
        if bn.purchaser_company_id == company_id:
            continue
        bn_region = (bn.region or "")
        purchaser_name = (bn.purchaser or "").strip()
        if not purchaser_name:
            continue
        hit = False
        for rw in region_words:
            if rw and (rw in bn_region or rw in purchaser_name):
                hit = True
                break
        if not hit:
            continue
        if purchaser_name not in region_owners:
            region_owners[purchaser_name] = {"count": 0, "company_id": bn.purchaser_company_id}
        region_owners[purchaser_name]["count"] += 1

    region_owner_list = sorted(
        [
            {"purchaser": n, "count": v["count"], "company_id": v["company_id"]}
            for n, v in region_owners.items()
        ],
        key=lambda x: -x["count"],
    )[:50]

    return {
        "company_id": company_id,
        "company_name": company.name,
        "potential_owners": _comp_list(owners),     # 潜在业主(该公司中标的对象, 强关联)
        "region_owners": region_owner_list,          # 同地域潜在业主(弱关联推荐, 含未入库公司)
        "competitors": _comp_list(competitors),      # 竞对(同场竞标)
        "potential_suppliers": _comp_list(suppliers),  # 潜在合作方(该公司发标后中标者)
        "stats": {
            "bids_won": len(winner_bids),
            "bids_purchased": len(purchaser_bids),
            "owners": len(owners), "region_owners": len(region_owner_list),
            "competitors": len(competitors), "suppliers": len(suppliers),
        },
    }


@router.get("/stats")
async def bid_stats(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """中标数据总览: 总数 / 匹配数 / 采购人top / 供应商top。"""
    total = db.execute(select(func.count()).select_from(
        select(BidNotice.id).where(BidNotice.is_deleted == False).subquery()
    )).scalar() or 0
    matched_purchasers = db.execute(select(func.count()).select_from(
        select(BidNotice.id).where(
            BidNotice.is_deleted == False, BidNotice.purchaser_company_id.isnot(None)
        ).subquery()
    )).scalar() or 0

    # 采购人 top(未匹配的公司也统计名称)
    all_bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all()
    purchasers: dict = {}
    suppliers: dict = {}
    for bn in all_bids:
        pname = bn.purchaser or "未知采购人"
        purchasers[pname] = purchasers.get(pname, 0) + 1
        for sp in (bn.meta or {}).get("suppliers") or []:
            sname = sp.get("supplier") or "未知供应商"
            suppliers[sname] = suppliers.get(sname, 0) + 1

    top_purchasers = sorted(purchasers.items(), key=lambda x: -x[1])[:10]
    top_suppliers = sorted(suppliers.items(), key=lambda x: -x[1])[:10]
    return {
        "total": total,
        "matched_purchasers": matched_purchasers,
        "top_purchasers": [{"name": n, "count": c} for n, c in top_purchasers],
        "top_suppliers": [{"name": n, "count": c} for n, c in top_suppliers],
    }


@router.get("/intent-recommendations")
async def intent_recommendations(
    region: Optional[str] = Query(None, description="地域(如 四川, 兼容旧参数)"),
    province: Optional[str] = Query(None, description="省过滤(核心词: 四川/西藏/新疆)"),
    city: Optional[str] = Query(None, description="市过滤(核心词: 成都/日喀则/喀什)"),
    county: Optional[str] = Query(None, description="县过滤(核心词: 喜德/普兰/定日)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """意向性政策 / 采购意向推荐 — 潜在可开展项目。

    从 web_clue 中筛选「采购意向/意向公开/采购需求」类公告, 作为潜在项目推荐推送。
    附带采购人/预算/电话/地址(meta), 供业务人员跟进。
    地域过滤(川藏新): province/city/county 三级, 从线索 meta 的
    regionName/regionName_/purchaserAddr 或标题文本提取目标省归属。
    """
    from app.models.web_clue import WebClue
    from app.services.china_regions import extract_target_province, is_target_province

    # 标题特征: 采购意向 / 意向公开 / 采购需求 / 采购计划 / 需求公示
    intent_kw = ("采购意向", "意向公开", "采购需求", "采购计划", "需求公示", "预公告")
    stmt = select(WebClue).where(
        WebClue.is_deleted == False,
        # 只展示已通过质量筛选的线索(status=accepted); 否则被拒绝的过期公告(rejected)会被当意向推送
        WebClue.status == "accepted",
        or_(*[WebClue.title.contains(k) for k in intent_kw]),
    )
    # 地域过滤: web_clue 无省/市/县列 → 取全部后在 Python 层按目标省归属过滤
    clues_all = db.execute(
        stmt.order_by(WebClue.published_at.is_(None), WebClue.published_at.desc(), WebClue.id.desc())
    ).scalars().all()
    if region:
        region = province_core(region) or region
    filtered = []
    for c in clues_all:
        meta = c.meta if isinstance(c.meta, dict) else {}
        text_pool = " ".join([
            c.title or "", c.region or "",
            meta.get("regionName") or "", meta.get("regionName_") or "",
            meta.get("purchaserAddr") or "", meta.get("purchaser") or "",
        ])
        target = extract_target_province(text_pool)
        if region and target != region:
            continue
        if province and target != province:
            continue
        if city and city not in text_pool:
            continue
        if county and county not in text_pool:
            continue
        filtered.append((c, meta))
    total = len(filtered)
    paged = filtered[(page - 1) * page_size: page * page_size]
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    stmt = stmt.order_by(WebClue.published_at.is_(None), WebClue.published_at.desc(), WebClue.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    clues = db.execute(stmt).scalars().all()

    items = []
    for c, meta in paged:
        items.append({
            "id": c.id,
            "title": c.title,
            "url": c.url,
            "source_name": c.source_name or "",
            "published_at": c.published_at.strftime("%Y-%m-%d") if c.published_at else "",
            "region": c.region or (meta.get("regionName") or ""),
            "purchaser": meta.get("purchaser") or "",
            "budget": meta.get("budget") or "",
            "phone": meta.get("purchaserLinkPhone") or "",
            "address": meta.get("purchaserAddr") or "",
            "agency": meta.get("agency") or "",
            "category": meta.get("catalogueNameList") or "",
        })
    return {
        "total": total,
        "items": items,
        "recommended_for": province or city or county or region or "全部",
        "note": "采购意向/需求公示为潜在可开展项目的政策线索, 建议结合内部资质与地域跟进",
    }
