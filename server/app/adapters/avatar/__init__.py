"""Optional presentation-module boundaries, without concrete providers."""

from app.adapters.avatar.ports import (
    EmotionAnalyzer,
    SpeechRecognizer,
    SpeechSynthesizer,
    SynthesizedSpeech,
)

__all__ = [
    "EmotionAnalyzer", "SpeechRecognizer", "SpeechSynthesizer", "SynthesizedSpeech",
]
