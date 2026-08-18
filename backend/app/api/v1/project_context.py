"""项目上下文智能服务 — 以项目为中心的情报与人脉关联。

核心逻辑:
  1. 行业情报: 基于项目地域(省/市/县)+类别(category)+名称关键词, 聚合
     意向公告(投资意向期)/招标线索(招标期)/中标公告(中标公示期),
     明确区分「实际发布时间(published_at)」与「抓取时间(fetched_at)」。
  2. 人脉关联: 找到做过相似/相关项目的单位与关键人员, 并给出触达路径
     (共同项目/任职单位/人脉边/公开渠道), 帮助判断如何接触和推进当前项目。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.project import Project
from app.models.web_clue import WebClue
from app.models.bid_notice import BidNotice
from app.models.intent_notice import IntentNotice
from app.models.company import Company, ProjectCompany
from app.models.project_member import ProjectMember
from app.models.person import Person
from app.models.business_network import NetworkEdge
from app.services.china_regions import extract_target_province, is_target_province, TARGET_PROVINCES

router = APIRouter(prefix="/projects", tags=["项目上下文"])

# 招标特征词
_BIDDING_KW = ("招标", "采购", "磋商", "竞争性", "询价", "比选", "谈判", "单一来源", "竞价")
_AWARD_KW = ("中标", "成交")

# 说明(2026-08 收紧): 不设「单类别词即强相关」白名单——
# 同类别公告(如所有含「地质灾害」的中标)会命中全部同类项目, 造成量级放大。
# 强相关须满足: ≥2 个类别词 / 类别词+项目核心词 / 纯项目核心词。

# 中文映射(角色/类别/状态)
_ROLE_ZH = {
    "owner": "业主", "constructor": "施工", "designer": "设计", "supervisor": "监理",
    "partner": "合作伙伴", "manager": "项目负责人", "member": "成员", "observer": "观察者",
    "业主联系人": "业主联系人",
}
_CATEGORY_ZH = {
    "geo_survey": "地质勘察", "geo_hazard": "地质灾害", "eco_restoration": "生态修复",
    "policy": "政策咨询", "mining_rights": "矿业权",
}
_STATUS_ZH = {
    "active": "进行中", "completed": "已完工", "suspended": "已暂停", "cancelled": "已取消",
}


def _zh_role(role: str) -> str:
    return _ROLE_ZH.get(role or "", role or "")


def _zh_category(cat: str) -> str:
    return _CATEGORY_ZH.get(cat or "", cat or "")


def _zh_status(status: str) -> str:
    return _STATUS_ZH.get(status or "", status or "")


def _is_bidding_clue(title: str) -> bool:
    t = title or ""
    if any(k in t for k in _AWARD_KW):
        return False
    return any(k in t for k in _BIDDING_KW)


def _extract_region_from_text(text: str) -> dict:
    """从文本(项目名)提取 省/市/县 核心词。项目 ext_attrs 常缺地域, 用项目名兜底。

    匹配策略(与 scripts/backfill_neo4j.py 保持一致):
      - 县级: 「核心词后跟 县/区/市/旗 后缀」或核心词本身带后缀。右边界避免嵌字误判——
        「安居房」的「安居」后跟「房」不算行政区(不误挂遂宁安居县); 而「得荣县」正确命中。
        不能用左边界 `(?<![\u4e00-\u9fa5])`, 真实项目名里地名前常紧跟「省/州/市」
        (如「甘孜州得荣县」), 左边界会全部漏掉导致只挂省级。
      - 市级: 子串匹配。
    """
    import re as _re
    from app.services.china_regions import REGION_COUNTIES, _CITY_OF, TARGET_PROVINCES, extract_target_province
    if not text:
        return {"province": "", "city": "", "county": ""}
    prov = extract_target_province(text)
    # 县级(右边界)
    county = ""
    for city_key, counties in REGION_COUNTIES.items():
        if _CITY_OF.get(city_key) not in TARGET_PROVINCES:
            continue
        for ct in counties:
            if not ct:
                continue
            if ct.endswith(("县", "区", "市", "旗")):
                if ct in text:
                    county = ct
                    break
            elif _re.search(rf"{_re.escape(ct)}(?=县|区|市|旗)", text):
                county = ct
                break
        if county:
            break
    # 市级(子串匹配)
    city = ""
    for c, p in _CITY_OF.items():
        if p in TARGET_PROVINCES and c in text:
            city = c
            break
    return {"province": prov, "city": city, "county": county}


def _project_ctx(project: Project) -> dict:
    """项目上下文: 地域三级(ext_attrs 优先, 项目名兜底) + 类别 + 名称关键词。"""
    ext = project.ext_attrs or {}
    name = str(project.name or "")
    province = (ext.get("province") or "").strip()
    city = (ext.get("city") or "").strip()
    county = (ext.get("county") or "").strip()
    category = (ext.get("category") or "").strip()
    # ext_attrs 缺地域 → 从项目名逐级兜底(项目名通常含「成都市高新区」「普兰县」等地名;
    # 修复: 原先整个地域非空就不兜底, 导致 province 有值时 city/county 永远为空, 县级情报无法关联)
    from_name = _extract_region_from_text(name)
    province = province or from_name["province"]
    city = city or from_name["city"]
    county = county or from_name["county"]
    name_kw = name.replace("项目", "").replace("工程", "").strip()[:6]
    return {"province": province, "city": city, "county": county,
            "category": category, "name_kw": name_kw}


def _project_text_pool(ctx: dict) -> str:
    return " ".join(filter(None, [ctx["province"], ctx["city"], ctx["county"], ctx["name_kw"], ctx["category"]]))


@router.get("/{project_id}/intelligence")
async def project_intelligence(
    project_id: int,
    stage: Optional[str] = Query(None, description="investment/bidding/awarded, 缺省全部"),
    days: int = Query(365, ge=0, le=3650, description="时间窗(近N天, 0=全部)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """项目相关行业情报 — 聚合意向/招标/中标三源, 每条含实际发布时间+抓取时间。"""
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    ctx = _project_ctx(project)
    want = {s: (not stage or stage == s) for s in ("investment", "bidding", "awarded")}
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if days:
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)
    items: list[dict] = []
    prov_ctx = ctx["province"] or ""
    city_ctx = ctx["city"] or ""
    county_ctx = ctx["county"] or ""

    # 关联必要条件: 至少 1 个「强相关」:
    #   - 纯主题强相关: 类别词命中 ≥2 个 / 类别词+项目核心词各命中 ≥1 / 纯项目核心词命中
    #   - 地域+主题: 市级/县级地域命中 且 主题词(类别词或核心词)至少命中 1 个
    # 仅省级命中 / 仅地域命中 / 仅单个类别词(地质灾害/勘察/矿业权…)命中 → 不关联,
    # 防止同市无关公告(铁路/光伏)、医疗「防治」公告、以及一条「地质灾害」
    # 公告命中全部地灾项目的量级放大。

    # 1) 投资意向期
    if want["investment"]:
        stmt = select(IntentNotice).where(IntentNotice.is_deleted == False)
        if days:
            stmt = stmt.where(IntentNotice.published_at >= cutoff)
        for it in db.execute(stmt.order_by(IntentNotice.published_at.desc())).scalars().all():
            tpool = f"{it.title or ''} {it.region or ''}"
            r_score, r_strong = _zh_region_overlap(prov_ctx, city_ctx, county_ctx, it.province or "", it.city or "", it.county or "", tpool)
            k_score, k_strong = _keyword_overlap(ctx["name_kw"], tpool, ctx["category"])
            # 强相关 = 纯主题强相关(k_strong) 或 地域(市/县级)命中+主题词命中(r_strong and k_score>0)
            if not ((r_strong and k_score > 0) or k_strong):
                continue  # 无强相关(仅地域/仅宽泛词/仅省级) → 不关联
            items.append(_mk_item("investment", "投资意向期", it.id, it.title or "", it.url or "",
                                  it.province or "", it.city or "", it.county or "",
                                  it.published_at, it.published_at, it.dept or "政务源",
                                  it.amount and f"{it.amount}万" or "", (it.raw_text or "")[:200],
                                  score=r_score + k_score))

    # 2) 招标期
    if want["bidding"]:
        stmt = select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted")
        if days:
            stmt = stmt.where(WebClue.published_at >= cutoff)
        for c in db.execute(stmt.order_by(WebClue.published_at.desc())).scalars().all():
            if not _is_bidding_clue(c.title or ""):
                continue
            meta = c.meta if isinstance(c.meta, dict) else {}
            tpool = " ".join([c.title or "", c.region or "", meta.get("regionName") or "",
                              meta.get("regionName_") or "", meta.get("purchaserAddr") or ""])
            tgt = extract_target_province(tpool)
            if not tgt:
                continue
            r_score, r_strong = _zh_region_overlap(prov_ctx, city_ctx, county_ctx, tgt, "", "", tpool)
            k_score, k_strong = _keyword_overlap(ctx["name_kw"], tpool, ctx["category"])
            if not ((r_strong and k_score > 0) or k_strong):
                continue  # 无强相关(仅地域/仅宽泛词/仅省级) → 不关联
            items.append(_mk_item("bidding", "招标期", c.id, c.title or "", c.url or "",
                                  tgt, "", "",
                                  c.published_at, c.fetched_at, c.source_name or "网页线索",
                                  str(meta.get("budget") or ""), (c.content or c.summary or "")[:200],
                                  score=r_score + k_score))

    # 3) 中标公示期
    if want["awarded"]:
        stmt = select(BidNotice).where(BidNotice.is_deleted == False)
        if days:
            stmt = stmt.where(BidNotice.published_at >= cutoff)
        for bn in db.execute(stmt.order_by(BidNotice.published_at.desc())).scalars().all():
            tpool = f"{bn.purchaser or ''} {bn.title or ''}"
            tgt = extract_target_province(tpool) or bn.region or ""
            if not tgt:
                continue
            r_score, r_strong = _zh_region_overlap(prov_ctx, city_ctx, county_ctx, tgt, "", "", tpool)
            k_score, k_strong = _keyword_overlap(ctx["name_kw"], tpool, ctx["category"])
            if not ((r_strong and k_score > 0) or k_strong):
                continue  # 无强相关(仅地域/仅宽泛词/仅省级) → 不关联
            suppliers = ", ".join([s.get("supplier", "") for s in (bn.meta or {}).get("suppliers", []) if s.get("supplier")])
            items.append(_mk_item("awarded", "中标公示期", bn.id, bn.title or "", bn.url or "",
                                  tgt, "", "",
                                  bn.published_at, bn.fetched_at, bn.source_name or "中标公告",
                                  "", f"中标供应商: {suppliers}" if suppliers else "",
                                  score=r_score + k_score))

    # 排序: 相关度优先, 再按实际发布时间倒序
    items.sort(key=lambda x: (-x.get("score", 0), x["published_at"] or ""), reverse=False)
    items.sort(key=lambda x: x["published_at"] or "", reverse=True)
    total = len(items)
    paged = items[(page - 1) * page_size: page * page_size]
    return {
        "success": True, "total": total, "items": paged,
        "project": {"id": project.id, "name": project.name, "ctx": ctx},
    }


def _mk_item(stage, stage_label, id_, title, url, province, city, county,
             published, fetched, source_name, amount, summary, score=0) -> dict:
    return {
        "id": id_, "stage": stage, "stage_label": stage_label,
        "title": title, "url": url,
        "province": province, "city": city, "county": county,
        # 实际发布时间 vs 抓取时间(用户需求: 必须明确区分)
        "published_at": published.strftime("%Y-%m-%d %H:%M") if published else "",
        "fetched_at": fetched.strftime("%Y-%m-%d %H:%M") if fetched else "",
        "source_name": source_name, "amount": amount, "summary": summary,
        "score": score,  # 相关度(地域+主题)
    }


def _zh_region_overlap(p1, c1, k1, p2, c2, k2, text2: str) -> tuple:
    """地域重叠评分(整词匹配, 避免单字符误命中)。

    返回 (score, strong):
      score: 市级命中 +2, 县级命中 +2, 仅省级命中 +0(太宽泛, 不作为关联依据)
      strong: 是否强地域相关(市级或县级命中)
    注意: 2026-08 起 strong 须与主题命中组合使用(调用处要求 k_score>0),
    纯地域命中(同市但不同主题, 如成都项目配铁路/光伏意向)不再单独罗列。
    市级/县级必须用整词匹配, 防止「市」「区」等单字误命中
    (之前 bug: 项目名含「绵阳市」, 逐字匹配情报文本导致几乎全部公告命中)。
    """
    import re as _re
    score = 0
    strong = False
    # 市级: 完整市名(≥2字)子串出现在情报文本。
    # 注意: 不能加「词前非中文」边界——中文正文里「市国土空间」等词前必然是中文字符,
    # 负向前瞻会让所有真实命中失败(曾导致 county/city 级情报 0 命中)。
    if c1:
        if c2 == c1 or (len(c1) >= 2 and c1 in text2):
            score += 2
            strong = True
    # 县级: 完整县名(≥2字)子串出现
    if k1:
        if k2 == k1 or (len(k1) >= 2 and k1 in text2):
            score += 2
            strong = True
    return score, strong


def _keyword_overlap(kw: str, text: str, category: str = "") -> tuple:
    """项目名关键词 + 类别 vs 情报文本 的相关性评分。

    关键词必须作为「完整子串(≥2字)」整词命中(不是逐字符!):
      1. 类别词(瘦身后业务词, 排除 地质/岩土/监测/防治 等易误伤宽泛词)命中, 每个 +2
      2. 项目名核心词(去地域/通用后缀, ≥2 字完整词)整词命中, 每个 +2
    strong(强相关)判定(任一), 单个类别词命中**不**构成强相关:
      a. 类别词命中 ≥2 个(多维度确认, 如「滑坡+治理」「矿业权+采矿」)
      b. 类别词命中 ≥1 个 且 项目核心词命中 ≥1 个(双维度互补)
      c. 项目核心词命中 ≥1 个(核心词精准, 如「越界勘查」「驻守技术支撑」)
    返回 (score, strong)。单类别词命中只给分、不构成强相关(须配合地域命中),
    防止一条「地质灾害」公告命中全部地灾项目(同类别量级放大)。
    """
    score = 0
    strong = False
    if not kw and not category:
        return 0, False
    # 1) 类别词(瘦身版: 去掉 地质/岩土/监测/防治/综合治理 等高频误伤词,
    #    改用组合词(工程地质/岩土工程/地质勘查)与业务动作词保持精度)
    cat_map = {
        "geo_hazard": ["地质灾害", "地灾", "滑坡", "崩塌", "泥石流", "排危"],
        "eco_restoration": ["生态修复", "生态保护", "环境治理", "水源涵养", "矿山修复", "土壤修复", "水污染治理"],
        "mining_rights": ["矿业权", "矿业", "采矿", "矿权", "探矿", "矿产", "储量"],
        "geo_survey": ["勘察", "勘查", "测绘", "详查", "钻探", "工程地质", "岩土工程", "地质勘查"],
        # 注意: 不能含孤立「规划」「政策」「编制」——「自然资源和规划局」等机构名几乎
        # 每条公告都有「规划」, 孤立词会误配; 「政策解读」省级泛新闻会误配规划项目。
        # 只用业务组合词(专项规划/总体规划/国土空间/规划编制等), 机构名不命中。
        "policy": ["专项规划", "总体规划", "国土空间", "规划编制", "城市体检", "评估咨询", "发展规划"],
    }
    cat_hits: list[str] = []
    if category:
        for w in cat_map.get(category, []):
            if w in text:
                cat_hits.append(w)
    # 词表内部含包含关系(「矿业权」⊃「矿业」)或公告自带组合(「地质灾害」+「灾害治理」),
    # 会同时命中多个"同维度"词 → 假「≥2词」把单公告放大到全部同类项目。
    # 只保留最长命中词: 保证「≥2 类别词」表示真正多维度业务(如 滑坡+排危 / 勘察+测绘)。
    cat_hits = [w for w in cat_hits if not any(w != w2 and w in w2 for w2 in cat_hits)]
    score += 2 * len(cat_hits)
    # 2) 项目名核心词: 提取 ≥2 字的连续中文字段, 子串出现在文本
    kw_hits: list[str] = []
    if kw:
        for t in _extract_key_tokens(kw):
            if len(t) >= 2 and t in text:
                kw_hits.append(t)
    score += 2 * len(kw_hits)
    # 强相关判定(详见 docstring)
    strong = (len(cat_hits) >= 2
              or (bool(cat_hits) and bool(kw_hits))
              or bool(kw_hits))
    return score, strong


# 机构名后缀: 以这些字结尾的中文段几乎都是机构/场所名(自然资源局/财政局/发展改革委/
# 地质勘查中心…), 而非业务词。若作为核心词命中, 会因「xx自然资源局」几乎每条公告
# 都出现而把全部公告误配进情报(曾导致某项目 32 条误配)。
_INSTITUTION_SUFFIX = ("局", "委", "办", "厅", "院", "所", "站", "中心")


def _extract_key_tokens(name: str) -> list:
    """从项目名提取核心业务词(去地域/机构/通用后缀), 返回 ≥2 字连续中文词。"""
    import re as _re
    # 去掉常见地域/机构后缀词, 避免「广元市」「绵阳市」等只匹配地域。
    # 「高新区/经开区/新区」须在「区」之前, 否则先被「区」拆散留下泛词「高新」,
    # 导致命中所有含「高新区」的无关公告(曾误配铁路/供电意向)。
    for drop in ("成都市", "绵阳市", "广元市", "自贡市", "达州市", "广安市", "雅安市",
                 "高新技术产业开发区", "高新技术开发区", "高新区", "经开区", "新区", "工业园区",
                 "自治区", "自治州", "地区", "市", "省", "县", "区",
                 "有限公司", "有限责任公司", "政府采购", "项目", "工程", "建设"):
        name = name.replace(drop, "")
    # 提取连续中文片段(≥2字)
    segs = _re.findall(r"[\u4e00-\u9fa5]{2,}", name)
    # 过滤机构/场所名(如「自然资源局」「财政局」), 避免采购人机构名全量误配
    segs = [s for s in segs if not s.endswith(_INSTITUTION_SUFFIX)]
    return segs[:3]


def _similar_score(a: dict, b: dict) -> tuple:
    """两个项目上下文的相似度(评分 + 强相关标记)。

    相似项目判定核心 = 业务本质相同(类别一致) + 同地域(市/区县)。
    触达网络只推荐 同类别 + 同市/同区县 的项目(范围收敛, 不跨市), 否则范围太广。
    例: 成都市双流区的地灾项目只相似于成都本地的地灾项目, 不会相似于绵阳/攀枝花的。

    规则:
      - 类别相同: +3(必备)
      - 同区县: 强相关必备 +3(精确)
      - 同市(不同区县): +2(同城兜底, 区县数据缺失时)
      - 省相同但市不同: 不算分(太宽泛)
      - 项目名核心词命中: +1
    返回 (score, strong): strong = 类别相同 且(同区县 或 同市)。
    """
    import re as _re
    score = 0
    strong = False
    # 类别是相似的核心
    if a["category"] and a["category"] == b["category"]:
        score += 3
        # 同地域是强相关必备: 同区县(精确) 或 同市(兜底)
        same_county = a["county"] and a["county"] == b["county"]
        same_city = a["city"] and a["city"] == b["city"]
        if same_county:
            score += 3
            strong = True
        elif same_city:
            score += 2
            strong = True
        # 市/县均无法比对(数据缺失)时: 不判定相似, 防范围过广
    # 名称核心词
    if a["name_kw"] and b.get("name_kw") and a["name_kw"] == b["name_kw"] and a["name_kw"] not in ("", "项目"):
        score += 1
    return score, strong


@router.get("/{project_id}/related-network")
async def project_related_network(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """项目人脉关联网络 — 以项目为中心, 自动关联相似项目/参与单位/关键人员/触达路径。

    返回:
      related_projects: 做过相似/相关项目的历史项目(同类别或同地域)
      related_companies: 相关单位(相似项目参与单位, 含角色)
      key_persons: 关键人员(相似项目参与者), 每个含触达路径:
        - 共同参与项目
        - 任职单位(可直接联系)
        - 人脉边(NetworkEdge)中转: 该人员认识谁, 谁可引荐
        - 公开渠道(电话/邮箱, 仅内部可见)
    """
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    ctx = _project_ctx(project)

    # 1) 相似项目: 要求「类别相同」(强相关, 业务本质一致)的其他项目。
    #    同省不算相似(太宽泛), 同市/同县辅助加分。
    #    例: 地质勘察项目只和地质勘察项目相似, 不会和生态修复/路灯治理项目相似。
    all_projs = db.execute(
        select(Project).where(Project.is_deleted == False, Project.id != project_id)
    ).scalars().all()
    similar = []
    for p in all_projs:
        pc = _project_ctx(p)
        score, strong = _similar_score(ctx, pc)
        if strong:  # 必须类别相同
            similar.append((p, score))
    # 按相似度(同类别优先)+ 更新时间排序
    similar.sort(key=lambda x: (-x[1], x[0].updated_at or datetime.min))
    similar = [p for p, _s in similar[:10]]

    rel_projects = []
    for p in similar:
        ext = p.ext_attrs or {}
        cat = ext.get("category") or ""
        rel_projects.append({
            "id": p.id, "name": p.name, "status": p.status, "status_zh": _zh_status(p.status),
            "province": ext.get("province") or "", "city": ext.get("city") or "",
            "category": cat, "category_zh": _zh_category(cat),
        })

    # 2) 相关单位: 相似项目参与单位(按角色聚合)
    sim_ids = [p.id for p in similar]
    companies: dict[int, dict] = {}
    if sim_ids:
        rows = db.execute(
            select(ProjectCompany, Company)
            .join(Company, Company.id == ProjectCompany.company_id)
            .where(ProjectCompany.project_id.in_(sim_ids), ProjectCompany.is_active == True)
        ).all()
        for pc, co in rows:
            d = companies.setdefault(co.id, {
                "id": co.id, "name": co.name, "province": co.province or "",
                "company_type": co.company_type or "", "roles": {}, "projects": [],
            })
            d["roles"][pc.role] = d["roles"].get(pc.role, 0) + 1
            d["projects"].append(pc.project_id)
    # 排序: 参与相似项目多的单位优先
    rel_companies = sorted(companies.values(), key=lambda x: len(x["projects"]), reverse=True)[:12]
    for d in rel_companies:
        d["roles_display"] = "、".join([f"{_zh_role(r)}×{n}" for r, n in d["roles"].items()])

    # 3) 关键人员: 相似项目参与人员 + 触达路径
    persons: dict[int, dict] = {}
    if sim_ids:
        rows = db.execute(
            select(ProjectMember, Person, Company)
            .join(Person, Person.id == ProjectMember.person_id)
            .outerjoin(Company, Company.id == Person.company_id)
            .where(ProjectMember.project_id.in_(sim_ids), ProjectMember.is_active == True)
        ).all()
        for pm, person, co in rows:
            d = persons.setdefault(person.id, {
                "id": person.id, "name": person.name,
                "position": person.position or "", "phone": person.phone or "", "email": person.email or "",
                "company_id": person.company_id, "company_name": co.name if co else "",
                "project_ids": [], "project_names": [], "roles": {},
            })
            d["project_ids"].append(pm.project_id)
            d["roles"][pm.role] = d["roles"].get(pm.role, 0) + 1

    # 人脉边: 该人员认识的关键联系人(引荐路径)
    pids = list(persons.keys())
    edge_rows = []
    if pids:
        edge_rows = db.execute(
            select(NetworkEdge).where(
                or_(
                    and_(NetworkEdge.src_type == "person", NetworkEdge.src_id.in_(pids)),
                    and_(NetworkEdge.tgt_type == "person", NetworkEdge.tgt_id.in_(pids)),
                ),
                NetworkEdge.is_deleted == False,
            )
        ).scalars().all()

    rel_persons = []
    proj_name_map = {p.id: p.name for p in similar}
    for pid, d in persons.items():
        d["project_names"] = [proj_name_map.get(i, "") for i in d["project_ids"]]
        d["roles_display"] = "、".join([f"{_zh_role(r)}×{n}" for r, n in d["roles"].items()])
        # 触达路径
        paths = []
        if d["company_name"]:
            paths.append(f"任职于「{d['company_name']}」，可直接致电/拜访")
        for pn in d["project_names"]:
            if pn:
                paths.append(f"参与过相似项目《{pn}》")
        # 人脉边引荐: 该人员→其他人
        referral = []
        for e in edge_rows:
            if e.src_type == "person" and e.src_id == pid and e.tgt_type == "person":
                referral.append((e.tgt_name or "", e.rel_zh or e.rel_type))
            elif e.tgt_type == "person" and e.tgt_id == pid and e.src_type == "person":
                referral.append((e.src_name or "", e.rel_zh or e.rel_type))
        # 去重
        seen = set()
        for name, rel in referral:
            if name and name != d["name"] and (name, rel) not in seen:
                seen.add((name, rel))
                paths.append(f"人脉中转：认识「{name}」({rel})，可请其引荐")
        if d["phone"]:
            paths.append(f"公开渠道：电话 {d['phone']}")
        if d["email"]:
            paths.append(f"公开渠道：邮箱 {d['email']}")
        d["contact_paths"] = paths[:6]
        rel_persons.append(d)

    return {
        "success": True,
        "project": {"id": project.id, "name": project.name, "ctx": ctx},
        "related_projects": rel_projects,
        "related_companies": rel_companies,
        "key_persons": rel_persons,
    }
