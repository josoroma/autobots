"""Admits a task granted the GitHub connector, as an owner's Expert would. Prints the run ID."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg

from autobots.application.runs import admit_run
from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import EXPERT_TOOLS, LOOP_TOOL_GRANTS


async def admit(workspace: str, limit: int, task: dict) -> None:
    binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools={**LOOP_TOOL_GRANTS, 'create_github_issue': EXPERT_TOOLS['create_github_issue']})
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        accepted = await admit_run(db, workspace_id=UUID(workspace), actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text=task['goal'], limit_micro_usd=limit,
                                   required_artifacts=(RequiredArtifact(name=task['artifact']),),
                                   input_documents=tuple(InputDocument(path=path, content=content) for path, content in task['documents'].items()),
                                   policy=resolve_role_policy(), binding=binding)
        print(accepted.run_id)


asyncio.run(admit(sys.argv[1], int(sys.argv[2]), json.loads(sys.argv[3])))
