"""US-17.1 offline: browsing's YOLO setting, Decision 0035 Y1 to Y4. These tests cover the
approval waiver, the Expert's browse domains, the tool row's `typing`, and the setting's view. The
database, the routes and admission's freezing are checked on a disposable stack
(tests/db/checks/browsing_yolo_check.py)."""

import asyncio
from collections.abc import Mapping
from typing import Any, NoReturn
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.api.browsing_routes import _view
from autobots.application import browsing_tool
from autobots.application.browsing_settings import BrowsingSetting
from autobots.application.experts import expert_record, expert_view_config
from autobots.application.loop_admission import active_middleware
from autobots.application.tool_definitions import (
    ApprovalPolicy,
    ToolContext,
    ToolFailed,
    ToolScope,
)
from autobots.application.tool_gateway import Released, hold_for_approval
from autobots.contracts.browsing import BrowseGoalInput
from autobots.contracts.experts import ExpertConfig
from autobots.domain.tool_guides import TOOL_GUIDES
from autobots.domain.tools import OperationClass
from autobots.persistence.records import read_expert_config
from fake_api import MEMBER, ApiClient
from sql_fakes import RuledConnection

ARGS = {
    "task": "Read the guide.",
    "start_url": "https://en.wikivoyage.org/",
    "allowed_domains": ["en.wikivoyage.org"],
}


def yolo(on: bool, domains: str | None = None) -> RuledConnection:
    """A run whose browsing is YOLO or not, and whose Expert lists `domains` as stored JSON."""
    return RuledConnection(
        ("browsing_yolo", [(on,)]),
        ("browse_domains", [{"domains": domains}]),
        ("", []),
    )


class Untouched:
    """An executor that must never be reached."""

    def __getattr__(self, name: str) -> NoReturn:
        raise AssertionError(f"the executor was touched: {name}")


class Middleware:
    async def admitted(self, request: object, handler: object, route: object) -> NoReturn:
        raise AssertionError("no model call is expected")


def browse(connection: RuledConnection) -> str:
    """The handler's refusal code for one call, with an executor that fails if touched."""
    runtime = browsing_tool.BrowsingRuntime(
        Untouched(),  # type: ignore[arg-type]  # a fake that proves nothing reached the executor
        object(),
        "route",  # type: ignore[arg-type]  # a placeholder route the handler never reads here
    )
    tool = browsing_tool.browse_tool(runtime, qualified=lambda: True)
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 1})

    async def go() -> str:
        with active_middleware(Middleware()):
            try:
                await tool.handler(
                    BrowseGoalInput.model_validate(ARGS),
                    ToolContext(connection, scope, None),
                )
            except ToolFailed as failed:
                return str(failed)
        return "ran"

    return asyncio.run(go())


def test_an_expert_with_no_browse_domains_cannot_browse_under_yolo() -> None:
    assert browse(yolo(True, None)) == "browse_domains_missing"
    assert browse(yolo(True, "[]")) == "browse_domains_missing"


def test_a_domain_outside_the_experts_list_is_refused_before_the_executor() -> None:
    connection = yolo(True, '["google.com", "gstatic.com"]')
    assert browse(connection) == "browse_domain_not_granted"


def test_a_subdomain_of_a_listed_domain_is_inside_it() -> None:
    assert browsing_tool.domain_refusal(["en.wikivoyage.org"], ["wikivoyage.org"]) is None
    assert browsing_tool.domain_refusal(["wikivoyage.org"], ["wikivoyage.org"]) is None
    assert (
        browsing_tool.domain_refusal(["wikivoyage.org"], ["en.wikivoyage.org"])
        == "browse_domain_not_granted"
    )
    assert (
        browsing_tool.domain_refusal(["notwikivoyage.org"], ["wikivoyage.org"])
        == "browse_domain_not_granted"
    )


def test_without_yolo_the_experts_list_is_not_consulted() -> None:
    """Y3 applies under YOLO only: a call that waits for approval goes on to the executor."""
    connection = yolo(False)
    with pytest.raises(AssertionError, match="the executor was touched"):
        browse(connection)
    assert not any("browse_domains" in query for query, _ in connection.statements)


def test_the_tool_row_records_typing_only_for_a_yolo_call() -> None:
    tool = browsing_tool.browse_tool(None, qualified=lambda: True)
    assert tool.public_context is not None
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 1})
    shown = tool.public_context

    async def typing(on: bool) -> Mapping[str, Any]:
        return await shown(ToolContext(yolo(on), scope, None))

    on, off = asyncio.run(typing(True)), asyncio.run(typing(False))
    assert (dict(on), dict(off)) == ({"typing": "on"}, {})


def test_a_yolo_call_is_released_without_any_approval_request() -> None:
    tool = browsing_tool.browse_tool(None, qualified=lambda: True)
    connection = yolo(True)
    parsed = BrowseGoalInput.model_validate(ARGS)
    call = type("Call", (), {"tool": tool, "parsed": parsed, "operation_id": None})()
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 1})
    released = asyncio.run(hold_for_approval(connection, scope, call))
    assert released == Released()
    assert all("approval" not in query for query, _ in connection.statements)


def test_a_consequential_write_never_takes_a_waiver() -> None:
    async def always(_: ToolContext) -> bool:
        return True

    policy = ApprovalPolicy(waived=always)
    write = OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE
    assert not policy.waivable(write)
    assert policy.label(write) == "always"
    assert ApprovalPolicy(always=True, waived=always).label(OperationClass.ARBITRARY_EXECUTION) == (
        "unless_yolo"
    )


def test_an_experts_browse_domains_are_checked_saved_and_shown() -> None:
    config = ExpertConfig.model_validate({"browse_domains": ["en.wikivoyage.org"]})
    record = expert_record(config)
    assert record.browse_domains == ("en.wikivoyage.org",)
    assert expert_view_config(record).browse_domains == ["en.wikivoyage.org"]
    with pytest.raises(ValidationError):
        ExpertConfig.model_validate({"browse_domains": ["a.com", "a.com"]})
    with pytest.raises(ValidationError):
        ExpertConfig.model_validate({"browse_domains": ["https://a.com/"]})
    with pytest.raises(ValidationError):
        ExpertConfig.model_validate({"browse_domains": [f"d{i}.com" for i in range(11)]})


def test_a_version_saved_before_the_list_existed_reads_as_none() -> None:
    assert read_expert_config({"purpose": "Older", "tools": ["browse_goal"]}).browse_domains == ()


def test_the_notice_is_pending_only_for_the_owner_while_yolo_is_on_and_unseen() -> None:
    unseen = BrowsingSetting(yolo=True, version=0, notice_seen=False)
    assert _view(unseen, owner=True).notice_pending
    assert not _view(unseen, owner=False).notice_pending
    assert not _view(BrowsingSetting(True, 1, True), owner=True).notice_pending
    assert not _view(BrowsingSetting(False, 1, False), owner=True).notice_pending
    assert _view(unseen, owner=False).viewer_can_change is False


def test_the_guide_says_when_approval_applies_and_where_a_yolo_browse_may_go() -> None:
    guide = TOOL_GUIDES["browse_goal"].why
    assert "while YOLO is off" in guide
    assert "Expert's browse domains" in guide
    assert "never to edit or post" in guide


def test_only_the_owner_changes_the_setting_or_marks_the_notice(api_client: ApiClient) -> None:
    refused = {"code": "owner_required", "message": "Only the workspace owner can change this."}
    change = api_client.http.put(
        "/v1/settings/browsing",
        headers=api_client.headers(MEMBER),
        json={"yolo": False, "expected_version": 0},
    )
    notice = api_client.http.post(
        "/v1/settings/browsing/notice", headers=api_client.headers(MEMBER)
    )
    assert (change.status_code, change.json()) == (403, refused)
    assert (notice.status_code, notice.json()) == (403, refused)
    assert "connect" not in api_client.log


def test_a_member_reads_the_setting_on_by_default_and_cannot_change_it(
    api_client: ApiClient,
) -> None:
    reply = api_client.http.get("/v1/settings/browsing", headers=api_client.headers(MEMBER))
    assert reply.status_code == 200
    assert reply.json() == {
        "schema_version": 1,
        "yolo": True,
        "version": 0,
        "notice_pending": False,
        "viewer_can_change": False,
    }
