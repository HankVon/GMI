"""意向情报「字段体检」— 检测字段完整性, 为后台审核与批量发布提供把关依据。

设计要点:
  1. 规则分两级:
     - REQUIRED(核心必填): 前台展示的底线字段, 缺失 → 禁止发布(阻断)
     - OPTIONAL(加分项):   政务公告常缺(如金额/联系人), 缺失 → 允许发布但标注提示
  2. 结果写入 intent_notice.ext_attrs["quality"], 无需新增表/字段(零 DDL 迁移)。
  3. level 语义:
     - ok   核心齐 + 完整度≥85
     - warn 核心齐, 但缺加分项(可发布, 二次确认)
     - poor 缺核心必填(禁止发布)

用法:
  - 采集入库后 / 后台保存后: apply_quality(it)   (计算并写回内存, 由调用方 commit)
  - 列表/详情展示:          quality_of(it)       (读缓存, 无则实时算, 不写库)
  - 发布前把关:             can_publish(it)      (返回是否放行 + 阻断原因)
"""
from __future__ import annotations

import datetime
from typing import Callable

# 权重: 核心必填 5 项 × 14 = 70; 加分项 5 项 × 6 = 30; 合计 100(即完整度百分比)
REQ_WEIGHT = 14
OPT_WEIGHT = 6


def _filled(v) -> bool:
    """值是否"有内容"(空串/None 视为缺失)。"""
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    return True


def _has_region(it) -> bool:
    """地域: region(展示串) 或 province(结构化) 任一有值即可。"""
    return _filled(it.region) or _filled(it.province)


def _has_category(it) -> bool:
    """行业/项目类型: 任一有值即可。"""
    return _filled(it.industry) or _filled(it.project_type)


def _long_text(it) -> bool:
    """原文摘要: 少于 30 字视为未解析到正文(常见采集失败表现)。"""
    return len((it.raw_text or "").strip()) >= 30


# (字段key, 中文标签, 判定函数)
REQUIRED_RULES: list[tuple[str, str, Callable]] = [
    ("title", "标题", lambda it: _filled(it.title)),
    ("published_at", "发布时间", lambda it: it.published_at is not None),
    ("dept", "发布部门", lambda it: _filled(it.dept)),
    ("region", "地域", _has_region),
    ("category", "行业/项目类型", _has_category),
]

OPTIONAL_RULES: list[tuple[str, str, Callable]] = [
    ("amount", "投资金额", lambda it: it.amount is not None),
    ("contact", "联系方式", lambda it: _filled(it.contact)),
    ("start_date", "拟开工时间", lambda it: it.start_date is not None),
    ("raw_text", "原文摘要", _long_text),
    ("matched_entity", "关联单位/人员", lambda it: _filled(it.matched_entity)),
]


def check_quality(it) -> dict:
    """计算一条意向的字段体检结果(纯计算, 不写库)。"""
    missing_required: list[str] = []
    missing_optional: list[str] = []
    missing_req_labels: list[str] = []
    missing_opt_labels: list[str] = []
    score = 0

    for key, label, ok in REQUIRED_RULES:
        try:
            passed = bool(ok(it))
        except Exception:  # noqa: BLE001 - 单条规则异常不应中断整体体检
            passed = False
        if passed:
            score += REQ_WEIGHT
        else:
            missing_required.append(key)
            missing_req_labels.append(label)

    for key, label, ok in OPTIONAL_RULES:
        try:
            passed = bool(ok(it))
        except Exception:  # noqa: BLE001
            passed = False
        if passed:
            score += OPT_WEIGHT
        else:
            missing_optional.append(key)
            missing_opt_labels.append(label)

    if missing_required:
        level = "poor"
    elif score >= 85:
        level = "ok"
    else:
        level = "warn"

    return {
        "completeness": score,
        "level": level,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "missing_required_labels": missing_req_labels,
        "missing_optional_labels": missing_opt_labels,
        # 供 UI 直接展示的"缺什么"清单(核心在前)
        "missing_labels": missing_req_labels + missing_opt_labels,
        "checked_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def quality_of(it) -> dict:
    """读取已缓存的体检结果; 无缓存则实时计算(不写库)。"""
    attrs = it.ext_attrs if isinstance(it.ext_attrs, dict) else {}
    q = attrs.get("quality")
    if isinstance(q, dict) and q.get("level"):
        return q
    return check_quality(it)


def apply_quality(it) -> dict:
    """计算并写回 it.ext_attrs["quality"](仅改内存, 由调用方负责 commit)。"""
    q = check_quality(it)
    attrs = dict(it.ext_attrs) if isinstance(it.ext_attrs, dict) else {}
    attrs["quality"] = q
    it.ext_attrs = attrs  # 整体重新赋值, 确保 SQLAlchemy 感知 JSON 变更
    return q


def can_publish(it) -> tuple[bool, str, list]:
    """发布闸门(核心必填阻断 + 加分项警告)。

    实时计算而非读缓存, 避免"补全后又改坏"或"缓存过期"导致误放行。

    return: (allow, block_reason, missing_optional_labels)
    """
    q = check_quality(it)
    if q["level"] == "poor":
        return False, "请先补全核心字段: " + "、".join(q["missing_required_labels"]), q["missing_optional_labels"]
    return True, "", q["missing_optional_labels"]
