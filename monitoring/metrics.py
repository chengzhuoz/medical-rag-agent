"""Prometheus 指标定义与低基数标签辅助函数。"""
from __future__ import annotations

import re

from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "medical_rag_http_requests_total",
    "HTTP 请求总数。",
    ("method", "path", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "medical_rag_http_request_duration_seconds",
    "HTTP 请求处理耗时。",
    ("method", "path"),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "medical_rag_http_requests_in_progress",
    "正在处理的 HTTP 请求数。",
    ("method", "path"),
)
QA_REQUESTS_TOTAL = Counter(
    "medical_rag_qa_requests_total",
    "问答请求总数。",
    ("outcome", "intent"),
)
QA_PIPELINE_DURATION_SECONDS = Histogram(
    "medical_rag_qa_pipeline_duration_seconds",
    "多 Agent 问答流水线耗时。",
    ("intent",),
)
AGENT_DURATION_SECONDS = Histogram(
    "medical_rag_agent_duration_seconds",
    "单个 Agent 执行耗时。",
    ("agent", "outcome"),
)
TOOL_CALLS_TOTAL = Counter(
    "medical_rag_tool_calls_total",
    "工具调用总数。",
    ("tool", "outcome"),
)
TOOL_DURATION_SECONDS = Histogram(
    "medical_rag_tool_duration_seconds",
    "工具调用耗时。",
    ("tool", "outcome"),
)
RERANK_REQUESTS_TOTAL = Counter(
    "medical_rag_rerank_requests_total",
    "重排序请求总数。",
    ("outcome",),
)
RERANK_DURATION_SECONDS = Histogram(
    "medical_rag_rerank_duration_seconds",
    "Cross-Encoder 重排序耗时。",
    ("outcome",),
)
RERANK_CANDIDATES = Histogram(
    "medical_rag_rerank_candidates",
    "每次重排序的候选文档数。",
)


_UUID_IN_PATH = re.compile(r"/[0-9a-f]{8}-[0-9a-f-]{27,}/", re.IGNORECASE)
_NUMBER_IN_PATH = re.compile(r"/\d+/")


def metric_path(path: str) -> str:
    """归一化路径，防止文档 ID 等动态值导致 Prometheus 标签爆炸。"""
    normalized = _UUID_IN_PATH.sub("/:id/", path or "/")
    return _NUMBER_IN_PATH.sub("/:id/", normalized)