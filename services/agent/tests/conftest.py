"""Block outbound sockets for the whole session, including imports done during collection.

An inherited provider key is removed too, so no test can read a developer's real key.
"""

import logging
import os
import socket
from collections.abc import Iterator
from typing import TYPE_CHECKING, NoReturn

import pytest

if TYPE_CHECKING:
    from fake_api import ApiClient

os.environ.pop("OPENROUTER_API_KEY", None)


class SocketBlockedError(RuntimeError):
    """A test or an imported package tried to reach the network."""


def _refuse(*_args: object, **_kwargs: object) -> NoReturn:
    raise SocketBlockedError("network access is blocked in these tests")


# Replaced at import, so third-party module-level code runs under the block too. Local socket pairs
# used by the event loop never connect, so they keep working.
socket.socket.connect = _refuse  # type: ignore[method-assign]  # the block replaces the method on purpose
socket.socket.connect_ex = _refuse  # type: ignore[method-assign]  # the block replaces the method on purpose
socket.socket.sendto = _refuse  # type: ignore[method-assign]  # the block replaces the method on purpose
socket.create_connection = _refuse
socket.getaddrinfo = _refuse


@pytest.fixture
def api_client() -> Iterator["ApiClient"]:
    """The app in process, its lifespan running, over a fake membership, a fake pool and signed
    sessions (refactor plan R-31, PAPI-15). Imported here, so the app's imports run under the
    block above."""
    from fake_api import ApiClient

    with ApiClient.started() as client:
        yield client


# Every logger configure_logging (autobots/logs.py) or uvicorn's own configuration changes.
CONFIGURED_LOGGERS = ("", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx")


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """Puts back each configured logger's handlers, level, propagation and disabled flag after a
    test that configures logging, so no later test logs into its stream (refactor plan R-66,
    PTST-07)."""
    loggers = [logging.getLogger(name) for name in CONFIGURED_LOGGERS]
    saved = [
        (item, list(item.handlers), item.level, item.propagate, item.disabled) for item in loggers
    ]
    yield
    for logger, handlers, level, propagate, disabled in saved:
        logger.handlers[:] = handlers
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled
