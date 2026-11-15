"""One admission gate for a person's run and a due routine (LM-07, Decision 0023 E2), on fakes.

The API's `require_ready` and the worker's maintenance step refuse on the same first blocking
condition. The worker logs its code, skips routines and keeps retention, and the gate's settings
are read once at process start (refactor plan R-24, POPS-02 and PAPI-10). No database, socket or
model is used.
"""

import asyncio
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from autobots.adapters.tool_registry import catalog
from autobots.api import main as api_main
from autobots.api.app import create_app
from autobots.api.settings import Settings, load_settings
from autobots.application import readiness
from autobots.application.operations import Condition, ProbeTimes, is_ready
from autobots.application.readiness import (
    DEFAULT_MIN_FREE_BYTES,
    ConnectionSource,
    LentConnection,
    MalformedSetting,
    ReadinessSettings,
    first_blocking,
    installation_conditions,
)
from autobots.operations import worker
from autobots.operations.composition import no_credential

INTERNAL = "fixture-internal"
SECRET = "fixture-jwt-secret-with-enough-length"
MEMBER = UUID("c1111111-1111-4111-8111-111111111111")
WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
CONNECTION = object()
DatabaseAnswer = tuple[Condition, Condition, Condition, Condition]
DATABASE_READY: DatabaseAnswer = (
    Condition("database", "ok", "database_ready"),
    Condition("schema", "ok", "schema_ready"),
    Condition("hold", "ok", "no_hold"),
    Condition("adapter", "ok", "adapter_qualified"),
)


def answer(replaced: Condition) -> DatabaseAnswer:
    """The database probe's answer with one condition replaced, the others ready."""
    first, second, third, fourth = (
        replaced if item.name == replaced.name else item for item in DATABASE_READY
    )
    return first, second, third, fourth


@dataclass
class Install:
    """What the gate reads, arranged: the database probe's answer, Storage, and the disk minimum."""

    database: DatabaseAnswer = DATABASE_READY
    storage_up: bool = True
    min_free_bytes: int = 0


# Each refusal a person's admission makes, arranged where it arises.
REFUSALS = {
    "database_unreachable": Install(
        database=(
            Condition("database", "unavailable", "database_unreachable"),
            Condition("schema", "unavailable", "schema_unknown"),
            Condition("hold", "unavailable", "hold_unknown"),
            Condition("adapter", "unavailable", "adapter_unknown"),
        )
    ),
    "schema_behind": Install(database=answer(Condition("schema", "unavailable", "schema_behind"))),
    "restore_hold": Install(database=answer(Condition("hold", "unavailable", "restore_hold"))),
    "adapter_unqualified": Install(
        database=answer(Condition("adapter", "unavailable", "adapter_unqualified"))
    ),
    "storage_unreachable": Install(storage_up=False),
    "disk_low": Install(min_free_bytes=2**62),
}
SCHEMA_AHEAD = Install(database=answer(Condition("schema", "degraded", "schema_ahead")))


class Storage:
    def __init__(self, up: bool) -> None:
        self.up = up

    async def ping(self) -> None:
        if not self.up:
            raise RuntimeError("arranged: Storage is down")


# The gate's rule


def test_the_refusal_is_the_first_blocking_condition_in_admission_order() -> None:
    behind = Condition("schema", "unavailable", "schema_behind")
    storage = Condition("storage", "unavailable", "storage_unreachable")
    low = Condition("disk", "degraded", "disk_low")
    conditions = [DATABASE_READY[0], behind, *DATABASE_READY[2:], storage, low]
    assert first_blocking(conditions) == behind
    assert first_blocking([DATABASE_READY[0], *DATABASE_READY[2:], storage, low]) == storage


def test_a_newer_database_and_conditions_outside_admission_never_refuse() -> None:
    conditions = [
        *answer(Condition("schema", "degraded", "schema_ahead")),
        Condition("worker", "degraded", "worker_absent"),
        Condition("queue", "degraded", "leases_expired"),
        Condition("storage", "ok", "storage_ready"),
    ]
    assert first_blocking(conditions) is None
    assert first_blocking([]) is None


@pytest.mark.parametrize(
    "conditions",
    [
        list(DATABASE_READY),
        [Condition("disk", "degraded", "disk_low")],
        [Condition("worker", "degraded", "no_inference_worker")],
        list(answer(Condition("schema", "degraded", "schema_ahead"))),
        list(answer(Condition("hold", "unavailable", "restore_hold"))),
    ],
)
def test_operations_readiness_says_what_the_gate_says(conditions: list[Condition]) -> None:
    assert is_ready(conditions) == (first_blocking(conditions) is None)


# Its settings, read once per process


def test_the_gate_settings_default_when_unset_or_blank() -> None:
    assert DEFAULT_MIN_FREE_BYTES == 2 * 1024**3
    assert ReadinessSettings.from_environment({}) == ReadinessSettings(
        Path("."), DEFAULT_MIN_FREE_BYTES
    )
    blank = {"AUTOBOTS_MIN_FREE_BYTES": " ", "AUTOBOTS_CONFIG_ROOT": ""}
    assert ReadinessSettings.from_environment(blank) == ReadinessSettings()


def test_the_gate_settings_read_the_data_root_and_the_minimum() -> None:
    read = ReadinessSettings.from_environment(
        {"AUTOBOTS_CONFIG_ROOT": "/srv/autobots", "AUTOBOTS_MIN_FREE_BYTES": "1024"}
    )
    assert read == ReadinessSettings(Path("/srv/autobots"), 1024)
    assert ReadinessSettings.from_environment({"AUTOBOTS_MIN_FREE_BYTES": "0"}).min_free_bytes == 0


@pytest.mark.parametrize("value", ["lots", "-1", "2GiB", "1.5", "0x10"])
def test_a_malformed_minimum_is_refused_naming_the_variable_and_not_its_value(value: str) -> None:
    with pytest.raises(MalformedSetting, match="AUTOBOTS_MIN_FREE_BYTES") as raised:
        ReadinessSettings.from_environment({"AUTOBOTS_MIN_FREE_BYTES": value})
    assert value not in str(raised.value)


def test_the_api_reads_the_gate_settings_and_backups_once_at_startup(tmp_path: Path) -> None:
    settings = load_settings(
        {
            "AUTOBOTS_CONFIG_ROOT": str(tmp_path),
            "AUTOBOTS_MIN_FREE_BYTES": "7",
            "AUTOBOTS_BACKUP_DIR": "/backups",
        }
    )
    assert settings.readiness == ReadinessSettings(tmp_path, 7)
    assert settings.backup_dir == "/backups"
    assert load_settings({}).readiness == ReadinessSettings()
    with pytest.raises(MalformedSetting):
        load_settings({"AUTOBOTS_MIN_FREE_BYTES": "lots"})


def test_a_malformed_minimum_stops_the_api_at_startup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 2, a prerequisite that isn't there, with the variable named (POPS-14)."""
    monkeypatch.setattr(api_main, "configure_logging", lambda: None)
    monkeypatch.setattr(api_main, "forbid_remote_tracing", lambda _environ: None)
    monkeypatch.setenv("AUTOBOTS_MIN_FREE_BYTES", "lots")
    with pytest.raises(SystemExit) as stopped:
        api_main.create_configured_app()
    assert stopped.value.code == 2
    assert capsys.readouterr().err.startswith("ERROR: AUTOBOTS_MIN_FREE_BYTES must be")


def test_the_worker_entry_point_refuses_before_it_serves(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def never(*_args: object, **_options: object) -> None:
        raise AssertionError("a malformed minimum must stop the worker before it serves")

    monkeypatch.setattr(worker, "configure_logging", lambda: None)
    monkeypatch.setattr(worker, "forbid_remote_tracing", lambda _environ: None)
    monkeypatch.setattr(worker, "serve", never)
    monkeypatch.setenv("AUTOBOTS_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("AUTOBOTS_MIN_FREE_BYTES", "lots")
    with pytest.raises(SystemExit) as stopped:
        asyncio.run(worker.main())
    assert stopped.value.code == 2
    assert capsys.readouterr().err.startswith("ERROR: AUTOBOTS_MIN_FREE_BYTES must be")


# What the gate reads


def test_the_gate_reads_database_storage_and_disk_in_admission_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    probes = ProbeTimes()
    passed: list[ProbeTimes | None] = []

    async def answers(_source: object, recorded: ProbeTimes | None = None) -> DatabaseAnswer:
        passed.append(recorded)
        return DATABASE_READY

    monkeypatch.setattr(readiness, "database_conditions", answers)
    conditions = asyncio.run(
        installation_conditions(None, Storage(up=True), ReadinessSettings(tmp_path, 0), probes)
    )
    assert [item.name for item in conditions] == [
        "database",
        "schema",
        "hold",
        "adapter",
        "storage",
        "disk",
    ]
    assert first_blocking(conditions) is None
    assert passed == [probes]


def test_with_nothing_configured_the_database_is_the_refusal(tmp_path: Path) -> None:
    conditions = asyncio.run(installation_conditions(None, None, ReadinessSettings(tmp_path, 0)))
    assert [item.code for item in conditions] == [
        "database_not_configured",
        "schema_unknown",
        "hold_unknown",
        "adapter_unknown",
        "storage_not_configured",
        "disk_ready",
    ]
    refusal = first_blocking(conditions)
    assert refusal is not None and refusal.code == "database_not_configured"


def test_a_lent_connection_is_the_one_its_holder_lent() -> None:
    async def borrowed() -> object:
        async with LentConnection(CONNECTION).connection() as connection:
            return connection

    assert asyncio.run(borrowed()) is CONNECTION


# The worker's maintenance step


class Said(logging.Handler):
    """The worker's log events, with their fields."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.events: list[tuple[str, dict[str, object]]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.events.append((record.getMessage(), dict(getattr(record, "fields", {}))))


@pytest.fixture
def said() -> Iterator[list[tuple[str, dict[str, object]]]]:
    handler = Said()
    logger = logging.getLogger("autobots.worker")
    logger.addHandler(handler)
    try:
        yield handler.events
    finally:
        logger.removeHandler(handler)


@dataclass
class Maintenance:
    """The maintenance step with its database work faked: what ran, in order, and what it probed."""

    database: DatabaseAnswer
    storage: Storage
    held: bool = False
    ran: list[str] = field(default_factory=list)
    probed: list[object] = field(default_factory=list)


def maintenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, install: Install, *, held: bool = False
) -> tuple[Maintenance, worker.Step]:
    state = Maintenance(install.database, Storage(install.storage_up), held)

    async def is_held(_connection: object) -> bool:
        state.ran.append("hold check")
        return state.held

    async def expire_due(_connection: object) -> None:
        state.ran.append("approvals")

    async def evaluate_routines(_connection: object, _check: object, **_: object) -> int:
        state.ran.append("routines")
        return 1

    async def apply_all(_connection: object, _store: object) -> None:
        state.ran.append("retention")

    async def database_conditions(
        source: ConnectionSource | None, _probes: ProbeTimes | None = None
    ) -> DatabaseAnswer:
        assert source is not None
        async with source.connection() as lent:
            state.probed.append(lent)
        return state.database

    for name, fake in (
        ("is_held", is_held),
        ("expire_due", expire_due),
        ("evaluate_routines", evaluate_routines),
        ("apply_all", apply_all),
    ):
        monkeypatch.setattr(worker, name, fake)
    monkeypatch.setattr(readiness, "database_conditions", database_conditions)
    settings = ReadinessSettings(tmp_path, install.min_free_bytes)
    step = worker.maintenance_step(no_credential, state.storage, settings, 0, catalog=catalog())
    return state, step


def one_pass(step: worker.Step) -> bool:
    async def run() -> bool:
        return await step(CONNECTION)

    return asyncio.run(run())


@pytest.mark.parametrize("code", sorted(REFUSALS))
def test_a_due_routine_waits_on_each_condition_a_person_waits_on(
    code: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    said: list[tuple[str, dict[str, object]]],
) -> None:
    state, step = maintenance(monkeypatch, tmp_path, REFUSALS[code])
    assert one_pass(step) is False
    assert state.ran == ["hold check", "approvals", "retention"]
    assert said == [("worker.routines_waiting", {"reason": code})]


def test_a_ready_install_evaluates_due_routines_on_the_worker_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, said: list[tuple[str, dict[str, object]]]
) -> None:
    state, step = maintenance(monkeypatch, tmp_path, Install())
    assert one_pass(step) is True
    assert state.ran == ["hold check", "approvals", "routines", "retention"]
    assert state.probed == [CONNECTION]
    assert said == []


def test_a_newer_database_does_not_hold_routines_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, said: list[tuple[str, dict[str, object]]]
) -> None:
    state, step = maintenance(monkeypatch, tmp_path, SCHEMA_AHEAD)
    assert one_pass(step) is True
    assert "routines" in state.ran and said == []


def test_the_refusal_is_logged_when_it_changes_not_on_every_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, said: list[tuple[str, dict[str, object]]]
) -> None:
    state, step = maintenance(monkeypatch, tmp_path, REFUSALS["schema_behind"])
    one_pass(step)
    one_pass(step)
    state.database, state.storage.up = DATABASE_READY, False
    one_pass(step)
    state.storage.up = True
    assert one_pass(step) is True
    state.database = REFUSALS["schema_behind"].database
    one_pass(step)
    assert [fields["reason"] for _event, fields in said] == [
        "schema_behind",
        "storage_unreachable",
        "schema_behind",
    ]
    assert state.ran.count("routines") == 1
    assert state.ran.count("retention") == 5


def test_a_held_install_changes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, said: list[tuple[str, dict[str, object]]]
) -> None:
    state, step = maintenance(monkeypatch, tmp_path, Install(), held=True)
    assert one_pass(step) is False
    assert state.ran == ["hold check"]
    assert state.probed == [] and said == []


# A person's admission through the API


class Membership:
    """A member, not the owner, of one workspace, so a request past the gate is refused next."""

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return user_id == MEMBER and workspace_id == WORKSPACE

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return [WORKSPACE] if user_id == MEMBER else []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return "member" if user_id == MEMBER else None


def gated_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, install: Install) -> TestClient:
    async def answers(_source: object, _probes: ProbeTimes | None = None) -> DatabaseAnswer:
        return install.database

    monkeypatch.setattr(readiness, "database_conditions", answers)
    settings = Settings(
        internal_token=SecretStr(INTERNAL),
        jwt_secret=SecretStr(SECRET),
        allowed_hosts=("testserver",),
        readiness=ReadinessSettings(tmp_path, install.min_free_bytes),
    )
    app = create_app(settings, membership=Membership())
    app.state.pool = object()
    app.state.object_store = Storage(install.storage_up)
    return TestClient(app, raise_server_exceptions=False)


def admit(client: TestClient) -> tuple[int, str]:
    """Retention's apply is an admission `require_ready` guards, as runs and workflows are."""
    claims = {"sub": str(MEMBER), "aud": "authenticated", "exp": time.time() + 60}
    reply = client.post(
        "/v1/operations/retention/apply",
        headers={
            "X-Autobots-Internal": INTERNAL,
            "Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}",
        },
    )
    return reply.status_code, str(reply.json().get("code"))


@pytest.mark.parametrize("code", sorted(REFUSALS))
def test_a_person_is_refused_on_each_blocking_condition_as_before(
    code: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert admit(gated_client(monkeypatch, tmp_path, REFUSALS[code])) == (503, "not_ready")


@pytest.mark.parametrize("install", [Install(), SCHEMA_AHEAD], ids=["ready", "schema_ahead"])
def test_a_ready_install_lets_a_person_past_the_gate(
    install: Install, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert admit(gated_client(monkeypatch, tmp_path, install)) == (403, "owner_required")


def test_a_request_never_rereads_the_gate_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    low = gated_client(monkeypatch, tmp_path, REFUSALS["disk_low"])
    ready = gated_client(monkeypatch, tmp_path, Install())
    monkeypatch.setenv("AUTOBOTS_MIN_FREE_BYTES", "lots")
    monkeypatch.setenv("AUTOBOTS_CONFIG_ROOT", str(tmp_path / "absent"))
    assert admit(low) == (503, "not_ready")
    assert admit(ready) == (403, "owner_required")
