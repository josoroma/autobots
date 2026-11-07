"""The approved model profiles and role policy, MP-01 and Decision 0019. No framework imports."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class ModelRole(StrEnum):
    COORDINATOR = "coordinator"
    ROUTER = "router"
    PLANNER = "planner"
    EXECUTOR = "executor"
    RESEARCHER = "researcher"
    CODER = "coder"
    REVIEWER = "reviewer"
    EVALUATOR = "evaluator"
    SUMMARIZER = "summarizer"
    MEMORY_CURATOR = "memory_curator"
    SKILL_LEARNER = "skill_learner"
    TOOL_REPAIR = "tool_repair"
    WORKFLOW_GENERATOR = "workflow_generator"
    GENERAL_PURPOSE = "general_purpose"


class ModelProfileId(StrEnum):
    DEEPSEEK_FLASH = "openrouter_deepseek_flash"
    TERRA = "openrouter_terra"
    SOL = "openrouter_sol"


@dataclass(frozen=True)
class ModelProfile:
    id: ModelProfileId
    canonical_id: str
    wire_id: str


PROFILES: Mapping[ModelProfileId, ModelProfile] = MappingProxyType(
    {
        ModelProfileId.DEEPSEEK_FLASH: ModelProfile(
            ModelProfileId.DEEPSEEK_FLASH,
            "deepseek/deepseek-v4.1-flash-20261017",
            "deepseek/deepseek-v4.1-flash-1017",
        ),
        ModelProfileId.TERRA: ModelProfile(
            ModelProfileId.TERRA,
            "openai/gpt-6.1-terra-20261026",
            "openai/gpt-6.1-terra",
        ),
        ModelProfileId.SOL: ModelProfile(
            ModelProfileId.SOL,
            "openai/gpt-6.1-sol-20260929",
            "openai/gpt-6.1-sol",
        ),
    }
)
DEFAULT_PROFILE = ModelProfileId.TERRA
# MP-07's initial budgets. Output is sent on every call. Context is the budget compaction works to.
MAX_OUTPUT_TOKENS = 512
CONTEXT_TOKENS = 8_000
ROLE_POLICY_VERSION = 1


class UnknownModelProfile(ValueError):
    """A profile or role outside the approved set. It is refused, never mapped to a default."""


# Approved stays approved. This is what new work can choose, by Decision 0013. A run already
# admitted keeps its frozen route, so this is checked where new work starts, not in the registry.
# Sol joined once its route was qualified on 2026-11-07, by Decision 0019 S2 and S4 (US-14.15).
OFFERED_FOR_NEW_RUNS = frozenset({ModelProfileId.TERRA, ModelProfileId.SOL})
NOT_OFFERED_CODE = "model_not_offered"
NOT_OFFERED_MESSAGE = "DeepSeek isn't offered for new runs until it's qualified."
NOT_OFFERED_MESSAGES: Mapping[ModelProfileId, str] = MappingProxyType(
    {
        ModelProfileId.DEEPSEEK_FLASH: NOT_OFFERED_MESSAGE,
        ModelProfileId.SOL: "Sol isn't offered for new runs until its route is qualified.",
    }
)


class ProfileNotOffered(Exception):
    """A typed reason, and nothing starts. No other model is ever put in its place."""

    code = NOT_OFFERED_CODE


def is_offered(profile: "ModelProfileId") -> bool:
    return profile in OFFERED_FOR_NEW_RUNS


def require_offered(profiles: Iterable["ModelProfileId"]) -> None:
    """Names the first refused profile, so the reason says which model and why."""
    for profile in profiles:
        if not is_offered(profile):
            raise ProfileNotOffered(
                NOT_OFFERED_MESSAGES.get(ModelProfileId(profile), NOT_OFFERED_MESSAGE)
            )


def builtin_default(role: "ModelRole") -> "ModelProfileId":
    """The last step of MP-01's order: Sol for `researcher` once Sol is offered, else Terra."""
    if role is ModelRole.RESEARCHER and is_offered(ModelProfileId.SOL):
        return ModelProfileId.SOL
    return DEFAULT_PROFILE


def approved_profile(value: object) -> ModelProfileId:
    try:
        return ModelProfileId(str(value))
    except ValueError:
        raise UnknownModelProfile("not an approved model profile") from None


def approved_role(value: object) -> ModelRole:
    try:
        return ModelRole(str(value))
    except ValueError:
        raise UnknownModelProfile("not a known model role") from None


@dataclass(frozen=True)
class RolePolicy:
    """The complete effective map, frozen at admission. Children and compaction inherit it."""

    version: int
    bindings: Mapping[ModelRole, ModelProfileId]

    def profile_for(self, role: ModelRole) -> ModelProfile:
        return PROFILES[self.bindings[role]]


def resolve_role_policy(
    *,
    run_role_overrides: Mapping[str, str] | None = None,
    run_profile: str | None = None,
    workspace_role_overrides: Mapping[str, str] | None = None,
    workspace_default: str | None = None,
) -> RolePolicy:
    """MP-01's exact order: run role, run-wide, workspace role, workspace default, then the
    role's built-in default (Sol for `researcher` once offered, Terra otherwise)."""
    run_roles = {
        approved_role(r): approved_profile(p) for r, p in (run_role_overrides or {}).items()
    }
    run_wide = approved_profile(run_profile) if run_profile is not None else None
    workspace_roles = {
        approved_role(r): approved_profile(p) for r, p in (workspace_role_overrides or {}).items()
    }
    workspace_wide = approved_profile(workspace_default) if workspace_default is not None else None

    def resolve(role: ModelRole) -> ModelProfileId:
        if role in run_roles:
            return run_roles[role]
        if run_wide is not None:
            return run_wide
        if role in workspace_roles:
            return workspace_roles[role]
        return workspace_wide if workspace_wide is not None else builtin_default(role)

    bindings = {role: resolve(role) for role in ModelRole}
    return RolePolicy(ROLE_POLICY_VERSION, MappingProxyType(bindings))
