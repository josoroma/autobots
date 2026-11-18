"""Tampering, expiry, rejection and interrupted replay, with a real graph. JSON cases through checklib, one
scenario at a time (refactor plan R-66, TDBC-06).

It also repeats an approved browse_goal call, which leaves no receipt and so uses its approval up, and arranges
an expiry that raced a decision or a cancel (refactor plan R-50: PTOL-06, PTOL-03).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.application import browsing_tool
from autobots.application.approvals import ApprovalRefused, decide, expire, expire_due
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import Inheritance, admit_run, apply_command
from autobots.application.tool_definitions import (
    ApprovalPolicy,
    ToolContext,
    ToolDefinition,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from autobots.domain.tools import PLAN_TOOLS, OperationClass
from autobots.operations.job_dispatch import process_next
from checklib import Cases, Db, run_check
from goal_loop_script import ROUTE, Script, calls, say
from pydantic import BaseModel, ConfigDict

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
ACTOR = uuid4()
sent: list[str] = []
BROWSE = {'task': 'What is example.com for?', 'start_url': 'https://example.com/', 'allowed_domains': ['example.com']}


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


MOCK = ToolDefinition(tool_id='mock_send', version=1, description='Send a message to a controlled sink.', input_model=SendInput, output_model=SendOutput, approval=ApprovalPolicy(resource_target=lambda arguments: f'Mail to {arguments.to}'), operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=send)
SEND = ('mock_send', {'to': 'team@example.invalid', 'body': 'hello'})
CONFIG = LoopConfig(route=ROUTE, tools=(MOCK,), sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry)


class Approving:
    """One connection, the proposal later scenarios read, and the arrangements each scenario repeats."""

    def __init__(self, db: Any, cases: Cases) -> None:
        self.db, self.cases = db, cases
        self.d = Db(db, cases, WORKSPACE, ACTOR)
        registry = ToolRegistry()
        registry.register(MOCK)
        self.gateway = ToolGateway(registry)
        self.proposal: tuple[UUID, UUID, str] | None = None
        self.env: dict[str, str] = {}

    async def value(self, sql: str, *values: object) -> Any:
        return (await (await self.db.execute(sql, values)).fetchone())[0]

    async def admit(self, workspace: UUID = WORKSPACE, started_by: UUID = ACTOR, expert: tuple[UUID, int] | None = None) -> UUID:
        await self.db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        binding = SimpleNamespace(session_id=None, expert_id=expert[0] if expert else None, version=expert[1] if expert else None, instructions='', tools={**PLAN_TOOLS, 'mock_send': 1})
        return (await admit_run(self.db, workspace_id=workspace, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Send it', limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding, started_by=started_by)).run_id

    async def state(self, run: UUID) -> str:
        return await self.value('select status from public.runs where id = %s', run)

    async def approval(self, run: UUID) -> tuple[UUID, str]:
        row = await (await self.db.execute("select id, argument_hash from public.approval_requests where run_id = %s order by created_at desc limit 1", (run,))).fetchone()
        return row[0], row[1]

    async def advance(self, items: list[Any]) -> tuple[Any, Script]:
        model = Script(items=items, seen=[], bound=[])
        return await process_next(self.db, URL, 'worker', lambda: model, CONFIG), model

    @staticmethod
    def replies(model: Script, name: str = 'mock_send') -> list[dict[str, Any]]:
        return [json.loads(item.content) for messages in model.seen for item in messages if item.type == 'tool' and item.name == name]


async def consequential_call_waits_for_approval(ctx: Approving) -> None:
    """A proposal is persisted, the run waits, and nothing has happened. Later scenarios read this proposal."""
    admit, advance, approval, check, state, value = ctx.admit, ctx.advance, ctx.approval, ctx.cases.check, ctx.state, ctx.value
    run = await admit()
    result, model = await advance([calls(SEND), say('never')])
    check('a consequential call stores a proposal and waits', 'waiting_approval, no effect, 1 model call', (await state(run), sent, len(model.seen), result.outcome), await state(run) == 'waiting_approval' and sent == [] and len(model.seen) == 1 and result.outcome == 'waiting')
    check('the wait lets go of the job', 'done', await value('select status from app_private.run_jobs where run_id = %s', run), await value('select status from app_private.run_jobs where run_id = %s', run) == 'done')
    idle, _ = await advance([say('never')])
    check('a waiting run is not claimed', 'nothing to do', idle, idle is None)
    event = await value("select payload ->> 'type' from public.run_events where run_id = %s and payload ->> 'type' like 'approval%%' limit 1", run)
    check('the request is a public event', 'approval.requested', event, event == 'approval.requested')
    approval_id, argument_hash = await approval(run)
    ctx.proposal = run, approval_id, argument_hash


async def request_records_its_provenance(ctx: Approving) -> None:
    """US-13.1: who asked, under what scope and which policy, stored with the proposal."""
    check, db = ctx.cases.check, ctx.db
    _, approval_id, argument_hash = ctx.proposal
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


async def child_takes_the_parents_person(ctx: Approving) -> None:
    """A child run takes the person who started its parent, whatever actor admits it."""
    check, db, value = ctx.cases.check, ctx.db, ctx.value
    run, _, _ = ctx.proposal
    child = await admit_run(db, workspace_id=WORKSPACE, actor_id=run, idempotency_key=str(uuid4()), goal_text='A part of it', limit_micro_usd=1,
                            policy=resolve_role_policy(), started_by=uuid4(),
                            inherit=Inheritance(parent_run_id=run, root_run_id=run, snapshot={}, tools={'mock_send': 1}, paths=(), instructions='',
                                                session_id=None, expert_id=None, version=None))  # type: ignore[arg-type]
    inherited = await value('select started_by from public.runs where id = %s', child.run_id)
    check('a child run records its parent\'s person, not its admitting actor', str(ACTOR), inherited, inherited == ACTOR)
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")


async def tampering_is_refused(ctx: Approving) -> None:
    """Tampering and authority."""
    check, db, state = ctx.cases.check, ctx.db, ctx.state
    run, approval_id, argument_hash = ctx.proposal
    for label, options, code in (
            ('a changed hash', {'workspace_id': WORKSPACE, 'argument_hash': '0' * 64, 'decision': 'approve'}, 'approval_mismatch'),
            ('another workspace', {'workspace_id': OTHER, 'argument_hash': argument_hash, 'decision': 'approve'}, 'approval_not_found')):
        try:
            await decide(db, actor_id=ACTOR, approval_id=approval_id, idempotency_key=str(uuid4()), **options)
            check(f'{label} is refused', code, 'applied', False)
        except ApprovalRefused as error:
            check(f'{label} is refused', code, error.code, error.code == code)
    check('so the run still waits, with no effect', 'waiting_approval', (await state(run), sent), await state(run) == 'waiting_approval' and sent == [])


async def approval_releases_one_operation_once(ctx: Approving) -> None:
    """Approval releases only that operation, once, after a restart in a new process pass."""
    advance, approval, check, db, state, value = ctx.advance, ctx.approval, ctx.cases.check, ctx.db, ctx.state, ctx.value
    run, approval_id, argument_hash = ctx.proposal
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
    _, model = await advance([calls(changed), say('never')])
    check('the approved call runs once, from the replayed tool step, with no new model call before it', 'delivered once', sent, sent == ['hello'])
    check('the next model turn with changed arguments needs its own approval', 'waiting_approval, a second proposal', (await state(run), await value('select count(*) from public.approval_requests where run_id = %s', run)), await state(run) == 'waiting_approval' and await value('select count(*) from public.approval_requests where run_id = %s', run) == 2)
    check('and did not happen', 'still once', sent, sent == ['hello'])
    second_id, second_hash = await approval(run)
    await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=second_id, idempotency_key='a3', decision='reject', argument_hash=second_hash)
    _, model = await advance([calls(SEND), say('stop')])
    latest = [json.loads(item.content) for item in model.seen[-1] if item.type == 'tool' and item.name == 'mock_send']
    check('a rejection reaches the model as an observation, and never runs', 'approval_rejected, no effect', latest[-2]['code'], latest[-2]['code'] == 'approval_rejected' and sent == ['hello'])
    receipt = latest[-1]
    check('repeating the approved call reuses its receipt rather than sending again', 'succeeded, still once', receipt['outcome'], receipt['outcome'] == 'succeeded' and sent == ['hello'])


async def expiry_is_not_consent(ctx: Approving) -> None:
    """Expiry is not consent."""
    admit, advance, approval, check, db, replies, state, value = ctx.admit, ctx.advance, ctx.approval, ctx.cases.check, ctx.db, ctx.replies, ctx.state, ctx.value
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
    await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, expected_version=version)
    _, model = await advance([say('stop')])
    check('resuming tells the model it expired, and still sends nothing', 'approval_expired, no effect', (replies(model)[0]['code'], sent), replies(model)[0]['code'] == 'approval_expired' and sent == [])

    run = await admit()
    await advance([calls(SEND), say('never')])
    swept, _ = await approval(run)
    await db.execute("update public.approval_requests set expires_at = clock_timestamp() - interval '1 second' where id = %s", (swept,))
    await advance([say('never')])
    check('expiry is also applied by the worker\'s own pass', 'paused, expired', (await state(run), await value('select status from public.approval_requests where id = %s', swept)), await state(run) == 'paused' and await value('select status from public.approval_requests where id = %s', swept) == 'expired')
    left = await expire_due(db)
    check('with nothing left to expire', '0', left, left == 0)


async def pause_keeps_and_cancel_withdraws_the_wait(ctx: Approving) -> None:
    """A pause during the wait keeps the obligation, and a cancel withdraws the request."""
    admit, advance, approval, check, db, state, value = ctx.admit, ctx.advance, ctx.approval, ctx.cases.check, ctx.db, ctx.state, ctx.value
    run = await admit()
    await advance([calls(SEND), say('never')])
    waiting, waiting_hash = await approval(run)
    version = await value('select version from public.runs where id = %s', run)
    await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.PAUSE, expected_version=version)
    try:
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=waiting, idempotency_key='p1', decision='approve', argument_hash=waiting_hash)
        check('a paused run takes no decision', 'approval_run_not_waiting', 'applied', False)
    except ApprovalRefused as error:
        check('a paused run takes no decision', 'approval_run_not_waiting', error.code, error.code == 'approval_run_not_waiting')
    version = await value('select version from public.runs where id = %s', run)
    await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, expected_version=version)
    _, model = await advance([say('never')])
    check('resuming returns to the same wait, with no model call or new proposal', 'waiting_approval, 0 calls, 1 proposal', (await state(run), len(model.seen), await value('select count(*) from public.approval_requests where run_id = %s', run)), await state(run) == 'waiting_approval' and not model.seen and await value('select count(*) from public.approval_requests where run_id = %s', run) == 1)
    version = await value('select version from public.runs where id = %s', run)
    await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, expected_version=version)
    check('cancelling withdraws the request', 'withdrawn, no effect', (await value('select status from public.approval_requests where id = %s', waiting), sent), await value('select status from public.approval_requests where id = %s', waiting) == 'withdrawn' and sent == [])


async def approval_does_not_carry_to_a_changed_scope(ctx: Approving) -> None:
    """An approved operation can't run with a different scope."""
    admit, approval, check, db = ctx.admit, ctx.approval, ctx.cases.check, ctx.db
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


async def repeated_approved_browse_goal_waits_again(ctx: Approving) -> None:
    """Decisions 0018 B6 and 0020 L5: browse_goal leaves no receipt, so the call an approval releases uses it up, and
    the same call again waits for a person (PTOL-06). With no runtime bound, a released call fails
    browsing_unavailable before any container starts, so no executor or model is reached."""
    cases, check, d, db, state = ctx.cases, ctx.cases.check, ctx.d, ctx.db, ctx.state
    with cases.scenario('a repeated approved browse_goal call'):
        browse = ToolRegistry()
        browse.register(browsing_tool.browse_tool(None, qualified=lambda: True))
        browsing = ToolGateway(browse)
        browser_expert = uuid4()
        await db.execute('insert into public.experts (id, workspace_id, name, latest_version) values (%s, %s, %s, 1)',
                         (browser_expert, WORKSPACE, f'Browser {browser_expert.hex[:6]}'))
        # A run names an Expert version that exists (migration 60's composite key).
        await db.execute("insert into public.expert_versions (expert_id, version, config, created_by) values (%s, 1, '{}', %s)", (browser_expert, uuid4()))
        run = await d.admit('Browse twice', tools={'browse_goal': 1}, expert=(browser_expert, 1))
        lease = await d.claim(run)
        first = await browsing.execute(db, ToolScope(WORKSPACE, run, lease.generation, {'browse_goal': 1}), 'browse_goal', BROWSE)
        await d.approve(run)
        lease = await d.claim(run)
        scope = ToolScope(WORKSPACE, run, lease.generation, {'browse_goal': 1})
        released = await browsing.execute(db, scope, 'browse_goal', BROWSE)
        used = await d.row('select status, consumed_at is not null from public.approval_requests where run_id = %s', run)
        repeated = await browsing.execute(db, scope, 'browse_goal', BROWSE)
        after = await d.row('select status, consumed_at is null, decided_by is null, count(*) over () '
                            'from public.approval_requests where run_id = %s', run)
        check('repeating an approved browse_goal call waits for a person again',
              'approval_pending; released once (failed browsing_unavailable), its approval approved and consumed; '
              'then approval_pending, the one request pending, undecided and unconsumed, and the run waiting_approval',
              (first.code, released.outcome.value, released.code, used, repeated.code, after, await state(run)),
              lambda seen: seen == ('approval_pending', 'failed', 'browsing_unavailable', ('approved', True),
                                    'approval_pending', ('pending', True, True, 1), 'waiting_approval'))


async def expiry_racing_a_decision_changes_nothing(ctx: Approving) -> None:
    """An expiry pass that read a request as pending before a person decided it, or before its run was cancelled,
    changes nothing (PTOL-03). Arranged: that pass's expiry is applied after the decision or the cancel, so its
    guarded write finds the request already settled, as the waiting write does once the lock is released."""
    approval, cases, check, d, db = ctx.approval, ctx.cases, ctx.cases.check, ctx.d, ctx.db
    with cases.scenario('an expiry racing a decision or a cancel'):
        sending = ToolRegistry()
        sending.register(MOCK)
        raced = []
        for settle in ('approve', 'cancel'):
            run = await d.admit('Send it', tools={'mock_send': 1})
            lease = await d.claim(run)
            await ToolGateway(sending).execute(db, ToolScope(WORKSPACE, run, lease.generation, {'mock_send': 1}), *SEND)
            request, _ = await approval(run)
            if settle == 'approve':
                await d.approve(run)
            else:
                await d.command(run, RunCommand.CANCEL)
            facts = ('select a.status, r.status, r.event_sequence from public.approval_requests a '
                     'join public.runs r on r.id = a.run_id where a.id = %s')
            before = await d.row(facts, request)
            moved = await expire(db, request, run, WORKSPACE)
            raced.append((settle, moved, before, await d.row(facts, request)))
        check('an expiry that read a request as pending before its decision or cancel changes nothing',
              'not expired; approved stays approved and queued, withdrawn stays withdrawn and cancelled, no new event',
              raced, lambda seen: [(item[0], item[1], item[2] == item[3], item[3][:2]) for item in seen]
              == [('approve', False, True, ('approved', 'queued')), ('cancel', False, True, ('withdrawn', 'cancelled'))])


async def inbox_arranged_for_the_browser(ctx: Approving) -> None:
    """Left pending for the browser's inbox. The owner signs in there, so the owner started it, through an Expert.
    Its browser_env is what main returns."""
    admit, approval, check, db, gateway, value = ctx.admit, ctx.approval, ctx.cases.check, ctx.db, ctx.gateway, ctx.value
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    owner = await value("select user_id from public.workspace_members where workspace_id = %s and role = 'owner'", WORKSPACE)
    expert = uuid4()
    await db.execute("insert into public.experts (id, workspace_id, name, latest_version) values (%s, %s, 'Mail sender', 2)", (expert, WORKSPACE))
    # A run names an Expert version that exists (migration 60's composite key).
    await db.execute("insert into public.expert_versions (expert_id, version, config, created_by) values (%s, 1, '{}', %s), (%s, 2, '{}', %s)", (expert, owner, expert, owner))
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
    ctx.env = env


# In order: the four after consequential_call_waits_for_approval read its proposal, and the browser inbox is last.
SCENARIOS = (
    consequential_call_waits_for_approval,
    request_records_its_provenance,
    child_takes_the_parents_person,
    tampering_is_refused,
    approval_releases_one_operation_once,
    expiry_is_not_consent,
    pause_keeps_and_cancel_withdraws_the_wait,
    approval_does_not_carry_to_a_changed_scope,
    repeated_approved_browse_goal_waits_again,
    expiry_racing_a_decision_changes_nothing,
    inbox_arranged_for_the_browser,
)


async def main(cases: Cases) -> dict[str, object]:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        context = Approving(db, cases)
        for scenario in SCENARIOS:
            with cases.scenario(scenario.__name__):
                await scenario(context)
    return {'browser_env': context.env}


if __name__ == '__main__':
    run_check(main)
