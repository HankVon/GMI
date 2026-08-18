"""按国家标准初始化公司三套分类的 option_set 与 field_metadata(幂等)。

三套标准:
  company_category 企业类别(行业): 农业/工业/服务业/邮电/通信/社区服务/批发/零售业/
                                    交通运输/建筑及安装业/医疗卫生/城市建设/旅游/宾馆/餐饮业
  company_type     单位类型(所有制): 政府部门/院校/科研所/国有企业/集体企业/股份合作企业/
                                    联营企业/有限责任公司/股份有限公司/私营企业/
                                    港澳台商投资企业/外商投资企业
  company_ownership 企业性质(经营): 国有/合作/合资/独资/集体/私营/个体工商户/报关/其他

运行: D:\\anaconda\\python.exe scripts/seed_company_std_cats.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings


CATEGORIES = [
    ("农业", "农业"), ("工业", "工业"), ("服务业", "服务业"), ("邮电", "邮电"),
    ("通信", "通信"), ("社区服务", "社区服务"), ("批发", "批发"), ("零售业", "零售业"),
    ("交通运输", "交通运输"), ("建筑及安装业", "建筑及安装业"), ("医疗卫生", "医疗卫生"),
    ("城市建设", "城市建设"), ("旅游", "旅游"), ("宾馆", "宾馆"), ("餐饮业", "餐饮业"),
    ("其他", "其他"),
]
TYPES = [
    ("政府部门", "政府部门"), ("院校", "院校"), ("科研所", "科研所"), ("国有企业", "国有企业"),
    ("集体企业", "集体企业"), ("股份合作企业", "股份合作企业"), ("联营企业", "联营企业"),
    ("有限责任公司", "有限责任公司"), ("股份有限公司", "股份有限公司"), ("私营企业", "私营企业"),
    ("港澳台商投资企业", "港澳台商投资企业"), ("外商投资企业", "外商投资企业"), ("其他", "其他"),
]
OWNERSHIPS = [
    ("国有", "国有"), ("合作", "合作"), ("合资", "合资"), ("独资", "独资"), ("集体", "集体"),
    ("私营", "私营"), ("个体工商户", "个体工商户"), ("报关", "报关"), ("其他", "其他"),
]


def seed_option_set(conn, code, name, desc, items):
    row = conn.execute(text(
        "SELECT id FROM option_set WHERE code=:c AND is_deleted=0"), {"c": code}).fetchone()
    if row:
        sid = row[0]
        print(f"option_set exists: {code}")
    else:
        r = conn.execute(text(
            "INSERT INTO option_set (code, name, description, is_deleted) "
            "VALUES (:c, :n, :d, 0)"), {"c": code, "n": name, "d": desc})
        sid = r.lastrowid
        print(f"inserted option_set: {code}")
    existing = set(r[0] for r in conn.execute(text(
        "SELECT value FROM option_item WHERE option_set_id=:sid AND is_deleted=0"),
        {"sid": sid}).fetchall())
    for i, (value, label) in enumerate(items):
        if value in existing:
            continue
        conn.execute(text(
            "INSERT INTO option_item (option_set_id, value, label, sort_order, is_deleted) "
            "VALUES (:sid, :v, :l, :so, 0)"),
            {"sid": sid, "v": value, "l": label, "so": i})
    print(f"  {code} 选项数: {len(items)}")


def seed_field_meta(conn, key, name, dtype, group, option_set_code):
    r = conn.execute(text(
        "SELECT id FROM field_metadata WHERE entity_type='company' AND field_key=:k AND is_deleted=0"),
        {"k": key}).fetchone()
    if r:
        # 已存在: 仅补齐 option_set_code
        conn.execute(text(
            "UPDATE field_metadata SET option_set_code=:osc, data_type=:dt WHERE id=:id"),
            {"osc": option_set_code, "dt": dtype, "id": r[0]})
        print(f"field exists, updated: {key} -> option_set={option_set_code}")
        return
    conn.execute(text(
        "INSERT INTO field_metadata "
        "(entity_type, field_key, display_name, data_type, group_name, "
        "is_list_visible, is_searchable, is_filterable, is_exportable, "
        "sort_order, option_set_code, status, is_deleted) "
        "VALUES ('company', :k, :n, :dt, :grp, 1, 1, 1, 1, :so, :osc, 'enabled', 0)"),
        {"k": key, "n": name, "dt": dtype, "grp": group, "so": 20, "osc": option_set_code})
    print(f"inserted field: {key}")


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        seed_option_set(conn, "company_category", "企业类别", "行业分类", CATEGORIES)
        seed_option_set(conn, "company_type", "单位类型", "所有制/机构类型", TYPES)
        seed_option_set(conn, "company_ownership", "企业性质", "经营性质", OWNERSHIPS)
        # 字段元数据: ownership 走 ext_attrs 动态字段; company_type/industry 已有内置列
        seed_field_meta(conn, "ownership", "企业性质", "select", "基础信息", "company_ownership")
        conn.commit()
    print("done")


if __name__ == "__main__":
    main()
