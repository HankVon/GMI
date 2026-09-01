"""中标公告与关联分析 API — 需求2: 人脉网络 / 关联查询。"""
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_, func, Text

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.company import Company
from app.models.bid_notice import BidNotice
from app.schemas.common import PaginatedResponse
from app.models.user_entity_action import UserEntityAction
from app.services.tender_detail_service import TenderDetailService

router = APIRouter(prefix="/bids", tags=["中标公告"])
tender_router = APIRouter(prefix="/tenders", tags=["招投标详情"])


def _published_bid(db: Session, bid_id: int) -> BidNotice:
    """前台取单条标讯: 必须 published 且未删除, 否则 404。"""
    bn = db.get(BidNotice, bid_id)
    if not bn or bn.is_deleted or bn.status != "published":
        raise HTTPException(status_code=404, detail="标讯不存在或未发布")
    return bn


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
        "status": bn.status,
        "industry": bn.industry or ((bn.meta or {}).get("industry") if isinstance(bn.meta, dict) else None),
    }


# LIKE 通配符转义: 用户关键字里的 % / _ 按字面量匹配, 避免被当成 SQL 通配符。
# 用 '!' 作转义符(避开 MySQL 对反斜杠的处理差异, 部分实例 NO_BACKSLASH_ESCAPES 开启)
def _escape_like(s: str) -> str:
    return s.replace("!", "!!").replace("%", "!%").replace("_", "!_")


# 标准公告类型关键词: notice_type 含其一即“标准档”; “其他”档 = 不含任何标准关键词
STANDARD_NOTICE_KEYWORDS = (
    "招标", "中标", "成交", "采购", "变更", "更正", "终止", "中止",
    "废标", "流标", "竞价", "比选", "谈判", "磋商", "预审", "意向", "结果",
)


@router.get("/attachment-gaps")
async def attachment_gap_stats(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """标讯附件抓取缺口统计(按来源聚合)。

    用于排查哪些来源网站抓不到附件(需适配解析器)。数据来自
    backend/logs/attachment_gaps.log, 由采集/解析流程在附件为空时写入。
    """
    from app.services.attachment_monitor import get_gap_stats
    return {"success": True, "data": get_gap_stats()}


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
    notice_type: Optional[str] = Query(None, description="公告类型(中标/成交/招标等, 模糊匹配)"),
    date_from: Optional[str] = Query(None, description="发布日期起(YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="发布日期止(YYYY-MM-DD)"),
    purchaser_keyword: Optional[str] = Query(None, description="采购人名称过滤(模糊)"),
    supplier_keyword: Optional[str] = Query(None, description="中标供应商名称过滤(模糊, 匹配 meta.suppliers)"),
    category: Optional[str] = Query(None, description="项目分类(工程/服务/货物, 模糊匹配)"),
    industry: Optional[str] = Query(None, description="行业类型(模糊匹配)"),
    purchase_way: Optional[str] = Query(None, description="采购方式(模糊匹配)"),
    price_type: Optional[str] = Query(None, description="询价方式(单价/总价, 模糊匹配)"),
    budget_min: Optional[float] = Query(None, description="预算下限(万元)"),
    budget_max: Optional[float] = Query(None, description="预算上限(万元)"),
    only_matched: bool = Query(False, description="只看已匹配内部公司"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """标讯列表(支持 关键词/地域/省/公告类型/仅匹配 筛选, 对标建设通 AI标讯)。

    前台可见性: 仅返回 status='published' 且未删除的标讯(生命周期由后台管理控制)。
    """
    from app.services.china_regions import province_core
    stmt = select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.status == "published")
    # 数据范围过滤(分发权限): 未启用数据范围时保持现状(不过滤)
    from app.services.data_scope_service import resolve_scope, scope_filter
    scope = resolve_scope(db, user, "bid")
    cond = scope_filter(scope, BidNotice, "bid", user_id=user.get("user_id"))
    if cond is not None:
        stmt = stmt.where(cond)
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(_escape_like(keyword), escape="!"))
    if region:
        # region 可能是省名(四川/四川省)或核心词 → 归一化匹配
        pc = province_core(region) or region
        stmt = stmt.where(BidNotice.region.in_([pc, f"{pc}省", f"{pc}自治区", f"{pc}维吾尔自治区"]))
    if province:
        pc = province_core(province) or province
        stmt = stmt.where(BidNotice.region.in_([pc, f"{pc}省", f"{pc}自治区", f"{pc}维吾尔自治区"]))
    if notice_type:
        if notice_type == "其他":
            # “其他”档 = 公告类型不含任何标准关键词(取反匹配)
            stmt = stmt.where(and_(*[~BidNotice.notice_type.contains(k, escape="!") for k in STANDARD_NOTICE_KEYWORDS]))
        else:
            stmt = stmt.where(BidNotice.notice_type.contains(_escape_like(notice_type), escape="!"))
    if date_from:
        stmt = stmt.where(BidNotice.published_at >= date_from)
    if date_to:
        stmt = stmt.where(BidNotice.published_at < f"{date_to} 23:59:59")
    if purchaser_keyword:
        stmt = stmt.where(BidNotice.purchaser.contains(_escape_like(purchaser_keyword), escape="!"))
    if supplier_keyword:
        # 中标供应商存于 meta.suppliers JSON, 用字符串模糊匹配(与 only_matched 同款方式)
        # 转义 %/_ 避免用户输入被当成 SQL 通配符
        stmt = stmt.where(BidNotice.meta.cast(Text).contains(_escape_like(supplier_keyword), escape="!"))
    if category:
        # 分类/行业/采购方式/询价: 各字段独立模糊, 与 keyword 解耦(不再拼进标题)
        stmt = stmt.where(BidNotice.category.contains(_escape_like(category), escape="!"))
    if industry:
        stmt = stmt.where(BidNotice.industry.contains(_escape_like(industry), escape="!"))
    if purchase_way:
        stmt = stmt.where(BidNotice.purchase_way.contains(_escape_like(purchase_way), escape="!"))
    if price_type:
        stmt = stmt.where(BidNotice.price_type.contains(_escape_like(price_type), escape="!"))
    if budget_min is not None:
        # 预算(万元)区间重叠匹配: 用户下限 a 命中标讯上限或下限达到 a
        stmt = stmt.where(or_(BidNotice.budget_max >= budget_min, BidNotice.budget_min >= budget_min))
    if budget_max is not None:
        stmt = stmt.where(BidNotice.budget_max <= budget_max)
    if only_matched:
        # 采购人或任一供应商已匹配内部公司
        stmt = stmt.where(
            or_(
                BidNotice.purchaser_company_id.isnot(None),
                BidNotice.meta.cast(Text).contains("supplier_company_id"),
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
            BidNotice.purchaser_company_id == company_id, BidNotice.is_deleted == False,
            BidNotice.status == "published",
        ).order_by(BidNotice.published_at.is_(None), BidNotice.published_at.desc())
    ).scalars().all()
    as_purchaser = [_bn_dict(bn) for bn in bns]

    # 作为中标供应商
    all_bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.status == "published")
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
            ext = c.ext_attrs or {}
            registered_capital = ext.get("registered_capital") or ext.get("注册资本") or ext.get("capital") or ""
            potential_owners.append({
                "company_id": c.id,
                "name": c.name,
                "company_type": c.company_type or "",
                "province": c.province or "",
                "registered_capital": registered_capital,
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
        select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.status == "published")
    ).scalars().all()
    for bn in all_bids:
        for sp in (bn.meta or {}).get("suppliers") or []:
            if sp.get("supplier_company_id") == company_id:
                winner_bids.add(bn.id)
        if bn.purchaser_company_id == company_id:
            purchaser_bids.add(bn.id)

    # 采购人(该公司中标了谁的标) → 潜在业主
    owners: dict = {}
    owner_evidence: dict = {}  # {company_id: [公告]}
    for bn in all_bids:
        if bn.id in winner_bids and bn.purchaser_company_id:
            pid = bn.purchaser_company_id
            owners[pid] = owners.get(pid, 0) + 1
            owner_evidence.setdefault(pid, []).append(bn)

    # 同场竞标对手(与该公司共同竞标某采购人项目的其他中标供应商)
    competitors: dict = {}
    comp_evidence: dict = {}
    for bn in all_bids:
        if bn.id not in winner_bids:
            continue
        for sp in (bn.meta or {}).get("suppliers") or []:
            scid = sp.get("supplier_company_id")
            if scid and scid != company_id:
                competitors[scid] = competitors.get(scid, 0) + 1
                comp_evidence.setdefault(scid, []).append(bn)

    # 该公司作为采购人时, 中标给它的供应商 → 潜在合作方
    suppliers: dict = {}
    sup_evidence: dict = {}
    for bn in all_bids:
        if bn.id not in purchaser_bids:
            continue
        for sp in (bn.meta or {}).get("suppliers") or []:
            scid = sp.get("supplier_company_id")
            if scid and scid != company_id:
                suppliers[scid] = suppliers.get(scid, 0) + 1
                sup_evidence.setdefault(scid, []).append(bn)

    def _comp_list(counter: dict, evidence_of: dict, limit: int = 50) -> list:
        """company 关联列表 + 每条关系的真实公告证据(evidence_of: {company_id: [公告]})。"""
        if not counter:
            return []
        comps = db.execute(
            select(Company).where(Company.id.in_(list(counter.keys())), Company.is_deleted == False)
        ).scalars().all()
        rows = []
        for c in comps:
            evs = evidence_of.get(c.id, [])
            ext = c.ext_attrs or {}
            registered_capital = ext.get("registered_capital") or ext.get("注册资本") or ext.get("capital") or ""
            rows.append({
                "company_id": c.id, "name": c.name,
                "company_type": c.company_type or "", "province": c.province or "",
                "registered_capital": registered_capital,
                "bid_count": counter.get(c.id, 0),
                "bids": [{
                    "id": b.id, "title": b.title, "url": b.url or "",
                    "published_at": b.published_at.strftime("%Y-%m-%d") if b.published_at else "",
                } for b in evs[:8]],
            })
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
        "potential_owners": _comp_list(owners, owner_evidence),     # 潜在业主(该公司中标的对象, 强关联)
        "region_owners": region_owner_list,                          # 同地域潜在业主(弱关联推荐, 含未入库公司)
        "competitors": _comp_list(competitors, comp_evidence),       # 竞对(同场竞标)
        "potential_suppliers": _comp_list(suppliers, sup_evidence),  # 潜在合作方(该公司发标后中标者)
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
        select(BidNotice.id).where(BidNotice.is_deleted == False, BidNotice.status == "published").subquery()
    )).scalar() or 0
    matched_purchasers = db.execute(select(func.count()).select_from(
        select(BidNotice.id).where(
            BidNotice.is_deleted == False, BidNotice.status == "published",
            BidNotice.purchaser_company_id.isnot(None),
        ).subquery()
    )).scalar() or 0

    # 采购人 top(未匹配的公司也统计名称)
    all_bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.status == "published")
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


def _display_field(value, gated: bool = False) -> dict:
    if value in (None, ""):
        return {"value": None, "displayText": "未披露", "isGated": False}
    return {"value": value, "displayText": "******" if gated else str(value), "isGated": gated}


def _action_state(db: Session, bid_id: int, user_id: int) -> dict:
    row = db.execute(select(UserEntityAction).where(UserEntityAction.user_id == user_id, UserEntityAction.entity_type == "bid", UserEntityAction.entity_id == bid_id, UserEntityAction.is_deleted == False)).scalar_one_or_none()
    return {"canDownload": True, "isMonitored": bool(row and row.monitored), "isCollected": bool(row and row.collected)}


@tender_router.get("/{bid_id}/detail")
async def tender_detail(bid_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    bn = db.get(BidNotice, bid_id)
    if not bn or bn.is_deleted or bn.status != "published": raise HTTPException(status_code=404, detail="标讯不存在或未发布")
    return {"success": True, "data": TenderDetailService(db, user).build(bn).model_dump()}


async def _legacy_tender_detail(bid_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    bn = _published_bid(db, bid_id)
    data = _bn_dict(bn); meta = bn.meta if isinstance(bn.meta, dict) else {}
    project = meta.get("project_info") or {}; finance = meta.get("finance") or {}; evaluation = meta.get("evaluation") or {}; requirements = meta.get("requirements") or {}
    kv = [{"label": "公告编号", "field": _display_field(bn.id)}, {"label": "公告类型", "field": _display_field(bn.notice_type)}, {"label": "项目地区", "field": _display_field(bn.region)}, {"label": "招标单位", "field": _display_field(bn.purchaser)}]
    for label, key in (("项目类型", "type"), ("建设规模", "scale"), ("建设工期", "duration"), ("招标方式", "method")):
        kv.append({"label": label, "field": _display_field(project.get(key))})
    for label, key in (("预算金额", "budget"), ("资金来源", "source"), ("投标保证金", "deposit")):
        kv.append({"label": label, "field": _display_field(finance.get(key))})
    for label, key in (("评标办法", "method"), ("企业资质", "company"), ("业绩要求", "performance")):
        kv.append({"label": label, "field": _display_field((evaluation | requirements).get(key))})
    timeline = meta.get("timeline") or meta.get("dates") or []
    if isinstance(timeline, dict): timeline = [{"label": k, "value": v} for k, v in timeline.items()]
    events = [{"name": row.get("label") or row.get("name") or "时间节点", "date": row.get("value") or row.get("date"), "summary": _display_field(row.get("summary"))} for row in timeline if isinstance(row, dict)]
    return {"success": True, "data": {"header": {"id": bn.id, "title": bn.title, "publishedAt": bn.published_at.strftime("%Y-%m-%d") if bn.published_at else "", "sourceUrl": bn.url}, "tags": [{"label": bn.notice_type, "kind": "status"}] if bn.notice_type else [], "kv": kv, "timeMatrix": [{"label": "报名截止", "field": _display_field(project.get("registration_deadline"))}, {"label": "文件获取截止", "field": _display_field(project.get("document_deadline"))}, {"label": "投标截止", "field": _display_field(project.get("bid_deadline"))}, {"label": "开标时间", "field": _display_field(project.get("opening_time"))}], "timeline": events, "body": meta.get("body") or meta.get("content") or "", "relatedCompanies": data.get("related_companies", []), "actions": _action_state(db, bid_id, int(user["user_id"]))}}


@tender_router.get("/{bid_id}/similar")
async def similar_tenders(bid_id: int, limit: int = Query(6, ge=1, le=20), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """按公告类型、地区和标题关键词返回相似标讯，排除当前公告。"""
    source = _published_bid(db, bid_id)
    stmt = select(BidNotice).where(BidNotice.id != bid_id, BidNotice.is_deleted == False, BidNotice.status == "published")
    if source.notice_type: stmt = stmt.where(BidNotice.notice_type == source.notice_type)
    if source.region: stmt = stmt.where(BidNotice.region == source.region)
    rows = db.execute(stmt.order_by(BidNotice.published_at.desc(), BidNotice.id.desc()).limit(limit)).scalars().all()
    if not rows and source.notice_type:
        rows = db.execute(select(BidNotice).where(BidNotice.id != bid_id, BidNotice.is_deleted == False, BidNotice.status == "published", BidNotice.notice_type == source.notice_type).order_by(BidNotice.published_at.desc()).limit(limit)).scalars().all()
    return {"success": True, "data": [{"id": row.id, "title": row.title, "notice_type": row.notice_type, "region": row.region, "purchaser": row.purchaser, "published_at": row.published_at.strftime("%Y-%m-%d") if row.published_at else "", "tags": [{"label": row.notice_type, "kind": "status"}] if row.notice_type else []} for row in rows]}


@tender_router.get("/actions/summary")
async def tender_action_summary(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    uid = int(user["user_id"])
    monitored = db.execute(select(func.count(UserEntityAction.id)).where(UserEntityAction.user_id == uid, UserEntityAction.entity_type == "bid", UserEntityAction.monitored == True, UserEntityAction.is_deleted == False)).scalar() or 0
    collected = db.execute(select(func.count(UserEntityAction.id)).where(UserEntityAction.user_id == uid, UserEntityAction.entity_type == "bid", UserEntityAction.collected == True, UserEntityAction.is_deleted == False)).scalar() or 0
    return {"success": True, "data": {"monitoredCount": monitored, "collectedCount": collected}}


@tender_router.get("/actions")
async def list_tender_actions(
    type: Optional[str] = Query(None, description="collected=只看收藏 | monitored=只看监控, 不传返回全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """★ P0-4: 当前用户收藏/监控标讯列表(用户级查看页数据源, 闭环后半段)。"""
    uid = int(user["user_id"])
    stmt = select(UserEntityAction).where(
        UserEntityAction.user_id == uid,
        UserEntityAction.entity_type == "bid",
        UserEntityAction.is_deleted == False,
    )
    if type == "collected":
        stmt = stmt.where(UserEntityAction.collected == True)
    elif type == "monitored":
        stmt = stmt.where(UserEntityAction.monitored == True)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(UserEntityAction.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    bid_ids = [r.entity_id for r in rows]
    bid_map: dict = {}
    if bid_ids:
        for bn in db.execute(
            select(BidNotice.id, BidNotice.title, BidNotice.region, BidNotice.purchaser,
                   BidNotice.published_at, BidNotice.notice_type)
            .where(BidNotice.id.in_(bid_ids), BidNotice.is_deleted == False)
        ):
            bid_map[bn[0]] = bn
    items = []
    for r in rows:
        b = bid_map.get(r.entity_id)
        items.append({
            "id": r.id,
            "bid_id": r.entity_id,
            "collected": bool(r.collected),
            "monitored": bool(r.monitored),
            "title": b[1] if b else None,
            "region": b[2] if b else None,
            "purchaser": b[3] if b else None,
            "published_at": b[4].isoformat() if b and b[4] else None,
            "notice_type": b[5] if b else None,
        })
    return {"success": True, "data": {"total": total, "page": page, "page_size": page_size, "items": items}}


@tender_router.get("/{bid_id}/actions")
async def tender_action_state(bid_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _published_bid(db, bid_id)
    return {"success": True, "data": _action_state(db, bid_id, int(user["user_id"]))}


@tender_router.post("/{bid_id}/monitor")
async def toggle_tender_monitor(bid_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return await _toggle_action(bid_id, "monitor", db, user)


@tender_router.post("/{bid_id}/favorite")
async def toggle_tender_favorite(bid_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return await _toggle_action(bid_id, "favorite", db, user)


async def _toggle_action(bid_id: int, action: str, db: Session, user: dict):
    _published_bid(db, bid_id)
    field = "monitored" if action == "monitor" else "collected"
    row = db.execute(select(UserEntityAction).where(UserEntityAction.user_id == int(user["user_id"]), UserEntityAction.entity_type == "bid", UserEntityAction.entity_id == bid_id)).scalar_one_or_none()
    if not row: row = UserEntityAction(user_id=int(user["user_id"]), entity_type="bid", entity_id=bid_id); db.add(row)
    setattr(row, field, not bool(getattr(row, field))); db.commit()
    return {"success": True, "data": {"action": field, "active": bool(getattr(row, field))}}


@router.post("/{bid_id}/actions")
async def toggle_bid_action(bid_id: int, payload: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    if not db.get(BidNotice, bid_id): raise HTTPException(status_code=404, detail="标讯不存在")
    field = "monitored" if payload.get("action") == "monitor" else "collected" if payload.get("action") == "favorite" else None
    if not field: raise HTTPException(status_code=422, detail="action 必须是 monitor 或 favorite")
    row = db.execute(select(UserEntityAction).where(UserEntityAction.user_id == int(user["user_id"]), UserEntityAction.entity_type == "bid", UserEntityAction.entity_id == bid_id)).scalar_one_or_none()
    if not row: row = UserEntityAction(user_id=int(user["user_id"]), entity_type="bid", entity_id=bid_id); db.add(row)
    setattr(row, field, not bool(getattr(row, field))); db.commit()
    return {"success": True, "data": {"action": field, "active": bool(getattr(row, field))}}


@router.get("/{bid_id}")
async def get_bid_detail(
    bid_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单条标讯详情(对标建设通标讯详情页: 基本信息/关键时间/中标供应商/关联单位)。

    返回标讯全字段 + 公告摘要 + 采购人/中标供应商关联内部单位信息。
    """
    bn = _published_bid(db, bid_id)
    data = _bn_dict(bn)
    meta = bn.meta if isinstance(bn.meta, dict) else {}
    # 公告摘要/分类关键词
    data.update({
        "summary": meta.get("summary") or "",
        "industry": meta.get("industry") or "",
        "keywords": meta.get("keywords") or [],
        "body_excerpt": (meta.get("body") or meta.get("content") or "")[:2000],
        "agency": meta.get("agency") or "",
        "budget": meta.get("budget") or "",
        # 兼容采集源的结构化字段，详情页按模块展示，缺失字段保持未披露。
        "project_info": meta.get("project_info") or meta.get("projectInfo") or {},
        "timeline": meta.get("timeline") or meta.get("dates") or [],
        "finance": meta.get("finance") or {},
        "evaluation": meta.get("evaluation") or {},
        "requirements": meta.get("requirements") or meta.get("qualification") or {},
        "attachments": meta.get("attachments") or [],
    })
    # 关联内部单位: 采购人 + 中标供应商(已匹配)
    comp_ids = set()
    if bn.purchaser_company_id:
        comp_ids.add(bn.purchaser_company_id)
    for s in data["suppliers"]:
        if s.get("supplier_company_id"):
            comp_ids.add(s["supplier_company_id"])
    data["related_companies"] = []
    if comp_ids:
        comps = db.execute(select(Company).where(Company.id.in_(comp_ids))).scalars().all()
        cmap = {c.id: c for c in comps}
        if bn.purchaser_company_id and bn.purchaser_company_id in cmap:
            c = cmap[bn.purchaser_company_id]
            data["purchaser_company"] = {"id": c.id, "name": c.name, "province": c.province, "city": c.city, "company_type": c.company_type}
        data["related_companies"] = [
            {"id": c.id, "name": c.name, "province": c.province, "city": c.city, "company_type": c.company_type}
            for c in comps if c.id != bn.purchaser_company_id
        ]
    return {"success": True, "data": data}


# ============================================================
# 前台「我的标讯订阅」接口(个人中心使用, 登录态, 基于 SubscriptionTask)
# 与 /api/v1/opportunities/subscriptions(商机订阅) 同源不同 product_type
# ============================================================

@router.get("/my-subscriptions")
async def list_my_bid_subscriptions(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """前台登录用户拉取自己的标讯订阅(按产品类型: tender)。"""
    from app.models.subscription_task import SubscriptionTask
    uid = int(user.get("user_id") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="请登录后访问")
    rows = db.execute(
        select(SubscriptionTask)
        .where(
            SubscriptionTask.user_id == uid,
            SubscriptionTask.product_type == "tender",
            SubscriptionTask.is_deleted == False,
        )
        .order_by(SubscriptionTask.updated_at.desc())
    ).scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "name": r.name,
                "condition": r.condition_snapshot or {},
                "enabled": r.enabled,
                "lastRunAt": r.last_run_at.isoformat() if r.last_run_at else None,
                "lastMatchCount": r.last_match_count or 0,
                "updatedAt": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.post("/my-subscriptions")
async def create_my_bid_subscription(
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """前台登录用户创建标讯订阅; payload = {name, condition}."""
    from app.models.subscription_task import SubscriptionTask
    import datetime
    uid = int(user.get("user_id") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="请登录后访问")
    name = (payload or {}).get("name")
    condition = (payload or {}).get("condition") or {}
    if not name:
        raise HTTPException(status_code=422, detail="订阅名称必填")
    task = SubscriptionTask(
        user_id=uid,
        name=name,
        condition_snapshot=condition,
        product_type="tender",
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


@router.put("/my-subscriptions/{sub_id}")
async def update_my_bid_subscription(
    sub_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """前台登录用户启停/更新自己的标讯订阅."""
    from app.models.subscription_task import SubscriptionTask
    uid = int(user.get("user_id") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="请登录后访问")
    row = db.get(SubscriptionTask, sub_id)
    if not row or row.is_deleted or row.user_id != uid or row.product_type != "tender":
        raise HTTPException(status_code=404, detail="订阅不存在")
    if "enabled" in (payload or {}):
        row.enabled = bool(payload["enabled"])
    if "name" in (payload or {}):
        row.name = payload["name"]
    if "condition" in (payload or {}):
        row.condition_snapshot = payload["condition"] or {}
    row.updated_at = datetime.datetime.now()
    db.commit()
    return {"success": True}


@router.delete("/my-subscriptions/{sub_id}")
async def delete_my_bid_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """前台登录用户删除自己的标讯订阅."""
    from app.models.subscription_task import SubscriptionTask
    import datetime
    uid = int(user.get("user_id") or 0)
    if uid <= 0:
        raise HTTPException(status_code=401, detail="请登录后访问")
    row = db.get(SubscriptionTask, sub_id)
    if not row or row.is_deleted or row.user_id != uid or row.product_type != "tender":
        raise HTTPException(status_code=404, detail="订阅不存在")
    row.is_deleted = True
    row.updated_at = datetime.datetime.now()
    db.commit()
    return {"success": True}
