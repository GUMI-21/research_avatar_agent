"""Tests for approved, client-scoped Gmail read tools."""

import base64
import json
import unittest
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from typing import Any

import httpx

from app.services.google_api_client import GoogleAuthorizationRequired
from app.tools.google import register_google_read_tools
from app.tools.registry import (
    ToolApprovalRequiredError,
    ToolContext,
    ToolRegistry,
    ToolRisk,
)


class FakeGoogleAPIClient:
    def __init__(self, *responses: httpx.Response | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, str, str, dict[str, Any] | None]] = []
        self.json_bodies: list[Any] = []

    async def request(
        self, client_id: str, method: str, service: str, path: str, *,
        params: dict[str, Any] | None = None, json: Any = None,
    ) -> httpx.Response:
        self.calls.append((client_id, method, service, path, params))
        self.json_bodies.append(json)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class GoogleToolsTest(unittest.IsolatedAsyncioTestCase):
    async def test_gmail_tools_require_approval_and_use_client_context(self) -> None:
        body = base64.urlsafe_b64encode("hello interview".encode()).decode()
        client = FakeGoogleAPIClient(
            httpx.Response(200, json={
                "messages": [{"id": "message-1", "threadId": "thread-1"}],
                "resultSizeEstimate": 1,
            }),
            httpx.Response(200, json={
                "id": "message-1",
                "threadId": "thread-1",
                "snippet": "hello",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Interview"},
                        {"name": "From", "value": "team@example.com"},
                    ],
                    "parts": [{"mimeType": "text/plain", "body": {"data": body}}],
                },
            }),
        )
        registry = ToolRegistry()
        register_google_read_tools(registry, client)  # type: ignore[arg-type]
        context = ToolContext("client-a", "agent-a")

        with self.assertRaises(ToolApprovalRequiredError) as approval:
            await registry.execute(
                "gmail_list_messages", context, {"query": "interview"}
            )
        self.assertEqual(approval.exception.tool.risk, ToolRisk.EXTERNAL_READ)
        self.assertEqual(client.calls, [])

        listed = await registry.execute(
            "gmail_list_messages", context,
            {"query": "interview", "max_results": 5}, approved=True,
        )
        message = await registry.execute(
            "gmail_get_message", context,
            {"message_id": "message-1", "max_body_chars": 5}, approved=True,
        )

        self.assertEqual(json.loads(listed.content)["messages"][0]["id"], "message-1")
        self.assertEqual(client.calls[0], (
            "client-a", "GET", "gmail", "/gmail/v1/users/me/messages",
            {"maxResults": 5, "q": "interview"},
        ))
        parsed = json.loads(message.content)
        self.assertEqual(parsed["headers"]["subject"], "Interview")
        self.assertEqual(parsed["body"], "hello")
        self.assertTrue(parsed["body_truncated"])
        self.assertNotIn("Interview", message.metadata)

    async def test_google_errors_return_to_the_tool_loop_safely(self) -> None:
        client = FakeGoogleAPIClient(
            GoogleAuthorizationRequired("Google authorization was revoked")
        )
        registry = ToolRegistry()
        register_google_read_tools(registry, client)  # type: ignore[arg-type]

        result = await registry.execute(
            "gmail_list_messages", ToolContext("client-a", "agent-a"), {},
            approved=True,
        )

        self.assertEqual(result.metadata["status"], "error")
        self.assertEqual(result.metadata["error_type"], "GoogleAuthorizationRequired")
        self.assertIn("revoked", result.content)

    async def test_calendar_events_are_approved_scoped_and_normalized(self) -> None:
        client = FakeGoogleAPIClient(httpx.Response(200, json={
            "timeZone": "Asia/Tokyo",
            "items": [{
                "id": "event-1",
                "status": "confirmed",
                "summary": "Interview",
                "start": {
                    "dateTime": "2026-09-20T10:00:00+09:00",
                    "untrusted": "must not pass through",
                },
                "end": {"dateTime": "2026-09-20T11:00:00+09:00"},
                "location": "Tokyo",
                "description": "must not be returned by a list operation",
            }],
        }))
        registry = ToolRegistry()
        register_google_read_tools(registry, client)  # type: ignore[arg-type]
        context = ToolContext("client-b", "agent-a")
        arguments = {
            "time_min": "2026-09-20T00:00:00+09:00",
            "time_max": "2026-09-21T00:00:00+09:00",
            "calendar_id": "person@example.com",
            "max_results": 5,
        }

        with self.assertRaises(ToolApprovalRequiredError):
            await registry.execute("calendar_list_events", context, arguments)
        result = await registry.execute(
            "calendar_list_events", context, arguments, approved=True
        )

        self.assertEqual(client.calls[0][0:4], (
            "client-b", "GET", "calendar",
            "/calendar/v3/calendars/person%40example.com/events",
        ))
        self.assertEqual(client.calls[0][4], {
            "timeMin": "2026-09-20T00:00:00+09:00",
            "timeMax": "2026-09-21T00:00:00+09:00",
            "maxResults": 5,
            "singleEvents": True,
            "orderBy": "startTime",
        })
        parsed = json.loads(result.content)
        self.assertEqual(parsed["events"][0]["summary"], "Interview")
        self.assertNotIn("description", parsed["events"][0])
        self.assertEqual(parsed["events"][0]["start"], {
            "dateTime": "2026-09-20T10:00:00+09:00"
        })
        self.assertEqual(result.metadata, {"event_count": 1})

    async def test_calendar_rejects_naive_or_reversed_time_ranges(self) -> None:
        registry = ToolRegistry()
        client = FakeGoogleAPIClient()
        register_google_read_tools(registry, client)  # type: ignore[arg-type]
        context = ToolContext("client-a", "agent-a")

        invalid_ranges = (
            (datetime(2026, 9, 20), datetime(2026, 9, 21)),
            (
                datetime(2026, 9, 21, tzinfo=timezone.utc),
                datetime(2026, 9, 20, tzinfo=timezone.utc),
            ),
        )
        for time_min, time_max in invalid_ranges:
            with self.subTest(time_min=time_min):
                with self.assertRaises(ValueError):
                    await registry.execute(
                        "calendar_list_events", context,
                        {"time_min": time_min, "time_max": time_max}, approved=True,
                    )
        self.assertEqual(client.calls, [])

    async def test_gmail_draft_and_send_require_safe_write_approval(self) -> None:
        client = FakeGoogleAPIClient(
            httpx.Response(200, json={
                "id": "draft-1", "message": {"id": "message-1"},
            }),
            httpx.Response(200, json={"id": "message-2"}),
        )
        registry = ToolRegistry()
        register_google_read_tools(registry, client)  # type: ignore[arg-type]
        context = ToolContext("client-a", "agent-a")
        arguments = {
            "to": ["candidate@example.com"],
            "cc": ["reviewer@example.com"],
            "subject": "Interview",
            "body": "private body",
        }

        with self.assertRaises(ToolApprovalRequiredError) as pending:
            await registry.execute("gmail_send_message", context, arguments)
        self.assertEqual(pending.exception.tool.risk, ToolRisk.EXTERNAL_WRITE)
        assert pending.exception.tool.approval_summary is not None
        summary = pending.exception.tool.approval_summary(arguments)
        self.assertEqual(summary["recipients"], "candidate@example.com")
        self.assertEqual(summary["cc"], "reviewer@example.com")
        self.assertEqual(summary["subject"], "Interview")
        self.assertNotIn("private body", summary.values())
        self.assertEqual(client.calls, [])

        draft = await registry.execute(
            "gmail_create_draft", context, arguments, approved=True
        )
        sent = await registry.execute(
            "gmail_send_message", context, arguments, approved=True
        )

        self.assertEqual(client.calls[0][3], "/gmail/v1/users/me/drafts")
        self.assertEqual(client.calls[1][3], "/gmail/v1/users/me/messages/send")
        encoded = client.json_bodies[0]["message"]["raw"]
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        message = BytesParser(policy=policy.default).parsebytes(decoded)
        self.assertEqual(message["To"], "candidate@example.com")
        self.assertEqual(message["Cc"], "reviewer@example.com")
        self.assertEqual(message["Subject"], "Interview")
        self.assertEqual(message.get_content().strip(), "private body")
        self.assertEqual(draft.metadata, {
            "draft_id": "draft-1", "message_id": "message-1",
        })
        self.assertEqual(sent.metadata, {"message_id": "message-2"})
        self.assertNotIn("private body", json.dumps(draft.metadata))


if __name__ == "__main__":
    unittest.main()
