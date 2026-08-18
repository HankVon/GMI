"""知识抽取引擎 — 基于大模型的开放域实体识别 + 区域属性关联 + 关系抽取。

三大能力(复用 llm_enhance._generate/_extract_json + china_regions):
  1. NER: 从文本识别 公司/人员/项目/区域/金额/时间 等实体(开放类型)
  2. Geo-linking: 实体区域属性 → china_regions.resolve_region 归一化(省-市-县三级)
  3. 开放域 RE: 实体间关系任意语义, 不限定预设类型, 输出 {source,target,relation,relation_zh,confidence,evidence}

原则:
  - 证据可溯源: 每个关系带 evidence(原文句子) + confidence(0-1)
  - 不编造: 文本中不存在则 null/空; 复用 _extract_json 容错
"""
import json
import logging
import re

from app.services.china_regions import resolve_region
from app.services.llm_enhance import LLMUnavailable, _extract_json, _generate

logger = logging.getLogger("knowledge_extractor")


def _extract_json_value(text: str):
    """从 LLM 输出提取 JSON(对象或数组), 返回 Python 对象。

    qwen-graphrag 对「只输出 JSON」的 prompt 常输出顶层数组(如 NER 的
    [{...},{...}]), 而 _extract_json 只匹配 {...} 对象 → 需兼容数组。
    """
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json 围栏
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    # 依次尝试: 顶层数组 → 顶层对象 → 大括号子串
    for pat in (r"^\[.*\]$", r"^\{.*\}$"):
        mm = re.search(pat, text, re.DOTALL)
        if mm:
            try:
                return json.loads(mm.group(0))
            except Exception:
                pass
    # 兜底: 对象/数组子串
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        mm = re.search(re.escape(open_ch) + r".*" + re.escape(close_ch), text, re.DOTALL)
        if mm:
            try:
                return json.loads(mm.group(0))
            except Exception:
                continue
    return None

# 实体类型(开放, LLM 可输出其他类型, 但需在本集合内才算标准)
STD_ENTITY_TYPES = {"company", "person", "project", "region", "material", "tech",
                    "amount", "time", "organization", "location", "other"}

# 预设关系映射: LLM 关系名 → Neo4j 标准关系(复用现有图谱)
PRESET_RELATION_MAP = {
    "WORKS_AT": ("WORKS_AT", "任职于"),
    "PARTICIPATES_IN": ("PARTICIPATES_IN", "参与"),
    "COLLABORATED_WITH": ("COLLABORATED_WITH", "合作过"),
    "COLLEAGUE": ("COLLEAGUE", "同事"),
    "IN_REGION": ("IN_REGION", "位于"),
    "BELONGS_TO": ("BELONGS_TO", "隶属于"),
    "LOCATED_IN": ("IN_REGION", "位于"),
    "EMPLOYED_BY": ("WORKS_AT", "任职于"),
    "JOINED": ("PARTICIPATES_IN", "参与"),
    "PARTNERS_WITH": ("COLLABORATED_WITH", "合作过"),
}


def _ner_prompt(text: str) -> str:
    return (
        "你是实体识别引擎。从下面的文本中识别出所有实体，只输出 JSON。\n"
        "实体类型(开放): company(公司/机构/事业单位/政府机关), person(人名), "
        "project(项目/工程/标段), region(行政区划), organization(其他组织), "
        "location(地点), material(材料/设备), tech(技术/资质), amount(金额), time(时间)。\n"
        "每个实体输出: {type, name, aliases:[别名], province, city, county, evidence(原文依据)}。\n"
        "province/city/county 为实体所属的行政区划(尽量精确到县)。\n"
        "规则: 文本中不存在的实体不要输出; 区域名(如 成都市)也作为 region 实体输出; 绝不编造。\n\n"
        f"文本：\n{text[:3500]}"
    )


def _re_prompt(text: str, entities: list) -> str:
    ents = json.dumps(entities, ensure_ascii=False)[:1500]
    return (
        "你是关系抽取引擎。基于给出的实体列表和文本，抽取实体之间的关系，只输出 JSON。\n"
        "关系: {source, target, relation(英文标识), relation_zh(中文), confidence(0-1), evidence(原文句子)}。\n"
        "规则: ①关系类型完全开放, 不限定预设集合, 由文本语义判断(如 控股/承建/供应给/监管/参与/位于…); "
        "②source 和 target 必须来自实体列表的 name; ③confidence<0.6 的关系不要输出; "
        "④evidence 必须引用原文; ⑤文本没有明确语义支撑的关系不要输出, 绝不编造。\n\n"
        f"实体列表：{ents}\n\n文本：\n{text[:3500]}"
    )


def extract_entities(text: str) -> list:
    """NER: 从文本提取实体列表(含区域属性)。

    返回 [{type, name, aliases, province, city, county, evidence}]
    区域属性用 china_regions 归一化到标准省/市/县核心词。
    """
    if not text or not text.strip():
        return []
    try:
        raw = _extract_json_value(_generate(_ner_prompt(text), timeout=120))
    except LLMUnavailable:
        logger.warning("ollama 不可用, NER 跳过")
        return []
    if isinstance(raw, list):
        entities = raw  # LLM 直接输出数组
    elif isinstance(raw, dict):
        entities = raw.get("entities") or raw.get("entity_list") or []
    else:
        return []
    cleaned = []
    for e in entities:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        etype = str(e.get("type") or "other").strip().lower()
        if not name:
            continue
        # 区域归一化(实体自己的 province/city/county + name 里的区划词)
        province = str(e.get("province") or "").strip()
        city = str(e.get("city") or "").strip()
        county = str(e.get("county") or "").strip()
        rg = resolve_region(province, city, county)
        # 实体是 region 类型时, 用 name 解析
        if etype == "region":
            rg = resolve_region("", "", name) or rg
            if not rg.get("matched"):
                rg = resolve_region("", name, "")
        cleaned.append({
            "type": etype if etype in STD_ENTITY_TYPES else "other",
            "name": name,
            "aliases": [str(a).strip() for a in (e.get("aliases") or []) if str(a).strip()] if isinstance(e.get("aliases"), list) else [],
            "province": rg.get("province", ""),
            "city": rg.get("city", ""),
            "county": rg.get("county", ""),
            "evidence": str(e.get("evidence") or "").strip()[:300],
        })
    # 去重
    seen = set()
    uniq = []
    for e in cleaned:
        key = (e["type"], e["name"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


def extract_relations(text: str, entities: list) -> list:
    """开放域 RE: 从文本抽取实体间关系。

    返回 [{source, target, relation, relation_zh, confidence, evidence}]
    关系名做标准化: 命中 PRESET_RELATION_MAP 映射到标准关系, 否则保留开放类型。
    """
    if not text or not entities:
        return []
    try:
        raw = _extract_json_value(_generate(_re_prompt(text, entities), timeout=120))
    except LLMUnavailable:
        logger.warning("ollama 不可用, RE 跳过")
        return []
    if isinstance(raw, list):
        rels = raw  # LLM 直接输出数组
    elif isinstance(raw, dict):
        rels = raw.get("relations") or []
    else:
        return []
    names = {e["name"] for e in entities}
    cleaned = []
    for r in rels:
        if not isinstance(r, dict):
            continue
        source = str(r.get("source") or "").strip()
        target = str(r.get("target") or "").strip()
        if not source or not target or source == target:
            continue
        if source not in names and target not in names:
            continue
        try:
            conf = float(r.get("confidence") or 0)
        except (TypeError, ValueError):
            conf = 0.5
        if conf < 0.6:
            continue
        relation = str(r.get("relation") or "").strip().upper()
        if not relation:
            continue
        relation_zh = str(r.get("relation_zh") or relation).strip()
        # 预设关系标准化
        std_rel, std_zh = PRESET_RELATION_MAP.get(relation, (relation, relation_zh))
        cleaned.append({
            "source": source, "target": target,
            "relation": std_rel, "relation_zh": std_zh,
            "confidence": round(conf, 2),
            "evidence": str(r.get("evidence") or "").strip()[:300],
        })
    return cleaned


def extract_knowledge(text: str) -> dict:
    """全链路: NER → 区域关联 → 开放域 RE。

    返回 {"entities": [...], "relations": [...], "regions": [去重的三级区域]}
    """
    entities = extract_entities(text)
    relations = extract_relations(text, entities) if entities else []
    # 区域汇总(去重)
    regions = []
    seen = set()
    for e in entities:
        rg = (e.get("province", ""), e.get("city", ""), e.get("county", ""))
        if any(rg) and rg not in seen:
            seen.add(rg)
            regions.append({"province": rg[0], "city": rg[1], "county": rg[2]})
    return {"entities": entities, "relations": relations, "regions": regions}
