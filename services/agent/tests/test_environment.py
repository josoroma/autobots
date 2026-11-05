"""PRD 3.1's import and local serialization gate, with sockets blocked and no model constructed.

This is not qualification of stream, reasoning or tool round trips, or of real routes. Those
belong to US-3.4 and are not claimed here.
"""

import gc
import importlib
import json
from importlib import metadata

import psycopg
import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

SELECTED = {
    "deepagents": ("deepagents", "0.7.32"),
    "langchain": ("langchain", "1.4.8"),
    "langgraph": ("langgraph", "1.2.19"),
    "langchain-openrouter": ("langchain_openrouter", "0.2.9"),
    "openrouter": ("openrouter", "0.11.46"),
    "langgraph-checkpoint-postgres": ("langgraph.checkpoint.postgres", "3.2.0"),
    "fastapi": ("fastapi", "0.162.0"),
    "psycopg": ("psycopg", "3.3.8"),
    "langchain-mcp-adapters": ("langchain_mcp_adapters", "0.3.2"),
}


class Note(BaseModel):
    text: str
    count: int


def serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=[("test_environment", "Note")])


@pytest.mark.parametrize(
    ("distribution", "module", "version"),
    [(distribution, *pin) for distribution, pin in SELECTED.items()],
)
def test_selected_package_imports_at_its_pin(distribution: str, module: str, version: str) -> None:
    importlib.import_module(module)
    assert metadata.version(distribution) == version


def test_nine_packages_are_selected() -> None:
    assert len(SELECTED) == 9


@pytest.mark.parametrize(
    "message",
    [HumanMessage(content="ping"), AIMessage(content="pong", id="a1")],
)
def test_message_round_trips_through_serializer_and_json(message: HumanMessage | AIMessage) -> None:
    codec = serializer()
    assert codec.loads_typed(codec.dumps_typed(message)) == message
    assert type(message).model_validate_json(message.model_dump_json()) == message


def test_pydantic_model_round_trips_through_serializer_and_json() -> None:
    note = Note(text="kept", count=2)
    codec = serializer()
    assert codec.loads_typed(codec.dumps_typed(note)) == note
    assert Note.model_validate(json.loads(note.model_dump_json())) == note


def test_psycopg_uses_binary_implementation_without_connecting() -> None:
    assert psycopg.pq.__impl__ == "binary"


def test_no_model_is_constructed() -> None:
    assert [item for item in gc.get_objects() if isinstance(item, BaseChatModel)] == []
