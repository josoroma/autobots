"""Fault: a model test forgot the fake and uses the real transport, with a key in the environment."""

import pytest
from fake_openrouter import ARRANGED_KEY, DEEPSEEK_WIRE_ID
from langchain_openrouter import ChatOpenRouter


def test_real_transport_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", ARRANGED_KEY)
    assert ChatOpenRouter(model=DEEPSEEK_WIRE_ID, max_retries=0).invoke("hello").content
