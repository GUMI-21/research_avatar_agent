"""Tests for the application database lifecycle."""

import unittest

from sqlalchemy import text

from app.core.database import Database


class DatabaseTest(unittest.IsolatedAsyncioTestCase):
    # session都是异步口
    async def test_session_executes_and_engine_disposes(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")

        async with database.session() as session:
            result = await session.execute(text("SELECT 1"))
            self.assertEqual(result.scalar_one(), 1)
        # 等待异步方法dispose结束
        await database.dispose()


if __name__ == "__main__":
    unittest.main()
