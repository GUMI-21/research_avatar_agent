"""Bounded model-suggested controls, independent of Unity or emotion providers."""

from pydantic import ConfigDict, Field

from app.schemas.chat import AvatarAction, AvatarCommand, EmotionLabel


class AvatarControl(AvatarCommand):
    # 防止大模型传入额外的字段和NAN
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    expression: EmotionLabel = EmotionLabel.NEUTRAL
    action: AvatarAction = AvatarAction.IDLE
    intensity: float = Field(default=0.0, ge=0.0, le=1.0, strict=True)
    duration_ms: int = Field(default=0, ge=0, le=60_000, strict=True)
