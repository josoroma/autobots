"""Block outbound sockets for the whole session, including imports done during collection."""

import socket
from typing import NoReturn


class SocketBlockedError(RuntimeError):
    """A test or an imported package tried to reach the network."""


def _refuse(*_args: object, **_kwargs: object) -> NoReturn:
    raise SocketBlockedError("network access is blocked in these tests")


# Replaced at import, so third-party module-level code runs under the block too. Local socket pairs
# used by the event loop never connect, so they keep working.
socket.socket.connect = _refuse  # type: ignore[method-assign]
socket.socket.connect_ex = _refuse  # type: ignore[method-assign]
socket.socket.sendto = _refuse  # type: ignore[method-assign]
socket.create_connection = _refuse
socket.getaddrinfo = _refuse
