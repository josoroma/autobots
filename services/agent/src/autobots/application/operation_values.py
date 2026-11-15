"""Numbers Local Operations shows about this Mac and a workspace (Decision 0022 D5, LM-07).

Each is a number or a yes or no, never an address, path or secret, and producing one sends nothing
off this Mac.
"""

import errno
import ipaddress
import os
import shutil
import socket
import stat
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import UUID

from autobots.application.sql import SqlConnection, one


async def stored_bytes(connection: SqlConnection, workspace_id: UUID) -> int:
    """This workspace's published artifact bytes in Storage, from their recorded sizes."""
    (stored,) = await one(
        connection,
        "select coalesce(sum(size_bytes), 0)::bigint from public.artifacts "
        "where workspace_id = %s and status = 'published'",
        (workspace_id,),
    )
    return int(stored)


def disk_bytes(path: Path) -> tuple[int, int] | None:
    """Free and total bytes of the disk under the app's data. Numbers only, never the path."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return int(usage.free), int(usage.total)


def _is_loopback(address: str) -> bool:
    try:
        return ipaddress.ip_address(address.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def loopback_only(fds: Iterable[int] | None = None) -> bool | None:
    """Whether every TCP socket this process listens on is bound to loopback. It reads this
    process's own sockets and sends nothing. None when it finds no listening socket, as under a
    test client, or the platform won't say."""
    try:
        descriptors = [int(name) for name in os.listdir("/dev/fd")] if fds is None else list(fds)
    except OSError:
        return None
    bound: list[str] = []
    for fd in descriptors:
        # Only sockets are looked at, and none is duplicated or closed: macOS kills a process that
        # duplicates or closes one of its guarded descriptors, such as the event loop's kqueue.
        try:
            if not stat.S_ISSOCK(os.fstat(fd).st_mode):
                continue
            probe = socket.socket(fileno=fd)
        except OSError:
            continue
        address: Any = None
        try:
            if probe.type != socket.SOCK_STREAM or probe.family not in (
                socket.AF_INET,
                socket.AF_INET6,
            ):
                continue
            address = probe.getsockname()
            if address[1] == 0:
                continue
            # A connection has a peer. A bound socket without one is a listener, since macOS
            # doesn't answer SO_ACCEPTCONN.
            probe.getpeername()
            continue
        except OSError as error:
            if error.errno != errno.ENOTCONN or address is None:
                continue
            bound.append(str(address[0]))
        finally:
            # Hands the descriptor back untouched, as this probe never owned it.
            probe.detach()
    if not bound:
        return None
    return all(_is_loopback(address) for address in bound)
