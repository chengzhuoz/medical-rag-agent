from __future__ import annotations

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from django.conf import settings
from neo4j import GraphDatabase

from .serializers import KgBuildResponseSerializer, KgSearchResponseSerializer, KgStatusResponseSerializer, KgSubgraphResponseSerializer
from .services import KgNotConfiguredError, build_graph_for_document, fetch_subgraph, search_entities


class KgBuildView(GenericAPIView):
    serializer_class = KgBuildResponseSerializer

    @extend_schema(request=None, responses=KgBuildResponseSerializer)
    def post(self, request, document_id):
        try:
            out = build_graph_for_document(str(document_id))
            ser = KgBuildResponseSerializer(
                {"document_id": document_id, "chunks": out["chunks"], "entities": out.get("entities", 0), "edges": out.get("edges", 0), "ok": True, "error": ""}
            )
            return Response(ser.data, status=status.HTTP_200_OK)
        except KgNotConfiguredError as e:
            ser = KgBuildResponseSerializer({"document_id": document_id, "chunks": 0, "entities": 0, "edges": 0, "ok": False, "error": str(e)})
            return Response(ser.data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(name="q", required=True, type=str),
            OpenApiParameter(name="limit", required=False, type=int),
        ],
        responses=KgSearchResponseSerializer,
    )
)
class KgSearchView(GenericAPIView):
    serializer_class = KgSearchResponseSerializer

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        limit = int(request.query_params.get("limit") or 20)
        if not q:
            return Response({"detail": "缺少参数 q"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            entities = search_entities(q, limit=min(max(limit, 1), 50))
            ser = KgSearchResponseSerializer({"q": q, "entities": entities, "ok": True, "error": ""})
            return Response(ser.data, status=status.HTTP_200_OK)
        except KgNotConfiguredError as e:
            ser = KgSearchResponseSerializer({"q": q, "entities": [], "ok": False, "error": str(e)})
            return Response(ser.data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(name="center", required=True, type=str),
            OpenApiParameter(name="limit", required=False, type=int),
        ],
        responses=KgSubgraphResponseSerializer,
    )
)
class KgSubgraphView(GenericAPIView):
    serializer_class = KgSubgraphResponseSerializer

    def get(self, request):
        center = (request.query_params.get("center") or "").strip()
        limit = int(request.query_params.get("limit") or 60)
        if not center:
            return Response({"detail": "缺少参数 center"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sg = fetch_subgraph(center=center, limit=min(max(limit, 1), 200))
            ser = KgSubgraphResponseSerializer({"center": center, "nodes": sg.nodes, "edges": sg.edges, "ok": True, "error": ""})
            return Response(ser.data, status=status.HTTP_200_OK)
        except KgNotConfiguredError as e:
            ser = KgSubgraphResponseSerializer({"center": center, "nodes": [], "edges": [], "ok": False, "error": str(e)})
            return Response(ser.data, status=status.HTTP_200_OK)


class KgStatusView(GenericAPIView):
    serializer_class = KgStatusResponseSerializer

    @extend_schema(request=None, responses=KgStatusResponseSerializer)
    def get(self, request):
        uri = getattr(settings, "NEO4J_URI", "") or ""
        user = getattr(settings, "NEO4J_USER", "") or ""
        database = getattr(settings, "NEO4J_DATABASE", "neo4j") or "neo4j"
        password = getattr(settings, "NEO4J_PASSWORD", "") or ""
        if not uri or not user or not password:
            ser = KgStatusResponseSerializer(
                {
                    "ok": False,
                    "connected": False,
                    "neo4j_uri": uri,
                    "neo4j_user": user,
                    "neo4j_database": database,
                    "error": "Neo4j 未配置，请设置 NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD（注意是 .env，不是 .env.example）",
                }
            )
            return Response(ser.data, status=status.HTTP_200_OK)

        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            try:
                with driver.session(database=database) as session:
                    session.run("RETURN 1 AS ok").single()
            finally:
                driver.close()
            ser = KgStatusResponseSerializer(
                {"ok": True, "connected": True, "neo4j_uri": uri, "neo4j_user": user, "neo4j_database": database, "error": ""}
            )
            return Response(ser.data, status=status.HTTP_200_OK)
        except Exception as e:
            ser = KgStatusResponseSerializer(
                {"ok": False, "connected": False, "neo4j_uri": uri, "neo4j_user": user, "neo4j_database": database, "error": str(e)}
            )
            return Response(ser.data, status=status.HTTP_200_OK)
