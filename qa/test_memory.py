import uuid

import pytest
from django.conf import settings

from qa.memory import clear_memory, prepare_memory_context, remember_turn
from qa.models import Conversation, LongTermMemory


@pytest.fixture
def memory_scope_factory():
    """只清理本测试创建的 UUID 范围，绝不删除开发者已有的会话记忆。"""
    scope_ids = []

    def create_scope_id():
        scope_id = uuid.uuid4()
        scope_ids.append(scope_id)
        return scope_id

    yield create_scope_id
    Conversation.objects.filter(memory_scope_id__in=scope_ids).delete()
    LongTermMemory.objects.filter(memory_scope_id__in=scope_ids).delete()


def test_short_term_history_is_compacted_and_recent_window_is_retained(monkeypatch, memory_scope_factory):
    monkeypatch.setattr(settings, "MEMORY_SHORT_TERM_MESSAGE_LIMIT", 2)
    monkeypatch.setattr(settings, "MEMORY_LONG_TERM_TOP_K", 0)
    monkeypatch.setattr("qa.memory._summarize_messages", lambda _summary, _messages: "压缩后的工作摘要")
    scope_id = memory_scope_factory()
    conversation_id = uuid.uuid4()

    conversation, _ = prepare_memory_context(scope_id, conversation_id, "第一个问题")
    remember_turn(conversation, "第一个问题", "第一个回答")
    conversation, _ = prepare_memory_context(scope_id, conversation_id, "第二个问题")
    remember_turn(conversation, "第二个问题", "第二个回答")

    conversation, context = prepare_memory_context(scope_id, conversation_id, "第三个问题")

    conversation.refresh_from_db()
    assert conversation.rolling_summary == "压缩后的工作摘要"
    assert conversation.compressed_until == 2
    assert "第一个问题" not in context
    assert "第二个问题" in context


def test_relevant_long_term_memory_is_recalled(memory_scope_factory):
    scope_id = memory_scope_factory()
    conversation_id = uuid.uuid4()
    LongTermMemory.objects.create(
        memory_scope_id=scope_id,
        content="研究主题：医疗器械注册\n已答复摘要：需关注备案与临床评价。",
        keywords="医疗器械 注册 备案 临床评价",
        importance=2,
    )

    _conversation, context = prepare_memory_context(scope_id, conversation_id, "医疗器械注册需要什么材料？")

    assert "需关注备案与临床评价" in context


def test_conversation_cannot_be_reused_by_another_memory_scope(memory_scope_factory):
    conversation_id = uuid.uuid4()
    prepare_memory_context(memory_scope_factory(), conversation_id, "首次问题")

    with pytest.raises(ValueError, match="不属于当前记忆范围"):
        prepare_memory_context(memory_scope_factory(), conversation_id, "越权问题")


def test_clear_memory_only_removes_the_requested_scope(memory_scope_factory):
    first_scope_id = memory_scope_factory()
    second_scope_id = memory_scope_factory()
    first_conversation, _ = prepare_memory_context(first_scope_id, uuid.uuid4(), "问题一")
    second_conversation, _ = prepare_memory_context(second_scope_id, uuid.uuid4(), "问题二")
    remember_turn(first_conversation, "问题一", "回答一")
    remember_turn(second_conversation, "问题二", "回答二")

    clear_memory(first_scope_id)

    assert Conversation.objects.filter(memory_scope_id=first_scope_id).count() == 0
    assert LongTermMemory.objects.filter(memory_scope_id=first_scope_id).count() == 0
    assert Conversation.objects.filter(memory_scope_id=second_scope_id).count() == 1
    assert LongTermMemory.objects.filter(memory_scope_id=second_scope_id).count() == 1