from django.urls import path

from .views import AskView, EmbedDocumentView, OllamaStatusView

urlpatterns = [
    path("ask/", AskView.as_view(), name="qa-ask"),
    path("embed/<uuid:document_id>/", EmbedDocumentView.as_view(), name="qa-embed-document"),
    path("ollama/status/", OllamaStatusView.as_view(), name="ollama-status"),
]

