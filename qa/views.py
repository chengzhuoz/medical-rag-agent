from __future__ import annotations

import json
import uuid
from queue import Empty, Queue
from threading import Thread

from django.db import close_old_connections
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from documents.models import Document, DocumentChunk
from documents.serializers import DocumentSerializer

from .memory import clear_memory, memory_overview, prepare_memory_context, remember_turn
from .serializers import AskRequestSerializer, AskResponseSerializer, EmbedDocumentResponseSerializer, MemoryScopeSerializer, OllamaStatusSerializer
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
        memory_enabled = req.validated_data.get("memory_enabled", True)
        memory_scope_id = req.validated_data.get("memory_scope_id") or uuid.uuid4()
        conversation_id = req.validated_data.get("conversation_id") or uuid.uuid4()
        retrieval_options = {
            "use_vector": req.validated_data.get("use_vector", True),
            "use_graph": req.validated_data.get("use_graph", True),
            "use_web": req.validated_data.get("use_web", True),
        }
        try:
            conversation, memory_context = prepare_memory_context(memory_scope_id, conversation_id, question, enabled=memory_enabled)
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
                memory_context=memory_context,
            )
            remember_turn(conversation, question, result.answer, enabled=memory_enabled)
        except RuntimeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        resp = AskResponseSerializer({
            "answer": result.answer,
            "contexts": result.contexts,
            "graph": result.graph,
            "trace": getattr(result, "trace", None),
        })
        return Response(resp.data, status=status.HTTP_200_OK)


class AskStreamView(GenericAPIView):
    """SSE 问答接口：输出可审计运行事件和回答 token，不输出模型原始隐式推理。"""

    serializer_class = AskRequestSerializer

    def post(self, request):
        req = self.get_serializer(data=request.data)
        req.is_valid(raise_exception=True)
        payload = req.validated_data
        queue: Queue[dict] = Queue()

        def emit(event: str, data: dict) -> None:
            queue.put({"event": event, "data": data})

        def run_pipeline() -> None:
            close_old_connections()
            question = payload["question"]
            document_ids = [str(item) for item in payload.get("document_ids") or []]
            top_k = int(payload.get("top_k") or 4)
            memory_enabled = payload.get("memory_enabled", True)
            memory_scope_id = payload.get("memory_scope_id") or uuid.uuid4()
            conversation_id = payload.get("conversation_id") or uuid.uuid4()
            retrieval_options = {
                "use_vector": payload.get("use_vector", True),
                "use_graph": payload.get("use_graph", True),
                "use_web": payload.get("use_web", True),
            }
            try:
                emit("progress", {"step": "memory", "message": "正在载入并压缩会话记忆"})
                conversation, memory_context = prepare_memory_context(memory_scope_id, conversation_id, question, enabled=memory_enabled)
                graph = {}
                if retrieval_options["use_graph"]:
                    try:
                        graph = graph_context_for_question(question)
                        if graph:
                            graph = {"ok": True, "error": "", **graph}
                    except KgNotConfiguredError as error:
                        graph = {"ok": False, "error": str(error), "keywords": [], "nodes": [], "edges": []}
                result = ask_question(
                    question=question,
                    document_ids=document_ids or None,
                    top_k=top_k,
                    graph=graph,
                    retrieval_options=retrieval_options,
                    memory_context=memory_context,
                    progress_callback=lambda step, message: emit("progress", {"step": step, "message": message}),
                    token_callback=lambda token: emit("token", {"token": token}),
                )
                remember_turn(conversation, question, result.answer, enabled=memory_enabled)
                response_data = AskResponseSerializer({
                    "answer": result.answer,
                    "contexts": result.contexts,
                    "graph": result.graph,
                    "trace": getattr(result, "trace", None),
                }).data
                emit("complete", {"result": response_data, "memory": memory_overview(memory_scope_id) if memory_enabled else None})
            except Exception as error:
                emit("error", {"detail": str(error)})
            finally:
                close_old_connections()

        Thread(target=run_pipeline, daemon=True, name="qa-sse-pipeline").start()

        def event_stream():
            while True:
                try:
                    item = queue.get(timeout=15)
                except Empty:
                    yield ": keepalive\n\n"
                    continue
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                if item["event"] in {"complete", "error"}:
                    break

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class MemoryOverviewView(GenericAPIView):
    serializer_class = MemoryScopeSerializer

    def get(self, request):
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(memory_overview(serializer.validated_data["memory_scope_id"]))


class MemoryClearView(GenericAPIView):
    serializer_class = MemoryScopeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        clear_memory(serializer.validated_data["memory_scope_id"])
        return Response(status=status.HTTP_204_NO_CONTENT)


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
