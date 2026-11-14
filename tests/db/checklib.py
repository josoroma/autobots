"""The case protocol and arrangements the database checks share (refactor plan R-38, TDBC-03).

A check prints one JSON line, `{"cases": [...], **extra}`. Each case keeps the DH-W04 record shape
`{'id', 'expected', 'observed', 'passed'}` (PRD-Development-Harness DH-W04), which scripts/app_db.py
and the qualifiers parse. New checks use this module, and an existing check moves onto it when it
is next changed (R-38).

Only the standard library loads with the module. The service and the database driver load in the
calls that need them, so tests/harness/test_db_case_protocol.py runs the protocol without them.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import signal
import traceback
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
)
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, TypedDict
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from autobots.application.approvals import DecisionResult
    from autobots.application.runs import TransitionResult
    from autobots.application.worker_leases import Lease
    from autobots.domain.runs import Actor, RunCommand

# The longest observation a case keeps. The parents shorten it again for their reports.
OBSERVED_LIMIT = 900
KILLED = -signal.SIGKILL

# What claim_next could take: a queued job, or a claimed one whose lease has run out
# (autobots.application.worker_leases). A live lease, such as a run a check holds for the browser
# suites, is never ended (TDBC-05).
CLAIMABLE = "status = 'queued' or (status = 'claimed' and lease_expires_at <= clock_timestamp())"
QUIESCE = f"update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where ({CLAIMABLE})"
APP_TABLES = ("select quote_ident(table_schema) || '.' || quote_ident(table_name) from information_schema.tables "
              "where table_type = 'BASE TABLE' and table_schema in ('public', 'app_private', 'agent_runtime') order by 1")


class Case(TypedDict):
    """One DH-W04 record: what was expected, what was observed, and whether that observation passed."""

    id: str
    expected: str
    observed: str
    passed: bool


class NoRow(LookupError):
    """A query a check reads a row from returned none. It names its SQL, where indexing None would not."""

    def __init__(self, sql: str) -> None:
        super().__init__(f'no row: {sql}')
        self.sql = sql


class NoClaim(LookupError):
    """The run under test could not be claimed, so its scenario stops rather than drive another run."""

    def __init__(self, run: UUID) -> None:
        super().__init__(f'run {run} was not claimed')
        self.run = run


def refusal_code(error: BaseException) -> str:
    """A refusal's code: its `code`, else a database error's SQLSTATE, else its message."""
    return str(getattr(error, 'code', None) or getattr(error, 'sqlstate', None) or error)


def holds_secret(text: str, secrets: Iterable[str]) -> bool:
    """Whether `text` holds any of `secrets`, as written or as JSON escapes it."""
    return any(secret and (secret in text or json.dumps(secret)[1:-1] in text) for secret in secrets)


class Cases:
    """The cases one check observed, in order."""

    def __init__(self) -> None:
        self.records: list[Case] = []

    def check[T](self, name: str, expected: str, observed: T, passed: bool | Callable[[T], bool]) -> T:
        """Record a case and return `observed`. A predicate for `passed` judges the very value the case
        shows, so a call that changes state is evaluated once (refactor plan R-08)."""
        verdict = passed(observed) if callable(passed) else passed
        self.records.append(Case(id=name, expected=expected, observed=str(observed)[:OBSERVED_LIMIT], passed=bool(verdict)))
        return observed

    async def refused(self, name: str, code: str | None, attempt: Awaitable[object],
                      refusal: type[Exception], *others: type[Exception]) -> Exception | None:
        """Await `attempt`, which passes only by raising one of the named classes with `code` (any code
        when None). Completing, another class or another code fails the case. Returns the refusal."""
        named = (refusal, *others)
        expected = ' or '.join(item.__name__ for item in named) + (f' {code}' if code else '')
        try:
            value = await attempt
        except named as error:
            shown = refusal_code(error)
            self.check(name, expected, f'{type(error).__name__} {shown}', code is None or shown == code)
            return error
        except Exception as error:  # noqa: BLE001 - another class fails this case and is never counted as the refusal
            self.check(name, expected, f'{type(error).__name__}: {error}', False)
            return None
        self.check(name, expected, f'accepted: {value}', False)
        return None

    @contextlib.contextmanager
    def scenario(self, name: str) -> Iterator[None]:
        """Guard one independent scenario. Its exception becomes a failed case and the check moves on,
        so a crash cannot drop the later scenarios unnamed (TDBC-04)."""
        try:
            yield
        except Exception as error:  # noqa: BLE001 - recorded as this scenario's failed case, so the next one still runs
            self.check(f'{name}: ran to the end', 'no exception', f'{type(error).__name__}: {error}', False)

    def emit(self, secrets: Iterable[str] = (), **extra: object) -> None:
        """Print the one line the parents parse. If a fixture secret reached it, print one failed case
        instead and stop, so no secret reaches evidence (AGENTS.md)."""
        output = json.dumps({'cases': self.records, **extra})
        if holds_secret(output, secrets):
            withheld = Case(id='this check printed no fixture secret', expected='no fixture secret in its output',
                            observed=f'{len(self.records)} cases withheld: a fixture secret reached them', passed=False)
            print(json.dumps({'cases': [withheld]}), flush=True)
            raise SystemExit('a fixture secret reached this check output')
        print(output, flush=True)


def run_check(main: Callable[[Cases], Coroutine[Any, Any, Mapping[str, object] | None]], *,
              secrets: Iterable[str] = ()) -> None:
    """Run a check and print its cases, after the fixture-secret scan, whether `main` returns or raises.

    What `main` returns joins the line, such as `browser_env`. A raise prints what was observed, then
    propagates, so the check still exits non-zero and its parent records the failure (TDBC-04). The
    parents copy the end of stderr into evidence, so a traceback holding a fixture secret is replaced
    by a bare exit.
    """
    cases, scanned = Cases(), tuple(secrets)
    try:
        extra = asyncio.run(main(cases)) or {}
    except BaseException as error:
        cases.emit(scanned)
        if holds_secret(''.join(traceback.format_exception(error)), scanned):
            raise SystemExit('this check failed with an error that held a fixture secret, so it is not shown') from None
        raise
    cases.emit(scanned, **extra)


def direct_binding(tools: Mapping[str, int], expert: tuple[UUID, int] | None = None) -> SimpleNamespace:
    """A run's binding without a session: these tool grants, and optionally one Expert revision."""
    return SimpleNamespace(session_id=None, expert_id=expert[0] if expert else None, version=expert[1] if expert else None,
                           instructions='', tools=dict(tools))


class OnePool:
    """A pool that lends its one connection, for code such as `database_conditions` that takes a pool."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    @contextlib.asynccontextmanager
    async def connection(self) -> AsyncIterator[Any]:
        yield self._connection


class Db:
    """One autocommit connection, with the arrangements the checks repeat for one workspace and actor."""

    def __init__(self, connection: Any, cases: Cases, workspace: UUID, actor: UUID) -> None:
        self.connection = connection
        self.cases = cases
        self.workspace = workspace
        self.actor = actor

    @classmethod
    @contextlib.asynccontextmanager
    async def connect(cls, url: str, cases: Cases, workspace: UUID, actor: UUID) -> AsyncIterator[Db]:
        import psycopg

        async with await psycopg.AsyncConnection.connect(url, autocommit=True) as connection:
            yield cls(connection, cases, workspace, actor)

    async def row(self, sql: str, *values: object) -> tuple[Any, ...]:
        found = await (await self.connection.execute(sql, values)).fetchone()
        if found is None:
            raise NoRow(sql)
        return tuple(found)

    async def value(self, sql: str, *values: object) -> Any:
        return (await self.row(sql, *values))[0]

    async def admit(self, goal: str = 'work', *, limit_micro_usd: int = 1_000_000, workspace: UUID | None = None,
                    tools: Mapping[str, int] | None = None, expert: tuple[UUID, int] | None = None, **options: Any) -> UUID:
        """Admit a run through the admission code, with the default role policy unless `options` names one.
        `tools` binds those grants directly, with `expert` as its Expert revision."""
        from autobots.application.runs import admit_run
        from autobots.domain.models import resolve_role_policy

        if tools is not None:
            options['binding'] = direct_binding(tools, expert)
        options.setdefault('policy', resolve_role_policy())
        admitted = await admit_run(self.connection, workspace_id=workspace or self.workspace, actor_id=self.actor,
                                   idempotency_key=str(uuid4()), goal_text=goal, limit_micro_usd=limit_micro_usd, **options)
        return admitted.run_id

    async def quiesce(self, keep: UUID | None = None) -> None:
        """End every job claim_next could take, except `keep`'s. Live leases stay (TDBC-05)."""
        if keep is None:
            await self.connection.execute(QUIESCE)
        else:
            await self.connection.execute(f'{QUIESCE} and run_id <> %s', (keep,))

    async def claim(self, run: UUID, *, worker_id: str = 'check', lease_seconds: float = 60) -> Lease:
        """Claim exactly this run, for a scenario whose subject is not the worker's own claim."""
        from autobots.application.worker_leases import claim_run

        lease = await claim_run(self.connection, run, worker_id=worker_id, lease_seconds=lease_seconds)
        if lease is None:
            raise NoClaim(run)
        return lease

    async def isolated_claim(self, run: UUID, *, worker_id: str = 'check', lease_seconds: float = 60) -> Lease:
        """The isolation step, named once: end only what claim_next could take besides `run`, let
        claim_next choose, then record that it chose the run under test (TDBC-05)."""
        from autobots.application.worker_leases import claim_next

        await self.quiesce(keep=run)
        lease = await claim_next(self.connection, worker_id=worker_id, lease_seconds=lease_seconds)
        self.cases.check(f'claim_next takes the run under test ({worker_id})', str(run),
                         lease.run_id if lease else 'no claim', lambda claimed: claimed == run)
        if lease is None or lease.run_id != run:
            raise NoClaim(run)
        return lease

    async def command(self, run: UUID, command: RunCommand, actor: Actor, **options: Any) -> TransitionResult:
        """Apply `command` at the run's current version, read just before, rather than a literal (TDBC-03)."""
        from autobots.application.runs import apply_command

        version = await self.value('select version from public.runs where id = %s', run)
        return await apply_command(self.connection, workspace_id=self.workspace, run_id=run, command=command, actor=actor,
                                   expected_version=version, **options)

    async def expire(self, run: UUID) -> None:
        """Let the run's lease lapse by database time."""
        await self.connection.execute(
            "update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))

    async def approve(self, run: UUID, decision: str = 'approve') -> DecisionResult:
        """Decide the run's newest pending approval, for the arguments it shows."""
        from autobots.application.approvals import decide

        approval, argument_hash = await self.row(
            "select id, argument_hash from public.approval_requests where run_id = %s and status = 'pending' "
            'order by created_at desc limit 1', run)
        return await decide(self.connection, workspace_id=self.workspace, actor_id=self.actor, approval_id=approval,
                            idempotency_key=str(uuid4()), decision=decision, argument_hash=argument_hash)

    async def leaked(self, secrets: Sequence[str], tables: Iterable[str] | None = None) -> list[str]:
        """The tables holding any of `secrets` as text: every base table in the application's schemas,
        unless `tables` names some. A table this role cannot read is skipped. No value is returned."""
        from psycopg import errors

        names = list(tables) if tables is not None else [row[0] for row in await (await self.connection.execute(APP_TABLES)).fetchall()]
        found = []
        for table in names:
            try:
                hits = await self.value(f'select count(*) from {table} t where exists '
                                        '(select 1 from unnest(%s::text[]) s(v) where strpos(t::text, s.v) > 0)',
                                        [secret for secret in secrets if secret])
            except errors.InsufficientPrivilege:
                continue
            if hits:
                found.append(table)
        return found


async def killed_worker(cases: Cases, name: str, argv: Sequence[str], *, exit_code: int = KILLED,
                        limit_seconds: float = 60, env: Mapping[str, str] | None = None) -> str:
    """Run a worker that must die, record its exit as a case, and return what it printed. One still
    running after `limit_seconds` is killed, and fails the case (TDBC-04)."""
    process = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                   env=None if env is None else dict(env))
    try:
        out, err = await asyncio.wait_for(process.communicate(), limit_seconds)
    except TimeoutError:
        process.kill()
        out, _ = await process.communicate()
        cases.check(name, f'exit {exit_code}', f'still running after {limit_seconds} seconds', False)
        return out.decode(errors='replace')
    cases.check(name, f'exit {exit_code}', f'exit {process.returncode}: {err.decode(errors="replace").strip()[-200:]}',
                process.returncode == exit_code)
    return out.decode(errors='replace')
