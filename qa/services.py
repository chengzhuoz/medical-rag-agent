from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from collections.abc import Callable

from django.conf import settings

import requests
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain_community.llms.ollama import OllamaEndpointNotFoundError
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument
from langchain_core.embeddings import Embeddings

from monitoring.services import task_create, task_fail, task_info, task_succeed
from monitoring.metrics import RERANK_CANDIDATES, RERANK_DURATION_SECONDS, RERANK_REQUESTS_TOTAL


logger = logging.getLogger(__name__)


class HashEmbeddings(Embeddings):
    def __init__(self, dim: int = 384):
        self.dim = int(dim)

    def _embed_one(self, text: str) -> list[float]:
        import hashlib
        import math
        import re

        vec = [0.0] * self.dim
        s = (text or "").strip()
        if not s:
            return vec

        tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z0-9]{2,32}", s)
        if not tokens:
            tokens = [s[:64]]

        for tok in tokens[:800]:
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little", signed=False) % self.dim
            sign = 1.0 if (h[4] & 1) == 0 else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


_embeddings_cache: Embeddings | None = None
_reranker_cache: Any | None = None
_reranker_initialized = False
_reranker_lock = Lock()


def get_embeddings() -> Embeddings:
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    if getattr(settings, "USE_HASH_EMBEDDINGS", False) or str(getattr(settings, "EMBEDDING_MODEL_NAME", "")).strip().lower() in {"hash", "local-hash"}:
        _embeddings_cache = HashEmbeddings(dim=384)
        return _embeddings_cache
    try:
        emb = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)
        _ = emb.embed_query("健康")
        _embeddings_cache = emb
        return emb
    except Exception:
        _embeddings_cache = HashEmbeddings(dim=384)
        return _embeddings_cache


def _vectorstore_dir() -> Path:
    return Path(settings.VECTORSTORE_DIR)


def _milvus_client():
    from pymilvus import MilvusClient

    kwargs = {"uri": settings.MILVUS_URI}
    if settings.MILVUS_TOKEN:
        kwargs["token"] = settings.MILVUS_TOKEN
    return MilvusClient(**kwargs)


def _milvus_collection(client, dimension: int):
    from pymilvus import DataType

    name = settings.MILVUS_COLLECTION
    if client.has_collection(collection_name=name):
        client.load_collection(collection_name=name)
        return name
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
    schema.add_field(field_name="document_id", datatype=DataType.VARCHAR, max_length=128)
    schema.add_field(field_name="chunk_index", datatype=DataType.INT64)
    schema.add_field(field_name="original_name", datatype=DataType.VARCHAR, max_length=512)
    schema.add_field(field_name="text", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dimension)
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="vector",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": settings.MILVUS_HNSW_M, "efConstruction": settings.MILVUS_HNSW_EF_CONSTRUCTION},
    )
    client.create_collection(collection_name=name, schema=schema, index_params=index_params)
    client.load_collection(collection_name=name)
    return name


def _milvus_embed(texts: list[str], metadatas: list[dict[str, Any]]) -> None:
    embeddings = get_embeddings().embed_documents(texts)
    if not embeddings:
        return
    client = _milvus_client()
    collection = _milvus_collection(client, len(embeddings[0]))
    if metadatas and metadatas[0].get("document_id"):
        document_id = str(metadatas[0]["document_id"]).replace('\\', '\\\\').replace('"', '\\"')
        client.delete(collection_name=collection, filter=f'document_id == "{document_id}"')
    rows = []
    for text, metadata, vector in zip(texts, metadatas, embeddings):
        rows.append({
            "document_id": str(metadata.get("document_id", "")),
            "chunk_index": int(metadata.get("chunk_index", 0)),
            "original_name": str(metadata.get("original_name", ""))[:512],
            "text": text[:65535],
            "vector": vector,
        })
    client.insert(collection_name=collection, data=rows)


def _milvus_retrieve(question: str, document_ids: list[str] | None, candidate_k: int) -> list[LCDocument]:
    client = _milvus_client()
    collection = settings.MILVUS_COLLECTION
    if not client.has_collection(collection_name=collection):
        return []
    client.load_collection(collection_name=collection)
    expr = None
    if document_ids:
        safe_ids = [str(x).replace('\\', '\\\\').replace('"', '\\"') for x in document_ids]
        expr = "document_id in [" + ",".join(f'"{x}"' for x in safe_ids) + "]"
    result = client.search(
        collection_name=collection,
        data=[get_embeddings().embed_query(question)],
        anns_field="vector",
        search_params={"metric_type": "COSINE", "params": {"ef": max(settings.MILVUS_HNSW_EF, candidate_k)}},
        limit=candidate_k,
        filter=expr,
        output_fields=["text", "document_id", "chunk_index", "original_name"],
    )
    docs = []
    for hit in (result[0] if result else []):
        entity = hit.get("entity", {})
        docs.append(LCDocument(
            page_content=entity.get("text", ""),
            metadata={k: entity.get(k) for k in ("document_id", "chunk_index", "original_name")},
        ))
    return docs


def load_vectorstore() -> FAISS | None:
    store_dir = _vectorstore_dir()
    index_path = store_dir / "index.faiss"
    if not index_path.exists():
        return None
    return FAISS.load_local(str(store_dir), get_embeddings(), allow_dangerous_deserialization=True)


def _embed_faiss(texts: list[str], metadatas: list[dict[str, Any]]) -> None:
    vs = load_vectorstore()
    if vs is None:
        vs = FAISS.from_texts(texts=texts, embedding=get_embeddings(), metadatas=metadatas)
    else:
        vs.add_texts(texts=texts, metadatas=metadatas)
    store_dir = _vectorstore_dir()
    store_dir.mkdir(parents=True, exist_ok=True)
    vs.save_local(str(store_dir))


_ROLE_MODEL_ATTR = {
    "router": "OLLAMA_ROUTER_MODEL",
    "retriever": "OLLAMA_RETRIEVER_MODEL",
    "reviewer": "OLLAMA_REVIEWER_MODEL",
    "answer": "OLLAMA_ANSWER_MODEL",
}


def get_llm(role: str = "answer", temperature: float = 0.0) -> Ollama:
    """按角色返回对应的 Ollama LLM。

    role:
      - router    → Qwen 8B  （意图识别、检索规划）
      - retriever → Qwen 8B  （实体抽取、关键词扩展）
      - reviewer  → DeepSeek （证据校验、风险审查）
      - answer    → DeepSeek （最终答案生成）
    未配置时回退到 OLLAMA_MODEL。
    """
    attr = _ROLE_MODEL_ATTR.get(role, "OLLAMA_MODEL")
    model = getattr(settings, attr, None) or settings.OLLAMA_MODEL
    return Ollama(base_url=settings.OLLAMA_BASE_URL, model=model, temperature=temperature)


def list_ollama_models() -> list[str]:
    resp = requests.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=10)
    resp.raise_for_status()
    data = resp.json() or {}
    models = data.get("models") or []
    names = []
    for m in models:
        name = m.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def embed_texts(texts: list[str], metadatas: list[dict[str, Any]], document_id: str | None = None) -> None:
    t = task_create(task_type="embed", document_id=document_id or "")
    try:
        if not texts:
            task_info(t, message="embedded=0")
            task_succeed(t)
            return

        if settings.VECTOR_BACKEND == "milvus":
            try:
                _milvus_embed(texts, metadatas)
            except Exception:
                if not settings.MILVUS_FALLBACK_TO_FAISS:
                    raise
                _embed_faiss(texts, metadatas)
        else:
            _embed_faiss(texts, metadatas)
        task_info(t, message=f"embedded={len(texts)}")
        task_succeed(t)
    except Exception as e:
        task_fail(t, error=str(e))
        raise


@dataclass(frozen=True)
class AskResult:
    answer: str
    contexts: list[dict[str, Any]]
    graph: dict[str, Any]
    trace: dict[str, Any] | None = None


def _candidate_count(top_k: int) -> int:
    """为 Cross-Encoder 保留足够候选，避免只对初始 Top K 重排。"""
    multiplier = max(1, int(getattr(settings, "RERANKER_CANDIDATE_MULTIPLIER", 5)))
    configured = max(1, int(getattr(settings, "RERANKER_CANDIDATE_K", 20)))
    return max(top_k, min(max(top_k * multiplier, configured), 100))


def get_reranker() -> Any | None:
    """延迟加载 Cross-Encoder，并缓存失败状态以防每个请求重复下载模型。"""
    global _reranker_cache, _reranker_initialized
    if not getattr(settings, "RERANKER_ENABLED", True):
        return None
    if _reranker_initialized:
        return _reranker_cache

    with _reranker_lock:
        if _reranker_initialized:
            return _reranker_cache
        try:
            from sentence_transformers import CrossEncoder

            _reranker_cache = CrossEncoder(
                settings.RERANKER_MODEL_NAME,
                max_length=int(getattr(settings, "RERANKER_MAX_LENGTH", 512)),
            )
            logger.info("reranker_loaded model=%s", settings.RERANKER_MODEL_NAME)
        except Exception:
            # 重排序是增强层；模型仓库不可达时，保留向量召回结果保证核心问答可用。
            logger.exception("reranker_unavailable model=%s", settings.RERANKER_MODEL_NAME)
            _reranker_cache = None
        finally:
            _reranker_initialized = True
    return _reranker_cache


def rerank_documents(question: str, candidates: list[LCDocument], top_k: int) -> list[LCDocument]:
    """使用 query-document Cross-Encoder 分数重排候选，并把评分写入证据元数据。"""
    import time

    if len(candidates) <= 1:
        return candidates[:top_k]
    reranker = get_reranker()
    if reranker is None:
        RERANK_REQUESTS_TOTAL.labels(outcome="skipped").inc()
        return candidates[:top_k]
    started_at = time.perf_counter()
    RERANK_CANDIDATES.observe(len(candidates))
    try:
        # Cross-Encoder 同时编码问题与全文，比 embedding 相似度更适合判断细粒度相关性。
        pairs = [(question, document.page_content[:8_000]) for document in candidates]
        scores = reranker.predict(
            pairs,
            batch_size=max(1, int(getattr(settings, "RERANKER_BATCH_SIZE", 8))),
            show_progress_bar=False,
        )
        if len(scores) != len(candidates):
            raise ValueError("reranker score count does not match candidates")
        ranked = sorted(enumerate(zip(candidates, scores)), key=lambda item: float(item[1][1]), reverse=True)
        result: list[LCDocument] = []
        for rerank_rank, (candidate_rank, (document, score)) in enumerate(ranked[:top_k], start=1):
            metadata = dict(document.metadata)
            metadata.update({
                "retrieval_rank": candidate_rank + 1,
                "rerank_rank": rerank_rank,
                "rerank_score": round(float(score), 5),
            })
            result.append(LCDocument(page_content=document.page_content, metadata=metadata))
        RERANK_REQUESTS_TOTAL.labels(outcome="success").inc()
        RERANK_DURATION_SECONDS.labels(outcome="success").observe(time.perf_counter() - started_at)
        return result
    except Exception:
        logger.exception("reranking_failed candidates=%d", len(candidates))
        RERANK_REQUESTS_TOTAL.labels(outcome="failed").inc()
        RERANK_DURATION_SECONDS.labels(outcome="failed").observe(time.perf_counter() - started_at)
        return candidates[:top_k]


def retrieve_chunks(question: str, document_ids: list[str] | None, top_k: int) -> list[LCDocument]:
    """先用 Milvus/FAISS 召回候选，再由 Cross-Encoder 进行精排。"""
    candidate_k = _candidate_count(top_k)
    if settings.VECTOR_BACKEND == "milvus":
        try:
            candidates = _milvus_retrieve(question, document_ids, candidate_k)
            return rerank_documents(question, candidates, top_k)
        except Exception:
            if not settings.MILVUS_FALLBACK_TO_FAISS:
                raise
    vs = load_vectorstore()
    if vs is None:
        return []
    candidates = vs.similarity_search(query=question, k=candidate_k)
    if document_ids:
        wanted = set(document_ids)
        candidates = [d for d in candidates if str(d.metadata.get("document_id", "")) in wanted]
    return rerank_documents(question, candidates, top_k)


def format_contexts(docs: list[LCDocument]) -> list[dict[str, Any]]:
    return [
        {"rank": i + 1, "text": d.page_content, "metadata": d.metadata}
        for i, d in enumerate(docs)
    ]


def ask_question(
    question: str,
    document_ids: list[str] | None,
    top_k: int,
    graph: dict[str, Any] | None = None,
    retrieval_options: dict[str, bool] | None = None,
    memory_context: str = "",
    progress_callback: Callable[[str, str], None] | None = None,
    token_callback: Callable[[str], None] | None = None,
) -> AskResult:
    """问答入口。启用 MAS 时走多智能体编排，否则走单步 GraphRAG。"""
    if getattr(settings, "MAS_ENABLED", False):
        from .agents import run_mas_pipeline
        return run_mas_pipeline(
            question=question,
            document_ids=document_ids,
            top_k=top_k,
            graph=graph,
            retrieval_options=retrieval_options,
            memory_context=memory_context,
            progress_callback=progress_callback,
            token_callback=token_callback,
        )
    return _legacy_ask_question(question=question, document_ids=document_ids, top_k=top_k, graph=graph)


def _legacy_ask_question(question: str, document_ids: list[str] | None, top_k: int, graph: dict[str, Any] | None = None) -> AskResult:
    t = task_create(task_type="qa")
    try:
        docs = retrieve_chunks(question=question, document_ids=document_ids, top_k=top_k)

        context_text = "\n\n".join([f"[{i+1}] {d.page_content}" for i, d in enumerate(docs)])
        g = graph or {}
        g_keywords = g.get("keywords") or []
        g_nodes = g.get("nodes") or []
        g_edges = g.get("edges") or []
        g_text_parts = []
        if g_keywords:
            g_text_parts.append("关键词：" + "、".join([str(x) for x in g_keywords]))
        if g_nodes:
            g_text_parts.append("相关实体：" + "、".join([str(n.get("label") or n.get("id")) for n in g_nodes[:16]]))
        if g_edges:
            g_text_parts.append("关系（部分）：")
            for e in g_edges[:16]:
                g_text_parts.append(f"- {e.get('source')} -[{e.get('type')}({e.get('weight', 1)})]-> {e.get('target')}")
        graph_text = "\n".join(g_text_parts).strip()
        prompt = (
            "你是公共卫生领域的知识助手。你会同时收到两类材料：\n"
            "A) 向量检索命中的证据片段（文本证据）\n"
            "B) Neo4j 知识图谱检索得到的实体与关系（结构化线索）\n\n"
            "请完成：\n"
            "1) 先给出结论（要点列表）。\n"
            "2) 给出证据引用：引用文本证据用[1][2]编号；引用图谱线索用(G)标记。\n"
            "3) 若材料不足，明确说明缺口，并给出建议补充信息。\n"
            "4) 输出结构必须为：\n"
            "【结论】\n"
            "【依据-文本证据】\n"
            "【依据-图谱线索】\n"
            "【不确定点与建议】\n\n"
            f"文本证据：\n{context_text}\n\n"
            f"图谱线索：\n{graph_text}\n\n"
            f"用户问题：{question}\n\n"
            "回答："
        )
        llm = get_llm()
        try:
            answer = llm.invoke(prompt)
        except OllamaEndpointNotFoundError as e:
            available = []
            try:
                available = list_ollama_models()
            except Exception:
                available = []
            msg = f"Ollama 模型未找到：{settings.OLLAMA_MODEL}"
            if available:
                msg += f"；可用模型：{', '.join(available[:12])}"
            raise RuntimeError(msg) from e

        contexts = []
        for i, d in enumerate(docs):
            contexts.append(
                {
                    "rank": i + 1,
                    "text": d.page_content,
                    "metadata": d.metadata,
                }
            )
        task_succeed(t)
        return AskResult(answer=str(answer), contexts=contexts, graph=g)
    except Exception as e:
        task_fail(t, error=str(e))
        raise
