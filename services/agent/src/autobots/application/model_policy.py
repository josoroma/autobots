"""A workspace's saved model policy: its version, its default and its role overrides (PRD-Model-
Providers MP-05, MD-02 and MD-03; refactor plan R-55, PAPI-01).

A save or a reset takes the row's lock, refuses an expected version that isn't the saved one with
nothing written, and writes the next version in the same transaction. A workspace with no row reads
as version 0, naming no default, so each role reads its built-in default as admission resolves it.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from autobots.application.provider_settings import policy_overrides_json
from autobots.application.sql import SqlConnection, optional_row
from autobots.domain.errors import FixedRefusal
from autobots.domain.models import ModelProfileId, require_offered, resolve_role_policy
from autobots.persistence.rows import ModelPolicyRow


class PolicyChanged(FixedRefusal):
    """The policy was saved again since the version the request expected. Nothing is written."""

    code = "stale_version"


@dataclass(frozen=True)
class StoredPolicy:
    version: int = 0
    default_profile: str | None = None
    role_overrides: Mapping[str, str] = field(default_factory=dict)


def validated_choice(
    default_profile: ModelProfileId | None, role_overrides: Mapping[str, ModelProfileId]
) -> tuple[str | None, dict[str, str]]:
    """A requested default and overrides as stored values, once every role is approved and every
    named profile is offered for new runs. Raises UnknownModelProfile, then ProfileNotOffered."""
    overrides = {role: profile.value for role, profile in role_overrides.items()}
    chosen_default = None if default_profile is None else default_profile.value
    resolve_role_policy(workspace_default=chosen_default, workspace_role_overrides=overrides)
    require_offered([*([default_profile] if default_profile else []), *role_overrides.values()])
    return chosen_default, overrides


async def read_model_policy(connection: SqlConnection, workspace_id: UUID) -> StoredPolicy:
    row = await optional_row(
        connection,
        ModelPolicyRow,
        "select version, default_profile, role_overrides from app_private.model_policies "
        "where workspace_id = %s",
        (workspace_id,),
    )
    if row is None:
        return StoredPolicy()
    return StoredPolicy(row.version, row.default_profile, row.role_overrides or {})


async def save_model_policy(
    connection: SqlConnection,
    workspace_id: UUID,
    *,
    expected_version: int,
    default_profile: str | None,
    role_overrides: dict[str, str],
) -> StoredPolicy:
    """Replaces the default and every override, as `validated_choice` returned them. Raises
    PolicyChanged."""
    async with connection.transaction():
        cursor = await connection.execute(
            "select version from app_private.model_policies where workspace_id = %s for update",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        current = row[0] if row else 0
        if current != expected_version:
            raise PolicyChanged(f"saved version {current}, expected {expected_version}")
        await connection.execute(
            "insert into app_private.model_policies "
            "(workspace_id, version, default_profile, role_overrides) values (%s, %s, %s, %s) "
            "on conflict (workspace_id) do update set version = excluded.version, "
            "default_profile = excluded.default_profile, role_overrides = excluded.role_overrides",
            (workspace_id, current + 1, default_profile, policy_overrides_json(role_overrides)),
        )
    return StoredPolicy(current + 1, default_profile, role_overrides)


async def reset_role_overrides(
    connection: SqlConnection, workspace_id: UUID, *, expected_version: int
) -> StoredPolicy:
    """Reset all, MD-03: every role override is cleared and the workspace default is kept. Raises
    PolicyChanged."""
    async with connection.transaction():
        cursor = await connection.execute(
            "select version, default_profile from app_private.model_policies "
            "where workspace_id = %s for update",
            (workspace_id,),
        )
        row = await cursor.fetchone()
        current, kept = (row[0], row[1]) if row else (0, None)
        if current != expected_version:
            raise PolicyChanged(f"saved version {current}, expected {expected_version}")
        await connection.execute(
            "insert into app_private.model_policies "
            "(workspace_id, version, default_profile, role_overrides) values (%s, %s, %s, '{}') "
            "on conflict (workspace_id) do update set version = excluded.version, "
            "role_overrides = excluded.role_overrides",
            (workspace_id, current + 1, kept),
        )
    return StoredPolicy(current + 1, kept, {})
