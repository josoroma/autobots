"""US-21.1 and Decision 0039 on a real database: browse_goal version 4's typed result saved straight to a run file, through
the real gateway, admission, lease and tool-use record. JSON cases.

Each browse is scripted: the tool's own rules run, and the box is replaced by a scripted outcome, so no container starts and
nothing reaches any host. The published transcript is tests/db/checks/transcript_check.py.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.application import browsing_tool, tool_uses
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.experts import create_expert
from autobots.application.loop_admission import active_middleware
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import ModelRoute, resolve_role_policy
from autobots.domain.tools import EXPERT_TOOLS, PLAN_TOOLS
from checklib import QUIESCE, Cases, run_check, run_scenarios

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ROUTE = ModelRoute('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 1000)
PLANTED = 'PLANTED-in-a-result'
SCHEMA = {'type': 'object', 'properties': {'title': {'type': 'string'}, 'lines': {'type': 'array', 'items': {
    'type': 'object', 'properties': {'time': {'type': 'string'}, 'text': {'type': 'string'}}, 'required': ['time', 'text']}}},
    'required': ['title', 'lines']}
SAVE = {'path': 'outputs/child-1/notes.md', 'before': '# {title}\n\nKeep { this } and {}', 'items': 'lines', 'line': '{time} {text}'}
ARGS = {'task': 'Read the page.', 'start_url': 'https://example.com/', 'allowed_domains': ['example.com'], 'output_schema': SCHEMA,
        'save': SAVE}
# Past the 48,000 characters a tool's output is offloaded at, and more than one model reply can hold.
LINES = [{'time': f'{n // 60}:{n % 60:02d}', 'text': f'{PLANTED} {n}' + ('\nsecond half' if n == 5 else '')} for n in range(3000)]
RESULT = {'title': 'A scripted page', 'lines': LINES}
Outcome = BrowseOutcome | Callable[[], Awaitable[BrowseOutcome]]


def done(result: Any, stopped: str = 'done') -> BrowseOutcome:
    return BrowseOutcome('Read.', ('https://example.com/',), 2, 3, stopped, result, ())  # type: ignore[arg-type]  # a stop reason


class NoBox:
    """The executor, which a scripted browse never reaches beyond its sweep."""

    def __init__(self) -> None:
        self.swept = 0

    async def sweep(self, alive: Any) -> list[str]:
        self.swept += 1
        return []

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f'the executor was touched: {name}')


class Middleware:
    async def admitted(self, request: Any, handler: Any, route: Any) -> Any:
        raise AssertionError('no model call is expected')


class Rig:
    def __init__(self, cases: Cases, db: Any) -> None:
        self.cases, self.db, self.box = cases, db, NoBox()
        self.outcomes: list[Outcome] = []
        self.registry = ToolRegistry()
        runtime = browsing_tool.BrowsingRuntime(self.box, None, ROUTE, settle=0, browser_use=lambda: True)  # type: ignore[arg-type]  # fakes
        for tool in browsing_tool.browse_tools(runtime, qualified=lambda: True):
            self.registry.register(tool)
        self.made: Any = None

    async def rows(self, sql: str, *values: object) -> list[tuple[Any, ...]]:
        return await (await self.db.execute(sql, values)).fetchall()

    async def files(self, run: UUID) -> list[tuple[Any, ...]]:
        return await self.rows('select path, version, content, sha256, media_type from app_private.run_files where run_id = %s '
                               'order by path, version', run)

    async def scope(self, tool_version: int = 4) -> ToolScope:
        """A run granted that version whose paths are a child run's, claimed."""
        await self.db.execute(QUIESCE)
        if self.made is None:
            self.made = await create_expert(
                self.db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), name=f'Saver {uuid4().hex[:6]}',
                catalog=tool_registry.catalog(), config=ExpertConfig(tools=['browse_goal'], browse_domains=['example.com']))
        grant = {**PLAN_TOOLS, 'browse_goal': tool_version}
        binding = SimpleNamespace(session_id=None, expert_id=self.made.id, version=1, instructions='', tools=grant)
        run = (await admit_run(self.db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Save',
                               limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
        return await self.claim(run, grant)

    async def claim(self, run: UUID, grant: dict[str, int]) -> ToolScope:
        lease = await claim_next(self.db, worker_id='saved-browse', lease_seconds=300)
        assert lease is not None and lease.run_id == run, lease
        await self.db.execute("update public.runs set status = 'running' where id = %s", (run,))
        return ToolScope(WORKSPACE, run, lease.generation, grant, ('inputs', 'outputs/child-1'))

    async def call(self, scope: ToolScope, *outcomes: Outcome, **change: Any) -> Any:
        self.outcomes[:] = outcomes
        with active_middleware(Middleware()):  # type: ignore[arg-type]  # the handler needs one; no model is called
            return await ToolGateway(self.registry).execute(self.db, scope, 'browse_goal', {**ARGS, **change})

    async def box_call(self, executor: Any, call: Any, **_: Any) -> BrowseOutcome:
        outcome = self.outcomes.pop(0)
        return outcome if isinstance(outcome, BrowseOutcome) else await outcome()


async def saved_whole(rig: Rig) -> None:
    scope = await rig.scope()
    first = await rig.call(scope, done(RESULT))
    # Indented JSON is longer than a line each, so fewer items fit in a run file.
    part = {'title': 'A scripted page', 'lines': LINES[:500]}
    second = await rig.call(scope, done(part), save={'path': 'outputs/child-1/notes.json'})
    as_json, laid_out = await rig.files(scope.run_id)
    lines = [f"{line['time']} {' '.join(line['text'].split(chr(10)))}" for line in LINES]
    wanted = '\n'.join(['# A scripted page', '', 'Keep { this } and {}', '', *lines]) + '\n'
    output = first.output or {}
    told = first.for_model() + second.for_model()
    rig.cases.check('every line is saved in order, one line each, and the output names the file and holds no result',
                    'the whole text past 48,000 characters; path, version, digest, items and characters as its row has them',
                    (laid_out[2] == wanted, len(wanted), {key: output.get(key) for key in output if key.startswith('saved') or key == 'result'}),
                    laid_out[2] == wanted and len(wanted) > 48_000 and output.get('result') is None and output.get('not_saved') is None
                    and (output['saved_path'], output['saved_version'], output['saved_sha256'], output['saved_items'],
                         output['saved_characters']) == (laid_out[0], laid_out[1], laid_out[3], 3000, len(wanted))
                    and laid_out[4] == 'text/markdown')
    rig.cases.check('with no layout the file is the result as indented JSON, with no item count', 'the same result, indented, saved_items empty',
                    (as_json[2][:60], (second.output or {}).get('saved_items')),
                    json.loads(as_json[2]) == part and as_json[2].startswith('{\n  "title"') and as_json[4] == 'application/json'
                    and (second.output or {}).get('saved_items') is None)
    rig.cases.check('no line of the result reaches the model', 'neither output holds the planted text', PLANTED in told, PLANTED not in told)


async def refused_first(rig: Rig) -> None:
    scope = await rig.scope()
    swept = rig.box.swept
    changes: list[dict[str, Any]] = [
        {'output_schema': None}, {'save': {**SAVE, 'items': 'rows'}}, {'save': {**SAVE, 'line': '{when}'}},
        {'save': {**SAVE, 'before': '{name}'}}, {'save': {**SAVE, 'path': 'outputs/elsewhere.md'}}]
    codes = [(await rig.call(scope, **change)).code for change in changes]
    rig.cases.check('a save with no schema, an unknown name or a path outside the grants is refused before the executor',
                    'invalid_arguments four times, then resource_not_granted, with the executor untouched and no file',
                    (codes, rig.box.swept - swept, await rig.files(scope.run_id)),
                    codes == ['invalid_arguments'] * 4 + ['resource_not_granted'] and rig.box.swept == swept
                    and await rig.files(scope.run_id) == [])


async def not_saved(rig: Rig) -> None:
    scope = await rig.scope()
    empty = {'title': 'None', 'lines': []}
    large = {'title': 'Long', 'lines': [{'time': '0:00', 'text': 'x' * 256_000}]}
    seen = [(await rig.call(scope, done(empty))).output, (await rig.call(scope, done(large))).output]
    stops = [(await rig.call(scope, done(RESULT, stop))).output for stop in ('max_steps', 'refused_action', 'bot_check')]
    bad = (await rig.call(scope, done({'title': 'No lines'}))).output
    rig.cases.check('an empty array and a file past the limit say why and return the result, and no other stop saves',
                    'no_items and too_large with the results; not_saved and result empty for the rest; no file',
                    ([(o['not_saved'], str(o['result'])[:40]) for o in seen], [(o['stopped'], o['not_saved']) for o in [*stops, bad]]),
                    [o['not_saved'] for o in seen] == ['no_items', 'too_large'] and [o['result'] for o in seen] == [empty, large]
                    and [o['stopped'] for o in [*stops, bad]] == ['max_steps', 'refused_action', 'bot_check', 'invalid_action']
                    and all(o['not_saved'] is None and o['result'] is None for o in [*stops, bad])
                    and await rig.files(scope.run_id) == [])
    short = {'title': 'Short', 'lines': LINES[:2]}
    handed: list[Any] = []
    typed = browsing_tool._saved_output

    async def kept(*given: Any) -> Any:
        handed.append(await typed(*given))
        return handed[-1]

    async def ended() -> BrowseOutcome:
        await rig.db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s",
                             (scope.run_id,))
        return done(short)

    browsing_tool._saved_output = kept  # type: ignore[assignment]  # records what the handler returned
    try:
        await rig.call(scope, ended)
    finally:
        browsing_tool._saved_output = typed
    rig.cases.check('an attempt that ended before the save writes nothing and says so', 'lease_lost with the result, and no file',
                    (handed[0].not_saved, handed[0].result == short, await rig.files(scope.run_id)),
                    handed[0].not_saved == 'lease_lost' and handed[0].result == short and await rig.files(scope.run_id) == [])


async def repeats(rig: Rig) -> None:
    scope = await rig.scope()
    complete = tool_uses.complete_use

    async def crash(*_: Any, **__: Any) -> None:
        raise ConnectionError('the worker stopped before the outcome was recorded')

    tool_uses.complete_use = crash  # type: ignore[assignment]  # arranged crash, after the file's row committed
    try:
        await rig.call(scope, done(RESULT))
        crashed = 'returned'
    except ConnectionError:
        crashed = 'crashed'
    finally:
        tool_uses.complete_use = complete
    first = await rig.files(scope.run_id)
    await rig.db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s",
                         (scope.run_id,))
    again = await rig.claim(scope.run_id, dict(scope.tools))
    revised = {'title': 'A later read', 'lines': LINES[:3]}
    swept = rig.box.swept
    result = await rig.call(again, done(revised))
    files = await rig.files(scope.run_id)
    rig.cases.check('a repeat after a crash browses again and saves a new version, and the earlier one stays',
                    'one version left by the crash, then a second browse and version 2, named by the output',
                    (crashed, len(first), rig.box.swept - swept, [(row[0], row[1], len(row[2])) for row in files], (result.output or {}).get('saved_version')),
                    crashed == 'crashed' and len(first) == 1 and rig.box.swept - swept == 1 and [row[1] for row in files] == [1, 2]
                    and files[0] == first[0] and '# A later read' in files[1][2] and (result.output or {}).get('saved_version') == 2)


async def pinned(rig: Rig) -> None:
    scope = await rig.scope(tool_version=3)
    call = {key: value for key, value in ARGS.items() if key != 'save'}
    refused = (await rig.call(scope)).code
    rig.outcomes[:] = [done({'title': 'A', 'lines': LINES[:2]})]
    with active_middleware(Middleware()):  # type: ignore[arg-type]  # no model is called
        result = await ToolGateway(rig.registry).execute(rig.db, scope, 'browse_goal', call)
    version = (await rig.rows("select tool_version from app_private.tool_uses where run_id = %s order by id desc limit 1", scope.run_id))[0][0]
    rig.cases.check('a run that pinned version 3 runs as version 3, takes no save and gets its result back, and new grants take version 4',
                    'invalid_arguments with a save; then version 3 with the result; 4 granted',
                    (refused, version, sorted(result.output or {}), EXPERT_TOOLS['browse_goal']),
                    refused == 'invalid_arguments' and version == 3 and (result.output or {}).get('result') == {'title': 'A', 'lines': LINES[:2]}
                    and 'saved_path' not in (result.output or {}) and EXPERT_TOOLS['browse_goal'] == 4)


async def shown(rig: Rig) -> None:
    scope = await rig.scope()
    await rig.call(scope, done(RESULT))
    rows = [row[0] for row in await rig.rows('select to_jsonb(u) from app_private.tool_uses u where run_id = %s', scope.run_id)]
    events = [row[0] for row in await rig.rows('select to_jsonb(e) from public.run_events e where run_id = %s', scope.run_id)]
    public = rows[0]['output_public']
    rig.cases.check("the tool row shows the saved path and the item count, and no row or event holds the file's text",
                    "saved_path and saved_items beside version 3's public fields, and the planted text nowhere",
                    (public, len(rows), len(events), PLANTED in json.dumps([rows, events])),
                    public.get('saved_path') == 'outputs/child-1/notes.md' and public.get('saved_items') == 3000
                    and set(public) == {'stopped', 'steps', 'visited_count', 'submits', 'saved_path', 'saved_items'}
                    and len(events) > 0 and PLANTED not in json.dumps([rows, events]))


SCENARIOS = (saved_whole, refused_first, not_saved, repeats, pinned, shown)


async def main(cases: Cases) -> None:
    # The catalog lets an Expert grant browse_goal only while the executor reports qualified.
    browsing_tool.executor_qualified = lambda *_: True
    os.environ['AUTOBOTS_BROWSER_EXECUTOR'] = 'enabled'
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        rig = Rig(cases, db)
        browsing_tool.browse_in_box = rig.box_call  # type: ignore[assignment]  # a scripted box, never a network
        await run_scenarios(cases, SCENARIOS, rig)


if __name__ == '__main__':
    run_check(main, parent_timeout=180)
