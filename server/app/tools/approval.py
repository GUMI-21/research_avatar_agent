"""In-process approval rendezvous for side-effecting tools."""

import asyncio
from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class PendingApproval:
    id: str
    decision: asyncio.Future[bool]


class ToolApprovalBroker:
    def __init__(self) -> None:
        self._pending: dict[str, tuple[str, str, asyncio.Future[bool]]] = {}

    def create(self, client_id: str, run_id: str) -> PendingApproval:
        approval_id = str(uuid4())
        decision = asyncio.get_running_loop().create_future()
        self._pending[approval_id] = (client_id, run_id, decision)
        return PendingApproval(approval_id, decision)

    def decide(
        self, client_id: str, run_id: str, approval_id: str, approved: bool
    ) -> bool:
        pending = self._pending.get(approval_id)
        if pending is None or pending[:2] != (client_id, run_id):
            return False
        self._pending.pop(approval_id)
        if not pending[2].done():
            pending[2].set_result(approved)
        return True

    def discard(self, approval_id: str) -> None:
        self._pending.pop(approval_id, None)
