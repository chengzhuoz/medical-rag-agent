from django.contrib import admin

from .models import Task, TaskLog


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["id", "task_type", "status", "document_id", "created_at", "finished_at"]
    search_fields = ["id", "task_type", "document_id"]
    list_filter = ["task_type", "status", "created_at"]


@admin.register(TaskLog)
class TaskLogAdmin(admin.ModelAdmin):
    list_display = ["id", "task", "level", "created_at"]
    search_fields = ["id", "task__id", "message"]
    list_filter = ["level", "created_at"]

