"""Tests for client-scoped Agent persistence operations."""

import unittest

from app.core.database import Base, Database
from app.repositories import AgentRepository


class AgentRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_queries_are_scoped_by_client(self) -> None:
        async with self.database.session() as session:
            repository = AgentRepository(session)
            first = await repository.create(
                "client-a",
                name="Personal",
                system_prompt="Help client A.",
            )
            await repository.create(
                "client-b",
                name="Personal",
                system_prompt="Help client B.",
            )
            await session.commit()

            client_agents = await repository.list_agents("client-a")
            visible = await repository.get("client-a", first.id)
            hidden = await repository.get("client-b", first.id)

        self.assertEqual([agent.id for agent in client_agents], [first.id])
        self.assertEqual(visible, first)
        self.assertIsNone(hidden)

    async def test_create_flushes_defaults_without_committing(self) -> None:
        async with self.database.session() as session:
            repository = AgentRepository(session)
            agent = await repository.create(
                "client-a",
                name="Coder",
                system_prompt="Implement scoped tasks.",
            )

            self.assertIsNotNone(agent.id)
            self.assertEqual(agent.runtime, "native")
            self.assertTrue(session.in_transaction())


if __name__ == "__main__":
    unittest.main()
