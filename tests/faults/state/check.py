"""Check a fixture's transitions, reducer and public events. Standard library only.

A fixture checker for H1. The product's run state machine is implemented by later stories.
"""

import json
import sys
from pathlib import Path

TERMINAL = {"succeeded", "failed", "cancelled"}
PERMITTED = {
    "queued": {"running", "paused"},
    "running": {"waiting_input", "waiting_approval", "paused", "verifying", "failed"},
    "waiting_input": {"queued", "paused"},
    "waiting_approval": {"queued", "paused"},
    "paused": {"queued"},
    "verifying": {"succeeded", "running", "failed", "paused"},
    "cancelling": {"cancelled"},
}
PRIVATE_KEYS = {"api_key", "authorization", "reasoning", "credential", "provider_key", "checkpoint"}


def transition_errors(states):
    errors = []
    for current, following in zip(states, states[1:], strict=False):
        if current in TERMINAL or current not in PERMITTED:
            errors.append(f"INVALID TRANSITION: {current} to {following}, {current} is terminal or unknown")
        elif following not in PERMITTED[current] and following not in {"cancelling", "cancelled"}:
            errors.append(f"INVALID TRANSITION: {current} to {following}")
    return errors


def reduce_events(events):
    """Apply by sequence, ignoring a replayed one, so reconnect and replay give the same result."""
    latest = {}
    for event in events:
        latest.setdefault(event["sequence"], event["value"])
    return [latest[sequence] for sequence in sorted(latest)]


def private_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in PRIVATE_KEYS:
                yield key
            yield from private_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from private_keys(item)


def main():
    fixture = json.loads(Path(sys.argv[1]).read_text())
    errors = transition_errors(fixture["states"])
    if reduce_events(fixture["events"]) != fixture["expected_reduced"]:
        errors.append("REDUCER: replayed events did not give the expected state")
    errors.extend(f"PRIVATE DATA: public event holds {key}" for key in private_keys(fixture["public_events"]))
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print("state fixture holds")


main()
