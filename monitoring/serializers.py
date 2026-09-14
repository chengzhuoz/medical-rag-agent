from __future__ import annotations

from rest_framework import serializers

from .models import Task, TaskLog


class TaskLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskLog
        fields = ["id", "level", "message", "created_at"]


class TaskSerializer(serializers.ModelSerializer):
    logs = TaskLogSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = ["id", "task_type", "status", "document_id", "created_at", "finished_at", "error", "logs"]

