"""线索 LLM 增强服务 — 用本地 Ollama 大模型对公告做 AI 筛选/抽取/总结。

设计权衡(实测 qwen-graphrag:latest, CPU 推理):
  - AI 筛选: ~3.7s/条 → 价值最高(语义判断比关键词准, 剔除无关线索)
  - LLM 抽取: ~12.9s/条 → 锦上添花(接口字段+正则已较全)
  - AI 总结: ~5.0s/条 → 纯增值展示

调用策略:
  - 来源配置 llm_enhance: "filter" / "summary" / "extract" / "all" / "" (默认 filter)
  - 抓取时对每条候选同步做 filter(拦截无关线索), 其他增强异步由前端按钮触发。
"""
import json
import logging
import re
import time

import httpx

from app.config import settings

logger = logging.getLogger("llm_enhance")

OLLAMA_BASE = settings.OLLAMA_BASE_URL.rstrip("/")
OLLAMA_MODEL = settings.OLLAMA_MODEL


class LLMUnavailable(Exception):
    """Ollama 不可用"""


def _generate(prompt: str, system: str = "", timeout: float = 180.0) -> str:
    """调用 Ollama generate, 返回文本。"""
    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system
    try:
        r = httpx.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("response") or ""
    except Exception as e:  # noqa: BLE001
        logger.warning("ollama call error: %s", e)
        raise LLMUnavailable(str(e)) from e


def _extract_json(text: str) -> dict:
    """从 LLM 输出提取 JSON(容忍 ```json 围栏/前后杂文)。"""
    if not text:
        return {}
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        # 尝试修复裸 key(LLM 常输出未加引号 key)
        try:
            fixed = re.sub(r"([{,]\s*)([A-Za-z_\u4e00-\u9fff][^:,\}\s]*)(\s*:)", r'\1"\2"\3', m.group(0))
            return json.loads(fixed)
        except Exception:  # noqa: BLE001
            return {}


def ai_filter(title: str, content: str, domain_hints: str = "") -> dict:
    """AI 语义筛选: 判断公告是否与目标领域相关。

    返回 {"relevant": bool, "reason": str, "elapsed": float}
    """
    hints = f"重点关注领域: {domain_hints}。" if domain_hints else ""
    prompt = (
        "判断以下政府采购公告是否与【生态修复、地质、矿山治理、地质勘查、水土保持、灾害防治】等领域相关。\n"
        f"{hints}"
        "只输出 JSON: {\"relevant\": true或false, \"reason\": \"一句话理由\"}\n\n"
        f"公告标题：{title}\n\n公告内容：\n{content[:3000]}"
    )
    t0 = time.time()
    out = _generate(prompt)
    elapsed = round(time.time() - t0, 1)
    parsed = _extract_json(out)
    relevant = bool(parsed.get("relevant"))
    reason = str(parsed.get("reason") or "")[:200]
    return {"relevant": relevant, "reason": reason, "elapsed": elapsed}


def ai_extract(content: str) -> dict:
    """LLM 抽取结构化字段(补充接口字段)。"""
    prompt = (
        "从以下政府采购公告正文中提取结构化信息，只输出 JSON，字段：\n"
        "{项目编号, 项目名称, 采购方式, 预算金额, 截止时间, 开标时间, "
        "采购人, 采购人电话, 代理机构, 合同履行期限, 特定资质要求}\n"
        "某字段正文不存在则值为空字符串。\n\n正文：\n" + content[:3000]
    )
    t0 = time.time()
    out = _generate(prompt)
    parsed = _extract_json(out)
    parsed["_elapsed"] = round(time.time() - t0, 1)
    return parsed


def ai_summary(title: str, content: str) -> dict:
    """AI 总结: 3 句话要点 + 关注理由。"""
    prompt = (
        f"用 3 句话总结以下政府采购公告的要点(项目内容/预算/时间/资质要求)，"
        f"并说明为什么这个项目值得生态修复或地质行业从业者关注。\n\n"
        f"公告标题：{title}\n\n正文：\n{content[:3000]}"
    )
    t0 = time.time()
    out = _generate(prompt)
    return {"summary": out.strip()[:800], "elapsed": round(time.time() - t0, 1)}


def enhance_content(title: str, content: str, mode: str = "filter") -> dict:
    """按模式对线索做 LLM 增强。mode: filter/summary/extract/all/''"""
    result = {}
    if not content:
        return result
    if mode in ("filter", "all", ""):
        try:
            result["ai_filter"] = ai_filter(title, content)
        except LLMUnavailable:
            pass
    if mode in ("summary", "all"):
        try:
            result["ai_summary"] = ai_summary(title, content)
        except LLMUnavailable:
            pass
    if mode in ("extract", "all"):
        try:
            result["ai_extract"] = ai_extract(content)
        except LLMUnavailable:
            pass
    return result
