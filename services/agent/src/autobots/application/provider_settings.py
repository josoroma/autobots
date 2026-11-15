"""MP-04 and MP-05. Validation uses key metadata and the public catalog, and never a completion."""

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from pydantic import SecretStr

from autobots.adapters.models.catalog import ModelUnavailable, parse_catalog, validated_entry
from autobots.application.catalog_check import SETTINGS_SECONDS, CatalogStatus, check_catalog
from autobots.application.credentials.precedence import (
    EnvironmentCandidate,
    looks_usable,
    resolve_environment_key,
)
from autobots.application.credentials.store import (
    CredentialMissing,
    CredentialReference,
    CredentialStorageUnavailable,
    ProviderCredentialStore,
    ResolvedCredential,
    resolve_for_attempt,
)
from autobots.application.sql import SqlConnection, all_rows, optional_row, stored
from autobots.contracts.settings import (
    AUTH_STATUSES,
    ROUTE_QUALIFICATION_STATUSES,
    AuthStatus,
    CredentialSource,
    ModelAvailability,
    ModelList,
    ProviderStatus,
    RouteQualification,
)
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.domain.models import PROFILES, ModelProfileId, is_offered
from autobots.persistence.rows import ProviderSettingsRow, RouteQualificationRow


class KeyCheck(StrEnum):
    VALID = "valid"
    REJECTED = "rejected"
    UNREACHABLE = "unreachable"


class StaleVersion(FixedRefusal):
    code = "stale_version"


class EnvironmentManaged(FixedRefusal):
    code = "environment_managed"


class InvalidKey(FixedRefusal):
    code = "invalid_key"
    kind = RefusalKind.INVALID


class ValidationUnavailable(FixedRefusal):
    code = "validation_unavailable"
    kind = RefusalKind.UNAVAILABLE


class CredentialRefused(Exception):
    """`run_intent` said no. `code` is its answer, and no key was read."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


KeyValidator = Callable[[SecretStr], Awaitable[KeyCheck]]
CatalogFetcher = Callable[[], Awaitable[dict[str, Any] | None]]
# `run_intent`'s answer, "ready" or the refusing code, for a workspace (XMOD-17). One takes the
# workspace only; the other also takes the connection to read it over, as the worker holds one.
WorkspaceReadiness = Callable[[UUID], Awaitable[str]]
ConnectionReadiness = Callable[[SqlConnection, UUID], Awaitable[str]]


@dataclass(frozen=True)
class ProviderContext:
    """What a process knows about its provider configuration.

    `process_environment` is the live mapping the entry point passes, `os.environ` itself, so an
    environment key is resolved again for each attempt and never copied (model-gateway rule). Its
    repr is hidden, since the environment holds secrets.
    """

    config_root: str
    mode: str
    master_key_file: Path
    process_environment: Mapping[str, str] = field(repr=False)
    validate_key: KeyValidator
    fetch_catalog: CatalogFetcher


class SettingsRows(Protocol):
    """A workspace's provider settings row: its version, authentication state and last check."""

    async def read(
        self, workspace_id: UUID, *, lock: bool = False
    ) -> tuple[int, AuthStatus, datetime | None]: ...

    async def ensure(self, workspace_id: UUID) -> None: ...

    async def record(self, workspace_id: UUID, status: AuthStatus) -> None: ...


class StoredSettingsRows:
    """`app_private.provider_settings`, over one runtime-role connection."""

    def __init__(self, connection: SqlConnection) -> None:
        self._connection = connection

    async def read(
        self, workspace_id: UUID, *, lock: bool = False
    ) -> tuple[int, AuthStatus, datetime | None]:
        """Writes nothing. A workspace with no row reads as the table's defaults: version 0,
        missing and never checked (supabase/migrations/20261105000005_provider_settings.sql). A
        writer calls `ensure` first, so `lock` has a row to hold (SP-014, POPS-12)."""
        suffix = " for update" if lock else ""
        row = await optional_row(
            self._connection,
            ProviderSettingsRow,
            "select version, auth_status, validated_at from app_private.provider_settings "
            f"where workspace_id = %s{suffix}",
            (workspace_id,),
        )
        if row is None:
            return 0, "missing", None
        # The column's check constraint allows these four (POPS-11), so another raises here.
        return row.version, stored(AUTH_STATUSES, row.auth_status), row.validated_at

    async def ensure(self, workspace_id: UUID) -> None:
        """Creates the row at its defaults if it isn't there yet, for a writer."""
        await self._connection.execute(
            "insert into app_private.provider_settings (workspace_id) values (%s) "
            "on conflict (workspace_id) do nothing",
            (workspace_id,),
        )

    async def record(self, workspace_id: UUID, status: AuthStatus) -> None:
        await self._connection.execute(
            "update app_private.provider_settings set version = version + 1, auth_status = %s, "
            "validated_at = case when %s = 'configured' then now() else validated_at end "
            "where workspace_id = %s",
            (status, status, workspace_id),
        )


class ProviderSettings:
    """One workspace's provider settings, over one runtime-role connection."""

    def __init__(
        self,
        connection: SqlConnection,
        context: ProviderContext,
        *,
        store: ProviderCredentialStore | None = None,
        rows: SettingsRows | None = None,
    ) -> None:
        self._connection = connection
        self._context = context
        # Production passes neither, so keys and the settings row come from this connection.
        # Tests pass in-memory ones to reach the gates without a database (PTST-01).
        self._store = (
            store
            if store is not None
            else ProviderCredentialStore(connection, context.master_key_file)
        )
        self._rows: SettingsRows = rows if rows is not None else StoredSettingsRows(connection)

    def _environment_candidate(self) -> EnvironmentCandidate | None:
        return resolve_environment_key(
            self._context.process_environment, self._context.config_root, self._context.mode
        )

    async def _effective_environment(self, workspace_id: UUID) -> EnvironmentCandidate | None:
        candidate = self._environment_candidate()
        if candidate is not None and await self._store.installation_key_allowed(workspace_id):
            return candidate
        return None

    async def catalog_status(self) -> CatalogStatus:
        """Within the HTTP client's own limit. A reply that isn't JSON reads as unavailable."""
        return (await check_catalog(self._context.fetch_catalog, SETTINGS_SECONDS)).status

    async def route_qualifications(self) -> list[RouteQualification]:
        return await read_route_qualifications(self._connection)

    async def auth_status(self, workspace_id: UUID) -> AuthStatus:
        """The stored authentication state only, as `status` reports it, with no catalog fetch."""
        _version, auth_status, _validated_at = await self._rows.read(workspace_id)
        if await self._effective_environment(workspace_id) is not None:
            return auth_status
        try:
            await self._store.load_active(workspace_id)
        except CredentialMissing:
            return "missing"
        except CredentialStorageUnavailable:
            return "unavailable"
        return auth_status

    async def status(self, workspace_id: UUID) -> ProviderStatus:
        version, auth_status, validated_at = await self._rows.read(workspace_id)
        source: CredentialSource = "none"
        credential_id = None
        credential_version = None
        environment = await self._effective_environment(workspace_id)
        if environment is not None:
            source = "environment"
        else:
            try:
                reference = (await self._store.load_active(workspace_id)).reference
                source = "app"
                credential_id, credential_version = reference.credential_id, reference.version
            except CredentialMissing:
                auth_status = "missing"
            except CredentialStorageUnavailable:
                # Still answers for a damaged row, since replacing it needs this version.
                auth_status = "unavailable"
        return ProviderStatus(
            schema_version=1,
            provider="openrouter",
            settings_version=version,
            source=source,
            auth_status=auth_status,
            catalog_status=await self.catalog_status(),
            qualification=await self.route_qualifications(),
            credential_id=credential_id,
            credential_version=credential_version,
            validated_at=validated_at,
        )

    def _check_version(self, current: int, expected: int) -> None:
        if current != expected:
            raise StaleVersion("the settings changed; reload them")

    async def save_credential(self, workspace_id: UUID, draft: str, expected: int) -> None:
        """Validate first. Only a valid key commits, so a bad draft leaves the prior key alone."""
        if await self._effective_environment(workspace_id) is not None:
            raise EnvironmentManaged("the environment supplies this key; change it there")
        current, _, _ = await self._rows.read(workspace_id)
        self._check_version(current, expected)
        if not looks_usable(draft):
            raise InvalidKey("that key was not accepted")
        result = await self._context.validate_key(SecretStr(draft))
        if result is KeyCheck.REJECTED:
            raise InvalidKey("that key was not accepted")
        if result is KeyCheck.UNREACHABLE:
            raise ValidationUnavailable("the key could not be checked right now")
        async with self._connection.transaction():
            await self._rows.ensure(workspace_id)
            current, _, _ = await self._rows.read(workspace_id, lock=True)
            self._check_version(current, expected)
            await self._store.save(workspace_id, draft)
            await self._rows.record(workspace_id, "configured")

    async def disconnect(self, workspace_id: UUID, expected: int) -> None:
        """Removes the app credential only. An environment key is neither deleted nor overridden."""
        async with self._connection.transaction():
            await self._rows.ensure(workspace_id)
            current, _, _ = await self._rows.read(workspace_id, lock=True)
            self._check_version(current, expected)
            await self._connection.execute(
                "update app_private.provider_credentials set status = 'deleted' "
                "where workspace_id = %s and provider = 'openrouter' and status = 'active'",
                (workspace_id,),
            )
            await self._rows.record(workspace_id, "missing")

    async def revalidate(self, workspace_id: UUID) -> None:
        """Checks the effective key's metadata. A failure never falls through to another source."""
        environment = await self._effective_environment(workspace_id)
        if environment is not None:
            secret = SecretStr(environment.value)
        else:
            # A row this key can't open raises the store's CredentialUnreadable, a storage error.
            secret = (await self._store.load_active(workspace_id)).client_secret()
        result = await self._context.validate_key(secret)
        statuses: dict[KeyCheck, AuthStatus] = {
            KeyCheck.VALID: "configured",
            KeyCheck.REJECTED: "invalid",
            KeyCheck.UNREACHABLE: "unavailable",
        }
        status = statuses[result]
        await self._rows.ensure(workspace_id)
        await self._rows.record(workspace_id, status)

    async def run_intent(self, workspace_id: UUID) -> str:
        """Every model call's gate. Saved drafts and page loads never reach past this into a run."""
        environment = await self._effective_environment(workspace_id)
        _, stored_status, _ = await self._rows.read(workspace_id)
        if environment is not None:
            if not looks_usable(environment.value) or stored_status == "invalid":
                return "credential_invalid"
            return "credential_unavailable" if stored_status == "unavailable" else "ready"
        try:
            await self._store.load_active(workspace_id)
        except CredentialMissing:
            return "credentials_required"
        except CredentialStorageUnavailable:
            return "credential_unavailable"
        if stored_status == "invalid":
            return "credential_invalid"
        return "credential_unavailable" if stored_status == "unavailable" else "ready"

    async def credential_for_attempt(self, workspace_id: UUID) -> ResolvedCredential:
        """The same gate as `run_intent`, then the current key. Hold it only to build a client."""
        code = await self.run_intent(workspace_id)
        if code != "ready":
            raise CredentialRefused(code)
        return await resolve_for_attempt(self._store, workspace_id, self._environment_candidate())

    async def mark_invalid(self, workspace_id: UUID, used: CredentialReference) -> None:
        """MP-08, after a 401: no attempt or resume until the key is replaced or rechecked.

        Only if that key is still the current one. A key replaced mid-call says nothing about its
        successor.
        """
        environment = await self._effective_environment(workspace_id)
        if environment is not None:
            current = CredentialReference(environment.source, None, None)
        else:
            try:
                current = (await self._store.load_active(workspace_id)).reference
            except (CredentialMissing, CredentialStorageUnavailable):
                return
        if current == used:
            await self._rows.ensure(workspace_id)
            await self._rows.record(workspace_id, "invalid")

    async def models(self) -> ModelList:
        """Within the HTTP client's own limit. A catalog that doesn't answer, or answers with
        something that isn't JSON, lists every profile as unavailable."""
        payload = (await check_catalog(self._context.fetch_catalog, SETTINGS_SECONDS)).payload
        now = datetime.now(UTC)
        snapshot = parse_catalog(payload or {}, retrieved_at=now, revision="live")
        models = []
        for profile in PROFILES.values():
            entry = None
            try:
                entry = validated_entry(profile, snapshot, now)
                available = True
            except ModelUnavailable:
                available = False
            models.append(
                ModelAvailability(
                    profile=profile.id,
                    canonical_id=profile.canonical_id,
                    wire_id=profile.wire_id,
                    available=available,
                    offered=is_offered(profile.id),
                    input_per_million_micro_usd=entry.listed_input_per_million if entry else None,
                    output_per_million_micro_usd=entry.listed_output_per_million if entry else None,
                    capabilities=sorted(entry.supported_parameters) if entry else [],
                )
            )
        status: CatalogStatus = "available" if payload is not None else "unavailable"
        return ModelList(
            schema_version=1,
            catalog_status=status,
            fetched_at=now if payload is not None else None,
            models=models,
        )


async def read_route_qualifications(connection: SqlConnection) -> list[RouteQualification]:
    """Only a stored record for the route's own canonical model counts, MP-04. Neither a key nor
    the catalog changes this."""
    rows = await all_rows(
        connection,
        RouteQualificationRow,
        "select profile, canonical_id, status, qualified_on, configuration, limits "
        "from agent_runtime.route_qualifications",
    )
    recorded = {row.profile: row for row in rows}
    return [
        qualification_from_record(profile.id, profile.canonical_id, recorded.get(profile.id))
        for profile in PROFILES.values()
    ]


def qualification_from_record(
    profile: ModelProfileId, canonical_id: str, record: RouteQualificationRow | None
) -> RouteQualification:
    """An unknown stored status raises, instead of reaching a client."""
    if record is None or record.canonical_id != canonical_id:
        return RouteQualification(
            profile=profile,
            canonical_id=canonical_id,
            status="not_qualified",
            qualified_on=None,
            configuration=None,
            limits=None,
        )
    return RouteQualification(
        profile=profile,
        canonical_id=canonical_id,
        status=stored(ROUTE_QUALIFICATION_STATUSES, record.status),
        qualified_on=record.qualified_on,
        configuration=record.configuration,
        limits=record.limits,
    )


def policy_overrides_json(overrides: dict[str, str]) -> str:
    return json.dumps(overrides, sort_keys=True)
