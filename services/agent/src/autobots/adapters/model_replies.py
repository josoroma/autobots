"""What one provider reply or failure means for the ledger, read from the reply alone.

`LoopMiddleware` settles each admitted call with these, and tests read them directly (PTST-01).
"""

import math

import httpx
from langchain_core.messages import AIMessage

from autobots.adapters.models.catalog import micro_usd
from autobots.application.model_attempts import FailureClass

INCOMPLETE_FINISHES = frozenset({"length", "error", "content_filter"})


def retry_after(error: Exception) -> float | None:
    """The provider's requested wait in seconds, or None where it gave no usable one."""
    # The SDK's errors carry `headers`. Other clients' errors carry them on `response`.
    headers = (
        getattr(error, "headers", None)
        or getattr(getattr(error, "response", None), "headers", None)
        or {}
    )
    try:
        seconds = float(str(headers.get("retry-after")))
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def charged(message: AIMessage) -> int | None:
    """Rounded up, as the paid trials round the same reply. Unreadable is unreported (PADP-12)."""
    return micro_usd(message.response_metadata.get("cost"))


def finished(message: AIMessage) -> bool:
    """A reply cut off or stopped by the provider is never run, whatever it appears to hold."""
    return message.response_metadata.get("finish_reason") not in INCOMPLETE_FINISHES


def failure_without_status(error: Exception) -> FailureClass:
    """A connection that never opened carried nothing. Anything else may have been accepted."""
    if isinstance(error, httpx.ConnectError | httpx.ConnectTimeout):
        return FailureClass.NETWORK_BEFORE_ACCEPTANCE
    return FailureClass.UNCERTAIN_ACCEPTANCE
