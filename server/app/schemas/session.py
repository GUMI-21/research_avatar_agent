"""Public request and response contracts for conversation Sessions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 创建对话框参数
class SessionCreate(BaseModel):
    agent_id: str = Field(min_length=1, max_length=36)
    title: str = Field(default="New conversation", min_length=1, max_length=160)

    # 校验参数
    @field_validator("agent_id", "title")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

# 会话属性
class SessionRead(BaseModel):
    # pydantic 类的内部配置，从数据库对象中按字段名提取数据，同时校验类型，生成 API 使用的结构化对象。
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    agent_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionRead]
