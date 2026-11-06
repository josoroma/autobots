"""What the worker inference qualification arranges or reads back, in the app's own code and runtime role."""
from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
from pydantic import SecretStr

from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.api.main import provider_context_from_environment
from autobots.application.artifacts import read_artifact
from autobots.application.experts import create_expert, create_session, resolve_binding
from autobots.application.provider_settings import KeyCheck, ProviderSettings
from autobots.application.runs import admit_run, apply_command
from autobots.application.worker_leases import claim_run
from autobots.application.workflows import create_execution, create_workflow, publish_version
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.contracts.plans import RequiredArtifact
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']


async def admit(workspace: str, tag: str, profile: str) -> None:
    """Directly, for what the API refuses to admit: a workspace with no key, or an explicit profile."""
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        accepted = await admit_run(db, workspace_id=UUID(workspace), actor_id=uuid4(), idempotency_key=str(uuid4()),
                                   goal_text=f'Write the report [{tag}]', limit_micro_usd=1_000_000,
                                   required_artifacts=(RequiredArtifact(name='report.md', must_contain=['Total: 42']),),
                                   policy=resolve_role_policy(run_profile=profile))
        print(accepted.run_id)


async def workflow(workspace: str) -> None:
    """A published workflow with no model step, to show the product worker runs workflows at all."""
    graph = {
        'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}}, {'id': 'up', 'block': 'transform', 'version': 1, 'config': {'operation': 'upper'}}, {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
        'links': [{'source': 'in', 'source_port': 'value', 'target': 'up', 'target_port': 'value'}, {'source': 'up', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}],
    }
    actor = uuid4()
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        flow = await create_workflow(db, workspace_id=UUID(workspace), actor_id=actor, idempotency_key=str(uuid4()), name=f'Worker {uuid4().hex[:6]}')
        await publish_version(db, workspace_id=UUID(workspace), actor_id=actor, workflow_id=flow.id, idempotency_key=str(uuid4()), expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')
        bound = await create_execution(db, workspace_id=UUID(workspace), actor_id=actor, workflow_id=flow.id, idempotency_key=str(uuid4()), version=1, inputs={'in': 'x'})
        print(bound.run_id)


async def admit_lead(workspace: str) -> None:
    """A run that can delegate, naming its Expert in the goal for the fake provider to read."""
    tools = ['calculate', 'save_artifact', 'publish_artifact']
    place, actor = UUID(workspace), uuid4()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        lead = await create_expert(db, workspace_id=place, actor_id=actor, idempotency_key=str(uuid4()), name='Worker lead', config=ExpertConfig(tools=tools))
        helper = await create_expert(db, workspace_id=place, actor_id=actor, idempotency_key=str(uuid4()), name='Worker helper', config=ExpertConfig(tools=tools, instructions='Help.'))
        session = await create_session(db, workspace_id=place, actor_id=actor, idempotency_key=str(uuid4()), kind='coordinator', experts=[SessionExpert(expert_id=item.id) for item in (lead, helper)])
        binding = await resolve_binding(db, place, session.id, expert_id=lead.id)
        accepted = await admit_run(db, workspace_id=place, actor_id=actor, idempotency_key=str(uuid4()),
                                   goal_text=f'Lead the work [parent] expert={helper.id}', limit_micro_usd=1_000_000,
                                   policy=resolve_role_policy(), binding=binding)
        print(accepted.run_id)


async def save_key(workspace: str) -> None:
    """The real save path. Only OpenRouter's key check is arranged, since this stack never reaches it."""
    async def accepted(_: SecretStr) -> KeyCheck:
        return KeyCheck.VALID

    context = provider_context_from_environment()
    assert context is not None
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        settings = ProviderSettings(db, replace(context, validate_key=accepted))
        status = await settings.status(UUID(workspace))
        await settings.save_credential(UUID(workspace), os.environ['AUTOBOTS_TEST_KEY'], status.settings_version)


async def artifact(workspace: str, run: str) -> None:
    """Read back through the app's own path, which checks the bytes against the recorded hash."""
    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        cursor = await db.execute("select id from public.artifacts where run_id = %s and status = 'published' order by created_at desc limit 1", (run,))
        row = await cursor.fetchone()
        assert row is not None, 'no published artifact'
        name, _, content = await read_artifact(db, store, UUID(workspace), row[0])
        sys.stdout.write(f'{name}\n{content.decode()}')


async def strand(workspace: str, run: str, state: str) -> None:
    """Arranged: a worker that claimed this run and died, leaving it cancelling or awaiting verification."""
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        lease = await claim_run(db, UUID(run), worker_id='gone', lease_seconds=1)
        assert lease is not None, 'the run could not be claimed'
        version = (await (await db.execute('select version from public.runs where id = %s', (run,))).fetchone())[0]
        if state == 'cancel':
            await apply_command(db, workspace_id=UUID(workspace), run_id=UUID(run), command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        else:
            await apply_command(db, workspace_id=UUID(workspace), run_id=UUID(run), command=RunCommand.VERIFY, actor=Actor.WORKER, expected_version=version, generation=lease.generation)


COMMANDS = {'workflow': workflow, 'admit': admit, 'admit-lead': admit_lead, 'save-key': save_key, 'artifact': artifact, 'strand': strand}

if __name__ == '__main__':
    asyncio.run(COMMANDS[sys.argv[1]](*sys.argv[2:]))
