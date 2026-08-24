"""Tests for Agent API contracts and shared FastAPI dependencies."""

import unittest

import httpx
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import text

from app.api.dependencies import ClientID, DBSession
from app.core.database import Database
from app.models import AgentRecord
from app.schemas.agent import AgentCreate, AgentRead


class AgentSchemaTest(unittest.TestCase):
    def test_create_normalizes_short_fields(self) -> None:
        data = AgentCreate(
            name="  Personal  ",
            system_prompt="Help with my work.",
            model="  demo-model  ",
        )

        self.assertEqual(data.name, "Personal")
        self.assertEqual(data.model, "demo-model")
        self.assertEqual(data.runtime, "native")

    def test_create_accepts_a_registered_runtime_name(self) -> None:
        data = AgentCreate(
            name="Worker",
            system_prompt="Handle coding tasks.",
            runtime="deepseek_harness",
        )

        self.assertEqual(data.runtime, "deepseek_harness")

    def test_blank_prompt_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AgentCreate(name="Personal", system_prompt="   ")

    def test_read_contract_accepts_orm_attributes(self) -> None:
        record = AgentRecord(
            id="agent-1",
            client_id="client-a",
            name="Personal",
            system_prompt="Help.",
            runtime="native",
            created_at="2026-08-24T00:00:00Z",
            updated_at="2026-08-24T00:00:00Z",
        )

        response = AgentRead.model_validate(record)

        self.assertEqual(response.runtime, "native")


class AgentDependencyTest(unittest.IsolatedAsyncioTestCase):
    async def test_header_scope_and_database_session_are_injected(self) -> None:
        app = FastAPI()
        database = Database("sqlite+aiosqlite:///:memory:")
        app.state.database = database

        @app.get("/dependency-test")
        async def dependency_test(client_id: ClientID, session: DBSession) -> dict:
            value = (await session.execute(text("SELECT 1"))).scalar_one()
            return {"client_id": client_id, "database": value}

        transport = httpx.ASGITransport(app=app)
        try:
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                missing = await client.get("/dependency-test")
                valid = await client.get(
                    "/dependency-test", headers={"X-Client-ID": " client-a "}
                )
        finally:
            await database.dispose()

        self.assertEqual(missing.status_code, 422)
        self.assertEqual(valid.json(), {"client_id": "client-a", "database": 1})


if __name__ == "__main__":
    unittest.main()
