"""Baseline model tests use a fake transport, and real inference is refused."""

import os

import openrouter
import pytest
from langchain_openrouter import ChatOpenRouter

from conftest import SocketBlockedError
from fake_openrouter import ARRANGED_KEY, DEEPSEEK_WIRE_ID, TERRA_WIRE_ID, FakeOpenRouter


def in_chain(error: BaseException | None, kind: type[BaseException]) -> bool:
    while error is not None:
        if isinstance(error, kind):
            return True
        error = error.__cause__ or error.__context__
    return False


@pytest.mark.parametrize("wire_id", [DEEPSEEK_WIRE_ID, TERRA_WIRE_ID])
def test_each_approved_profile_round_trips_through_the_fake(wire_id: str) -> None:
    fake = FakeOpenRouter()
    assert fake.chat_model(wire_id).invoke("hello").content == "fake reply"
    assert fake.models() == [wire_id]


def test_an_unapproved_model_is_refused() -> None:
    fake = FakeOpenRouter()
    with pytest.raises(openrouter.errors.OpenRouterError):
        fake.chat_model("openai/gpt-unapproved").invoke("hello")


def test_a_fallback_array_is_refused() -> None:
    fake = FakeOpenRouter()
    with pytest.raises(openrouter.errors.OpenRouterError):
        fake.chat_model(DEEPSEEK_WIRE_ID).invoke("hello", models=[DEEPSEEK_WIRE_ID, TERRA_WIRE_ID])


def test_a_missing_key_is_refused_before_any_request() -> None:
    assert "OPENROUTER_API_KEY" not in os.environ
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        ChatOpenRouter(model=DEEPSEEK_WIRE_ID, max_retries=0)


def test_no_inherited_provider_key_reaches_a_test() -> None:
    assert "OPENROUTER_API_KEY" not in os.environ


def test_external_inference_is_refused_even_with_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", ARRANGED_KEY)
    with pytest.raises(BaseException) as caught:
        ChatOpenRouter(model=DEEPSEEK_WIRE_ID, max_retries=0).invoke("hello")
    assert in_chain(caught.value, SocketBlockedError)
