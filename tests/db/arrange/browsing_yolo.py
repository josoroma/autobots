"""US-17.1, arranged for the Settings → Browsing browser spec on a disposable stack. JSON out.

`unseen <workspace>` makes Home's one-time YOLO notice pending again for that workspace, as for one
whose owner hasn't opened Home since the setting shipped (Decision 0035 Y1), with YOLO on. Other
suites open Home as this owner too, so the spec can't rely on being first.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID

import psycopg

URL = os.environ['AUTOBOTS_DATABASE_URL']


async def main() -> None:
    action, workspace = sys.argv[1], UUID(sys.argv[2])
    if action != 'unseen':
        raise SystemExit(f'unknown action {action}')
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await db.execute(
            'insert into app_private.browsing_settings (workspace_id) values (%s) on conflict (workspace_id) do update '
            'set notice_seen_at = null, yolo = true, version = app_private.browsing_settings.version + 1',
            (workspace,))
    print(json.dumps({'action': action}))


if __name__ == '__main__':
    asyncio.run(main())
