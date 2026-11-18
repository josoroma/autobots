"""What a qualification of the browser executor binds, offline: US-14.13, PRD-Tool-Catalog BX-05.

The executor reports qualified only from a passing live report at today's fingerprint, and only
while both images it starts carry that fingerprint's digest in their label (Decision 0018 B8,
refactor plan R-57, SQLI-02). Label reads parse fake `docker image inspect` output; nothing calls
Docker.
"""

import ast
import json
import os
import re
import shutil
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path

import pytest

from autobots.adapters import browser_qualification
from autobots.adapters.browser_qualification import (
    FINGERPRINT_LABEL,
    FINGERPRINTED,
    IMAGE_CHECK_SECONDS,
    IMAGES,
    INSPECT_LABELS,
    REQUIRED_CASES,
    ImageCheck,
    executor_qualified,
    fingerprint_digest,
    image_labels,
    images_fingerprint,
    parse_labels,
)

ROOT = Path(__file__).resolve().parents[3]
SOURCE = "services/agent/src"
ADAPTERS = f"{SOURCE}/autobots/adapters"
TAGS = tuple(image.tag for image in IMAGES)
TODAY = fingerprint_digest(images_fingerprint(ROOT))
Reader = Callable[[tuple[str, ...]], Mapping[str, str | None]]


def inspected(*labels: str | None) -> str:
    """What `docker image inspect --format '{{json .Config.Labels}}'` prints for these images."""
    return "".join(
        json.dumps(None if label is None else {FINGERPRINT_LABEL: label, "maintainer": "x"}) + "\n"
        for label in labels
    )


def labelled(*labels: str | None) -> Reader:
    def read(tags: tuple[str, ...]) -> Mapping[str, str | None]:
        return parse_labels(inspected(*labels), tags)

    return read


def report(tmp_path: Path, **changes: object) -> Path:
    data: dict[str, object] = {
        "status": "passed",
        "executor_fingerprint": images_fingerprint(ROOT),
        "cases": [{"id": case, "status": "passed"} for case in REQUIRED_CASES],
    }
    data.update(changes)
    path = tmp_path / "qualification.json"
    path.write_text(json.dumps(data))
    return path


def _type_only(node: ast.AST) -> bool:
    """An `if TYPE_CHECKING:` block, which never runs."""
    test = node.test if isinstance(node, ast.If) else None
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _runtime_imports(node: ast.AST) -> Iterator[ast.Import | ast.ImportFrom]:
    """Every import that can run, function-level ones included, outside type-only blocks."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.If) and _type_only(child):
            for branch in child.orelse:
                yield from _runtime_imports(ast.Module(body=[branch], type_ignores=[]))
            continue
        if isinstance(child, ast.Import | ast.ImportFrom):
            yield child
        yield from _runtime_imports(child)


def _module_path(module: str) -> str:
    return f"{SOURCE}/{module.replace('.', '/')}.py"


def autobots_imports(source: str) -> set[str]:
    """The service modules a module runs, from any layer, as repository paths. A name imported
    from a package, such as `from autobots.adapters import browser_cdp`, is read as its module."""
    found = set()
    for node in _runtime_imports(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {_module_path(a.name) for a in node.names if a.name.startswith("autobots.")}
        elif node.module is None or node.module.split(".")[0] != "autobots":
            continue
        elif (ROOT / SOURCE / node.module.replace(".", "/")).is_dir():
            found |= {_module_path(f"{node.module}.{alias.name}") for alias in node.names}
        else:
            found.add(_module_path(node.module))
    return found


def test_every_module_split_from_the_executor_is_fingerprinted() -> None:
    modules = ("browser_executor", "browser_cdp", "browser_qualification", "egress_proxy")
    assert {f"{ADAPTERS}/{module}.py" for module in modules} <= set(FINGERPRINTED)
    assert f"{SOURCE}/autobots/application/browser_leases.py" in FINGERPRINTED
    assert sorted(images_fingerprint(ROOT)) == sorted(FINGERPRINTED)
    assert len(set(FINGERPRINTED)) == len(FINGERPRINTED)


def test_a_fingerprinted_module_runs_only_fingerprinted_modules() -> None:
    """Executor code moved into another module, or a check that ends a session read from the
    application layer, would otherwise leave the binding. A type-only import runs nothing."""
    for name in FINGERPRINTED:
        if name.endswith(".py"):
            assert autobots_imports((ROOT / name).read_text()) <= set(FINGERPRINTED), name


@pytest.mark.parametrize(
    "line",
    [
        "from autobots.application.tool_gateway import ownership_refusal",
        "from autobots.application import worker_leases",
        "import autobots.application.worker_leases",
        "from autobots.adapters import tool_registry",
        "from autobots.domain.runs import RunStatus",
        "def alive():\n    from autobots.application.worker_leases import hold_lease",
        "if TYPE_CHECKING:\n    pass\nelse:\n    from autobots.application.sql import one",
    ],
)
def test_the_binding_sees_a_runtime_import_from_any_layer(line: str) -> None:
    assert not autobots_imports(line) <= set(FINGERPRINTED)


def test_a_type_only_import_runs_nothing() -> None:
    source = "if TYPE_CHECKING:\n    from autobots.application.sql import SqlConnection\n"
    assert autobots_imports(source) == set()
    assert autobots_imports("from autobots.application import browser_leases, sql") == {
        f"{SOURCE}/autobots/application/browser_leases.py",
        f"{SOURCE}/autobots/application/sql.py",
    }


def test_each_image_is_built_only_from_fingerprinted_files() -> None:
    for image in IMAGES:
        lines = (ROOT / image.dockerfile).read_text().splitlines()
        copied = [line.split()[1] for line in lines if line.startswith("COPY ")]
        ignore = (ROOT / image.ignore_file).read_text().splitlines()
        kept = [line for line in ignore if line and not line.startswith("#")]
        assert copied and kept == ["*", *(f"!{source}" for source in copied)], image.tag
        inputs = (image.dockerfile, image.ignore_file, *(f"{image.context}/{s}" for s in copied))
        assert set(inputs) <= set(FINGERPRINTED), image.tag


def test_an_edit_to_any_fingerprinted_file_changes_the_label(tmp_path: Path) -> None:
    for name in FINGERPRINTED:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, tmp_path / name)
    assert fingerprint_digest(images_fingerprint(tmp_path)) == TODAY
    for name in FINGERPRINTED:
        source = tmp_path / name
        original = source.read_bytes()
        source.write_bytes(original + b"\n")
        assert fingerprint_digest(images_fingerprint(tmp_path)) != TODAY, name
        source.write_bytes(original)
    assert fingerprint_digest(images_fingerprint(tmp_path)) == TODAY


def test_the_label_is_one_digest_of_the_whole_fingerprint() -> None:
    fingerprint = images_fingerprint(ROOT)
    assert re.fullmatch("[0-9a-f]{64}", TODAY)
    assert fingerprint_digest(dict(reversed(fingerprint.items()))) == TODAY
    assert fingerprint_digest({**fingerprint, FINGERPRINTED[0]: "0" * 64}) != TODAY


def test_qualified_only_from_a_passing_report_at_todays_fingerprint(tmp_path: Path) -> None:
    current = labelled(TODAY, TODAY)
    assert executor_qualified(ROOT, report(tmp_path), current)
    assert not executor_qualified(ROOT, tmp_path / "missing.json", current)
    assert not executor_qualified(ROOT, report(tmp_path, status="failed"), current)
    missing_one = [{"id": case, "status": "passed"} for case in REQUIRED_CASES[1:]]
    assert not executor_qualified(ROOT, report(tmp_path, cases=missing_one), current)
    one_failed = [{"id": REQUIRED_CASES[0], "status": "failed"}, *missing_one]
    assert not executor_qualified(ROOT, report(tmp_path, cases=one_failed), current)
    assert not executor_qualified(ROOT, report(tmp_path, executor_fingerprint={"x": "y"}), current)
    (tmp_path / "list.json").write_text("[]")
    assert not executor_qualified(ROOT, tmp_path / "list.json", current)


@pytest.mark.parametrize(
    ("browser", "proxy"),
    [("0" * 64, TODAY), (TODAY, "0" * 64), (None, TODAY), (TODAY, None), (None, None)],
)
def test_qualified_only_while_both_images_carry_todays_fingerprint(
    tmp_path: Path, browser: str | None, proxy: str | None
) -> None:
    assert not executor_qualified(ROOT, report(tmp_path), labelled(browser, proxy))


def test_no_image_is_inspected_unless_the_report_passes(tmp_path: Path) -> None:
    asked: list[tuple[str, ...]] = []

    def read(tags: tuple[str, ...]) -> Mapping[str, str | None]:
        asked.append(tags)
        return dict.fromkeys(tags, TODAY)

    for refused in (
        tmp_path / "missing.json",
        report(tmp_path, status="failed"),
        report(tmp_path, executor_fingerprint={"x": "y"}),
    ):
        assert not executor_qualified(ROOT, refused, read)
    assert asked == []
    assert executor_qualified(ROOT, report(tmp_path), read)
    assert asked == [TAGS]


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Inspected:
    """A fake `docker image inspect`: what each call prints, and how often it was asked."""

    def __init__(self, *labels: str | None) -> None:
        self.labels = labels
        self.asked = 0

    def __call__(self, tags: tuple[str, ...]) -> Mapping[str, str | None]:
        self.asked += 1
        return parse_labels(inspected(*self.labels), tags)


@pytest.fixture
def process_check(monkeypatch: pytest.MonkeyPatch) -> tuple[Inspected, Clock]:
    """The process's IMAGE_CHECK, over a fake inspect and a clock the test moves."""
    docker, clock = Inspected(TODAY, TODAY), Clock()
    monkeypatch.setattr(browser_qualification, "IMAGE_CHECK", ImageCheck(docker, clock=clock))
    return docker, clock


def test_repeated_reads_inspect_the_images_once_per_window(
    tmp_path: Path, process_check: tuple[Inspected, Clock]
) -> None:
    docker, clock = process_check
    passing = report(tmp_path)
    assert all(executor_qualified(ROOT, passing) for _ in range(50))
    assert docker.asked == 1
    clock.now += IMAGE_CHECK_SECONDS - 0.1
    assert executor_qualified(ROOT, passing) and docker.asked == 1
    clock.now += 0.1
    assert executor_qualified(ROOT, passing) and docker.asked == 2


def test_an_image_rebuilt_with_another_label_reads_unqualified_by_the_next_window(
    tmp_path: Path, process_check: tuple[Inspected, Clock]
) -> None:
    docker, clock = process_check
    passing = report(tmp_path)
    assert executor_qualified(ROOT, passing)
    docker.labels = (TODAY, "0" * 64)
    clock.now += IMAGE_CHECK_SECONDS
    assert not executor_qualified(ROOT, passing)
    # A mismatch is reused like a match, until the window ends.
    docker.labels = (TODAY, TODAY)
    assert not executor_qualified(ROOT, passing) and docker.asked == 2
    clock.now += IMAGE_CHECK_SECONDS
    assert executor_qualified(ROOT, passing) and docker.asked == 3


def test_an_unanswered_inspect_reads_unqualified_and_is_not_repeated_on_every_read(
    tmp_path: Path, process_check: tuple[Inspected, Clock]
) -> None:
    docker, _clock = process_check
    docker.labels = ()
    passing = report(tmp_path)
    assert not any(executor_qualified(ROOT, passing) for _ in range(10))
    assert docker.asked == 1


def test_changed_sources_turn_browsing_off_at_once_and_a_new_digest_is_inspected_afresh(
    tmp_path: Path, process_check: tuple[Inspected, Clock]
) -> None:
    docker, _clock = process_check
    root = tmp_path / "root"
    for name in FINGERPRINTED:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, root / name)
    passing = report(tmp_path)
    assert executor_qualified(root, passing) and docker.asked == 1
    edited = root / FINGERPRINTED[-1]
    edited.write_bytes(edited.read_bytes() + b"\n")
    # The report no longer binds these sources, so nothing asks Docker.
    assert not executor_qualified(root, passing) and docker.asked == 1
    # Requalified and rebuilt at the new digest: inspected now, not when the window ends.
    fingerprint = images_fingerprint(root)
    requalified = tmp_path / "requalified.json"
    requalified.write_text(
        json.dumps({**json.loads(passing.read_text()), "executor_fingerprint": fingerprint})
    )
    docker.labels = (fingerprint_digest(fingerprint),) * 2
    assert executor_qualified(root, requalified) and docker.asked == 2


def test_threads_asking_together_share_one_inspect(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()
    calls: list[tuple[str, ...]] = []

    def slow(tags: tuple[str, ...]) -> Mapping[str, str | None]:
        calls.append(tags)
        started.set()
        release.wait(5)
        return dict.fromkeys(tags, TODAY)

    check = ImageCheck(slow)
    fingerprint = images_fingerprint(ROOT)
    found: list[bool] = []
    workers = [
        threading.Thread(target=lambda: found.append(check.matches(fingerprint))) for _ in range(4)
    ]
    for worker in workers:
        worker.start()
    assert started.wait(5)
    time.sleep(0.05)
    release.set()
    for worker in workers:
        worker.join(5)
    assert found == [True] * 4 and calls == [TAGS]


def test_a_report_whose_sources_are_missing_is_not_qualified(tmp_path: Path) -> None:
    assert not executor_qualified(tmp_path, report(tmp_path), labelled(TODAY, TODAY))


def test_labels_are_read_from_inspect_output_in_the_order_named() -> None:
    assert parse_labels(inspected("abc", None), ("a", "b")) == {"a": "abc", "b": None}
    # Docker prints nothing for an image it can't find, so a short answer names no label.
    assert parse_labels(inspected("abc"), ("a", "b")) == {"a": None, "b": None}
    assert parse_labels("not json\n{}\n", ("a", "b")) == {"a": None, "b": None}
    assert parse_labels(json.dumps({FINGERPRINT_LABEL: 5}) + "\n", ("a",)) == {"a": None}


def fake_docker(folder: Path, output: str, code: int = 0) -> Path:
    """A `docker` that records its arguments and whether a credential reached it, then answers."""
    (folder / "answer").write_text(output)
    script = folder / "docker"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$@\" > '{folder}/argv'\n"
        f"printf '%s' \"${{OPENROUTER_API_KEY-unset}}\" > '{folder}/key'\n"
        f"/bin/cat '{folder}/answer'\n"
        f"exit {code}\n"
    )
    script.chmod(0o755)
    return script


def test_labels_come_from_one_read_only_inspect_given_only_dockers_names(tmp_path: Path) -> None:
    docker = fake_docker(tmp_path, inspected("abc", None))
    environ = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "OPENROUTER_API_KEY": "sk-or-fake"}
    found = image_labels(("a:local", "b:local"), docker=str(docker), environ=environ)
    assert found == {"a:local": "abc", "b:local": None}
    argv = (tmp_path / "argv").read_text().splitlines()
    assert argv == [*INSPECT_LABELS, "a:local", "b:local"]
    assert argv[:2] == ["image", "inspect"]
    assert (tmp_path / "key").read_text() == "unset"


def test_labels_read_as_missing_when_docker_cant_answer(tmp_path: Path) -> None:
    failing = fake_docker(tmp_path, inspected("abc"), code=1)
    assert image_labels(("a",), docker=str(failing), environ={}) == {"a": None}
    assert image_labels(("a",), docker=str(tmp_path / "absent"), environ={}) == {"a": None}
