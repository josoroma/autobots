"""Backup seed and restored-instance checks, through the runtime role. No provider is involved. JSON cases."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.artifacts import read_artifact
from autobots.application.credentials.store import (
    CredentialStorageUnavailable,
    CredentialUnreadable,
    ProviderCredentialStore,
)
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.worker_leases import claim_next
from autobots.operations.job_dispatch import process_next
from goal_loop_script import ROUTE
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from pydantic import SecretStr

URL = os.environ['AUTOBOTS_DATABASE_URL']
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def seed(workspace: UUID, key_path: Path, value: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await ProviderCredentialStore(db, key_path).save(workspace, value)


def never() -> Any:
    raise AssertionError('a model was built under a restore hold')


async def verify(workspace: UUID, key_path: Path, manifest_path: Path, expected_sha: str, wrong_key: Path) -> None:
    manifest = json.loads(manifest_path.read_text())  # noqa: ASYNC240 - a test helper reading one small local file
    facts = manifest['facts']
    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        for name, sql in (('runs', 'public.runs'), ('events', 'public.run_events'), ('tool_receipts', 'app_private.tool_receipts'),
                          ('model_invocations', 'app_private.model_invocations'), ('checkpoints', 'agent_runtime.checkpoints')):
            count = await value(f'select count(*) from {sql}')
            check(f'restored {name} match the manifest', str(facts[name]), count, count == facts[name])

        artifacts = facts['artifacts']
        check('the backup holds artifacts to verify', 'at least one', len(artifacts), len(artifacts) >= 1)
        for artifact in artifacts:
            _, _, content = await read_artifact(db, store, UUID(artifact['workspace_id']), UUID(artifact['id']))
            digest = hashlib.sha256(content).hexdigest()
            check('a restored artifact downloads with its recorded hash', artifact['sha256'][:12], digest[:12], digest == artifact['sha256'] and len(content) == artifact['size_bytes'])

        resolved = await ProviderCredentialStore(db, key_path).load_active(workspace)
        decrypted = hashlib.sha256(resolved.client_secret().get_secret_value().encode()).hexdigest()
        check('the credential decrypts with the separately kept key, without showing it', 'the same fingerprint', decrypted == expected_sha, decrypted == expected_sha)
        # TDBC-07: only the store's own refusal counts. Anything else propagates and fails the check.
        # Judged by exact type, as a row it can't open is a subclass of a missing key (R-41, POPS-09).
        for label, path, refusal in (('a different key', wrong_key, CredentialUnreadable),
                                     ('no key', key_path.parent / 'absent.key', CredentialStorageUnavailable)):
            try:
                await ProviderCredentialStore(db, path).load_active(workspace)
                outcome = 'opened'
            except CredentialStorageUnavailable as error:
                outcome = type(error).__name__
            check(f'the database alone cannot open it: {label}', refusal.__name__, outcome, outcome == refusal.__name__)

        threads = facts['threads']
        check('the backup holds checkpoint history', 'at least one thread', len(threads), len(threads) >= 1)
        async with await psycopg.AsyncConnection.connect(URL, autocommit=True, prepare_threshold=0, row_factory=dict_row, options='-c search_path=agent_runtime') as saver_db:
            saver = AsyncPostgresSaver(saver_db)
            for thread in threads:
                config: Any = {'configurable': {'thread_id': thread['thread_id'], 'checkpoint_ns': ''}}
                latest = await saver.aget_tuple(config)
                history = [item async for item in saver.alist(config)]
                observed = latest.checkpoint['id'] if latest else None
                check('checkpoint history reads through the real saver', f"latest {thread['latest'][:18]}, {thread['count']} total", f'{str(observed)[:18]}, {len(history)}', observed == thread['latest'] and len(history) >= 1)

        # The hold, with the pending work a backup naturally holds.
        before = await value("select json_agg(json_build_object('run', run_id, 'status', status, 'attempts', attempts) order by run_id) from app_private.run_jobs")
        pending = await value("select count(*) from app_private.run_jobs where status = 'queued'")
        uncertain = await value("select count(*) from app_private.model_invocations where status = 'uncertain'")
        check('the restore holds pending and uncertain work', 'a queued job and an uncertain call', f'{pending}, {uncertain}', pending >= 1 and uncertain >= 1)
        lease = await claim_next(db, worker_id='restored-claim')
        check('a claim under the hold takes nothing', 'none', lease, lease is None)
        processed = await process_next(db, URL, 'restored-worker', never, LoopConfig(route=ROUTE))
        check('a worker pass under the hold builds no model', 'none', processed, processed is None)
        after = await value("select json_agg(json_build_object('run', run_id, 'status', status, 'attempts', attempts) order by run_id) from app_private.run_jobs")
        check('every job is unchanged', 'same', before == after, before == after)
        invocations = await value('select count(*) from app_private.model_invocations')
        check('no model call was added', str(facts['model_invocations']), invocations, invocations == facts['model_invocations'])
        try:
            await db.execute("delete from app_private.installation_holds")
            denied = 'released'
        except psycopg.errors.InsufficientPrivilege:
            denied = 'denied'
        check('the runtime role cannot release the hold', 'denied', denied, denied == 'denied')
    print(json.dumps({'cases': cases}))


if __name__ == '__main__':
    if sys.argv[1] == 'seed':
        asyncio.run(seed(UUID(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]))
    else:
        asyncio.run(verify(UUID(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5], Path(sys.argv[6])))
