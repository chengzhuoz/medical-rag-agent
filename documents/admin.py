from django.contrib import admin

from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["id", "original_name", "status", "uploaded_at"]
    search_fields = ["original_name", "id"]
    list_filter = ["status", "uploaded_at"]


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ["id", "document", "chunk_index", "created_at"]
    search_fields = ["id", "document__id", "document__original_name"]
    list_filter = ["created_at"]

