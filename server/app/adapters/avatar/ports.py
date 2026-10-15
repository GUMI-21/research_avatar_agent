"""Optional speech and independent affect ports; no providers are enabled here."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.chat import EmotionState


@dataclass(frozen=True)
class SynthesizedSpeech:
    content: bytes
    media_type: str


class SpeechRecognizer(Protocol):
    async def transcribe(
        self, audio: bytes, *, media_type: str, language: str,
    ) -> str: ...


class SpeechSynthesizer(Protocol):
    async def synthesize(
        self, text: str, *, language: str,
    ) -> SynthesizedSpeech: ...


class EmotionAnalyzer(Protocol):
    async def analyze(self, text: str, *, language: str) -> EmotionState: ...
