"""Tests for the safe Codex CLI status endpoint."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.services.codex_status import CodexStatusService


class CodexStatusTest(unittest.IsolatedAsyncioTestCase):
    def test_normalizes_account_without_exposing_identity(self) -> None:
        result = CodexStatusService._normalize(
            {"account": {"type": "chatgpt", "email": "private@example.com"}},
            {"rateLimits": {
                "planType": "plus",
                "primary": {
                    "usedPercent": 53, "windowDurationMins": 300,
                    "resetsAt": 1789303661,
                },
                "secondary": {
                    "usedPercent": 20, "windowDurationMins": 10080,
                    "resetsAt": 1789805406,
                },
            }},
        )

        self.assertTrue(result["authenticated"])
        self.assertEqual(result["auth_mode"], "chatgpt")
        self.assertEqual(result["windows"][0]["used_percent"], 53)
        self.assertNotIn("email", result)

    async def test_status_route_requires_scope_and_returns_safe_snapshot(self) -> None:
        app = FastAPI()
        app.state.settings = SimpleNamespace(
            codex=SimpleNamespace(executable="codex", timeout_seconds=300),
        )
        app.include_router(api_router)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        )
        response_data = {
            "installed": True, "authenticated": True,
            "auth_mode": "chatgpt", "plan_type": "plus",
            "windows": [{
                "name": "primary", "used_percent": 53,
                "window_minutes": 300, "resets_at": 1789303661,
            }],
            "error": None,
        }
        try:
            with patch.object(
                CodexStatusService, "read", AsyncMock(return_value=response_data),
            ):
                missing = await client.get("/api/v1/codex/status")
                response = await client.get(
                    "/api/v1/codex/status", headers={"X-Client-ID": "client-a"},
                )
        finally:
            await client.aclose()

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["windows"][0]["window_minutes"], 300)
        self.assertNotIn("account_id", response.json())


if __name__ == "__main__":
    unittest.main()
