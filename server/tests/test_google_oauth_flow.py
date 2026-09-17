"""Tests for Google OAuth state, PKCE, token exchange, and routing."""

import unittest
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI
from pydantic import SecretStr

from app.api.routes import google_oauth
from app.services.google_oauth_flow import (
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    GoogleOAuthFlow,
    GoogleOAuthFlowError,
)


class FakeCredentialStore:
    def __init__(self) -> None:
        self.saved: tuple[str, str, tuple[str, ...]] | None = None

    async def save(
        self,
        client_id: str,
        refresh_token: SecretStr,
        scopes: tuple[str, ...],
        account_email: str | None = None,
    ) -> None:
        del account_email
        self.saved = (
            client_id, refresh_token.get_secret_value(), scopes,
        )


class GoogleOAuthFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_state_pkce_and_token_exchange_are_client_scoped(self) -> None:
        store = FakeCredentialStore()
        token_request: dict[str, list[str]] = {}

        async def exchange(request: httpx.Request) -> httpx.Response:
            self.assertEqual(str(request.url), GOOGLE_TOKEN_URL)
            token_request.update(parse_qs(request.content.decode()))
            return httpx.Response(200, json={
                "refresh_token": "refresh-secret",
                "scope": "gmail.readonly calendar.readonly",
            })

        flow = GoogleOAuthFlow(
            store,
            "google-client",
            SecretStr("google-secret"),
            "http://127.0.0.1:8000/api/v1/google/oauth/callback",
            httpx.MockTransport(exchange),
        )
        authorization_url = flow.start("alice")
        parsed = urlparse(authorization_url)
        query = parse_qs(parsed.query)

        self.assertEqual(
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}", GOOGLE_AUTH_URL
        )
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertNotIn("google-secret", authorization_url)

        state = query["state"][0]
        await flow.complete(state, "authorization-code")

        self.assertEqual(
            store.saved,
            ("alice", "refresh-secret", ("gmail.readonly", "calendar.readonly")),
        )
        self.assertEqual(token_request["code"], ["authorization-code"])
        self.assertIn("code_verifier", token_request)
        with self.assertRaisesRegex(GoogleOAuthFlowError, "invalid or expired"):
            await flow.complete(state, "replayed-code")

    async def test_routes_start_and_complete_the_flow(self) -> None:
        store = FakeCredentialStore()

        async def exchange(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "refresh_token": "route-refresh",
                "scope": "gmail.readonly",
            })

        app = FastAPI()
        app.state.google_oauth_flow = GoogleOAuthFlow(
            store,
            "google-client",
            SecretStr("google-secret"),
            "http://testserver/api/v1/google/oauth/callback",
            httpx.MockTransport(exchange),
        )
        app.include_router(google_oauth.router, prefix="/api/v1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            started = await client.post(
                "/api/v1/google/oauth/start",
                headers={"X-Client-ID": "alice"},
            )
            state = parse_qs(
                urlparse(started.json()["authorization_url"]).query
            )["state"][0]
            completed = await client.get(
                "/api/v1/google/oauth/callback",
                params={"state": state, "code": "route-code"},
            )

        self.assertEqual(started.status_code, 200)
        self.assertEqual(completed.json(), {"connected": True})
        self.assertEqual(store.saved, ("alice", "route-refresh", ("gmail.readonly",)))

if __name__ == "__main__":
    unittest.main()