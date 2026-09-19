"""Approved Gmail read tools backed by the shared Google API client."""

import base64
import json
from typing import Any
from urllib.parse import quote

from pydantic import Field

from app.services.google_api_client import GoogleAPIClient, GoogleAPIError
from app.tools.registry import (
    ToolArguments,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolRisk,
    ToolSpec,
)


class GmailListMessagesArguments(ToolArguments):
    query: str = Field(default="", max_length=500)
    max_results: int = Field(default=10, ge=1, le=20)
    page_token: str | None = Field(default=None, max_length=1_000)


class GmailGetMessageArguments(ToolArguments):
    message_id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    max_body_chars: int = Field(default=12_000, ge=1, le=16_000)


def _plain_text(part: object) -> str:
    if not isinstance(part, dict):
        return ""
    body = part.get("body")
    if part.get("mimeType") == "text/plain" and isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, str):
            try:
                padded = data + "=" * (-len(data) % 4)
                return base64.urlsafe_b64decode(padded).decode(
                    "utf-8", errors="replace"
                )
            except ValueError:
                return ""
    parts = part.get("parts")
    if isinstance(parts, list):
        return "\n".join(filter(None, (_plain_text(child) for child in parts)))
    return ""


def _message_summary(payload: dict[str, Any], max_body_chars: int) -> dict[str, Any]:
    message_payload = payload.get("payload")
    headers: dict[str, str] = {}
    if isinstance(message_payload, dict):
        raw_headers = message_payload.get("headers")
        if isinstance(raw_headers, list):
            for item in raw_headers:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    name = item["name"].lower()
                    if name in {"subject", "from", "to", "date"} and isinstance(
                        item.get("value"), str
                    ):
                        headers[name] = item["value"]
    body = _plain_text(message_payload)
    return {
        "id": payload.get("id"),
        "thread_id": payload.get("threadId"),
        "headers": headers,
        "snippet": payload.get("snippet", ""),
        "body": body[:max_body_chars],
        "body_truncated": len(body) > max_body_chars,
    }


def register_google_read_tools(
    registry: ToolRegistry, client: GoogleAPIClient
) -> None:
    async def list_messages(
        context: ToolContext, raw: ToolArguments
    ) -> ToolResult:
        assert isinstance(raw, GmailListMessagesArguments)
        params: dict[str, Any] = {"maxResults": raw.max_results}
        if raw.query:
            params["q"] = raw.query
        if raw.page_token:
            params["pageToken"] = raw.page_token
        try:
            response = await client.request(
                context.client_id, "GET", "gmail",
                "/gmail/v1/users/me/messages", params=params,
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise GoogleAPIError("Gmail returned an invalid response")
            messages = payload.get("messages", [])
            result = {
                "messages": messages if isinstance(messages, list) else [],
                "next_page_token": payload.get("nextPageToken"),
                "result_size_estimate": payload.get("resultSizeEstimate"),
            }
            return ToolResult(json.dumps(result), {"message_count": len(result["messages"])})
        except (GoogleAPIError, ValueError) as error:
            return ToolResult(str(error), {
                "status": "error", "error_type": type(error).__name__,
            })

    async def get_message(
        context: ToolContext, raw: ToolArguments
    ) -> ToolResult:
        assert isinstance(raw, GmailGetMessageArguments)
        try:
            response = await client.request(
                context.client_id, "GET", "gmail",
                f"/gmail/v1/users/me/messages/{quote(raw.message_id, safe='')}",
                params={"format": "full"},
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise GoogleAPIError("Gmail returned an invalid response")
            result = _message_summary(payload, raw.max_body_chars)
            return ToolResult(json.dumps(result), {
                "message_id": raw.message_id,
                "body_truncated": result["body_truncated"],
            })
        except (GoogleAPIError, ValueError) as error:
            return ToolResult(str(error), {
                "status": "error", "error_type": type(error).__name__,
            })

    registry.register(ToolSpec(
        "gmail_list_messages", "List Gmail message IDs matching a Gmail search query.",
        GmailListMessagesArguments, ToolRisk.EXTERNAL_READ, list_messages,
    ))
    registry.register(ToolSpec(
        "gmail_get_message", "Read one Gmail message, including selected headers and plain text.",
        GmailGetMessageArguments, ToolRisk.EXTERNAL_READ, get_message,
    ))
