from django.conf import settings
from django.db.models import Count
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Task
from .serializers import TaskSerializer


class TaskListView(generics.ListAPIView):
    queryset = Task.objects.all().order_by("-created_at")
    serializer_class = TaskSerializer


class TaskDetailView(generics.RetrieveAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer


class ObservabilityOverviewView(APIView):
    """为前端监控页提供配置状态和近期任务摘要，不暴露 LangSmith 密钥。"""

    def get(self, request):
        summary = {item["status"]: item["count"] for item in Task.objects.values("status").annotate(count=Count("id"))}
        return Response({
            "langsmith": {
                "enabled": bool(settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY),
                "project": settings.LANGSMITH_PROJECT,
                "dashboard_url": settings.LANGSMITH_DASHBOARD_URL,
            },
            "prometheus": {"metrics_url": "/metrics", "dashboard_url": settings.PROMETHEUS_URL},
            "grafana": {"dashboard_url": settings.GRAFANA_URL},
            "tasks": {
                "running": summary.get(Task.Status.RUNNING, 0),
                "succeeded": summary.get(Task.Status.SUCCEEDED, 0),
                "failed": summary.get(Task.Status.FAILED, 0),
            },
        })
