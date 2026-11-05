"""What `scripts/live_goal.py` does with the real key, in a process of its own so the runner never holds it.

Reads only OPENROUTER_API_KEY from the named file, and prints only numbers or counts. The key check and
the usage read are OpenRouter's free metadata calls, not inference.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from uuid import UUID

import httpx
import psycopg

from autobots.api.main import provider_context_from_environment
from autobots.application.provider_settings import ProviderSettings
from autobots.operations.route_qualification import read_key

USAGE_URL = 'https://openrouter.ai/api/v1/key'


async def save(key_file: str, workspace: str) -> None:
    """The real save path, including OpenRouter's own check of the key."""
    context = provider_context_from_environment()
    assert context is not None
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        settings = ProviderSettings(db, context)
        status = await settings.status(UUID(workspace))
        await settings.save_credential(UUID(workspace), read_key(Path(key_file)).get_secret_value(), status.settings_version)


async def usage(key_file: str) -> None:
    """The key's whole spend as OpenRouter reports it, in US dollars."""
    headers = {'Authorization': f'Bearer {read_key(Path(key_file)).get_secret_value()}'}
    async with httpx.AsyncClient(timeout=30) as client:
        reply = await client.get(USAGE_URL, headers=headers)
    reply.raise_for_status()
    print(reply.json()['data']['usage'])


async def leaks(key_file: str, logs: str) -> None:
    """How many durable rows and log files hold the key. Counts only, so the key can't reach a report."""
    secret = read_key(Path(key_file)).get_secret_value()
    found = 0
    queries = ('select blob from agent_runtime.checkpoint_blobs', 'select blob from agent_runtime.checkpoint_writes',
               'select payload::text from public.run_events', 'select result::text from app_private.tool_receipts',
               'select content from app_private.run_files', 'select accumulated_output from app_private.model_invocations')
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        for query in queries:
            cursor = await db.execute(query)
            for (value,) in await cursor.fetchall():
                text = bytes(value).decode(errors='replace') if isinstance(value, (bytes, memoryview)) else str(value)
                found += secret in text
    written = sum(secret in path.read_text(errors='replace') for path in Path(logs).glob('*.log'))
    print(f'{found} {written}')


COMMANDS = {'save': save, 'usage': usage, 'leaks': leaks}

if __name__ == '__main__':
    asyncio.run(COMMANDS[sys.argv[1]](*sys.argv[2:]))
