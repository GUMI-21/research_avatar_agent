"""Teaching bindings are scoped, unique, transactional and separate from chat history."""

import unittest

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, Database
from app.models import SessionRecord, TeachingSessionRecord
from app.repositories import (
    AgentRepository,
    SessionRepository,
    TeachingRepository,
    TeachingSessionNotFoundError,
)
from app.schemas.teaching import CourseSelection


class TeachingRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            await connection.run_sync(Base.metadata.create_all)
        async with self.database.session() as session:
            agent = await AgentRepository(session).create(
                "client-a", name="Teacher", system_prompt="Teach kana in English."
            )
            conversation = await SessionRepository(session).create("client-a", agent.id)
            self.session_id = conversation.id
            await session.commit()

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def _bind(self, session: AsyncSession) -> TeachingSessionRecord:
        return await TeachingRepository(session).create(
            "client-a", self.session_id,
            selection=CourseSelection(), course_version="a" * 64,
        )

    async def test_persists_selection_version_defaults_and_scope(self) -> None:
        async with self.database.session() as session:
            record = await self._bind(session)
            self.assertEqual(record.completed_turns, 0)
            self.assertEqual(record.state_version, 1)
            self.assertIsNotNone(record.created_at)
            self.assertIsNotNone(record.updated_at)
            await session.commit()

        async with self.database.session() as session:
            repository = TeachingRepository(session)
            record = await repository.get("client-a", self.session_id)
            self.assertIsNotNone(record)
            self.assertEqual(record.course_id, "gojuon-en")
            self.assertEqual(record.lesson_id, "hiragana-vowels")
            self.assertEqual(record.course_version, "a" * 64)
            self.assertIsNone(await repository.get("client-b", self.session_id))
            self.assertIsNone(await repository.get("client-a", "missing"))

    async def test_missing_and_cross_client_parents_are_rejected(self) -> None:
        async with self.database.session() as session:
            repository = TeachingRepository(session)
            for client_id, session_id in (
                ("client-b", self.session_id), ("client-a", "missing"),
            ):
                with self.subTest(client_id=client_id, session_id=session_id):
                    with self.assertRaisesRegex(TeachingSessionNotFoundError, "Session not found"):
                        await repository.create(
                            client_id, session_id,
                            selection=CourseSelection(), course_version="a" * 64,
                        )
            self.assertIsNone(await repository.get("client-a", self.session_id))

    async def test_one_binding_per_conversation(self) -> None:
        async with self.database.session() as session:
            await self._bind(session)
            await session.commit()
        async with self.database.session() as session:
            with self.assertRaises(IntegrityError):
                await self._bind(session)
            await session.rollback()
            record = await TeachingRepository(session).get("client-a", self.session_id)
            self.assertEqual(record.course_version, "a" * 64)

    async def test_repository_does_not_commit(self) -> None:
        async with self.database.session() as session:
            await self._bind(session)
            await session.rollback()
        async with self.database.session() as session:
            self.assertIsNone(await TeachingRepository(session).get("client-a", self.session_id))
            self.assertIsNotNone(await SessionRepository(session).get("client-a", self.session_id))

    async def test_progress_constraints(self) -> None:
        for invalid in ({"completed_turns": -1}, {"state_version": 0}):
            with self.subTest(invalid=invalid):
                async with self.database.session() as session:
                    record = await self._bind(session)
                    for name, value in invalid.items():
                        setattr(record, name, value)
                    with self.assertRaises(IntegrityError):
                        await session.flush()
                    await session.rollback()

    async def test_foreign_key_and_session_deletion(self) -> None:
        async with self.database.session() as session:
            session.add(TeachingSessionRecord(
                session_id="missing", client_id="client-a", course_id="gojuon-en",
                lesson_id="hiragana-vowels", course_version="a" * 64,
            ))
            with self.assertRaises(IntegrityError):
                await session.flush()
            await session.rollback()
            await self._bind(session)
            await session.commit()
            await session.execute(delete(SessionRecord).where(SessionRecord.id == self.session_id))
            await session.commit()
            self.assertIsNone(await TeachingRepository(session).get("client-a", self.session_id))
