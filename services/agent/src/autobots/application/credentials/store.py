"""Encrypted credential rows and transient resolution. Durable state holds references only."""

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn
from uuid import UUID, uuid4

from pydantic import SecretStr

from autobots.application.credentials.crypto import (
    CredentialDecryptionError,
    Sealed,
    associated_data,
    seal,
    unseal,
)
from autobots.application.credentials.master_key import (
    MasterKeyUnavailable,
    create_master_key,
    load_master_key,
)
from autobots.application.credentials.precedence import (
    EnvironmentCandidate,
    looks_usable,
)
from autobots.application.sql import SqlConnection, optional_row
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.persistence.rows import SealedCredentialRow

PROVIDER = "openrouter"
KEY_VERSION = 1


class CredentialStorageUnavailable(FixedRefusal):
    """The master key is missing or unsafe, or a stored row can't be opened with it. Never a cause
    to try another key or source (SP-007)."""

    code = "credential_storage_unavailable"
    kind = RefusalKind.UNAVAILABLE


class CredentialUnreadable(CredentialStorageUnavailable):
    """A stored row this master key can't open: the wrong key, altered bytes or a row moved between
    identities. Its own type, so a log that names only types tells it from a missing key (refactor
    plan R-41, POPS-09)."""


class CredentialBlocked(Exception):
    """A higher-priority key is present and unusable. Lower sources are not consulted."""

    code = "credential_invalid"


class CredentialMissing(FixedRefusal):
    code = "credential_missing"


@dataclass(frozen=True)
class CredentialReference:
    """What a checkpoint or run may record. It holds no secret."""

    source: str
    credential_id: UUID | None
    version: int | None


class ResolvedCredential:
    """Lives only inside one attempt, and is deliberately neither a dataclass nor a SecretStr.

    LangGraph's checkpoint serializer writes dataclass fields and `SecretStr` values in plaintext.
    This plain class has no encoding there, so putting it in graph state fails instead of leaking.
    Call `client_secret()` only at the point of building a client.
    """

    __slots__ = ("_value", "reference")

    def __init__(self, reference: CredentialReference, value: str) -> None:
        self.reference = reference
        self._value = value

    def client_secret(self) -> SecretStr:
        return SecretStr(self._value)

    def __repr__(self) -> str:
        return f"ResolvedCredential(reference={self.reference!r}, value=<hidden>)"

    def __reduce_ex__(self, protocol: object) -> NoReturn:
        raise TypeError("a resolved credential cannot be serialized")

    def __getstate__(self) -> NoReturn:
        raise TypeError("a resolved credential cannot be serialized")


def resolve_for_attempt_blocked_check(candidate: EnvironmentCandidate) -> None:
    if not looks_usable(candidate.value):
        raise CredentialBlocked("the configured key is not usable")


class ProviderCredentialStore:
    """Takes an open async connection with the restricted runtime role."""

    def __init__(self, connection: SqlConnection, key_path: Path, provider: str = PROVIDER) -> None:
        self._connection = connection
        self._key_path = key_path
        self._provider = provider

    async def _encrypted_rows_exist(self) -> bool:
        cursor = await self._connection.execute(
            "select 1 from app_private.provider_credentials limit 1"
        )
        return await cursor.fetchone() is not None

    async def _writable_key(self) -> bytes:
        """A key is generated only when none exists and nothing depends on one."""
        if not self._key_path.exists() and not self._key_path.is_symlink():
            if await self._encrypted_rows_exist():
                raise CredentialStorageUnavailable("the master key is unavailable")
            try:
                create_master_key(self._key_path)
            except (MasterKeyUnavailable, OSError) as error:
                raise CredentialStorageUnavailable("the master key is unavailable") from error
        try:
            return load_master_key(self._key_path)
        except MasterKeyUnavailable as error:
            raise CredentialStorageUnavailable("the master key is unavailable") from error

    async def save(self, workspace_id: UUID, plaintext: str) -> CredentialReference:
        """Store a validated key as a new version, superseding the previous one atomically."""
        key = await self._writable_key()
        async with self._connection.transaction():
            cursor = await self._connection.execute(
                "select credential_id, version from app_private.provider_credentials "
                "where workspace_id = %s and provider = %s and status = 'active' for update",
                (workspace_id, self._provider),
            )
            active = await cursor.fetchone()
            credential_id = active[0] if active else uuid4()
            version = active[1] + 1 if active else 1
            if active:
                await self._connection.execute(
                    "update app_private.provider_credentials set status = 'superseded' "
                    "where credential_id = %s and version = %s",
                    (credential_id, active[1]),
                )
            aad = associated_data(workspace_id, self._provider, credential_id, version)
            sealed = seal(key, plaintext, aad)
            await self._connection.execute(
                "insert into app_private.provider_credentials (credential_id, version, "
                "workspace_id, provider, ciphertext, nonce, tag, key_version, status) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, 'active')",
                (
                    credential_id,
                    version,
                    workspace_id,
                    self._provider,
                    sealed.ciphertext,
                    sealed.nonce,
                    sealed.tag,
                    KEY_VERSION,
                ),
            )
        return CredentialReference("app", credential_id, version)

    async def load_active(self, workspace_id: UUID) -> ResolvedCredential:
        row = await optional_row(
            self._connection,
            SealedCredentialRow,
            "select credential_id, version, ciphertext, nonce, tag "
            "from app_private.provider_credentials "
            "where workspace_id = %s and provider = %s and status = 'active'",
            (workspace_id, self._provider),
        )
        if row is None:
            raise CredentialMissing("no credential is configured")
        try:
            key = load_master_key(self._key_path)
        except MasterKeyUnavailable as error:
            raise CredentialStorageUnavailable("the master key is unavailable") from error
        aad = associated_data(workspace_id, self._provider, row.credential_id, row.version)
        sealed = Sealed(bytes(row.ciphertext), bytes(row.nonce), bytes(row.tag))
        try:
            plaintext = unseal(key, sealed, aad)
        except CredentialDecryptionError as error:
            raise CredentialUnreadable("the stored key cannot be read") from error
        return ResolvedCredential(
            CredentialReference("app", row.credential_id, row.version), plaintext
        )

    async def installation_key_allowed(self, workspace_id: UUID) -> bool:
        cursor = await self._connection.execute(
            "select 1 from app_private.installation_credential_grants where workspace_id = %s",
            (workspace_id,),
        )
        return await cursor.fetchone() is not None


async def resolve_for_attempt(
    store: ProviderCredentialStore,
    workspace_id: UUID,
    candidate: EnvironmentCandidate | None,
) -> ResolvedCredential:
    """Called inside each attempt, so a rotation applies to the next one without a restart.

    An installation key counts only for a workspace explicitly granted it. When it counts, nothing
    below it is consulted, even if it is unusable.
    """
    if candidate is not None and await store.installation_key_allowed(workspace_id):
        resolve_for_attempt_blocked_check(candidate)
        return ResolvedCredential(
            CredentialReference(candidate.source, None, None), candidate.value
        )
    return await store.load_active(workspace_id)
