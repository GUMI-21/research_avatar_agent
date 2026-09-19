"""Client-scoped Google API access with automatic token refresh."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr

from app.services.google_oauth_flow import GOOGLE_TOKEN_URL, GoogleCredentialStore


GOOGLE_API_ROOTS = {
    "gmail": "https://gmail.googleapis.com",
    "calendar": "https://www.googleapis.com",
}


class GoogleAPIError(RuntimeError):
    """A safe-to-display Google integration error."""


class GoogleAuthorizationRequired(GoogleAPIError):
    pass


class GooglePermissionDenied(GoogleAPIError):
    pass


class GoogleAPIUnavailable(GoogleAPIError):
    pass


@dataclass(frozen=True)
class _AccessToken:
    value: SecretStr
    expires_at: float


class GoogleAPIClient:
    def __init__(
        self,
        credential_store: GoogleCredentialStore,
        oauth_client_id: str,
        oauth_client_secret: SecretStr,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._store = credential_store
        self._oauth_client_id = oauth_client_id
        self._oauth_client_secret = oauth_client_secret
        self._http = httpx.AsyncClient(transport=transport, timeout=30)
        self._tokens: dict[str, _AccessToken] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def close(self) -> None:
        await self._http.aclose()

    async def request(
        self,
        client_id: str,
        method: str,
        service: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        root = GOOGLE_API_ROOTS.get(service)
        if root is None or not path.startswith("/"):
            raise ValueError("Unsupported Google API target")
        token = await self._access_token(client_id)
        response = await self._send(method, root + path, token, params, json)
        if response.status_code == 401:
            self._tokens.pop(client_id, None)
            token = await self._access_token(client_id)
            response = await self._send(method, root + path, token, params, json)
            if response.status_code == 401:
                raise GoogleAuthorizationRequired(
                    "Google authorization expired; reconnect the account"
                )
        if response.status_code == 403:
            raise GooglePermissionDenied(
                "Google authorization does not grant the required permission"
            )
        if response.is_error:
            raise GoogleAPIError(
                f"Google API request failed with status {response.status_code}"
            )
        return response

    async def _access_token(self, client_id: str) -> SecretStr:
        cached = self._tokens.get(client_id)
        if cached is not None and cached.expires_at > time.monotonic() + 30:
            return cached.value
        lock = self._locks.setdefault(client_id, asyncio.Lock())
        async with lock:
            cached = self._tokens.get(client_id)
            if cached is not None and cached.expires_at > time.monotonic() + 30:
                return cached.value
            credential = await self._store.load(client_id)
            if credential is None:
                raise GoogleAuthorizationRequired("Connect a Google account first")
            try:
                response = await self._http.post(GOOGLE_TOKEN_URL, data={
                    "client_id": self._oauth_client_id,
                    "client_secret": self._oauth_client_secret.get_secret_value(),
                    "refresh_token": credential.refresh_token.get_secret_value(),
                    "grant_type": "refresh_token",
                })
            except httpx.RequestError as error:
                raise GoogleAPIUnavailable("Google token service is unavailable") from error
            payload = self._safe_json(response)
            if response.status_code != 200:
                if payload.get("error") == "invalid_grant":
                    raise GoogleAuthorizationRequired(
                        "Google authorization was revoked; reconnect the account"
                    )
                raise GoogleAPIError("Google access token refresh failed")
            access_token = payload.get("access_token")
            expires_in = payload.get("expires_in", 3600)
            if not isinstance(access_token, str) or not isinstance(expires_in, (int, float)):
                raise GoogleAPIError("Google token service returned an invalid response")
            token = _AccessToken(
                SecretStr(access_token), time.monotonic() + max(float(expires_in), 0)
            )
            self._tokens[client_id] = token
            return token.value

    async def _send(
        self, method: str, url: str, token: SecretStr,
        params: dict[str, Any] | None, json: Any,
    ) -> httpx.Response:
        try:
            return await self._http.request(
                method, url, params=params, json=json,
                headers={"Authorization": f"Bearer {token.get_secret_value()}"},
            )
        except httpx.RequestError as error:
            raise GoogleAPIUnavailable("Google API is unavailable") from error

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}
