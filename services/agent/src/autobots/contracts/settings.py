"""Safe provider settings. Nothing here carries a stored key; only a request holds a draft."""

from datetime import date
from typing import Literal, get_args

from pydantic import BaseModel, Field

from autobots.contracts.models import EffectiveRolePolicy
from autobots.contracts.primitives import (
    LAX_CONTRACT,
    STRICT_CONTRACT,
    Count,
    Identifier,
    MicroUsd,
    UtcTimestamp,
)
from autobots.domain.budgets import budget_choices
from autobots.domain.models import ModelProfileId

AuthStatus = Literal["missing", "configured", "invalid", "unavailable"]
CatalogStatus = Literal["available", "unavailable", "unknown"]
RouteQualificationStatus = Literal["qualified_with_limits", "not_qualified"]
CredentialSource = Literal["none", "app", "environment"]
AUTH_STATUSES: tuple[AuthStatus, ...] = get_args(AuthStatus)
ROUTE_QUALIFICATION_STATUSES: tuple[RouteQualificationStatus, ...] = get_args(
    RouteQualificationStatus
)


class RouteQualification(BaseModel):
    """One route's stored live result. No record means not qualified, and the rest stay empty."""

    model_config = STRICT_CONTRACT

    profile: ModelProfileId
    canonical_id: str
    status: RouteQualificationStatus
    qualified_on: date | None
    configuration: str | None
    limits: str | None


class ProviderStatus(BaseModel):
    """Source, authentication, catalog and qualification are independent facts, MP-04."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    provider: Literal["openrouter"]
    settings_version: int
    source: CredentialSource
    auth_status: AuthStatus
    catalog_status: CatalogStatus
    qualification: list[RouteQualification]
    credential_id: Identifier | None
    credential_version: int | None
    validated_at: UtcTimestamp | None


class CredentialDraft(BaseModel):
    """Transient. It is validated and encrypted, and never returned, logged or echoed."""

    model_config = STRICT_CONTRACT

    draft_key: str = Field(min_length=1, max_length=512)
    expected_version: int = Field(ge=0)


class ExpectedVersion(BaseModel):
    model_config = STRICT_CONTRACT

    expected_version: int = Field(ge=0)


KeyOrVarName = Literal[
    "tavily", "jina", "serpapi", "github_token", "github_repository", "browser_executor"
]


class KeyOrVar(BaseModel):
    """One Settings → Keys & vars item for this workspace, PK-07. A secret never carries its value,
    prefix, length or hash. A value carries its resolved value, which isn't secret."""

    model_config = STRICT_CONTRACT

    name: KeyOrVarName
    variable: str
    kind: Literal["secret", "value"]
    source: Literal["settings", "environment"] | None
    value: str | None
    version: int


class KeysAndVars(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    items: list[KeyOrVar]


class KeyOrVarDraft(BaseModel):
    """Transient. A secret is checked and sealed, and never returned, logged or echoed."""

    model_config = STRICT_CONTRACT

    value: str = Field(min_length=1, max_length=512)
    expected_version: int = Field(ge=0)


class ModelAvailability(BaseModel):
    model_config = STRICT_CONTRACT

    profile: ModelProfileId
    canonical_id: str
    wire_id: str
    available: bool
    # New work can choose it. An approved model that isn't offered stays listed, with its record.
    offered: bool
    # From the catalog only, PRD-Studio MD-01, and never a qualification. Micro-USD per 1M tokens,
    # None when this exact model isn't in a fresh catalog or its base price can't be read.
    input_per_million_micro_usd: MicroUsd | None
    output_per_million_micro_usd: MicroUsd | None
    capabilities: list[str]


class ModelList(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    catalog_status: CatalogStatus
    # When the catalog behind these facts was fetched, or None when it couldn't be.
    fetched_at: UtcTimestamp | None
    models: list[ModelAvailability]


class ModelPolicyUpdate(BaseModel):
    # Not strict, so JSON strings become enums. Unknown fields and values are still refused.

    model_config = LAX_CONTRACT

    expected_version: Count
    # None names no workspace default, so each role takes its built-in default (MD-02).
    default_profile: ModelProfileId | None
    role_overrides: dict[str, ModelProfileId]


class ModelPolicyState(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    version: int
    default_profile: ModelProfileId | None
    role_overrides: dict[str, ModelProfileId]
    policy: EffectiveRolePolicy


ModelSourceName = Literal["openrouter", "local"]
# The owner's llama-server for the Local default: serving its model, serving another, or not there.
LocalRuntimeStatus = Literal["ready", "other_model", "not_running"]


class LocalRuntime(BaseModel):
    """The runtime's health for one local profile (Decision 0041 A3, A13). Its address is the
    owner's loopback, never anything a run's box sees."""

    model_config = STRICT_CONTRACT

    status: LocalRuntimeStatus
    port: int
    served_model_id: str | None
    # Whether the file the server reports serving has the profile's pinned SHA-256. None while
    # it's still being hashed, or when the server doesn't report its file.
    sha256_matches: bool | None
    sha256_checking: bool


class LocalProfileState(BaseModel):
    model_config = STRICT_CONTRACT

    profile: ModelProfileId
    name: str
    offered: bool
    # Why it isn't offered, safe to show. None when it is.
    reason: str | None
    qualified_on: date | None
    limits: str | None
    # The runs this profile has matched on Local (A7). None is recorded before US-23.4 to US-23.6.
    matched_runs: list[str]


class ModelSourceState(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    # The model policy row's version, which a switch and a policy save both expect.
    version: int
    source: ModelSourceName
    local_profile: ModelProfileId | None
    local_profiles: list[LocalProfileState]
    # The roles Local must cover: executor, and researcher while an Expert grants browse_goal.
    roles_needed: list[str]
    # Those no offered local profile covers, so a switch to Local would be refused.
    roles_uncovered: list[str]
    # The runtime for the Local default, or the first offered local profile. None when none is.
    runtime: LocalRuntime | None


class ModelSourceUpdate(BaseModel):
    # Not strict, so JSON strings become enums. Unknown fields and values are still refused.

    model_config = LAX_CONTRACT

    expected_version: Count
    source: ModelSourceName
    # The Local default to keep. None keeps the saved one while it's offered, else the first.
    local_profile: ModelProfileId | None = None


class BudgetRange(BaseModel):
    """US$0.25 to US$5.00 in US$0.25 steps, never above what's left of the daily cap (D11)."""

    model_config = STRICT_CONTRACT

    min_micro_usd: MicroUsd
    # Below `min_micro_usd` when nothing is left today, so no budget can be chosen.
    max_micro_usd: MicroUsd
    step_micro_usd: MicroUsd
    default_micro_usd: MicroUsd
    remaining_daily_micro_usd: MicroUsd


def budget_range(remaining_daily: int) -> BudgetRange:
    choices = budget_choices(remaining_daily)
    return BudgetRange(
        min_micro_usd=choices.lowest,
        max_micro_usd=choices.highest,
        step_micro_usd=choices.step,
        default_micro_usd=choices.default,
        remaining_daily_micro_usd=choices.remaining_daily,
    )


class RunIntentCheck(BaseModel):
    """Whether model-backed work could proceed. It creates no run and calls no model."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    ready: bool
    code: Literal[
        "ready",
        "model_not_offered",
        "credentials_required",
        "credential_invalid",
        "credential_unavailable",
    ]
    # The budgets a person may choose now, D11. None when spend can't be read.
    budget: BudgetRange | None = None


class PreviewProfile(BaseModel):
    """One profile and the roles that would resolve to it, HM-03."""

    model_config = STRICT_CONTRACT

    profile: ModelProfileId
    label: str
    canonical_id: str
    roles: list[str]


class RunPreview(BaseModel):
    """What a run would use, read before Run. It creates nothing and calls no model."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    budget: BudgetRange | None
    profiles: list[PreviewProfile]
    # The tools the run would be granted, without the plan tools every goal run has.
    tools: list[str]
