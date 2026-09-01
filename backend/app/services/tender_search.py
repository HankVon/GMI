"""招投标检索引擎适配层。

ES 可用时使用 bool + search_after；ES 不可用时由上层回退现有 MySQL 查询。
"""
from __future__ import annotations
from typing import Any
import httpx


def build_es_query(node: dict[str, Any]) -> dict[str, Any]:
    """将树形条件转换为 Elasticsearch bool 查询。"""
    operator = str(node.get("operator", "AND")).upper()
    children = node.get("children") or []
    clauses = []
    for child in children:
        if not isinstance(child, dict): continue
        clause = leaf_clause(child) if child.get("field") else build_es_query(child)
        if clause: clauses.append(clause)
    if operator == "OR":
        return {"bool": {"should": clauses, "minimum_should_match": 1}}
    if operator == "NOT":
        return {"bool": {"must_not": clauses}}
    return {"bool": {"must": clauses}}


def leaf_clause(condition: dict[str, Any]) -> dict[str, Any] | None:
    field, value = condition.get("field"), condition.get("value")
    if not field or value in (None, "", []):
        return None
    op = condition.get("operator", "contains")
    if op == "term": return {"term": {field: value}}
    if op == "terms": return {"terms": {field: value if isinstance(value, list) else [value]}}
    if op == "range": return {"range": {field: value}}
    if op == "match": return {"match": {field: {"query": value, "operator": "and"}}}
    return {"match": {field: value}}


def build_tender_query(payload: dict[str, Any]) -> dict[str, Any]:
    """生成 ES DSL；condition_tree 支持 field/value 叶子节点和嵌套 AND/OR/NOT。"""
    filters: list[dict[str, Any]] = []
    must: list[dict[str, Any]] = []
    should: list[dict[str, Any]] = []
    for condition in payload.get("filters", []):
        clause = leaf_clause(condition)
        if clause: filters.append(clause)
    if payload.get("keyword"):
        must.append({"multi_match": {"query": payload["keyword"], "fields": ["title^3", "purchaser", "supplier_names", "project_code"], "operator": "and"}})
    tree = payload.get("condition_tree")
    if isinstance(tree, dict):
        tree_clause = build_es_query(tree)
        (should if str(tree.get("operator", "AND")).upper() == "OR" else must).append(tree_clause)
    query: dict[str, Any] = {"bool": {"must": must, "filter": filters}}
    if should: query["bool"]["should"] = should
    return {"query": query, "sort": [{"published_at": "desc"}, {"_id": "desc"}], "size": min(int(payload.get("size", 20)), 100)}


async def search_es(base_url: str, index: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = build_tender_query(payload)
    if payload.get("search_after") is not None: body["search_after"] = payload["search_after"]
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(f"{base_url.rstrip('/')}/{index}/_search", json=body)
        response.raise_for_status()
        data = response.json()
    hits = data.get("hits", {}).get("hits", [])
    return {"total": data.get("hits", {}).get("total", {}).get("value", 0), "items": [hit.get("_source", {}) | {"id": hit.get("_id"), "sort": hit.get("sort")} for hit in hits], "lastSortValue": hits[-1].get("sort") if hits else None}
