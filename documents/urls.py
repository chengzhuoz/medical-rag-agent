from django.urls import path

from .views import DocumentDetailView, DocumentListCreateView, DocumentParseView

urlpatterns = [
    path("", DocumentListCreateView.as_view(), name="documents"),
    path("<uuid:pk>/", DocumentDetailView.as_view(), name="document-detail"),
    path("<uuid:pk>/parse/", DocumentParseView.as_view(), name="document-parse"),
]

