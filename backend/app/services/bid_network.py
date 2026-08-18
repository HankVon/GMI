"""中标公告解析与人脉图谱服务 — 需求2: 基于已挂网的中标数据建立人脉网络。

链路:
  1. 扫描 web_clue 中标公告(标题含 中标/成交/结果公告, meta 含 procurement_result)
  2. 解析: 采购人(purchaser) / 中标供应商(meta.procurement_result[].supplier) / 金额/地址/时间
  3. 按名称匹配公司表(完整名 → 核心名), 得到 purchaser_company_id / supplier_company_id
  4. 写 bid_notice 表(幂等: 同 clue_id 覆盖)
  5. 同步 Neo4j: Bid 节点 + Company-[:WON_BID]->Bid + Company-[:IS_PURCHASER]->Bid,
     形成「内部公司 → 中标 → 采购人(潜在业主)」与「内部公司(业主) ← 中标 ← 供应商(潜在施工方)」人脉网

说明: 匹配采用名称完整/核心名双向判断, 未匹配的公司不建节点(避免污染图谱)。
"""
import datetime
import json
import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.web_clue import WebClue
from app.models.company import Company
from app.models.bid_notice import BidNotice
from app.services.neo4j_sync import _run, _get_driver
from app.services.china_regions import extract_target_province, is_target_province, TARGET_PROVINCES

logger = logging.getLogger("bid_network")

# 中标公告标题特征
_BID_TITLE_PATTERN = re.compile(r"中标|成交|结果公告|评审结果")
# 供应商字段里常有的前缀/后缀噪音
_SUPPLIER_NOISE = (
    "牵头供应商", "投标联合体", "中标供应商", "成交供应商", "预中标人",
    "第一中标候选人", "第二中标候选人", "第三中标候选人",
)


def _is_bid_clue(clue: WebClue) -> bool:
    """是否中标公告线索。"""
    title = clue.title or ""
    if not _BID_TITLE_PATTERN.search(title):
        return False
    return True


def _clue_meta(clue: WebClue) -> dict:
    if isinstance(clue.meta, dict):
        return clue.meta
    if isinstance(clue.meta, str):
        try:
            return json.loads(clue.meta)
        except Exception:
            return {}
    return {}


def _clean_supplier(raw: str) -> str:
    """清理供应商名称: 去「牵头供应商:」等前缀与「投标联合体:...」后缀。"""
    s = (raw or "").strip()
    for noise in _SUPPLIER_NOISE:
        s = s.replace(noise, "").replace(f"{noise}：", "").replace(f"{noise}:", "")
    # 取冒号后第一段(多个供应商时)
    if "：" in s:
        s = s.split("：")[1].strip()
    elif ":" in s:
        s = s.split(":")[1].strip()
    # 去「投标联合体:xxx」部分
    s = re.split(r"投标联合体[:：]", s)[0].strip()
    return s


def _name_match(unit_name: str, target: str) -> bool:
    """公司名匹配: 完整名 / 核心名(去省市县前缀) 双向判断。"""
    if not target:
        return False
    a = unit_name.replace(" ", "")
    b = target.replace(" ", "")
    if a == b:
        return True
    # 核心名: 去 省/市/县/区 前缀
    def core(n: str) -> str:
        return re.sub(r"^(?:[\u4e00-\u9fa5]{2,6}(?:省|市|县|区|自治区|自治州|地区|旗|州))", "", n)
    ca, cb = core(a), core(b)
    if ca and cb:
        if ca == cb:
            return True
        # 一方包含另一方(长度>=4)
        if len(ca) >= 4 and (ca in cb or cb in ca):
            return True
    return False


def _find_company(db: Session, name: str) -> Optional[Company]:
    """按名称在 company 表匹配(严格), 返回公司或 None。

    匹配规则(防误配):
      1. 完整名完全一致
      2. 带区划词的核心匹配: 目标名称的「区划词 + 机构类型词」与候选完全一致
         (普兰县住房和城乡建设局 → 必须同时含「普兰」+「住房和城乡建设局」,
         避免达日/德江等任何同后缀局误配)
      3. 禁止无条件包含匹配
    """
    if not name:
        return None
    name = name.strip()
    # 1) 完整名精确
    comp = db.execute(
        select(Company).where(Company.name == name, Company.is_deleted == False).limit(1)
    ).scalar_one_or_none()
    if comp:
        return comp
    # 2) 提取目标名的区划词(普兰/达日/德江...) 与 机构核心词(住房和城乡建设局)
    region = re.search(r"([\u4e00-\u9fa5]{2,4}(?:省|市|县|区|旗|州))", name)
    core = re.sub(r"^(?:[\u4e00-\u9fa5]{2,6}(?:省|市|县|区|自治区|自治州|地区|旗|州))", "", name)
    if len(core) < 5:
        return None
    region_word = region.group(1) if region else ""
    companies = db.execute(
        select(Company).where(Company.is_deleted == False)
    ).scalars().all()
    for c in companies:
        cname = c.name or ""
        if cname == name:
            return c
        if region_word and region_word not in cname:
            continue
        # 候选也去前缀后, 机构核心词一致
        c_core = re.sub(r"^(?:[\u4e00-\u9fa5]{2,6}(?:省|市|县|区|自治区|自治州|地区|旗|州))", "", cname)
        if c_core and c_core == core:
            return c
    return None


def _parse_amount(raw: str) -> Optional[str]:
    """从金额文本提取数字(元), 失败返回 None。"""
    if not raw:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)", raw.replace("，", ","))
    return m.group(1).replace(",", "") if m else None


def parse_bid_clues(db: Session, max_age_days: int = 730) -> dict:
    """扫描并解析 web_clue 中标公告, 写 bid_notice 表(幂等), 返回统计。

    max_age_days: 仅保留近 N 天(默认 730=近两年)的中标公告, 超期不纳入(需求)。
    地域过滤: 仅入库 四川/西藏/新疆 三地中标公告, 其他省份(全国站)公告跳过。
    """
    cutoff = datetime.datetime.now() - datetime.timedelta(days=max_age_days)
    clues = db.execute(
        select(WebClue).where(WebClue.is_deleted == False).order_by(WebClue.fetched_at.desc())
    ).scalars().all()

    parsed = 0
    skipped = 0
    matched_purchaser = 0
    matched_supplier = 0
    expired = 0
    region_skipped = 0
    errors = []

    for clue in clues:
        if not _is_bid_clue(clue):
            continue
        meta = _clue_meta(clue)
        purchaser = (meta.get("purchaser") or "").strip()
        # 全国站: purchaser; 四川站: 公告详情 meta 里 purchaser 也有
        region = (meta.get("region") or "").strip()
        notice_type = (meta.get("notice_type") or "").strip() or "中标（成交）公告"
        published_raw = (meta.get("published_at") or "").strip()
        published = None
        if published_raw:
            try:
                published = datetime.datetime.strptime(published_raw[:16], "%Y-%m-%d %H:%M")
            except Exception:  # noqa: BLE001
                try:
                    published = datetime.datetime.fromisoformat(published_raw.replace("Z", ""))
                except Exception:  # noqa: BLE001
                    published = None

        # 近两年过滤: 有发布时间且超过 2 年的公告不纳入(需求: 只保留近两年)
        if published and published < cutoff:
            expired += 1
            continue

        # 地域过滤: 仅四川/西藏/新疆
        # 权威来源 = 采购人名称+公告标题中的目标省/市/县地名(meta.region 不可靠,
        # 全国站公告 region 可能是站点级误标, 如「四川」但采购人实为惠州/舟山)
        name_text = f"{purchaser} {clue.title or ''}"
        target_prov = extract_target_province(name_text)
        if not target_prov:
            # 采购人/标题均无川藏新地名 → 跳过(全国站非目标公告)
            region_skipped += 1
            continue
        # region 字段归一化为目标省核心词(四川/西藏/新疆)
        region = target_prov

        # 代理机构提取(meta.agency 或公告正文中的「采购代理机构」)
        agency = (meta.get("agency") or "").strip()
        if not agency:
            m = re.search(r"(?:采购代理机构|采购代理)[：:]\s*([\u4e00-\u9fa5]{4,40}(?:公司|中心|所))", clue.content or "")
            if m:
                agency = m.group(1).strip()

        # 供应商列表(兼容字段错位: 全国站 procurement_result 的 supplier/amount/address 可能对调)
        suppliers = []
        for item in meta.get("procurement_result") or []:
            if not isinstance(item, dict):
                continue
            raw_supplier = _clean_supplier(item.get("supplier") or "")
            raw_amount = str(item.get("amount") or "").strip()
            raw_address = (item.get("address") or "").strip()
            # 若 supplier 字段像金额(纯数字/含(元)), 说明字段错位 → 尝试从 address/amount 提取供应商
            if re.fullmatch(r"[\d,，.]+(?:（元）|\(元\)|元)?", raw_supplier.replace("（元）", "").replace("(元)", "")):
                # address 里常是「青海兆仁建筑工程有限公司（评审总得分...）」
                cand = re.sub(r"（.*?）|\(.*?\)", "", raw_address).strip()
                if cand and not re.fullmatch(r"[\d,，.]+", cand):
                    raw_supplier = cand
                    raw_address = ""
            sname = raw_supplier
            if not sname:
                continue
            suppliers.append({
                "supplier": sname,
                "amount": _parse_amount(raw_amount) or _parse_amount(raw_supplier),
                "address": raw_address,
            })

        # 采购人/供应商按名称匹配公司
        purchaser_comp = _find_company(db, purchaser)
        for sp in suppliers:
            sp_comp = _find_company(db, sp["supplier"])
            sp["supplier_company_id"] = sp_comp.id if sp_comp else None

        # 幂等: 同 clue_id 覆盖
        existing = db.execute(
            select(BidNotice).where(BidNotice.clue_id == clue.id).limit(1)
        ).scalar_one_or_none()
        if existing:
            bn = existing
        else:
            bn = BidNotice(clue_id=clue.id)
            db.add(bn)
        bn.title = clue.title or ""
        bn.url = clue.url or ""
        bn.purchaser = purchaser or None
        bn.purchaser_company_id = purchaser_comp.id if purchaser_comp else None
        bn.region = region or None
        bn.notice_type = notice_type
        bn.agency = agency or None
        bn.source_name = clue.source_name or ""
        bn.published_at = published
        bn.meta = {"suppliers": suppliers}
        if purchaser_comp:
            matched_purchaser += 1
        for sp in suppliers:
            if sp.get("supplier_company_id"):
                matched_supplier += 1
        parsed += 1

    db.commit()
    return {
        "parsed": parsed,
        "skipped": skipped,
        "expired": expired,
        "region_skipped": region_skipped,
        "matched_purchaser": matched_purchaser,
        "matched_supplier": matched_supplier,
        "errors": errors,
    }


def sync_bid_graph(db: Session) -> dict:
    """把 bid_notice 数据同步到 Neo4j 图谱。

    节点: Bid {bid_id, title, published_at}
    关系: (Company)-[:WON_BID {amount}]->(Bid)   # 中标供应商
          (Company)-[:IS_PURCHASER]->(Bid)        # 采购人(业主)
    只对已匹配到内部公司的采购人/供应商建立关系, 避免外部公司污染图谱。
    幂等: 全量重建(MERGE + 关系重建)。
    """
    bids = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False).order_by(BidNotice.id)
    ).scalars().all()

    synced = 0
    rel_count = 0
    try:
        driver = _get_driver()
        for bn in bids:
            # 公司名缓存
            def comp_name(cid):
                if not cid:
                    return ""
                return db.execute(select(Company.name).where(Company.id == cid)).scalar_one_or_none() or ""

            suppliers = (bn.meta or {}).get("suppliers") or []
            pub = bn.published_at.strftime("%Y-%m-%d") if bn.published_at else ""
            with driver.session() as s:
                # 幂等: 删除旧 Bid 节点重建(关联关系自动清除)
                s.run("MATCH (b:Bid {bid_id: $bid}) DETACH DELETE b", bid=bn.id)
                s.run(
                    """
                    CREATE (b:Bid {bid_id: $bid, title: $title, published_at: $pub})
                    """,
                    bid=bn.id, title=bn.title or "", pub=pub,
                )
                # 采购人关系
                if bn.purchaser_company_id:
                    s.run(
                        """
                        MATCH (c:Company {company_id: $cid})
                        MATCH (b:Bid {bid_id: $bid})
                        MERGE (c)-[:IS_PURCHASER {name_zh: '采购人'}]->(b)
                        """,
                        cid=bn.purchaser_company_id, bid=bn.id,
                    )
                    rel_count += 1
                # 中标供应商关系
                for sp in suppliers:
                    scid = sp.get("supplier_company_id")
                    if not scid:
                        continue
                    s.run(
                        """
                        MATCH (c:Company {company_id: $cid})
                        MATCH (b:Bid {bid_id: $bid})
                        MERGE (c)-[r:WON_BID {name_zh: '中标'}]->(b)
                        SET r.amount = $amount, r.name_zh = '中标'
                        """,
                        cid=scid, bid=bn.id, amount=sp.get("amount") or "",
                    )
                    rel_count += 1
            synced += 1
    except Exception as e:  # noqa: BLE001
        logger.warning("中标图谱同步失败: %s", e)
        return {"synced": synced, "rel_count": rel_count, "error": str(e)}

    return {"synced": synced, "rel_count": rel_count}


def rebuild(db: Session) -> dict:
    """一键重建: 解析 + 图谱同步。"""
    r1 = parse_bid_clues(db)
    r2 = sync_bid_graph(db)
    return {"parse": r1, "graph": r2}
