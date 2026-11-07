"""US-14.1: the catalog is the registry, discovery never grants, and no key value appears."""

import json
from uuid import uuid4

import pytest

from autobots.application.tool_catalog import (
    all_descriptors,
    catalog_digest,
    catalog_registry,
    tool_catalog,
)
from autobots.application.tool_gateway import ToolGateway, ToolScope
from autobots.domain.tool_catalog import PLANNED_TOOLS
from autobots.domain.tools import OperationClass
from test_api import client, headers, token

FAKE_TOKEN = "zz_fixture_q8w7e6r5t4y3u2i1"
FAKE_REPOSITORY = "zq9xv7-fixture/kq4wm2-fixture"


def test_every_registered_tool_appears_once_and_nothing_else() -> None:
    registry = catalog_registry()
    descriptors = all_descriptors({}, registry)
    registered = {(tool.tool_id, tool.version) for tool in registry.definitions()}
    listed = [(item.tool_id, item.version) for item in descriptors if item.registered]
    assert sorted(listed) == sorted(registered)
    assert len(listed) == len(set(listed))
    planned = {(item.tool_id, item.version) for item in descriptors if not item.registered}
    assert planned == {(tool.tool_id, tool.version) for tool in PLANNED_TOOLS}
    assert not planned & registered


def test_each_registered_tool_is_fully_described() -> None:
    for tool in catalog_registry().definitions():
        assert tool.title, f"{tool.tool_id} needs a title"
        item = next(
            entry
            for entry in all_descriptors({})
            if (entry.tool_id, entry.version) == (tool.tool_id, tool.version)
        )
        assert item.input_schema == tool.input_model.model_json_schema()
        assert item.output_schema == tool.output_model.model_json_schema()
        assert item.operation_class == tool.operation_class.value
        assert item.limits is not None
        assert item.limits.timeout_seconds == tool.timeout_seconds
        inputs = {field.path for field in item.fields if field.direction == "input"}
        assert set(tool.input_model.model_fields) <= inputs
        public = {field.path for field in item.fields if field.public and "." not in field.path}
        names = {*tool.public_input_fields, *tool.public_output_fields}
        assert public <= names
        assert set(tool.public_input_fields) <= set(tool.input_model.model_fields)
        assert set(tool.public_output_fields) <= set(tool.output_model.model_fields)


def test_planned_tools_are_disabled_and_never_registered() -> None:
    registry = catalog_registry()
    for tool in PLANNED_TOOLS:
        assert tool.operation_class is OperationClass.ARBITRARY_EXECUTION
        assert registry.get(tool.tool_id, tool.version) is None
    browse = next(item for item in all_descriptors({}) if item.tool_id == "browse_goal")
    assert browse.availability == "disabled_by_policy"
    assert browse.grantable_to == []


@pytest.mark.asyncio
async def test_discovery_does_not_grant() -> None:
    registry = catalog_registry()
    scope = ToolScope(workspace_id=uuid4(), run_id=uuid4(), generation=1, tools={"calculate": 1})
    shown = {entry["name"] for entry in registry.catalog(scope)}
    assert shown == {"calculate"}
    assert "read_run_file" in {item.tool_id for item in tool_catalog({}).tools}
    # Refused before the connection is touched, so before any effect.
    result = await ToolGateway(registry).execute(None, scope, "read_run_file", {"path": "x"})
    assert (result.outcome.value, result.code) == ("denied", "tool_not_granted")


def test_no_key_value_appears_in_the_catalog() -> None:
    environ = {"GITHUB_TOKEN": FAKE_TOKEN, "GITHUB_REPOSITORY": FAKE_REPOSITORY}
    catalog = tool_catalog(environ)
    encoded = json.dumps(catalog.model_dump(mode="json"))
    for value in environ.values():
        for start in range(0, len(value) - 7):
            assert value[start : start + 8] not in encoded
    github = next(item for item in catalog.tools if item.tool_id == "create_github_issue")
    assert github.availability == "available"
    assert github.key_requirement is not None
    assert github.key_requirement.variables == ["GITHUB_REPOSITORY", "GITHUB_TOKEN"]


def test_a_missing_key_shows_its_typed_reason() -> None:
    github = next(
        item
        for item in tool_catalog({"GITHUB_TOKEN": " "}).tools
        if item.tool_id == "create_github_issue"
    )
    assert (github.availability, github.availability_reason) == (
        "key_missing",
        "github_key_missing",
    )


def test_the_digest_names_the_catalog_not_the_install() -> None:
    without = tool_catalog({})
    configured = tool_catalog({"GITHUB_TOKEN": FAKE_TOKEN, "GITHUB_REPOSITORY": FAKE_REPOSITORY})
    assert (
        without.catalog_digest == configured.catalog_digest == catalog_digest(all_descriptors({}))
    )


def test_filters_narrow_tools_and_keep_groups() -> None:
    catalog = tool_catalog({}, group="files")
    assert {item.group for item in catalog.tools} == {"files"}
    assert any(group.group == "planning" for group in catalog.groups)
    assert {item.tool_id for item in tool_catalog({}, availability="disabled_by_policy").tools} == {
        "browse_goal"
    }


def test_the_routes_need_a_member() -> None:
    assert client().get("/v1/tools", headers=headers()).status_code == 401


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/v1/tools", 200),
        ("/v1/tools?group=files", 200),
        ("/v1/tools?group=nonsense", 422),
        ("/v1/tools/calculate", 200),
        ("/v1/tools/calculate/versions/1", 200),
        ("/v1/tools/calculate/versions/9", 404),
        ("/v1/tools/no_such_tool", 404),
    ],
)
def test_the_routes_answer_members(path: str, status: int) -> None:
    reply = client().get(path, headers=headers(token()))
    assert reply.status_code == status
    if path == "/v1/tools/calculate/versions/1":
        assert reply.json()["tool_id"] == "calculate"


# US-14.2: a group grant expands to explicit tools when a version is saved.


def test_a_group_expands_to_the_tools_an_expert_may_name() -> None:
    from autobots.application.experts import expand_groups
    from autobots.contracts.experts import ExpertConfig

    expanded = expand_groups(ExpertConfig(tools=["calculate"], tool_groups=["files"]), {})
    assert expanded.tools == [
        "calculate",
        "publish_artifact",
        "read_csv",
        "read_run_file",
        "save_artifact",
        "store_remote_file",
    ]
    assert expanded.tool_groups == ["files"]


def test_a_saved_expansion_does_not_follow_the_group() -> None:
    from autobots.application.experts import expand_groups
    from autobots.contracts.experts import ExpertConfig

    saved = expand_groups(ExpertConfig(tool_groups=["files"]), {})
    # The saved config holds the explicit list, so reading it back never re-expands it.
    assert ExpertConfig.model_validate(saved.model_dump()).tools == saved.tools


@pytest.mark.parametrize(
    ("config", "code"),
    [
        ({"tool_groups": ["planning"]}, "expert_tool_group_empty"),
        ({"tool_groups": ["files", "files"]}, "expert_tool_group_duplicated"),
        ({"tools": ["create_github_issue"]}, "expert_tool_unavailable"),
        ({"tool_groups": ["connectors"]}, "expert_tool_unavailable"),
        ({"tools": ["browse_goal"]}, "expert_tool_not_available"),
    ],
)
def test_an_unavailable_or_empty_grant_is_refused(config: dict[str, object], code: str) -> None:
    from autobots.application.experts import ExpertRefused, expand_groups, validate_config
    from autobots.contracts.experts import ExpertConfig

    with pytest.raises(ExpertRefused) as refused:
        validate_config(expand_groups(ExpertConfig.model_validate(config), {}), {})
    assert refused.value.code == code


def test_a_configured_connector_can_be_granted() -> None:
    from autobots.application.experts import expand_groups, validate_config
    from autobots.contracts.experts import ExpertConfig

    environ = {"GITHUB_TOKEN": FAKE_TOKEN, "GITHUB_REPOSITORY": FAKE_REPOSITORY}
    config = expand_groups(ExpertConfig(tool_groups=["connectors"]), environ)
    validate_config(config, environ)
    assert config.tools == ["create_github_issue"]


# US-14.5: availability and a provider key's use make no request of their own. Sockets are blocked
# here (conftest), so any connection would fail the test.


def test_availability_with_a_real_looking_key_makes_no_request() -> None:
    environ = {"GITHUB_TOKEN": "ghp_" + "a" * 36, "GITHUB_REPOSITORY": "owner/repo"}
    github = next(
        item for item in tool_catalog(environ).tools if item.tool_id == "create_github_issue"
    )
    assert github.availability == "available"


@pytest.mark.asyncio
async def test_a_provider_client_reads_its_key_per_attempt_and_only_uses_its_transport() -> None:
    import httpx

    from autobots.adapters.provider_http import provider_client, provider_key
    from autobots.application.tool_gateway import ToolFailed
    from autobots.domain.tool_catalog import KeyRequirement

    requirement = KeyRequirement("tavily", ("TAVILY_API_KEY",))
    with pytest.raises(ToolFailed) as missing:
        provider_key(requirement, {"TAVILY_API_KEY": "  "})
    assert str(missing.value) == "tavily_key_missing"
    seen: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        return httpx.Response(200, json={})

    key = provider_key(requirement, {"TAVILY_API_KEY": "tvly-fixture"})["TAVILY_API_KEY"]
    async with provider_client(
        "https://api.tavily.invalid",
        {"Authorization": f"Bearer {key}"},
        httpx.MockTransport(answer),
    ) as client:
        reply = await client.post("/search", json={})
    assert reply.status_code == 200
    assert seen == ["Bearer tvly-fixture"]
    assert client.follow_redirects is False
