"""按新国家标准三套分类回填所有活跃单位(company_type/industry/ownership)。

判定优先级:
  1. 单位已有 company_type/industry/ownership 且是标准枚举值 → 保留(尊重人工/导入值)
  2. 空白或非标准值 → 用 _guess_company_* 按名称重判

运行: D:\\anaconda\\python.exe scripts/backfill_company_cats.py
"""
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import select
from app.config import settings
from app.models.company import Company
from app.database import SessionLocal
from app.services.data_pipeline import (_guess_company_type, _guess_company_category,
                                        _guess_company_ownership)
from app.services.neo4j_sync import sync_company

# 标准枚举值集合(用于判断是否保留现有值)
STANDARD_TYPES = {"政府部门", "院校", "科研所", "国有企业", "集体企业", "股份合作企业", "联营企业",
                  "有限责任公司", "股份有限公司", "私营企业", "港澳台商投资企业", "外商投资企业", "其他"}
STANDARD_CATS = {"农业", "工业", "服务业", "邮电", "通信", "社区服务", "批发", "零售业", "交通运输",
                 "建筑及安装业", "医疗卫生", "城市建设", "旅游", "宾馆", "餐饮业", "其他"}
STANDARD_OWNS = {"国有", "合作", "合资", "独资", "集体", "私营", "个体工商户", "报关", "其他"}


def main():
    db = SessionLocal()
    rows = db.execute(select(Company).where(Company.is_deleted == False)).scalars().all()
    changed_type = changed_cat = changed_own = 0
    for c in rows:
        name = c.name or ""
        # 单位类型: 非标准值或兜底"其他"都重判(旧版"其他"多为漏判, 新逻辑能命中具体类型)
        old_t = c.company_type or ""
        if old_t not in STANDARD_TYPES or old_t == "其他":
            new_t = _guess_company_type(name)
            if new_t != old_t:
                c.company_type = new_t
                changed_type += 1
        # 企业类别: 同理,"其他"也重判
        old_c = c.industry or ""
        if old_c not in STANDARD_CATS or old_c == "其他":
            new_c = _guess_company_category(name)
            if new_c != old_c:
                c.industry = new_c
                changed_cat += 1
        # 企业性质: 同理,"其他"也重判
        ext = dict(c.ext_attrs or {})
        old_o = ext.get("ownership") or ""
        if old_o not in STANDARD_OWNS or old_o == "其他":
            new_o = _guess_company_ownership(name, ext.get("econ_kind") or "")
            if new_o != old_o:
                ext["ownership"] = new_o
                c.ext_attrs = ext
                changed_own += 1
    db.commit()
    print(f"回填完成: company_type 变更 {changed_type}, industry 变更 {changed_cat}, ownership 变更 {changed_own}")

    # Neo4j 重同步
    with db:
        for c in db.execute(select(Company).where(Company.is_deleted == False)).scalars().all():
            try:
                sync_company(c.id, c.name or "", code=c.code or "",
                             company_type=c.company_type or "",
                             province=c.province or "", city=c.city or "")
            except Exception as e:  # noqa: BLE001
                print(f"  sync_company {c.id} 失败: {e}")
    print("Neo4j 同步完成")
    db.close()


if __name__ == "__main__":
    main()
