"""Encrypted, client-scoped persistence for Google OAuth refresh tokens."""

import json
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from app.core.database import Database
from app.models import GoogleOAuthCredentialRecord


class GoogleOAuthCredentialError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleOAuthCredential:
    account_email: str | None
    scopes: tuple[str, ...]
    refresh_token: SecretStr


class GoogleOAuthCredentialStore:
    def __init__(self, database: Database, key_path: Path) -> None:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            key_path.write_bytes(Fernet.generate_key())
            key_path.chmod(0o600)
        self._database = database
        self._cipher = Fernet(key_path.read_bytes().strip())

    async def save(
        self,
        client_id: str,
        refresh_token: SecretStr,
        scopes: tuple[str, ...],
        account_email: str | None = None,
    ) -> None:
        normalized_scopes = tuple(sorted(set(scopes)))
        if not normalized_scopes:
            raise ValueError("At least one Google OAuth scope is required")
        ciphertext = self._cipher.encrypt(
            refresh_token.get_secret_value().encode()
        ).decode()
        async with self._database.session() as session:
            record = await session.get(GoogleOAuthCredentialRecord, client_id)
            if record is None:
                record = GoogleOAuthCredentialRecord(client_id=client_id)
                session.add(record)
            record.account_email = account_email
            record.scopes_json = json.dumps(normalized_scopes)
            record.refresh_token_ciphertext = ciphertext
            await session.commit()

    async def load(self, client_id: str) -> GoogleOAuthCredential | None:
        async with self._database.session() as session:
            record = await session.get(GoogleOAuthCredentialRecord, client_id)
        if record is None:
            return None
        try:
            token = self._cipher.decrypt(
                record.refresh_token_ciphertext.encode()
            ).decode()
        except InvalidToken as error:
            raise GoogleOAuthCredentialError(
                "Stored Google OAuth credential cannot be decrypted"
            ) from error
        raw_scopes: object = json.loads(record.scopes_json)
        if not isinstance(raw_scopes, list) or not all(
            isinstance(scope, str) for scope in raw_scopes
        ):
            raise GoogleOAuthCredentialError("Stored Google OAuth scopes are invalid")
        return GoogleOAuthCredential(
            account_email=record.account_email,
            scopes=tuple(raw_scopes),
            refresh_token=SecretStr(token),
        )

    async def delete(self, client_id: str) -> bool:
        async with self._database.session() as session:
            record = await session.get(GoogleOAuthCredentialRecord, client_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True