from __future__ import annotations

import time

from .metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_IN_PROGRESS, HTTP_REQUESTS_TOTAL, metric_path


class PrometheusMetricsMiddleware:
    """记录 HTTP 指标；排除 /metrics，避免 Prometheus 抓取自身形成噪声。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/metrics":
            return self.get_response(request)

        method = request.method
        path = metric_path(request.path)
        started_at = time.perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()
        try:
            response = self.get_response(request)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(response.status_code)).inc()
            return response
        except Exception:
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status="500").inc()
            raise
        finally:
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(time.perf_counter() - started_at)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()