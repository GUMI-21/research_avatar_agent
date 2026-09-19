"""Tests for approved, client-scoped Gmail read tools."""

import base64
import json
import unittest
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

    async def request(
        self, client_id: str, method: str, service: str, path: str, *,
        params: dict[str, Any] | None = None, json: Any = None,
    ) -> httpx.Response:
        self.calls.append((client_id, method, service, path, params))
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


if __name__ == "__main__":
    unittest.main()
