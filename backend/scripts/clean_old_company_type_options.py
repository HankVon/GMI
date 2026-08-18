"""清理 option_set:company_type 中旧版业务角色选项(业主/施工/监理/设计院/政府/供应商/事业单位/合作伙伴)。

新标准: 政府部门/院校/科研所/国有企业/集体企业/股份合作企业/联营企业/有限责任公司/
        股份有限公司/私营企业/港澳台商投资企业/外商投资企业/其他

运行: D:\\anaconda\\python.exe scripts/clean_old_company_type_options.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.config import settings

NEW_VALUES = {"政府部门", "院校", "科研所", "国有企业", "集体企业", "股份合作企业", "联营企业",
              "有限责任公司", "股份有限公司", "私营企业", "港澳台商投资企业", "外商投资企业", "其他"}
OLD_VALUES = {"业主", "施工", "监理", "设计院", "政府", "供应商", "事业单位", "合作伙伴"}


def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT id FROM option_set WHERE code='company_type' AND is_deleted=0")).fetchone()
        if not row:
            print("company_type option_set not found")
            return
        sid = row[0]
        # 软删旧选项
        for v in OLD_VALUES:
            r = conn.execute(text(
                "UPDATE option_item SET is_deleted=1 WHERE option_set_id=:sid AND value=:v"),
                {"sid": sid, "v": v})
            if r.rowcount:
                print(f"  soft-deleted old option: {v}")
        # 校验新选项齐全
        existing = set(r[0] for r in conn.execute(text(
            "SELECT value FROM option_item WHERE option_set_id=:sid AND is_deleted=0"),
            {"sid": sid}).fetchall())
        missing = NEW_VALUES - existing
        if missing:
            print(f"  缺新选项: {missing} — 请先运行 seed_company_std_cats.py")
        else:
            print("  新选项齐全 ✓")
        conn.commit()
    print("done")


if __name__ == "__main__":
    main()
