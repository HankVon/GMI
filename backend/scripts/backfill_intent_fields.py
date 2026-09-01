"""回填 intent_notice / opportunity 的空缺字段(金额/联系人/西藏地市)。

策略:
  - 仅填充 NULL 字段, 绝不覆盖已有人工策展数据。
  - 抽取正则与 intent_crawler.py 的改进版保持一致(金额/联系人/西藏地市)。
  - 纯 SQL + 纯 Python 正则, 规避 Py3.14 下 ORM 模型类定义不兼容问题。
  - opportunity 通过 source='intent-notice-{id}' 关联回 intent_notice。
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://ssm_user:ssm_pass@127.0.0.1:3306/ssm?charset=utf8mb4",
)
from sqlalchemy import create_engine, text

ENGINE = create_engine(os.environ["DATABASE_URL"])

# ── 改进版抽取(与 intent_crawler.py 保持一致) ──
_AMOUNT_RE = re.compile(
    r"(?:总投资|投资[总估]?额?|估算[总]?投资|项目总投资|预算[金额]*|概算[投资]*|采购预算|"
    r"起始价|挂牌起始价|出让起始价|出让收益|中标价|中标金额|合同[总]?价|合同金额)"
    r"[约\s]*[:：]?\s*(?:人民币)?\s*(?:¥|￥)?\s*([\d,，.]+)\s*(?:亿|万元?|万)"
)
_CONTACT_RE = re.compile(
    r"(?:联系人|联系电话|联系单位|联系部门|代理机构|招标代理|出让人|受让人|咨询电话|业务咨询)[：:]\s*"
    r"((?:[^\n]|[\n\r]){2,200}?)(?=\n[一二三四五六七八九十]+、|\n\s*[A-Z]|\n\s*$|\Z)"
)
_XZ_CITY = ["拉萨", "日喀则", "昌都", "林芝", "山南", "那曲", "阿里"]
_XZ_COUNTY = {
    "拉萨": ["城关", "堆龙德庆", "达孜", "林周", "尼木", "曲水", "墨竹工卡", "当雄"],
    "日喀则": ["桑珠孜", "南木林", "江孜", "定日", "萨迦", "拉孜", "昂仁", "谢通门", "白朗", "仁布", "康马", "定结", "仲巴", "亚东", "吉隆", "聂拉木", "萨嘎", "岗巴"],
    "昌都": ["卡若", "江达", "贡觉", "类乌齐", "丁青", "察雅", "八宿", "左贡", "芒康", "洛隆", "边坝"],
    "林芝": ["巴宜", "工布江达", "米林", "墨脱", "波密", "察隅", "朗县"],
    "山南": ["乃东", "扎囊", "贡嘎", "桑日", "琼结", "曲松", "措美", "洛扎", "加查", "隆子", "错那", "浪卡子"],
    "那曲": ["色尼", "嘉黎", "比如", "聂荣", "安多", "申扎", "索县", "班戈", "巴青", "尼玛", "双湖"],
    "阿里": ["噶尔", "普兰", "札达", "日土", "革吉", "改则", "措勤"],
}


def parse_amount(text: str):
    if not text:
        return None
    if any(k in text for k in ("会议", "调度", "座谈", "专题会", "调研", "培训", "讲话", "致辞")):
        return None
    for m in _AMOUNT_RE.finditer(text):
        num = float(m.group(1).replace(",", "").replace("，", ""))
        unit = "万" if "亿" not in m.group(0) else "亿"
        return round(num * (10000 if unit == "亿" else 1), 2)
    return None


def parse_contact(text: str) -> str:
    if not text:
        return ""
    m = _CONTACT_RE.search(text)
    if m:
        out = re.sub(r"\s+", " ", m.group(1)).strip()
        phone = re.search(r"(?:[0-9]{3,4}-?[0-9]{7,8}|[0-9]{8,12}|1[3-9]\d{9})", out)
        if phone:
            return out[: phone.start() + 40][:160]
        return out[:60]
    return ""


def parse_xz_city(text: str) -> str:
    for counties in _XZ_COUNTY.values():
        for ct in counties:
            if ct in text:
                for city, cs in _XZ_COUNTY.items():
                    if ct in cs:
                        return city
    for c in _XZ_CITY:
        if c in text:
            return c
    return ""


def main():
    with ENGINE.begin() as c:
        # 1) intent_notice 空缺补全
        rows = c.execute(text(
            "SELECT id, raw_text, province, city, amount, contact FROM intent_notice "
            "WHERE is_deleted=0 AND raw_text IS NOT NULL AND raw_text<>'' "
            "AND (amount IS NULL OR contact IS NULL "
            "OR (province='西藏' AND (city IS NULL OR city='')))"
        )).mappings().all()
        u_amt = u_con = u_city = 0
        for r in rows:
            raw = r["raw_text"] or ""
            amt = parse_amount(raw) if r["amount"] is None else None
            con = parse_contact(raw) if (r["contact"] is None or r["contact"] == "") else None
            xz = parse_xz_city(raw) if (r["province"] == "西藏" and (r["city"] is None or r["city"] == "")) else None
            if amt is not None:
                c.execute(text("UPDATE intent_notice SET amount=:a WHERE id=:i"), {"a": amt, "i": r["id"]})
                u_amt += 1
            if con:
                c.execute(text("UPDATE intent_notice SET contact=:cc WHERE id=:i"), {"cc": con, "i": r["id"]})
                u_con += 1
            if xz:
                c.execute(text("UPDATE intent_notice SET city=:cc WHERE id=:i"), {"cc": xz, "i": r["id"]})
                u_city += 1
        print(f"[intent_notice] 回填 amount={u_amt}, contact={u_con}, 西藏city={u_city} (扫描 {len(rows)} 行)")

        # 2) opportunity 经 source 关联回填(仅填空)
        rows = c.execute(text(
            "SELECT o.id, o.amount_wan, o.contact_summary, o.region_city, o.region_province, "
            "i.amount, i.contact, i.city, i.county "
            "FROM opportunity o "
            "LEFT JOIN intent_notice i ON i.id = CAST(SUBSTRING_INDEX(o.source, '-', -1) AS UNSIGNED) "
            "WHERE o.source LIKE 'intent-notice-%'"
        )).mappings().all()
        o_amt = o_con = o_city = 0
        for r in rows:
            if r["amount_wan"] is None and r["amount"] is not None:
                c.execute(text("UPDATE opportunity SET amount_wan=:a WHERE id=:i"),
                          {"a": int(r["amount"]), "i": r["id"]})
                o_amt += 1
            if (r["contact_summary"] is None or r["contact_summary"] == "") and r["contact"]:
                c.execute(text("UPDATE opportunity SET contact_summary=:cc WHERE id=:i"),
                          {"cc": (r["contact"] or "")[:500], "i": r["id"]})
                o_con += 1
            if (r["region_city"] is None or r["region_city"] == "") and r["region_province"] == "西藏" and (r["city"] or r["county"]):
                c.execute(text("UPDATE opportunity SET region_city=:cc WHERE id=:i"),
                          {"cc": r["city"] or r["county"], "i": r["id"]})
                o_city += 1
        print(f"[opportunity] 回填 amount_wan={o_amt}, contact_summary={o_con}, 西藏region_city={o_city} (扫描 {len(rows)} 行)")


if __name__ == "__main__":
    main()
    print("回填完成")
