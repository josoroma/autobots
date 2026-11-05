"""Role precedence, catalog association and refused options, on a fake transport only."""

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import openrouter
import pytest
from pydantic import SecretStr

from autobots.adapters.models.catalog import (
    CatalogEntry,
    CatalogSnapshot,
    ModelUnavailable,
    parse_catalog,
)
from autobots.adapters.models.factory import (
    FORBIDDEN_OPTIONS,
    OPENROUTER_BASE_URL,
    UnsupportedRequestOption,
    chat_model,
    prepare_attempt,
)
from autobots.contracts.models import effective_policy
from autobots.domain.models import (
    DEFAULT_PROFILE,
    PROFILES,
    ModelProfileId,
    ModelRole,
    UnknownModelProfile,
    resolve_role_policy,
)
from fake_openrouter import ARRANGED_KEY, FakeOpenRouter

REPOSITORY = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
ROLES_FROM_PRD = {
    "coordinator",
    "router",
    "planner",
    "executor",
    "researcher",
    "coder",
    "reviewer",
    "evaluator",
    "summarizer",
    "memory_curator",
    "skill_learner",
    "tool_repair",
    "workflow_generator",
    "general_purpose",
}
DEEPSEEK = ModelProfileId.DEEPSEEK_FLASH
ASTRA = ModelProfileId.ASTRA
DEEPSEEK_PARAMETERS = frozenset(
    {"temperature", "top_p", "max_tokens", "parallel_tool_calls", "seed"}
)
ASTRA_PARAMETERS = frozenset({"max_tokens", "reasoning"})


def catalog(*entries: CatalogEntry, at: datetime = NOW) -> CatalogSnapshot:
    return CatalogSnapshot("fixture-revision", at, entries)


def healthy_catalog(at: datetime = NOW) -> CatalogSnapshot:
    return catalog(
        CatalogEntry(
            PROFILES[DEEPSEEK].wire_id, PROFILES[DEEPSEEK].canonical_id, DEEPSEEK_PARAMETERS
        ),
        CatalogEntry(PROFILES[ASTRA].wire_id, PROFILES[ASTRA].canonical_id, ASTRA_PARAMETERS),
        at=at,
    )


def test_exactly_two_profiles_with_their_identities() -> None:
    assert {key.value: (p.canonical_id, p.wire_id) for key, p in PROFILES.items()} == {
        "openrouter_deepseek_flash": (
            "deepseek/deepseek-v4.1-flash-20261017",
            "deepseek/deepseek-v4.1-flash-1017",
        ),
        "openrouter_astra": ("openai/gpt-6-astra-20260903", "openai/gpt-6-astra"),
    }
    assert DEFAULT_PROFILE is DEEPSEEK


def test_a_new_workspace_binds_all_14_roles_to_deepseek() -> None:
    policy = resolve_role_policy()
    assert {role.value for role in policy.bindings} == ROLES_FROM_PRD
    assert set(policy.bindings.values()) == {DEEPSEEK}


def test_the_documented_precedence() -> None:
    coder, router, planner = ModelRole.CODER, ModelRole.ROUTER, ModelRole.PLANNER
    # Workspace default, then a workspace role override over it.
    policy = resolve_role_policy(workspace_default="openrouter_astra")
    assert policy.bindings[planner] is ASTRA
    policy = resolve_role_policy(
        workspace_default="openrouter_astra",
        workspace_role_overrides={"planner": "openrouter_deepseek_flash"},
    )
    assert policy.bindings[planner] is DEEPSEEK
    assert policy.bindings[coder] is ASTRA
    # A run-wide selection applies to every role, over workspace settings.
    policy = resolve_role_policy(
        run_profile="openrouter_astra",
        workspace_role_overrides={"planner": "openrouter_deepseek_flash"},
    )
    assert set(policy.bindings.values()) == {ASTRA}
    # A run-specific role override wins over everything.
    policy = resolve_role_policy(
        run_role_overrides={"router": "openrouter_deepseek_flash"},
        run_profile="openrouter_astra",
        workspace_default="openrouter_astra",
    )
    assert policy.bindings[router] is DEEPSEEK
    assert policy.bindings[coder] is ASTRA


@pytest.mark.parametrize(
    "arguments",
    [
        {"run_profile": "openai/gpt-6-astra"},
        {"run_profile": "local"},
        {"workspace_default": "openrouter_auto"},
        {"run_role_overrides": {"coder": "anthropic/claude"}},
        {"workspace_role_overrides": {"coder": ""}},
        {"run_role_overrides": {"embedder": "openrouter_astra"}},
    ],
)
def test_an_unknown_profile_or_role_is_refused(arguments: dict[str, Any]) -> None:
    with pytest.raises(UnknownModelProfile):
        resolve_role_policy(**arguments)


def test_a_policy_cannot_be_changed_after_admission() -> None:
    policy = resolve_role_policy()
    with pytest.raises(TypeError):
        policy.bindings[ModelRole.CODER] = ASTRA  # type: ignore[index]


def test_the_effective_map_can_be_displayed_before_dispatch() -> None:
    body = effective_policy(resolve_role_policy(run_profile="openrouter_astra"))
    assert len(body.bindings) == 14
    assert {binding.wire_id for binding in body.bindings} == {"openai/gpt-6-astra"}


@pytest.mark.parametrize(
    ("snapshot", "reason"),
    [
        (healthy_catalog(at=NOW - timedelta(minutes=5, seconds=1)), "stale"),
        (healthy_catalog(at=NOW + timedelta(minutes=5)), "future"),
        (catalog(), "missing"),
        (
            catalog(
                CatalogEntry(PROFILES[DEEPSEEK].wire_id, "deepseek/other-20270101", frozenset())
            ),
            "drifted",
        ),
        (
            catalog(
                CatalogEntry(
                    PROFILES[DEEPSEEK].wire_id, PROFILES[DEEPSEEK].canonical_id, frozenset()
                ),
                CatalogEntry(PROFILES[DEEPSEEK].wire_id, "deepseek/other", frozenset()),
            ),
            "ambiguous",
        ),
    ],
)
def test_catalog_problems_block_dispatch(snapshot: CatalogSnapshot, reason: str) -> None:
    with pytest.raises(ModelUnavailable, match=reason) as caught:
        prepare_attempt(resolve_role_policy(), ModelRole.CODER, snapshot, now=NOW)
    assert caught.value.code == "model_unavailable"


def test_a_catalog_exactly_at_the_limit_is_accepted() -> None:
    snapshot = healthy_catalog(at=NOW - timedelta(minutes=5))
    assert prepare_attempt(
        resolve_role_policy(), ModelRole.CODER, snapshot, now=NOW
    ).catalog_revision


def test_a_drifted_model_is_never_substituted() -> None:
    policy = resolve_role_policy(run_profile="openrouter_astra")
    snapshot = catalog(
        CatalogEntry(
            PROFILES[DEEPSEEK].wire_id, PROFILES[DEEPSEEK].canonical_id, DEEPSEEK_PARAMETERS
        ),
        CatalogEntry(PROFILES[ASTRA].wire_id, "openai/gpt-7", ASTRA_PARAMETERS),
    )
    with pytest.raises(ModelUnavailable, match="drifted"):
        prepare_attempt(policy, ModelRole.CODER, snapshot, now=NOW)


@pytest.mark.parametrize("option", sorted(FORBIDDEN_OPTIONS))
def test_routing_options_are_refused(option: str) -> None:
    with pytest.raises(UnsupportedRequestOption):
        prepare_attempt(
            resolve_role_policy(),
            ModelRole.CODER,
            healthy_catalog(),
            options={option: "x"},
            now=NOW,
        )


def test_an_option_the_catalog_lacks_is_refused_for_that_model() -> None:
    astra = resolve_role_policy(run_profile="openrouter_astra")
    for option in ("temperature", "top_p", "parallel_tool_calls"):
        with pytest.raises(UnsupportedRequestOption, match=option):
            prepare_attempt(
                astra, ModelRole.CODER, healthy_catalog(), options={option: 0.5}, now=NOW
            )
    deepseek = resolve_role_policy()
    attempt = prepare_attempt(
        deepseek, ModelRole.CODER, healthy_catalog(), options={"temperature": 0.5}, now=NOW
    )
    assert attempt.options == {"temperature": 0.5}


def test_an_unknown_option_is_refused() -> None:
    with pytest.raises(UnsupportedRequestOption, match="not a known"):
        prepare_attempt(
            resolve_role_policy(), ModelRole.CODER, healthy_catalog(), options={"magic": 1}, now=NOW
        )


def recording_factory() -> tuple[list[dict[str, Any]], list[str], Any]:
    requests: list[dict[str, Any]] = []
    urls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "fake",
                "object": "chat.completion",
                "created": 1,
                "model": requests[-1]["model"],
                "system_fingerprint": "fake",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "fake"},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    def factory(key: str) -> openrouter.OpenRouter:
        return openrouter.OpenRouter(
            api_key=key,
            server_url=OPENROUTER_BASE_URL,
            client=httpx.Client(transport=httpx.MockTransport(handle)),
        )

    return requests, urls, factory


@pytest.mark.parametrize(
    ("policy_arguments", "wire_id"),
    [
        ({}, "deepseek/deepseek-v4.1-flash-1017"),
        ({"run_profile": "openrouter_astra"}, "openai/gpt-6-astra"),
    ],
)
def test_the_request_on_the_wire(policy_arguments: dict[str, Any], wire_id: str) -> None:
    requests, urls, factory = recording_factory()
    attempt = prepare_attempt(
        resolve_role_policy(**policy_arguments), ModelRole.CODER, healthy_catalog(), now=NOW
    )
    chat_model(attempt, SecretStr(ARRANGED_KEY), client_factory=factory).invoke("hello")
    assert urls == ["https://openrouter.ai/api/v1/chat/completions"]
    body = requests[0]
    assert body["model"] == wire_id
    assert body["provider"] == {"require_parameters": True, "allow_fallbacks": False}
    assert not {"models", "route", "plugins"} & set(body)


def test_astra_sends_no_sampler_settings_by_default() -> None:
    requests, _, factory = recording_factory()
    attempt = prepare_attempt(
        resolve_role_policy(run_profile="openrouter_astra"),
        ModelRole.CODER,
        healthy_catalog(),
        now=NOW,
    )
    chat_model(attempt, SecretStr(ARRANGED_KEY), client_factory=factory).invoke("hello")
    for name in ("temperature", "top_p", "parallel_tool_calls"):
        assert requests[0].get(name) is None


def test_the_environment_cannot_redirect_the_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_BASE", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "arranged-other-key")
    attempt = prepare_attempt(resolve_role_policy(), ModelRole.CODER, healthy_catalog(), now=NOW)
    model = chat_model(attempt, SecretStr(ARRANGED_KEY))
    assert model.openrouter_api_base == OPENROUTER_BASE_URL
    assert model.openrouter_api_key is not None
    assert model.openrouter_api_key.get_secret_value() == ARRANGED_KEY
    assert model.max_retries == 0
    assert model.route is None
    assert model.plugins is None


def test_a_real_catalog_snapshot_parses_to_the_approved_association() -> None:
    data = json.loads((REPOSITORY / "research/openrouter-model-catalog.json").read_text())
    found: list[dict[str, Any]] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            if "canonical_slug" in value:
                found.append(value)
                return
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    snapshot = parse_catalog({"data": found}, retrieved_at=NOW, revision="dated-snapshot")
    for profile in (DEEPSEEK, ASTRA):
        attempt = prepare_attempt(
            resolve_role_policy(run_profile=profile.value), ModelRole.CODER, snapshot, now=NOW
        )
        assert attempt.profile.id is profile
    astra = resolve_role_policy(run_profile="openrouter_astra")
    with pytest.raises(UnsupportedRequestOption):
        prepare_attempt(astra, ModelRole.CODER, snapshot, options={"temperature": 0.1}, now=NOW)


def test_only_the_factory_builds_an_inference_client() -> None:
    source_root = REPOSITORY / "services/agent/src/autobots"
    forbidden = {
        "langchain_openrouter",
        "openrouter",
        "langchain_openai",
        "openai",
        "init_chat_model",
    }
    offenders = []
    for path in source_root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0], *(alias.name for alias in node.names)]
            if forbidden & set(names) and path.name != "factory.py":
                offenders.append(path.name)
    assert offenders == []


def test_fake_transport_helper_stays_available() -> None:
    assert FakeOpenRouter().models() == []
