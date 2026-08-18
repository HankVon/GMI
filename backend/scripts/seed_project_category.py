"""为项目创建"类别"选项集与字段元数据（幂等）。

运行: python -m scripts.seed_project_category
效果:
  1. 创建选项集 project_category(项目类别), 预置: 生态修复/地质灾害/地质勘查/矿业权
     (后续可在"选项集管理"中继续添加类别)
  2. 创建项目动态字段 category(类别, select, 列表可见/可筛选)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

CATEGORIES = [
    ("eco_restoration", "生态修复"),
    ("geo_hazard", "地质灾害"),
    ("geo_survey", "地质勘查"),
    ("mining_rights", "矿业权"),
]


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        # ── 1. 选项集 ──
        row = conn.execute(
            text("SELECT id FROM option_set WHERE code='project_category' AND is_deleted=0")
        ).fetchone()
        if row:
            set_id = row[0]
            print("option_set exists: project_category")
        else:
            result = conn.execute(
                text(
                    "INSERT INTO option_set (code, name, description, is_deleted) "
                    "VALUES ('project_category', '项目类别', '生态修复/地质灾害/地质勘查/矿业权', 0)"
                )
            )
            set_id = result.lastrowid
            print("inserted option_set: project_category")

        # ── 2. 选项项(幂等: 按 value 去重) ──
        existing_values = set(
            r[0]
            for r in conn.execute(
                text("SELECT value FROM option_item WHERE option_set_id=:sid AND is_deleted=0"),
                {"sid": set_id},
            ).fetchall()
        )
        for i, (value, label) in enumerate(CATEGORIES):
            if value in existing_values:
                continue
            conn.execute(
                text(
                    "INSERT INTO option_item (option_set_id, value, label, sort_order, is_deleted) "
                    "VALUES (:sid, :value, :label, :so, 0)"
                ),
                {"sid": set_id, "value": value, "label": label, "so": i},
            )
            print(f"inserted option_item: {value} ({label})")

        # ── 3. 字段元数据(幂等) ──
        frow = conn.execute(
            text(
                "SELECT id FROM field_metadata "
                "WHERE entity_type='project' AND field_key='category' AND is_deleted=0"
            )
        ).fetchone()
        if not frow:
            conn.execute(
                text(
                    "INSERT INTO field_metadata "
                    "(entity_type, field_key, display_name, data_type, group_name, "
                    "is_list_visible, is_searchable, is_filterable, is_exportable, "
                    "sort_order, option_set_code, status, is_deleted) "
                    "VALUES ('project', 'category', '类别', 'select', '基础信息', "
                    "1, 1, 1, 1, 1, 'project_category', 'enabled', 0)"
                )
            )
            print("inserted field_metadata: project.category")
        else:
            print("field_metadata exists: project.category")

        conn.commit()
    print("done")


if __name__ == "__main__":
    main()
