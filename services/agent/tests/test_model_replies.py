"""What a provider's reply or failure means for the ledger, read through the real SDK where its
errors matter. Split from test_worker_inference.py by module (PTST-04)."""

import httpx
import openrouter
import pytest
from langchain_core.messages import AIMessage

from autobots.adapters import model_replies
from autobots.application.model_attempts import FailureClass
from fake_openrouter import invoke, model_over


def test_retry_after_is_read_from_a_real_sdk_error() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        error = {"error": {"code": 429, "message": "arranged"}}
        return httpx.Response(429, json=error, headers={"Retry-After": "60"})

    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        invoke(model_over(handle))
    assert model_replies.retry_after(caught.value) == 60.0


def test_an_unusable_retry_after_is_ignored() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        error = {"error": {"code": 429, "message": "arranged"}}
        return httpx.Response(429, json=error, headers={"Retry-After": "soon"})

    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        invoke(model_over(handle))
    assert model_replies.retry_after(caught.value) is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectError("arranged"), FailureClass.NETWORK_BEFORE_ACCEPTANCE),
        (httpx.ConnectTimeout("arranged"), FailureClass.NETWORK_BEFORE_ACCEPTANCE),
        (httpx.ReadTimeout("arranged"), FailureClass.UNCERTAIN_ACCEPTANCE),
        (httpx.RemoteProtocolError("arranged"), FailureClass.UNCERTAIN_ACCEPTANCE),
        (RuntimeError("arranged"), FailureClass.UNCERTAIN_ACCEPTANCE),
    ],
)
def test_only_a_connection_that_never_opened_counts_as_unsent(
    error: Exception, expected: FailureClass
) -> None:
    assert model_replies.failure_without_status(error) is expected


@pytest.mark.parametrize(
    ("finish", "finished"),
    [
        ("stop", True),
        ("tool_calls", True),
        ("length", False),
        ("error", False),
        ("content_filter", False),
    ],
)
def test_only_a_reply_the_model_finished_can_run(finish: str, finished: bool) -> None:
    assert (
        model_replies.finished(AIMessage(content="", response_metadata={"finish_reason": finish}))
        is finished
    )
