"""US-14.9: what a run holds under inputs/, by path, media type and size, for a browser test."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import psycopg


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        cursor = await db.execute("select path, media_type, octet_length(content) from app_private.run_files "
                                  "where run_id = %s and path like 'inputs/%%' order by path", (sys.argv[1],))
        print(json.dumps([{'path': row[0], 'media_type': row[1], 'bytes': row[2]} for row in await cursor.fetchall()]))


asyncio.run(main())
