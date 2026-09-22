from django.urls import path

from .views import AskStreamView, AskView, EmbedDocumentView, MemoryClearView, MemoryOverviewView, OllamaStatusView

urlpatterns = [
    path("ask/", AskView.as_view(), name="qa-ask"),
    path("ask/stream/", AskStreamView.as_view(), name="qa-ask-stream"),
    path("memory/overview/", MemoryOverviewView.as_view(), name="qa-memory-overview"),
    path("memory/clear/", MemoryClearView.as_view(), name="qa-memory-clear"),
    path("embed/<uuid:document_id>/", EmbedDocumentView.as_view(), name="qa-embed-document"),
    path("ollama/status/", OllamaStatusView.as_view(), name="ollama-status"),
]
