"""将 MySQL 存量数据全量回填到 Neo4j 知识图谱(幂等)。

运行: D:\\anaconda\\python.exe scripts/backfill_neo4j.py

覆盖:
  - Person / Company / Project 三类节点
  - (Person)-[:WORKS_AT]->(Company)
  - (Person)-[:PARTICIPATES_IN]->(Project)
  - (Company)-[:PARTICIPATES_IN]->(Project)
  - (Person)-[:COLLABORATED_WITH]->(Person)  同项目两两合作(双向)
  - (Entity)-[:IN_REGION]->(Region)          实体区域挂载(公司/项目/人员, 有省市县时)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings
from app.services.neo4j_sync import (
    sync_person, sync_company, sync_project,
    sync_project_members, sync_project_companies,
    sync_company_colleagues,
)


def _extract_region_from_text(text: str) -> dict:
    """从文本(项目名)提取 省/市/县 核心词。项目 ext_attrs 常缺地域, 用项目名兜底。

    匹配策略:
      - 县级: 「核心词后跟 县/区/市/旗 后缀」或核心词本身带后缀。用右边界避免
        嵌字误判——「安居房」的「安居」后跟「房」不算行政区(不误挂遂宁安居县),
        而「得荣县」的「得荣」后跟「县」正确命中。注意不能像左边界 `(?<![\u4e00-\u9fa5])`
        那样要求地名前非中文——真实项目名里地名前常紧跟「省/州/市」(如「甘孜州得荣县」),
        左边界会全部漏掉导致只挂省级。
      - 市级: 子串匹配(市级词多 2 字且后缀多样, 子串可接受)。
    """
    import re as _re
    from app.services.china_regions import REGION_COUNTIES, _CITY_OF, TARGET_PROVINCES, extract_target_province
    if not text:
        return {"province": "", "city": "", "county": ""}
    prov = extract_target_province(text)
    # 县级: 右边界(核心词后跟区划后缀, 或核心词本身带后缀)
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
    # 市级: 子串匹配
    city = ""
    for c, p in _CITY_OF.items():
        if p in TARGET_PROVINCES and c in text:
            city = c
            break
    return {"province": prov, "city": city, "county": county}


def main():
    engine = create_engine(settings.DATABASE_URL)
    # 先删除全部 Region 节点(连带 IN_REGION/BELONGS_TO 边), 彻底清理自环/孤立/多级残留,
    # 由本轮 sync_entity_region 按「市/县同名防自环」逻辑幂等重建。
    from app.services.neo4j_sync import _get_driver
    driver = _get_driver()
    if driver:
        with driver.session() as s:
            s.run("MATCH (r:Region) DETACH DELETE r")
        print("已清理全部 Region 节点与边")
    else:
        print("Neo4j 不可用, 跳过清理")
    with engine.connect() as conn:
        # ── 孤儿节点清理: 删除图谱中 MySQL 已软删/不存在的实体(幂等) ──
        # 场景: 直接改数据库软删、或 API 删除时 Neo4j 熔断降级, 都会造成图谱残留。
        # backfill 只做增量同步, 若不清理, 软删实体将永久留在图谱。
        if driver:
            with driver.session() as s:
                for label, key, table in [
                    ("Person", "person_id", "person"),
                    ("Project", "project_id", "project"),
                    ("Company", "company_id", "company"),
                ]:
                    active_ids = [r[0] for r in conn.execute(text(f"SELECT id FROM {table} WHERE is_deleted=0")).fetchall()]
                    if not active_ids:
                        continue
                    r = s.run(
                        f"MATCH (n:{label}) WHERE n.{key} IS NOT NULL AND NOT n.{key} IN $ids "
                        f"WITH n LIMIT 2000 DETACH DELETE n RETURN count(n) AS deleted",
                        ids=active_ids,
                    ).single()
                    if r and r["deleted"]:
                        print(f"已清理孤儿 {label}: {r['deleted']} 个")
            print("孤儿节点清理完成")

        # 单位(先查, 供人员公司名/区域使用)
        comp_rows = conn.execute(text(
            "SELECT id, name, code, company_type, province, city FROM company WHERE is_deleted=0"
        )).mappings().all()
        companies = {c["id"]: c["name"] for c in comp_rows}
        # 公司区域: 列优先, 公司名兜底
        company_regions = {}
        for c in comp_rows:
            crg = _extract_region_from_text(c["name"] or "")
            company_regions[c["id"]] = (
                c["province"] or crg["province"],
                c["city"] or crg["city"],
                crg["county"],
            )

        # 人员
        persons = conn.execute(text(
            "SELECT id, name, position, status, email, phone, company_id, is_active "
            "FROM person WHERE is_deleted=0"
        )).mappings().all()
        for p in persons:
            cprov, ccity, ccounty = company_regions.get(p["company_id"], ("", "", "")) if p["company_id"] else ("", "", "")
            sync_person(
                person_id=int(p["id"]), name=p["name"] or "", position=p["position"] or "",
                status=p["status"] or "active", company_id=int(p["company_id"]) if p["company_id"] else None,
                company_name=companies.get(p["company_id"], ""),
                email=p["email"] or "", phone=p["phone"] or "", is_active=bool(p["is_active"]),
                province=cprov, city=ccity, county=ccounty,
            )
        print(f"已同步人员 {len(persons)} 条")

        # 单位(带区域挂载; 列缺失时公司名兜底)
        for c in comp_rows:
            crg = _extract_region_from_text(c["name"] or "")
            sync_company(int(c["id"]), c["name"] or "", code=c["code"] or "",
                         company_type=c["company_type"] or "",
                         province=c["province"] or crg["province"],
                         city=c["city"] or crg["city"], county=crg["county"])
        print(f"已同步单位 {len(comp_rows)} 条")

        # 同事关系: 按单位分组, 同单位人员两两建立 COLLEAGUE
        by_company: dict[int, list] = {}
        for p in persons:
            if p["company_id"]:
                by_company.setdefault(int(p["company_id"]), []).append(
                    {"person_id": int(p["id"]), "name": p["name"] or ""}
                )
        for cid, plist in by_company.items():
            sync_company_colleagues(cid, plist)
        print(f"已同步同事关系 {len(by_company)} 个单位")

        # 项目 + 成员 + 单位参与
        projects = conn.execute(text(
            "SELECT id, name, code, status, ext_attrs FROM project WHERE is_deleted=0"
        )).mappings().all()
        for pr in projects:
            ext = pr["ext_attrs"] or {}
            # 地域: ext_attrs 优先, 项目名兜底(常缺)
            rg = _extract_region_from_text(pr["name"] or "")
            province = ext.get("province", "") if isinstance(ext, dict) else ""
            city = ext.get("city", "") if isinstance(ext, dict) else ""
            county = ext.get("county", "") if isinstance(ext, dict) else ""
            province = province or rg["province"]
            city = city or rg["city"]
            county = county or rg["county"]
            sync_project(int(pr["id"]), pr["name"] or "", code=pr["code"] or "",
                         status=pr["status"] or "active",
                         category=ext.get("category", "") if isinstance(ext, dict) else "",
                         province=province, city=city, county=county)

            member_rows = conn.execute(text(
                "SELECT pm.person_id, p.name AS pname, pm.role, p.company_id "
                "FROM project_member pm JOIN person p ON pm.person_id=p.id "
                "WHERE pm.project_id=:pid AND pm.is_active=1 AND pm.is_deleted=0 AND p.is_deleted=0"
            ), {"pid": int(pr["id"])}).mappings().all()
            members = [{"person_id": int(m["person_id"]), "name": m["pname"] or "",
                        "role": m["role"] or "member",
                        "company_id": int(m["company_id"]) if m["company_id"] else None}
                       for m in member_rows]
            sync_project_members(int(pr["id"]), members)

            comp_rows2 = conn.execute(text(
                "SELECT pc.company_id, c.name AS cname, pc.role "
                "FROM project_company pc JOIN company c ON pc.company_id=c.id "
                "WHERE pc.project_id=:pid AND pc.is_active=1 AND pc.is_deleted=0 AND c.is_deleted=0"
            ), {"pid": int(pr["id"])}).mappings().all()
            comps = [{"company_id": int(cc["company_id"]), "name": cc["cname"] or "",
                      "role": cc["role"] or ""} for cc in comp_rows2]
            sync_project_companies(int(pr["id"]), comps)
        print(f"已同步项目 {len(projects)} 条")
    print("回填完成")


if __name__ == "__main__":
    main()
