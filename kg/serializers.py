from __future__ import annotations

from rest_framework import serializers


class KgBuildResponseSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    chunks = serializers.IntegerField()
    ok = serializers.BooleanField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)
    entities = serializers.IntegerField(required=False)
    edges = serializers.IntegerField(required=False)


class KgSearchResponseSerializer(serializers.Serializer):
    q = serializers.CharField()
    entities = serializers.ListField(child=serializers.CharField())
    ok = serializers.BooleanField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)


class KgSubgraphResponseSerializer(serializers.Serializer):
    center = serializers.CharField()
    nodes = serializers.ListField(child=serializers.DictField())
    edges = serializers.ListField(child=serializers.DictField())
    ok = serializers.BooleanField(required=False)
    error = serializers.CharField(required=False, allow_blank=True)


class KgStatusResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    connected = serializers.BooleanField()
    neo4j_uri = serializers.CharField(allow_blank=True)
    neo4j_user = serializers.CharField(allow_blank=True)
    neo4j_database = serializers.CharField(allow_blank=True)
    error = serializers.CharField(allow_blank=True)
