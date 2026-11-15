"""What every operator command shares: its exit codes, refusals and argument types (POPS-14).

Exit codes follow AGENTS.md Commands: 0 done; 1 refused, with nothing created or sent unless the
message says what was; 2 a setting or argument the command can't run with. A refusal is one line on
stderr, `REFUSED: <reason>`, and a missing or malformed setting `ERROR: <what to set>`, as the
service's own entry points say it (`composition.stop_unconfigured`). Standard output keeps the JSON
result that wrappers parse.
"""

import argparse
import sys
from collections.abc import Callable
from uuid import UUID

from autobots.application.readiness import MalformedSetting
from autobots.operations.composition import unconfigured

EXIT_REFUSED = 1


class Refused(Exception):
    """A command stopped before it created or sent anything. The message says why, and never holds
    a secret or a value read from a file."""


def command(run: Callable[[], int]) -> int:
    """Runs one command, and turns the stops its code raises into the shared exit codes."""
    try:
        return run()
    except MalformedSetting as error:
        return unconfigured(error)
    except Refused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        return EXIT_REFUSED


def uuid_argument(text: str) -> UUID:
    """For argparse's `type=`: a malformed identifier is a usage error, exit 2, not a traceback."""
    try:
        return UUID(text)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a UUID") from None


def counts_argument(text: str) -> dict[str, int]:
    """For argparse's `type=`: `name=count` pairs, as `refusal=3,schema_nested=1`. Each count is a
    whole number above 0, and an empty text is no pairs."""
    counts: dict[str, int] = {}
    for item in filter(None, (part.strip() for part in text.split(","))):
        name, separator, count = item.partition("=")
        if not separator or not name.strip() or not count.strip().isdigit() or int(count) < 1:
            raise argparse.ArgumentTypeError(f"expected name=count pairs, as refusal=3: {item}")
        counts[name.strip()] = int(count)
    return counts
