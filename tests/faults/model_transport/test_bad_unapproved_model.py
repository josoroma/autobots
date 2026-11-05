"""Fault: a model outside the two approved profiles."""

from fake_openrouter import FakeOpenRouter


def test_unapproved_model() -> None:
    assert FakeOpenRouter().chat_model("openai/gpt-unapproved").invoke("hello").content
