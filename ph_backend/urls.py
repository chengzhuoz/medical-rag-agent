from __future__ import annotations

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

urlpatterns = [
    path("healthz/", lambda request: JsonResponse({"ok": True}), name="healthz"),
    path("metrics", lambda request: HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST), name="metrics"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/documents/", include("documents.urls")),
    path("api/qa/", include("qa.urls")),
    path("api/monitoring/", include("monitoring.urls")),
    path("api/kg/", include("kg.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
