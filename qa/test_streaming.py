import uuid

from django.test import Client
from django.test import override_settings

from qa.services import AskResult


@override_settings(ALLOWED_HOSTS=["testserver"])
def test_sse_endpoint_emits_auditable_progress_tokens_and_completion(monkeypatch):
    def fake_ask_question(*_args, progress_callback=None, token_callback=None, **_kwargs):
        progress_callback("router", "正在识别问题意图与风险等级")
        token_callback("这是")
        token_callback("流式回答")
        return AskResult(answer="这是流式回答", contexts=[], graph={}, trace={"pipeline": "mas"})

    monkeypatch.setattr("qa.views.ask_question", fake_ask_question)
    response = Client().post(
        "/api/qa/ask/stream/",
        data={
            "question": "测试流式接口",
            "conversation_id": str(uuid.uuid4()),
            "memory_scope_id": str(uuid.uuid4()),
            "memory_enabled": False,
            "use_graph": False,
        },
        content_type="application/json",
    )

    payload = b"".join(response.streaming_content).decode("utf-8")

    assert response.status_code == 200
    assert "event: progress" in payload
    assert "event: token" in payload
    assert "这是流式回答" in payload
    assert "event: complete" in payload