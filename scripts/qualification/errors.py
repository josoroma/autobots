"""One exception for each exit code a check reports besides a failed case (AGENTS.md Commands, SCRP-08).

toolchain.py and disposable_db.py import these, so a script that calls both catches one Unavailable.
"""
from __future__ import annotations


class Refused(Exception):
    """A target or request was refused before any change. Exit code 1."""

    exit_code = 1


class Unavailable(Exception):
    """A prerequisite is missing: Docker, a pinned tool or image, a prepared environment, or an arrangement
    nothing after it could do without. Exit code 2."""

    exit_code = 2
