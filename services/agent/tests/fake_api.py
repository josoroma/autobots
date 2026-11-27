"""The API in process over fakes: a membership store, a pool whose connections answer scripted rows,
and signed session tokens (refactor plan R-31, PAPI-15). `conftest.api_client` builds one per test.

Every statement a connection runs, each connection's start and end, each transaction and each role
question go into one shared `log`, in order, so a test can read which checks ran and which didn't.
No database, socket or model is used.
"""

import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from autobots.api.app import create_app
from autobots.api.resources import AppResources
from autobots.api.settings import Settings
from autobots.application.sql import SqlParams
from sql_fakes import Row, ScriptedRows

INTERNAL = "fixture-internal"
SECRET = "fixture-jwt-secret-with-enough-length"
OWNER = UUID("0b000000-0000-4000-8000-000000000001")
MEMBER = UUID("0b000000-0000-4000-8000-000000000002")
OUTSIDER = UUID("0b000000-0000-4000-8000-000000000003")
WORKSPACE = UUID("0b000000-0000-4000-8000-0000000000aa")


# The statement every run view starts from (application/run_projection/summary.py).
RUN_ROW = "from public.runs r where r.id = %(run)s"


def run_row(run: UUID, *, status: str = "running", **columns: object) -> dict[str, object]:
    """A run as its views read it, by column name, in this workspace."""
    moment = datetime(2026, 11, 15, tzinfo=UTC)
    return {
        "id": run,
        "workspace_id": WORKSPACE,
        "parent_run_id": None,
        "status": status,
        "created_at": moment,
        "updated_at": moment,
        "charged_micro_usd": 0,
        "reserved_micro_usd": 0,
        "limit_micro_usd": 1_000_000,
        "lease_generation": 1,
        "checkpoint_thread_id": None,
        "version": 1,
        "event_sequence": 0,
        **columns,
    }


def token(user: UUID = OWNER, secret: str = SECRET, **claims: object) -> str:
    """A session token as the BFF forwards one, valid for a minute."""
    body = {"sub": str(user), "aud": "authenticated", "exp": time.time() + 60, **claims}
    return jwt.encode(body, secret, algorithm="HS256")


class FakeMembership:
    """OWNER owns WORKSPACE and MEMBER belongs to it. OUTSIDER belongs nowhere."""

    def __init__(self, log: list[str]) -> None:
        self.roles: dict[UUID, str] = {OWNER: "owner", MEMBER: "member"}
        self.log = log

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return workspace_id == WORKSPACE and user_id in self.roles

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return [WORKSPACE] if user_id in self.roles else []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        self.log.append("role_in")
        return self.roles.get(user_id) if workspace_id == WORKSPACE else None


class PooledMembership(FakeMembership):
    """As `PostgresMembership` answers: each question borrows one of `database`'s connections, so a
    test sees a membership check made while the request holds another (PAPI-11)."""

    def __init__(self, log: list[str], database: "FakeDatabase") -> None:
        super().__init__(log)
        self.database = database

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        async with self.database.connection():
            return await super().is_member(user_id, workspace_id)

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        async with self.database.connection():
            return await super().workspaces_for(user_id)

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        async with self.database.connection():
            return await super().role_in(user_id, workspace_id)


@dataclass
class FakeDatabase:
    """The app's pool. A statement is answered by the first scripted fragment it contains, and by no
    rows otherwise. `statements` keeps each statement with its values."""

    log: list[str]
    answers: list[tuple[str, list[Row]]] = field(default_factory=list)
    statements: list[tuple[str, object]] = field(default_factory=list)

    def answer(self, fragment: str, *rows: Row) -> None:
        """Scripted ahead of earlier answers, so a test can replace a default."""
        self.answers.insert(0, (fragment, list(rows)))

    def saved_policy(self, default: object, overrides: object, source: str = "openrouter") -> None:
        """A saved model policy row on a Model source (Decision 0041 A1), as admission reads it
        and as the source alone is read."""
        self.answer("select model_source from app_private.model_policies", (source,))
        self.answer(
            "select default_profile, role_overrides, model_source, local_profile "
            "from app_private.model_policies",
            (default, overrides, source, None),
        )

    def written(self, table: str) -> list[object]:
        """The values of each insert into `table`, in order."""
        return [values for text, values in self.statements if f"insert into {table} " in text]

    def changes(self) -> list[str]:
        return [text for text, _ in self.statements if text.startswith(("insert", "update"))]

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    @asynccontextmanager
    async def connection(self) -> AsyncIterator["FakeConnection"]:
        self.log.append("connect")
        try:
            yield FakeConnection(self)
        finally:
            self.log.append("release")


class FakeConnection:
    # Retention commits only when it isn't (application/retention.py).
    autocommit = True

    def __init__(self, database: FakeDatabase) -> None:
        self.database = database

    async def execute(self, statement: str, values: SqlParams | None = None, /) -> ScriptedRows:
        self.database.log.append(statement)
        self.database.statements.append((statement, () if values is None else values))
        for fragment, rows in self.database.answers:
            if fragment in statement:
                return ScriptedRows(rows)
        return ScriptedRows()

    async def commit(self) -> None:
        self.database.log.append("commit")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.database.log.append("begin")
        try:
            yield
        except BaseException:
            self.database.log.append("rollback")
            raise
        self.database.log.append("commit")


@dataclass
class ApiClient:
    """The app with its lifespan running over the fakes. Each request carries the internal
    credential and, through `headers`, a session."""

    http: TestClient
    app: FastAPI
    database: FakeDatabase
    membership: FakeMembership
    log: list[str]

    @classmethod
    @contextmanager
    def started(cls) -> Iterator[Self]:
        log: list[str] = []
        database = FakeDatabase(log)
        membership = FakeMembership(log)
        settings = Settings(
            internal_token=SecretStr(INTERNAL),
            jwt_secret=SecretStr(SECRET),
            database_url=SecretStr("postgresql://fixture"),
            allowed_hosts=("testserver",),
        )
        app = create_app(
            AppResources(settings, membership=membership), pool_factory=lambda _url: database
        )
        with TestClient(app) as http:
            yield cls(http, app, database, membership, log)

    def headers(self, user: UUID | None = OWNER, **extra: str) -> dict[str, str]:
        """The internal credential, a session for `user` unless None, and any other headers."""
        values = {"X-Autobots-Internal": INTERNAL, **extra}
        return values if user is None else {**values, "Authorization": f"Bearer {token(user)}"}
