"""One runner for the tests/db checks a qualifier starts (refactor plan R-39, SCRP-01).

A child runs with the service's interpreter and exactly the arguments, environment, timeout and
directory its qualifier gives it. Its cases are replayed only from a last stdout line that parses as
`{"cases": [...]}` (tests/db/fixtures/checklib.py). A child that could not start, outlived its timeout, exited
non-zero, printed partial output, printed after its report or printed no report adds exactly one failed
case of its own and never raises, so a check that could not run stays visible as failed
(PRD-Development-Harness DH-09.2). Cases a failed child printed before it stopped are kept (TDBC-04),
and its stderr is kept under the qualifier's .checks directory.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from harness_lib import reduced_env

from qualification.errors import Unavailable
from qualification.records import Cases, ChildCase, ChildReport

CHECK_PYTHON = Path('services/agent/.venv/bin/python')
# Each child names its script under here with its folder: `checks/`, `arrange/` or `workers/` (tests/db/README.md).
CHECKS = Path('tests/db')
SERVICE_SOURCE = Path('services/agent/src')
# The modules the checks, workers and arrangements import, such as checklib (tests/db/README.md, TDBC-09).
DB_FIXTURES = Path('tests/db/fixtures')
CHILD_CASE_FIELDS = frozenset({'id', 'expected', 'observed', 'passed'})
# The end of a failed child's stderr holds its exception; Cases keeps the first 400 characters it is shown.
STDERR_SHOWN = 380
# What a failed arrangement's error shows of the command's stderr.
ARRANGEMENT_STDERR = 500
# Answers the first line a child prints with text for its stdin, or None to send nothing.
Answer = Callable[[str], str | None]


def tool_env() -> dict[str, str]:
    """No inherited credential, and no inherited target: only what Docker needs to find its engine."""
    env = reduced_env()
    for name in ('HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG'):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def service_env(root: Path, database_url: str, **extra: str) -> dict[str, str]:
    """A child's environment: no inherited credential, the given database URL, and the service's source and the
    database checks' fixtures on its path. A worker or browser helper a child starts inherits that path."""
    return {**tool_env(), 'AUTOBOTS_DATABASE_URL': database_url, **extra,
            'PYTHONPATH': os.pathsep.join((str(root / SERVICE_SOURCE), str(root / DB_FIXTURES))), 'PYTHONDONTWRITEBYTECODE': '1'}


@dataclass(frozen=True)
class Child:
    """One tests/db check in a qualifier's table, named with its folder, such as 'checks/memory_check.py'. Each
    argument is a template that `run_child` formats, such as '{workspace}'; `from_root` runs it from the repository
    root instead of the qualifier's directory."""

    script: str
    label: str
    args: tuple[str, ...] = ()
    timeout: float = 180
    from_root: bool = False
    err_name: str | None = None


@dataclass(frozen=True)
class ChildRun:
    """What one child did. `returncode` is None when it could not start or outlived its timeout."""

    label: str
    returncode: int | None
    stdout: str
    stderr: str
    report: ChildReport | None
    fields: Mapping[str, object] = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        """It exited 0 and printed its cases."""
        return self.returncode == 0 and self.report is not None

    def text(self, key: str) -> str:
        """A text field the report carried beside its cases, or ''."""
        value = self.fields.get(key)
        return value if isinstance(value, str) else ''

    def env(self, key: str) -> dict[str, str]:
        """A mapping the report carried beside its cases, such as `browser_env`, or {}."""
        value = self.fields.get(key)
        return {str(name): str(item) for name, item in value.items()} if isinstance(value, dict) else {}


def last_json(stdout: str) -> dict[str, object] | None:
    """The JSON object on the last line of `stdout`, or None."""
    lines = stdout.strip().splitlines()
    try:
        printed = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    return printed if isinstance(printed, dict) else None


def parse_report(stdout: str) -> tuple[ChildReport, dict[str, object]] | None:
    """A child's report and every field it printed, or None unless the last line is `{"cases": [...]}` with
    each case naming its id, expected, observed and a boolean passed."""
    printed = last_json(stdout)
    raw = printed.get('cases') if printed is not None else None
    if printed is None or not isinstance(raw, list):
        return None
    cases: list[ChildCase] = []
    for item in raw:
        if not (isinstance(item, dict) and CHILD_CASE_FIELDS <= item.keys() and isinstance(item['id'], str)
                and isinstance(item['passed'], bool)):
            return None
        cases.append({'id': item['id'], 'expected': str(item['expected']), 'observed': str(item['observed']),
                      'passed': item['passed']})
    return {'cases': cases}, printed


def record_child(cases: Cases, label: str, returncode: int | None, stdout: str, stderr: str,
                 problem: str | None = None) -> ChildRun:
    """Add a child's cases. A child that did not exit 0 fails one case, `<label> ran`; one that exited 0
    with no report, or with an empty one, fails one case, `<label> printed its cases` (XDUP-14). A report's
    cases are kept either way (TDBC-04)."""
    parsed = parse_report(stdout)
    if returncode != 0:
        reason = problem or f'exit {returncode}'
        tail = stderr.strip()[-STDERR_SHOWN:]
        cases.check(f'{label} ran', 'exit 0', f'{reason}: {tail}' if tail else reason, False)
    elif parsed is None:
        cases.check(f'{label} printed its cases', 'one JSON line of cases',
                    'a last line that is not one' if stdout.strip() else 'no output', False)
    if parsed is None:
        return ChildRun(label, returncode, stdout, stderr, None)
    report, fields = parsed
    if not report['cases']:
        # A report with nothing in it proves nothing, so it can't pass.
        cases.check(f'{label} printed its cases', 'at least one case', 'an empty list', False)
    for case in report['cases']:
        cases.check(case['id'], case['expected'], case['observed'], case['passed'])
    return ChildRun(label, returncode, stdout, stderr, report, fields)


def text_of(output: str | bytes | None) -> str:
    return output.decode(errors='replace') if isinstance(output, bytes) else output or ''


def answered(argv: list[str], env: Mapping[str, str], timeout: float, cwd: Path | str | None,
             answer: Answer) -> tuple[int, str, str]:
    """Run a child that waits on stdin after its first line, and reply with `answer`. `timeout` bounds the
    rest of its run, after the reply."""
    with subprocess.Popen(argv, env=dict(env), cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, errors='replace') as process:
        if process.stdin is None or process.stdout is None:
            raise OSError('the child has no pipes')
        first = ''
        try:
            first = process.stdout.readline()
            reply = answer(first)
            if reply is not None:
                with contextlib.suppress(BrokenPipeError):
                    process.stdin.write(reply)
                    process.stdin.flush()
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            out, err = process.communicate()
            raise subprocess.TimeoutExpired(argv, timeout, first + out, err) from None
        except BaseException:
            process.kill()
            raise
    return process.returncode, first + out, err


def keep_stderr(path: Path, stderr: str | None) -> None:
    """Keep a failed child's stderr, or remove what an earlier failed run left. Never raises."""
    with contextlib.suppress(OSError):
        if stderr is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(stderr)


def run_child_check(cases: Cases, root: Path, script: str, *args: str, label: str, env: Mapping[str, str], timeout: float,
                    err_dir: Path | None, cwd: Path | str | None = None, err_name: str | None = None,
                    answer: Answer | None = None) -> ChildRun:
    """Run `tests/db/<script>`, such as 'checks/memory_check.py', with the service's interpreter and record its
    cases (`record_child`).
    A failed child's stderr goes to `<err_dir>/<err_name or the script's stem>.err`."""
    argv = [str(root / CHECK_PYTHON), str(root / CHECKS / script), *args]
    returncode: int | None = None
    stdout = stderr = ''
    problem = None
    try:
        if answer is None:
            result = subprocess.run(argv, env=dict(env), capture_output=True, text=True, errors='replace', timeout=timeout,
                                    check=False, cwd=cwd)
            returncode, stdout, stderr = result.returncode, result.stdout, result.stderr
        else:
            returncode, stdout, stderr = answered(argv, env, timeout, cwd, answer)
    except subprocess.TimeoutExpired as error:
        problem, stdout, stderr = f'timed out after {timeout} seconds', text_of(error.stdout), text_of(error.stderr)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        problem = f'could not start: {type(error).__name__}: {error}'
    ran = record_child(cases, label, returncode, stdout, stderr, problem)
    if err_dir is not None:
        keep_stderr(err_dir / f'{err_name or Path(script).stem}.err', None if ran.completed else stderr)
    return ran


def run_child(cases: Cases, root: Path, child: Child, values: Mapping[str, str], *, env: Mapping[str, str],
              err_dir: Path | None) -> ChildRun:
    """Run one table entry, formatting its argument templates from `values`."""
    return run_child_check(cases, root, child.script, *(argument.format_map(values) for argument in child.args), label=child.label,
                           env=env, timeout=child.timeout, err_dir=err_dir, cwd=root if child.from_root else None,
                           err_name=child.err_name)


def launch(argv: Sequence[str], *, label: str, env: Mapping[str, str], timeout: float,
           cwd: Path | str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a helper a qualifier needs and judges itself. One that can't start or runs past `timeout`
    raises Unavailable, so the qualifier ends with exit 2 rather than a traceback (SCRP-01, DH-09.2)."""
    try:
        return subprocess.run(list(argv), env=dict(env), capture_output=True, text=True, errors='replace', timeout=timeout,
                              check=False, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise Unavailable(f'{label} timed out after {timeout} seconds') from None
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise Unavailable(f'{label} could not start: {type(error).__name__}') from error


def run_arrangement(cases: Cases, root: Path, script: str, *args: str, label: str, env: Mapping[str, str], timeout: float,
                    cwd: Path | str | None = None) -> dict[str, object]:
    """Run a tests/db helper that arranges state and prints one JSON object last, record `arranged: <label>`
    and return that object. One that could not run, failed or printed none raises Unavailable (SCRP-09)."""
    argv = [str(root / CHECK_PYTHON), str(root / CHECKS / script), *args]
    try:
        result = subprocess.run(argv, env=dict(env), capture_output=True, text=True, errors='replace', timeout=timeout,
                                check=False, cwd=cwd)
    except subprocess.TimeoutExpired:
        raise Unavailable(f'{label} could not be arranged: timed out after {timeout} seconds') from None
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise Unavailable(f'{label} could not be arranged: {type(error).__name__}: {error}') from error
    printed = last_json(result.stdout)
    if result.returncode or printed is None:
        raise Unavailable(f'{label} could not be arranged: exit {result.returncode}: {result.stderr[-ARRANGEMENT_STDERR:]}')
    cases.arranged(label, 'exit 0 and one JSON line', 'exit 0', True)
    return printed
