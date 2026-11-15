"""Operator commands agree on refusals, exit codes and argument parsing (POPS-14, AGENTS.md
Commands): 0 done, 1 refused, 2 a setting or argument the command can't run with."""

import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from uuid import UUID

import psycopg
import pytest

from autobots.application.readiness import MalformedSetting
from autobots.operations import concept_seed
from autobots.operations import route_qualification as rq
from autobots.operations.cli import Refused, command, counts_argument, uuid_argument
from sql_fakes import ScriptedConnection

WORKSPACE = "a0000000-0000-4000-8000-000000000001"


def test_a_refusal_is_one_line_and_exit_1(capsys: pytest.CaptureFixture[str]) -> None:
    def refuses() -> int:
        raise Refused("the cap is spent, so nothing was sent")

    assert command(refuses) == 1
    printed = capsys.readouterr()
    assert (printed.out, printed.err) == ("", "REFUSED: the cap is spent, so nothing was sent\n")


def test_a_setting_to_set_is_one_line_and_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    def unconfigured() -> int:
        raise MalformedSetting("set AUTOBOTS_DATABASE_URL")

    assert command(unconfigured) == 2
    assert capsys.readouterr().err == "ERROR: set AUTOBOTS_DATABASE_URL\n"


def test_a_command_that_finishes_keeps_its_own_code() -> None:
    assert command(lambda: 0) == 0


def test_an_unexpected_failure_is_not_turned_into_a_refusal() -> None:
    def breaks() -> int:
        raise RuntimeError("a defect")

    with pytest.raises(RuntimeError):
        command(breaks)


def test_identifiers_and_counts_parse_or_are_usage_errors() -> None:
    assert uuid_argument(WORKSPACE) == UUID(WORKSPACE)
    with pytest.raises(argparse.ArgumentTypeError):
        uuid_argument("not-a-uuid")
    assert counts_argument("") == {}
    assert counts_argument("refusal=3, schema_nested=1") == {"refusal": 3, "schema_nested": 1}
    for malformed in ("refusal", "refusal=", "=3", "refusal=0", "refusal=two", "refusal=-1"):
        with pytest.raises(argparse.ArgumentTypeError):
            counts_argument(malformed)


def test_a_malformed_rerun_list_is_a_usage_error_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["route_qualification", "--out", "x", "--only", "refusal"])
    with pytest.raises(SystemExit) as stopped:
        rq.main()
    assert stopped.value.code == 2
    assert "expected name=count pairs" in capsys.readouterr().err


def test_a_paid_qualification_refusal_says_nothing_was_sent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "keys.env"
    empty.write_text("OTHER=keep-out\n")
    monkeypatch.setattr(rq, "forbid_remote_tracing", lambda _environ: None)
    monkeypatch.setattr(rq, "configure_logging", lambda: None)
    argv = ["route_qualification", "--paid", "--key-file", str(empty), "--out", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", argv)
    assert rq.main() == 1
    assert capsys.readouterr().err == (
        "REFUSED: nothing was sent: OPENROUTER_API_KEY isn't set in that file\n"
    )
    assert list(tmp_path.iterdir()) == [empty]


def test_seeding_without_a_database_url_is_exit_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AUTOBOTS_DATABASE_URL", raising=False)
    assert concept_seed.main(["--workspace", WORKSPACE]) == 2
    assert capsys.readouterr().err == "ERROR: set AUTOBOTS_DATABASE_URL\n"


def test_seeding_a_malformed_workspace_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as stopped:
        concept_seed.main(["--workspace", "not-a-uuid"])
    assert stopped.value.code == 2


class NoOwner(ScriptedConnection):
    """A workspace with no owner row: every select answers nothing."""


def test_a_workspace_with_no_owner_is_refused_before_anything_is_written(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    @asynccontextmanager
    async def opened() -> AsyncIterator[NoOwner]:
        yield NoOwner()

    async def connect(*_args: object, **_options: object) -> AbstractAsyncContextManager[NoOwner]:
        return opened()

    monkeypatch.setenv("AUTOBOTS_DATABASE_URL", "postgresql://unused")
    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    assert concept_seed.main(["--workspace", WORKSPACE]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err == "REFUSED: that workspace has no owner, so nothing was seeded\n"


def test_the_seed_itself_raises_a_refusal_rather_than_exiting() -> None:
    with pytest.raises(concept_seed.NoOwner):
        asyncio.run(concept_seed.seed(NoOwner(), UUID(WORKSPACE), {}))
