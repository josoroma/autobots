"""One runner for a qualifier's scenarios, each a function of the qualifier's context and its cases (SCRP-05).

The order is the tuple's, and stated there, because a scenario may use what an earlier one left. A scenario
that raises anything but Refused or Unavailable records one failed case, and each later one a failed case
observed as not run, so a crash can't pass and no scenario goes missing from the report (PRD-Development-Harness
DH-09.2). A case record's status is passed or failed (qualification/records.py CaseStatus), which has no not_run.
Refused and Unavailable keep their exit codes, 1 and 2 (AGENTS.md Commands).
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from qualification.errors import Refused, Unavailable
from qualification.records import Cases


def scenario_name(scenario: Callable[..., object]) -> str:
    return getattr(scenario, '__name__', 'a scenario').replace('_', ' ')


def run_scenarios[Context](context: Context, cases: Cases, scenarios: Sequence[Callable[[Context, Cases], None]]) -> None:
    """Run each scenario in order with the shared context."""
    for index, scenario in enumerate(scenarios):
        try:
            scenario(context, cases)
        except (Refused, Unavailable):
            raise
        except Exception as error:  # noqa: BLE001 - recorded as a failed case, so a crash can't pass and the rest stay visible
            name = scenario_name(scenario)
            cases.check(f'{name} ran', 'no exception', f'{type(error).__name__}: {error}', False)
            for later in scenarios[index + 1:]:
                cases.check(f'{scenario_name(later)} ran', 'run after the scenarios before it', f'not run, because {name} raised', False)
            return
