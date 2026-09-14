from django.urls import path

from .views import KgBuildView, KgSearchView, KgStatusView, KgSubgraphView

urlpatterns = [
    path("build/<uuid:document_id>/", KgBuildView.as_view(), name="kg-build"),
    path("search/", KgSearchView.as_view(), name="kg-search"),
    path("status/", KgStatusView.as_view(), name="kg-status"),
    path("subgraph/", KgSubgraphView.as_view(), name="kg-subgraph"),
]
