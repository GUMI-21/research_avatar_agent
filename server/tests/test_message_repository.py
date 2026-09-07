"""Tests for client-scoped conversation Message operations."""

import unittest

from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    MessageParentNotFoundError,
    MessageRepository,
    SessionRepository,
)


class MessageRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_append_orders_messages_and_enforces_client_scope(self) -> None:
        async with self.database.session() as database_session:
            agents = AgentRepository(database_session)
            personal = await agents.create(
                "client-a", name="Personal", system_prompt="Help client A."
            )
            outsider = await agents.create(
                "client-b", name="Personal", system_prompt="Help client B."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", personal.id
            )
            messages = MessageRepository(database_session)
            first = await messages.append(
                "client-a",
                conversation.id,
                personal.id,
                role="user",
                content="Hello",
            )
            second = await messages.append(
                "client-a",
                conversation.id,
                personal.id,
                role="assistant",
                content="Hi",
            )
            await database_session.commit()

            visible = await messages.list_messages("client-a", conversation.id)
            latest = await messages.list_messages(
                "client-a", conversation.id, limit=1
            )
            older = await messages.list_messages(
                "client-a",
                conversation.id,
                before_sequence=latest[0].sequence,
                limit=1,
            )
            hidden = await messages.list_messages("client-b", conversation.id)
            with self.assertRaises(MessageParentNotFoundError):
                await messages.append(
                    "client-a",
                    conversation.id,
                    outsider.id,
                    role="assistant",
                    content="Should not persist",
                )

        self.assertEqual([item.id for item in visible], [first.id, second.id])
        self.assertEqual([item.sequence for item in visible], [1, 2])
        self.assertEqual([item.id for item in latest], [second.id])
        self.assertEqual([item.id for item in older], [first.id])
        self.assertEqual(hidden, [])


if __name__ == "__main__":
    unittest.main()
