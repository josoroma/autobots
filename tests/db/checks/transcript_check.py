"""US-17.5 and Decision 0035 Y3, Y10, Y13, Y14, Y17 and Y18 on a real database: the seeded Transcript reader and Transcript
workflow. JSON cases.

The model is scripted, and so is each browse: browse_goal's own tool runs, with its YOLO, domain, approval and typed-result
rules, but the box is replaced by a scripted outcome, so nothing reaches YouTube or any other host (Y18). Published files go
to an in-memory store that keeps the real store's path rule. browse_goal's availability is arranged by the catalog's
executor check answering "unavailable" or "available", and reported as arranged.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.object_storage import _scoped
from autobots.application import browsing_tool
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.experts import add_version
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.tool_definitions import Browsing
from autobots.application.workflow_executions import create_execution
from autobots.application.workflows import WorkflowRefused
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import ModelRoute
from autobots.operations import concept_seed
from autobots.operations.job_dispatch import process_next
from goal_loop_script import ROUTE, Script, calls, say

URL = os.environ['AUTOBOTS_DATABASE_URL']
RESEARCHER = ModelRoute('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 1000)
VIDEO = 'https://www.youtube.com/watch?v=aaaaaaaaaaa&t=5s'
DOMAINS = ['youtube.com', 'ytimg.com', 'ggpht.com', 'gstatic.com']
TITLE = 'A scripted video'
LINES = [{'time': f'{n // 60}:{n % 60:02d}', 'text': f'Scripted caption number {n}.'} for n in range(0, 240, 12)]
cases: list[dict[str, Any]] = []
available = [False]
browses: list[Any] = []
outcomes: list[BrowseOutcome] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:900], 'passed': bool(passed)})


class Store:
    """The run's private storage, in memory, with the real store's path rule."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        _scoped(path)
        if path in self.objects:
            return False
        self.objects[path] = content
        return True

    async def get(self, path: str) -> bytes | None:
        return self.objects.get(path)

    async def remove(self, path: str) -> None:
        self.objects.pop(path, None)

    async def names(self, prefix: str) -> list[str]:
        return [name for name in self.objects if name.startswith(prefix)]

    async def ping(self) -> None:
        return None


class NoBox:
    """The executor, which a scripted browse never reaches beyond its sweep."""

    async def sweep(self, alive: Any) -> list[str]:
        return []

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f'the executor was touched: {name}')


async def scripted_browse(executor: Any, call: Any, **_: Any) -> BrowseOutcome:
    """The box's outcome, as the next scripted browse says. Its call is recorded."""
    browses.append(call)
    return outcomes.pop(0)


def markdown() -> str:
    """What the scripted model writes from the typed result, as the Transcript reader's instructions say."""
    lines = [f'# {TITLE}', '', f'Source: {VIDEO}', '', "These lines are YouTube's own captions for the video.", '']
    return '\n'.join(lines + [f"{line['time']} {line['text']}" for line in LINES]) + '\n'


def transcribing(result: dict[str, Any] | None) -> list[Any]:
    """The scripted Transcript reader: a plan, one browse with the seeded schema, then the file or a stop."""
    plan = calls(('propose_plan', {'tasks': [{'id': 't', 'title': 'Transcribe the video', 'criteria': ['c1'],
                                              'expected_evidence': 'transcript.md'}]}))
    browse = calls(('browse_goal', {'task': 'Open the address, press "...more" and "Show transcript", and read every line.',
                                    'start_url': VIDEO, 'allowed_domains': DOMAINS,
                                    'output_schema': json.loads(concept_seed.TRANSCRIPT_SCHEMA)}))
    if result is None:
        return [plan, browse, say('YouTube answered with a bot check, so nothing was published.')]
    if not result['lines']:
        return [plan, browse, say('The video offers no transcript, so nothing was published.')]
    path = 'outputs/child-1/transcript.md'
    return [plan, browse, calls(('save_artifact', {'path': path, 'content': markdown()})),
            calls(('publish_artifact', {'path': path, 'version': 1})),
            calls(('complete_task', {'task_id': 't', 'evidence': [{'kind': 'artifact', 'reference': path}], 'summary': 'published'})),
            say('Published transcript.md.')]


async def main() -> None:
    browsing_tool.executor_ready = lambda *_, **__: available[0]  # type: ignore[assignment]  # arranged availability
    browsing_tool.browse_in_box = scripted_browse  # type: ignore[assignment]  # a scripted box, never a network
    store = Store()
    runtime = browsing_tool.BrowsingRuntime(NoBox(), None, RESEARCHER, settle=0, browser_use=lambda: True)  # type: ignore[arg-type]
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry,
                        browsing=Browsing(lambda: True, runtime))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def workspace(name: str) -> tuple[UUID, UUID]:
            made, owner = uuid4(), uuid4()
            await db.execute('insert into public.workspaces (id, name) values (%s, %s)', (made, name))
            await db.execute("insert into public.workspace_members (workspace_id, user_id, role) values (%s, %s, 'owner')", (made, owner))
            return made, owner

        async def latest(space: UUID, name: str) -> dict[str, Any]:
            return await value('select v.config from public.experts e join public.expert_versions v on v.expert_id = e.id '
                               'and v.version = e.latest_version where e.workspace_id = %s and e.name = %s', space, name)

        async def flow_state(space: UUID) -> tuple[int, bool]:
            return (await (await db.execute(
                'select w.latest_version, exists (select 1 from public.workflow_drafts d where d.workflow_id = w.id) '
                "from public.workflows w where w.workspace_id = %s and w.name = 'Transcript'", (space,))).fetchone())

        # Seeded twice where browse_goal isn't available, and twice where it is.
        off, _ = await workspace('No browsing')
        available[0] = False
        off_first, off_second = await concept_seed.seed(db, off, {}), await concept_seed.seed(db, off, {})
        on, owner = await workspace('Browsing')
        available[0] = True
        on_first, on_second = await concept_seed.seed(db, on, {}), await concept_seed.seed(db, on, {})
        off_reader, on_reader = await latest(off, 'Transcript reader'), await latest(on, 'Transcript reader')
        second_runs = {*off_second['experts'].values(), *off_second['workflows'].values(), *on_second['experts'].values(),
                       *on_second['workflows'].values()}
        check('seeded once, and as a draft without browsing',
              'without browse_goal: the reader lacks it and says so, the workflow is a draft; with it: the workflow is published; '
              'the second run keeps everything in both',
              (off_reader.get('tools'), 'Saved without browse_goal' in off_reader.get('purpose', ''), await flow_state(off),
               on_reader.get('tools'), await flow_state(on), sorted(second_runs, key=str)),
              off_reader.get('tools') == ['save_artifact', 'publish_artifact'] and 'Saved without browse_goal' in off_reader.get('purpose', '')
              and await flow_state(off) == (0, True) and on_reader.get('tools') == ['browse_goal', 'save_artifact', 'publish_artifact']
              and await flow_state(on) == (1, False) and second_runs == {'kept'}
              and off_first['workflows']['Transcript'] == {'draft': True, 'unavailable': ['browse_goal']}
              and on_first['workflows']['Transcript'] == {'published': 1})

        workflow_id = await value("select id from public.workflows where workspace_id = %s and name = 'Transcript'", on)

        async def execute(video: str, key: str) -> Any:
            return await create_execution(db, workspace_id=on, actor_id=owner, workflow_id=workflow_id, idempotency_key=key,
                                          version=1, inputs={'video': video})

        # Only an https YouTube watch or youtu.be address starts an execution.
        refusals = []
        for bad in ('http://www.youtube.com/watch?v=aaaaaaaaaaa', 'https://www.youtube.com.evil.test/watch?v=aaaaaaaaaaa',
                    'https://www.youtube.com/@channel', 'not an address'):
            try:
                await execute(bad, str(uuid4()))
                refusals.append((bad, 'started'))
            except WorkflowRefused as refused:
                refusals.append((bad, refused.code, [(error.code, error.node) for error in refused.errors]))
        runs_before = await value('select count(*) from public.runs where workspace_id = %s', on)
        check('only a YouTube watch address is accepted',
              'each refused before it starts as workflow_inputs_invalid, naming video; no run admitted',
              refusals, all(entry[1:] == ('workflow_inputs_invalid', [('input_pattern_mismatch', 'video')]) for entry in refusals)
              and runs_before == 0)

        async def run(script: list[Any], outcome: BrowseOutcome | None) -> tuple[Any, Script]:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             "where status <> 'done'")
            if outcome is not None:
                outcomes.append(outcome)
            model = Script(items=script, seen=[], bound=[])
            execution = await execute(VIDEO, str(uuid4()))
            for _ in range(8):
                await process_next(db, URL, 'transcript', lambda: model, config)
                status = await value('select status from public.runs where id = %s', execution.run_id)
                if status in ('succeeded', 'failed', 'cancelled', 'waiting_approval'):
                    break
            return execution, model

        async def children(execution: Any) -> list[UUID]:
            return [row[0] for row in await (await db.execute(
                'select child_run_id from app_private.assignments where parent_run_id = %s order by created_at',
                (execution.run_id,))).fetchall()]

        async def published(execution: Any) -> list[tuple[str, str]]:
            return [tuple(row) for row in await (await db.execute(
                "select name, object_path from public.artifacts where status = 'published' and run_id = any(%s)",
                ([execution.run_id, *(await children(execution))],))).fetchall()]

        # Seeded with no domains: the reader's browse is refused before any box, naming the missing list.
        domains_before = list(on_reader.get('browse_domains', []))
        browses.clear()
        empty, _ = await run([*transcribing({'title': TITLE, 'lines': LINES})[:2], say('stopped')], None)
        refused_code = await value("select code from app_private.tool_uses where tool_id = 'browse_goal' and run_id = any(%s)",
                                   await children(empty))
        check('seeded with no domains',
              "an empty browse domain list, and the call refused browse_domains_missing with no box and no file",
              (domains_before, refused_code, len(browses), await published(empty)),
              domains_before == [] and 'browser' not in on_reader and refused_code == 'browse_domains_missing' and browses == []
              and await published(empty) == [])

        # The owner adds YouTube's hosts, which is where the owner accepts YouTube's terms (Y14).
        expert_id = await value("select id from public.experts where workspace_id = %s and name = 'Transcript reader'", on)
        version = await value('select latest_version from public.experts where id = %s', expert_id)
        await add_version(db, workspace_id=on, actor_id=owner, expert_id=expert_id, idempotency_key=str(uuid4()), expected_version=version,
                          config=ExpertConfig.model_validate({**on_reader, 'browse_domains': DOMAINS}), catalog=tool_registry.catalog())

        browses.clear()
        done = BrowseOutcome('Read the transcript.', ('https://www.youtube.com/watch',), 6, 7, 'done', {'title': TITLE, 'lines': LINES}, ())
        transcribed, model = await run(transcribing({'title': TITLE, 'lines': LINES}), done)
        files = await published(transcribed)
        content = store.objects.get(files[0][1], b'').decode() if files else ''
        timed = [line for line in content.splitlines() if re.match(r'^\d+:\d{2} ', line)]
        shown = [str(message.content) for message in (model.seen[2] if len(model.seen) > 2 else [])]
        check('a watch address in, transcript.md out',
              'transcript.md published with the title, the source address and every line with its timestamp, as many lines as the '
              "transcript's, from the browse's typed result",
              ([name for name, _ in files], content[:160], len(timed), len(LINES),
               any('Scripted caption number 0.' in text for text in shown)),
              [name for name, _ in files] == ['transcript.md'] and f'# {TITLE}' in content and f'Source: {VIDEO}' in content
              and len(timed) == len(LINES) and timed == [f"{line['time']} {line['text']}" for line in LINES]
              and any('Scripted caption number 0.' in text for text in shown))

        use = await (await db.execute(
            "select input_public, outcome from app_private.tool_uses where tool_id = 'browse_goal' and run_id = any(%s)",
            (await children(transcribed),))).fetchone()
        asked = await value('select count(*) from public.approval_requests where run_id = any(%s)',
                            [transcribed.run_id, *(await children(transcribed))])
        named = list(browses[0].allowed_domains) if browses else []
        check("the video host isn't allowed",
              "started without approval, its allowed domains within the Transcript reader's, none of them googlevideo.com",
              (asked, named, use), asked == 0 and bool(named) and set(named) <= set(DOMAINS) and not any('googlevideo' in host for host in named)
              and use is not None and use[1] == 'succeeded')

        browses.clear()
        nothing = BrowseOutcome('There is no Show transcript.', ('https://www.youtube.com/watch',), 3, 4, 'done', {'title': TITLE, 'lines': []}, ())
        empty_video, model = await run(transcribing({'title': TITLE, 'lines': []}), nothing)
        status = await value('select status from public.runs where id = %s', empty_video.run_id)
        check('no transcript offered',
              'the run ends, its last word says no transcript is offered, and no file is published',
              (status, await published(empty_video), model.items, len(browses)),
              status in ('succeeded', 'failed') and await published(empty_video) == [] and model.items == [] and len(browses) == 1)

        browses.clear()
        blocked = BrowseOutcome('', ('https://www.youtube.com/watch',), 1, 1, 'bot_check', None, ())
        bot, model = await run(transcribing(None), blocked)
        seen = ' '.join(str(message.content) for message in (model.seen[2] if len(model.seen) > 2 else []))
        status = await value('select status from public.runs where id = %s', bot.run_id)
        check('a bot check stops it',
              'the browse stops bot_check, the model sees it, one browse only, nothing published, and the run ends',
              (status, 'bot_check' in seen, len(browses), await published(bot)),
              status in ('succeeded', 'failed') and 'bot_check' in seen and len(browses) == 1 and await published(bot) == [])
    print(json.dumps({'cases': cases}))


asyncio.run(main())
