"""Encrypted persistence for client-scoped provider configuration."""

from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import select

from app.adapters.llm.errors import LLMConfigurationError
from app.core.database import Database
from app.models import LLMCredentialRecord
from app.schemas.llm import LLMConfigRequest, LLMConfigResponse
from app.services.llm_runtime import LLMRuntime
from logs import log


# 保存api_key密钥
class LLMCredentialStore:
    def __init__(self, database: Database, key_path: Path) -> None:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        if not key_path.exists():
            key_path.write_bytes(Fernet.generate_key())
            key_path.chmod(0o600)
        self._database = database
        self._cipher = Fernet(key_path.read_bytes().strip())

    async def save(
        self, client_id: str, request: LLMConfigRequest, response: LLMConfigResponse
    ) -> None:
        async with self._database.session() as session:
            identity = {"client_id": client_id, "provider": response.provider.value}
            record = await session.get(LLMCredentialRecord, identity)
            ciphertext = record.api_key_ciphertext if record else None
            if request.api_key is not None:
                secret = request.api_key.get_secret_value().encode()
                ciphertext = self._cipher.encrypt(secret).decode()
            if record is None:
                record = LLMCredentialRecord(**identity)
                session.add(record)
            record.model = response.model
            record.base_url = response.base_url
            record.api_key_ciphertext = ciphertext
            await session.commit()

    async def restore(self, runtime: LLMRuntime) -> None:
        async with self._database.session() as session:
            result = await session.execute(
                select(LLMCredentialRecord).order_by(LLMCredentialRecord.updated_at)
            )
            records = result.scalars().all()
        for record in records:
            try:
                api_key = (
                    SecretStr(
                        self._cipher.decrypt(
                            record.api_key_ciphertext.encode()
                        ).decode()
                    )
                    if record.api_key_ciphertext
                    else None
                )
                runtime.configure(
                    LLMConfigRequest(
                        provider=record.provider,
                        model=record.model,
                        base_url=record.base_url,
                        api_key=api_key,
                    ),
                    record.client_id,
                )
            except (
                InvalidToken, LLMConfigurationError, ValueError, TypeError
            ) as error:
                log.warning(
                    "LLM credential restore skipped client_id={} provider={} error_type={}",
                    record.client_id, record.provider, type(error).__name__,
                )
