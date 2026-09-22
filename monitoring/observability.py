"""LangSmith 可选追踪封装，关闭时不影响本地或离线问答。"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from django.conf import settings


CallableResult = TypeVar("CallableResult")


def langsmith_trace(name: str, run_type: str = "chain"):
    """只在显式启用且配置 API Key 后发送 LangSmith 追踪。"""
    def decorator(func: Callable[..., CallableResult]) -> Callable[..., CallableResult]:
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any) -> CallableResult:
            if not getattr(settings, "LANGSMITH_TRACING", False) or not getattr(settings, "LANGSMITH_API_KEY", ""):
                return func(*args, **kwargs)
            try:
                from langsmith import traceable
                traced = traceable(name=name, run_type=run_type)(func)
            except Exception:
                return func(*args, **kwargs)
            # LangSmith 会在网络异常时自行降级；业务函数异常必须原样抛出，不能重复执行。
            return traced(*args, **kwargs)
        return wrapped
    return decorator