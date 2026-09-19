"""Approved Gmail read tools backed by the shared Google API client."""

import base64
import json
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Self
from urllib.parse import quote

from pydantic import Field, field_validator, model_validator

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


class CalendarListEventsArguments(ToolArguments):
    time_min: datetime
    time_max: datetime
    calendar_id: str = Field(default="primary", min_length=1, max_length=256)
    max_results: int = Field(default=20, ge=1, le=50)
    page_token: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.time_min.tzinfo is None or self.time_max.tzinfo is None:
            raise ValueError("Calendar time range must include a timezone")
        if self.time_max <= self.time_min:
            raise ValueError("Calendar time_max must be later than time_min")
        return self


class GmailComposeArguments(ToolArguments):
    to: list[str] = Field(min_length=1, max_length=20)
    cc: list[str] = Field(default_factory=list, max_length=20)
    subject: str = Field(default="", max_length=998)
    body: str = Field(default="", max_length=100_000)

    @field_validator("to", "cc")
    @classmethod
    def validate_addresses(cls, values: list[str]) -> list[str]:
        if any(
            not value or len(value) > 320 or "@" not in value
            or "\r" in value or "\n" in value
            for value in values
        ):
            raise ValueError("Email addresses are invalid")
        return values

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Email subject cannot contain newlines")
        return value


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


def _event_time(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item for key in ("dateTime", "date", "timeZone")
        if isinstance((item := value.get(key)), str)
    }


def _limited_text(value: object) -> str:
    return value[:500] if isinstance(value, str) else ""


def _raw_message(arguments: GmailComposeArguments) -> str:
    message = EmailMessage()
    message["To"] = ", ".join(arguments.to)
    if arguments.cc:
        message["Cc"] = ", ".join(arguments.cc)
    message["Subject"] = arguments.subject
    message.set_content(arguments.body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")


def _email_approval(arguments: dict[str, object], action: str) -> dict[str, str]:
    recipients = arguments.get("to")
    visible = ", ".join(str(item)[:320] for item in recipients[:20]) \
        if isinstance(recipients, list) else ""
    cc = arguments.get("cc")
    visible_cc = ", ".join(str(item)[:320] for item in cc[:20]) \
        if isinstance(cc, list) else ""
    return {
        "action": action,
        "recipients": visible[:1_000],
        "cc": visible_cc[:1_000],
        "subject": _limited_text(arguments.get("subject")),
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

    async def list_events(
        context: ToolContext, raw: ToolArguments
    ) -> ToolResult:
        assert isinstance(raw, CalendarListEventsArguments)
        params: dict[str, Any] = {
            "timeMin": raw.time_min.isoformat(),
            "timeMax": raw.time_max.isoformat(),
            "maxResults": raw.max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if raw.page_token:
            params["pageToken"] = raw.page_token
        try:
            response = await client.request(
                context.client_id, "GET", "calendar",
                f"/calendar/v3/calendars/{quote(raw.calendar_id, safe='')}/events",
                params=params,
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise GoogleAPIError("Google Calendar returned an invalid response")
            items = payload.get("items")
            events = [
                {
                    "id": item.get("id"),
                    "status": item.get("status"),
                    "summary": _limited_text(item.get("summary")),
                    "start": _event_time(item.get("start")),
                    "end": _event_time(item.get("end")),
                    "location": _limited_text(item.get("location")),
                }
                for item in items if isinstance(item, dict)
            ] if isinstance(items, list) else []
            result = {
                "events": events,
                "next_page_token": payload.get("nextPageToken"),
                "time_zone": payload.get("timeZone"),
            }
            return ToolResult(json.dumps(result), {"event_count": len(events)})
        except (GoogleAPIError, ValueError) as error:
            return ToolResult(str(error), {
                "status": "error", "error_type": type(error).__name__,
            })

    async def write_message(
        context: ToolContext, raw: ToolArguments, *, draft: bool,
    ) -> ToolResult:
        assert isinstance(raw, GmailComposeArguments)
        try:
            body = {"message": {"raw": _raw_message(raw)}} if draft \
                else {"raw": _raw_message(raw)}
            response = await client.request(
                context.client_id, "POST", "gmail",
                "/gmail/v1/users/me/drafts" if draft
                else "/gmail/v1/users/me/messages/send",
                json=body,
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise GoogleAPIError("Gmail returned an invalid response")
            message = payload.get("message") if draft else payload
            message_id = message.get("id") if isinstance(message, dict) else None
            return ToolResult(
                "Gmail draft created" if draft else "Gmail message sent",
                {"draft_id": payload.get("id"), "message_id": message_id}
                if draft else {"message_id": message_id},
            )
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
    registry.register(ToolSpec(
        "calendar_list_events", "List calendar events in an explicit RFC3339 time range.",
        CalendarListEventsArguments, ToolRisk.EXTERNAL_READ, list_events,
    ))
    registry.register(ToolSpec(
        "gmail_create_draft", "Create a Gmail draft after explicit user approval.",
        GmailComposeArguments, ToolRisk.EXTERNAL_WRITE,
        lambda context, raw: write_message(context, raw, draft=True),
        approval_summary=lambda args: _email_approval(args, "create_draft"),
    ))
    registry.register(ToolSpec(
        "gmail_send_message", "Send an email through Gmail after explicit user approval.",
        GmailComposeArguments, ToolRisk.EXTERNAL_WRITE,
        lambda context, raw: write_message(context, raw, draft=False),
        approval_summary=lambda args: _email_approval(args, "send_message"),
    ))
