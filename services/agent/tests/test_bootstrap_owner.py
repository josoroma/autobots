"""Owner bootstrap's order and recovery, on a fake database and a fake Auth (POPS-15, POPS-14).

The database is proven before any Auth user exists; a workspace that fails after the user exists is
reported with the user's ID and finished with `--user-id`; nothing printed holds a secret.
"""

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from email.message import Message
from http.client import IncompleteRead
from typing import Any
from urllib import error
from uuid import UUID

import psycopg
import pytest

from autobots.operations import bootstrap_owner

USER = UUID("c1111111-1111-4111-8111-111111111111")
OWNED = UUID("a0000000-0000-4000-8000-000000000009")
PASSWORD = "arranged-owner-password-0000"
SERVICE_KEY = "arranged-service-role-key-0000"
DATABASE_URL = "postgresql://autobots_runtime:arranged-db-password@127.0.0.1:1/postgres"
ENVIRON = {
    "AUTOBOTS_SUPABASE_URL": "http://127.0.0.1:1",
    "AUTOBOTS_SERVICE_ROLE_KEY": SERVICE_KEY,
    "AUTOBOTS_OWNER_PASSWORD": PASSWORD,
    "AUTOBOTS_DATABASE_URL": DATABASE_URL,
}
SECRETS = (PASSWORD, SERVICE_KEY, "arranged-db-password")


class Rows:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self.row = row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


class Database:
    """One fake runtime-role database: what it was asked, in order, and what it committed."""

    def __init__(
        self,
        *,
        unreachable: bool = False,
        refuse_workspace: bool = False,
        refuse_member: bool = False,
        can_add_member: bool = True,
        owned: UUID | None = None,
    ) -> None:
        self.unreachable = unreachable
        self.refuse_workspace = refuse_workspace
        self.refuse_member = refuse_member
        self.can_add_member = can_add_member
        self.owned = owned
        self.steps: list[str] = []
        self.pending: list[tuple[object, ...]] = []
        self.committed: list[tuple[object, ...]] = []

    @contextmanager
    def connect(self, url: str) -> Iterator["Database"]:
        if self.unreachable:
            raise psycopg.OperationalError("arranged: connection refused")
        self.steps.append("connect")
        try:
            yield self
        except BaseException:
            self.steps.append("rollback")
            self.pending = []
            raise

    def commit(self) -> None:
        self.steps.append("commit")
        self.committed.extend(self.pending)
        self.pending = []

    def execute(self, query: str, params: Sequence[object], /) -> Rows:
        if query.startswith("insert into public.workspaces"):
            self.steps.append("workspace")
            if self.refuse_workspace:
                raise psycopg.errors.InsufficientPrivilege("arranged")
            self.pending.append(("workspace", *params))
            return Rows(None)
        if "has_table_privilege" in query:
            self.steps.append("grant check")
            return Rows((self.can_add_member,))
        if query.startswith("select pg_advisory_xact_lock"):
            self.steps.append(f"lock {params[0]}")
            return Rows((None,))
        if query.startswith("select workspace_id from public.workspace_members"):
            self.steps.append("ownership check")
            return Rows(None if self.owned is None else (self.owned,))
        if query.startswith("insert into public.workspace_members"):
            self.steps.append("member")
            if self.refuse_member:
                raise psycopg.errors.InsufficientPrivilege("arranged")
            self.pending.append(("member", *params))
            return Rows(None)
        raise AssertionError(query)


class Auth:
    """A fake Auth admin API that records each call in the database's own step list."""

    def __init__(
        self,
        steps: list[str],
        *,
        refuse: int | None = None,
        lost: BaseException | None = None,
        exists: bool = True,
    ) -> None:
        self.steps = steps
        self.refuse = refuse
        self.lost = lost
        self.exists = exists
        self.passwords: list[str] = []

    def create_user(self, email: str, password: str) -> UUID:
        self.steps.append("auth create")
        self.passwords.append(password)
        if self.refuse is not None:
            raise error.HTTPError("http://127.0.0.1:1", self.refuse, "arranged", Message(), None)
        if self.lost is not None:
            raise self.lost
        return USER

    def user_exists(self, user_id: UUID) -> bool:
        self.steps.append("auth read")
        return self.exists


def run(
    database: Database,
    auth: Auth,
    capsys: pytest.CaptureFixture[str],
    *arguments: str,
    environ: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    argv = list(arguments) or ["--email", "owner@example.invalid"]
    code = bootstrap_owner.main(
        [*argv, "--workspace-name", "Home"],
        environ=ENVIRON if environ is None else environ,
        auth=auth,
        connect=database.connect,
    )
    printed = capsys.readouterr()
    for secret in SECRETS:
        assert secret not in printed.out + printed.err
    return code, printed.out, printed.err


def test_the_database_is_proven_before_the_auth_user_and_both_commit_together(
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = Database()
    auth = Auth(database.steps)
    code, out, _ = run(database, auth, capsys)
    assert code == 0
    assert database.steps == [
        "connect",
        "workspace",
        "grant check",
        "auth create",
        "member",
        "commit",
    ]
    created = json.loads(out)
    assert created["user_id"] == str(USER)
    assert [row[0] for row in database.committed] == ["workspace", "member"]
    assert auth.passwords == [PASSWORD]


@pytest.mark.parametrize(
    "database",
    [
        Database(unreachable=True),
        Database(refuse_workspace=True),
        Database(can_add_member=False),
    ],
    ids=["unreachable", "workspace refused", "no member grant"],
)
def test_a_database_that_cant_finish_refuses_before_any_user_exists(
    database: Database, capsys: pytest.CaptureFixture[str]
) -> None:
    auth = Auth(database.steps)
    code, out, err = run(database, auth, capsys)
    assert code == 1 and out == ""
    assert err.startswith("REFUSED: ") and "nothing was created" in err
    assert "auth create" not in database.steps and database.committed == []


def test_auth_refusing_the_user_leaves_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    database = Database()
    code, out, err = run(database, Auth(database.steps, refuse=422), capsys)
    assert code == 1 and out == ""
    assert err.startswith("REFUSED: Auth refused the user (HTTP 422)")
    assert database.steps[-1] == "rollback" and database.committed == []


def test_a_workspace_that_fails_after_the_user_exists_prints_its_id_and_the_recovery(
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = Database(refuse_member=True)
    code, out, err = run(database, Auth(database.steps), capsys)
    assert code == 1
    assert json.loads(out) == {"status": "workspace_incomplete", "user_id": str(USER)}
    assert err.startswith("INCOMPLETE: ")
    assert f"--user-id {USER}" in err and "InsufficientPrivilege" in err
    assert database.committed == []


@pytest.mark.parametrize(
    ("auth", "named"),
    [
        ({"lost": TimeoutError("arranged")}, "TimeoutError"),
        ({"lost": IncompleteRead(b"{")}, "IncompleteRead"),
        ({"lost": ValueError("arranged: not JSON")}, "ValueError"),
        ({"refuse": 500}, "HTTP 500"),
        ({"refuse": 503}, "HTTP 503"),
    ],
    ids=["timeout", "reply cut short", "no id", "server error", "unavailable"],
)
def test_an_answer_that_may_follow_a_created_user_is_unresolved_not_refused(
    auth: dict[str, Any], named: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A 5xx can come after Auth created the user, and a lost or cut-short reply says nothing
    either way, so none of them is reported as nothing created (POPS-15)."""
    database = Database()
    code, out, err = run(database, Auth(database.steps, **auth), capsys)
    assert code == 1 and out == ""
    assert err.startswith(f"UNRESOLVED: Auth's answer was lost or failed ({named})")
    assert "may exist" in err and "--user-id <id>" in err and "REFUSED" not in err
    assert database.committed == []


def test_user_id_finishes_the_workspace_for_an_existing_user_without_creating_one(
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = Database()
    auth = Auth(database.steps)
    environ = {name: value for name, value in ENVIRON.items() if name != "AUTOBOTS_OWNER_PASSWORD"}
    code, out, _ = run(database, auth, capsys, "--user-id", str(USER), environ=environ)
    assert code == 0
    assert database.steps == [
        "connect",
        "workspace",
        "grant check",
        f"lock {USER}",
        "ownership check",
        "auth read",
        "member",
        "commit",
    ]
    assert json.loads(out)["user_id"] == str(USER) and auth.passwords == []


def test_user_id_refuses_a_user_who_already_owns_a_workspace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = Database(owned=OWNED)
    code, out, err = run(database, Auth(database.steps), capsys, "--user-id", str(USER))
    assert code == 1 and out == ""
    assert err.startswith(f"REFUSED: that user already owns workspace {OWNED}")
    assert "auth read" not in database.steps and database.committed == []
    # The lock on the user's ID comes first, so a concurrent finish waits for this answer.
    assert database.steps.index(f"lock {USER}") < database.steps.index("ownership check")


def test_a_lookup_cut_short_is_a_refusal_not_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class CutShort(Auth):
        def user_exists(self, user_id: UUID) -> bool:
            raise IncompleteRead(b"{")

    database = Database()
    code, _, err = run(database, CutShort(database.steps), capsys, "--user-id", str(USER))
    assert code == 1
    assert err.startswith("REFUSED: Auth didn't answer the lookup (IncompleteRead)")
    assert database.committed == []


def test_user_id_refuses_a_user_auth_doesnt_have(capsys: pytest.CaptureFixture[str]) -> None:
    database = Database()
    code, _, err = run(database, Auth(database.steps, exists=False), capsys, "--user-id", str(USER))
    assert code == 1 and err.startswith("REFUSED: Auth has no user with that ID")
    assert database.committed == []


def test_missing_configuration_is_named_with_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    database = Database()
    code, out, err = run(database, Auth(database.steps), capsys, environ={})
    assert code == 2 and out == ""
    assert err == (
        "ERROR: set AUTOBOTS_SUPABASE_URL, AUTOBOTS_SERVICE_ROLE_KEY, AUTOBOTS_OWNER_PASSWORD, "
        "AUTOBOTS_DATABASE_URL\n"
    )
    assert database.steps == []


def test_a_malformed_user_id_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as stopped:
        bootstrap_owner.main(["--user-id", "not-a-uuid", "--workspace-name", "Home"], environ={})
    assert stopped.value.code == 2
