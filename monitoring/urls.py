from django.urls import path

from .views import TaskDetailView, TaskListView

urlpatterns = [
    path("tasks/", TaskListView.as_view(), name="tasks"),
    path("tasks/<uuid:pk>/", TaskDetailView.as_view(), name="task-detail"),
]

