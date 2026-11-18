"""The approved model profiles and role policy, MP-01 and Decision 0019. No framework imports."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from autobots.domain.errors import FixedRefusal, RefusalKind


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


@dataclass(frozen=True)
class ModelRoute:
    """A worker takes this from the run's frozen policy. `run_goal` refuses one that differs."""

    role: str
    profile: str
    wire_id: str
    worst_case_micro_usd: int
    # For a request larger than the worst case already assumes. Zero where no price is known.
    input_per_million_micro_usd: int = 0
    # Where a higher rate starts, past the size assumed. Nothing is reserved at that rate.
    tier_from_tokens: int | None = None


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
# MP-07's budgets. Output is sent on every call, and is 4,096 tokens so one save holds a 2,000 to
# 3,000-word document (Decision 0034 L1). Context is the budget compaction works to.
MAX_OUTPUT_TOKENS = 4_096
CONTEXT_TOKENS = 8_000
# How long one model call may stream before it's interrupted, long enough for a full reply
# (Decision 0034 L4). A cancel still interrupts it at once.
MODEL_CALL_SECONDS = 300.0
# What one call reserves for its prompt, an estimate since no tokenizer is pinned. Compaction keeps
# messages near 24K characters, and the system prompt and tool schemas add some. Mostly Latin text
# stays under this, but text with more than a token per character can pass it, and nothing refuses
# that. The reported cost settles each call either way. A route's worst case assumes it, and the
# loop reserves past it for a larger request (application/loop_policy.py).
RESERVED_PROMPT_TOKENS = 32_000
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


class ProfileNotOffered(FixedRefusal):
    """A typed reason, and nothing starts. No other model is ever put in its place. `reason` says
    which model and why, and is safe to show. A request that names the profile is refused as
    invalid; where a saved choice names it, the raise passes CONFLICT (PolicyNotOffered)."""

    code = NOT_OFFERED_CODE
    kind = RefusalKind.INVALID

    def __init__(self, reason: str, *, kind: RefusalKind | None = None) -> None:
        super().__init__(reason, kind=kind)
        self.reason = reason


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


class BindingSource(StrEnum):
    """Which step of MP-01's order chose a role's binding, PRD-Studio MD-02."""

    RUN_OVERRIDE = "run_override"
    WORKSPACE_OVERRIDE = "workspace_override"
    WORKSPACE_DEFAULT = "workspace_default"
    BUILTIN_DEFAULT = "builtin_default"


@dataclass(frozen=True)
class RolePolicy:
    """The complete effective map, frozen at admission. Children and compaction inherit it."""

    version: int
    bindings: Mapping[ModelRole, ModelProfileId]
    # Empty for a run frozen before sources were recorded.
    sources: Mapping[ModelRole, BindingSource] = MappingProxyType({})

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

    def resolve(role: ModelRole) -> tuple[ModelProfileId, BindingSource]:
        if role in run_roles:
            return run_roles[role], BindingSource.RUN_OVERRIDE
        if run_wide is not None:
            return run_wide, BindingSource.RUN_OVERRIDE
        if role in workspace_roles:
            return workspace_roles[role], BindingSource.WORKSPACE_OVERRIDE
        if workspace_wide is not None:
            return workspace_wide, BindingSource.WORKSPACE_DEFAULT
        return builtin_default(role), BindingSource.BUILTIN_DEFAULT

    resolved = {role: resolve(role) for role in ModelRole}
    return RolePolicy(
        ROLE_POLICY_VERSION,
        MappingProxyType({role: found[0] for role, found in resolved.items()}),
        MappingProxyType({role: found[1] for role, found in resolved.items()}),
    )
