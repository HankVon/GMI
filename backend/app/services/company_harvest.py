"""企业库扩充服务 — 从既有业务数据(bid_notice 供应商/采购人)提取未匹配企业名自动建档。

对应指导文档: docs/gmi-renovation-guide.md E-4「内网私有数据优先 + 公共数据补充」/ B2

背景: 行业采集(industry_crawler)落库要求命中 company 库; 而公司库若未覆盖外部公示
企业则命中率为 0。本服务把业务数据(bid_notice 中标供应商/业主等)中出现的、尚未建档的
企业名称自动建档并回填关联(purchaser_company_id / supplier_company_id), 提升后续
行业采集命中率与 360° 关联完整度。

规则:
  - 仅对企业名称建档(尾缀 有限/股份/集团/公司), 政府机关/事业单位(采购人常见)跳过
  - 名称规范化匹配已有单位(复用 intent_crawler._match_unit_to_company), 命中则复用
  - 编码: AUTO-时间戳-序号(与现有 AUTO- 前缀约定一致)
  - 建档后实时同步 Neo4j(失败降级不影响主流程)
"""
import logging
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.bid_notice import BidNotice
from app.services import neo4j_sync
from app.services.intent_crawler import _match_unit_to_company

logger = logging.getLogger("company_harvest")

# 机关/事业单位关键词(采购人/业主常见, 不应作为公司建档)
_ORG_KW = (
    "人民政府", "发展和改革委员会", "发展改革委", "自然资源局", "自然资源厅", "自然资源和规划局",
    "生态环境局", "生态环境厅", "水利局", "水利厅", "住建局", "住房和城乡建设局",
    "财政局", "交通局", "教育局", "卫生健康委员会", "林业和草原局", "农业农村局",
    "委员会", "办公室", "管理站", "管理处", "服务中心", "服务中心",
    "学校", "医院", "支队", "大队", "中队", "交易中心", "公共资源交易",
    "人民法院", "人民检察院", "管理局", "监管局", "审计局", "统计局",
    "机关", "事务局", "人民政府办公厅", "应急管理局",
)
# 企业名称尾缀(建档判断)
_COMPANY_SUFFIX_RE = re.compile(
    r"(有限责任公司|股份有限公司|集团有限公司?|有限公司|矿业公司|公司)$"
)


def is_enterprise_name(name: str) -> bool:
    """判断名称是否为企业(含企业尾缀且非机关/事业单位)。"""
    n = (name or "").strip()
    if len(n) < 6 or len(n) > 250:
        return False
    if not re.search(r"[\u4e00-\u9fa5]{2,}", n):
        return False
    if any(k in n for k in _ORG_KW):
        return False
    return bool(_COMPANY_SUFFIX_RE.search(n))


def _gen_code(db: Session) -> str:
    """生成唯一企业编码: AUTO-时间戳-序号。"""
    ts = datetime.now().strftime("%y%m%d%H%M%S")
    seq = 0
    while True:
        code = f"AUTO-{ts}-{seq}"
        exists = db.execute(select(Company).where(Company.code == code)).scalar_one_or_none()
        if not exists:
            return code
        seq += 1


def harvest_company(db: Session, name: str, region: str | None = None,
                    source_note: str = "") -> tuple:
    """按企业名称建档(已存在则复用)。

    返回 (company|None, how): how ∈ created/matched/skipped。
    """
    n = (name or "").strip()
    if not is_enterprise_name(n):
        return None, "skipped"
    m = _match_unit_to_company(db, n)
    if m:
        return db.get(Company, m["company_id"]), "matched"
    c = Company(
        code=_gen_code(db),
        name=n[:250],
        short_name=None,
        company_type=None,
        province=(region or None),
        city=None,
        ext_attrs={"harvested": True, "harvest_source": source_note[:200], "harvested_at": datetime.now().isoformat(timespec="seconds")},
    )
    db.add(c)
    db.flush()
    try:
        neo4j_sync.sync_company(
            c.id, c.name, code=c.code or "", company_type="",
            province=c.province or "", city=c.city or "",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("[harvest] Neo4j 同步失败(已降级): %s", e)
    return c, "created"


def harvest_bid_companies(db: Session, max_new: int = 500) -> dict:
    """从 bid_notice 未匹配供应商/采购人建档并回填关联。

    幂等: 已建档/已回填的公告下次跳过。
    """
    stats = {"created": 0, "matched": 0, "skipped": 0,
             "linked_supplier": 0, "linked_purchaser": 0, "notices": 0}
    notices = db.execute(
        select(BidNotice).where(BidNotice.is_deleted == False)
    ).scalars().all()
    stats["notices"] = len(notices)
    for n in notices:
        if stats["created"] >= max_new:
            break
        # 采购人(业主)
        if n.purchaser and not n.purchaser_company_id:
            c, how = harvest_company(db, n.purchaser, region=n.region,
                                     source_note=f"bid_notice:{n.id}:purchaser")
            if how == "created":
                n.purchaser_company_id = c.id
                stats["linked_purchaser"] += 1
            elif how == "matched":
                n.purchaser_company_id = c.id
            stats[how] += 1
        # 中标供应商(meta.suppliers)
        meta = dict(n.meta or {})
        suppliers = meta.get("suppliers") or []
        for s in suppliers:
            if not isinstance(s, dict):
                continue
            sn = (s.get("supplier") or "").strip()
            if sn and not s.get("supplier_company_id"):
                c, how = harvest_company(db, sn, region=n.region,
                                         source_note=f"bid_notice:{n.id}:supplier")
                if how in ("created", "matched") and c:
                    s["supplier_company_id"] = c.id
                    n.meta = meta
                    stats["linked_supplier"] += 1
                stats[how] += 1
    db.commit()
    return stats
