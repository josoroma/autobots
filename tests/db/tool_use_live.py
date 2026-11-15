"""US-14.4: one more gateway call on an arranged, claimed run, made while a browser watches it."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID

import psycopg
from autobots.adapters.tool_registry import build_registry
from autobots.application.tool_definitions import ToolScope
from autobots.application.tool_gateway import ToolGateway


async def main() -> None:
    run_id, generation, workspace = UUID(sys.argv[1]), int(sys.argv[2]), UUID(sys.argv[3])
    scope = ToolScope(workspace, run_id, generation, {'calculate': 1, 'save_artifact': 1}, ('inputs', 'outputs'))
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        result = await ToolGateway(build_registry(None)).execute(db, scope, 'save_artifact', {'path': 'outputs/live.md', 'content': 'written live'})
    print(json.dumps({'outcome': result.outcome.value, 'code': result.code}))


asyncio.run(main())
