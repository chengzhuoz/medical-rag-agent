from __future__ import annotations

from rest_framework import serializers


class AskRequestSerializer(serializers.Serializer):
    question = serializers.CharField()
    document_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=True)
    top_k = serializers.IntegerField(required=False, min_value=1, max_value=20, default=4)
    use_vector = serializers.BooleanField(required=False, default=True)
    use_graph = serializers.BooleanField(required=False, default=True)
    use_web = serializers.BooleanField(required=False, default=True)


class AskResponseSerializer(serializers.Serializer):
    answer = serializers.CharField()
    contexts = serializers.ListField(child=serializers.DictField(), required=True)
    graph = serializers.DictField(required=False)
    trace = serializers.DictField(required=False, allow_null=True)


class EmbedDocumentResponseSerializer(serializers.Serializer):
    document = serializers.DictField()


class OllamaStatusSerializer(serializers.Serializer):
    base_url = serializers.CharField()
    model = serializers.CharField()
    ok = serializers.BooleanField()
    model_available = serializers.BooleanField()
    available_models = serializers.ListField(child=serializers.CharField(), required=False)
    error = serializers.CharField(required=False, allow_blank=True)

