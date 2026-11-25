"""A browse's typed result saved straight to a run file, browse_goal version 4, US-21.1 and Decision
0039. Nothing here starts a container or calls a model. The published transcript is in
tests/db/checks/transcript_check.py.
"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.application import browsing_tool
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.browsing_tool import browse_tool, browse_tools
from autobots.application.tool_definitions import ToolContext, ToolRegistry, ToolScope
from autobots.application.tool_gateway import Call, Refused, resolve
from autobots.application.typed_results import rendered
from autobots.contracts.browsing import (
    BrowseGoalInput,
    BrowseGoalV2Input,
    BrowseGoalV3Input,
    BrowseGoalV4Input,
    BrowseGoalV4Output,
    SaveResult,
)
from autobots.domain.stops import GatewayCode
from autobots.domain.tools import EXPERT_TOOLS
from sql_fakes import Row, RuledConnection

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"time": {"type": "string"}, "text": {"type": "string"}},
                "required": ["time", "text"],
            },
        },
    },
    "required": ["title", "lines"],
}
SAVE = {
    "path": "outputs/notes.md",
    "before": "# {title}\n\nSource: https://a.test/",
    "items": "lines",
    "line": "{time} {text}",
}
ARGS = {
    "task": "Read",
    "start_url": "https://a.test/",
    "allowed_domains": ["a.test"],
    "output_schema": SCHEMA,
    "save": SAVE,
}
# More than one model reply can hold, and past the size a tool's output is offloaded at.
LINES = [{"time": f"{n // 60}:{n % 60:02d}", "text": f"Line {n} as it came."} for n in range(3000)]
LEASED = ("for share", [(1,)])
LOCK = ("pg_advisory_xact_lock", [(None,)])
NEXT = ("coalesce(max(version)", [(1,)])
INSERT: tuple[str, list[Row]] = ("insert into app_private.run_files", [])


def saved(
    result: object,
    *,
    save: dict[str, Any] | None = SAVE,
    stopped: str = "done",
    lease: bool = True,
    use_id: int | None = 41,
) -> tuple[BrowseGoalV4Output, list[tuple[str, Any]]]:
    """Version 4's output for one scripted browse, and the files it wrote."""
    rules = (LEASED if lease else ("for share", []), LOCK, NEXT, INSERT)
    connection = RuledConnection(*rules)
    scope = ToolScope(uuid4(), uuid4(), 3, {"browse_goal": 4}, ("outputs",))
    context = ToolContext(connection, scope, None, None, use_id)
    args = BrowseGoalV4Input.model_validate({**ARGS, "save": save})
    done = BrowseOutcome("Read.", ("https://a.test/",), 2, 3, stopped, result, ())  # type: ignore[arg-type]  # a stop reason literal
    output = asyncio.run(browsing_tool._saved_output(done, args, context))
    return output, [s for s in connection.statements if "insert into" in s[0]]


def test_a_long_result_is_saved_whole_in_order_and_never_returned() -> None:
    output, [(_, written)] = saved({"title": "A talk", "lines": LINES})
    text = written[3]
    head, _, body = text.partition("\n\n0:00 ")
    assert head == "# A talk\n\nSource: https://a.test/"
    assert ("0:00 " + body).splitlines() == [f"{i['time']} {i['text']}" for i in LINES]
    assert len(text) > 48_000
    assert written[1] == "outputs/notes.md" and written[5:] == ("text/markdown", "use:41")
    shown = output.model_dump(exclude_none=True)
    assert "result" not in shown and "not_saved" not in shown
    assert (output.saved_path, output.saved_version, output.saved_items) == (
        "outputs/notes.md",
        1,
        3000,
    )
    assert output.saved_sha256 == written[4] and output.saved_characters == len(text)
    assert len(json.dumps(shown)) < 1000


def test_an_item_stays_one_line_and_braces_that_name_nothing_are_text() -> None:
    save = SaveResult.model_validate(
        {**SAVE, "before": "{title} {}", "line": "[{time}] {text} { }"}
    )
    result = {
        "title": "a\nb",
        "lines": [
            {"time": "0:01", "text": " one\r\n\r\ntwo  three "},
            {"time": "0:02", "text": ""},
        ],
    }
    assert rendered(result, save) == "a b {}\n\n[0:01] one two  three { }\n[0:02]  { }\n"


def test_values_that_arent_text_and_missing_ones() -> None:
    save = SaveResult.model_validate({"path": "outputs/a.md", "items": "lines", "line": "{n}|{m}"})
    result = {"lines": [{"n": 5, "m": True}, {"n": {"a": "é"}}, {"n": None}]}
    assert rendered(result, save) == '5|true\n{"a": "é"}|\n|\n'


def test_text_a_database_refuses_is_written_without_it() -> None:
    save = SaveResult.model_validate({**SAVE, "before": ""})
    result = {"title": "t", "lines": [{"time": "0:00", "text": "a\x00b \ud83d c 🙂"}]}
    assert rendered(result, save) == "0:00 ab ? c 🙂\n"
    as_json = rendered(result, SaveResult.model_validate({"path": "outputs/a.json"}))
    assert "\x00" not in as_json and as_json.encode()


def test_with_no_layout_the_file_is_the_result_as_json() -> None:
    result = {"title": "A talk", "lines": LINES[:2]}
    output, [(_, written)] = saved(result, save={"path": "outputs/notes.json"})
    assert json.loads(written[3]) == result and written[5] == "application/json"
    assert (output.saved_items, output.saved_path) == (None, "outputs/notes.json")


def test_what_isnt_saved_says_why_and_comes_back_as_version_3_does() -> None:
    empty = {"title": "A talk", "lines": []}
    output, written = saved(empty)
    assert (output.not_saved, output.result, written) == ("no_items", empty, [])
    large = {"title": "A talk", "lines": [{"time": "0:00", "text": "x" * 256_000}]}
    output, written = saved(large)
    assert (output.not_saved, output.result, written) == ("too_large", large, [])
    small = {"title": "A talk", "lines": LINES[:2]}
    for arranged in ({"lease": False}, {"use_id": None}):
        output, written = saved(small, **arranged)
        assert (output.not_saved, output.result, written) == ("lease_lost", small, [])


@pytest.mark.parametrize("stopped", ["max_steps", "max_seconds", "refused_action", "bot_check"])
def test_a_call_that_ends_any_other_way_saves_nothing(stopped: str) -> None:
    output, written = saved({"title": "A talk", "lines": LINES[:2]}, stopped=stopped)
    assert (output.stopped, output.not_saved, output.saved_path, written) == (
        stopped,
        None,
        None,
        [],
    )


def test_a_result_that_doesnt_validate_saves_nothing() -> None:
    output, written = saved({"title": "A talk"})
    assert (output.stopped, output.saved_path, written) == ("invalid_action", None, [])


def test_without_save_version_4_returns_what_version_3_does() -> None:
    result = {"title": "A talk", "lines": LINES[:2]}
    output, written = saved(result, save=None)
    assert (output.result, output.not_saved, written) == (result, None, [])


@pytest.mark.parametrize(
    "change",
    [
        {"output_schema": None},
        {"save": {**SAVE, "items": "rows"}},
        {"save": {**SAVE, "items": "title"}},
        {"save": {**SAVE, "line": "{when} {text}"}},
        {"save": {**SAVE, "before": "# {name}"}},
        {"save": {**SAVE, "line": ""}},
        {"save": {"path": "outputs/a.md", "line": "{time}"}},
        {"save": {"path": "outputs/a.json", "before": "# {title}"}},
        {"save": {**SAVE, "path": "inputs/a.md"}},
        {"save": {**SAVE, "path": "notes.md"}},
        {"save": {**SAVE, "extra": 1}},
    ],
)
def test_a_save_the_schema_or_outputs_doesnt_hold_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BrowseGoalV4Input.model_validate({**ARGS, **change})


def registry() -> ToolRegistry:
    built = ToolRegistry()
    for tool in browse_tools(None, qualified=lambda: True):
        built.register(tool)
    return built


def test_a_path_outside_the_grants_is_refused_before_anything_starts() -> None:
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 4}, ("inputs", "outputs/child-1"))
    refused = resolve(registry(), scope, "browse_goal", ARGS)
    assert isinstance(refused, Refused) and refused.code is GatewayCode.RESOURCE_NOT_GRANTED
    inside = {**ARGS, "save": {**SAVE, "path": "outputs/child-1/notes.md"}}
    assert isinstance(resolve(registry(), scope, "browse_goal", inside), Call)
    assert isinstance(resolve(registry(), scope, "browse_goal", {**ARGS, "save": None}), Call)


def test_a_save_the_call_cant_make_is_refused_as_invalid_arguments() -> None:
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 4}, ("outputs",))
    refused = resolve(registry(), scope, "browse_goal", {**ARGS, "output_schema": None})
    assert isinstance(refused, Refused) and refused.code is GatewayCode.INVALID_ARGUMENTS


def test_every_version_stays_registered_and_new_grants_take_version_4() -> None:
    models = [tool.input_model for tool in browse_tools(None, qualified=lambda: True)]
    assert models == [BrowseGoalInput, BrowseGoalV2Input, BrowseGoalV3Input, BrowseGoalV4Input]
    assert EXPERT_TOOLS["browse_goal"] == 4
    with pytest.raises(ValidationError):
        BrowseGoalV3Input.model_validate(ARGS)


def test_the_tool_row_shows_the_path_and_the_count_and_never_the_text() -> None:
    tool = browse_tool(None, qualified=lambda: True, version=4)
    assert {"saved_path", "saved_items"} <= set(tool.public_output_fields)
    assert not {"result", "saved_sha256"} & set(tool.public_output_fields)
    assert not {"save", "output_schema"} & set(tool.public_input_fields)
