"""补全 company 实体的企查查字段元数据（幂等，仅插入缺失字段）

运行: python -m scripts.seed_company_fields
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings


FIELDS = [
    ("legal_rep", "法定代表人", "text", "工商信息", 1, 0),
    ("establish_date", "成立日期", "date", "工商信息", 1, 1),
    ("oper_status", "经营状态", "text", "工商信息", 1, 2),
    ("reg_no", "注册号", "text", "工商信息", 0, 3),
    ("econ_kind", "企业类型", "text", "工商信息", 1, 4),
    ("belong_org", "登记机关", "text", "工商信息", 0, 5),
    ("registered_capital", "注册资本", "text", "工商信息", 1, 6),
    ("business_scope", "经营范围", "textarea", "工商信息", 0, 7),
]


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        existing = set(
            r[0]
            for r in conn.execute(
                text(
                    "SELECT field_key FROM field_metadata "
                    "WHERE entity_type='company' AND is_deleted=0"
                )
            ).fetchall()
        )
        for key, name, dtype, group, list_visible, sort in FIELDS:
            if key in existing:
                print(f"skip (exists): {key}")
                continue
            conn.execute(
                text(
                    "INSERT INTO field_metadata "
                    "(entity_type, field_key, display_name, data_type, group_name, "
                    "is_list_visible, is_searchable, is_filterable, is_exportable, "
                    "sort_order, status, is_deleted) "
                    "VALUES (:et, :fk, :dn, :dt, :grp, :lv, 0, 0, 1, :so, 'enabled', 0)"
                ),
                {
                    "et": "company",
                    "fk": key,
                    "dn": name,
                    "dt": dtype,
                    "grp": group,
                    "lv": list_visible,
                    "so": sort,
                },
            )
            print(f"insert: {key} ({name})")
        conn.commit()
    print("done")


if __name__ == "__main__":
    main()
