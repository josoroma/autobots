"""Safe provider settings. Nothing here carries a stored key; only a request holds a draft."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.models import EffectiveRolePolicy
from autobots.contracts.primitives import STRICT_CONTRACT, Identifier
from autobots.domain.budgets import budget_choices
from autobots.domain.models import ModelProfileId

AuthStatus = Literal["missing", "configured", "invalid", "unavailable"]
CatalogStatus = Literal["available", "unavailable", "unknown"]
RouteQualificationStatus = Literal["qualified_with_limits", "not_qualified"]
CredentialSource = Literal["none", "app", "environment"]


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
    validated_at: datetime | None


class CredentialDraft(BaseModel):
    """Transient. It is validated and encrypted, and never returned, logged or echoed."""

    model_config = STRICT_CONTRACT

    draft_key: str = Field(min_length=1, max_length=512)
    expected_version: int = Field(ge=0)


class ExpectedVersion(BaseModel):
    model_config = STRICT_CONTRACT

    expected_version: int = Field(ge=0)


KeyOrVarName = Literal["tavily", "jina", "github_token", "github_repository", "browser_executor"]


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
    input_per_million_micro_usd: int | None
    output_per_million_micro_usd: int | None
    capabilities: list[str]


class ModelList(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    catalog_status: CatalogStatus
    # When the catalog behind these facts was fetched, or None when it couldn't be.
    fetched_at: datetime | None
    models: list[ModelAvailability]


class ModelPolicyUpdate(BaseModel):
    # Not strict, so JSON strings become enums. Unknown fields and values are still refused.

    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_version: int = Field(ge=0)
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


class BudgetRange(BaseModel):
    """US$0.25 to US$5.00 in US$0.25 steps, never above what's left of the daily cap (D11)."""

    model_config = STRICT_CONTRACT

    min_micro_usd: int
    # Below `min_micro_usd` when nothing is left today, so no budget can be chosen.
    max_micro_usd: int
    step_micro_usd: int
    default_micro_usd: int
    remaining_daily_micro_usd: int


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
