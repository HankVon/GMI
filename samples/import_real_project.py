"""将 samples/real_project_info.xlsx 的真实项目导入 SSM(数据库+Neo4j 图谱, 关键在关联)。

直接读取 xlsx 全字段, 自动创建/复用公司、人员, 建立项目-单位/项目-成员关联, 并同步 Neo4j。

流程(全部走后端 API, 自动触发 MySQL 落库 + Neo4j 实时同步 + 动态字段校验):
  1. 读取 xlsx (可指定路径)
  2. 法人单位公司(鑫冶) — 已存在则复用, 否则创建
  3. 项目 — 已存在则更新状态/负责人/进度, 否则创建
  4. 项目负责人(归属法人单位) — 创建并关联项目(role=项目负责人)
  5. 业主单位(甲方社区) — 按名称匹配复用已存在实体, 关联项目(role=owner)
  6. 业主联系人(归属业主单位) — 创建并关联项目(role=业主联系人)
  7. 项目-单位关联(法人单位=constructor)
  8. 项目状态=completed + 「项目已完工」进度

用法:
  D:\\anaconda\\python.exe samples\\import_real_project.py [xlsx路径]
"""
from __future__ import annotations

import sys
import time
from typing import Any

import pandas as pd
import requests

BASE = "http://localhost:8100/api/v1"
USER = "admin"
PWD = "admin123"

# ---------- 0. 读取 xlsx ----------
XLSX = sys.argv[1] if len(sys.argv) > 1 else "samples/real_project_info.xlsx"
df = pd.read_excel(XLSX, sheet_name="Sheet1", dtype=str)


def cell(row: pd.Series, col: str) -> str:
    v = row.get(col)
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


rows: list[dict[str, str]] = []
for _, r in df.iterrows():
    rows.append({
        "项目名称": cell(r, "项目名称"),
        "核算单元": cell(r, "核算单元"),
        "法人单位": cell(r, "法人单位"),
        "行业类别": cell(r, "行业类别"),
        "服务方式": cell(r, "服务方式"),
        "项目负责人": cell(r, "项目负责人"),
        "项目负责人联系电话": cell(r, "项目负责人联系电话"),
        "项目获取方式": cell(r, "项目获取方式"),
        "合同金额": cell(r, "合同金额"),
        "项目级别": cell(r, "项目级别"),
        "项目业主": cell(r, "项目业主"),
        "经营模式": cell(r, "经营模式"),
        "资金来源": cell(r, "资金来源"),
        "项目开工日期": cell(r, "项目开工日期"),
        "业主联系人": cell(r, "业主联系人"),
        "业主联系人电话": cell(r, "业主联系人电话"),
        "甲方单位类型": cell(r, "甲方单位类型"),
        "甲方单位名称": cell(r, "甲方单位名称"),
        "甲方纳税人代码": cell(r, "甲方纳税人代码"),
        "甲方联系方式": cell(r, "甲方联系方式"),
        "甲方地址": cell(r, "甲方地址"),
    })

if not rows:
    print("FATAL: xlsx 无数据")
    sys.exit(1)

PROJECT_NAME = rows[0]["项目名称"]
LEGAL_COMPANY = rows[0]["法人单位"]
print(f"读取 {len(rows)} 行 | 项目: {PROJECT_NAME} | 法人单位: {LEGAL_COMPANY}")

# ---------- 1. 登录 ----------
r = requests.post(f"{BASE}/auth/login", json={"username": USER, "password": PWD}, timeout=10)
tok = r.json().get("access_token")
if not tok:
    print("FATAL: 登录失败", r.status_code, r.text[:300])
    sys.exit(1)
H = {"Authorization": f"Bearer {tok}"}
print("OK 登录成功")


def api(method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    """带鉴权的 API 调用。返回 (HTTP状态码, 响应 JSON)。"""
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=H, timeout=30)
        elif method == "POST":
            resp = requests.post(url, json=body or {}, headers=H, timeout=30)
        elif method == "PUT":
            resp = requests.put(url, json=body or {}, headers=H, timeout=30)
        else:
            resp = requests.delete(url, headers=H, timeout=30)
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("detail") or resp.text
            except Exception:  # noqa: BLE001
                detail = resp.text[:300]
            return resp.status_code, {"detail": detail}
        return resp.status_code, resp.json()
    except Exception as e:  # noqa: BLE001
        return -1, {"detail": str(e)}


def find_company(name: str) -> int | None:
    """按名称查找公司(优先未删除)。返回 id 或 None。"""
    _, sj = api("GET", "/companies", {"page": 1, "page_size": 10, "keyword": name[:30]})
    for it in (sj.get("items") or []):
        if it.get("name") == name and not it.get("is_deleted"):
            return it["id"]
    return None


def find_person(name: str) -> int | None:
    _, sj = api("GET", "/persons", {"page": 1, "page_size": 10, "keyword": name})
    for it in (sj.get("items") or []):
        if it.get("name") == name and not it.get("is_deleted"):
            return it["id"]
    return None


def find_project(name: str) -> int | None:
    _, sj = api("GET", "/projects", {"page": 1, "page_size": 10, "keyword": name[:30]})
    for it in (sj.get("items") or []):
        if it.get("name") == name and not it.get("is_deleted"):
            return it["id"]
    return None


# ---------- 2. 法人单位公司(复用或创建) ----------
legal_id = find_company(LEGAL_COMPANY)
if not legal_id:
    sc, sj = api("POST", "/companies", {
        "code": f"CO-{int(time.time())}",
        "name": LEGAL_COMPANY,
        "short_name": LEGAL_COMPANY[:8],
        "company_type": "施工",
        "province": "四川",
        "city": "成都",
        "industry": rows[0]["行业类别"],
    })
    legal_id = sj.get("id") if sc in (201, 200) else None
    if not legal_id:
        print(f"FATAL 创建法人单位失败: {sc} {sj}")
        sys.exit(1)
    print(f"OK 创建公司[{LEGAL_COMPANY}] id={legal_id}")
else:
    print(f"OK 复用公司[{LEGAL_COMPANY}] id={legal_id}")
LEGAL_ID = legal_id

# ---------- 3. 项目(创建或更新) ----------
project_id = find_project(PROJECT_NAME)
total_amount = sum(int(c["合同金额"]) for c in rows if c["合同金额"].isdigit())
contracts_summary = "\n".join(
    [f"- {c['甲方单位名称'] or c['项目业主']}: {c['合同金额']}元, "
     + f"负责人{c['项目负责人']}, 业主联系人{c['业主联系人']}({c['业主联系人电话']}), 开工{c['项目开工日期']}"
     for c in rows]
)
contact_names = "/".join(sorted({c["项目负责人"] for c in rows if c["项目负责人"]}))
progress_title = "项目已完工"
progress_content = f"{PROJECT_NAME} 已完成, 共 {len(rows)} 份分项合同(合计 {total_amount} 元)均已完成交付。"

if project_id:
    print(f"OK 项目已存在 id={project_id}, 更新状态/进度")
    sc, pj = api("PUT", f"/projects/{project_id}", {
        "status": "completed",
        "description": (
            f"项目获取方式:{rows[0]['项目获取方式']}; 服务方式:{rows[0]['服务方式']}; "
            f"经营模式:{rows[0]['经营模式']}; 资金来源:{rows[0]['资金来源']}; "
            f"项目级别:{rows[0]['项目级别']}; 核算单元:{rows[0]['核算单元']}。\n分项合同:\n{contracts_summary}"
        ),
    })
    print("  更新:", "OK" if sc in (200, 201) else f"FAIL({sc}) {pj}")
else:
    sc, pj = api("POST", "/projects", {
        "code": f"PRJ-{int(time.time()) % 10000}",
        "name": PROJECT_NAME,
        "status": "completed",
        "start_date": rows[0]["项目开工日期"] or None,
        "end_date": "2025-12-31",
        "description": (
            f"项目获取方式:{rows[0]['项目获取方式']}; 服务方式:{rows[0]['服务方式']}; "
            f"经营模式:{rows[0]['经营模式']}; 资金来源:{rows[0]['资金来源']}; "
            f"项目级别:{rows[0]['项目级别']}; 核算单元:{rows[0]['核算单元']}。\n分项合同:\n{contracts_summary}"
        ),
        "ext_attrs": {
            "amount": str(total_amount),
            "category": "geo_survey",
            "contact": contact_names,
        },
    })
    if sc not in (201, 200):
        print(f"FATAL 创建项目失败: {sc} {pj}")
        sys.exit(1)
    project_id = pj.get("id")
    print(f"OK 创建项目[{PROJECT_NAME}] id={project_id}")
PROJECT_ID = project_id

# 4. 进度记录(项目已完工, 幂等)
sc, rc = api("GET", f"/project-progress?project_id={PROJECT_ID}&page=1&page_size=20")
existing_progress = [p for p in (rc.get("items") or []) if p.get("title") == progress_title]
if not existing_progress:
    sc, rc = api("POST", "/project-progress", {
        "project_id": PROJECT_ID,
        "title": progress_title,
        "content": progress_content,
        "progress_date": "2025-12-31T00:00:00",
        "sort_order": 0,
    })
    print(("OK" if sc in (200, 201) else f"FAIL({sc})") + f" 进度[项目已完工] {rc}")
else:
    print("OK 进度[项目已完工] 已存在")

# ---------- 5. 项目负责人(归属法人单位, 去重后创建/关联) ----------
leaders = []
for c in rows:
    if c["项目负责人"] and c["项目负责人"] not in [x["name"] for x in leaders]:
        leaders.append({"name": c["项目负责人"], "phone": c["项目负责人联系电话"]})

for ld in leaders:
    pid = find_person(ld["name"])
    if not pid:
        sc, pj2 = api("POST", "/persons", {
            "code": f"EMP-{int(time.time()) % 100000}",
            "name": ld["name"],
            "phone": ld["phone"],
            "company_id": LEGAL_ID,
            "position": "项目负责人",
            "status": "active",
        })
        pid = pj2.get("id") if sc in (201, 200) else None
        if not pid:
            print(f"WARN 创建项目负责人[{ld['name']}]失败: {sc} {pj2}")
            continue
        print(f"OK 创建项目负责人[{ld['name']}] id={pid} 归属公司={LEGAL_ID}")
    else:
        print(f"OK 复用人员[{ld['name']}] id={pid}")
    # 关联项目
    sc, rc = api("POST", "/project-members", {
        "project_id": PROJECT_ID, "person_id": pid,
        "role": "manager",
        "responsibility": f"项目负责人(电话 {ld['phone']})",
        "joined_at": f"{rows[0]['项目开工日期'] or '2025-03-01'}T00:00:00",
    })
    print(("OK" if sc in (200, 201) else f"FAIL({sc})") + f" 项目-负责人[{ld['name']}] {rc}")

# ---------- 6. 业主单位 + 业主联系人 ----------
owner_map = {}
for c in rows:
    owner_name = c["甲方单位名称"] or c["项目业主"]
    if owner_name in owner_map:
        continue
    ocid = find_company(owner_name)
    if not ocid:
        sc, sj = api("POST", "/companies", {
            "code": f"CO-OWN{int(time.time()) % 100000}",
            "name": owner_name,
            "short_name": (c["项目业主"] or owner_name)[:8],
            "company_type": "业主",
            "province": "四川",
            "city": "成都",
            "ext_attrs": {"legal_rep": "", "reg_no": c["甲方纳税人代码"]},
        })
        ocid = sj.get("id") if sc in (201, 200) else None
        if not ocid:
            print(f"WARN 创建业主单位[{owner_name}]失败: {sc} {sj}")
            continue
        print(f"OK 创建业主单位[{owner_name}] id={ocid}")
    else:
        print(f"OK 复用业主单位[{owner_name}] id={ocid}")
    owner_map[owner_name] = ocid
    # 关联项目-单位(owner)
    sc, rc = api("POST", "/project-companies", {
        "project_id": PROJECT_ID, "company_id": ocid,
        "role": "owner", "joined_at": f"{c['项目开工日期']}T00:00:00",
    })
    print(("OK" if sc in (200, 201) else f"FAIL({sc})") + f" 项目-业主[{owner_name}] {rc}")
    # 业主联系人
    cname = c["业主联系人"]
    cphone = c["业主联系人电话"]
    if cname:
        cpid = find_person(cname)
        if not cpid:
            sc, pj2 = api("POST", "/persons", {
                "code": f"EMP-{int(time.time()) % 100000}",
                "name": cname,
                "phone": cphone,
                "company_id": ocid,
                "position": "业主联系人",
                "status": "active",
            })
            cpid = pj2.get("id") if sc in (201, 200) else None
            if not cpid:
                print(f"WARN 创建业主联系人[{cname}]失败: {sc} {pj2}")
                continue
            print(f"OK 创建业主联系人[{cname}] id={cpid} 归属公司={ocid}")
        else:
            print(f"OK 复用人员[{cname}] id={cpid}")
        sc, rc = api("POST", "/project-members", {
            "project_id": PROJECT_ID, "person_id": cpid,
            "role": "业主联系人",
            "responsibility": f"甲方联系人(电话 {cphone})",
            "joined_at": f"{c['项目开工日期']}T00:00:00",
        })
        print(("OK" if sc in (200, 201) else f"FAIL({sc})") + f" 项目-业主联系人[{cname}] {rc}")

# ---------- 7. 法人单位关联项目(constructor) ----------
sc, rc = api("POST", "/project-companies", {
    "project_id": PROJECT_ID, "company_id": LEGAL_ID,
    "role": "constructor", "joined_at": f"{rows[0]['项目开工日期'] or '2025-03-01'}T00:00:00",
})
print(("OK" if sc in (200, 201) else f"FAIL({sc})") + f" 项目-法人单位[{LEGAL_COMPANY}=constructor] {rc}")

# ---------- 8. 验证 ----------
print("\n===== 验证关联 =====")
sc, rc = api("GET", f"/project-members/timeline/{PROJECT_ID}")
items = rc.get("items") or []
print(f"项目成员: {len(items)} 条")
for it in items:
    print(f"  - {it.get('person_name')} | {it.get('role')} | 公司={it.get('company_name')}")

sc, rc = api("GET", f"/project-companies/timeline/{PROJECT_ID}")
items = rc.get("items") or []
print(f"项目单位: {len(items)} 条")
for it in items:
    print(f"  - {it.get('company_name')} | {it.get('role')}")

print("\nDONE")
