"""Cutting a conversation without separating a tool call from its results."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from autobots.application.compaction import pairing_is_valid, safe_split


def conversation() -> list[object]:
    return [
        HumanMessage("goal"),
        AIMessage("", tool_calls=[{"name": "a", "args": {}, "id": "1", "type": "tool_call"}]),
        ToolMessage("r", tool_call_id="1"),
        AIMessage(
            "",
            tool_calls=[
                {"name": "a", "args": {}, "id": "2", "type": "tool_call"},
                {"name": "b", "args": {}, "id": "3", "type": "tool_call"},
            ],
        ),
        ToolMessage("r", tool_call_id="2"),
        ToolMessage("r", tool_call_id="3"),
        AIMessage("done"),
    ]


def test_a_cut_never_starts_on_a_tool_result() -> None:
    messages = conversation()
    for keep in range(1, len(messages)):
        cut = safe_split(messages, keep)
        assert pairing_is_valid(messages[cut:]), keep


def test_the_conversation_is_valid_and_a_bad_cut_is_not() -> None:
    messages = conversation()
    assert pairing_is_valid(messages)
    assert not pairing_is_valid(messages[2:])
    assert not pairing_is_valid(messages[5:])


def test_a_call_missing_its_result_is_invalid_unless_nothing_follows() -> None:
    messages = conversation()
    assert not pairing_is_valid([messages[1], messages[6]])
    assert pairing_is_valid([messages[1]])


def test_keeping_everything_cuts_nothing() -> None:
    assert safe_split(conversation(), 100) == 0
