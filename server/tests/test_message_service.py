"""Tests for conversation Message transaction handling."""

import unittest
from unittest.mock import patch

from app.core.database import Base, Database
from app.repositories import AgentRepository, MessageRepository, SessionRepository
from app.services import MessageService


class MessageServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_append_commits_without_logging_content(self) -> None:
        async with self.database.session() as database_session:
            agent = await AgentRepository(database_session).create(
                "client-a", name="Personal", system_prompt="Help me."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", agent.id
            )
            await database_session.commit()

            with (
                patch("app.repositories.message.log"),
                patch("app.services.message.log") as service_log,
            ):
                created = await MessageService(database_session).append(
                    "client-a",
                    conversation.id,
                    agent.id,
                    role="user",
                    content="private message",
                )

            records = await MessageRepository(database_session).list_messages(
                "client-a", conversation.id
            )

        self.assertEqual([record.id for record in records], [created.id])
        logged_arguments = service_log.info.call_args.args
        self.assertNotIn("private message", logged_arguments)


if __name__ == "__main__":
    unittest.main()
