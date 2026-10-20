"""Strict joint-output parsing with reply-preserving avatar fallback."""

import json
from dataclasses import dataclass
from typing import NoReturn

from pydantic import ValidationError

from app.schemas.avatar import AvatarControl
from app.schemas.teaching import TeachingTurn

MAX_TEACHING_OUTPUT_CHARS = 65_536


class TeachingOutputError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Invalid teaching output ({reason})")


@dataclass(frozen=True)
class ParsedTeachingTurn:
    turn: TeachingTurn
    fallback_reason: str | None = None

    def presentation(self) -> dict[str, object]:
        return {
            "schema_version": self.turn.schema_version,
            "avatar": self.turn.avatar.model_dump(mode="json"),
            "fallback_reason": self.fallback_reason,
        }


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("Nonstandard JSON constant")


class TeachingTurnParser:
    def parse(self, text: str) -> ParsedTeachingTurn:
        if len(text) > MAX_TEACHING_OUTPUT_CHARS:
            raise TeachingOutputError("output_too_large")
        try:
            payload = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        except (ValueError, RecursionError):
            raise TeachingOutputError("invalid_json") from None
        if not isinstance(payload, dict):
            raise TeachingOutputError("invalid_turn")
        if type(payload.get("schema_version", 1)) is not int:
            raise TeachingOutputError("invalid_turn")
        # 先验证回复、版本及顶层字段，不能用表情回退掩盖坏回复或额外指令。
        try:
            turn = TeachingTurn.model_validate({key: value for key, value in payload.items() if key != "avatar"})
            _ = turn.reply.encode("utf-8")
        except (ValidationError, UnicodeError):
            raise TeachingOutputError("invalid_turn") from None
        try:
            avatar = AvatarControl.model_validate(payload.get("avatar", {}))
        except ValidationError:
            return ParsedTeachingTurn(turn, "invalid_avatar")
        return ParsedTeachingTurn(turn.model_copy(update={"avatar": avatar}))
