"""R-05, STD-01: service layers import inward only, function-level imports included.

Pairs outside ALLOWED are today's exceptions, counted exactly. A refactor that removes one lowers
its count here; a new one fails until someone decides to raise it (Decision 0027 D4).
"""

import ast
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src/autobots"
ALLOWED = {
    "domain": set(),
    "persistence": {"domain"},
    "contracts": {"domain", "persistence"},
    "application": {"domain", "persistence", "contracts"},
    "adapters": {"domain", "persistence", "contracts", "application"},
    "api": {"domain", "persistence", "contracts", "application", "adapters"},
    "operations": {"domain", "persistence", "contracts", "application", "adapters"},
}
BASELINE = {
    ("application", "adapters"): 21,
    ("application", "operations"): 5,
    ("adapters", "operations"): 2,
    ("api", "operations"): 2,
    ("operations", "api"): 1,
}


def crossings(source: Path) -> Counter[tuple[str, str]]:
    """Import statements from one layer into a layer it may not use, anywhere in a module."""
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(source.rglob("*.py")):
        parts = path.relative_to(source).parts
        if len(parts) < 2 or parts[0] not in ALLOWED:
            continue
        layer = parts[0]
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module == "autobots":
                # `from autobots import application` names its layers one by one.
                names = [f"autobots.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                names = []
            for name in names:
                pieces = name.split(".")
                if pieces[0] != "autobots" or len(pieces) < 2:
                    continue
                target = pieces[1]
                if target in ALLOWED and target != layer and target not in ALLOWED[layer]:
                    found[(layer, target)] += 1
    return found


def test_layers_import_inward_apart_from_counted_exceptions() -> None:
    assert dict(crossings(SOURCE)) == BASELINE


def test_a_planted_violation_is_caught(tmp_path: Path) -> None:
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain/rules.py").write_text(
        "def later() -> None:\n    from autobots.api import app\n"
    )
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts/views.py").write_text("import autobots.persistence.rows\n")
    (tmp_path / "domain/more.py").write_text("from autobots import application\n")
    assert dict(crossings(tmp_path)) == {("domain", "api"): 1, ("domain", "application"): 1}
