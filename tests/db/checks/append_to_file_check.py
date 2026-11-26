"""US-22.1 and Decision 0040 P1 and P2 on a real database: append_to_file through the real gateway, receipts, lease and
path grants. JSON cases. It needs no model, no key and no network.
"""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.application import tool_gateway
from autobots.application.experts import create_expert, create_session, resolve_binding
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import LOOP_TOOL_GRANTS, PLAN_TOOLS
from checklib import QUIESCE, Cases, run_check, run_scenarios

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
GRANT = {**PLAN_TOOLS, 'append_to_file': 1, 'save_artifact': 1}


class Rig:
    def __init__(self, cases: Cases, db: Any) -> None:
        self.cases, self.db = cases, db
        self.gateway = ToolGateway(tool_registry.build_registry(None))

    async def versions(self, run: UUID, path: str) -> list[tuple[Any, ...]]:
        return await (await self.db.execute('select version, content, media_type from app_private.run_files where run_id = %s '
                                            'and path = %s order by version', (run, path))).fetchall()

    async def scope(self, paths: tuple[str, ...] = ('inputs', 'outputs')) -> ToolScope:
        await self.db.execute(QUIESCE)
        binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools=GRANT)
        run = (await admit_run(self.db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Add',
                               limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
        return await self.claim(run, paths)

    async def claim(self, run: UUID, paths: tuple[str, ...] = ('inputs', 'outputs')) -> ToolScope:
        lease = await claim_next(self.db, worker_id='append', lease_seconds=300)
        assert lease is not None and lease.run_id == run, lease
        await self.db.execute("update public.runs set status = 'running' where id = %s", (run,))
        return ToolScope(WORKSPACE, run, lease.generation, GRANT, paths)

    async def call(self, scope: ToolScope, name: str, connection: Any = None, **arguments: Any) -> Any:
        return await self.gateway.execute(connection or self.db, scope, name, arguments)


async def adds_to_the_end(rig: Rig) -> None:
    scope = await rig.scope()
    created = await rig.call(scope, 'append_to_file', path='outputs/new.md', content='# First\n\n')
    await rig.call(scope, 'save_artifact', path='outputs/plain.txt', content='x\n', media_type='text/plain')
    added = await rig.call(scope, 'append_to_file', path='outputs/plain.txt', content='y\n')
    rig.cases.check('a missing file is created as Markdown, and an add goes to the end of the latest version as a new one with its '
                    'media type', 'version 1 text/markdown; version 2 "x\\ny\\n" text/plain; the outputs name each',
                    (await rig.versions(scope.run_id, 'outputs/new.md'), await rig.versions(scope.run_id, 'outputs/plain.txt'),
                     created.output, added.output),
                    await rig.versions(scope.run_id, 'outputs/new.md') == [(1, '# First\n\n', 'text/markdown')]
                    and (await rig.versions(scope.run_id, 'outputs/plain.txt'))[-1] == (2, 'x\ny\n', 'text/plain')
                    and created.output['version'] == 1 and created.output['characters'] == 9
                    and added.output['version'] == 2 and added.output['characters'] == 4 and len(added.output['sha256']) == 64)
    child = await rig.scope(('inputs', 'outputs/child-1'))
    outside = await rig.call(child, 'append_to_file', path='outputs/elsewhere.md', content='x')
    inputs = await rig.call(child, 'append_to_file', path='inputs/notes.md', content='x')
    rig.cases.check('a path outside the run grants, or under inputs/, is refused and nothing is written',
                    'resource_not_granted, then invalid_arguments, and no file', (outside.code, inputs.code),
                    outside.code == 'resource_not_granted' and inputs.code == 'invalid_arguments'
                    and await rig.versions(child.run_id, 'outputs/elsewhere.md') == [])


async def never_loses_one(rig: Rig) -> None:
    scope = await rig.scope()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as one, \
            await psycopg.AsyncConnection.connect(URL, autocommit=True) as two:
        results = await asyncio.gather(*(rig.call(scope, 'append_to_file', connection, path='outputs/both.md', content=f'{name}\n')
                                         for connection, name in ((one, 'one'), (two, 'two'), (rig.db, 'three'))))
    found = await rig.versions(scope.run_id, 'outputs/both.md')
    rig.cases.check('three adds to one file at once never lose one', 'versions 1 to 3, the last holding all three once each',
                    ([r.outcome.value for r in results], [(v, c) for v, c, _ in found]),
                    all(r.outcome.value == 'succeeded' for r in results) and [v for v, _, _ in found] == [1, 2, 3]
                    and sorted(found[-1][1].splitlines()) == ['one', 'three', 'two'])


async def too_large(rig: Rig) -> None:
    scope = await rig.scope()
    await rig.call(scope, 'save_artifact', path='outputs/big.md', content='y' * 255_995)
    refused = await rig.call(scope, 'append_to_file', path='outputs/big.md', content='x' * 10)
    rig.cases.check('an add past 256,000 characters is refused file_too_large and nothing changes', 'file_too_large, still version 1',
                    (refused.code, [v for v, _, _ in await rig.versions(scope.run_id, 'outputs/big.md')]),
                    refused.code == 'file_too_large' and [v for v, _, _ in await rig.versions(scope.run_id, 'outputs/big.md')] == [1])


async def read_back(rig: Rig) -> None:
    scope = await rig.scope()
    succeeded = tool_gateway._succeeded

    async def crash(*_: Any, **__: Any) -> Any:
        raise ConnectionError('the worker stopped before the receipt was recorded')

    tool_gateway._succeeded = crash  # type: ignore[assignment]  # an arranged crash after the add committed
    try:
        await rig.call(scope, 'append_to_file', path='outputs/once.md', content='section\n')
        crashed = 'returned'
    except ConnectionError:
        crashed = 'crashed'
    finally:
        tool_gateway._succeeded = succeeded
    await rig.db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' "
                         'where run_id = %s', (scope.run_id,))
    scope = await rig.claim(scope.run_id)
    again = await rig.call(scope, 'append_to_file', path='outputs/once.md', content='section\n')
    twice = await rig.call(scope, 'append_to_file', path='outputs/once.md', content='section\n')
    found = await rig.versions(scope.run_id, 'outputs/once.md')
    rig.cases.check('an add interrupted after its write is read back by the next attempt, and the same content twice is added once',
                    'crashed; then succeeded twice by readback and replay, and one version holding the section once',
                    (crashed, again.outcome.value, again.replayed, twice.replayed, found),
                    crashed == 'crashed' and again.outcome.value == 'succeeded' and again.replayed and twice.replayed
                    and found == [(1, 'section\n', 'text/markdown')] and again.output['version'] == 1)


async def expert_only(rig: Rig) -> None:
    made = await create_expert(rig.db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()),
                               name=f'Writer {uuid4().hex[:6]}', catalog=tool_registry.catalog(),
                               config=ExpertConfig(tools=['append_to_file']))
    session = await create_session(rig.db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), kind='direct',
                                   experts=[SessionExpert(expert_id=made.id)])
    binding = await resolve_binding(rig.db, WORKSPACE, session.id)
    plain = await rig.scope()
    refused = await rig.gateway.execute(rig.db, ToolScope(WORKSPACE, plain.run_id, plain.generation, dict(LOOP_TOOL_GRANTS),
                                                          ('outputs',)), 'append_to_file', {'path': 'outputs/a.md', 'content': 'x'})
    listed = next(item for item in tool_registry.catalog().descriptors({}) if item.tool_id == 'append_to_file')
    rig.cases.check("only an Expert grants it: the catalog lists it in Files for Experts only, an Expert's run gets version 1, "
                    "and a plain goal's call is refused",
                    'files, version 1, grantable to expert only; version 1 in the binding; tool_not_granted for a plain run',
                    (listed.group, listed.version, listed.grantable_to, binding.tools.get('append_to_file'), refused.code),
                    listed.group == 'files' and listed.version == 1 and listed.grantable_to == ['expert']
                    and binding.tools.get('append_to_file') == 1 and 'append_to_file' not in LOOP_TOOL_GRANTS
                    and refused.code == 'tool_not_granted' and await rig.versions(plain.run_id, 'outputs/a.md') == [])


SCENARIOS = (adds_to_the_end, never_loses_one, too_large, read_back, expert_only)


async def main(cases: Cases) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await run_scenarios(cases, SCENARIOS, Rig(cases, db))


if __name__ == '__main__':
    run_check(main, parent_timeout=180)
