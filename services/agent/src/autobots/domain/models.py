"""The two approved model profiles and role policy, MP-01. Pure, with no framework imports."""

from collections.abc import Mapping
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
    }
)
DEFAULT_PROFILE = ModelProfileId.TERRA
# MP-07's initial budgets. Output is sent on every call. Context is the budget compaction works to.
MAX_OUTPUT_TOKENS = 512
CONTEXT_TOKENS = 8_000
ROLE_POLICY_VERSION = 1


class UnknownModelProfile(ValueError):
    """A profile or role outside the approved set. It is refused, never mapped to a default."""


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
    """MP-01's exact order: run role, run-wide, workspace role, workspace default, then Terra."""
    run_roles = {
        approved_role(r): approved_profile(p) for r, p in (run_role_overrides or {}).items()
    }
    run_wide = approved_profile(run_profile) if run_profile is not None else None
    workspace_roles = {
        approved_role(r): approved_profile(p) for r, p in (workspace_role_overrides or {}).items()
    }
    fallback = (
        approved_profile(workspace_default) if workspace_default is not None else DEFAULT_PROFILE
    )

    def resolve(role: ModelRole) -> ModelProfileId:
        if role in run_roles:
            return run_roles[role]
        if run_wide is not None:
            return run_wide
        return workspace_roles.get(role, fallback)

    bindings = {role: resolve(role) for role in ModelRole}
    return RolePolicy(ROLE_POLICY_VERSION, MappingProxyType(bindings))
