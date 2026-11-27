"""US-23.3 on a real database: a workspace's Model source, switched to Local and back on a workspace
of its own, with OpenRouter's saved choices kept, every role on the Local default, a run frozen on
Local, a role override refused, a linked new run admitted on Local, and the worker's refusal of a
run frozen on the source switched off (Decision 0041 A1, A8, A12). JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from uuid import uuid4

import psycopg
from autobots.application.model_policy import read_model_policy, save_model_policy
from autobots.application.model_source import save_local_default, switch_model_source
from autobots.application.run_admission import PolicyNotOffered, saved_workspace_policy
from autobots.application.runs import admit_run
from autobots.application.worker_inference import InferenceSource, frozen_policy
from autobots.domain.models import PROFILES, ModelProfileId, ModelSource, limits_for
from psycopg.types.json import Jsonb

URL = os.environ['AUTOBOTS_DATABASE_URL']
BONSAI = ModelProfileId.LOCAL_BONSAI_2_5.value
INKLING = ModelProfileId.LOCAL_INKLING_2_MINI.value
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        workspace = uuid4()
        await db.execute('insert into public.workspaces (id, name) values (%s, %s)', (workspace, 'Model source'))
        saved = await save_model_policy(db, workspace, expected_version=0, default_profile='openrouter_sol',
                                        role_overrides={'coder': 'openrouter_terra'})
        start = await read_model_policy(db, workspace)
        check('a workspace starts on OpenRouter with its saved choices', 'openrouter, Sol, coder on Terra',
              (start.model_source, start.default_profile, dict(start.role_overrides)),
              start.model_source is ModelSource.OPENROUTER and start.default_profile == 'openrouter_sol'
              and dict(start.role_overrides) == {'coder': 'openrouter_terra'})

        local = await switch_model_source(db, workspace, expected_version=saved.version, source=ModelSource.LOCAL,
                                          local_profile=None)
        check('a switch to Local keeps the offered local default and OpenRouter\'s choices',
              'local, Bonsai 2.5, Sol and coder on Terra kept',
              (local.model_source, local.local_profile, local.default_profile, dict(local.role_overrides)),
              local.model_source is ModelSource.LOCAL and local.local_profile == BONSAI
              and local.default_profile == 'openrouter_sol' and dict(local.role_overrides) == {'coder': 'openrouter_terra'})

        policy = (await saved_workspace_policy(db, workspace)).for_new_work(require_offer=True)
        run = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                              goal_text='on Local', limit_micro_usd=1000, policy=policy)
        snapshot: dict[str, Any] = (await (await db.execute(
            'select policy_snapshot from public.runs where id = %s', (run.run_id,))).fetchone())[0]
        check('a run on Local freezes every role on the Local default, with its route',
              'every role Bonsai 2.5, its route frozen',
              (set(snapshot['bindings'].values()), sorted(snapshot['routes'])),
              set(snapshot['bindings'].values()) == {BONSAI} and sorted(snapshot['routes']) == [BONSAI])

        try:
            (await saved_workspace_policy(db, workspace)).for_new_work(
                run_role_overrides={'researcher': BONSAI}, require_offer=True)
            refused = 'admitted'
        except PolicyNotOffered as error:
            refused = error.code
        check('on Local a run that names a role override is refused', 'model_not_offered', refused,
              refused == 'model_not_offered')

        ended = uuid4()
        await db.execute(
            'insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot) '
            "values (%s, %s, 'cancelled', 'ended on OpenRouter', 1000, %s)",
            (ended, workspace, Jsonb({'version': 1, 'bindings': {'executor': 'openrouter_terra'}})))
        linked = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                 goal_text='continued', limit_micro_usd=1000, policy=policy, continues_run_id=ended)
        continued: dict[str, Any] = (await (await db.execute(
            'select policy_snapshot from public.runs where id = %s', (linked.run_id,))).fetchone())[0]
        check('a run ended on OpenRouter continues as a linked new run on Local', 'executor Bonsai 2.5',
              continued['bindings'].get('executor'), continued['bindings'].get('executor') == BONSAI)

        source = InferenceSource(URL, None, None)  # type: ignore[arg-type]  # the refusal reads neither
        on_openrouter = frozen_policy({'version': 1, 'bindings': {'executor': 'openrouter_terra'}})
        refusal, _ = await source._refusal(db, workspace, on_openrouter)
        check('on Local, a run frozen on OpenRouter is refused before anything is sent', 'model_source_disabled',
              refusal, refusal == 'model_source_disabled')

        back = await switch_model_source(db, workspace, expected_version=local.version, source=ModelSource.OPENROUTER,
                                         local_profile=None)
        check('switching back restores OpenRouter\'s saved choices', 'openrouter, Sol, coder on Terra',
              (back.model_source, back.default_profile, dict(back.role_overrides)),
              back.model_source is ModelSource.OPENROUTER and back.default_profile == 'openrouter_sol'
              and dict(back.role_overrides) == {'coder': 'openrouter_terra'})
        on_local = frozen_policy({'version': 1, 'bindings': {'executor': BONSAI}})
        refusal, _ = await source._refusal(db, workspace, on_local)
        check('on OpenRouter, a run frozen on Local is refused too', 'model_source_disabled', refusal,
              refusal == 'model_source_disabled')

        # US-23.8: with Inkling 2 Mini offered too (migration 72), either is the Local default, and it answers every role.
        async def frozen(goal: str) -> dict[str, Any]:
            policy = (await saved_workspace_policy(db, workspace)).for_new_work(require_offer=True)
            admitted = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                       goal_text=goal, limit_micro_usd=1000, policy=policy)
            return (await (await db.execute('select policy_snapshot from public.runs where id = %s',
                                            (admitted.run_id,))).fetchone())[0]

        inkling = await switch_model_source(db, workspace, expected_version=back.version, source=ModelSource.LOCAL,
                                            local_profile=ModelProfileId.LOCAL_INKLING_2_MINI)
        on_inkling = await frozen('on Inkling')
        cap = limits_for(PROFILES[ModelProfileId.LOCAL_INKLING_2_MINI]).output_tokens
        check('a switch to Local can choose Inkling 2 Mini, and it answers every role', 'every role Inkling 2 Mini, 8,192 tokens',
              (inkling.local_profile, set(on_inkling['bindings'].values()), cap),
              inkling.local_profile == INKLING and set(on_inkling['bindings'].values()) == {INKLING} and cap == 8_192)
        bonsai = await save_local_default(db, workspace, expected_version=inkling.version,
                                          local_profile=ModelProfileId.LOCAL_BONSAI_2_5)
        on_bonsai = await frozen('on Bonsai')
        cap = limits_for(PROFILES[ModelProfileId.LOCAL_BONSAI_2_5]).output_tokens
        check('saving Bonsai 2.5 as the Local default moves the next run to it', 'every role Bonsai 2.5, 4,096 tokens',
              (bonsai.local_profile, set(on_bonsai['bindings'].values()), cap),
              bonsai.local_profile == BONSAI and set(on_bonsai['bindings'].values()) == {BONSAI} and cap == 4_096)
        await switch_model_source(db, workspace, expected_version=bonsai.version, source=ModelSource.OPENROUTER,
                                  local_profile=None)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
