"""Tests for the safe runtime policy endpoint."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.main import _mark_mcp_unavailable
from app.tools import MCPError


class RuntimePolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_policy_requires_scope_and_reports_demo_restrictions(self) -> None:
        app = FastAPI()
        app.state.demo_mode = True
        app.state.blocked_tool_risks = ("local_write", "external_write")
        app.state.mcp_statuses = {
            ("stdio", "browser"): {
                "name": "browser", "transport": "stdio",
                "status": "connected", "tool_count": 3,
                "error_type": None,
            },
        }
        app.include_router(api_router)
        try:
            raise MCPError("safe") from TimeoutError("private URL")
        except MCPError as error:
            _mark_mcp_unavailable(app, "stdio", "browser", error)
        client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        )
        try:
            missing = await client.get("/api/v1/runtime/policy")
            response = await client.get(
                "/api/v1/runtime/policy",
                headers={"X-Client-ID": "client-a"},
            )
            mcp = await client.get(
                "/api/v1/runtime/mcp-status",
                headers={"X-Client-ID": "client-a"},
            )
        finally:
            await client.aclose()

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(response.json(), {
            "demo_mode": True,
            "blocked_tool_risks": ["local_write", "external_write"],
        })
        self.assertEqual(mcp.json()["servers"], [{
            "name": "browser", "transport": "stdio",
            "status": "unavailable", "tool_count": 3,
            "error_type": "TimeoutError",
        }])


if __name__ == "__main__":
    unittest.main()
