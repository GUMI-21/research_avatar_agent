"""Upgrade an existing workspace without modifying its conversations."""

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from app.models import AgentRecord, SessionRecord, TeachingSessionRecord


class TeachingMigrationTest(unittest.TestCase):
    def test_upgrade_defaults_metadata_and_downgrade_preserve_conversations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "teaching.db"
            server = Path(__file__).resolve().parents[1]
            config = Config(str(server / "alembic.ini"))
            config.set_main_option("script_location", str(server / "migrations"))
            config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{path}")
            command.upgrade(config, "20260919_20")
            engine = create_engine(f"sqlite:///{path}")
            try:
                with engine.begin() as connection:
                    connection.execute(AgentRecord.__table__.insert().values(
                        id="teacher", client_id="client-a", name="Teacher", system_prompt="Teach."
                    ))
                    connection.execute(SessionRecord.__table__.insert().values(
                        id="conversation", client_id="client-a", agent_id="teacher"
                    ))
                command.upgrade(config, "head")
                command.check(config)
                inspector = inspect(engine)
                self.assertEqual(
                    inspector.get_pk_constraint("teaching_session_states")["constrained_columns"],
                    ["session_id"],
                )
                with engine.begin() as connection:
                    # Raw SQL verifies database defaults, not just Python ORM defaults.
                    connection.exec_driver_sql(
                        "INSERT INTO teaching_session_states "
                        "(session_id,client_id,course_id,lesson_id,course_version,created_at,updated_at) "
                        "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                        ("conversation", "client-a", "gojuon-en", "hiragana-vowels", "a" * 64),
                    )
                    row = connection.execute(select(TeachingSessionRecord.__table__)).mappings().one()
                    self.assertEqual(row["completed_turns"], 0)
                    self.assertEqual(row["state_version"], 1)
                command.downgrade(config, "20260919_20")
                self.assertNotIn("teaching_session_states", inspect(engine).get_table_names())
                with engine.connect() as connection:
                    self.assertEqual(connection.execute(select(SessionRecord.id)).scalar_one(), "conversation")
                command.upgrade(config, "head")
                command.check(config)
            finally:
                engine.dispose()
