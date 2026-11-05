"""Corrected: the approved profile goes through the fake transport."""

from fake_openrouter import DEEPSEEK_WIRE_ID, FakeOpenRouter


def test_approved_profile_uses_the_fake() -> None:
    fake = FakeOpenRouter()
    assert fake.chat_model(DEEPSEEK_WIRE_ID).invoke("hello").content == "fake reply"
    assert fake.models() == [DEEPSEEK_WIRE_ID]
