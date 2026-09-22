from langchain_core.documents import Document as LCDocument

from qa import services


class _FakeReranker:
    def predict(self, pairs, **_kwargs):
        assert pairs[0][0] == "医疗器械注册要求"
        return [0.1, 0.9, 0.5]


def test_reranker_promotes_best_cross_encoder_match(monkeypatch):
    candidates = [
        LCDocument(page_content="候选 A", metadata={"document_id": "a"}),
        LCDocument(page_content="候选 B", metadata={"document_id": "b"}),
        LCDocument(page_content="候选 C", metadata={"document_id": "c"}),
    ]
    monkeypatch.setattr(services, "get_reranker", lambda: _FakeReranker())

    ranked = services.rerank_documents("医疗器械注册要求", candidates, top_k=2)

    assert [document.metadata["document_id"] for document in ranked] == ["b", "c"]
    assert ranked[0].metadata["retrieval_rank"] == 2
    assert ranked[0].metadata["rerank_rank"] == 1
    assert ranked[0].metadata["rerank_score"] == 0.9


def test_reranker_failure_preserves_vector_retrieval_order(monkeypatch):
    class BrokenReranker:
        def predict(self, *_args, **_kwargs):
            raise RuntimeError("model unavailable")

    candidates = [LCDocument(page_content="候选 A"), LCDocument(page_content="候选 B")]
    monkeypatch.setattr(services, "get_reranker", lambda: BrokenReranker())

    ranked = services.rerank_documents("测试", candidates, top_k=1)

    assert [document.page_content for document in ranked] == ["候选 A"]