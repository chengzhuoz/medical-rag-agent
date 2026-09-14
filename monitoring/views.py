from rest_framework import generics

from .models import Task
from .serializers import TaskSerializer


class TaskListView(generics.ListAPIView):
    queryset = Task.objects.all().order_by("-created_at")
    serializer_class = TaskSerializer


class TaskDetailView(generics.RetrieveAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

