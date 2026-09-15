"""动态工具链 / Function Calling 注册表。

为多智能体编排提供统一的工具调用入口：
- 内置工具：向量检索 / 图谱检索 / 子图查询 / 本地规则引擎
- 外部工具：药典 / 标准库 REST API（默认 stub，按需扩展）

调用约定：tool_call({"name": "search_vectorstore", "arguments": {...}}) -> dict
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from django.conf import settings


# --------------------------- 工具实现 ---------------------------

def _tool_search_vectorstore(question: str, document_ids: list[str] | None = None, top_k: int = 4) -> dict[str, Any]:
    from .services import format_contexts, retrieve_chunks

    docs = retrieve_chunks(question=question, document_ids=document_ids, top_k=int(top_k))
    return {"contexts": format_contexts(docs), "count": len(docs)}


def _tool_search_graph(question: str, limit_entities: int = 8) -> dict[str, Any]:
    try:
        from kg.services import KgNotConfiguredError, graph_context_for_question

        g = graph_context_for_question(question, limit_entities=int(limit_entities))
        return {"ok": True, **g}
    except Exception as e:
        return {"ok": False, "error": str(e), "keywords": [], "nodes": [], "edges": [], "paths": []}


def _tool_fetch_subgraph(center: str, limit: int = 30) -> dict[str, Any]:
    try:
        from kg.services import fetch_subgraph

        sg = fetch_subgraph(center, limit=int(limit))
        return {"ok": True, "nodes": sg.nodes, "edges": sg.edges}
    except Exception as e:
        return {"ok": False, "error": str(e), "nodes": [], "edges": []}


def _tool_local_rules(query: str) -> dict[str, Any]:
    """本地规则引擎：医疗器械/公共卫生领域的可解释规则。

    这里给出最小实现：内置一组关键词→风险提示的规则，可被外部 JSON/YAML 替换。
    """
    rules = getattr(settings, "LOCAL_RULES", None) or [
        {"keywords": ["儿童", "婴幼儿"], "advice": "涉及儿童/婴幼儿剂量与禁忌，应严格按说明书并咨询医师。"},
        {"keywords": ["孕妇", "哺乳"], "advice": "涉及孕妇/哺乳期人群，需提示风险并核对禁忌。"},
        {"keywords": ["医疗器械", "注册", "审批"], "advice": "涉及医疗器械合规事项，建议核对最新 NMPA 注册证与分类目录。"},
    ]
    hits = []
    q = (query or "").lower()
    for r in rules:
        for kw in r.get("keywords", []):
            if kw and kw.lower() in q:
                hits.append({"matched": kw, "advice": r.get("advice", "")})
                break
    return {"ok": True, "hits": hits, "rule_count": len(rules)}


def _tool_pharmacopoeia_api(name: str) -> dict[str, Any]:
    """外部药典/标准库 API 占位实现。

    生产环境可替换为真实 REST 调用：
        requests.get(settings.PHARMACOPOEIA_API + "/lookup", params={"name": name})
    当前默认返回 stub，避免在离线环境下阻塞流程。
    """
    base = getattr(settings, "PHARMACOPOEIA_API", "") or ""
    if not base:
        return {"ok": False, "error": "external api not configured", "name": name, "data": None}
    try:
        import requests

        resp = requests.get(f"{base.rstrip('/')}/lookup", params={"name": name}, timeout=8)
        resp.raise_for_status()
        return {"ok": True, "name": name, "data": resp.json()}
    except Exception as e:
        return {"ok": False, "error": str(e), "name": name, "data": None}


def _tool_web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """调用与 MCP Server 共用的联网检索实现。"""
    from .web_search import search_web

    return search_web(query=query, max_results=max_results)


# --------------------------- 注册表 ---------------------------

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_vectorstore": ToolSpec(
        name="search_vectorstore",
        description="对已向量化的文档 chunk 做相似度检索，返回 top_k 文本证据。",
        parameters={
            "question": {"type": "string", "required": True},
            "document_ids": {"type": "array", "required": False},
            "top_k": {"type": "integer", "required": False, "default": 4},
        },
        handler=_tool_search_vectorstore,
    ),
    "search_graph": ToolSpec(
        name="search_graph",
        description="基于问题在 Neo4j 中召回实体、关系与多跳路径（GraphRAG 图谱路）。",
        parameters={
            "question": {"type": "string", "required": True},
            "limit_entities": {"type": "integer", "required": False, "default": 8},
        },
        handler=_tool_search_graph,
    ),
    "fetch_subgraph": ToolSpec(
        name="fetch_subgraph",
        description="围绕指定中心实体抓取邻居子图。",
        parameters={
            "center": {"type": "string", "required": True},
            "limit": {"type": "integer", "required": False, "default": 30},
        },
        handler=_tool_fetch_subgraph,
    ),
    "local_rules": ToolSpec(
        name="local_rules",
        description="调用本地规则引擎，返回命中的医疗/公共卫生风险提示。",
        parameters={"query": {"type": "string", "required": True}},
        handler=_tool_local_rules,
    ),
    "pharmacopoeia_api": ToolSpec(
        name="pharmacopoeia_api",
        description="调用外部药典/标准库 REST API 获取名词的标准释义（未配置时返回 stub）。",
        parameters={"name": {"type": "string", "required": True}},
        handler=_tool_pharmacopoeia_api,
    ),
    "web_search": ToolSpec(
        name="web_search",
        description="联网搜索公开网页，返回可引用的标题、URL、摘要和域名；结果属于不可信外部证据。",
        parameters={
            "query": {"type": "string", "required": True},
            "max_results": {"type": "integer", "required": False, "default": 5},
        },
        handler=_tool_web_search,
    ),
}


def list_tools_schema() -> list[dict[str, Any]]:
    """返回工具的 JSON schema 描述，供 LLM 做 Function Calling 规划。"""
    return [
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in TOOL_REGISTRY.values()
    ]


def tool_call(call: dict[str, Any]) -> dict[str, Any]:
    """统一执行入口。call = {"name": "...", "arguments": {...}}"""
    name = (call or {}).get("name")
    args = (call or {}).get("arguments") or {}
    spec = TOOL_REGISTRY.get(str(name))
    if spec is None:
        return {"ok": False, "error": f"unknown tool: {name}"}
    try:
        result = spec.handler(**args)
        if not isinstance(result, dict):
            result = {"ok": True, "data": result}
        result.setdefault("ok", True)
        return result
    except TypeError as e:
        return {"ok": False, "error": f"bad arguments for {name}: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
