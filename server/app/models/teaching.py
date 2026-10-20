"""One durable teaching configuration per conversation, separate from chat history."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.agent import utc_now


class TeachingSessionRecord(Base):
    __tablename__ = "teaching_session_states"
    __table_args__ = (
        Index("ix_teaching_sessions_client", "client_id"),
        CheckConstraint("completed_turns >= 0", name="ck_teaching_turns_nonnegative"),
        CheckConstraint("state_version >= 1", name="ck_teaching_version_positive"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )  # 一个对话最多一份教学配置，不复制 Message
    client_id: Mapped[str] = mapped_column(String(64))  # 数据隔离作用域
    course_id: Mapped[str] = mapped_column(String(64))  # CourseCatalog 中的课程 ID
    lesson_id: Mapped[str] = mapped_column(String(64))  # 课程声明的课节 ID
    course_version: Mapped[str] = mapped_column(String(64))  # 绑定时脚本原始字节的 SHA256
    completed_turns: Mapped[int] = mapped_column(default=0, server_default="0")  # 已提交教学轮数，不代表掌握程度
    state_version: Mapped[int] = mapped_column(default=1, server_default="1")  # 预留乐观并发版本，后续更新时递增
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)
