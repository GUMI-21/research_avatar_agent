"""Tests for Google OAuth state, PKCE, token exchange, and routing."""

import unittest
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI
from pydantic import SecretStr

from app.api.routes import google_oauth
from app.services.google_oauth_credentials import GoogleOAuthCredential
from app.services.google_oauth_flow import (
    GOOGLE_AUTH_URL,
    GOOGLE_REVOKE_URL,
    GOOGLE_TOKEN_URL,
    GoogleOAuthFlow,
    GoogleOAuthFlowError,
)


class FakeCredentialStore:
    def __init__(self) -> None:
        self.saved: tuple[str, str, tuple[str, ...]] | None = None
        self.credentials: dict[str, GoogleOAuthCredential] = {}

    async def save(
        self,
        client_id: str,
        refresh_token: SecretStr,
        scopes: tuple[str, ...],
        account_email: str | None = None,
    ) -> None:
        self.saved = (
            client_id, refresh_token.get_secret_value(), scopes,
        )
        self.credentials[client_id] = GoogleOAuthCredential(
            account_email, scopes, refresh_token
        )

    async def load(self, client_id: str) -> GoogleOAuthCredential | None:
        return self.credentials.get(client_id)

    async def delete(self, client_id: str) -> bool:
        return self.credentials.pop(client_id, None) is not None


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

    async def test_routes_report_and_revoke_only_current_client(self) -> None:
        store = FakeCredentialStore()
        revoked_tokens: list[str] = []

        async def google(request: httpx.Request) -> httpx.Response:
            if str(request.url) == GOOGLE_TOKEN_URL:
                return httpx.Response(200, json={
                    "refresh_token": "route-refresh",
                    "scope": "gmail.readonly",
                })
            if str(request.url).startswith(GOOGLE_REVOKE_URL):
                revoked_tokens.extend(parse_qs(request.url.query.decode())["token"])
                return httpx.Response(200)
            return httpx.Response(500)

        app = FastAPI()
        app.state.google_oauth_flow = GoogleOAuthFlow(
            store,
            "google-client",
            SecretStr("google-secret"),
            "http://testserver/api/v1/google/oauth/callback",
            httpx.MockTransport(google),
        )
        app.include_router(google_oauth.router, prefix="/api/v1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            headers = {"X-Client-ID": "alice"}
            started = await client.post(
                "/api/v1/google/oauth/start", headers=headers
            )
            state = parse_qs(
                urlparse(started.json()["authorization_url"]).query
            )["state"][0]
            completed = await client.get(
                "/api/v1/google/oauth/callback",
                params={"state": state, "code": "route-code"},
            )
            connected = await client.get(
                "/api/v1/google/oauth/status", headers=headers
            )
            other = await client.get(
                "/api/v1/google/oauth/status",
                headers={"X-Client-ID": "bob"},
            )
            disconnected = await client.delete(
                "/api/v1/google/oauth/connection", headers=headers
            )

        self.assertEqual(completed.json(), {"connected": True})
        self.assertTrue(connected.json()["connected"])
        self.assertFalse(other.json()["connected"])
        self.assertEqual(disconnected.json(), {
            "connected": False, "account_email": None, "scopes": [],
        })
        self.assertEqual(revoked_tokens, ["route-refresh"])
        self.assertNotIn("alice", store.credentials)


if __name__ == "__main__":
    unittest.main()