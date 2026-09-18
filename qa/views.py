from __future__ import annotations

from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from documents.models import Document, DocumentChunk
from documents.serializers import DocumentSerializer

from .serializers import AskRequestSerializer, AskResponseSerializer, EmbedDocumentResponseSerializer, OllamaStatusSerializer
from .services import ask_question, embed_texts, list_ollama_models
from kg.services import KgNotConfiguredError, graph_context_for_question


class EmbedDocumentView(GenericAPIView):
    serializer_class = EmbedDocumentResponseSerializer

    @extend_schema(request=None, responses=EmbedDocumentResponseSerializer)
    def post(self, request, document_id):
        doc = get_object_or_404(Document, id=document_id)
        chunks = DocumentChunk.objects.filter(document=doc).order_by("chunk_index")
        if not chunks.exists():
            doc.status = Document.Status.FAILED
            doc.error_message = "未找到可向量化的 chunk：请先完成解析，且确保 PDF 可提取文本。"
            doc.save(update_fields=["status", "error_message"])
            return Response({"document": DocumentSerializer(doc, context={"request": request}).data})
        texts = [c.content for c in chunks]
        metadatas = [{"document_id": str(doc.id), "chunk_index": c.chunk_index, "original_name": doc.original_name} for c in chunks]
        embed_texts(texts=texts, metadatas=metadatas, document_id=str(doc.id))
        doc.status = Document.Status.EMBEDDED
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message"])
        return Response({"document": DocumentSerializer(doc, context={"request": request}).data})


class AskView(GenericAPIView):
    serializer_class = AskRequestSerializer

    @extend_schema(request=AskRequestSerializer, responses=AskResponseSerializer)
    def post(self, request):
        req = self.get_serializer(data=request.data)
        req.is_valid(raise_exception=True)
        question = req.validated_data["question"]
        document_ids = [str(x) for x in req.validated_data.get("document_ids") or []]
        top_k = int(req.validated_data.get("top_k") or 4)
        retrieval_options = {
            "use_vector": req.validated_data.get("use_vector", True),
            "use_graph": req.validated_data.get("use_graph", True),
            "use_web": req.validated_data.get("use_web", True),
        }
        try:
            graph = {}
            if retrieval_options["use_graph"]:
                try:
                    graph = graph_context_for_question(question)
                    if graph:
                        graph = {"ok": True, "error": "", **graph}
                except KgNotConfiguredError as e:
                    graph = {"ok": False, "error": str(e), "keywords": [], "nodes": [], "edges": []}
            result = ask_question(
                question=question,
                document_ids=document_ids or None,
                top_k=top_k,
                graph=graph,
                retrieval_options=retrieval_options,
            )
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        resp = AskResponseSerializer({
            "answer": result.answer,
            "contexts": result.contexts,
            "graph": result.graph,
            "trace": getattr(result, "trace", None),
        })
        return Response(resp.data, status=status.HTTP_200_OK)


class OllamaStatusView(GenericAPIView):
    serializer_class = OllamaStatusSerializer

    @extend_schema(request=None, responses=OllamaStatusSerializer)
    def get(self, request):
        from django.conf import settings

        try:
            models = list_ollama_models()
            model_available = settings.OLLAMA_MODEL in set(models)
            payload = {
                "base_url": settings.OLLAMA_BASE_URL,
                "model": settings.OLLAMA_MODEL,
                "ok": True,
                "model_available": model_available,
                "available_models": models,
                "error": "",
            }
        except Exception as e:
            payload = {
                "base_url": settings.OLLAMA_BASE_URL,
                "model": settings.OLLAMA_MODEL,
                "ok": False,
                "model_available": False,
                "available_models": [],
                "error": str(e),
            }
        ser = OllamaStatusSerializer(payload)
        return Response(ser.data, status=status.HTTP_200_OK)

