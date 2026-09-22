"""会话记忆：短期窗口压缩为滚动摘要，长期记忆按浏览器记忆范围隔离存储。"""
from __future__ import annotations

import re
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import Conversation, ConversationMessage, LongTermMemory


_TERM_PATTERN = re.compile(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z0-9][a-zA-Z0-9_-]{1,32}")


def _terms(text: str, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for term in _TERM_PATTERN.findall((text or "").lower()):
        candidates = [term]
        # 连续中文没有天然分词边界；补充 2~4 字滑动词片段，
        # 使“医疗器械注册”可以命中已存储的“医疗器械”“注册”记忆。
        if re.fullmatch(r"[\u4e00-\u9fff]+", term):
            candidates.extend(
                term[start:start + width]
                for width in (2, 3, 4)
                for start in range(max(0, len(term) - width + 1))
            )
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
            if len(result) >= limit:
                return result
    return result


def _conversation(memory_scope_id, conversation_id) -> Conversation:
    conversation, _ = Conversation.objects.get_or_create(
        id=conversation_id,
        defaults={"memory_scope_id": memory_scope_id},
    )
    if conversation.memory_scope_id != memory_scope_id:
        raise ValueError("conversation_id 不属于当前记忆范围")
    return conversation


def _summarize_messages(existing_summary: str, messages: list[ConversationMessage]) -> str:
    """压缩旧消息；模型不可用时仍生成确定性摘要，确保上下文窗口可控。"""
    transcript = "\n".join(f"{message.role}: {message.content[:600]}" for message in messages)
    prompt = (
        "将以下医疗知识问答历史压缩为不超过 800 字的工作摘要。保留已确认主题、约束、未解决问题和重要风险提示。"
        "不要加入新事实，不要写推理过程。\n\n"
        f"已有摘要：{existing_summary[:800] or '(无)'}\n\n待压缩历史：\n{transcript[:6000]}"
    )
    try:
        from .services import get_llm

        summary = str(get_llm(role="reviewer", temperature=0.0).invoke(prompt) or "").strip()
        if summary and not summary.startswith("__LLM_ERROR__"):
            return summary[: int(getattr(settings, "MEMORY_SUMMARY_MAX_CHARS", 1_200))]
    except Exception:
        pass
    # 离线保底：保留角色与开头信息，防止压缩失败导致会话失忆。
    fallback = "；".join(f"{message.role}: {message.content[:180]}" for message in messages)
    return f"{existing_summary[:500]}；{fallback}".strip("；")[: int(getattr(settings, "MEMORY_SUMMARY_MAX_CHARS", 1_200))]


def _compact_short_term_memory(conversation: Conversation) -> None:
    short_term_limit = max(2, int(getattr(settings, "MEMORY_SHORT_TERM_MESSAGE_LIMIT", 8)))
    messages = list(conversation.messages.filter(sequence__gt=conversation.compressed_until))
    if len(messages) <= short_term_limit:
        return

    # 始终保留最近消息原文；其余内容写入 rolling_summary，模拟 Claude Code 的压缩上下文策略。
    to_compress = messages[:-short_term_limit]
    summary = _summarize_messages(conversation.rolling_summary, to_compress)
    conversation.rolling_summary = summary
    conversation.compressed_until = to_compress[-1].sequence
    conversation.save(update_fields=["rolling_summary", "compressed_until", "updated_at"])


def _recall_long_term_memory(memory_scope_id, question: str) -> list[LongTermMemory]:
    terms = _terms(question)
    memories = list(LongTermMemory.objects.filter(memory_scope_id=memory_scope_id)[:100])
    if not terms:
        return memories[: int(getattr(settings, "MEMORY_LONG_TERM_TOP_K", 3))]

    scored = []
    for memory in memories:
        haystack = f"{memory.keywords} {memory.content}".lower()
        overlap = sum(term in haystack for term in terms)
        if overlap:
            scored.append((overlap * 10 + memory.importance, memory))
    recalled = [memory for _, memory in sorted(scored, key=lambda item: item[0], reverse=True)]
    result = recalled[: int(getattr(settings, "MEMORY_LONG_TERM_TOP_K", 3))]
    if result:
        LongTermMemory.objects.filter(id__in=[memory.id for memory in result]).update(last_recalled_at=timezone.now())
    return result


def prepare_memory_context(memory_scope_id, conversation_id, question: str, enabled: bool = True) -> tuple[Conversation | None, str]:
    """生成给 Agent 的上下文：滚动摘要 + 最近窗口 + 与当前问题相关的长期记忆。"""
    if not enabled or not getattr(settings, "MEMORY_ENABLED", True):
        return None, "(会话记忆未启用)"
    conversation = _conversation(memory_scope_id, conversation_id)
    _compact_short_term_memory(conversation)
    recent = list(conversation.messages.filter(sequence__gt=conversation.compressed_until))
    long_term = _recall_long_term_memory(memory_scope_id, question)
    recent_text = "\n".join(f"- {message.role}: {message.content[:500]}" for message in recent)
    long_term_text = "\n".join(f"- {memory.content[:500]}" for memory in long_term)
    context = (
        f"滚动摘要：{conversation.rolling_summary or '(无)'}\n"
        f"近期对话：\n{recent_text or '(无)'}\n"
        f"相关长期记忆：\n{long_term_text or '(无)'}"
    )
    return conversation, context[: int(getattr(settings, "MEMORY_CONTEXT_MAX_CHARS", 3_000))]


def remember_turn(conversation: Conversation | None, question: str, answer: str, enabled: bool = True) -> None:
    """持久化本轮问答，并生成供后续召回的长期记忆记录。"""
    if conversation is None or not enabled or not getattr(settings, "MEMORY_ENABLED", True):
        return
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
        next_sequence = (conversation.messages.aggregate(maximum=Max("sequence"))["maximum"] or 0) + 1
        ConversationMessage.objects.bulk_create([
            ConversationMessage(conversation=conversation, sequence=next_sequence, role=ConversationMessage.Role.USER, content=question[:2_000]),
            ConversationMessage(conversation=conversation, sequence=next_sequence + 1, role=ConversationMessage.Role.ASSISTANT, content=answer[:8_000]),
        ])
        # 只保存可复用的问答摘要，避免长期库无限复制完整回答。
        memory_text = f"研究主题：{question[:400]}\n已答复摘要：{answer[:900]}"
        LongTermMemory.objects.create(
            memory_scope_id=conversation.memory_scope_id,
            source_conversation=conversation,
            content=memory_text,
            keywords=" ".join(_terms(question + " " + answer, limit=30)),
            importance=2 if any(keyword in question for keyword in ("风险", "禁忌", "法规", "注册")) else 1,
        )
    _compact_short_term_memory(conversation)


def memory_overview(memory_scope_id: Any) -> dict[str, Any]:
    return {
        "conversations": Conversation.objects.filter(memory_scope_id=memory_scope_id).count(),
        "long_term_memories": LongTermMemory.objects.filter(memory_scope_id=memory_scope_id).count(),
    }


def clear_memory(memory_scope_id: Any) -> None:
    Conversation.objects.filter(memory_scope_id=memory_scope_id).delete()
    LongTermMemory.objects.filter(memory_scope_id=memory_scope_id).delete()