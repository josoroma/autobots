"""R-05, STD-01: service layers import inward only, function-level imports included.

Pairs outside ALLOWED are today's exceptions, counted exactly. A refactor that removes one lowers
its count here; a new one fails until someone decides to raise it (Decision 0027 D4).
"""

import ast
from collections import Counter
from collections.abc import Iterator
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
    ("application", "adapters"): 12,
    # cronjob_tool's lazy import of the worker's credential check from operations/composition.py.
    ("application", "operations"): 1,
    # api/main.py, the API's process entry, composes from operations/composition.py (Decision 0029
    # F6 puts process configuration in operations/).
    ("api", "operations"): 1,
}
# Modules beside the layers, and the layers each may import. Every layer may import them, so they
# stay leaves (R-64, POPS-03).
LEAVES = {"logs.py": {"domain"}}


def imported_layers(tree: ast.AST) -> Iterator[str]:
    """The `autobots` package each import statement names, once per statement and name."""
    for node in ast.walk(tree):
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
            if pieces[0] == "autobots" and len(pieces) >= 2:
                yield pieces[1]


def crossings(source: Path) -> Counter[tuple[str, str]]:
    """Import statements from one layer into a layer it may not use, anywhere in a module."""
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(source.rglob("*.py")):
        parts = path.relative_to(source).parts
        if len(parts) < 2 or parts[0] not in ALLOWED:
            continue
        layer = parts[0]
        for target in imported_layers(ast.parse(path.read_text())):
            if target in ALLOWED and target != layer and target not in ALLOWED[layer]:
                found[(layer, target)] += 1
    return found


def leaf_imports(source: Path) -> dict[str, set[str]]:
    """What each module beside the layers imports from `autobots`."""
    return {
        path.name: set(imported_layers(ast.parse(path.read_text())))
        for path in sorted(source.glob("*.py"))
        if path.name != "__init__.py"
    }


def test_layers_import_inward_apart_from_counted_exceptions() -> None:
    assert dict(crossings(SOURCE)) == BASELINE


def test_the_modules_beside_the_layers_are_leaves() -> None:
    found = leaf_imports(SOURCE)
    assert set(found) == set(LEAVES)
    assert {name: layers - LEAVES[name] for name, layers in found.items()} == {
        name: set() for name in LEAVES
    }


def test_a_planted_violation_is_caught(tmp_path: Path) -> None:
    (tmp_path / "domain").mkdir()
    (tmp_path / "domain/rules.py").write_text(
        "def later() -> None:\n    from autobots.api import app\n"
    )
    (tmp_path / "contracts").mkdir()
    (tmp_path / "contracts/views.py").write_text("import autobots.persistence.rows\n")
    (tmp_path / "domain/more.py").write_text("from autobots import application\n")
    assert dict(crossings(tmp_path)) == {("domain", "api"): 1, ("domain", "application"): 1}


def test_a_leaf_that_imports_a_layer_is_caught(tmp_path: Path) -> None:
    (tmp_path / "logs.py").write_text(
        "from autobots.domain import secret_patterns\nfrom autobots.operations import worker\n"
    )
    assert leaf_imports(tmp_path) == {"logs.py": {"domain", "operations"}}
