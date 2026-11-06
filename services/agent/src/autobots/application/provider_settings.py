"""MP-04 and MP-05. Validation uses key metadata and the public catalog, and never a completion."""

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import SecretStr

from autobots.adapters.models.catalog import ModelUnavailable, parse_catalog, validated_entry
from autobots.application.credentials.crypto import CredentialDecryptionError
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
from autobots.contracts.settings import (
    ModelAvailability,
    ModelList,
    ProviderStatus,
    RouteQualification,
)
from autobots.domain.models import PROFILES, ModelProfileId, is_offered


class KeyCheck(StrEnum):
    VALID = "valid"
    REJECTED = "rejected"
    UNREACHABLE = "unreachable"


class StaleVersion(Exception):
    code = "stale_version"


class EnvironmentManaged(Exception):
    code = "environment_managed"


class InvalidKey(Exception):
    code = "invalid_key"


class ValidationUnavailable(Exception):
    code = "validation_unavailable"


class CredentialRefused(Exception):
    """`run_intent` said no. `code` is its answer, and no key was read."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


KeyValidator = Callable[[SecretStr], Awaitable[KeyCheck]]
CatalogFetcher = Callable[[], Awaitable[dict[str, Any] | None]]


@dataclass(frozen=True)
class ProviderContext:
    config_root: str
    mode: str
    master_key_file: Path
    process_environment: dict[str, str]
    validate_key: KeyValidator
    fetch_catalog: CatalogFetcher


class ProviderSettings:
    """One workspace's provider settings, over one runtime-role connection."""

    def __init__(self, connection: Any, context: ProviderContext) -> None:
        self._connection = connection
        self._context = context
        self._store = ProviderCredentialStore(connection, context.master_key_file)

    def _environment_candidate(self) -> EnvironmentCandidate | None:
        return resolve_environment_key(
            self._context.process_environment, self._context.config_root, self._context.mode
        )

    async def _effective_environment(self, workspace_id: UUID) -> EnvironmentCandidate | None:
        candidate = self._environment_candidate()
        if candidate is not None and await self._store.installation_key_allowed(workspace_id):
            return candidate
        return None

    async def _settings_row(self, workspace_id: UUID, lock: bool = False) -> tuple[int, str, Any]:
        await self._connection.execute(
            "insert into app_private.provider_settings (workspace_id) values (%s) "
            "on conflict (workspace_id) do nothing",
            (workspace_id,),
        )
        suffix = " for update" if lock else ""
        cursor = await self._connection.execute(
            "select version, auth_status, validated_at from app_private.provider_settings "
            f"where workspace_id = %s{suffix}",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        return row[0], row[1], row[2]

    async def _record(self, workspace_id: UUID, status: str) -> None:
        await self._connection.execute(
            "update app_private.provider_settings set version = version + 1, auth_status = %s, "
            "validated_at = case when %s = 'configured' then now() else validated_at end "
            "where workspace_id = %s",
            (status, status, workspace_id),
        )

    async def catalog_status(self) -> str:
        try:
            return "available" if await self._context.fetch_catalog() is not None else "unavailable"
        except OSError:
            return "unavailable"

    async def route_qualifications(self) -> list[RouteQualification]:
        return await read_route_qualifications(self._connection)

    async def status(self, workspace_id: UUID) -> ProviderStatus:
        version, auth_status, validated_at = await self._settings_row(workspace_id)
        source = "none"
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
            except (CredentialStorageUnavailable, CredentialDecryptionError):
                # Still answers for a damaged row, since replacing it needs this version.
                auth_status = "unavailable"
        return ProviderStatus(
            schema_version=1,
            provider="openrouter",
            settings_version=version,
            source=source,  # type: ignore[arg-type]
            auth_status=auth_status,  # type: ignore[arg-type]
            catalog_status=await self.catalog_status(),  # type: ignore[arg-type]
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
        current, _, _ = await self._settings_row(workspace_id)
        self._check_version(current, expected)
        if not looks_usable(draft):
            raise InvalidKey("that key was not accepted")
        result = await self._context.validate_key(SecretStr(draft))
        if result is KeyCheck.REJECTED:
            raise InvalidKey("that key was not accepted")
        if result is KeyCheck.UNREACHABLE:
            raise ValidationUnavailable("the key could not be checked right now")
        async with self._connection.transaction():
            current, _, _ = await self._settings_row(workspace_id, lock=True)
            self._check_version(current, expected)
            await self._store.save(workspace_id, draft)
            await self._record(workspace_id, "configured")

    async def disconnect(self, workspace_id: UUID, expected: int) -> None:
        """Removes the app credential only. An environment key is neither deleted nor overridden."""
        async with self._connection.transaction():
            current, _, _ = await self._settings_row(workspace_id, lock=True)
            self._check_version(current, expected)
            await self._connection.execute(
                "update app_private.provider_credentials set status = 'deleted' "
                "where workspace_id = %s and status = 'active'",
                (workspace_id,),
            )
            await self._record(workspace_id, "missing")

    async def revalidate(self, workspace_id: UUID) -> None:
        """Checks the effective key's metadata. A failure never falls through to another source."""
        environment = await self._effective_environment(workspace_id)
        if environment is not None:
            secret = SecretStr(environment.value)
        else:
            try:
                secret = (await self._store.load_active(workspace_id)).client_secret()
            except CredentialDecryptionError:
                raise CredentialStorageUnavailable("the stored key cannot be read") from None
        result = await self._context.validate_key(secret)
        status = {
            KeyCheck.VALID: "configured",
            KeyCheck.REJECTED: "invalid",
            KeyCheck.UNREACHABLE: "unavailable",
        }[result]
        await self._settings_row(workspace_id)
        await self._record(workspace_id, status)

    async def run_intent(self, workspace_id: UUID) -> str:
        """Every model call's gate. Saved drafts and page loads never reach past this into a run."""
        environment = await self._effective_environment(workspace_id)
        _, stored_status, _ = await self._settings_row(workspace_id)
        if environment is not None:
            if not looks_usable(environment.value) or stored_status == "invalid":
                return "credential_invalid"
            return "credential_unavailable" if stored_status == "unavailable" else "ready"
        try:
            await self._store.load_active(workspace_id)
        except CredentialMissing:
            return "credentials_required"
        except (CredentialStorageUnavailable, CredentialDecryptionError):
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
            except (CredentialMissing, CredentialStorageUnavailable, CredentialDecryptionError):
                return
        if current == used:
            await self._settings_row(workspace_id)
            await self._record(workspace_id, "invalid")

    async def models(self) -> ModelList:
        payload = await self._context.fetch_catalog()
        now = datetime.now(UTC)
        snapshot = parse_catalog(payload or {}, retrieved_at=now, revision="live")
        models = []
        for profile in PROFILES.values():
            try:
                validated_entry(profile, snapshot, now)
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
                )
            )
        status = "available" if payload is not None else "unavailable"
        return ModelList(schema_version=1, catalog_status=status, models=models)  # type: ignore[arg-type]


async def read_route_qualifications(connection: Any) -> list[RouteQualification]:
    """Only a stored record for the route's own canonical model counts, MP-04. Neither a key nor
    the catalog changes this."""
    cursor = await connection.execute(
        "select profile, canonical_id, status, qualified_on, configuration, limits "
        "from agent_runtime.route_qualifications"
    )
    stored = {row[0]: row for row in await cursor.fetchall()}
    return [
        qualification_from_record(profile.id, profile.canonical_id, stored.get(profile.id))
        for profile in PROFILES.values()
    ]


def qualification_from_record(
    profile: ModelProfileId, canonical_id: str, record: Sequence[Any] | None
) -> RouteQualification:
    if record is None or record[1] != canonical_id:
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
        status=record[2],
        qualified_on=record[3],
        configuration=record[4],
        limits=record[5],
    )


def policy_overrides_json(overrides: dict[str, str]) -> str:
    return json.dumps(overrides, sort_keys=True)
