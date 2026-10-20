"""Strict JSON/reply validation, safe fallback and buffered teaching output."""

import asyncio
import json
import re
import traceback
import unittest
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from app.adapters.agent import NativeAgentRuntime, RuntimeEventType, RuntimeRequest
from app.adapters.llm import LLMClient, LLMRequest, LLMResult, LLMStreamChunk, LLMUsage
from app.schemas.avatar import AvatarControl
from app.schemas.llm import LLMProvider
from app.services.teaching_output import (
    MAX_TEACHING_OUTPUT_CHARS, TeachingOutputError, TeachingTurnParser,
)


class TeachingTurnParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = TeachingTurnParser()

    def test_real_course_example_and_presentation_are_valid(self) -> None:
        script = (Path(__file__).resolve().parents[2] / "courses/gojuon-en/SKILL.md").read_text()
        example = re.search(r"```json\n(.*?)\n```", script, re.DOTALL)
        assert example is not None
        parsed = self.parser.parse(example[1])
        self.assertIn("い is i", parsed.turn.reply)
        self.assertEqual(parsed.turn.avatar.expression.value, "happy")
        self.assertEqual(parsed.turn.avatar.action.value, "nod")
        self.assertEqual(parsed.turn.avatar.intensity, 0.35)
        self.assertIsNone(parsed.fallback_reason)
        self.assertEqual(set(parsed.presentation()), {"schema_version", "avatar", "fallback_reason"})
        self.assertNotIn("reply", parsed.presentation())
        self.assertEqual(parsed.presentation()["avatar"], parsed.turn.avatar.model_dump(mode="json"))

    def test_missing_and_partial_avatar_use_contract_defaults(self) -> None:
        for payload in ({"reply": " Let's start. "}, {"reply": "Let's start.", "avatar": {}},
                        {"reply": "Let's start.", "avatar": {"expression": "happy"}}):
            with self.subTest(payload=payload):
                parsed = self.parser.parse(json.dumps(payload))
                self.assertEqual(parsed.turn.reply, "Let's start.")
                self.assertIsNone(parsed.fallback_reason)
                self.assertEqual(parsed.turn.avatar.action.value, "idle")
                self.assertEqual(parsed.turn.avatar.intensity, 0)

    def test_invalid_avatar_preserves_reply_but_replaces_entire_control(self) -> None:
        for avatar in (None, [], "happy", {"expression": "execute_code"}, {"action": "run_script"},
                       {"expression": "happy", "intensity": 1.1}, {"duration_ms": -1},
                       {"duration_ms": True}, {"duration_ms": "800"}, {"intensity": "0.5"},
                       {"expression": "happy", "script": "private-code"}):
            with self.subTest(avatar=avatar):
                parsed = self.parser.parse(json.dumps({"reply": " Try い (i). ", "avatar": avatar}))
                self.assertEqual(parsed.turn.reply, "Try い (i).")
                self.assertEqual(parsed.turn.avatar, AvatarControl())
                self.assertEqual(parsed.fallback_reason, "invalid_avatar")
                self.assertNotIn("private-code", json.dumps(parsed.presentation()))

    def test_invalid_reply_and_top_level_fields_are_not_rescued_by_fallback(self) -> None:
        for payload in ({}, {"reply": " \n "}, {"reply": None}, {"reply": True}, {"reply": 7},
                        {"reply": []}, {"reply": {}}, {"reply": "x" * 10_001},
                        {"reply": "ok", "thoughts": "private"}, {"reply": "ok", "tool": "shell"}):
            with self.subTest(payload_keys=list(payload)):
                with self.assertRaises(TeachingOutputError) as caught:
                    self.parser.parse(json.dumps({**payload, "avatar": {"action": "unsafe"}}))
                self.assertEqual(caught.exception.reason, "invalid_turn")

    def test_version_requires_integer_one(self) -> None:
        for version in (True, False, 1.0, 0, 2, "1", None):
            with self.subTest(version=version), self.assertRaises(TeachingOutputError):
                self.parser.parse(json.dumps({"reply": "Practice.", "schema_version": version}))

    def test_malformed_ambiguous_and_nonstandard_json_is_rejected(self) -> None:
        for text in ("", "hello", '```json\n{"reply":"ok"}\n```', '{"reply":"ok"',
                     '{"reply":"ok"}{"reply":"other"}', '"reply"', "[]", "null", "7",
                     '{"reply":"first","reply":"second"}',
                     '{"reply":"ok","avatar":{"intensity":0.3,"intensity":0.4}}',
                     '{"reply":"ok","avatar":{"intensity":NaN}}',
                     '{"reply":"ok","avatar":{"intensity":Infinity}}'):
            with self.subTest(text=text), self.assertRaises(TeachingOutputError):
                self.parser.parse(text)
        with self.assertRaises(TeachingOutputError):
            self.parser.parse("[" * 1500 + "0" + "]" * 1500)

    def test_numeric_overflow_in_avatar_falls_back_and_invalid_unicode_reply_fails(self) -> None:
        parsed = self.parser.parse('{"reply":"Practice.","avatar":{"intensity":1e999}}')
        self.assertEqual(parsed.fallback_reason, "invalid_avatar")
        with self.assertRaises(TeachingOutputError):
            self.parser.parse('{"reply":"\\ud800"}')

    def test_raw_output_limit_and_reply_unicode_boundaries(self) -> None:
        raw = '{"reply":"ok"}'
        self.assertEqual(self.parser.parse(raw + " " * (MAX_TEACHING_OUTPUT_CHARS - len(raw))).turn.reply, "ok")
        with self.assertRaises(TeachingOutputError) as caught:
            self.parser.parse(raw + " " * (MAX_TEACHING_OUTPUT_CHARS - len(raw) + 1))
        self.assertEqual(caught.exception.reason, "output_too_large")
        reply = "あ" * 10_000
        self.assertEqual(self.parser.parse(json.dumps({"reply": reply})).turn.reply, reply)

    def test_errors_do_not_expose_original_output_or_validation_details(self) -> None:
        private = "sensitive-model-output"
        for raw in (json.dumps({"reply": {private: private}}), '{"reply":"' + private):
            try:
                self.parser.parse(raw)
            except TeachingOutputError as error:
                rendered = "".join(traceback.format_exception(error))
                self.assertNotIn(private, rendered)
                self.assertNotIn(private, str(error))
            else:
                self.fail("Expected sanitized parsing failure")


class JointOutputLLM(LLMClient):
    def __init__(self, fragments: list[str], error: BaseException | None = None) -> None:
        self.fragments = fragments
        self.error = error
        self.calls = 0
        self.consumed = 0

    async def generate(self, request: LLMRequest) -> LLMResult:
        raise AssertionError("Do not make a second model request")

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.calls += 1
        for fragment in self.fragments:
            self.consumed += 1
            yield LLMStreamChunk(fragment, LLMProvider.MOCK, "joint-test")
        yield LLMStreamChunk("", LLMProvider.MOCK, "joint-test", usage=LLMUsage(12, 4))
        if self.error:
            raise self.error


class NativeTeachingOutputTest(unittest.IsolatedAsyncioTestCase):
    def request(self, mode: Literal["workspace", "teaching"] = "teaching") -> RuntimeRequest:
        return RuntimeRequest("run-1", "client-a", "teacher", "session-1", "Teach kana.", mode=mode)

    async def test_split_json_produces_one_plain_reply_and_separate_validated_presentation(self) -> None:
        client = JointOutputLLM(['{"schema_version":1,"reply":"Which ',
                                 'kana is i?","avatar":{"expression":"happy","action":"nod",',
                                 '"intensity":0.35,"duration_ms":800}}'])
        events = [event async for event in NativeAgentRuntime(client).stream(self.request())]
        deltas = [event.payload["text"] for event in events if event.type is RuntimeEventType.ASSISTANT_DELTA]
        self.assertEqual(deltas, ["Which kana is i?"])
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FINISHED)
        self.assertEqual(events[-1].payload["teaching"]["avatar"]["action"], "nod")
        self.assertIsNone(events[-1].payload["teaching"]["fallback_reason"])
        usage = [event for event in events if event.type is RuntimeEventType.USAGE_UPDATED]
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].payload["input_tokens"], 12)
        self.assertEqual(client.calls, 1)

    async def test_bad_avatar_keeps_reply_and_logs_only_safe_fallback_metadata(self) -> None:
        client = JointOutputLLM(['{"reply":"Try again.","avatar":{"script":"private-code"}}'])
        with patch("app.adapters.agent.native.log") as logger:
            events = [event async for event in NativeAgentRuntime(client).stream(self.request())]
        self.assertEqual([event.payload["text"] for event in events
                          if event.type is RuntimeEventType.ASSISTANT_DELTA], ["Try again."])
        result = events[-1].payload["teaching"]
        self.assertEqual(result["avatar"], AvatarControl().model_dump(mode="json"))
        self.assertEqual(result["fallback_reason"], "invalid_avatar")
        self.assertNotIn("private-code", str(events))
        logger.warning.assert_called_once()
        self.assertNotIn("private-code", str(logger.warning.call_args))
        self.assertEqual(client.calls, 1)

    async def test_bad_output_has_no_reply_or_success_but_preserves_reported_usage(self) -> None:
        for text in ('{"reply":"partial', '{"reply":" "}', '{"reply":"ok","thoughts":"private"}'):
            with self.subTest(text=text):
                client = JointOutputLLM([text])
                events = []
                with self.assertRaises(TeachingOutputError):
                    async for event in NativeAgentRuntime(client).stream(self.request()):
                        events.append(event)
                self.assertFalse(any(event.type in {RuntimeEventType.ASSISTANT_DELTA, RuntimeEventType.RUN_FINISHED}
                                     for event in events))
                self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)
                self.assertEqual(events[-1].payload, {"error_type": "TeachingOutputError"})
                usage = [event for event in events if event.type is RuntimeEventType.USAGE_UPDATED]
                self.assertEqual(len(usage), 1)
                self.assertEqual(usage[0].payload["input_tokens"], 12)
                self.assertEqual(client.calls, 1)

    async def test_provider_failure_discards_buffer_and_cancellation_propagates(self) -> None:
        for error in (RuntimeError("provider failed"), asyncio.CancelledError()):
            with self.subTest(error=type(error).__name__):
                client = JointOutputLLM(['{"reply":"complete but not confirmed"}'], error)
                events = []
                with self.assertRaises(type(error)):
                    async for event in NativeAgentRuntime(client).stream(self.request()):
                        events.append(event)
                self.assertFalse(any(event.type in {RuntimeEventType.ASSISTANT_DELTA, RuntimeEventType.RUN_FINISHED}
                                     for event in events))

    async def test_buffer_limit_stops_before_consuming_remaining_provider_output(self) -> None:
        client = JointOutputLLM(["x" * MAX_TEACHING_OUTPUT_CHARS, "x", "must not be read"])
        events = []
        with self.assertRaises(TeachingOutputError) as caught:
            async for event in NativeAgentRuntime(client).stream(self.request()):
                events.append(event)
        self.assertEqual(caught.exception.reason, "output_too_large")
        self.assertEqual(client.consumed, 2)
        self.assertFalse(any(event.type is RuntimeEventType.ASSISTANT_DELTA for event in events))
        usage = [event for event in events if event.type is RuntimeEventType.USAGE_UPDATED]
        self.assertEqual(usage[0].payload["usage_status"], "unavailable")

    async def test_workspace_keeps_original_incremental_text_without_json_parsing(self) -> None:
        parts = ['{"reply":', '"not parsed"}']
        client = JointOutputLLM(parts)
        events = [event async for event in NativeAgentRuntime(client).stream(self.request("workspace"))]
        self.assertEqual([event.payload["text"] for event in events
                          if event.type is RuntimeEventType.ASSISTANT_DELTA], parts)
        self.assertEqual(events[-1].payload, {})
