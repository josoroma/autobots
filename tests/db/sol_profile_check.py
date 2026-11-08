"""US-14.15 on a real database: Sol's rows, researcher's resolution and frozen runs. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg

from autobots.application.experts import create_expert, create_session
from autobots.application.runs import Inheritance, admit_run
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.application.worker_inference import frozen_policy
from autobots.domain.models import ModelRole, UnknownModelProfile, require_offered, resolve_role_policy

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        row = await value("select canonical_id || ' ' || wire_id || ' ' || label from public.model_profiles where profile_id = 'openrouter_sol'")
        qualified = await value("select status || ' ' || qualified_on::text || ' ' || evidence from agent_runtime.route_qualifications where profile = 'openrouter_sol'")
        check("Sol's profile row and its route qualification are stored", 'Sol row, qualified_with_limits on 2026-11-08, from US-14.15 and US-16.4',
              (row, qualified), row == 'openai/gpt-6.1-sol-20260929 openai/gpt-6.1-sol Sol' and qualified == 'qualified_with_limits 2026-11-08 US-14.15, US-16.4')

        async def admitted(policy: Any) -> dict[str, Any]:
            require_offered(policy.bindings.values())
            result = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='browse',
                                     limit_micro_usd=1000, policy=policy)
            snapshot: dict[str, Any] = await value('select policy_snapshot from public.runs where id = %s', result.run_id)
            snapshot['run_id'] = str(result.run_id)
            return snapshot

        plain = await admitted(resolve_role_policy())
        others = {role: bound for role, bound in plain['bindings'].items() if role != 'researcher'}
        check('a run with no model choice freezes researcher on Sol and every other role on Terra', 'researcher Sol, 13 roles Terra, Sol route frozen',
              (plain['bindings']['researcher'], set(others.values()), plain['routes'].get('openrouter_sol')),
              plain['bindings']['researcher'] == 'openrouter_sol' and set(others.values()) == {'openrouter_terra'} and len(others) == 13
              and plain['routes'].get('openrouter_sol') == {'wire_id': 'openai/gpt-6.1-sol', 'canonical_id': 'openai/gpt-6.1-sol-20260929'})
        named = await admitted(resolve_role_policy(run_profile='openrouter_sol'))
        check('a run naming Sol is admitted', 'every role Sol', set(named['bindings'].values()), set(named['bindings'].values()) == {'openrouter_sol'})
        choices = {
            'a run role override': resolve_role_policy(run_role_overrides={'researcher': 'openrouter_terra'}),
            'a run-wide profile': resolve_role_policy(run_profile='openrouter_terra'),
            'a workspace role override': resolve_role_policy(workspace_role_overrides={'researcher': 'openrouter_terra'}),
            'a workspace default': resolve_role_policy(workspace_default='openrouter_terra'),
        }
        frozen = {label: (await admitted(policy))['bindings']['researcher'] for label, policy in choices.items()}
        check('any explicit choice of Terra wins over the researcher default', 'researcher Terra in each', frozen,
              set(frozen.values()) == {'openrouter_terra'})
        written = await db.execute("select pg_get_constraintdef(oid) from pg_constraint where conname in "
                                   "('model_policies_default_profile_check', 'model_invocations_profile_check', 'model_profiles_profile_id_check')")
        definitions = [item[0] for item in await written.fetchall()]
        check('every profile check admits Sol', 'three checks naming openrouter_sol', definitions,
              len(definitions) == 3 and all('openrouter_sol' in definition for definition in definitions))

        parent = UUID(plain['run_id'])
        snapshot = {key: item for key, item in plain.items() if key != 'run_id'}
        expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), name=f'Researcher {uuid4().hex[:6]}',
                                     config=ExpertConfig(tools=['calculate']))
        session = await create_session(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), kind='direct',
                                       experts=[SessionExpert(expert_id=expert.id)])
        child = await admit_run(db, workspace_id=WORKSPACE, actor_id=parent, idempotency_key=str(uuid4()), goal_text='child', limit_micro_usd=100,
                                inherit=Inheritance(parent_run_id=parent, root_run_id=parent, snapshot=snapshot, tools={}, paths=('outputs',),
                                                    instructions='', session_id=session.id, expert_id=expert.id, version=1))
        inherited = await value('select policy_snapshot from public.runs where id = %s', child.run_id)
        resumed = frozen_policy(inherited)
        check("a child and a resumed run keep the parent's frozen Sol route", 'researcher Sol after inheritance and on resume',
              (inherited['bindings']['researcher'], resumed.bindings[ModelRole.RESEARCHER].value),
              inherited == snapshot and resumed.bindings[ModelRole.RESEARCHER].value == 'openrouter_sol')
        moved = dict(snapshot, routes=dict(snapshot['routes'], openrouter_sol={'wire_id': 'openai/gpt-6.1-sol-pro', 'canonical_id': 'openai/gpt-6.1-sol-pro-20260929'}))
        try:
            frozen_policy(moved)
            refused = 'resumed'
        except UnknownModelProfile:
            refused = 'stopped'
        check('a run frozen on Sol stops rather than move if the profile points elsewhere', 'stopped', refused, refused == 'stopped')
    print(json.dumps({'cases': cases}))


asyncio.run(main())
