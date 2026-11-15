"""Admission receipts replay across refactor plan R-30, on a real database through the runtime role.

Each digest is a golden fingerprint from services/agent/tests/test_run_admission.py, captured from the
admission code before R-30 changed it. A receipt stored with one must replay its stored result, the same
key with other content must be refused (SP-012), and a fresh admission must store that digest. JSON cases
through checklib. No model call.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Coroutine
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from autobots.application.experts import RunBinding
from autobots.application.runs import (
    AdmissionResult,
    Fresh,
    IdempotencyConflict,
    Inheritance,
    Inherited,
    RunAdmission,
    RunGrant,
    admit,
    admit_run,
)
from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from checklib import Cases, Db, run_check

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
SESSION = UUID('0a000000-0000-4000-8000-000000000004')
EXPERT = UUID('0a000000-0000-4000-8000-000000000005')
PARENT = UUID('0a000000-0000-4000-8000-000000000006')
ROOT = UUID('0a000000-0000-4000-8000-000000000007')
EARLIER = UUID('0a000000-0000-4000-8000-000000000008')
PLAN = {'propose_plan': 1, 'complete_task': 1, 'read_offload': 1}
LOOP = {**PLAN, 'calculate': 1}
# FINGERPRINTS from services/agent/tests/test_run_admission.py, captured before R-30. Never edit these
# values. The unit test's api_repeat is left out: its goal is read from the earlier run before the receipt,
# and that run's id is in the digest, so no stored receipt can stand in for it here.
FINGERPRINTS = {
    'api_goal': '02dcf43b990efa771bb5388e781285f8ddc257d00940fb4a092de9f8f3aed8b0',
    'api_goal_in_full': '55f01a25319233c2b77d5ca75803eaede62a25db6cc0b888fba8d4ed377bd876',
    'api_session_expert': 'ccfd8da273b1da7ce44cd283e8062e1d54308e355ee650592394df2a7b5b4139',
    'api_continue': '8a9f176f03200f64b7e83605c83d883b0b10ca7c58ce552ed032649ec7599d4d',
    'routine_expert': '2268da0744d82d6bbd1256239769d447f3430b4120c1cfce70e49ef07b7a90a2',
    'workflow': '7a5534586a99a49f4759560eabbb6d462012940422fbc900e0cbf829b8c24711',
    'improvement_replay': '0eaadb43bff660a43cff07cea52cb35aabd349292e44d9b34995b7c73fbca7cc',
    'browse_trial': 'c02b68d1da0733957599b82ac3cf18ec8f5725b9a9179f9f90e3ddf593dc6d60',
    'assignment_child': 'c245e43a12216d4d1b1e43af7e727853634940fce6c9c017f8b965827052b5e3',
}
# The shapes whose content names no other row, so a fresh admission can store them.
FRESH = ('api_goal', 'api_goal_in_full', 'improvement_replay')
RECEIPT = ('select request_hash from app_private.idempotency_receipts where workspace_id = %s and actor_id = %s '
           "and operation = 'admit_run' and target = %s and idempotency_key = %s")
STORE = ('insert into app_private.idempotency_receipts (workspace_id, actor_id, operation, target, idempotency_key, '
         "request_hash, result) values (%s, %s, 'admit_run', %s, %s, %s, %s)")


def caller_shapes() -> dict[str, dict[str, Any]]:
    """The unit test's shapes, keyword for keyword, in the form the golden digests were captured from."""
    policy = resolve_role_policy()
    return {
        'api_goal': {'started_by': ACTOR, 'goal_text': 'Write the report', 'limit_micro_usd': 1_000_000, 'policy': policy},
        'api_goal_in_full': {
            'started_by': ACTOR, 'goal_text': '  Compare the two tables  ', 'limit_micro_usd': 250_000,
            'policy': resolve_role_policy(run_profile='openrouter_terra'),
            'acceptance_criteria': ('  Names the larger total ', '   ', 'Shows the difference'),
            'required_artifacts': (RequiredArtifact(name='report.md', must_contain=['Total', 'Difference']),),
            'input_documents': (InputDocument(path='inputs/notes.txt', content='plain notes'),
                                InputDocument(path='inputs/table.csv', content='a,b\n1,2', media_type='text/csv')),
            'run_profile': 'openrouter_terra'},
        'api_session_expert': {
            'started_by': ACTOR, 'goal_text': 'Summarize the inputs', 'limit_micro_usd': 1_000_000, 'policy': policy,
            'acceptance_criteria': ('Cites a source',),
            'binding': RunBinding(session_id=SESSION, expert_id=EXPERT, version=3, instructions='Be brief.',
                                  tools={**PLAN, 'calculate': 1, 'web_search': 1}, role_bindings={'researcher': 'openrouter_terra'})},
        'api_continue': {'started_by': ACTOR, 'goal_text': 'Try again with the figures', 'limit_micro_usd': 1_000, 'policy': policy,
                         'continues_run_id': EARLIER},
        'routine_expert': {
            'goal_text': 'Check the overnight figures', 'limit_micro_usd': 500_000, 'policy': policy,
            'binding': SimpleNamespace(session_id=None, expert_id=EXPERT, version=2, instructions='Routine instructions\n\nReference: a skill',
                                       tools={**PLAN, 'calculate': 1})},
        'workflow': {
            'started_by': ACTOR, 'goal_text': 'Workflow Weekly digest, version 4', 'limit_micro_usd': 750_000, 'policy': policy,
            'input_documents': (InputDocument(path='inputs/brief.md', content='# Brief', media_type='text/markdown'),),
            'binding': SimpleNamespace(session_id=SESSION, expert_id=None, version=None, instructions='',
                                       tools={**LOOP, 'assign_specialist': 1, 'workflow_approval': 1})},
        'improvement_replay': {
            'started_by': ACTOR, 'goal_text': 'Find the quarterly figure', 'limit_micro_usd': 100_000,
            'acceptance_criteria': ('States the figure',), 'policy': policy,
            'binding': SimpleNamespace(session_id=None, expert_id=None, version=None,
                                       instructions='Reference skill:\nfigures:\nRead the table first.', tools=dict(LOOP))},
        'browse_trial': {
            'goal_text': 'Live browse trial', 'limit_micro_usd': 1_000_000, 'policy': policy,
            'binding': type('Binding', (), {'session_id': None, 'expert_id': EXPERT, 'version': 1, 'instructions': '',
                                            'tools': {**PLAN, 'browse_goal': 1}})()},
        'assignment_child': {
            'goal_text': 'Total the second table', 'limit_micro_usd': 20_000, 'acceptance_criteria': ('Gives the total',),
            'inherit': Inheritance(parent_run_id=PARENT, root_run_id=ROOT, snapshot={'version': 1, 'bindings': {'coordinator': 'openrouter_terra'}},
                                   tools={'calculate': 1}, paths=('inputs', 'outputs/child-1'), instructions='Child instructions',
                                   session_id=SESSION, expert_id=EXPERT, version=3)},
    }


Admit = Callable[[Db, str, str], Coroutine[Any, Any, AdmissionResult]]


async def by_keywords(db: Db, shape: str, key: str) -> AdmissionResult:
    """The keyword call the database checks make."""
    return await admit_run(db.connection, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=key, **caller_shapes()[shape])


async def by_request(db: Db, shape: str, key: str) -> AdmissionResult:
    """The typed request the callers build, with a RunGrant for a routine, a workflow, a replay or a trial."""
    options = dict(caller_shapes()[shape])
    inherit, binding = options.pop('inherit', None), options.pop('binding', None)
    policy, started_by = options.pop('policy', None), options.pop('started_by', None)
    if binding is not None and not isinstance(binding, RunBinding):
        binding = RunGrant(instructions=binding.instructions, tools=binding.tools, session_id=binding.session_id,
                           expert_id=binding.expert_id, version=binding.version)
    origin = Inherited(inherit) if inherit is not None else Fresh(policy, binding, started_by)
    return await admit(db.connection, RunAdmission(workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=key, origin=origin, **options))


WAYS: dict[str, Admit] = {'keywords': by_keywords, 'request': by_request}


async def fresh_admissions_store_the_golden_digest(db: Db, way: str, call: Admit) -> list[UUID]:
    """A run admitted now stores the golden digest, and its repeat replays it."""
    admitted = []
    for shape in FRESH:
        with db.cases.scenario(f'{way}, {shape}: a fresh admission'):
            key = f'fresh-{uuid4()}'
            first = await call(db, shape, key)
            admitted.append(first.run_id)
            stored = await db.value(RECEIPT, WORKSPACE, ACTOR, str(WORKSPACE), key)
            db.cases.check(f'{way}, {shape}: admission stores the golden fingerprint', FINGERPRINTS[shape], stored,
                           stored == FINGERPRINTS[shape])
            again = await call(db, shape, key)
            db.cases.check(f'{way}, {shape}: the same key and content replay the first run', f'replayed {first.run_id}',
                           f'replayed={again.replayed} {again.run_id}', again.replayed and again.run_id == first.run_id)
            written = (await db.value('select count(*) from public.runs where id = %s', first.run_id),
                       await db.value('select count(*) from app_private.run_jobs where run_id = %s', first.run_id),
                       await db.value('select count(*) from public.run_events where run_id = %s', first.run_id),
                       await db.value('select count(*) from app_private.goal_specs where run_id = %s', first.run_id))
            db.cases.check(f'{way}, {shape}: one run, job, first event and goal', '(1, 1, 1, 1)', written, written == (1, 1, 1, 1))
    return admitted


async def stored_receipts_replay(db: Db, way: str, call: Admit, run: UUID) -> None:
    """A receipt stored with a golden digest replays its stored result and writes no run."""
    for shape in sorted(FINGERPRINTS):
        with db.cases.scenario(f'{way}, {shape}: a stored receipt'):
            key = f'stored-{uuid4()}'
            result = {'run_id': str(run), 'version': 1, 'status': 'queued'}
            await db.connection.execute(STORE, (WORKSPACE, ACTOR, str(WORKSPACE), key, FINGERPRINTS[shape], json.dumps(result)))
            before = await db.value('select count(*) from public.runs where workspace_id = %s', WORKSPACE)
            replayed = await call(db, shape, key)
            after = await db.value('select count(*) from public.runs where workspace_id = %s', WORKSPACE)
            db.cases.check(f'{way}, {shape}: a receipt stored with the golden digest replays', f'replayed {run}, no new run',
                           f'replayed={replayed.replayed} {replayed.run_id}, {after - before} new runs',
                           replayed.replayed and replayed.run_id == run and after == before)
    with db.cases.scenario(f'{way}: a stored receipt of other content'):
        key = f'other-{uuid4()}'
        result = {'run_id': str(run), 'version': 1, 'status': 'queued'}
        await db.connection.execute(STORE, (WORKSPACE, ACTOR, str(WORKSPACE), key, FINGERPRINTS['api_goal'], json.dumps(result)))
        await db.cases.refused(f'{way}: the same key with other content is refused, not replayed', 'idempotency_conflict',
                               call(db, 'routine_expert', key), IdempotencyConflict)


async def main(cases: Cases) -> None:
    async with Db.connect(URL, cases, WORKSPACE, ACTOR) as db:
        admitted: list[UUID] = []
        for way, call in WAYS.items():
            admitted += await fresh_admissions_store_the_golden_digest(db, way, call)
        if not admitted:
            raise RuntimeError('no run was admitted, so no stored receipt can name one')
        for way, call in WAYS.items():
            await stored_receipts_replay(db, way, call, admitted[0])
        # These runs exist only for their receipts, so none is left for a later check's worker to claim.
        for run in admitted:
            await db.command(run, RunCommand.CANCEL)


run_check(main)
