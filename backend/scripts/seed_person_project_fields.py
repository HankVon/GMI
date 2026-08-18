"""补全 person / project 实体的字段元数据，使其像 company 一样可在字段管理中管理（幂等）。

运行: python -m scripts.seed_person_project_fields
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings


# (entity_type, field_key, display_name, data_type, group_name,
#  is_list_visible, sort_order, option_set_code)
# data_type: text/textarea/number/money/date/select/switch/entity_ref
PERSON_FIELDS = [
    ("person", "email", "邮箱", "text", "基础信息", 1, 0, None),
    ("person", "phone", "电话", "text", "基础信息", 1, 1, None),
    ("person", "department_id", "所属部门", "entity_ref", "组织", 0, 2, "department"),
    ("person", "company_id", "所属单位", "entity_ref", "组织", 1, 3, "company"),
    ("person", "position", "职位", "text", "基础信息", 1, 4, None),
    ("person", "status", "在职状态", "select", "基础信息", 1, 5, "person_status"),
    ("person", "entry_date", "入职日期", "date", "基础信息", 0, 6, None),
    ("person", "resign_date", "离职日期", "date", "基础信息", 0, 7, None),
    ("person", "age", "年龄", "number", "基础信息", 1, 8, None),
]

PROJECT_FIELDS = [
    ("project", "description", "项目描述", "textarea", "基础信息", 0, 0, None),
    ("project", "manager_id", "负责人", "entity_ref", "组织", 1, 1, "person"),
    ("project", "department_id", "归属部门", "entity_ref", "组织", 0, 2, "department"),
    ("project", "end_date", "预计结束日期", "date", "基础信息", 1, 3, None),
    ("project", "amount", "金额", "money", "基础信息", 1, 4, None),
    ("project", "contact", "联系", "text", "基础信息", 1, 5, None),
    ("project", "meta_data", "元数据", "text", "基础信息", 0, 6, None),
]


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        existing = set(
            (r[0], r[1])
            for r in conn.execute(
                text(
                    "SELECT entity_type, field_key FROM field_metadata "
                    "WHERE is_deleted=0"
                )
            ).fetchall()
        )
        for f in PERSON_FIELDS + PROJECT_FIELDS:
            et, fk, name, dtype, grp, lv, so, osc = f
            if (et, fk) in existing:
                print(f"skip (exists): {et}.{fk}")
                continue
            conn.execute(
                text(
                    "INSERT INTO field_metadata "
                    "(entity_type, field_key, display_name, data_type, group_name, "
                    "is_list_visible, is_searchable, is_filterable, is_exportable, "
                    "sort_order, option_set_code, status, is_deleted) "
                    "VALUES (:et, :fk, :dn, :dt, :grp, :lv, 0, 0, 1, :so, "
                    ":osc, 'enabled', 0)"
                ),
                {
                    "et": et,
                    "fk": fk,
                    "dn": name,
                    "dt": dtype,
                    "grp": grp,
                    "lv": lv,
                    "so": so,
                    "osc": osc,
                },
            )
            print(f"insert: {et}.{fk} ({name})")
        conn.commit()
    print("done")


if __name__ == "__main__":
    main()
