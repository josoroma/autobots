"""Safe provider settings. Nothing here carries a stored key; only a request holds a draft."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.models import EffectiveRolePolicy
from autobots.contracts.primitives import STRICT_CONTRACT, Identifier
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
    """Not strict, so JSON strings become enums. Unknown fields and values are still refused."""

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
