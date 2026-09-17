"""Tests for encrypted, client-scoped Google OAuth persistence."""

import tempfile
import unittest
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import select

from app.core.database import Base, Database
from app.models import GoogleOAuthCredentialRecord
from app.services.google_oauth_credentials import GoogleOAuthCredentialStore


class GoogleOAuthCredentialStoreTest(unittest.IsolatedAsyncioTestCase):
    async def test_encrypts_and_isolates_refresh_tokens(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        with tempfile.TemporaryDirectory() as directory:
            store = GoogleOAuthCredentialStore(
                database, Path(directory) / "credential.key"
            )
            await store.save(
                "alice",
                SecretStr("alice-refresh-token"),
                ("calendar.readonly", "gmail.readonly", "gmail.readonly"),
                "alice@example.com",
            )
            await store.save(
                "bob", SecretStr("bob-refresh-token"), ("gmail.readonly",)
            )

            alice = await store.load("alice")
            bob = await store.load("bob")
            missing = await store.load("charlie")
            async with database.session() as session:
                records = (
                    await session.execute(select(GoogleOAuthCredentialRecord))
                ).scalars().all()

            self.assertIsNotNone(alice)
            self.assertIsNotNone(bob)
            assert alice is not None and bob is not None
            self.assertEqual(alice.account_email, "alice@example.com")
            self.assertEqual(
                alice.scopes, ("calendar.readonly", "gmail.readonly")
            )
            self.assertEqual(
                alice.refresh_token.get_secret_value(), "alice-refresh-token"
            )
            self.assertEqual(
                bob.refresh_token.get_secret_value(), "bob-refresh-token"
            )
            self.assertIsNone(missing)
            ciphertext = " ".join(
                record.refresh_token_ciphertext for record in records
            )
            self.assertNotIn("alice-refresh-token", ciphertext)
            self.assertNotIn("bob-refresh-token", ciphertext)

        await database.dispose()


if __name__ == "__main__":
    unittest.main()