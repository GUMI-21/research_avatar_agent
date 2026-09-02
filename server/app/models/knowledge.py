"""Client-scoped knowledge sources and imported Markdown documents."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import new_id, utc_now

# 知识库目录索引
class KnowledgeSourceRecord(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('obsidian', 'markdown')",
            name="ck_knowledge_sources_type",
        ),
        CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'ready', 'failed')",
            name="ck_knowledge_sources_sync_status",
        ),
        UniqueConstraint(
            "client_id",
            "name",
            name="uq_knowledge_sources_client_name",
        ),
        Index("ix_knowledge_sources_client_created", "client_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    name: Mapped[str] = mapped_column(String(120))  # 前端展示名称
    source_type: Mapped[str] = mapped_column(
        String(16), default="obsidian", server_default="obsidian"
    )  # 解析策略
    root_path: Mapped[str] = mapped_column(String(2048))  # 本机知识库绝对路径
    sync_status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending"
    )  # 最近一次同步状态
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)  # 最近成功同步时间
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class KnowledgeDocumentRecord(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "relative_path",
            name="uq_knowledge_documents_source_path",
        ),
        Index(
            "ix_knowledge_documents_client_source_path",
            "client_id",
            "source_id",
            "relative_path",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE")
    )  # 所属 Vault 或 Markdown 目录
    relative_path: Mapped[str] = mapped_column(String(1024))  # 面向 Vault 的相对路径
    title: Mapped[str] = mapped_column(String(240))  # 标题或文件名回退值
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256 增量同步依据
    frontmatter: Mapped[dict[str, object]] = mapped_column(
        JSON, default=dict
    )  # YAML 元数据
    source_modified_at: Mapped[datetime] = mapped_column()  # 文件系统修改时间
    indexed_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # 最近写入检索索引的时间
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class KnowledgeChunkRecord(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunks_document_index",
        ),
        Index(
            "ix_knowledge_chunks_client_source_document",
            "client_id",
            "source_id",
            "document_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE")
    )  # 所属知识库
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE")
    )  # 所属 Markdown 文档
    chunk_index: Mapped[int] = mapped_column(Integer)  # 文档内稳定顺序
    heading_path: Mapped[list[str]] = mapped_column(JSON, default=list)  # 标题层级
    content: Mapped[str] = mapped_column(Text)  # 检索与上下文使用的原文片段
    start_line: Mapped[int] = mapped_column(Integer)  # 原文件起始行，包含首行
    end_line: Mapped[int] = mapped_column(Integer)  # 原文件结束行，包含末行
    content_hash: Mapped[str] = mapped_column(String(64))  # 分块变化检测依据
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
