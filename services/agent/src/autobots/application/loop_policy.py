"""The goal loop's model-call policy that needs neither a framework nor the database: its stop, what
a request reserves, and what a log may keep about an uncertain call (refactor plan R-62, PADP-08 and
PADP-09). application/loop_admission.py applies it, and adapters/loop_middleware.py is the LangChain
side.
"""

from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.domain.models import RESERVED_PROMPT_TOKENS, ModelRoute

REPAIR_NOTE = "Your last reply was cut off, so none of it was used. Reply again, more briefly."


class LoopStopped(Exception):
    """The loop stops here, with `code` as the pass's stop code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class UnadmittedModelCall(Exception):
    """The SDK tried to call the model on its own, such as to summarize."""


class DispatchStopped(ProviderFailure):
    """An attempt the loop stopped itself: its guard refused it, a run limit was reached, or the run
    was interrupted while the call was out. The ledger settles it by `failure` like any other, and
    the loop stops with `code` rather than the failure class (PADP-08)."""

    def __init__(self, failure: FailureClass, code: str, *, reason: str | None = None) -> None:
        super().__init__(failure, reason=reason)
        self.code = code


def reservation_for(route: ModelRoute, prompt_bytes: int) -> int:
    """The route's worst case, plus whatever this request has beyond the tokens that assumes."""
    excess = max(prompt_bytes - RESERVED_PROMPT_TOKENS, 0)
    return (
        route.worst_case_micro_usd
        + (excess * route.input_per_million_micro_usd + 999_999) // 1_000_000
    )


def past_known_price(route: ModelRoute, prompt_bytes: int) -> bool:
    """A token takes at least a byte, so a request this short can't reach the tier."""
    return route.tier_from_tokens is not None and prompt_bytes >= route.tier_from_tokens


def _type_name(error: BaseException) -> str:
    return f"{type(error).__module__}.{type(error).__qualname__}"


def uncertain_call_fields(error: BaseException) -> dict[str, object]:
    """Types and a status only. A message can carry a provider's reply or a connection string."""
    fields: dict[str, object] = {"error_type": _type_name(error)}
    cause = error.__cause__ or error.__context__
    if cause is not None:
        fields["cause_type"] = _type_name(cause)
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        fields["status"] = status
    return fields
