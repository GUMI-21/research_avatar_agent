"""Business rules for creating client-scoped Agent configurations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRecord
from app.repositories import AgentRepository, KnowledgeSourceRepository


class AgentKnowledgeSourceNotFoundError(LookupError):
    pass


class AgentService:
    def __init__(self, session: AsyncSession) -> None:
        self._agents = AgentRepository(session)
        self._sources = KnowledgeSourceRepository(session)

    async def create(
        self,
        client_id: str,
        *,
        name: str,
        system_prompt: str,
        avatar_emoji: str = "🤖",
        runtime: str = "native",
        provider: str | None = None,
        model: str | None = None,
        knowledge_source_ids: list[str] | None = None,
    ) -> AgentRecord:
        requested_ids = knowledge_source_ids or []
        sources = await self._sources.list_by_ids(client_id, requested_ids)
        sources_by_id = {source.id: source for source in sources}
        missing_ids = [item for item in requested_ids if item not in sources_by_id]
        if missing_ids:
            raise AgentKnowledgeSourceNotFoundError(missing_ids[0])
        return await self._agents.create(
            client_id,
            name=name,
            system_prompt=system_prompt,
            avatar_emoji=avatar_emoji,
            runtime=runtime,
            provider=provider,
            model=model,
            knowledge_sources=[sources_by_id[item] for item in requested_ids],
        )
