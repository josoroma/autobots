"""US-15.18: Operations' measured values (Decision 0022 D5), on fakes, nothing sent off the Mac."""

import asyncio
import json
import socket
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from autobots.api import operation_routes
from autobots.api.app import create_app
from autobots.api.settings import Settings
from autobots.application import readiness
from autobots.application.catalog_check import OPERATIONS_SECONDS, CatalogCheck, check_catalog
from autobots.application.operation_values import loopback_only
from autobots.application.operations import (
    PROBES_KEPT,
    Condition,
    ProbeTimes,
    QueueCounts,
    database_conditions,
)
from autobots.application.retention import RetentionPolicy
from autobots.contracts.operations import JobHour, JobsChart, OperationValues

INTERNAL = "fixture-internal"
SECRET = "fixture-jwt-secret-with-enough-length"
OWNER = UUID("c1111111-1111-4111-8111-111111111111")
WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
SETTINGS = Settings(
    internal_token=SecretStr(INTERNAL), jwt_secret=SecretStr(SECRET), allowed_hosts=("testserver",)
)
# Exactly what D5 lists, as fields, and Decision 0023 E2's shipped count. A new measured value
# needs a decision first.
D5_VALUES = {
    "shipped_migrations",
    "database_p95_ms",
    "database_probes",
    "applied_migrations",
    "storage_bytes",
    "disk_free_bytes",
    "disk_total_bytes",
    "leased_jobs",
    "queued_jobs",
    "checkpoint_adapter",
    "catalog_fetch_ms",
    "loopback_only",
    "workers",
}


def test_the_p95_is_the_nearest_rank_of_the_last_20_probes() -> None:
    probes = ProbeTimes()
    assert (probes.p95(), probes.count()) == (None, 0)
    for value in range(1, 21):
        probes.record(float(value))
    assert (probes.p95(), probes.count()) == (19, 20)
    # Only the newest 20 stay: 6 to 25.
    for value in range(21, 26):
        probes.record(float(value))
    assert (probes.p95(), probes.count(), PROBES_KEPT) == (24, 20, 20)
    single = ProbeTimes()
    single.record(0.2)
    assert single.p95() == 1


def test_a_probe_that_finds_no_database_records_no_time() -> None:
    probes = ProbeTimes()
    asyncio.run(database_conditions(None, probes))
    assert probes.count() == 0


def test_the_bind_check_reads_this_process_own_listeners() -> None:
    assert loopback_only() is None
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    # Bound and never listening, on any port, isn't a listener this check knows from a peerless one,
    # so only real listeners are made here. The suite blocks connections, so none is opened.
    try:
        assert loopback_only() is True
        wildcard = socket.socket()
        wildcard.bind(("0.0.0.0", 0))
        wildcard.listen()
        try:
            assert loopback_only() is False
        finally:
            wildcard.close()
        assert loopback_only() is True
    finally:
        listener.close()
    assert loopback_only() is None


def test_the_catalog_time_is_measured_only_when_it_answers() -> None:
    async def answers() -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return {"data": []}

    async def nothing() -> None:
        return None

    answered = asyncio.run(check_catalog(answers, OPERATIONS_SECONDS))
    assert answered.status == "available" and answered.payload == {"data": []}
    assert answered.milliseconds is not None and answered.milliseconds >= 10
    assert asyncio.run(check_catalog(nothing, OPERATIONS_SECONDS)) == CatalogCheck("unavailable")
    assert asyncio.run(check_catalog(None, OPERATIONS_SECONDS)) == CatalogCheck("unknown")


@pytest.mark.parametrize("failure", [TimeoutError(), OSError("arranged"), ValueError("not JSON")])
def test_every_expected_catalog_failure_reads_as_unavailable(failure: Exception) -> None:
    """POPS-13: a 200 whose body isn't JSON raises ValueError in the fetcher, as a lost connection
    raises OSError, and none of them escapes."""

    async def fails() -> dict[str, Any]:
        raise failure

    assert asyncio.run(check_catalog(fails, OPERATIONS_SECONDS)) == CatalogCheck("unavailable")


def test_a_catalog_slower_than_its_limit_reads_as_unavailable() -> None:
    async def slow() -> dict[str, Any]:
        await asyncio.sleep(1)
        return {"data": []}

    assert asyncio.run(check_catalog(slow, 0.01)) == CatalogCheck("unavailable")


def test_the_values_are_exactly_d5s_list() -> None:
    assert set(OperationValues.model_fields) == D5_VALUES


def catalog_limits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Each time limit the Operations routes give the shared catalog check."""
    limits: list[float] = []

    async def timed(fetch: Any, seconds: float) -> CatalogCheck:
        limits.append(seconds)
        return await check_catalog(fetch, seconds)

    monkeypatch.setattr(operation_routes, "check_catalog", timed)
    return limits


class Membership:
    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return user_id == OWNER and workspace_id == WORKSPACE

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return [WORKSPACE] if user_id == OWNER else []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return "owner" if user_id == OWNER else None


class Pool:
    @asynccontextmanager
    async def connection(self) -> Any:
        yield object()


def test_the_status_holds_numbers_only_and_producing_it_sends_nothing_off_this_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready = (
        Condition("database", "ok", "database_ready"),
        Condition("schema", "ok", "schema_ready"),
        Condition("hold", "ok", "no_hold"),
        Condition("adapter", "ok", "adapter_qualified"),
    )

    async def conditions(_pool: object, probes: ProbeTimes | None = None) -> tuple[Condition, ...]:
        if probes is not None:
            probes.record(4.2)
        return ready

    async def counts(_connection: object, _workspace: UUID) -> QueueCounts:
        return QueueCounts(queued=3, claimed=2, expired_leases=0, oldest_queued_seconds=5)

    async def worker(_connection: object, _counts: object) -> Condition:
        return Condition("worker", "ok", "worker_ready")

    async def policy(_connection: object, _workspace: UUID) -> RetentionPolicy:
        return RetentionPolicy(run_days=None, receipt_days=None)

    async def none(*_args: object) -> list[Any]:
        return []

    async def number(value: int) -> Any:
        async def answer(*_args: object) -> int:
            return value

        return answer

    async def storage(_store: object) -> Condition:
        return Condition("storage", "ok", "storage_ready")

    async def catalog() -> dict[str, Any]:
        return {"data": []}

    sent: list[Any] = []
    original = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            sent.append(host)
            raise OSError("nothing may leave this Mac in this test")
        return original(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    limits = catalog_limits(monkeypatch)
    # The installation's conditions come through the admission gate's module.
    monkeypatch.setattr(readiness, "database_conditions", conditions)
    monkeypatch.setattr(readiness, "storage_condition", storage)
    for name, stub in (
        ("queue_counts", counts),
        ("worker_condition", worker),
        ("read_policy", policy),
        ("delayed_occurrences", none),
        ("read_route_qualifications", none),
        ("live_workers", asyncio.run(number(2))),
        ("applied_migrations", asyncio.run(number(49))),
        ("stored_bytes", asyncio.run(number(4096))),
    ):
        monkeypatch.setattr(operation_routes, name, stub)
    app = create_app(SETTINGS, membership=Membership())
    client = TestClient(app, raise_server_exceptions=False)
    app.state.pool = Pool()
    app.state.provider_context = SimpleNamespace(fetch_catalog=catalog)
    claims = {"sub": str(OWNER), "aud": "authenticated", "exp": time.time() + 60}
    reply = client.get(
        "/v1/operations/local-status",
        headers={
            "X-Autobots-Internal": INTERNAL,
            "Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}",
        },
    )
    assert reply.status_code == 200, reply.text
    body = reply.json()
    values = body["values"]
    assert set(values) == D5_VALUES
    assert values["workers"] == 2 and values["applied_migrations"] == 49
    assert values["storage_bytes"] == 4096 and (values["leased_jobs"], values["queued_jobs"]) == (
        2,
        3,
    )
    assert values["database_probes"] == 1 and values["database_p95_ms"] == 5
    assert values["disk_free_bytes"] <= values["disk_total_bytes"]
    assert values["catalog_fetch_ms"] is not None
    # A page load waits 3 s for the catalog at most, as Operations always has.
    assert limits == [OPERATIONS_SECONDS] == [3.0]
    assert values["checkpoint_adapter"].startswith("langgraph-checkpoint-postgres ")
    text = json.dumps(body)
    for leak in (
        "/",
        "\\",
        "127.0.0.1",
        "localhost",
        "postgres://",
        "sk-or-",
        "Bearer",
        INTERNAL,
        SECRET,
    ):
        assert leak not in text, leak
    assert sent == []


def test_the_jobs_chart_holds_hourly_counts_by_outcome_only() -> None:
    assert set(JobsChart.model_fields) == {"schema_version", "timezone", "hours"}
    assert set(JobHour.model_fields) == {
        "starts_at",
        "hour",
        "succeeded",
        "waited",
        "failed",
        "in_progress",
    }
    with pytest.raises(ValueError):
        JobHour.model_validate(
            {
                "starts_at": "2026-11-08T10:00:00Z",
                "hour": "Run 7f3a",
                "succeeded": 0,
                "waited": 0,
                "failed": 0,
                "in_progress": 0,
            }
        )


class MemberOnly(Membership):
    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return "member" if user_id == OWNER else None


def test_any_member_reads_the_retention_summary_and_their_own_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def policy(_connection: object, _workspace: UUID) -> RetentionPolicy:
        return RetentionPolicy(run_days=30, receipt_days=60)

    monkeypatch.setattr(operation_routes, "read_policy", policy)
    claims = {"sub": str(OWNER), "aud": "authenticated", "exp": time.time() + 60}
    headers = {
        "X-Autobots-Internal": INTERNAL,
        "Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}",
    }
    for membership, role in ((MemberOnly(), "member"), (Membership(), "owner")):
        app = create_app(SETTINGS, membership=membership)
        app.state.pool = Pool()
        client = TestClient(app, raise_server_exceptions=False)
        reply = client.get("/v1/retention", headers=headers)
        assert reply.status_code == 200, reply.text
        assert reply.json() == {
            "schema_version": 1,
            "run_days": 30,
            "receipt_days": 60,
            "viewer_role": role,
        }
        assert client.put("/v1/retention", headers=headers, json={}).status_code == 405
