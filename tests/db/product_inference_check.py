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
from autobots.application.provider_settings import KeyCheck, ProviderSettings
from autobots.application.runs import admit_run, apply_command
from autobots.application.worker_leases import claim_run
from autobots.contracts.plans import RequiredArtifact
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


COMMANDS = {'admit': admit, 'save-key': save_key, 'artifact': artifact, 'strand': strand}

if __name__ == '__main__':
    asyncio.run(COMMANDS[sys.argv[1]](*sys.argv[2:]))
