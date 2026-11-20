"""US-17.4 and Decision 0035 Y11 on a real database: a browse's steps, recorded against their tool-use row, read by the
run's own workspace only, with each screenshot checked against its digest. JSON cases.

No browser or model is involved: a recording read tool stands in for browse_goal at the gateway, so the dispatch's
tool-use id reaches the handler as a browse's steps need it. The object store is in memory; the run workspace's
browser suite reads real screenshots through the API (tests/db/checks/tool_use_view_check.py arranges them).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.object_storage import _scoped
from autobots.application.browse_steps import (
    StepUnavailable,
    list_steps,
    read_screenshot,
    record_step,
    screenshot_path,
)
from autobots.application.run_usage import ensure_usage
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import (
    ToolContext,
    ToolDefinition,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import OperationClass
from pydantic import BaseModel, ConfigDict

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:900], 'passed': bool(passed)})


class Store:
    """The run's private storage, in memory."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        _scoped(path)  # the real store's rule: one name below the workspace and run
        self.objects[path] = content
        return True

    async def get(self, path: str) -> bytes | None:
        return self.objects.get(path)

    async def remove(self, path: str) -> None:
        self.objects.pop(path, None)

    async def names(self, prefix: str) -> list[str]:
        return [name for name in self.objects if name.startswith(prefix)]


class Nothing(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Done(BaseModel):
    steps: int


async def main() -> None:
    store = Store()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Browse',
                                   limit_micro_usd=1000, policy=resolve_role_policy())
        lease = await claim_next(db, worker_id='browse-steps', lease_seconds=300)
        assert lease is not None and lease.run_id == admitted.run_id
        await db.execute("update public.runs set status = 'running' where id = %s", (lease.run_id,))
        await ensure_usage(db, lease.run_id)
        scope = ToolScope(WORKSPACE, lease.run_id, lease.generation, {'recorded_browse': 1})
        handed: list[int | None] = []

        async def browse(args: Nothing, context: ToolContext) -> Done:
            # What browse_goal's step sink does for each browser-use step.
            handed.append(context.use_id)
            assert context.use_id is not None
            for step, (page, submits, image) in enumerate(
                    [('https://example.com/?q=secret', (), b'first'), ('https://example.com/search', ('example.com/search',), b'second')],
                    start=1):
                path = screenshot_path(scope, context.use_id, step)
                await store.put(path, image, 'image/jpeg')
                await record_step(db, scope, context.use_id, step, page=page, submits=submits, screenshot=(path, image))
            await record_step(db, scope, context.use_id, 3, page=None, submits=(), screenshot=None)
            return Done(steps=3)

        tool = ToolDefinition(tool_id='recorded_browse', version=1, title='Recorded browse', description='Records steps.',
                              input_model=Nothing, output_model=Done, operation_class=OperationClass.READ_ONLY, handler=browse,
                              timeout_seconds=10.0)
        registry = ToolRegistry()
        registry.register(tool)
        result = await ToolGateway(registry).execute(db, scope, 'recorded_browse', {})
        use_id = (await (await db.execute("select id from app_private.tool_uses where run_id = %s and tool_id = 'recorded_browse'",
                                          (lease.run_id,))).fetchone())[0]
        check("the gateway hands a read its tool-use row's id, and each step is recorded against that row",
              'succeeded, the handler saw the row id, 3 rows for it', (result.outcome.value, handed, use_id),
              result.outcome.value == 'succeeded' and handed == [use_id])

        steps = await list_steps(db, WORKSPACE, lease.run_id, use_id)
        listed = [(s.step, s.page, s.submits, s.screenshot) for s in steps]
        check('a step keeps its page and submits as host and path only, in order, and says whether a screenshot was kept',
              "[(1, 'example.com/', [], True), (2, 'example.com/search', ['example.com/search'], True), (3, None, [], False)]",
              listed, listed == [(1, 'example.com/', [], True), (2, 'example.com/search', ['example.com/search'], True), (3, None, [], False)]
              and 'secret' not in json.dumps(listed))

        first = await read_screenshot(db, store, WORKSPACE, lease.run_id, use_id, 1)
        check("a member reads a step's screenshot by its run, use and step", "b'first'", first, first == b'first')

        refusals = []
        other = uuid4()
        await db.execute("insert into public.workspaces (id, name) values (%s, 'Another workspace')", (other,))
        for label, arguments in (('another workspace', (other, lease.run_id, use_id, 1)), ('another run', (WORKSPACE, uuid4(), use_id, 1)),
                                 ('a step with no screenshot', (WORKSPACE, lease.run_id, use_id, 3)),
                                 ('no such step', (WORKSPACE, lease.run_id, use_id, 9))):
            try:
                await read_screenshot(db, store, *arguments)
                refusals.append((label, 'read'))
            except StepUnavailable as refused:
                refusals.append((label, refused.code))
        store.objects[screenshot_path(scope, use_id, 2)] = b'altered'
        try:
            await read_screenshot(db, store, WORKSPACE, lease.run_id, use_id, 2)
            refusals.append(('an altered object', 'read'))
        except StepUnavailable as refused:
            refusals.append(('an altered object', refused.code))
        foreign = await list_steps(db, other, lease.run_id, use_id)
        check("another workspace, run or step reads nothing, and an altered screenshot never leaves",
              'browse_step_not_found for each, browse_step_missing when altered, and an empty list for another workspace',
              (refusals, foreign),
              refusals == [('another workspace', 'browse_step_not_found'), ('another run', 'browse_step_not_found'),
                           ('a step with no screenshot', 'browse_step_not_found'), ('no such step', 'browse_step_not_found'),
                           ('an altered object', 'browse_step_missing')] and foreign == [])

        grants = await (await db.execute(
            "select grantee, string_agg(privilege_type, ',' order by privilege_type) from information_schema.role_table_grants "
            "where table_schema = 'app_private' and table_name = 'browse_steps' group by grantee order by grantee")).fetchall()
        check('the steps table is private: only the runtime role reads and writes it, and no browser role',
              "[('autobots_runtime', 'INSERT,SELECT')] beside the owner", grants,
              ('autobots_runtime', 'INSERT,SELECT') in grants
              and not any(grantee in ('anon', 'authenticated', 'public', 'PUBLIC') for grantee, _ in grants))
    print(json.dumps({'cases': cases}))


asyncio.run(main())
