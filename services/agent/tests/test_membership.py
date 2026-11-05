"""The membership store with no database. Real queries run in scripts/qualify_identity.py."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from autobots.api.membership import PostgresMembership


@pytest.mark.asyncio
async def test_no_pool_fails_closed() -> None:
    store = PostgresMembership(SimpleNamespace(pool=None))
    assert await store.is_member(uuid4(), uuid4()) is False
    assert await store.workspaces_for(uuid4()) == []
