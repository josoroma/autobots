"""Key checks and decisions that need no database. Real rows run in scripts/qualify_identity.py.

`ProviderSettings` takes its credential store and settings rows through its seams here, so its own
gates run as production runs them (PTST-01).
"""

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.application.credentials.crypto import CredentialDecryptionError
from autobots.application.credentials.store import (
    CredentialReference,
    CredentialStorageUnavailable,
    ProviderCredentialStore,
    ResolvedCredential,
)
from autobots.application.provider_settings import (
    KeyCheck,
    ProviderSettings,
    qualification_from_record,
)
from autobots.contracts.settings import CredentialDraft, ProviderStatus
from autobots.domain.models import PROFILES, ModelProfileId
from fake_openrouter import ARRANGED_KEY, provider_context


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
    record = (ModelProfileId.TERRA, canonical, "qualified_with_limits", date(2026, 11, 5), "c", "l")

    def status(stored: tuple[Any, ...] | None) -> str:
        return qualification_from_record(ModelProfileId.TERRA, canonical, stored).status

    assert status(record) == "qualified_with_limits"
    assert status(None) == "not_qualified"
    assert status((record[0], "openai/another-model", *record[2:])) == "not_qualified"
    empty = qualification_from_record(ModelProfileId.TERRA, canonical, None)
    assert (empty.qualified_on, empty.configuration, empty.limits) == (None, None, None)


class Keys(ProviderCredentialStore):
    """The stored key as an arranged answer, a credential or what reading it raised, and whether
    this workspace may use the installation's key."""

    def __init__(
        self, active: ResolvedCredential | Exception, *, installation_allowed: bool = False
    ) -> None:
        super().__init__(None, Path("/nonexistent"))
        self.active = active
        self.installation_allowed = installation_allowed

    async def load_active(self, workspace_id: UUID) -> ResolvedCredential:
        if isinstance(self.active, Exception):
            raise self.active
        return self.active

    async def installation_key_allowed(self, workspace_id: UUID) -> bool:
        return self.installation_allowed


class Rows:
    """The settings row in memory: version 1 at its stored status, and each status recorded."""

    def __init__(self, stored: str = "configured") -> None:
        self.stored = stored
        self.recorded: list[str] = []

    async def read(
        self, workspace_id: UUID, *, lock: bool = False
    ) -> tuple[int, str, datetime | None]:
        return 1, self.stored, None

    async def record(self, workspace_id: UUID, status: str) -> None:
        self.recorded.append(status)


class NoQualifications:
    """A connection with no route qualification stored, the only read left on it here."""

    async def execute(self, *_: object) -> "NoQualifications":
        return self

    async def fetchall(self) -> list[tuple[object, ...]]:
        return []


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
    settings = settings_over(CredentialDecryptionError())
    assert asyncio.run(settings.run_intent(uuid4())) == "credential_unavailable"


def test_a_damaged_key_still_gives_the_version_needed_to_replace_it() -> None:
    status = asyncio.run(settings_over(CredentialDecryptionError()).status(uuid4()))
    assert (status.auth_status, status.settings_version) == ("unavailable", 1)


def test_rechecking_a_damaged_key_says_storage_not_an_error() -> None:
    settings = settings_over(CredentialDecryptionError())
    with pytest.raises(CredentialStorageUnavailable):
        asyncio.run(settings.revalidate(uuid4()))


def test_a_stored_failed_check_blocks_an_environment_key_too() -> None:
    rows = Rows(stored="unavailable")
    settings = settings_over(CredentialDecryptionError(), rows, environment_key=ARRANGED_KEY)
    assert asyncio.run(settings.run_intent(uuid4())) == "credential_unavailable"
    rows.stored = "configured"
    assert asyncio.run(settings.run_intent(uuid4())) == "ready"
