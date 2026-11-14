"""Run work that can hold the interpreter lock in a child interpreter a timeout can stop (R-20).

A regular expression holds the lock while it matches, so `asyncio.to_thread` can't be stopped: the
event loop, the lease keeper and the status beat stall until it ends (PTOL-01). A child interpreter
is killed when its time runs out. It starts isolated (`-I`) and runs only the named module, so it
never re-imports the parent's main module, and the event loop writes and reads its pipes without
blocking (Decision 0027 D9).
"""

import asyncio
import contextlib
import math
import signal
import sys
from pathlib import Path

# The directory holding the `autobots` package, so the child runs this same source tree whatever
# put it on the parent's path.
SOURCE_ROOT = str(Path(__file__).resolve().parents[2])
# The child also caps its own CPU time, so the kernel stops it even if the parent is killed first.
# The soft limit sends SIGXCPU, which ends the child; it sits a second under the hard limit, since
# Linux kills outright when both are reached together. An inherited hard limit is never raised.
BOOTSTRAP = (
    "import resource, runpy, sys; "
    "soft = int(sys.argv[3]); inherited = resource.getrlimit(resource.RLIMIT_CPU)[1]; "
    "hard = soft + 1 if inherited == resource.RLIM_INFINITY else min(soft + 1, inherited); "
    "resource.setrlimit(resource.RLIMIT_CPU, (min(soft, hard), hard)); "
    "sys.path.insert(0, sys.argv[1]); "
    "runpy.run_module(sys.argv[2], run_name='__main__', alter_sys=True)"
)


class BoundExceeded(Exception):
    """The work ran past its time, and its process was killed."""


class ChildFailed(Exception):
    """The child ended without an answer."""


async def run_module(module: str, payload: bytes, seconds: float) -> bytes:
    """`python -m module` given `payload` on stdin, returning its stdout. Raises BoundExceeded
    after `seconds`, with the child killed and reaped, and ChildFailed when it exits non-zero."""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-B",
        "-c",
        BOOTSTRAP,
        SOURCE_ROOT,
        module,
        str(math.ceil(seconds) + 1),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(payload), seconds)
    except TimeoutError:
        raise BoundExceeded from None
    finally:
        # Also on cancellation, so no child outlives the call that started it.
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
    # The kernel's CPU limit ends a runaway match with SIGXCPU: that is running out of time too.
    if process.returncode == -signal.SIGXCPU:
        raise BoundExceeded
    if process.returncode != 0:
        raise ChildFailed(process.returncode)
    return output
