"""What a child run shows, and how its parent records it, against a real database. JSON cases.

Found as N-2, N-8 and N-9 by US-11.12's review, defined in
docs/engineering/evidence/US-11.12/review-r1-open-findings.md. Named review_check.py until refactor plan
R-66 named it for its behavior."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.loop_middleware import ModelRoute
from autobots.application import loop_policy
from autobots.application.compaction import SUMMARY_MARKER, CompactionPolicy
from autobots.application.experts import create_expert
from autobots.application.model_admission import ModelAdmission, ledger_usage
from autobots.application.operations import REQUIRED_COLUMNS, database_conditions
from autobots.application.plans import load_goal
from autobots.application.routines import RoutineRefused, admit_occurrence, routine_record
from autobots.application.run_lifecycle import LoopConfig, settle_children
from autobots.application.run_projection import read_inspector, read_summary, read_workspace
from autobots.application.runs import LinkRefused, admit_run
from autobots.application.worker_leases import claim_run
from autobots.application.workflow_executions import create_execution
from autobots.application.workflows import (
    WorkflowRefused,
    create_workflow,
    publish_version,
)
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.routines import RoutineConfig, RoutineTarget
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.models import resolve_role_policy
from autobots.operations.job_dispatch import drive_lease
from goal_loop_script import Script, calls, say

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
cases: list[dict] = []


class Aware(Script):
    """Answers a summary request itself, so the working script only holds the work."""

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **options: Any) -> Any:
        if SUMMARY_MARKER in str(messages[-1].content):
            self.items.insert(0, say('arranged summary'))
        return super()._generate(messages, stop, run_manager, **options)


class OnePool:
    """`database_conditions` takes a pool, and this is the real database behind one."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def connection(self) -> Any:
        connection = self._connection

        class Held:
            async def __aenter__(self) -> Any:
                return connection

            async def __aexit__(self, *_: Any) -> None:
                return None

        return Held()


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:300], 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def admitted(text: str, limit: int = 1000) -> UUID:
            accepted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text=text, limit_micro_usd=limit, policy=resolve_role_policy())
            return accepted.run_id

        parent, child = await admitted('Parent'), await admitted('Child')
        await db.execute('update public.runs set root_run_id = %s, parent_run_id = %s where id = %s', (parent, parent, child))
        # N-9: a call a child made shows on the child, though the root holds the budget.
        invocation = uuid4()
        await db.execute("insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day, reserved_micro_usd, charged_micro_usd, status) "
                         "values (%s, %s, %s, %s, 'executor', 'openrouter_terra', 'fixture/model', 1, current_date, 100, 25, 'succeeded')", (invocation, WORKSPACE, parent, child))
        summary = await read_summary(db, WORKSPACE, child)
        check("a child's spend is its own, not 0", '25', summary.budget.spent_micro_usd, summary.budget.spent_micro_usd == 25)
        root = await read_summary(db, WORKSPACE, parent)
        check("the root still counts it, once", '25', root.budget.spent_micro_usd, root.budget.spent_micro_usd == 25)

        # Decision 0029 F10: a depth-2 tree, every call carrying the top root as its children inherit it. The root shows
        # what admission counts against it, and each child the calls it made itself (N-9). The old view formula gives the
        # same figures for these runs, so this pins agreement and N-9; run_list_check's seeded ledger is the case that
        # fails under the old formula. Its own workspace, finished runs with no jobs and no active call, so it holds no
        # inference slot and leaves nothing a later check could claim.
        depth = uuid4()
        await db.execute('insert into public.workspaces (id, name) values (%s, %s)', (depth, f'Depth {depth.hex[:6]}'))
        top, middle, leaf = uuid4(), uuid4(), uuid4()
        for run, above in ((top, None), (middle, top), (leaf, middle)):
            await db.execute("insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, "
                             "parent_run_id, root_run_id) values (%s, %s, 'succeeded', 'Depth', 1000, '{}', %s, %s)",
                             (run, depth, above, None if above is None else top))
        for run, status, reserved, charged in ((top, 'succeeded', 50, 10), (middle, 'succeeded', 60, 20), (middle, 'uncertain', 30, None),
                                               (leaf, 'uncertain', 40, None), (leaf, 'succeeded', 70, 5)):
            await db.execute("insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day, "
                             "reserved_micro_usd, charged_micro_usd, status) values (%s, %s, %s, %s, 'executor', 'openrouter_terra', 'fixture/model', 1, "
                             'current_date, %s, %s, %s)', (uuid4(), depth, top, run, reserved, charged, status))
        counted = (await ledger_usage(db, depth, top, datetime.now(UTC).date())).root_micro_usd
        figures = {}
        for name, run in (('top', top), ('middle', middle), ('leaf', leaf)):
            shown = await read_summary(db, depth, run)
            figures[name] = (shown.budget.spent_micro_usd, shown.budget.reserved_micro_usd) if shown else None
        check('the root of a depth-2 tree shows what admission counts against it (the old formula agrees here)',
              f'{counted} = 105, as 35 charged and 70 reserved', (counted, figures['top']), counted == 105 and figures['top'] == (35, 70))
        check("each child's spend is its own calls, not its subtree's and not 0 (the old formula agrees here)",
              'middle 20 and 30, leaf 5 and 40', figures, figures['middle'] == (20, 30) and figures['leaf'] == (5, 40))

        # N-2: settling a finished child records how it really ended.
        expert = uuid4()
        await db.execute("insert into public.experts (id, workspace_id, name, latest_version) values (%s, %s, %s, 1)", (expert, WORKSPACE, f'Review {expert}'))
        await db.execute("insert into public.expert_versions (expert_id, version, config, created_by) values (%s, 1, '{}', %s)", (expert, uuid4()))
        await db.execute("update public.runs set status = 'succeeded' where id = %s", (child,))
        assignment = uuid4()
        await db.execute("insert into app_private.assignments (id, workspace_id, parent_run_id, child_run_id, root_run_id, operation_id, depth, expert_id, expert_version) values (%s, %s, %s, %s, %s, %s, 1, %s, 1)",
                         (assignment, WORKSPACE, parent, child, parent, f'review-{assignment}', expert))
        lease = await claim_run(db, parent, worker_id='review')
        await settle_children(db, lease)
        outcome = (await (await db.execute('select outcome from app_private.assignments where id = %s', (assignment,))).fetchone())[0]
        check('a child that succeeded is recorded as having succeeded', 'succeeded', outcome, outcome == 'succeeded')

        # R2-3: who supplied a reconciled charge, and whether the outcome was ever in doubt.
        async def uncertain(failure: str) -> tuple[UUID, UUID]:
            run = await admitted('Reconciled')
            call = uuid4()
            await db.execute("insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, attempt, spend_day, reserved_micro_usd, status, failure_class) "
                             "values (%s, %s, %s, %s, 'executor', 'openrouter_terra', 'fixture/model', 1, current_date, 100, 'uncertain', %s)", (call, WORKSPACE, run, run, failure))
            return run, call

        async def shown(run: UUID) -> Any:
            return (await read_inspector(db, WORKSPACE, run)).model_calls[0]

        run, call = await uncertain('worker_lost')
        await ModelAdmission(db).reconcile(call, 30)
        seen = await shown(run)
        check("an owner's charge on a lost call is theirs, and the outcome is unknown", 'entered by the owner, outcome unknown', (seen.reconciled, seen.outcome_unknown), seen.reconciled and seen.outcome_unknown)
        run, call = await uncertain('worker_lost')
        await ModelAdmission(db).reconcile(call, 30, source='provider')
        seen = await shown(run)
        check("a provider's late report isn't called the owner's", 'not entered, outcome known', (seen.reconciled, seen.outcome_unknown, seen.status), not seen.reconciled and not seen.outcome_unknown and seen.status == 'succeeded')
        run, call = await uncertain('worker_lost')
        await ModelAdmission(db).reconcile(call, 30)
        await db.execute('update app_private.model_invocations set charge_source = null where id = %s', (call,))
        seen = await shown(run)
        check('a row from before the source was recorded claims neither', 'not the owner, outcome not claimed, source unknown', (seen.reconciled, seen.outcome_unknown, seen.charge_source_unknown), not seen.reconciled and not seen.outcome_unknown and seen.charge_source_unknown)
        run, call = await uncertain('charge_not_reported')
        await ModelAdmission(db).reconcile(call, 30)
        seen = await shown(run)
        check('a call that worked, with only its charge missing, has a known outcome', 'entered by the owner, outcome known', (seen.reconciled, seen.outcome_unknown), seen.reconciled and not seen.outcome_unknown)

        # R2-2, R2-10: continuing repeats the stored goal whole, and only for a goal run of its own.
        long_goal = 'Keep every word of this goal. ' * 40
        ended = await admitted(long_goal)
        await db.execute("update public.runs set status = 'failed' where id = %s", (ended,))
        view = await read_workspace(db, WORKSPACE, ended)
        check('the page has only a cut copy of a long goal', 'at most 500 characters', len(view.objective or ''), 0 < len(view.objective or '') <= 500 < len(long_goal))
        check('a finished goal run can continue', 'true', view.can_continue, view.can_continue)
        linked = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text=None, limit_micro_usd=1_000, policy=resolve_role_policy(), continues_run_id=ended)
        spec = await load_goal(db, linked.run_id)
        link = (await (await db.execute('select continues_run_id from public.runs where id = %s', (linked.run_id,))).fetchone())[0]
        check('a continued run gets the whole stored goal, and the link', 'the same goal, linked', (len(spec.original_request), link == ended), spec.original_request == long_goal and link == ended)
        check('a finished child offers no continuing', 'false', (await read_workspace(db, WORKSPACE, child)).can_continue, not (await read_workspace(db, WORKSPACE, child)).can_continue)
        try:
            await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text=None, limit_micro_usd=1_000, policy=resolve_role_policy(), continues_run_id=child)
            check("a child's goal can't be repeated on a budget of its own", 'refused', 'admitted', False)
        except LinkRefused as refusal:
            check("a child's goal can't be repeated on a budget of its own", 'refused', str(refusal)[:60], True)

        # R2-10: a workflow's run has no goal of its own to repeat.
        graph = {'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}}, {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
                 'links': [{'source': 'in', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}]}
        actor = uuid4()
        flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), name=f'Review {uuid4().hex[:6]}')
        await publish_version(db, workspace_id=WORKSPACE, actor_id=actor, workflow_id=flow.id, idempotency_key=str(uuid4()), expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')
        execution = await create_execution(db, workspace_id=WORKSPACE, actor_id=actor, workflow_id=flow.id, idempotency_key=str(uuid4()), version=1, inputs={'in': 'x'})
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where run_id = %s", (execution.run_id,))
        await db.execute("update public.runs set status = 'failed' where id = %s", (execution.run_id,))
        offers = (await read_workspace(db, WORKSPACE, execution.run_id)).can_continue
        check("a finished workflow's run offers no continuing", 'false', offers, not offers)
        try:
            await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text=None, limit_micro_usd=1_000, policy=resolve_role_policy(), continues_run_id=execution.run_id)
            check("a workflow's stored text can't be repeated as a goal", 'refused', 'admitted', False)
        except LinkRefused as refusal:
            check("a workflow's stored text can't be repeated as a goal", 'refused', str(refusal)[:60], True)

        # N-8: a child shows what it froze, not what its Expert says today.
        await db.execute("insert into public.expert_versions (expert_id, version, config, created_by) values (%s, 2, %s, %s)", (expert, json.dumps({'role_bindings': {'executor': 'openrouter_deepseek_flash'}}), uuid4()))
        await db.execute("update public.runs set expert_id = %s, expert_version = 2, policy_snapshot = jsonb_set(policy_snapshot, '{bindings,executor}', '\"openrouter_terra\"') where id = %s", (expert, child))
        binding = (await read_workspace(db, WORKSPACE, child)).expert
        shown_route = binding.role_bindings.get('executor') if binding else None
        check("a child's Expert card shows the model it froze", 'openrouter_terra, though the Expert names another', shown_route, shown_route == 'openrouter_terra')

        # E-4, on real catalogs: a column that isn't there reads as behind, and the real ones don't.
        conditions = await database_conditions(OnePool(db))
        check('the columns a migration added are all present', 'no schema_behind', [item.code for item in conditions], 'schema_behind' not in [item.code for item in conditions])
        from autobots.application import operations
        operations.REQUIRED_COLUMNS = (*REQUIRED_COLUMNS, ('public.runs', 'no_such_column'))
        conditions = await database_conditions(OnePool(db))
        operations.REQUIRED_COLUMNS = REQUIRED_COLUMNS
        check('a column-only migration not applied reads as behind', 'schema_behind', [item.code for item in conditions], 'schema_behind' in [item.code for item in conditions])

        # WI-2, R2-1: the real call sites reserve past the worst case, for work and for a summary.
        big = await admitted('Reserve for the real request', 1_000_000)
        worst = 1_000
        route = ModelRoute('executor', 'openrouter_terra', 'fixture/model', worst, 1_000_000)
        assumed = loop_policy.RESERVED_PROMPT_TOKENS
        loop_policy.RESERVED_PROMPT_TOKENS = 1
        try:
            calc = ('calculate', {'operation': 'sum', 'values': [1, 2]})
            model = Aware(items=[calls(calc), calls(calc), calls(calc), calls(calc), calls(calc), say('done')], seen=[], bound=[])
            config = LoopConfig(route=route, compaction=CompactionPolicy(context_chars=200, large_tool_chars=1000, keep_recent=2), sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry)
            # This exact run, so the jobs of the suites around it stay as they are.
            ran = await drive_lease(db, URL, await claim_run(db, big, worker_id='reserving'), lambda: model, config)
        finally:
            loop_policy.RESERVED_PROMPT_TOKENS = assumed
        rows = await (await db.execute('select role, min(reserved_micro_usd) from app_private.model_invocations where run_id = %s group by role', (big,))).fetchall()
        found = dict(rows)
        check('a call larger than assumed reserves past the worst case', f'over {worst}', (found.get('executor'), ran.code, ran.run_status), (found.get('executor') or 0) > worst)
        check('and so does a summary', f'over {worst}', found.get('summarizer'), (found.get('summarizer') or 0) > worst)

        # R3-2: a request that could reach a rate nothing was reserved at isn't sent.
        tiered = await admitted('Past the tier', 1_000_000)
        model = Aware(items=[say('never')], seen=[], bound=[])
        result = await drive_lease(db, URL, await claim_run(db, tiered, worker_id='tiered'), lambda: model, LoopConfig(route=ModelRoute('executor', 'openrouter_terra', 'fixture/model', 1_000, 1_000_000, 1), sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry))
        check('a request that could reach a higher tier is refused before sending', 'cost_unavailable, no call', (result.code, len(model.seen)), result.code == 'cost_unavailable' and not model.seen)

        # US-12.1: a saved choice naming DeepSeek refuses new work, with no substitute and no rewrite.
        chooser = uuid4()
        await db.execute("insert into public.workspaces (id, name) values (%s, 'Saved DeepSeek')", (chooser,))
        await db.execute("insert into app_private.model_policies (workspace_id, version, default_profile, role_overrides) values (%s, 1, 'openrouter_deepseek_flash', '{}')", (chooser,))
        saved_flow = await create_workflow(db, workspace_id=chooser, actor_id=actor, idempotency_key=str(uuid4()), name=f'Saved {uuid4().hex[:6]}')
        await publish_version(db, workspace_id=chooser, actor_id=actor, workflow_id=saved_flow.id, idempotency_key=str(uuid4()), expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')
        # With no agent step it calls no model, so a saved choice can't stop it.
        plain = await create_execution(db, workspace_id=chooser, actor_id=actor, workflow_id=saved_flow.id, idempotency_key=str(uuid4()), version=1, inputs={'in': 'x'})
        check('a workflow with no agent step still runs under a saved DeepSeek default', 'admitted', plain.run_id, bool(plain.run_id))
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where run_id = %s", (plain.run_id,))
        helper = await create_expert(db, workspace_id=chooser, actor_id=actor, idempotency_key=str(uuid4()), name=f'Saved helper {uuid4().hex[:6]}', config=ExpertConfig(tools=['calculate']), catalog=tool_registry.catalog())
        agent_graph = {'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}}, {'id': 'ask', 'block': 'agent', 'version': 1, 'config': {'expert_id': str(helper.id)}}, {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
                       'links': [{'source': 'in', 'source_port': 'value', 'target': 'ask', 'target_port': 'goal'}, {'source': 'ask', 'source_port': 'result', 'target': 'out', 'target_port': 'value'}]}
        agent_flow = await create_workflow(db, workspace_id=chooser, actor_id=actor, idempotency_key=str(uuid4()), name=f'Saved agent {uuid4().hex[:6]}')
        await publish_version(db, workspace_id=chooser, actor_id=actor, workflow_id=agent_flow.id, idempotency_key=str(uuid4()), expected_version=0, graph=WorkflowGraph.model_validate(agent_graph), source='user')
        started_before = (await (await db.execute('select count(*) from public.runs where workspace_id = %s', (chooser,))).fetchone())[0]
        try:
            await create_execution(db, workspace_id=chooser, actor_id=actor, workflow_id=agent_flow.id, idempotency_key=str(uuid4()), version=1, inputs={'in': 'x'})
            check("a workflow with an agent step under a saved DeepSeek default is refused", 'model_not_offered', 'admitted', False)
        except WorkflowRefused as refused:
            check("a workflow with an agent step under a saved DeepSeek default is refused", 'model_not_offered', refused.code, refused.code == 'model_not_offered')
        started = (await (await db.execute('select count(*) from public.runs where workspace_id = %s', (chooser,))).fetchone())[0] - started_before
        kept = (await (await db.execute('select default_profile, version from app_private.model_policies where workspace_id = %s', (chooser,))).fetchone())
        check('no run started, and the saved choice stands', "0 runs, still DeepSeek at version 1", (started, kept), started == 0 and kept == ('openrouter_deepseek_flash', 1))
        lover = await create_expert(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), name=f'Saved binding {uuid4().hex[:6]}', config=ExpertConfig(tools=['calculate'], role_bindings={'executor': 'openrouter_deepseek_flash'}), catalog=tool_registry.catalog())
        routine = routine_record(RoutineConfig(target=RoutineTarget(kind='expert', id=lover.id, version=1), goal='Scheduled work', trigger={'kind': 'interval', 'minutes': 60}, limit_micro_usd=500))
        before_runs = (await (await db.execute('select count(*) from public.runs where workspace_id = %s', (WORKSPACE,))).fetchone())[0]
        try:
            await admit_occurrence(db, WORKSPACE, uuid4(), 1, routine, datetime(2026, 1, 1, tzinfo=UTC), catalog=tool_registry.catalog())
            check("an occurrence on a saved Expert binding is refused", 'model_not_offered', 'admitted', False)
        except RoutineRefused as refused:
            after_runs = (await (await db.execute('select count(*) from public.runs where workspace_id = %s', (WORKSPACE,))).fetchone())[0]
            check("an occurrence on a saved Expert binding is refused", 'model_not_offered, no run', (refused.code, after_runs - before_runs), refused.code == 'model_not_offered' and after_runs == before_runs)

        # R5-4: a scripted model's tool arguments holding a lone surrogate, the way one could arrive.
        odd = await admitted('A model that returns a lone surrogate', 1_000_000)
        task = {'id': 'a', 'title': 'T', 'criteria': ['c1'], 'expected_evidence': 'a file'}
        model = Aware(items=[calls(('propose_plan', {'tasks': [task]})), calls(('calculate', {'operation': 'sum', 'values': [1, 2], 'note': 'x\ud83dy'})), say('after'), say('after')], seen=[], bound=[])
        odd_lease = await claim_run(db, odd, worker_id='surrogate')
        try:
            outcome = await drive_lease(db, URL, odd_lease, lambda: model, LoopConfig(route=ModelRoute('executor', 'openrouter_terra', 'fixture/model', 1_000, 1_000_000), sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry))
            ended = (outcome.run_status, outcome.code)
        except Exception as raised:  # noqa: BLE001 - what the worker's loop would see.
            ended = ('raised', type(raised).__name__)
        reserved_rows = await (await db.execute('select count(*) from app_private.model_invocations where run_id = %s', (odd,))).fetchone()
        status_now = (await (await db.execute('select status from public.runs where id = %s', (odd,))).fetchone())[0]
        check('a lone surrogate from a model ends the run truthfully, with nothing more reserved', 'failed, request_unencodable, and neither a reservation nor a call after it', (ended, status_now, reserved_rows[0], len(model.seen)), ended == ('failed', 'request_unencodable') and status_now == 'failed' and reserved_rows[0] == 2 and len(model.seen) == 2)

        # R5-4: whether a lone surrogate can arrive. A goal can't be stored with one.
        try:
            await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='before \ud83d after', limit_micro_usd=1000, policy=resolve_role_policy())
            check('a goal holding a lone surrogate never reaches a model', 'refused on the way in', 'stored', False)
        except (UnicodeEncodeError, psycopg.Error, ValueError) as refused:
            check('a goal holding a lone surrogate never reaches a model', 'refused on the way in', type(refused).__name__, True)
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
