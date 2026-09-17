"""Server-side Google OAuth authorization-code flow with state and PKCE."""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from pydantic import SecretStr

from app.services.google_oauth_credentials import GoogleOAuthCredential


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_READ_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
)


class GoogleOAuthFlowError(RuntimeError):
    pass


class GoogleCredentialStore(Protocol):
    async def save(
        self,
        client_id: str,
        refresh_token: SecretStr,
        scopes: tuple[str, ...],
        account_email: str | None = None,
    ) -> None: ...

    async def load(self, client_id: str) -> GoogleOAuthCredential | None: ...

    async def delete(self, client_id: str) -> bool: ...


@dataclass(frozen=True)
class PendingGoogleAuthorization:
    client_id: str
    code_verifier: str
    expires_at: float


class GoogleOAuthFlow:
    def __init__(
        self,
        credential_store: GoogleCredentialStore,
        client_id: str,
        client_secret: SecretStr,
        redirect_uri: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._store = credential_store
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._transport = transport
        self._pending: dict[str, PendingGoogleAuthorization] = {}

    def start(self, workspace_client_id: str) -> str:
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        now = time.monotonic()
        self._pending = {
            key: value for key, value in self._pending.items()
            if value.expires_at >= now
        }
        self._pending[state] = PendingGoogleAuthorization(
            workspace_client_id, verifier, now + 600
        )
        query = urlencode({
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_READ_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        })
        return f"{GOOGLE_AUTH_URL}?{query}"

    async def complete(self, state: str, code: str) -> str:
        pending = self._pending.pop(state, None)
        if pending is None or pending.expires_at < time.monotonic():
            raise GoogleOAuthFlowError("Google OAuth state is invalid or expired")
        async with httpx.AsyncClient(
            transport=self._transport, timeout=30
        ) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": self._client_id,
                "client_secret": self._client_secret.get_secret_value(),
                "code": code,
                "code_verifier": pending.code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": self._redirect_uri,
            })
        if response.status_code != 200:
            raise GoogleOAuthFlowError("Google OAuth token exchange failed")
        payload: object = response.json()
        if not isinstance(payload, dict):
            raise GoogleOAuthFlowError("Google OAuth token response is invalid")
        refresh_token = payload.get("refresh_token")
        scope = payload.get("scope")
        if not isinstance(refresh_token, str):
            raise GoogleOAuthFlowError("Google did not return a refresh token")
        scopes = tuple(scope.split()) if isinstance(scope, str) else GOOGLE_READ_SCOPES
        await self._store.save(
            pending.client_id, SecretStr(refresh_token), scopes
        )
        return pending.client_id

    async def connection(
        self, client_id: str,
    ) -> GoogleOAuthCredential | None:
        return await self._store.load(client_id)

    async def disconnect(self, client_id: str) -> bool:
        credential = await self._store.load(client_id)
        if credential is None:
            return False
        async with httpx.AsyncClient(
            transport=self._transport, timeout=30
        ) as client:
            response = await client.post(
                GOOGLE_REVOKE_URL,
                params={"token": credential.refresh_token.get_secret_value()},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code not in {200, 400}:
            raise GoogleOAuthFlowError("Google OAuth revocation failed")
        return await self._store.delete(client_id)