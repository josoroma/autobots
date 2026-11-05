"""What a query returns. A row is never a public response; adapters convert it explicitly."""

from datetime import datetime
from typing import TypedDict
from uuid import UUID


class RunRow(TypedDict):
    id: UUID
    workspace_id: UUID
    parent_run_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    spent_micro_usd: int
    reserved_micro_usd: int
    limit_micro_usd: int
    lease_generation: int
    checkpoint_thread_id: str | None
    version: int
