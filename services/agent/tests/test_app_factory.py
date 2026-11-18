"""The factory stays pure: no resources, no network and no credential."""

import json
import socket
from pathlib import Path

import pytest

from autobots.api.app import create_app
from conftest import SocketBlockedError

REPOSITORY = Path(__file__).resolve().parents[3]


def test_sockets_are_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.create_connection(("127.0.0.1", 9))
    with socket.socket() as probe, pytest.raises(SocketBlockedError):
        probe.connect(("127.0.0.1", 9))


def test_the_schema_builds_without_any_connection() -> None:
    """With sockets blocked and no key, the factory builds every path the committed contract
    holds, which the contract_drift step pins, and no other (PTST-14)."""
    committed = json.loads((REPOSITORY / "contracts/generated/openapi.json").read_text())
    assert set(create_app().openapi()["paths"]) == set(committed["paths"])


def test_each_call_builds_a_new_app() -> None:
    assert create_app() is not create_app()


@pytest.mark.asyncio
async def test_lifespan_enters_and_leaves() -> None:
    app = create_app()
    stages = []
    async with app.router.lifespan_context(app):
        stages.append("entered")
    stages.append("left")
    assert stages == ["entered", "left"]
