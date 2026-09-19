"""Tests for client-scoped Google API access and token refresh."""

import unittest
from urllib.parse import parse_qs

import httpx
from pydantic import SecretStr

from app.services.google_api_client import (
    GoogleAPIClient,
    GoogleAPIError,
    GoogleAPIUnavailable,
    GoogleAuthorizationRequired,
    GooglePermissionDenied,
)
from app.services.google_oauth_credentials import GoogleOAuthCredential
from app.services.google_oauth_flow import GOOGLE_TOKEN_URL


class FakeCredentialStore:
    def __init__(self) -> None:
        self.credentials = {
            "alice": GoogleOAuthCredential(
                None, ("gmail.readonly",), SecretStr("alice-refresh")
            ),
            "bob": GoogleOAuthCredential(
                None, ("calendar.readonly",), SecretStr("bob-refresh")
            ),
        }

    async def load(self, client_id: str) -> GoogleOAuthCredential | None:
        return self.credentials.get(client_id)


class GoogleAPIClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_refreshes_and_caches_tokens_per_client(self) -> None:
        refreshes: list[str] = []
        api_tokens: list[str] = []

        async def google(request: httpx.Request) -> httpx.Response:
            if str(request.url) == GOOGLE_TOKEN_URL:
                refresh_token = parse_qs(request.content.decode())["refresh_token"][0]
                refreshes.append(refresh_token)
                return httpx.Response(200, json={
                    "access_token": f"access-{refresh_token}", "expires_in": 3600,
                })
            api_tokens.append(request.headers["Authorization"])
            return httpx.Response(200, json={"ok": True})

        client = GoogleAPIClient(
            FakeCredentialStore(), "oauth-client", SecretStr("oauth-secret"),
            httpx.MockTransport(google),
        )
        try:
            await client.request("alice", "GET", "gmail", "/gmail/v1/users/me/messages")
            await client.request("alice", "GET", "gmail", "/gmail/v1/users/me/messages")
            await client.request("bob", "GET", "calendar", "/calendar/v3/calendars/primary/events")
        finally:
            await client.close()

        self.assertEqual(refreshes, ["alice-refresh", "bob-refresh"])
        self.assertEqual(api_tokens, [
            "Bearer access-alice-refresh",
            "Bearer access-alice-refresh",
            "Bearer access-bob-refresh",
        ])

    async def test_401_refreshes_once_and_403_reports_permission(self) -> None:
        refresh_count = 0

        async def google(request: httpx.Request) -> httpx.Response:
            nonlocal refresh_count
            if str(request.url) == GOOGLE_TOKEN_URL:
                refresh_count += 1
                return httpx.Response(200, json={
                    "access_token": f"access-{refresh_count}", "expires_in": 3600,
                })
            if request.headers["Authorization"] == "Bearer access-1":
                return httpx.Response(401)
            return httpx.Response(403)

        client = GoogleAPIClient(
            FakeCredentialStore(), "id", SecretStr("secret"),
            httpx.MockTransport(google),
        )
        try:
            with self.assertRaises(GooglePermissionDenied):
                await client.request("alice", "GET", "gmail", "/test")
        finally:
            await client.close()
        self.assertEqual(refresh_count, 2)

    async def test_reports_missing_revoked_and_failed_refresh(self) -> None:
        responses = iter([
            httpx.Response(400, json={"error": "invalid_grant", "token": "hidden"}),
            httpx.Response(500, text="access-token-must-not-appear"),
        ])

        async def google(request: httpx.Request) -> httpx.Response:
            return next(responses)

        client = GoogleAPIClient(
            FakeCredentialStore(), "id", SecretStr("secret"),
            httpx.MockTransport(google),
        )
        try:
            with self.assertRaisesRegex(GoogleAuthorizationRequired, "Connect"):
                await client.request("missing", "GET", "gmail", "/test")
            with self.assertRaisesRegex(GoogleAuthorizationRequired, "revoked"):
                await client.request("alice", "GET", "gmail", "/test")
            with self.assertRaises(GoogleAPIError) as raised:
                await client.request("bob", "GET", "calendar", "/test")
            self.assertNotIn("access-token", str(raised.exception))
        finally:
            await client.close()

    async def test_expired_token_refreshes_and_network_errors_are_safe(self) -> None:
        refresh_count = 0

        async def google(request: httpx.Request) -> httpx.Response:
            nonlocal refresh_count
            if str(request.url) == GOOGLE_TOKEN_URL:
                refresh_count += 1
                return httpx.Response(200, json={
                    "access_token": f"short-lived-{refresh_count}", "expires_in": 0,
                })
            if refresh_count == 1:
                return httpx.Response(200)
            raise httpx.ConnectError("secret transport detail", request=request)

        client = GoogleAPIClient(
            FakeCredentialStore(), "id", SecretStr("secret"),
            httpx.MockTransport(google),
        )
        try:
            await client.request("alice", "GET", "gmail", "/test")
            with self.assertRaises(GoogleAPIUnavailable) as raised:
                await client.request("alice", "GET", "gmail", "/test")
            self.assertNotIn("secret", str(raised.exception))
        finally:
            await client.close()
        self.assertEqual(refresh_count, 2)


if __name__ == "__main__":
    unittest.main()
