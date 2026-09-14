from __future__ import annotations

from django.utils import timezone

from .models import Task, TaskLog


def task_create(task_type: str, document_id: str = "") -> Task:
    t = Task.objects.create(task_type=task_type, document_id=document_id, status=Task.Status.RUNNING)
    TaskLog.objects.create(task=t, level="info", message="started")
    return t


def task_info(task: Task, message: str) -> None:
    TaskLog.objects.create(task=task, level="info", message=message)


def task_fail(task: Task, error: str) -> None:
    task.status = Task.Status.FAILED
    task.error = error
    task.finished_at = timezone.now()
    task.save(update_fields=["status", "error", "finished_at"])
    TaskLog.objects.create(task=task, level="error", message=error)


def task_succeed(task: Task) -> None:
    task.status = Task.Status.SUCCEEDED
    task.finished_at = timezone.now()
    task.save(update_fields=["status", "finished_at"])
    TaskLog.objects.create(task=task, level="info", message="finished")

