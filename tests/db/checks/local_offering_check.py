"""US-23.7 and US-23.8 on a real database: Bonsai 2.5's and Inkling 2 Mini's route qualifications as
migrations 70 and 72 store them, read the way Settings reads them, and the Local source's offering from
them (Decision 0041 A7, A18). JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date
from typing import Any

import psycopg
from autobots.application.local_offering import local_offers
from autobots.application.provider_settings import read_route_qualifications
from autobots.domain.models import OFFERED_FOR_NEW_RUNS, PROFILES, ModelProfileId

URL = os.environ['AUTOBOTS_DATABASE_URL']
BONSAI = PROFILES[ModelProfileId.LOCAL_BONSAI_2_5]
CAVEAT = "Concurrent admission on a live route wasn't tested."
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        row = await (await db.execute(
            "select canonical_id, status, qualified_on::text, evidence, limits from agent_runtime.route_qualifications "
            "where profile = 'local_bonsai_2_5_27b'")).fetchone()
        canonical, status, qualified_on, evidence, limits = row if row else (None,) * 5
        check("Bonsai 2.5's stored qualification is migration 70's", 'qualified_with_limits on 2026-11-27, from US-23.2 and US-23.7, for its own canonical ID',
              (status, qualified_on, evidence), canonical == BONSAI.canonical_id and status == 'qualified_with_limits'
              and qualified_on == '2026-11-27' and evidence == 'US-23.2, US-23.7')
        check('its limits list what stays disabled and the concurrency caveat', 'schema_nested 0 of 3, and SQLI-12', limits,
              limits is not None and 'schema_nested passed 0 of 3' in limits and CAVEAT in limits
              and 'tool_required' not in limits and 'tool_named_conflict' not in limits)
        offers = {offer.profile: offer for offer in local_offers(await read_route_qualifications(db))}
        bonsai, inkling = offers[ModelProfileId.LOCAL_BONSAI_2_5], offers[ModelProfileId.LOCAL_INKLING_2_MINI]
        check('the Local source offers Bonsai 2.5 from its stored row, with its date and limits', 'offered, 2026-11-27',
              (bonsai.offered, bonsai.qualified_on), bonsai.offered and bonsai.qualified_on == date(2026, 11, 27) and bonsai.limits == limits)
        # US-23.8: migration 72 stores Inkling 2 Mini's qualification, so it is offered beside Bonsai 2.5.
        check('the Local source offers Inkling 2 Mini too, with its date and limits', 'offered, 2026-11-27, schema_nested',
              (inkling.offered, inkling.qualified_on), inkling.offered and inkling.qualified_on == date(2026, 11, 27)
              and inkling.limits is not None and 'schema_nested passed 2 of 3' in inkling.limits and CAVEAT in inkling.limits)
        check('on OpenRouter, neither local profile is offered', 'neither in OFFERED_FOR_NEW_RUNS', sorted(p.value for p in OFFERED_FOR_NEW_RUNS),
              ModelProfileId.LOCAL_BONSAI_2_5 not in OFFERED_FOR_NEW_RUNS and ModelProfileId.LOCAL_INKLING_2_MINI not in OFFERED_FOR_NEW_RUNS)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
