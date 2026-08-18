"""将 SSM 系统中的人员清单导入 Neo4j 知识图谱。

运行: D:\\anaconda\\python.exe scripts/import_persons_to_neo4j.py

功能:
  1. 读取 MySQL person 表(未删除、启用)与 company 表
  2. 在 Neo4j 中幂等创建 Person 节点(以 person_id 为唯一键, MERGE)
  3. 为有所属单位的人员创建 Company 节点 + WORKS_AT 关系
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase
from sqlalchemy import create_engine, text
from app.config import settings

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j19991220")


def load_persons():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, code, name, email, phone, company_id, department_id, position, status, "
                "entry_date, resign_date, is_active "
                "FROM person WHERE is_deleted = 0"
            )
        ).mappings().all()
        companies = conn.execute(
            text("SELECT id, name FROM company WHERE is_deleted = 0")
        ).mappings().all()
    company_names = {c["id"]: c["name"] for c in companies}
    return rows, company_names


def import_to_neo4j(rows, company_names):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            for r in rows:
                props = {
                    "person_id": int(r["id"]),
                    "code": r["code"] or "",
                    "name": r["name"] or "",
                    "position": r["position"] or "",
                    "status": r["status"] or "active",
                    "email": r["email"] or "",
                    "phone": r["phone"] or "",
                    "company_id": int(r["company_id"]) if r["company_id"] else None,
                    "department_id": int(r["department_id"]) if r["department_id"] else None,
                    "is_active": bool(r["is_active"]),
                }
                session.execute_write(
                    lambda tx: tx.run(
                        """
                        MERGE (p:Person {person_id: $person_id})
                        SET p.code = $code,
                            p.name = $name,
                            p.position = $position,
                            p.status = $status,
                            p.email = $email,
                            p.phone = $phone,
                            p.company_id = $company_id,
                            p.department_id = $department_id,
                            p.is_active = $is_active,
                            p.updated_at = datetime()
                        """,
                        **props,
                    )
                )
                # 所属单位: 建 Company 节点 + WORKS_AT 关系
                cid = props["company_id"]
                if cid and cid in company_names:
                    session.execute_write(
                        lambda tx: tx.run(
                            """
                            MERGE (c:Company {company_id: $company_id})
                            SET c.name = $company_name, c.updated_at = datetime()
                            WITH c
                            MATCH (p:Person {person_id: $person_id})
                            MERGE (p)-[w:WORKS_AT]->(c)
                            SET w.updated_at = datetime()
                            """,
                            company_id=cid,
                            company_name=company_names[cid],
                            person_id=int(r["id"]),
                        )
                    )
        # 统计
        with driver.session() as session:
            p = session.run("MATCH (p:Person) RETURN count(p) AS n").single()["n"]
            c = session.run("MATCH (c:Company) RETURN count(c) AS n").single()["n"]
            w = session.run("MATCH ()-[w:WORKS_AT]->() RETURN count(w) AS n").single()["n"]
            print(f"Neo4j 现状: Person={p}, Company={c}, WORKS_AT={w}")
    finally:
        driver.close()


def main():
    rows, company_names = load_persons()
    print(f"从 MySQL 读取人员 {len(rows)} 条")
    import_to_neo4j(rows, company_names)
    print("导入完成")


if __name__ == "__main__":
    main()
