"""Persistent configuration for one Personal Agent instance."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentKnowledgeSourceRecord(Base):
    __tablename__ = "agent_knowledge_sources"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)  # 数据隔离作用域
    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )  # 被配置的 Agent
    source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), primary_key=True
    )  # Agent 可以检索的知识库


class AgentRecord(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("client_id", "name", name="uq_agents_client_name"),
    )
    # Mapped[str] 映射为字符串
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_id: Mapped[str] = mapped_column(String(64), index=True)  # 数据隔离作用域
    name: Mapped[str] = mapped_column(String(80))  # 同一客户端内唯一的展示名称
    system_prompt: Mapped[str] = mapped_column(Text)  # Agent 的身份和行为指令
    runtime: Mapped[str] = mapped_column(
        String(32), default="native", server_default="native"
    )  # Runtime Adapter 注册名
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 可选模型覆盖
    knowledge_links: Mapped[list[AgentKnowledgeSourceRecord]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    @property
    def knowledge_source_ids(self) -> list[str]:
        links = self.__dict__.get("knowledge_links", ())
        return [link.source_id for link in links]
