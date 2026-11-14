"""US-15.8, arranged for the Models browser spec on a disposable stack. JSON out.

The owner's workspace saves no default and one role override, as the policy PUT writes it. A run
is admitted through a direct session whose Expert binds the executor to Sol, through the same
binding, policy and admission code the run route uses, as admission through the API needs a key.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID, uuid4

import psycopg
from autobots.application.experts import create_expert, create_session, resolve_binding
from autobots.application.runs import admit_run
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.domain.models import resolve_role_policy

URL = os.environ['AUTOBOTS_DATABASE_URL']


async def main() -> None:
    workspace, owner = UUID(sys.argv[1]), UUID(sys.argv[2])
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await db.execute(
            'insert into app_private.model_policies (workspace_id, version, default_profile, role_overrides) '
            "values (%s, 1, null, '{\"coder\": \"openrouter_terra\"}')", (workspace,))
        expert = await create_expert(db, workspace_id=workspace, actor_id=owner, idempotency_key=str(uuid4()),
                                     name='Sol executor', config=ExpertConfig(tools=['calculate'],
                                                                             role_bindings={'executor': 'openrouter_sol'}))
        session = await create_session(db, workspace_id=workspace, actor_id=owner, idempotency_key=str(uuid4()),
                                       kind='direct', experts=[SessionExpert(expert_id=expert.id)])
        binding = await resolve_binding(db, workspace, session.id)
        row = await (await db.execute('select default_profile, role_overrides from app_private.model_policies '
                                      'where workspace_id = %s', (workspace,))).fetchone()
        policy = resolve_role_policy(run_role_overrides=binding.role_bindings, workspace_default=row[0],
                                     workspace_role_overrides=row[1])
        accepted = await admit_run(db, workspace_id=workspace, actor_id=owner, started_by=owner,
                                   idempotency_key=str(uuid4()), goal_text='Where each binding comes from',
                                   limit_micro_usd=1_000_000, binding=binding, policy=policy)
        snapshot = (await (await db.execute('select policy_snapshot from public.runs where id = %s',
                                            (accepted.run_id,))).fetchone())[0]
    print(json.dumps({'run_id': str(accepted.run_id), 'sources': snapshot.get('sources', {})}))


asyncio.run(main())
