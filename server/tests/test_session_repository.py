"""Tests for client-scoped conversation Session operations."""

import unittest

from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    SessionAgentNotFoundError,
    SessionRepository,
)


class SessionRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_queries_and_agent_reference_are_client_scoped(self) -> None:
        async with self.database.session() as database_session:
            agents = AgentRepository(database_session)
            personal = await agents.create(
                "client-a",
                name="Personal",
                system_prompt="Help client A.",
            )
            sessions = SessionRepository(database_session)
            conversation = await sessions.create("client-a", personal.id)
            await database_session.commit()

            visible_list = await sessions.list_sessions("client-a")
            hidden_list = await sessions.list_sessions("client-b")
            visible = await sessions.get("client-a", conversation.id)
            hidden = await sessions.get("client-b", conversation.id)

            with self.assertRaises(SessionAgentNotFoundError):
                await sessions.create("client-b", personal.id)

        self.assertEqual([item.id for item in visible_list], [conversation.id])
        self.assertEqual(hidden_list, [])
        self.assertEqual(visible, conversation)
        self.assertIsNone(hidden)


if __name__ == "__main__":
    unittest.main()
