"""SQL's one terminal-state predicate names exactly the domain's TERMINAL (R-56, SQLI-17).

app_private.run_is_terminal, from migration 58, is what new migrations call instead of restating
the list. The db profile also evaluates it over the runs status CHECK's vocabulary.
"""

import re
from pathlib import Path

from autobots.domain.runs import TERMINAL, RunStatus

MIGRATION = (
    Path(__file__).resolve().parents[3] / "supabase/migrations/20261115000058_run_is_terminal.sql"
)


def test_the_sql_predicate_lists_exactly_the_terminal_states() -> None:
    body = re.search(r"\$\$ select status in \(([^)]*)\) \$\$", MIGRATION.read_text())
    assert body is not None
    listed = {item.strip().strip("'") for item in body.group(1).split(",")}
    assert listed == {status.value for status in TERMINAL}
    assert listed <= {status.value for status in RunStatus}
