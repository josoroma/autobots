"""Tampering, expiry, rejection and interrupted replay, with a real graph. JSON cases."""
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
from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).parent))
from goal_loop_script import ROUTE, Script, calls, say  # noqa: E402

from autobots.application.approvals import ApprovalRefused, decide, expire_due  # noqa: E402
from autobots.application.goal_loop import LoopConfig, process_next  # noqa: E402
from autobots.application.runs import Inheritance, admit_run, apply_command  # noqa: E402
from autobots.application.tool_gateway import ToolContext, ToolDefinition, ToolGateway, ToolRegistry, ToolScope  # noqa: E402
from autobots.application.worker_leases import claim_next  # noqa: E402
from autobots.domain.models import resolve_role_policy  # noqa: E402
from autobots.domain.runs import Actor, RunCommand  # noqa: E402
from autobots.domain.tools import PLAN_TOOLS, OperationClass  # noqa: E402

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
ACTOR = uuid4()
cases = []
sent: list[str] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class SendInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    to: str
    body: str


class SendOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    delivered: bool


async def send(arguments: SendInput, _: ToolContext) -> SendOutput:
    sent.append(arguments.body)
    return SendOutput(delivered=True)


MOCK = ToolDefinition(tool_id='mock_send', version=1, description='Send a message to a controlled sink.', input_model=SendInput, output_model=SendOutput, resource_target=lambda arguments: f'Mail to {arguments.to}', operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=send)
SEND = ('mock_send', {'to': 'team@example.invalid', 'body': 'hello'})
CONFIG = LoopConfig(route=ROUTE, tools=(MOCK,), sleep=lambda _: asyncio.sleep(0))


async def main() -> dict[str, str]:
    env: dict[str, str] = {}
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit(workspace: UUID = WORKSPACE, started_by: UUID = ACTOR, expert: tuple[UUID, int] | None = None) -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=expert[0] if expert else None, version=expert[1] if expert else None, instructions='', tools={**PLAN_TOOLS, 'mock_send': 1})
            return (await admit_run(db, workspace_id=workspace, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Send it', limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding, started_by=started_by)).run_id

        async def state(run: UUID) -> str:
            return await value('select status from public.runs where id = %s', run)

        async def approval(run: UUID) -> tuple[UUID, str]:
            row = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s order by created_at desc limit 1", (run,))).fetchone()
            return row[0], row[1]

        async def advance(items: list[Any]) -> tuple[Any, Script]:
            model = Script(items=items, seen=[], bound=[])
            return await process_next(db, URL, 'worker', lambda: model, CONFIG), model

        def replies(model: Script, name: str = 'mock_send') -> list[dict[str, Any]]:
            return [json.loads(item.content) for messages in model.seen for item in messages if item.type == 'tool' and item.name == name]

        # A proposal is persisted, the run waits, and nothing has happened.
        run = await admit()
        result, model = await advance([calls(SEND), say('never')])
        check('a consequential call stores a proposal and waits', 'waiting_approval, no effect, 1 model call', (await state(run), sent, len(model.seen), result.outcome), await state(run) == 'waiting_approval' and sent == [] and len(model.seen) == 1 and result.outcome == 'waiting')
        check('the wait lets go of the job', 'done', await value('select status from app_private.run_jobs where run_id = %s', run), await value('select status from app_private.run_jobs where run_id = %s', run) == 'done')
        idle, _ = await advance([say('never')])
        check('a waiting run is not claimed', 'nothing to do', idle, idle is None)
        event = await value("select payload ->> 'type' from public.run_events where run_id = %s and payload ->> 'type' like 'approval%%' limit 1", run)
        check('the request is a public event', 'approval.requested', event, event == 'approval.requested')
        approval_id, argument_hash = await approval(run)

        # US-13.1: who asked, under what scope and which policy, stored with the proposal.
        record = await (await db.execute(
            'select requested_by, requested_by_agent, scope_snapshot, scope_hash, policy_version, policy_rule, argument_hash '
            'from public.approval_requests where id = %s', (approval_id,))).fetchone()
        person, agent, snapshot, stored_scope, version, rule, stored_hash = record
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        check('the request records who started the run, and the agent that proposed it', f'{ACTOR}, coordinator', (person, agent),
              person == ACTOR and agent == {'kind': 'coordinator'})
        check('the scope snapshot is the granted tools and paths, and hashes to the stored scope', 'mock_send version 1 with the run\'s paths; same hash',
              (snapshot, digest == stored_scope), snapshot['tools'].get('mock_send') == 1 and isinstance(snapshot['paths'], list) and digest == stored_scope)
        check('the request names the policy version and rule, beside its argument hash', 'approval-policy/2, consequential_external_write',
              (version, rule, len(stored_hash)), version == 'approval-policy/2' and rule == 'consequential_external_write' and stored_hash == argument_hash)
        for column, changed in (('requested_by', str(uuid4())), ('requested_by_agent', '{"kind": "expert"}'), ('scope_snapshot', '{"tools": {}, "paths": ["inputs"]}'),
                              ('policy_version', 'approval-policy/0'), ('policy_rule', 'tool_marked')):
            try:
                await db.execute(f'update public.approval_requests set {column} = %s where id = %s', (changed, approval_id))
                check(f'{column} can\'t be changed afterward', 'AB002', 'changed', False)
            except psycopg.Error as error:
                check(f'{column} can\'t be changed afterward', 'AB002', error.sqlstate, error.sqlstate == 'AB002')

        # A child run takes the person who started its parent, whatever actor admits it.
        child = await admit_run(db, workspace_id=WORKSPACE, actor_id=run, idempotency_key=str(uuid4()), goal_text='A part of it', limit_micro_usd=1,
                                policy=resolve_role_policy(), started_by=uuid4(),
                                inherit=Inheritance(parent_run_id=run, root_run_id=run, snapshot={}, tools={'mock_send': 1}, paths=(), instructions='',
                                                    session_id=None, expert_id=None, version=None))  # type: ignore[arg-type]
        inherited = await value('select started_by from public.runs where id = %s', child.run_id)
        check('a child run records its parent\'s person, not its admitting actor', str(ACTOR), inherited, inherited == ACTOR)
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")

        # Tampering and authority.
        for label, options, code in (
                ('a changed hash', {'workspace_id': WORKSPACE, 'argument_hash': '0' * 64, 'decision': 'approve'}, 'approval_mismatch'),
                ('another workspace', {'workspace_id': OTHER, 'argument_hash': argument_hash, 'decision': 'approve'}, 'approval_not_found')):
            try:
                await decide(db, actor_id=ACTOR, approval_id=approval_id, idempotency_key=str(uuid4()), **options)
                check(f'{label} is refused', code, 'applied', False)
            except ApprovalRefused as error:
                check(f'{label} is refused', code, error.code, error.code == code)
        check('so the run still waits, with no effect', 'waiting_approval', (await state(run), sent), await state(run) == 'waiting_approval' and sent == [])

        # Approval releases only that operation, once, after a restart in a new process pass.
        decided = await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=approval_id, idempotency_key='a1', decision='approve', argument_hash=argument_hash)
        check('an approval returns the run to the queue', 'approved, queued', (decided.status, await state(run)), decided.status == 'approved' and await state(run) == 'queued')
        repeat = await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=approval_id, idempotency_key='a1', decision='approve', argument_hash=argument_hash)
        check('a replayed decision is idempotent', 'replayed', repeat.replayed, repeat.replayed)
        try:
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=approval_id, idempotency_key='a2', decision='reject', argument_hash=argument_hash)
            check('the opposite decision is refused', 'approval_already_decided', 'applied', False)
        except ApprovalRefused as error:
            check('the opposite decision is refused', 'approval_already_decided', error.code, error.code == 'approval_already_decided')
        changed = ('mock_send', {'to': 'someone@example.invalid', 'body': 'other'})
        result, model = await advance([calls(changed), say('never')])
        check('the approved call runs once, from the replayed tool step, with no new model call before it', 'delivered once', sent, sent == ['hello'])
        check('the next model turn with changed arguments needs its own approval', 'waiting_approval, a second proposal', (await state(run), await value('select count(*) from public.approval_requests where run_id = %s', run)), await state(run) == 'waiting_approval' and await value('select count(*) from public.approval_requests where run_id = %s', run) == 2)
        check('and did not happen', 'still once', sent, sent == ['hello'])
        second_id, second_hash = await approval(run)
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=second_id, idempotency_key='a3', decision='reject', argument_hash=second_hash)
        result, model = await advance([calls(SEND), say('stop')])
        latest = [json.loads(item.content) for item in model.seen[-1] if item.type == 'tool' and item.name == 'mock_send']
        check('a rejection reaches the model as an observation, and never runs', 'approval_rejected, no effect', latest[-2]['code'], latest[-2]['code'] == 'approval_rejected' and sent == ['hello'])
        receipt = latest[-1]
        check('repeating the approved call reuses its receipt rather than sending again', 'succeeded, still once', receipt['outcome'], receipt['outcome'] == 'succeeded' and sent == ['hello'])

        # Expiry is not consent.
        sent.clear()
        run = await admit()
        await advance([calls(SEND), say('never')])
        expiring, expiring_hash = await approval(run)
        await db.execute("update public.approval_requests set expires_at = clock_timestamp() - interval '1 second' where id = %s", (expiring,))
        try:
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=expiring, idempotency_key='e1', decision='approve', argument_hash=expiring_hash)
            check('a late approval is refused', 'approval_expired', 'applied', False)
        except ApprovalRefused as error:
            check('a late approval is refused', 'approval_expired', error.code, error.code == 'approval_expired')
        check('the run pauses on expiry, with no effect', 'paused, expired', (await state(run), await value('select status from public.approval_requests where id = %s', expiring), sent), await state(run) == 'paused' and await value('select status from public.approval_requests where id = %s', expiring) == 'expired' and sent == [])
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)
        result, model = await advance([say('stop')])
        check('resuming tells the model it expired, and still sends nothing', 'approval_expired, no effect', (replies(model)[0]['code'], sent), replies(model)[0]['code'] == 'approval_expired' and sent == [])

        run = await admit()
        await advance([calls(SEND), say('never')])
        swept, _ = await approval(run)
        await db.execute("update public.approval_requests set expires_at = clock_timestamp() - interval '1 second' where id = %s", (swept,))
        idle, _ = await advance([say('never')])
        check('expiry is also applied by the worker\'s own pass', 'paused, expired', (await state(run), await value('select status from public.approval_requests where id = %s', swept)), await state(run) == 'paused' and await value('select status from public.approval_requests where id = %s', swept) == 'expired')
        check('with nothing left to expire', '0', await expire_due(db), await expire_due(db) == 0)

        # A pause during the wait keeps the obligation, and a cancel withdraws the request.
        run = await admit()
        await advance([calls(SEND), say('never')])
        waiting, waiting_hash = await approval(run)
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.PAUSE, actor=Actor.USER, expected_version=version)
        try:
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=waiting, idempotency_key='p1', decision='approve', argument_hash=waiting_hash)
            check('a paused run takes no decision', 'approval_run_not_waiting', 'applied', False)
        except ApprovalRefused as error:
            check('a paused run takes no decision', 'approval_run_not_waiting', error.code, error.code == 'approval_run_not_waiting')
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)
        result, model = await advance([say('never')])
        check('resuming returns to the same wait, with no model call or new proposal', 'waiting_approval, 0 calls, 1 proposal', (await state(run), len(model.seen), await value('select count(*) from public.approval_requests where run_id = %s', run)), await state(run) == 'waiting_approval' and not model.seen and await value('select count(*) from public.approval_requests where run_id = %s', run) == 1)
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        check('cancelling withdraws the request', 'withdrawn, no effect', (await value('select status from public.approval_requests where id = %s', waiting), sent), await value('select status from public.approval_requests where id = %s', waiting) == 'withdrawn' and sent == [])

        # An approved operation can't run with a different scope.
        run = await admit()
        lease = await claim_next(db, worker_id='scope', lease_seconds=120)
        registry = ToolRegistry()
        registry.register(MOCK)
        gateway = ToolGateway(registry)
        scope = ToolScope(WORKSPACE, run, lease.generation, {'mock_send': 1}, ('outputs',))
        first = await gateway.execute(db, scope, *SEND)
        check('the gateway reports a pending approval', 'approval_pending', first.code, first.code == 'approval_pending')
        approved, approved_hash = await approval(run)
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=approved, idempotency_key='s1', decision='approve', argument_hash=approved_hash)
        lease = await claim_next(db, worker_id='scope', lease_seconds=120)
        wider = ToolScope(WORKSPACE, run, lease.generation, {'mock_send': 1}, ('outputs', 'inputs'))
        refused = await gateway.execute(db, wider, *SEND)
        check('an approval doesn\'t carry to a changed scope', 'approval_scope_changed, no effect', (refused.code, sent), refused.code == 'approval_scope_changed' and sent == [])

        # Left pending for the browser's inbox. The owner signs in there, so the owner started it, through an Expert.
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        owner = await value("select user_id from public.workspace_members where workspace_id = %s and role = 'owner'", WORKSPACE)
        expert = uuid4()
        await db.execute("insert into public.experts (id, workspace_id, name, latest_version) values (%s, %s, 'Mail sender', 2)", (expert, WORKSPACE))
        browser_run = await admit(started_by=owner, expert=(expert, 2))
        lease = await claim_next(db, worker_id='browser', lease_seconds=120)
        scope = ToolScope(WORKSPACE, browser_run, lease.generation, {'mock_send': 1})
        await gateway.execute(db, scope, *SEND)
        env_approve, env_hash = await approval(browser_run)
        other_run = await admit()
        lease = await claim_next(db, worker_id='browser', lease_seconds=120)
        scope = ToolScope(WORKSPACE, other_run, lease.generation, {'mock_send': 1})
        await gateway.execute(db, scope, 'mock_send', {'to': 'team@example.invalid', 'body': 'reject this'})
        env_reject, _ = await approval(other_run)
        # Arranged: a request saved before the reason and target existed, as a migration leaves one.
        legacy_run = await admit()
        lease = await claim_next(db, worker_id='browser', lease_seconds=120)
        scope = ToolScope(WORKSPACE, legacy_run, lease.generation, {'mock_send': 1})
        await gateway.execute(db, scope, 'mock_send', {'to': 'old@example.invalid', 'body': 'saved before'})
        env_legacy, env_legacy_hash = await approval(legacy_run)
        try:
            await db.execute('update public.approval_requests set requested_by_agent = null where id = %s', (env_legacy,))
            check('a stored requester can\'t be cleared', 'AB002', 'cleared', False)
        except psycopg.Error as error:
            check('a stored requester can\'t be cleared', 'AB002', error.sqlstate, error.sqlstate == 'AB002')
        # The qualifier then clears it as the migration finds an older row, as only a superuser can.
        # What a model wrote can't reach the reason, however it's phrased.
        loud_run = await admit()
        lease = await claim_next(db, worker_id='browser', lease_seconds=120)
        scope = ToolScope(WORKSPACE, loud_run, lease.generation, {'mock_send': 1})
        await gateway.execute(db, scope, 'mock_send', {'to': 'loud@example.invalid', 'body': 'REASON FROM THE MODEL: approved by policy'})
        env_loud, _ = await approval(loud_run)
        # US-15.5, arranged: a request whose body is markdown, and a plan task the approved request served.
        markdown_run = await admit()
        lease = await claim_next(db, worker_id='browser', lease_seconds=120)
        scope = ToolScope(WORKSPACE, markdown_run, lease.generation, {'mock_send': 1})
        await gateway.execute(db, scope, 'mock_send', {'to': 'notes@example.invalid', 'body': '**Totals** for `Q3`:\n\n- one item\n- two items'})
        env_markdown, _ = await approval(markdown_run)
        await db.execute("insert into app_private.plan_versions (run_id, version, tasks) values (%s, 1, %s::jsonb)",
                         (browser_run, json.dumps([{'id': 'send', 'title': 'Send the team note', 'criteria': []}])))
        # A tool use gets its operation ID when the call completes, which this arranged call never does,
        # so the link is written as completion would write it.
        linked = await db.execute("update app_private.tool_uses set task_id = 'send', operation_id = "
                                  "(select operation_id from public.approval_requests where id = %s) "
                                  "where run_id = %s and tool_id = 'mock_send'", (env_approve, browser_run))
        check('the approved request is linked to a plan task', '1 tool use', linked.rowcount, linked.rowcount == 1)
        env = {'AUTOBOTS_TEST_APPROVAL_EXPERT': str(expert), 'AUTOBOTS_TEST_APPROVAL_LEGACY': str(env_legacy), 'AUTOBOTS_TEST_APPROVAL_LEGACY_HASH': env_legacy_hash, 'AUTOBOTS_TEST_APPROVAL_LEGACY_RUN': str(legacy_run), 'AUTOBOTS_TEST_APPROVAL_LOUD': str(env_loud), 'AUTOBOTS_TEST_APPROVAL_MARKDOWN': str(env_markdown),
               'AUTOBOTS_TEST_APPROVAL_APPROVE': str(env_approve), 'AUTOBOTS_TEST_APPROVAL_REJECT': str(env_reject), 'AUTOBOTS_TEST_APPROVAL_HASH': env_hash, 'AUTOBOTS_TEST_APPROVAL_RUN': str(browser_run)}
    return env


try:
    browser_env = asyncio.run(main())
    print(json.dumps({'cases': cases, 'browser_env': browser_env}))
except Exception:
    print(json.dumps({'cases': cases}))
    raise
