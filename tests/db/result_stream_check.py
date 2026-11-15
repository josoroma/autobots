"""US-15.24: a run writes its result with a streaming scripted model while this check listens.

The live text must be the result file's content only, coalesced, and never a durable event, and what
streamed must equal the stored artifact. The reasoning, a raw framework value, the path and every other
tool argument the model streamed must never appear. JSON cases, and the values the browser suite needs.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.adapters.result_stream import CHANNEL
from autobots.api.event_routes import live_frame
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import admit_run
from autobots.application.worker_leases import claim_run
from autobots.contracts.runs import RunEvent
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import LOOP_TOOL_GRANTS
from autobots.operations.job_dispatch import drive_lease
from goal_loop_script import ROUTE, calls, say
from pydantic import SecretStr
from stream_script import FRAMEWORK_MARKER, REASONING_MARKER, StreamScript

URL, BASE = os.environ['AUTOBOTS_DATABASE_URL'], os.environ['AUTOBOTS_STORAGE_BASE']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
WORKSPACE = UUID(sys.argv[1])
CONTENT = '# Quarterly report\n\n' + ''.join(f'Line {n}: the total so far is "{n * 7}" — café ✓\n' for n in range(1, 60))
TASK = {'id': 'report', 'title': 'Write the report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}
STEPS = [calls(('propose_plan', {'tasks': [TASK]})),
         calls(('save_artifact', {'path': 'outputs/notes.md', 'content': 'WORKING-NOTE-NOT-A-RESULT'}),
               ('save_artifact', {'path': 'outputs/report.md', 'content': CONTENT})),
         calls(('publish_artifact', {'path': 'outputs/report.md', 'version': 1})),
         calls(('complete_task', {'task_id': 'report', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/report.md'}], 'summary': 'Wrote it.'})),
         say('The report is ready.')]
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:400], 'passed': bool(passed)})


async def main() -> None:
    store = SupabaseObjectStore(BASE, SERVICE)
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0))
    notes: list[dict[str, Any]] = []
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db, \
            await psycopg.AsyncConnection.connect(URL, autocommit=True) as listener:
        await listener.execute(f'listen {CHANNEL}')
        binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools=dict(LOOP_TOOL_GRANTS))
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the quarterly report',
                                   limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)
        run = admitted.run_id
        lease = await claim_run(db, run, worker_id='result-stream-check')
        assert lease is not None
        model = StreamScript(items=list(STEPS), seen=[], bound=[], delay=0.0005, chunked=[])

        async def listen() -> None:
            async for note in listener.notifies():
                payload = json.loads(note.payload)
                if payload.get('run_id') == str(run):
                    notes.append(payload)

        listening = asyncio.ensure_future(listen())
        result = await drive_lease(db, URL, lease, lambda: model, config)
        await asyncio.sleep(0.5)
        listening.cancel()

        status = (await (await db.execute('select status from public.runs where id = %s', (run,))).fetchone())[0]
        check('the run writes and publishes its result with a streaming model', 'succeeded', (result.outcome, status), status == 'succeeded')
        streamed = ''.join(note['text'] for note in sorted(notes, key=lambda note: note['offset']) if note['segment'] == 2)
        segments = sorted({note['segment'] for note in notes})
        check('the live text is the result file content, and equals the stored artifact', 'equal, as segment 2 after the note',
              (len(streamed), len(CONTENT), segments), streamed == CONTENT and segments == [1, 2])
        stored = await (await db.execute("select content from app_private.run_files where run_id = %s and path = 'outputs/report.md' and version = 1", (run,))).fetchone()
        published = await (await db.execute("select sha256, status from public.artifacts where run_id = %s and name = 'report.md'", (run,))).fetchone()
        check('the stored artifact is what streamed', 'same bytes and digest, published',
              (published, hashlib.sha256(CONTENT.encode()).hexdigest()[:12]),
              stored is not None and stored[0] == CONTENT and published is not None
              and published[0] == hashlib.sha256(CONTENT.encode()).hexdigest() and published[1] == 'published')
        save_fragments = model.chunked[1] if len(model.chunked) > 1 else 0
        check('the deltas are coalesced, far fewer than the streamed fragments', 'fewer than a quarter',
              (len(notes), save_fragments), 0 < len(notes) < save_fragments / 4)
        check('each delta carries the run, segment, offset and text only', '{offset, run_id, segment, text}',
              sorted({tuple(sorted(note)) for note in notes}), {tuple(sorted(note)) for note in notes} == {('offset', 'run_id', 'segment', 'text')})
        everything = json.dumps(notes)
        leaks = [marker for marker in (REASONING_MARKER, FRAMEWORK_MARKER, 'outputs/report.md', 'outputs/notes.md', 'propose_plan', 'Write the report',
                                       'publish_artifact', 'complete_task', '"tool') if marker in everything]
        check('no reasoning, framework value, path or other argument is streamed', 'none', leaks or 'none', not leaks)
        # The working note is under outputs/ too, so it streams as its own segment: it's result text.
        first = ''.join(note['text'] for note in notes if note['segment'] == 1)
        check('each file the run writes streams as its own segment', 'segment 1 is the first file', first, first == 'WORKING-NOTE-NOT-A-RESULT')
        durable = (await (await db.execute("select count(*) from public.run_events where run_id = %s and payload ->> 'type' = 'result.text.delta'", (run,))).fetchone())[0]
        check('no delta is stored as a durable event', '0', durable, durable == 0)
        frame = live_frame(run, 3, json.dumps(notes[0])) if notes else None
        event = RunEvent.model_validate_json(frame.split('data: ', 1)[1]) if frame else None
        check('the API sends a delta as a typed result.text.delta at schema_version 1, and only this run\'s', 'typed, other runs dropped',
              (event.payload.type if event else None, live_frame(uuid4(), 3, json.dumps(notes[0])) if notes else 'none'),
              event is not None and event.schema_version == 1 and event.payload.type == 'result.text.delta'
              and live_frame(uuid4(), 3, json.dumps(notes[0])) is None)
    print(json.dumps({'cases': cases, 'browser_env': {
        'AUTOBOTS_TEST_STREAM_HELPER': str(Path(__file__).parent / 'result_stream_live.py'),
        'AUTOBOTS_TEST_STORAGE_BASE': BASE}}))


asyncio.run(main())
