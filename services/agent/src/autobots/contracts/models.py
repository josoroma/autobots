"""The effective role map shown before dispatch. Roles and profiles have one definition."""

from typing import Literal

from pydantic import BaseModel

from autobots.contracts.primitives import STRICT_CONTRACT
from autobots.domain.models import PROFILES, ModelProfileId, ModelRole, RolePolicy


class RoleBinding(BaseModel):
    model_config = STRICT_CONTRACT

    role: ModelRole
    profile: ModelProfileId
    canonical_id: str
    wire_id: str


class EffectiveRolePolicy(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    role_policy_version: int
    bindings: list[RoleBinding]


def effective_policy(policy: RolePolicy) -> EffectiveRolePolicy:
    return EffectiveRolePolicy(
        schema_version=1,
        role_policy_version=policy.version,
        bindings=[
            RoleBinding(
                role=role,
                profile=profile,
                canonical_id=PROFILES[profile].canonical_id,
                wire_id=PROFILES[profile].wire_id,
            )
            for role, profile in policy.bindings.items()
        ],
    )
