"""多智能体（MAS）编排：Router → Retriever → Tools → Answer → Reviewer。

设计：
- Router(Qwen 8B)    : 意图路由（factoid / multi_hop / regulation / risk / chitchat）
- Retriever(Qwen 8B) : 关键词扩展 + 工具调用规划
- Tool Executor      : 调用 qa.tools 中注册的工具（向量/图谱/规则/外部 API）
- Answer(DeepSeek)   : 融合证据生成结构化答案（GraphRAG Prompt）
- Reviewer(DeepSeek) : 校验幻觉/证据缺口/医疗风险，必要时回写补充建议

Ollama 调用通过 langchain_community.llms.Ollama 完成；JSON 解析做了容错。
"""
from __future__ import annotations

import json
import re
import asyncio
from typing import Any

from monitoring.services import task_create, task_fail, task_info, task_succeed

from .services import AskResult, format_contexts, get_llm, retrieve_chunks
from .tools import list_tools_schema, tool_call


# --------------------------- 工具：JSON 解析容错 ---------------------------

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")


def _safe_json(text: str, default: Any) -> Any:
    if not text:
        return default
    s = text.strip()
    s = re.sub(r"^```(?:json)?", "", s).strip()
    s = re.sub(r"```$", "", s).strip()
    try:
        return json.loads(s)
    except Exception:
        m = _JSON_BLOCK.search(s)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return default
        return default


def _llm_invoke(role: str, prompt: str, temperature: float = 0.0) -> str:
    llm = get_llm(role=role, temperature=temperature)
    try:
        out = llm.invoke(prompt)
    except Exception as e:
        return f"__LLM_ERROR__: {e}"
    return str(out or "").strip()


# --------------------------- Agent：Router ---------------------------

_ROUTE_PROMPT = """你是医疗器械与公共卫生领域的意图路由器。请判断下面问题的意图类型，并输出严格 JSON。

可选意图：
- factoid       : 单点事实查询
- multi_hop     : 涉及多个实体、需要跨段/跨文档推理
- regulation    : 涉及法规、注册、标准、审批
- risk          : 涉及医疗风险/禁忌/不良反应/特殊人群
- chitchat      : 闲聊或与领域无关

输出格式（仅 JSON，不要解释）：
{"intent": "<上面之一>", "needs_graph": true|false, "needs_rules": true|false, "reason": "<不超过30字>"}

问题：{question}
"""


def agent_router(question: str) -> dict[str, Any]:
    raw = _llm_invoke("router", _ROUTE_PROMPT.replace("{question}", question), temperature=0.0)
    data = _safe_json(raw, default={})
    intent = str(data.get("intent") or "factoid").strip().lower()
    if intent not in {"factoid", "multi_hop", "regulation", "risk", "chitchat"}:
        intent = "factoid"
    return {
        "intent": intent,
        "needs_graph": bool(data.get("needs_graph", intent in {"multi_hop", "regulation"})),
        "needs_rules": bool(data.get("needs_rules", intent in {"risk", "regulation"})),
        "reason": str(data.get("reason") or "")[:80],
        "raw": raw,
    }


# --------------------------- Agent：Retriever（规划工具调用） ---------------------------

_PLAN_PROMPT = """你是检索规划智能体。基于问题与可用工具，输出一份最小化的工具调用计划（严格 JSON 数组）。
约束：
- 至少包含一次 search_vectorstore。
- 若意图为 multi_hop/regulation 或 needs_graph=true，加入一次 search_graph。
- 若 needs_rules=true，加入一次 local_rules。
- 不要重复同名工具。最多 4 次调用。

可用工具：
{tools}

上下文：
- 问题：{question}
- 意图：{intent}
- needs_graph={needs_graph}, needs_rules={needs_rules}
- top_k={top_k}, document_ids={document_ids}

只输出 JSON 数组，元素形如：{"name":"<tool>","arguments":{...}}
"""


def agent_retriever_plan(question: str, route: dict[str, Any], top_k: int, document_ids: list[str] | None) -> list[dict[str, Any]]:
    tools_desc = json.dumps(list_tools_schema(), ensure_ascii=False)
    prompt = (
        _PLAN_PROMPT
        .replace("{tools}", tools_desc)
        .replace("{question}", question)
        .replace("{intent}", route.get("intent", "factoid"))
        .replace("{needs_graph}", "true" if route.get("needs_graph") else "false")
        .replace("{needs_rules}", "true" if route.get("needs_rules") else "false")
        .replace("{top_k}", str(top_k))
        .replace("{document_ids}", json.dumps(document_ids or [], ensure_ascii=False))
    )
    raw = _llm_invoke("retriever", prompt, temperature=0.0)
    plan = _safe_json(raw, default=None)

    fallback: list[dict[str, Any]] = [
        {"name": "search_vectorstore", "arguments": {"question": question, "document_ids": document_ids or [], "top_k": top_k}},
    ]
    if route.get("needs_graph"):
        fallback.append({"name": "search_graph", "arguments": {"question": question, "limit_entities": 8}})
    if route.get("needs_rules"):
        fallback.append({"name": "local_rules", "arguments": {"query": question}})

    if not isinstance(plan, list) or not plan:
        return fallback

    norm: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in plan[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name in seen:
            continue
        args = item.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        if name == "search_vectorstore":
            args.setdefault("question", question)
            args.setdefault("top_k", top_k)
            if document_ids:
                args.setdefault("document_ids", document_ids)
        if name == "search_graph":
            args.setdefault("question", question)
        if name == "local_rules":
            args.setdefault("query", question)
        norm.append({"name": name, "arguments": args})
        seen.add(name)
    if "search_vectorstore" not in seen:
        norm.insert(0, fallback[0])
    return norm


# --------------------------- Tool Executor ---------------------------

async def execute_plan_async(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """并发执行相互独立的工具调用；同步 SDK 在线程池中运行。"""
    async def run_one(call: dict[str, Any]) -> dict[str, Any]:
        out = await asyncio.to_thread(tool_call, call)
        return {"call": call, "result": out}

    return list(await asyncio.gather(*(run_one(call) for call in plan)))


def execute_plan(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """兼容同步调用方，同时使用 asyncio + 工作线程执行工具。"""
    return asyncio.run(execute_plan_async(plan))


# --------------------------- Agent：Answer ---------------------------

_ANSWER_PROMPT = """你是医疗器械与公共卫生领域的专家助手。融合下列“双路证据”作答。

A) 文本证据（向量检索 chunk，编号 [1][2]…）：
{contexts}

B) 图谱证据（Neo4j 实体/关系/多跳路径，引用用 (G)）：
关键词：{kw}
实体：{nodes}
关系：
{edges}
路径：
{paths}

C) 规则提示（若有）：
{rules}

要求：
1) 先给出结论（要点列表，3~6 条）。
2) 引用证据：文本证据用 [n]；图谱用 (G)；规则用 (R)。
3) 若证据不足，明确指出缺口并给出建议补充（不要编造）。
4) 涉及风险/禁忌/特殊人群的，请单列“风险提示”。
5) 中文回答，结构清晰。

问题：{question}
"""


def _format_graph_for_prompt(g: dict[str, Any]) -> tuple[str, str, str, str]:
    g = g or {}
    kw = "、".join([str(x) for x in (g.get("keywords") or [])][:12]) or "(无)"
    nodes = "、".join([str(n.get("label") or n.get("id")) for n in (g.get("nodes") or [])[:20]]) or "(无)"
    edges_lines = []
    for e in (g.get("edges") or [])[:20]:
        edges_lines.append(f"- {e.get('source')} -[{e.get('type')}({e.get('weight',1)})]-> {e.get('target')}")
    edges_text = "\n".join(edges_lines) or "(无)"
    paths_lines = []
    for p in (g.get("paths") or [])[:12]:
        ns = p.get("nodes") or []
        if ns:
            paths_lines.append("- " + " → ".join(str(n) for n in ns))
    paths_text = "\n".join(paths_lines) or "(无)"
    return kw, nodes, edges_text, paths_text


def agent_answer(question: str, contexts: list[dict[str, Any]], graph: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    ctx_text = "\n\n".join([f"[{c.get('rank', i+1)}] {c.get('text','')}" for i, c in enumerate(contexts)]) or "(无)"
    kw, nodes, edges_text, paths_text = _format_graph_for_prompt(graph)
    rules_text = "\n".join([f"- (R) {r.get('matched')}: {r.get('advice')}" for r in (rules or [])]) or "(无)"
    prompt = (
        _ANSWER_PROMPT
        .replace("{contexts}", ctx_text)
        .replace("{kw}", kw)
        .replace("{nodes}", nodes)
        .replace("{edges}", edges_text)
        .replace("{paths}", paths_text)
        .replace("{rules}", rules_text)
        .replace("{question}", question)
    )
    return _llm_invoke("answer", prompt, temperature=0.1)


# --------------------------- Agent：Reviewer ---------------------------

_REVIEW_PROMPT = """你是答案审查智能体。请基于“原问题 + 证据 + 候选答案”输出严格 JSON：
{"ok": true|false, "issues": ["..."], "patch": "若有需要补充/纠正的简短追加说明，否则空字符串"}

判定准则：
- 候选答案中的关键事实是否能在文本证据 [n] 或图谱 (G) 中找到对应支撑。
- 是否存在医疗风险却未提示。
- 是否引用了未给出的材料。

问题：{question}

文本证据：
{contexts}

图谱关键词：{kw}
图谱关系：
{edges}

候选答案：
{answer}
"""


def agent_reviewer(question: str, answer: str, contexts: list[dict[str, Any]], graph: dict[str, Any]) -> dict[str, Any]:
    ctx_text = "\n\n".join([f"[{c.get('rank', i+1)}] {c.get('text','')[:400]}" for i, c in enumerate(contexts)]) or "(无)"
    kw, _nodes, edges_text, _paths = _format_graph_for_prompt(graph)
    prompt = (
        _REVIEW_PROMPT
        .replace("{question}", question)
        .replace("{contexts}", ctx_text)
        .replace("{kw}", kw)
        .replace("{edges}", edges_text)
        .replace("{answer}", answer or "")
    )
    raw = _llm_invoke("reviewer", prompt, temperature=0.0)
    data = _safe_json(raw, default={"ok": True, "issues": [], "patch": ""})
    return {
        "ok": bool(data.get("ok", True)),
        "issues": [str(x) for x in (data.get("issues") or [])][:8],
        "patch": str(data.get("patch") or "")[:600],
        "raw": raw,
    }


# --------------------------- 编排入口 ---------------------------

def run_mas_pipeline(question: str, document_ids: list[str] | None, top_k: int, graph: dict[str, Any] | None = None) -> AskResult:
    t = task_create(task_type="qa")
    trace: dict[str, Any] = {"pipeline": "mas", "steps": []}
    try:
        # 1) Router
        route = agent_router(question)
        trace["route"] = {k: v for k, v in route.items() if k != "raw"}
        task_info(t, message=f"router intent={route['intent']} graph={route['needs_graph']} rules={route['needs_rules']}")

        # 2) Retriever 规划
        plan = agent_retriever_plan(question, route, top_k=top_k, document_ids=document_ids)
        trace["plan"] = plan
        task_info(t, message=f"plan={[c.get('name') for c in plan]}")

        # 3) Tool Executor
        results = execute_plan(plan)
        trace["tool_calls"] = [
            {"name": r["call"].get("name"), "ok": r["result"].get("ok", True)} for r in results
        ]
        trace["execution"] = {"mode": "asyncio.to_thread", "parallel": len(plan) > 1, "tool_count": len(plan)}

        # 4) 汇总证据
        contexts: list[dict[str, Any]] = []
        graph_ctx: dict[str, Any] = graph or {"keywords": [], "nodes": [], "edges": [], "paths": []}
        rules_hits: list[dict[str, Any]] = []
        for r in results:
            name = r["call"].get("name")
            res = r["result"] or {}
            if name == "search_vectorstore" and res.get("ok", True):
                contexts = res.get("contexts") or contexts
            elif name == "search_graph" and res.get("ok"):
                graph_ctx = {
                    "ok": True,
                    "error": "",
                    "keywords": res.get("keywords") or [],
                    "nodes": res.get("nodes") or [],
                    "edges": res.get("edges") or [],
                    "paths": res.get("paths") or [],
                }
            elif name == "local_rules" and res.get("ok"):
                rules_hits = res.get("hits") or []

        # 兜底：若 plan 没跑向量检索（极端情况），直接补
        if not contexts:
            docs = retrieve_chunks(question=question, document_ids=document_ids, top_k=top_k)
            contexts = format_contexts(docs)

        # 5) Answer
        answer = agent_answer(question, contexts=contexts, graph=graph_ctx, rules=rules_hits)
        if answer.startswith("__LLM_ERROR__"):
            raise RuntimeError(answer.replace("__LLM_ERROR__: ", ""))

        # 6) Reviewer（失败/有补丁则追加，不阻断）
        review = agent_reviewer(question, answer=answer, contexts=contexts, graph=graph_ctx)
        trace["review"] = {"ok": review["ok"], "issues": review["issues"], "patched": bool(review["patch"])}
        if review.get("patch"):
            answer = f"{answer}\n\n---\n校验补充：{review['patch']}"
        if review.get("issues"):
            answer = f"{answer}\n\n校验提示：\n" + "\n".join([f"- {x}" for x in review['issues']])

        task_succeed(t)
        return AskResult(answer=str(answer), contexts=contexts, graph=graph_ctx, trace=trace)
    except Exception as e:
        task_fail(t, error=str(e))
        raise
