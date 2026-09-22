from django.urls import path

from .views import ObservabilityOverviewView, TaskDetailView, TaskListView

urlpatterns = [
    path("tasks/", TaskListView.as_view(), name="tasks"),
    path("overview/", ObservabilityOverviewView.as_view(), name="observability-overview"),
    path("tasks/<uuid:pk>/", TaskDetailView.as_view(), name="task-detail"),
]
