from __future__ import annotations

from rest_framework import serializers

from .models import Document, DocumentChunk


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ["id", "original_name", "uploaded_at", "status", "error_message", "file_url"]

    def get_file_url(self, obj: Document) -> str | None:
        request = self.context.get("request")
        if request is None:
            return None
        if not obj.file:
            return None
        return request.build_absolute_uri(obj.file.url)


class DocumentDetailSerializer(DocumentSerializer):
    class Meta(DocumentSerializer.Meta):
        fields = DocumentSerializer.Meta.fields + ["parsed_text"]


class DocumentChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentChunk
        fields = ["id", "chunk_index", "page_start", "page_end", "content", "created_at"]


class UploadDocumentSerializer(serializers.Serializer):
    file = serializers.FileField()


class ParseDocumentResponseSerializer(serializers.Serializer):
    document_id = serializers.UUIDField()
    pages = serializers.IntegerField()
    chunks = serializers.IntegerField()

