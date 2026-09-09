"""End-to-end tests for native runtime keyword RAG execution."""

import asyncio
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.adapters.agent import NativeAgentRuntime, RuntimeEventType
from app.adapters.llm import LLMClient, LLMRequest, LLMResult
from app.core.database import Database
from app.repositories import AgentRepository, SessionRepository
from app.schemas.llm import LLMProvider
from app.services import KnowledgeSourceService, RunEventService, RunExecutionService
from app.services.runtime_registry import RuntimeRegistry


class RecordingLLMClient(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        return LLMResult("answer", LLMProvider.MOCK, "mock-echo")


class NativeKnowledgeRunTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_fts_rag_reaches_native_llm_with_isolation_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database_path = root / "rag.db"
            database_url = f"sqlite+aiosqlite:///{database_path}"
            config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            await asyncio.to_thread(command.upgrade, config, "head")
            bound_root = root / "bound"
            second_bound_root = root / "second-bound"
            unbound_root = root / "unbound"
            foreign_root = root / "foreign"
            for note_root, marker in (
                (bound_root, "BOUND"),
                (second_bound_root, "SECOND"),
                (unbound_root, "UNBOUND"),
                (foreign_root, "FOREIGN"),
            ):
                note_root.mkdir()
                sections = "\n\n".join(
                    f"## Section {index}\n目标知识 {marker} " + ("绑定资料。" * 180)
                    for index in range(6 if marker in {"BOUND", "SECOND"} else 1)
                )
                (note_root / "note.md").write_text(sections, encoding="utf-8")

            database = Database(database_url)
            llm = RecordingLLMClient()
            try:
                async with database.session() as session:
                    sources = KnowledgeSourceService(session)
                    bound = await sources.create(
                        "client-a", name="bound", root_path=str(bound_root)
                    )
                    second_bound = await sources.create(
                        "client-a",
                        name="second-bound",
                        root_path=str(second_bound_root),
                    )
                    unbound = await sources.create(
                        "client-a", name="unbound", root_path=str(unbound_root)
                    )
                    foreign = await sources.create(
                        "client-b", name="foreign", root_path=str(foreign_root)
                    )
                    await sources.sync("client-a", bound.id)
                    await sources.sync("client-a", second_bound.id)
                    await sources.sync("client-a", unbound.id)
                    await sources.sync("client-b", foreign.id)
                    agent = await AgentRepository(session).create(
                        "client-a",
                        name="Personal",
                        system_prompt="Use cited notes.",
                        knowledge_sources=[second_bound, bound],
                    )
                    conversation = await SessionRepository(session).create(
                        "client-a", agent.id
                    )
                    await session.commit()
                    registry = RuntimeRegistry()
                    registry.register("native", lambda: NativeAgentRuntime(llm))
                    service = RunExecutionService(session, registry)
                    streamed = [
                        item
                        async for item in service.stream(
                            "client-a", conversation.id, "目标知识"
                        )
                    ]

                request = llm.requests[-1]
                self.assertEqual(request.instructions, "Use cited notes.")
                self.assertIn("BOUND", request.message)
                self.assertNotIn("UNBOUND", request.message)
                self.assertNotIn("FOREIGN", request.message)
                context = request.message.split("\n\n用户问题:\n", 1)[0]
                self.assertLessEqual(len(context), 6000)
                retrieval = [
                    item
                    for item in streamed
                    if item.event.type is RuntimeEventType.RETRIEVAL_RESULT
                ]
                self.assertEqual(len(retrieval), 2)
                self.assertEqual(
                    [item.event.payload["source_id"] for item in retrieval],
                    sorted((bound.id, second_bound.id)),
                )
                self.assertTrue(
                    all(item.event.payload["hit_count"] == 5 for item in retrieval)
                )
                self.assertEqual(
                    [item.event.type for item in streamed].count(
                        RuntimeEventType.RUN_STARTED
                    ),
                    1,
                )
                prepared = [
                    item for item in streamed
                    if item.event.type is RuntimeEventType.CONTEXT_PREPARED
                ]
                self.assertEqual(len(prepared), 1)
                audit = prepared[0].event.payload
                candidate_ids = [
                    chunk_id for item in retrieval
                    for chunk_id in item.event.payload["chunk_ids"]
                ]
                included_ids = audit["included_chunk_ids"]
                self.assertGreater(len(included_ids), 0)
                self.assertLess(len(included_ids), len(candidate_ids))
                self.assertEqual(included_ids, candidate_ids[:len(included_ids)])
                self.assertEqual(len(included_ids), context.count("[来源 "))
                self.assertEqual(audit["used_chars"], len(context))
                self.assertEqual(audit["budget_chars"], 6000)
                self.assertTrue(audit["truncated"])
                self.assertEqual(
                    audit["context_sha256"], sha256(context.encode("utf-8")).hexdigest()
                )
                self.assertEqual(set(audit), {
                    "included_chunk_ids", "used_chars", "budget_chars",
                    "truncated", "context_sha256",
                })
                self.assertLess(streamed.index(retrieval[-1]), streamed.index(prepared[0]))
                agent_started = next(
                    item for item in streamed
                    if item.event.type is RuntimeEventType.AGENT_STARTED
                )
                self.assertLess(streamed.index(prepared[0]), streamed.index(agent_started))

                no_context_agent = await AgentRepository(session).create(
                    "client-a", name="NoContext", system_prompt="Plain."
                )
                no_context_session = await SessionRepository(session).create(
                    "client-a", no_context_agent.id
                )
                zero_hit_agent = await AgentRepository(session).create(
                    "client-a",
                    name="ZeroHit",
                    system_prompt="Plain.",
                    knowledge_sources=[bound],
                )
                zero_hit_session = await SessionRepository(session).create(
                    "client-a", zero_hit_agent.id
                )
                await session.commit()
                plain_events = [
                    item
                    async for item in RunExecutionService(session, registry).stream(
                        "client-a", no_context_session.id, "没有绑定源"
                    )
                ]
                self.assertEqual(llm.requests[-1].message, "没有绑定源")
                self.assertFalse(any(
                    item.event.type is RuntimeEventType.CONTEXT_PREPARED
                    for item in plain_events
                ))
                empty_events = [
                    item
                    async for item in RunExecutionService(session, registry).stream(
                        "client-a", zero_hit_session.id, "完全不存在的词"
                    )
                ]
                self.assertEqual(llm.requests[-1].message, "完全不存在的词")
                empty_audit = next(
                    item.event.payload for item in empty_events
                    if item.event.type is RuntimeEventType.CONTEXT_PREPARED
                )
                self.assertEqual(empty_audit, {
                    "included_chunk_ids": [], "used_chars": 0,
                    "budget_chars": 6000, "truncated": False,
                    "context_sha256": sha256(b"").hexdigest(),
                })

                # 重建索引后旧事件仍保留当次准备的元数据，而不是重算当前笔记。
                for source, note_root in ((bound, bound_root), (second_bound, second_bound_root)):
                    (note_root / "note.md").write_text("# 更新\n新的笔记。", encoding="utf-8")
                    await sources.sync("client-a", source.id)
                async with database.session() as reader:
                    events = RunEventService(reader)
                    replayed = await events.replay("client-a", prepared[0].run_id)
                    persisted = next(
                        item for item in replayed if item.event_type == "context_prepared"
                    )
                    self.assertEqual(persisted.payload, audit)
                    self.assertEqual(persisted.sequence, prepared[0].sequence)
                    self.assertEqual(await events.replay("client-b", prepared[0].run_id), [])
            finally:
                await database.dispose()


if __name__ == "__main__":
    unittest.main()
