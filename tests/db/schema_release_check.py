"""US-16.2: the schema check on a real database, as the runtime role. qualify_identity arranges each
state as the stack's admin and restores it afterwards; this reads what readiness and Operations see.

Argument: equal, behind, ahead, no-history or no-history-missing. JSON cases out.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import psycopg
from autobots.application.operations import applied_migrations, database_conditions, is_ready
from autobots.application.schema_release import SHIPPED_MIGRATIONS

URL = os.environ['AUTOBOTS_DATABASE_URL']
STATE = sys.argv[1]
EXPECTED = {
    'equal': ('ok', 'schema_ready', True, SHIPPED_MIGRATIONS),
    'behind': ('unavailable', 'schema_behind', False, SHIPPED_MIGRATIONS - 1),
    'ahead': ('degraded', 'schema_ahead', True, SHIPPED_MIGRATIONS + 1),
    'no-history': ('ok', 'schema_ready', True, None),
    'no-history-missing': ('unavailable', 'schema_behind', False, None),
}
WORDS = {
    'equal': f'{SHIPPED_MIGRATIONS} applied of {SHIPPED_MIGRATIONS} shipped',
    'behind': f'{SHIPPED_MIGRATIONS - 1} applied of {SHIPPED_MIGRATIONS} shipped',
    'ahead': f'{SHIPPED_MIGRATIONS + 1} applied of {SHIPPED_MIGRATIONS} shipped',
    'no-history': 'no readable history, every required object present',
    'no-history-missing': 'no readable history, and plan_task_times (migration 48) missing',
}


class OnePool:
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


async def main() -> None:
    state, code, ready, applied = EXPECTED[STATE]
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        conditions = await database_conditions(OnePool(db))
        schema = conditions[1]
        # What Operations reads for its value line: the same count, through the same function.
        counted = await applied_migrations(db)
    observed = {'schema': f'{schema.state} {schema.code}', 'admission_ready': is_ready(conditions), 'applied': counted,
                'shipped': SHIPPED_MIGRATIONS, 'other_blocking': [f'{item.name} {item.code}' for item in conditions if item.name != 'schema' and item.state != 'ok']}
    # Admission is is_ready over the blocking checks; only the schema's effect on it is judged here.
    admission = is_ready([schema])
    passed = (schema.state, schema.code) == (state, code) and admission == ready and counted == applied
    cases = [{'id': f'schema readiness, {WORDS[STATE]}', 'expected': f'{state} {code}, admission {"open" if ready else "stopped"} by it, applied {applied}',
              'observed': json.dumps(observed), 'passed': passed}]
    print(json.dumps({'cases': cases}))


asyncio.run(main())
