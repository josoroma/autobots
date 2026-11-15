"""Key checks and decisions that need no database. Real rows run in scripts/qualify_identity.py.

`ProviderSettings` takes its credential store and settings rows through its seams here, so its own
gates run as production runs them (PTST-01).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.application import provider_settings as settings_module
from autobots.application.catalog_check import SETTINGS_SECONDS, CatalogCheck, Fetch, check_catalog
from autobots.application.credentials.store import (
    CredentialReference,
    CredentialStorageUnavailable,
    CredentialUnreadable,
    ProviderCredentialStore,
    ResolvedCredential,
)
from autobots.application.provider_settings import (
    KeyCheck,
    ProviderSettings,
    StoredSettingsRows,
    qualification_from_record,
)
from autobots.application.sql import SqlParams, UnknownStoredValue
from autobots.contracts.settings import AuthStatus, CredentialDraft, ProviderStatus
from autobots.domain.models import PROFILES, ModelProfileId
from autobots.persistence.rows import RouteQualificationRow
from fake_openrouter import ARRANGED_KEY, provider_context
from sql_fakes import Row, ScriptedConnection, ScriptedRows


def client_for(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="https://openrouter.ai/api/v1", transport=handler)


def validator(status: int) -> object:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/key", "only the key metadata route"
        assert request.method == "GET"
        return httpx.Response(status, json={"data": {}})

    transport = httpx.MockTransport(handle)
    return key_validator(lambda: client_for(transport))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (200, KeyCheck.VALID),
        (401, KeyCheck.REJECTED),
        (403, KeyCheck.REJECTED),
        (429, KeyCheck.UNREACHABLE),
        (500, KeyCheck.UNREACHABLE),
    ],
)
async def test_key_metadata_results(status: int, expected: KeyCheck) -> None:
    validate = validator(status)
    assert await validate(SecretStr("sk-or-arranged")) is expected  # type: ignore[operator]


@pytest.mark.asyncio
async def test_a_network_failure_is_not_a_rejected_key() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    transport = httpx.MockTransport(handle)
    validate = key_validator(lambda: client_for(transport))
    assert await validate(SecretStr("sk-or-arranged")) is KeyCheck.UNREACHABLE


@pytest.mark.asyncio
async def test_a_catalog_outage_returns_nothing() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    assert await catalog_fetcher(lambda: client_for(transport))() is None


def test_a_status_cannot_carry_a_key() -> None:
    assert "draft_key" not in ProviderStatus.model_fields
    assert not any("key" in name and name != "draft_key" for name in ProviderStatus.model_fields)


def test_a_draft_repr_does_not_matter_because_it_is_never_returned() -> None:
    assert CredentialDraft(draft_key="x", expected_version=0).expected_version == 0


def test_only_a_record_for_the_routes_own_model_counts() -> None:
    canonical = PROFILES[ModelProfileId.TERRA].canonical_id
    record = RouteQualificationRow(
        profile=ModelProfileId.TERRA.value,
        canonical_id=canonical,
        status="qualified_with_limits",
        qualified_on=date(2026, 11, 5),
        configuration="c",
        limits="l",
    )

    def status(stored: RouteQualificationRow | None) -> str:
        return qualification_from_record(ModelProfileId.TERRA, canonical, stored).status

    assert status(record) == "qualified_with_limits"
    assert status(None) == "not_qualified"
    assert status(replace(record, canonical_id="openai/another-model")) == "not_qualified"
    shown = qualification_from_record(ModelProfileId.TERRA, canonical, record)
    assert (shown.qualified_on, shown.configuration, shown.limits) == (date(2026, 11, 5), "c", "l")
    with pytest.raises(UnknownStoredValue, match="qualified"):
        status(replace(record, status="qualified"))
    empty = qualification_from_record(ModelProfileId.TERRA, canonical, None)
    assert (empty.qualified_on, empty.configuration, empty.limits) == (None, None, None)


class Keys(ProviderCredentialStore):
    """The stored key as an arranged answer, a credential or what reading it raised, and whether
    this workspace may use the installation's key."""

    def __init__(
        self, active: ResolvedCredential | Exception, *, installation_allowed: bool = False
    ) -> None:
        super().__init__(ScriptedConnection(), Path("/nonexistent"))
        self.active = active
        self.installation_allowed = installation_allowed

    async def load_active(self, workspace_id: UUID) -> ResolvedCredential:
        if isinstance(self.active, Exception):
            raise self.active
        return self.active

    async def installation_key_allowed(self, workspace_id: UUID) -> bool:
        return self.installation_allowed


class Rows:
    """The settings row in memory: version 1 at its stored status, each status recorded, and every
    call in order."""

    def __init__(self, stored: AuthStatus = "configured") -> None:
        self.stored: AuthStatus = stored
        self.recorded: list[str] = []
        self.calls: list[str] = []

    async def read(
        self, workspace_id: UUID, *, lock: bool = False
    ) -> tuple[int, AuthStatus, datetime | None]:
        self.calls.append("read locked" if lock else "read")
        return 1, self.stored, None

    async def ensure(self, workspace_id: UUID) -> None:
        self.calls.append("ensure")

    async def record(self, workspace_id: UUID, status: AuthStatus) -> None:
        self.calls.append(f"record {status}")
        self.recorded.append(status)


class NoQualifications(ScriptedConnection):
    """A connection with no route qualification stored, the only read left on it here."""


def stored_key(version: int) -> ResolvedCredential:
    return ResolvedCredential(CredentialReference("app", None, version), ARRANGED_KEY)


def settings_over(
    active: ResolvedCredential | Exception,
    rows: Rows | None = None,
    *,
    environment_key: str | None = None,
) -> ProviderSettings:
    """The real gates over these keys and rows. An environment key, when given, is granted."""
    environment = {} if environment_key is None else {"OPENROUTER_API_KEY": environment_key}
    return ProviderSettings(
        NoQualifications(),
        provider_context(environment=environment),
        store=Keys(active, installation_allowed=environment_key is not None),
        rows=rows or Rows(),
    )


def test_a_401_marks_the_key_that_received_it_while_it_is_current() -> None:
    rows = Rows()
    settings = settings_over(stored_key(2), rows)
    asyncio.run(settings.mark_invalid(uuid4(), CredentialReference("app", None, 2)))
    assert rows.recorded == ["invalid"]


def test_a_401_for_a_key_replaced_mid_call_leaves_its_successor_alone() -> None:
    rows = Rows()
    settings = settings_over(stored_key(3), rows)
    asyncio.run(settings.mark_invalid(uuid4(), CredentialReference("app", None, 2)))
    assert rows.recorded == []


def test_a_key_that_wont_decrypt_reads_as_unavailable_not_an_error() -> None:
    settings = settings_over(CredentialUnreadable("arranged"))
    assert asyncio.run(settings.run_intent(uuid4())) == "credential_unavailable"


def test_a_damaged_key_still_gives_the_version_needed_to_replace_it() -> None:
    status = asyncio.run(settings_over(CredentialUnreadable("arranged")).status(uuid4()))
    assert (status.auth_status, status.settings_version) == ("unavailable", 1)


def test_rechecking_a_damaged_key_says_storage_not_an_error() -> None:
    settings = settings_over(CredentialUnreadable("arranged"))
    with pytest.raises(CredentialStorageUnavailable):
        asyncio.run(settings.revalidate(uuid4()))


def test_a_stored_failed_check_blocks_an_environment_key_too() -> None:
    rows = Rows(stored="unavailable")
    settings = settings_over(CredentialUnreadable("arranged"), rows, environment_key=ARRANGED_KEY)
    assert asyncio.run(settings.run_intent(uuid4())) == "credential_unavailable"
    rows.stored = "configured"
    assert asyncio.run(settings.run_intent(uuid4())) == "ready"


class Statements:
    """A connection that answers every select with `row` and keeps each statement it was sent."""

    def __init__(self, row: Row | None) -> None:
        self.row = row
        self.sent: list[str] = []

    async def execute(self, query: str, _params: SqlParams | None = None, /) -> ScriptedRows:
        self.sent.append(query)
        return ScriptedRows([] if self.row is None else [self.row])

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield


def test_reading_a_workspace_with_no_settings_row_writes_nothing_and_gives_the_defaults() -> None:
    """POPS-12: every status read and run-intent check reads; only a writer creates the row, with
    the table's own defaults (supabase/migrations/20261105000005_provider_settings.sql)."""
    connection = Statements(None)
    rows = StoredSettingsRows(connection)
    assert asyncio.run(rows.read(uuid4())) == (0, "missing", None)
    assert asyncio.run(rows.read(uuid4(), lock=True)) == (0, "missing", None)
    assert [query.split()[0] for query in connection.sent] == ["select", "select"]
    assert connection.sent[1].endswith(" for update")
    asyncio.run(rows.ensure(uuid4()))
    assert connection.sent[2].startswith("insert into app_private.provider_settings")


def test_a_stored_row_is_read_as_it_is() -> None:
    checked = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
    rows = StoredSettingsRows(
        Statements({"version": 4, "auth_status": "invalid", "validated_at": checked})
    )
    assert asyncio.run(rows.read(uuid4())) == (4, "invalid", checked)


def test_each_writer_makes_sure_the_row_exists_before_it_records() -> None:
    rows = Rows()
    settings = settings_over(stored_key(2), rows)
    asyncio.run(settings.mark_invalid(uuid4(), CredentialReference("app", None, 2)))
    assert rows.calls == ["ensure", "record invalid"]

    async def valid(_key: SecretStr) -> KeyCheck:
        return KeyCheck.VALID

    rows = Rows()
    checked = ProviderSettings(
        NoQualifications(),
        replace(provider_context(), validate_key=valid),
        store=Keys(stored_key(2)),
        rows=rows,
    )
    asyncio.run(checked.revalidate(uuid4()))
    assert rows.calls == ["ensure", "record configured"]


def test_the_gate_and_the_status_only_read_the_row() -> None:
    rows = Rows()
    settings = settings_over(stored_key(2), rows)
    asyncio.run(settings.run_intent(uuid4()))
    asyncio.run(settings.auth_status(uuid4()))
    assert set(rows.calls) == {"read"}


def catalog_limits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Each time limit Settings gives the shared catalog check."""
    limits: list[float] = []

    async def timed(fetch: Fetch | None, seconds: float) -> CatalogCheck:
        limits.append(seconds)
        return await check_catalog(fetch, seconds)

    monkeypatch.setattr(settings_module, "check_catalog", timed)
    return limits


def test_settings_wait_for_the_catalog_as_long_as_the_http_client_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limits = catalog_limits(monkeypatch)
    settings = settings_over(stored_key(2))
    asyncio.run(settings.status(uuid4()))
    asyncio.run(settings.models())
    assert limits == [SETTINGS_SECONDS, SETTINGS_SECONDS] == [15.0, 15.0]


def test_a_catalog_reply_that_isnt_json_reads_as_unavailable_in_settings_and_the_model_list() -> (
    None
):
    """POPS-13: the fetcher raises ValueError for a 200 whose body isn't JSON. Operations already
    read that as unavailable; Settings and the model list now do too, instead of an error."""

    async def not_json() -> dict[str, Any] | None:
        raise ValueError("arranged: not JSON")

    settings = ProviderSettings(
        NoQualifications(),
        provider_context(fetch=not_json),
        store=Keys(stored_key(2)),
        rows=Rows(),
    )
    assert asyncio.run(settings.status(uuid4())).catalog_status == "unavailable"
    listed = asyncio.run(settings.models())
    assert listed.catalog_status == "unavailable" and listed.fetched_at is None
    assert not any(model.available for model in listed.models)
