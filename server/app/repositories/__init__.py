"""Persistence boundaries for workspace resources and run history. 数据库访问封装层"""

from app.repositories.agent import AgentRepository
from app.repositories.knowledge import (
    KnowledgeChunkHit,
    KnowledgeChunkRepository,
    KnowledgeDocumentRepository,
    KnowledgeEmbeddingRepository,
    KnowledgeSourceRepository,
)
from app.repositories.memory import MemoryParentNotFoundError, MemoryRepository
from app.repositories.message import MessageParentNotFoundError, MessageRepository
from app.repositories.run import RunParentNotFoundError, RunRepository, RunUsageTotals
from app.repositories.run_event import RunEventRepository, RunEventRunNotFoundError
from app.repositories.session import (
    SessionAgentNotFoundError,
    SessionRepository,
)

# 引用*时，对外暴露类
__all__ = [
    "AgentRepository",
    "KnowledgeChunkRepository",
    "KnowledgeDocumentRepository",
    "KnowledgeEmbeddingRepository",
    "KnowledgeSourceRepository",
    "KnowledgeChunkHit",
    "MemoryParentNotFoundError",
    "MemoryRepository",
    "MessageParentNotFoundError",
    "MessageRepository",
    "RunParentNotFoundError",
    "RunRepository",
    "RunUsageTotals",
    "RunEventRepository",
    "RunEventRunNotFoundError",
    "SessionAgentNotFoundError",
    "SessionRepository",
]
