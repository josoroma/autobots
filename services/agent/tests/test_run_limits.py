"""The limits every run gets, set by Decision 0034 L1 to L4 for deep research runs (US-16.6).

How each limit refuses is tested where it's enforced: test_loop_middleware.py for model calls, tool
dispatches and repairs, test_tool_gateway_steps.py and tests/db/checks/tool_use_check.py for
metered calls, and tests/db/checks/assignment_check.py for children and active time."""

import inspect

from autobots.adapters.loop_middleware import LoopMiddleware
from autobots.application.loop_admission import LoopSettings
from autobots.application.run_usage import LIMIT_CODES, RootLimits
from autobots.application.tool_uses import METERED_TOOL_CALLS
from autobots.application.worker_inference import OPTIONS
from autobots.domain.models import (
    CONTEXT_TOKENS,
    MAX_OUTPUT_TOKENS,
    MODEL_CALL_SECONDS,
    RESERVED_PROMPT_TOKENS,
)
from autobots.domain.stops import StopCode


def test_a_model_call_asks_for_4096_output_tokens_and_may_take_300_seconds() -> None:
    """L1 and L4. Context and the prompt reservation are unchanged."""
    assert MAX_OUTPUT_TOKENS == 4_096
    assert OPTIONS["max_tokens"] == MAX_OUTPUT_TOKENS
    assert (CONTEXT_TOKENS, RESERVED_PROMPT_TOKENS) == (8_000, 32_000)
    assert MODEL_CALL_SECONDS == 300.0
    assert LoopSettings().model_call_seconds == MODEL_CALL_SECONDS
    default = inspect.signature(LoopMiddleware).parameters["model_call_seconds"].default
    assert default == MODEL_CALL_SECONDS


def test_a_run_tree_gets_the_raised_limits_and_keeps_the_rest() -> None:
    """L2 and L3, refused with their existing codes."""
    limits = RootLimits()
    assert (limits.model_calls, limits.tool_dispatches, limits.children, limits.active_seconds) == (
        64,
        96,
        8,
        2_700.0,
    )
    assert (
        limits.repairs,
        limits.plan_revisions,
        limits.child_levels,
        limits.outstanding_assignments,
    ) == (1, 2, 2, 2)
    assert METERED_TOOL_CALLS == 40
    assert LIMIT_CODES == {
        "model_calls": StopCode.MODEL_CALLS_LIMIT,
        "tool_dispatches": StopCode.TOOL_DISPATCHES_LIMIT,
        "repairs": StopCode.REPAIRS_LIMIT,
        "plan_revisions": StopCode.PLAN_REVISIONS_LIMIT,
        "children": StopCode.CHILDREN_LIMIT,
    }
