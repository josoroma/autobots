"""US-14.11: the code tools' search over files, and their names, without a database."""

import pytest

from autobots.application.code_tools import CODE_TOOLS, search
from autobots.application.tool_gateway import ToolFailed
from autobots.contracts.code_tools import SearchFilesInput

FILES = {
    "inputs/app.py": "import os\n\ndef main():\n    return os.getcwd()\n",
    "inputs/util.py": "def helper():\n    return 1\n# main is elsewhere\n",
    "outputs/notes.md": "main points\n" + "x" * 900 + " main\n",
}


def run(**arguments: object) -> object:
    return search(FILES, SearchFilesInput.model_validate(arguments))


def test_content_matches_with_context_from_run_files_only() -> None:
    found = run(pattern=r"def \w+", context=1)
    assert [(m.path, m.line_number, m.content) for m in found.matches] == [  # type: ignore[attr-defined]
        ("inputs/app.py", 3, "def main():"),
        ("inputs/util.py", 1, "def helper():"),
    ]
    first = found.matches[0]  # type: ignore[attr-defined]
    assert (first.before, first.after) == ([""], ["    return os.getcwd()"])


def test_prefix_glob_modes_paging_and_caps() -> None:
    assert run(pattern="main", path="inputs/", output_mode="count").total_count == 2  # type: ignore[attr-defined]
    only = run(pattern="main", output_mode="files_only")
    assert only.files == ["inputs/app.py", "inputs/util.py", "outputs/notes.md"]  # type: ignore[attr-defined]
    assert run(pattern="main", file_glob="*.md").total_count == 2  # type: ignore[attr-defined]
    page = run(pattern="main", limit=2, offset=1)
    assert len(page.matches) == 2 and page.total_count == 4 and page.truncated is True  # type: ignore[attr-defined]
    first = run(pattern="main", limit=1)
    assert first.truncated is True  # type: ignore[attr-defined]
    long_line = [m for m in run(pattern="x{10}").matches]  # type: ignore[attr-defined]
    assert len(long_line[0].content) == 500
    named = run(pattern=r"util", target="files")
    assert named.files == ["inputs/util.py"]  # type: ignore[attr-defined]


def test_an_uncompilable_pattern_is_invalid_pattern() -> None:
    with pytest.raises(ToolFailed) as failed:
        run(pattern="(unclosed")
    assert str(failed.value) == "invalid_pattern"


def test_names_never_match_the_sdks_file_tools() -> None:
    sdk = {"read_file", "write_file", "edit_file", "grep", "glob", "ls", "execute"}
    assert not sdk & {tool.tool_id for tool in CODE_TOOLS}


@pytest.mark.parametrize(
    "arguments",
    [
        {"pattern": ""},
        {"pattern": "a", "context": 6},
        {"pattern": "a", "limit": 201},
        {"pattern": "a" * 201},
    ],
)
def test_ceilings_are_in_the_schema(arguments: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SearchFilesInput.model_validate(arguments)


# R-20, PTOL-01: a pattern that backtracks without end holds the interpreter lock, so a thread
# can't be stopped. The bounded search runs in a child process, which is stopped on time, and the
# event loop keeps going.
def test_a_runaway_pattern_ends_on_time_and_the_event_loop_keeps_running() -> None:
    import asyncio
    import time

    from autobots.application.code_tools import bounded_search

    files = {"inputs/slow.txt": "a" * 40 + "b"}
    arguments = SearchFilesInput.model_validate({"pattern": "(a+)+$", "path": "inputs/"})

    async def run() -> tuple[float, int, str]:
        ticks = 0
        stop = asyncio.Event()

        async def ticker() -> None:
            nonlocal ticks
            while not stop.is_set():
                ticks += 1
                await asyncio.sleep(0.01)

        task = asyncio.create_task(ticker())
        began = time.monotonic()
        try:
            await bounded_search(files, arguments, seconds=1.0)
            code = "finished"
        except ToolFailed as failed:
            code = str(failed)
        elapsed = time.monotonic() - began
        stop.set()
        await task
        return elapsed, ticks, code

    elapsed, ticks, code = asyncio.run(run())
    assert code == "search_timeout"
    assert elapsed < 5.0
    # About 100 ticks a second while the child works, so the loop was never stalled.
    assert ticks > elapsed * 50


def test_a_bounded_search_gives_the_same_answer_as_the_plain_one() -> None:
    import asyncio
    import time

    from autobots.application.code_tools import bounded_search

    arguments = SearchFilesInput.model_validate(
        {"pattern": "def ", "path": "inputs/", "context": 1}
    )
    began = time.monotonic()
    bounded = asyncio.run(bounded_search(FILES, arguments, seconds=8.0))
    spent = time.monotonic() - began
    assert bounded == search(FILES, arguments)
    # A process start per search: measured here, and well within the tool's 10 s timeout.
    assert spent < 5.0
    with pytest.raises(ToolFailed) as failed:
        asyncio.run(
            bounded_search(
                FILES, SearchFilesInput.model_validate({"pattern": "(", "path": ""}), seconds=8.0
            )
        )
    assert str(failed.value) == "invalid_pattern"


# R-20: the child never re-imports the caller's main module. A spawned process did, so a script
# with work at module level ran twice, and its second copy took the first one's leases. The request
# here is larger than a pipe's buffer, and the event loop keeps running while it is written.
SCRIPT = """
import asyncio, pathlib, sys, time
with pathlib.Path(sys.argv[1]).open("a") as marker:
    marker.write("imported\\n")
from autobots.application.code_tools import bounded_search
from autobots.contracts.code_tools import SearchFilesInput

async def main():
    ticks = 0
    stop = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    files = {f"inputs/{index}.txt": "line\\n" * 4000 for index in range(40)}
    arguments = SearchFilesInput.model_validate(
        {"pattern": "line", "path": "inputs/", "output_mode": "count"}
    )
    began = time.monotonic()
    found = await bounded_search(files, arguments)
    elapsed = time.monotonic() - began
    stop.set()
    await task
    print(found.total_count, ticks >= elapsed * 50)

asyncio.run(main())
"""


def test_a_search_from_a_script_runs_that_script_once(tmp_path: object) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    from autobots.application.bounded import SOURCE_ROOT

    folder = Path(str(tmp_path))
    script = folder / "worker_like.py"
    marker = folder / "imports.txt"
    script.write_text(SCRIPT)
    finished = subprocess.run(
        [sys.executable, str(script), str(marker)],
        env={**os.environ, "PYTHONPATH": SOURCE_ROOT},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr[-2000:]
    assert finished.stdout.split() == ["160000", "True"]
    assert marker.read_text() == "imported\n"


def test_a_child_that_ends_without_an_answer_fails_the_search_with_no_effect() -> None:
    import asyncio

    from autobots.application.bounded import ChildFailed, run_module

    with pytest.raises(ChildFailed):
        asyncio.run(run_module("autobots.application.no_such_module", b"{}", seconds=8.0))


def test_a_cancelled_search_kills_and_reaps_its_child(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from autobots.application.code_tools import bounded_search

    started: list[asyncio.subprocess.Process] = []
    spawn = asyncio.create_subprocess_exec

    async def recorded(*args: object, **kwargs: object) -> asyncio.subprocess.Process:
        process = await spawn(*args, **kwargs)  # type: ignore[arg-type]  # forwarded unchanged
        started.append(process)
        return process

    # bounded.py looks it up on the asyncio module at each call.
    monkeypatch.setattr(asyncio, "create_subprocess_exec", recorded)
    files = {"inputs/slow.txt": "a" * 40 + "b"}
    arguments = SearchFilesInput.model_validate({"pattern": "(a+)+$", "path": "inputs/"})

    async def run() -> None:
        task = asyncio.create_task(bounded_search(files, arguments, seconds=30.0))
        await asyncio.sleep(1.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert len(started) == 1
    # Reaped: the exit status was collected, here from the kill.
    assert started[0].returncode is not None
    assert started[0].returncode < 0


def test_the_child_limits_its_own_cpu_time() -> None:
    import signal
    import subprocess
    import sys

    from autobots.application.bounded import BOOTSTRAP, SOURCE_ROOT

    # A one-second cap, under the wait, so the kernel ends the match even with no parent to kill it.
    request = (
        b'{"files": {"inputs/slow.txt": "' + b"a" * 40 + b'b"}, '
        b'"arguments": {"pattern": "(a+)+$", "path": "inputs/"}}'
    )
    finished = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            BOOTSTRAP,
            SOURCE_ROOT,
            "autobots.application.code_search",
            "1",
        ],
        input=request,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert finished.returncode == -signal.SIGXCPU
