"""Run work that can hold the interpreter lock in a child process a timeout can stop (R-20).

A regular expression holds the lock while it matches, so `asyncio.to_thread` can't be stopped: the
event loop, the lease keeper and the status beat stall until it ends (PTOL-01). A spawned process
is terminated when its time runs out, and the loop only waits on a pipe meanwhile.
"""

import asyncio
import multiprocessing
from collections.abc import Callable
from multiprocessing.connection import Connection
from typing import Any


class BoundExceeded(Exception):
    """The work ran past its time, and its process was stopped."""


def _child(sender: Connection, work: Callable[..., Any], args: tuple[Any, ...]) -> None:
    try:
        sender.send((True, work(*args)))
    except Exception as error:  # noqa: BLE001 - the parent re-raises it as it was
        sender.send((False, error))
    finally:
        sender.close()


async def run_in_child[T](work: Callable[..., T], *args: object, seconds: float) -> T:
    """`work(*args)` in a spawned process, or BoundExceeded after `seconds`. `work` must be
    importable from a light module, and its arguments and result picklable."""
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_child, args=(sender, work, args), daemon=True)
    process.start()
    sender.close()
    try:
        # Waiting on the pipe releases the lock, so the event loop keeps running meanwhile.
        if not await asyncio.to_thread(receiver.poll, seconds):
            raise BoundExceeded
        succeeded, value = receiver.recv()
    finally:
        if process.is_alive():
            process.terminate()
        await asyncio.to_thread(process.join, 1.0)
        receiver.close()
    if not succeeded:
        raise value
    result: T = value
    return result
