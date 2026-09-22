from __future__ import annotations

import uuid

from django.db import models


class Conversation(models.Model):
    """一个前端会话对应一条压缩摘要，避免把完整历史反复塞进模型上下文。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memory_scope_id = models.UUIDField(db_index=True)
    rolling_summary = models.TextField(blank=True, default="")
    compressed_until = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ConversationMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "用户"
        ASSISTANT = "assistant", "助手"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sequence = models.PositiveIntegerField()
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [models.UniqueConstraint(fields=["conversation", "sequence"], name="unique_conversation_message_sequence")]


class LongTermMemory(models.Model):
    """跨会话持久化的研究主题与已确认结论，按 memory_scope_id 隔离。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    memory_scope_id = models.UUIDField(db_index=True)
    source_conversation = models.ForeignKey(Conversation, null=True, blank=True, on_delete=models.SET_NULL, related_name="long_term_memories")
    content = models.TextField()
    keywords = models.CharField(max_length=1000, blank=True, default="")
    importance = models.PositiveSmallIntegerField(default=1)
    last_recalled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-importance", "-updated_at"]