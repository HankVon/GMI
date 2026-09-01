# -*- coding: utf-8 -*-
"""走 HTTP 调容器内 backend(8200), 验证新代码已生效且全链路打通。

用 admin 登录拿 JWT, 再调 /api/v1/tenders/383/detail, 打印关键字段。
这比直连库更能证明: 容器内跑的是新镜像 + auth 通过 + 接口返回新 schema。
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://localhost:8200"


def _post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def _get(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def main():
    token = _post("/api/v1/auth/login", {"username": "admin", "password": "admin123"})["access_token"]
    print("[auth] 登录成功, token 长度:", len(token))

    data = _get("/api/v1/tenders/383/detail", token)["data"]

    print("\n--- 附件(应为 2 个带真实下载链接) ---")
    for a in data.get("attachments") or []:
        print(f"  {a.get('name')}  ->  {str(a.get('url'))[:55]}")

    print("\n--- 基本信息填空(应不再全是'未披露') ---")
    for r in data.get("kv") or []:
        if r["label"] in ("招标代理", "建设规模", "建设工期", "预算金额"):
            print(f"  {r['label']}: {r['field']['displayText']}")

    print("\n--- 中标供应商(应 1 家, 带金额/得分) ---")
    for s in data.get("suppliers") or []:
        print(f"  {s.get('name')}  ¥{s.get('amount_text')}  得分={s.get('score')}")

    print("\n--- enriched 补抽字段 ---")
    print("  ", list((data.get("enriched") or {}).keys())[:8])

    # 断言: 新 schema 字段必须存在
    assert "suppliers" in data, "容器内接口缺少 suppliers（新 schema 未生效）"
    assert "enriched" in data, "容器内接口缺少 enriched（新 schema 未生效）"
    assert (data.get("attachments") or []), "容器内 383 附件为空（补抓未生效）"
    assert "zcy-gov-open-doc" in (data["attachments"][0].get("url") or ""), "附件无真实下载链接"
    print("\n✅ 容器内新后端已生效, 全链路打通")


if __name__ == "__main__":
    main()
