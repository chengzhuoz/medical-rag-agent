import json
import time

import pytest
from django.conf import settings

from qa.agents import agent_retriever_plan, agent_router, execute_plan


def test_router_policy_controls_tool_permissions(monkeypatch):
    monkeypatch.setattr(
        "qa.agents._llm_invoke",
        lambda *_args, **_kwargs: json.dumps({"intent": "risk", "confidence": 0.92, "needs_graph": True}),
    )

    route = agent_router("孕妇使用该器械有哪些风险？", request_id="test-route")

    assert route["intent"] == "risk"
    assert route["needs_graph"] is False
    assert route["needs_rules"] is True
    assert route["requires_human_review"] is True
    assert route["trace_id"] == "test-route"


def test_router_llm_failure_uses_conservative_fallback(monkeypatch):
    monkeypatch.setattr("qa.agents._llm_invoke", lambda *_args, **_kwargs: "__LLM_ERROR__: unavailable")

    route = agent_router("这个产品有哪些禁忌和不良反应？")

    assert route["intent"] == "risk"
    assert route["needs_rules"] is True
    assert route["route_source"] == "fallback"
    assert route["fallback_reason"] == "llm_error"


def test_planner_rejects_unapproved_tools_and_rewrites_arguments(monkeypatch):
    plan_from_model = [
        {"name": "fetch_subgraph", "arguments": {"center": "伪造实体"}},
        {"name": "search_vectorstore", "arguments": {"question": "伪造问题", "top_k": 999}},
        {"name": "search_graph", "arguments": {"question": "伪造问题", "limit_entities": 999}},
        {"name": "local_rules", "arguments": {"query": "伪造问题"}},
    ]
    monkeypatch.setattr("qa.agents._llm_invoke", lambda *_args, **_kwargs: json.dumps(plan_from_model, ensure_ascii=False))

    plan = agent_retriever_plan(
        "某器械的注册风险是什么？",
        {"intent": "regulation", "needs_graph": False, "needs_rules": False},
        top_k=999,
        document_ids=["doc-1"],
    )

    calls = {call["name"]: call["arguments"] for call in plan}
    assert "fetch_subgraph" not in calls
    assert calls["search_vectorstore"] == {"question": "某器械的注册风险是什么？", "document_ids": ["doc-1"], "top_k": 10}
    assert calls["search_graph"]["question"] == "某器械的注册风险是什么？"
    assert calls["search_graph"]["limit_entities"] == 20
    assert calls["local_rules"] == {"query": "某器械的注册风险是什么？"}


def test_executor_preserves_success_when_another_tool_fails(monkeypatch):
    def fake_tool_call(call):
        if call["name"] == "broken_tool":
            raise RuntimeError("backend unavailable")
        return {"ok": True, "data": call["name"]}

    monkeypatch.setattr("qa.agents.tool_call", fake_tool_call)
    monkeypatch.setattr(settings, "MAS_TOOL_TIMEOUT_SECONDS", 1)

    results = execute_plan([
        {"name": "broken_tool", "arguments": {}},
        {"name": "healthy_tool", "arguments": {}},
    ])

    result_by_name = {item["call"]["name"]: item["result"] for item in results}
    assert result_by_name["broken_tool"]["ok"] is False
    assert result_by_name["broken_tool"]["error"] == "tool_execution_failed"
    assert result_by_name["healthy_tool"] == {"ok": True, "data": "healthy_tool"}


def test_executor_times_out_one_tool_without_blocking_others(monkeypatch):
    def fake_tool_call(call):
        if call["name"] == "slow_tool":
            time.sleep(0.2)
        return {"ok": True}

    monkeypatch.setattr("qa.agents.tool_call", fake_tool_call)
    monkeypatch.setattr(settings, "MAS_TOOL_TIMEOUT_SECONDS", 0.1)

    results = execute_plan([{"name": "slow_tool", "arguments": {}}, {"name": "fast_tool", "arguments": {}}])

    result_by_name = {item["call"]["name"]: item["result"] for item in results}
    assert result_by_name["slow_tool"]["error"] == "tool_timeout"
    assert result_by_name["fast_tool"]["ok"] is True
