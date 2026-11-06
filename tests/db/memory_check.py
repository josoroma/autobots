"""Compaction and lexical retrieval with a real graph and a scripted model. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult

sys.path.insert(0, str(Path(__file__).parent))
from goal_loop_script import PLAN, ROUTE, Script, calls, say  # noqa: E402

from autobots.application.compaction import SUMMARY_MARKER, CompactionPolicy, pairing_is_valid, state_block  # noqa: E402
from autobots.application.goal_loop import LoopConfig, process_next, run_goal  # noqa: E402
from autobots.application.memory import search, store_memory  # noqa: E402
from autobots.application.plans import load_goal  # noqa: E402
from autobots.application.runs import admit_run  # noqa: E402
from autobots.application.tool_gateway import ToolGateway, ToolScope  # noqa: E402
from autobots.application.goal_loop import loop_registry  # noqa: E402
from autobots.application.run_usage import RootLimits  # noqa: E402
from autobots.application.worker_leases import claim_next  # noqa: E402
from autobots.contracts.plans import InputDocument  # noqa: E402
from autobots.domain.models import resolve_role_policy  # noqa: E402

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
SERVICE_SOURCE = Path(sys.argv[3])
ACTOR = uuid4()
LONG = 'The quarterly figure for zanzibar shipments is 4217. ' + ('padding text ' * 800)
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class Aware(Script):
    """Answers a summary request itself, so the working script only holds the work."""

    summaries: list[list[Any]] = []
    truncate_summary: bool = False

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **options: Any) -> ChatResult:
        if any(SUMMARY_MARKER in str(item.content) for item in messages if item.type == 'human'):
            self.summaries.append(list(messages))
            self.seen.append(list(messages))
            self.items.insert(0, say('Read the document. The figure is noted.', finish='length' if self.truncate_summary else 'stop'))
            item = self.items.pop(0)
            self.seen.pop()
            from langchain_core.outputs import ChatGeneration  # noqa: PLC0415
            return ChatResult(generations=[ChatGeneration(message=item)])
        return super()._generate(messages, stop, run_manager, **options)


READ = ('read_run_file', {'path': 'inputs/long.md'})
CALC = ('calculate', {'operation': 'sum', 'values': [1, 2]})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit(workspace: UUID = WORKSPACE, documents: tuple[InputDocument, ...] = (InputDocument(path='inputs/long.md', content=LONG),)) -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            return (await admit_run(db, workspace_id=workspace, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Find the quarterly figure', limit_micro_usd=1_000_000, policy=resolve_role_policy(), acceptance_criteria=('States the figure',), input_documents=documents)).run_id

        policy = CompactionPolicy(context_chars=600, large_tool_chars=1000, keep_recent=2)
        config = LoopConfig(route=ROUTE, compaction=policy, sleep=lambda _: asyncio.sleep(0))

        # Long output moves out, the view stays bounded, and state stays outside the summary.
        run = await admit()
        model = Aware(items=[calls(READ), calls(CALC), calls(CALC), calls(CALC), calls(CALC), say('done')], seen=[], bound=[], summaries=[])
        await process_next(db, URL, 'worker', lambda: model, config)
        offload = await (await db.execute('select id, tool_name, sha256, length(content) from app_private.run_offloads where run_id = %s', (run,))).fetchone()
        check('a long tool result is stored whole', 'longer than the document, with a hash', offload[1:], offload[1] == 'read_run_file' and offload[3] > len(LONG) and len(offload[2]) == 64)
        later = model.seen[-1]
        tool_text = ' '.join(str(item.content) for item in later if item.type == 'tool')
        check('the model sees a pointer and short preview rather than the long text', 'far shorter than the document', len(tool_text), len(tool_text) < 2000 and LONG not in tool_text)
        check('a summary was made once the view grew past its budget', 'at least one', len(model.summaries), len(model.summaries) >= 1)
        stored = await (await db.execute('select summary, sources, role, profile from app_private.run_summaries where run_id = %s order by covers desc limit 1', (run,))).fetchone()
        check('it used the run\'s own summarizer role', 'summarizer, the frozen profile', stored[2:], stored[2] == 'summarizer' and stored[3] == 'openrouter_terra')
        invocation = await value("select count(*) from app_private.model_invocations where run_id = %s and role = 'summarizer'", run)
        check('and went through admission like any other call', 'recorded', invocation, invocation >= 1)
        check('its citations are the stored results, worked out by code', 'the offload', stored[1], str(offload[0]) in stored[1])
        human = ' '.join(str(item.content) for item in later if item.type in ('human', 'ai'))
        for label, needle in (('the goal', 'Find the quarterly figure'), ('the criteria', 'States the figure'), ('the permissions', 'Allowed tools:')):
            check(f'{label} stays in the view, outside the summary', 'present', needle in human, needle in human)
        check('the view cites what can be read again', 'the offload id', str(offload[0]) in human, str(offload[0]) in human)
        original = await load_goal(db, run)
        check('the stored goal never changes', 'unchanged', original.objective, original.objective == 'Find the quarterly figure')
        full = await (await db.execute("select count(*) from agent_runtime.checkpoints where thread_id = %s", (str(run),))).fetchone()
        check('the checkpoint keeps the whole conversation', 'checkpoints exist', full[0], full[0] > 0)
        pairs = [pairing_is_valid([m for m in seen if m.type in {'ai', 'tool', 'human'}]) for seen in model.seen]
        check('tool calls and results are never separated in any view', 'valid every time', sum(pairs), all(pairs))

        # The citation is real, and only for this run.
        lease = await claim_next(db, worker_id='none')
        check('nothing else is claimable here', 'none', lease, lease is None)
        run2 = await admit()
        lease = await claim_next(db, worker_id='reader', lease_seconds=120)
        scope = ToolScope(WORKSPACE, run2, lease.generation, {'read_offload': 1, 'search_memory': 1})
        gateway = ToolGateway(loop_registry(RootLimits()))
        foreign = await gateway.execute(db, scope, 'read_offload', {'offload_id': str(offload[0])})
        check('another run can\'t read a stored result', 'offload_not_found', foreign.code, foreign.code == 'offload_not_found')

        # Resumed from a stored summary, and with an unresolved wait.
        await db.execute("insert into app_private.run_obligations (id, run_id, kind, detail) values (%s, %s, 'input', 'Which quarter?')", (uuid4(), run2))
        block = await state_block(db, run2, await load_goal(db, run2))
        check('an open wait is part of the state, from its record', 'Which quarter?', 'Which quarter?' in block, 'Which quarter?' in block)
        await db.execute("update app_private.run_obligations set status = 'met' where run_id = %s", (run2,))

        # A summary that comes back cut off isn't used.
        run3 = await admit()
        model = Aware(items=[calls(READ), calls(CALC), calls(CALC), calls(CALC), say('done')], seen=[], bound=[], summaries=[], truncate_summary=True)
        result = await process_next(db, URL, 'worker', lambda: model, config)
        check('a truncated summary stops the run rather than losing context', 'compaction_failed, failed', (result.code, result.run_status), result.code == 'compaction_failed' and result.run_status == 'failed')
        rows = await value('select count(*) from app_private.run_summaries where run_id = %s', run3)
        check('and nothing was stored from it', '0', rows, rows == 0)

        # A short run stays untouched.
        run4 = await admit(documents=())
        model = Aware(items=[calls(PLAN), say('stop')], seen=[], bound=[], summaries=[])
        await process_next(db, URL, 'worker', lambda: model, LoopConfig(route=ROUTE))
        check('a short conversation isn\'t summarized', 'no summary call', len(model.summaries), not model.summaries and 'Current state' not in str(model.seen[-1]))

        # Lexical search, scoped to the workspace.
        await store_memory(db, workspace_id=WORKSPACE, actor_id=ACTOR, title='Shipping note', content='The zanzibar route ships on Tuesdays.', source={'kind': 'user'})
        await store_memory(db, workspace_id=OTHER, actor_id=ACTOR, title='Secret of the other workspace', content='The zanzibar password is hidden.', source={'kind': 'user'})
        hits = await search(db, WORKSPACE, 'zanzibar')
        memory = [hit for hit in hits if hit.kind == 'memory']
        evidence = [hit for hit in hits if hit.kind == 'evidence']
        check('a keyword finds memory, with its provenance', 'Shipping note, a source', (memory[0].title if memory else None), len(memory) == 1 and memory[0].title == 'Shipping note' and memory[0].source['kind'] == 'user')
        check('and saved evidence, with its path and hash', 'inputs/long.md', evidence[0].source if evidence else None, bool(evidence) and evidence[0].source['path'] == 'inputs/long.md' and len(evidence[0].source['sha256']) == 64)
        check('another workspace\'s memory never appears', 'absent', any('other workspace' in hit.title for hit in hits), not any('other workspace' in hit.title or 'password' in hit.snippet for hit in hits))
        other_hits = await search(db, OTHER, 'zanzibar')
        check('and that workspace doesn\'t see this one', 'only its own', [hit.title for hit in other_hits], [hit.title for hit in other_hits] == ['Secret of the other workspace'])
        check('nonsense query text is harmless', 'no hits, no error', await search(db, WORKSPACE, "'; drop table x; --"), await search(db, WORKSPACE, "'; drop table x; --") == [])
        run5 = await admit(documents=())
        lease = await claim_next(db, worker_id='searcher', lease_seconds=120)
        tool_scope = ToolScope(WORKSPACE, run5, lease.generation, {'search_memory': 1})
        found = await gateway.execute(db, tool_scope, 'search_memory', {'query': 'zanzibar'})
        check('the search tool goes through the gateway with its scope', 'hits, none foreign', len(found.output['hits']), found.outcome.value == 'succeeded' and all('other workspace' not in hit['title'] for hit in found.output['hits']))
        await db.execute("insert into app_private.run_files (run_id, path, version, content, sha256, media_type, operation_id) values (%s, 'outputs/k.md', 1, 'zanzibar sk-or-leakedkeyvalue', 'h', 'text/plain', %s)", (run2, str(uuid4())))
        redacted = await search(db, WORKSPACE, 'zanzibar')
        check('a key-like value is masked in snippets', 'no key', any('sk-or-leaked' in hit.snippet for hit in redacted), not any('sk-or-leaked' in hit.snippet for hit in redacted))

        # No extra inference endpoint exists.
        words = ('embedding', 'rerank', 'pgvector', 'vectorstore')
        found_words = sorted({word for path in SERVICE_SOURCE.rglob('*.py') for word in words if word in path.read_text().lower().replace('no embedding or reranking', '')})
        check('the service code has no embedding or reranking client', 'none', found_words, found_words == [])
        assert run_goal and AIMessage
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
