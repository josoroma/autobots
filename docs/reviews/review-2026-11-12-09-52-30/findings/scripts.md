# Scripts and hooks

The scripts area (28 modules, 10,215 lines, plus the 243-line hook dispatcher) is careful about safety and honest about what it proves. Every entry point documents its exit codes and what passing does not establish. Target guards refuse before any Docker or database change and prove ownership before removal. The hook is a thin adapter that fails closed. Pure logic such as release scoring, refusal rules and request shapes is covered by about 235 harness tests. Maintainability is weak, though. No linter, formatter or type checker covers this code: under the service's own configuration none of the 29 files passes `ruff format --check`, and 2,092 lines exceed 100 characters. The code grows by copying. The child-check runner appears 29 times, the disposable-stack setup, teardown and report skeleton 13 times, and the paid-run helper and watchdog 3 to 4 times, and the copies have started to drift on exit-code checks and on spend reporting. Qualifier scripts double as libraries: qualify_identity and qualify_operations are imported by 7 and 6 other scripts. Meanwhile harness_lib's hand-written domain map ignores that import graph, so the Stop hook can accept stale db evidence. Six functions run 215 to 410 lines, and qualify_identity.qualify takes on an inline fixture for nearly every story (52 commits between 2026-11-05 and 2026-11-08). Records and reports are untyped dicts whose vocabulary drifts. Two unrelated `Unavailable` classes break the exit-code contract in three scripts. [Back to the review](../README.md)

Area `scripts`, revision `156534da0bd5b19417f05d313077d767804b175b`, run `2026-11-12-09-52-30`. Every finding below was re-opened at its cited lines and recounted by an adversarial verifier.

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 2 | DH-06 asks for Ruff and strict mypy on owned modules, and neither runs here (0 of 29 files formatted, 2,092 lines over 100 characters), though the project's own conventions (exit codes, no installs, stated limits) are followed consistently. |
| modules | 2 | Qualifiers double as libraries (fan-in 7 and 6), harness_lib mixes six concerns behind 24 importers, and the check-domain map ignores the import graph. |
| size | 2 | Ten functions exceed 150 lines (410, 326, 315, 250, 240, 215, 165, 164, 160, 153) and three files exceed 700 lines (persistent_install.py 810, qualify_identity.py 754, app_db.py 721). |
| functions | 2 | Scenario monoliths are built from nested closures, browser_cases takes 14 parameters, and validators mutate what they validate; well-shaped pure helpers are the exception. |
| structure | 3 | Entry points are named and documented consistently, but one flat directory mixes harness tools, libraries, DB tooling, qualifiers and paid trials, and DH-03's scripts/db/ does not exist. |
| approach | 3 | The guard design is sound (refuse first, prove ownership, fail closed), but orchestration relies on copied code, f-string SQL piped to psql and inline -c programs. |
| comments | 4 | Every module states its purpose, exit codes and limits, and why-comments cite stories and decisions; one module docstring is stale, and the giant functions lean on section comments. |
| types | 2 | Records and reports are untyped dicts, Any and object appear with 14 type: ignore in persistent_install.py and no checker running, and evidence vocabulary is free text; the specs.py and toolchain.py dataclasses are the exception. |
| errors | 3 | There is a clear Refused/Unavailable/exit-code contract and a fail-closed hook, but scripts that mix two Unavailable classes break it, JSON at child boundaries is unguarded, and 33 results are discarded. |
| tests | 3 | About 235 harness tests cover guards, hooks, specs, evidence and scoring, but the paid watchdog has no behavioral test, goal's call to its guard has only a source-text test, and some qualifier cases can pass vacuously. |
| maintainability | 2 | The busiest files (qualify_identity.py with 52 commits, app_db.py with 31) grow by copying blocks, and no lint or type ratchet catches the drift that has already started. |

## Strengths

- **Thin, fail-closed hook adapter.** .claude/hooks/dispatch.py bounds its input (MAX_INPUT and MAX_PATH_BYTES, lines 24-25 and 227-229), lets an environment override only shorten the 9 s deadline (207-213), passes filenames after `--` in an argument array (134-138), keeps stdout for the JSON response and turns any failure into exit 2 (235-237). It chooses the worktree by asking Git with a ceiling directory (58-93). tests/harness/test_hooks.py holds 45 tests for it.
- **Refuse before any change, prove ownership before removal.** scripts/disposable_db.py identity_refusals runs before any Docker call and refuses connection variables that name another target (122-153). rendered_refusals inspects the merged Compose output (162-190). require_labels and the marker row prove ownership before cleanup or reset (202-230). scripts/persistent_install.py identity_refusals checks the name, label, port and identity row (135-158). scripts/qualify_persistent_apply.py refused() asserts that the database state is unchanged after each refusal (32-40). tests/harness/test_disposable_guard.py has 11 guard tests.
- **Pure decisions pulled out of effectful runs and unit-tested.** scripts/release_scoring.py is pure and has 26 tests in test_release_qualification.py. qualify_worker_inference.request_shape_problems (52-58), qualify_mac_sleep.assess (85-102) and persistent_install refuse_other_work and note_failed (309-321) are tested without Docker in test_final_review.py. This is the shape to spread to the paid watchdog and ledger settlement.
- **Results that cannot overclaim.** scripts/verify.py judge_unittest and judge_pytest fail an empty or skipped suite (91-107), exit_code_for ranks a failure above an unavailable prerequisite (190-197), the non-mutation guard compares before and after snapshots ([scripts/toolchain.py:271-290](../../../../scripts/toolchain.py#L271)), and every report lists what it does not establish ([verify.py:42-49](../../../../scripts/verify.py#L42)).
- **Docstrings as contracts.** Each entry point's module docstring states its purpose, exit codes and limits ([scripts/verify.py:2-7](../../../../scripts/verify.py#L2), [scripts/disposable_db.py:2-10](../../../../scripts/disposable_db.py#L2), [scripts/local_backup.py:2-10](../../../../scripts/local_backup.py#L2), [scripts/qualify_web.py:2-9](../../../../scripts/qualify_web.py#L2)), and why-comments record constraints that are not obvious ([.claude/hooks/dispatch.py:23](../../../../.claude/hooks/dispatch.py#L23) and 26, [scripts/toolchain.py:183-185](../../../../scripts/toolchain.py#L183), [scripts/local_backup.py:345-346](../../../../scripts/local_backup.py#L345)).
- **Careful backup format.** scripts/local_backup.py seals chunks with AES-GCM and binds the component, index and final flag into the associated data, so frames cannot be reordered, dropped or moved (98-141). It verifies an HMAC'd manifest before Docker is touched (261-280) and creates every file with O_EXCL and mode 0600 (105, 225-230).
- **specs.py as a typed, layered tool.** scripts/specs.py uses frozen or plain dataclasses for Issue, Task, Story, Epic and Document (40-87), keeps parse, validate, render and promote as separate steps, and writes atomically, refusing a concurrent edit (565-582). It has 41 tests in tests/harness/test_specs.py.
- **Reproducible toolchain selection.** scripts/toolchain.py find_pinned accepts only an install that reports the exact pinned version and never downloads (152-157). child_env reduces the environment, keeps tool state inside the repository and forces offline mode when verifying (172-189). run_step kills the whole process group on timeout (229-256).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [SCRP-01](#scrp-01) | high | duplication | The service child-check runner is hand-copied 29 times, with divergent failure handling | M | medium |
| [SCRP-02](#scrp-02) | high | size | qualify_identity.py takes on a new inline fixture for nearly every story | M | medium |
| [SCRP-03](#scrp-03) | high | duplication | Paid-run guards are copied across four entry points and already disagree | M | high |
| [SCRP-04](#scrp-04) | high | standards | No linter, formatter or type checker covers scripts/ or the hook | L | low |
| [SCRP-05](#scrp-05) | medium | size | Six more qualifiers are single 165-410 line functions held together by closures and section comments | M | medium |
| [SCRP-06](#scrp-06) | medium | modules | Qualifiers double as libraries, and the Stop hook's domain map ignores that import graph | M | medium |
| [SCRP-07](#scrp-07) | medium | duplication | The disposable-stack skeleton is copied into 13 entry points, and only one copy checks its cleanup listing | M | medium |
| [SCRP-08](#scrp-08) | medium | errors | Two unrelated Unavailable classes break the exit-code contract where scripts mix them | S | low |
| [SCRP-09](#scrp-09) | medium | tests | Arrangements whose failures are never checked let qualifier cases pass vacuously | S | medium |
| [SCRP-10](#scrp-10) | medium | types | Case records and qualification reports are untyped dicts whose vocabulary drifts | M | low |
| [SCRP-12](#scrp-12) | medium | modules | harness_lib is a grab bag, and each profile's checks are registered in five places | M | medium |
| [SCRP-15](#scrp-15) | medium | structure | scripts/ is a flat mix of entry points and libraries, without the scripts/db/ that DH-03 lays out | L | medium |
| [SCRP-11](#scrp-11) | low | functions | config_errors validates six concerns in 91 lines, and its early returns drop errors | S | low |
| [SCRP-13](#scrp-13) | low | duplication | Secret-file names are listed three times, and the input manifest's list is the shortest | S | low |
| [SCRP-14](#scrp-14) | low | duplication | Small helpers are re-implemented per script, often under the same name with different behavior | M | low |
| [SCRP-16](#scrp-16) | low | duplication | Three ad hoc dotenv parsers ignore the quoting and export rules the app's own parser applies | S | medium |
| [SCRP-17](#scrp-17) | low | approach | Six Python programs are passed as -c strings and import service internals out of sight | S | low |
| [SCRP-18](#scrp-18) | low | approach | verify runs checks two ways, with different timeout semantics and record shapes | S | low |
| [SCRP-19](#scrp-19) | low | naming | Schema facts are hard-coded where they will go stale | S | low |
| [SCRP-20](#scrp-20) | low | functions | specs.py validate_story fills in the Story while validating it, and fence parsing exists twice | S | low |
| [SCRP-21](#scrp-21) | low | comments | specs.py's module docstring understates what the tool writes | S | low |

### <a id="scrp-01"></a>SCRP-01: The service child-check runner is hand-copied 29 times, with divergent failure handling

- **Severity** high · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 29
- **Where:**
  - [scripts/app_db.py:408-491](../../../../scripts/app_db.py#L408): tool_cases: nine copies in one function
  - [scripts/app_db.py:334-358](../../../../scripts/app_db.py#L334): credential_cases: Popen variant that returns on failure
  - [scripts/app_db.py:501-514](../../../../scripts/app_db.py#L501): loop_cases: parses stdout even after a failure
  - [scripts/app_db.py:586-593](../../../../scripts/app_db.py#L586): routine_cases: also writes stderr to a .err file
  - [scripts/qualify_identity.py:175-187](../../../../scripts/qualify_identity.py#L175): 16 children in one loop, with browser_env side output
  - [scripts/qualify_operations.py:314-321](../../../../scripts/qualify_operations.py#L314)
  - [scripts/qualify_upgrade.py:181-188](../../../../scripts/qualify_upgrade.py#L181)
  - [scripts/qualify_browse_goal.py:74-84](../../../../scripts/qualify_browse_goal.py#L74)
- **Evidence:** There are 29 copies of the replay statement `for case in json.loads(<proc>.stdout.strip().splitlines()[-1])['cases']: cases.check(case['id'], case['expected'], case['observed'], case['passed'])`, counted with grep: 19 in app_db, 4 in qualify_identity, 2 in qualify_upgrade, and one each in qualify_operations, qualify_backup, qualify_browse_goal and qualify_browser_executor. Each follows its own subprocess call with an inline service environment, and `'PYTHONPATH': str(root / 'services/agent/src')` appears 39 times in 10 files. On failure, some copies return, some parse whatever stdout holds, and 9 of the 29 save stderr to a .err file. No copy guards the parse:

  ```python
  if result.returncode:
      cases.check('the goal loop check ran', 'exit 0', f'exit {result.returncode}: ...', False)
      if not result.stdout.strip():
          return
  for case in json.loads(result.stdout.strip().splitlines()[-1])['cases']:
  ```
- **Why it matters:** Each db story adds another copy (app_db.py has 31 commits since 2026-10-01), and the copies already disagree on what a crashed child records. If a child's last stdout line is not its JSON report, for example after a late warning or a crash with partial output, json.loads raises out of qualify(). main catches only Refused and Unavailable, so the run ends in a traceback with exit 1. The report file was already deleted at the start, so every other case's evidence is lost too.
- **Recommendation:** Write one run_child_check helper in a shared qualification module. It should build the service environment once, run the child with its own argv, timeout and cwd, always keep stderr under the profile's .checks directory, and record a failed '&lt;label> check ran' case on a non-zero exit. It should replay cases only from a last line that parses as {'cases': [...]}, so a parse failure becomes one failed case instead of an exception. Express app_db.tool_cases and qualify_identity's child loop as data tables. Prove the change with the db and operations profiles.
- **Rule check:** DH-09.2 and AGENTS.md completion evidence: a check that could not run must stay visible as failed and never count as passed. The helper keeps each child's argv, environment and timeout and touches no target guard, so nothing is weakened.
- **Verification:** confirmed. 29 replay statements recounted with grep (19 in app_db, 4 in qualify_identity, 2 in qualify_upgrade, one each in four more), plus 39 inline PYTHONPATH entries in 10 files and 9 .err writes. app_db.main catches only Refused and Unavailable, and qualify() deletes the report before the run, so a bad last line loses the whole report.

```text
# scripts/qualification/children.py
def service_env(root: Path, database_url: str, **extra: str) -> dict[str, str]
def run_child_check(cases: Cases, root: Path, script: str, *args: str, label: str,
                    env: Mapping[str, str], timeout: float = 180, cwd: Path | None = None,
                    err_dir: Path) -> ChildReport | None   # never raises on bad output
# scripts/app_db.py
TOOL_CHILDREN = (Child('tool_gateway_check.py', 'tool gateway', temp_cwd=True),
                 Child('tool_use_check.py', 'tool-use'), ...)
for child in TOOL_CHILDREN:
    run_child_check(cases, root, child.script, WORKSPACE_A, label=child.label, env=..., err_dir=...)
```

### <a id="scrp-02"></a>SCRP-02: qualify_identity.py takes on a new inline fixture for nearly every story

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 3
- **Where:**
  - [scripts/qualify_identity.py:414-739](../../../../scripts/qualify_identity.py#L414): qualify, 326 lines
  - [scripts/qualify_identity.py:252-411](../../../../scripts/qualify_identity.py#L252): browser_cases, 160 lines and 14 parameters
  - [scripts/qualify_identity.py:140-249](../../../../scripts/qualify_identity.py#L140): artifact_cases, 110 lines, mostly not about artifacts
  - [scripts/qualify_identity.py:474-494](../../../../scripts/qualify_identity.py#L474): US-15.4 arrangement as an f-string SQL fixture
  - [scripts/qualify_identity.py:590-646](../../../../scripts/qualify_identity.py#L590): US-15.13 arrangement, 57 lines
  - [scripts/qualify_identity.py:317](../../../../scripts/qualify_identity.py#L317): 442-character Playwright argv of substring filters
- **Evidence:** qualify() holds 12 story-labelled arrangement blocks (US-15.3 to US-16.3). Each one bootstraps an owner (15 calls with the same four leading arguments), runs an f-string SQL fixture with hand-escaped JSON and grows `artifacts` (12 `artifacts = {**artifacts, ...}` steps). The later blocks record an 'arranged' case, but seven arrangements record none (the first run, member C, the no-key run and the US-15.3, 15.4, 15.6 and 15.7 blocks). Only then does browser_cases receive 14 parameters. artifact_cases also runs 16 unrelated child checks, the US-16.2 schema-state arrangement and the US-13.1 legacy-approval arrangement, so its name hides most of what it does. Ordering invariants live only in comments, such as 'Last, so no later check's cleanup ends the runs they leave claimed for the browser' (line 170). The file has 52 commits, all between 2026-11-05 and 2026-11-08, and 48 of the repository's 114 Deliver commits edit it.
- **Why it matters:** Every browser story edits the same 326-line function, so unrelated fixtures collide in review and merge, ordering between arrangements stays implicit, and no arrangement can be run or tested on its own. SQL and JSON hand-escaped inside f-strings break easily, and in the seven unasserted arrangements they break silently. Which browser spec runs where can only be read from argv lists like the one at line 317.
- **Recommendation:** Introduce an IdentityRun context (stack, base, db_port, runtime_url, service key, anon key) and an Owner record (email, password, workspace_id, user_id). Move each story's arrangement into an `arrange_<story>(run, cases) -> dict[str, str]` function registered in an ordered tuple, and keep its SQL in tests/db fixture files or build it with a quoting helper. browser_cases then takes (run, owners, env). Rename artifact_cases to say what it does, or split it into artifact children, schema-state cases and legacy-approval cases. Name the Playwright suite lists as constants.
- **Rule check:** DH-07: test fixtures are synthetic and used in disposable environments only. Moving them into tests/db fixture files keeps them out of supabase/migrations and supabase/seeds, and the qualification stays on its disposable target.
- **Verification:** revised. Spans recounted with ast (qualify 414-739, browser_cases 252-411 with 14 parameters, artifact_cases 140-249), and the 12 story blocks, 15 owner bootstraps, 12 artifact merges and 442-character argv confirmed. Corrected: seven arrangements go unasserted rather than most, and 48 of 114 Deliver commits touch the file rather than most.

```text
@dataclass(frozen=True)
class Owner: email: str; password: str; workspace_id: str; user_id: str
@dataclass
class IdentityRun:
    root: Path; stack: AppStack; base: str; db_port: int; runtime_url: str
    def owner(self, email: str) -> Owner          # bootstrap_owner + generated password
Arrangement = Callable[[IdentityRun, Cases], dict[str, str]]
ARRANGEMENTS: tuple[Arrangement, ...] = (arrange_no_key_run, arrange_reader_15_3, arrange_runs_15_4, ...)
def qualify(root):
    with disposable_app_stack(root, cases, extra_ports=0) as stack_run:
        run = IdentityRun(...); env: dict[str, str] = {}
        for arrange in ARRANGEMENTS: env |= arrange(run, cases)
        browser_cases(run, owners, env)
MAIN_SUITE: tuple[str, ...] = ('browser/workflows.spec', 'browser/operations', ...)
```

### <a id="scrp-03"></a>SCRP-03: Paid-run guards are copied across four entry points and already disagree

- **Severity** high · **Dimension** duplication · **Effort** M · **Risk** high · **Occurrences** 4
- **Where:**
  - [scripts/persistent_install.py:324-476](../../../../scripts/persistent_install.py#L324): goal, 153 lines
  - [scripts/persistent_install.py:535-698](../../../../scripts/persistent_install.py#L535): examples, 164 lines
  - [scripts/persistent_install.py:399-415](../../../../scripts/persistent_install.py#L399): watchdog copy 1
  - [scripts/persistent_install.py:633-650](../../../../scripts/persistent_install.py#L633): watchdog copy 2
  - [scripts/persistent_install.py:660-663](../../../../scripts/persistent_install.py#L660): examples stores None for an unreadable spend; goal records a failed check
  - [scripts/live_goal.py:127-143](../../../../scripts/live_goal.py#L127): watchdog copy 3
  - [scripts/qualify_release.py:99-103](../../../../scripts/qualify_release.py#L99): fourth identical helper()
  - [tests/harness/test_final_review.py:91-93](../../../../tests/harness/test_final_review.py#L91): the only test of goal's guard reads its source text
- **Evidence:** helper() is identical in persistent_install.goal (337), examples (549), live_goal.attempt (74) and qualify_release.attempt (99). The spend watchdog loop exists three times. stop_worker, owner sign-in, refuse_other_work, the post-run key-usage and leak checks and the ledger settlement are duplicated between goal and examples. The copies have drifted: goal records an unreadable spend as a failed check (427-430), but examples stores None and can still exit 0 (660-663, 698):

  ```python
  spent = sql(spent_since)
  report['committed_micro_usd'] = int(spent) if spent else None
  charged = int(spent) if spent else None
  ```

  All three watchdogs read spend through a helper that returns '' on any SQL error, and `if committed and int(committed) > limit` then skips that poll. The only unit test of goal's guard asserts on inspect.getsource(persistent_install.goal), because the function cannot be called on its own. There are 14 `type: ignore[attr-defined]` because reserve_goal returns `tuple[object, dict]`.
- **Why it matters:** These paths spend real money under the shared cap. A fix to the watchdog, the settlement or the after-run checks must be made in three or four places, and the examples copy can already report success without knowing what it spent. An unreadable spend never stops the worker, so each poll fails open, and none of this logic has a behavioral test.
- **Recommendation:** Start with tests. Extract pure decision functions and test them in tests/harness with a fake clock and a fake sql: watchdog_verdict(committed, limit, unreadable_polls), settlement(started, finals, charged) and goal_exit_code(report). Then move the shared mechanics into one module that goal, examples, live_goal and qualify_release all use. Make 'spend unreadable for N polls' an explicit decision, such as stopping the worker, rather than an accident. Type the ledger through a TYPE_CHECKING import or a Protocol so the ignores can go.
- **Rule check:** AGENTS.md Boundaries (OpenRouter only, budgets before live inference) and the ground rule never to weaken a guardrail. Keep the --paid refusal, refuse_other_work, the reservation before any request, the SIGKILL watchdog and the hold-on-unfinished settlement; the change only makes them single and tested. The extracted pure functions need no paid run; a live check stays a separately authorized task.
- **Verification:** confirmed. Four helper() bodies (differing only in their env), three watchdog loops (persistent_install.py:399 and 633, live_goal.py:127), the goal/examples drift on an unreadable spend (persistent_install.py:427-430 versus 660-663 and 698) and 14 type: ignore comments confirmed. The source-text test sits at test_final_review.py:91-93.

```text
# scripts/paid_run.py
class Ledger(Protocol):
    def settle(self, entry: dict, charged: int | None, state: str) -> None: ...
    def committed(self) -> int: ...
@dataclass
class PaidSession:
    root: Path; stack: AppStack; env: dict[str, str]
    def helper(self, *argv: str) -> str
    def sql(self, statement: str) -> str | None        # None = unreadable, never ''
    def sign_in(self, owner: Mapping[str, str]) -> str
    def start_worker(self, log: Path) -> Popen; def stop_worker(self, report: dict) -> None
def watch(session, run_ids, limit, spend_query, worker, *, clock=time.monotonic, sleep=time.sleep) -> WatchResult
def settle(ledger: Ledger, entry, started: bool, finals: Mapping[str, str], charged: int | None) -> None
def after_run_checks(session, key_file: Path, logs: Path, report: dict) -> None
```

### <a id="scrp-04"></a>SCRP-04: No linter, formatter or type checker covers scripts/ or the hook

- **Severity** high · **Dimension** standards · **Effort** L · **Risk** low · **Occurrences** 29
- **Where:**
  - [services/agent/pyproject.toml:41-52](../../../../services/agent/pyproject.toml#L41): ruff and mypy configured for src and tests only
  - [scripts/toolchain.py:208-213](../../../../scripts/toolchain.py#L208): ruff and mypy steps run inside services/agent
  - [.claude/hooks/dispatch.py:161](../../../../.claude/hooks/dispatch.py#L161): post-edit ruff diagnostic only for services/agent paths
  - [scripts/app_db.py:117](../../../../scripts/app_db.py#L117): 578-character line
  - [scripts/persistent_install.py:31](../../../../scripts/persistent_install.py#L31): F401: other_resources imported but unused
  - [scripts/qualify_backup.py:89](../../../../scripts/qualify_backup.py#L89): F841: workspace_b never used
  - [scripts/persistent_install.py:331](../../../../scripts/persistent_install.py#L331): one of 15 type: ignore with no checker running
- **Evidence:** ruff and mypy run only on services/agent (`files = ["src", "tests"]`). Under the service's own configuration, `ruff format --check` would reformat all 29 files. 2,092 lines exceed 100 characters (464 exceed 150, 102 exceed 200, and the longest is 578 at app_db.py:117). Beyond 2,079 E501 hits, `ruff check` reports 94 more: 30 unsorted import blocks, 34 datetime.UTC aliases, five deliberate UP036 interpreter-version guards and 25 others, including F401 at persistent_install.py:31, F841 at qualify_backup.py:89, five unused unpacked values and four zip() calls without strict=. The 15 `type: ignore` comments (14 in persistent_install.py) suppress a checker that never runs. The hook's post-edit ruff diagnostic fires only when `domains == {'python'}`, so editing a script gets no lint feedback. Quoting style also diverges: single quotes everywhere except specs.py, against the service's double-quoted ruff format.
- **Why it matters:** About 10,000 lines that guard disposable targets, the persistent install, backups and paid caps change daily with no mechanical check. The defect classes found in this review (dead variables, mismatched exception classes, untyped records, escaped newlines) can recur unnoticed, and no ratchet stops size and duplication from growing.
- **Recommendation:** Add a ruff and mypy scope for scripts/ and .claude/hooks/ that the fast profile runs with the prepared binaries, with no install. (1) Reformat once in an explicit commit, then rerun the profiles because the verifier fingerprint changes. (2) Run `ruff check` with the service's rule set, baselining E501 per file and ratcheting it down. (3) Run mypy --strict first on dispatch.py, harness_lib.py, verify.py, specs.py, evidence.py and toolchain.py, which form the hook's trust boundary, then on the libraries, listing per-module overrides in config. Map script edits to this step in check_domains, and let the hook's post-edit diagnostic lint scripts too.
- **Rule check:** DH-06: 'Use Ruff for lint/format, mypy strict for owned modules'. DH-05 forbids automatic formatter rewrites in hooks, so formatting is one explicit commit and the hook only diagnoses. AGENTS.md says checks use prepared environments and install nothing; the service venv already holds ruff and mypy.
- **Verification:** confirmed. Re-ran `ruff format --check --no-cache` with the service configuration: 29 files would be reformatted. Line counts, the 15 ignores and the hook's python-only diagnostic (dispatch.py:161) confirmed; the ruff check breakdown comes from the run saved in .checks/reviews/review-2026-11-12-09-52-30/scripts/.

```text
# ruff.toml at the root, or a scripts section that extends the service config
extend = 'services/agent/pyproject.toml'
src = ['scripts', '.claude/hooks']
[lint.per-file-ignores]
'scripts/qualify_identity.py' = ['E501']   # baseline, shrink per wave
# mypy config
files = ['scripts', '.claude/hooks']; strict = true
[[tool.mypy.overrides]] module = ['qualify_*', 'app_db']; disallow_untyped_defs = false   # ratchet list
# verify.py: Step('scripts_lint', (venv / 'ruff', 'check', 'scripts', '.claude/hooks'), root) in PYTHON_STEPS
```

### <a id="scrp-05"></a>SCRP-05: Six more qualifiers are single 165-410 line functions held together by closures and section comments

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 6
- **Where:**
  - [scripts/qualify_worker_inference.py:65-474](../../../../scripts/qualify_worker_inference.py#L65): qualify, 410 lines
  - [scripts/qualify_worker_inference.py:94-147](../../../../scripts/qualify_worker_inference.py#L94): 13 closures over shared locals
  - [scripts/qualify_release.py:76-390](../../../../scripts/qualify_release.py#L76): attempt, 315 lines, paid
  - [scripts/qualify_release.py:192-266](../../../../scripts/qualify_release.py#L192): run_task rebinds the outer worker with nonlocal
  - [scripts/qualify_backup.py:43-292](../../../../scripts/qualify_backup.py#L43): qualify, 250 lines
  - [scripts/qualify_operations.py:136-375](../../../../scripts/qualify_operations.py#L136): qualify, 240 lines; scenarios separated by comments
  - [scripts/qualify_upgrade.py:47-261](../../../../scripts/qualify_upgrade.py#L47): qualify, 215 lines
  - [scripts/qualify_mac_sleep.py:105-269](../../../../scripts/qualify_mac_sleep.py#L105): observe, 165 lines
- **Evidence:** qualify_worker_inference.qualify is 410 lines with 13 nested closures (helper, save_key, admit, status, settled, sent, goal_view, invocations, reply_facts, verdict, stop_reason, resume, verified_report) and a later why(). qualify_release.attempt is 315 lines with seven closures, including a 75-line run_task. qualify_operations.qualify separates its scenarios only with comments ('# Drain: ...', '# Readiness failures ...', '# Ordinary shutdown ...', '# Recovery ...', '# Retention ...'). One worker process started at qualify_worker_inference.py:195 serves every later case; the comment above it says so, but nothing marks which later cases depend on the state earlier ones leave.
- **Why it matters:** No scenario can be run, reviewed or retried on its own. An unexpected exception mid-function skips every later scenario, and the report records nothing about them. Reading one case means holding up to 400 lines of shared local state in mind.
- **Recommendation:** Turn the closures into methods of a small context class per qualifier, and each commented section into a scenario function `def drain(ctx, cases) -> None`. Run the scenarios from an ordered tuple through a shared runner that records a scenario that raised as one failed case and marks the remaining ones not_run. Keep the order explicit in the tuple.
- **Rule check:** AGENTS.md: the operations profile runs on disposable projects with a scripted model. Scenarios keep their assertions and arranged inputs, and not_run stays visible as DH-09.2 requires, so nothing that passes today can pass by being skipped.
- **Verification:** revised. Six spans recounted with ast (410, 315, 250, 240, 215 and 165 lines) and the closures confirmed. The shared worker is documented at qualify_worker_inference.py:194, so the evidence now says the order is stated for the worker, though not for the cases that follow it.

```text
class InferenceRun:            # was the closures inside qualify()
    def status(self, run_id: str) -> str
    def settled(self, run_id: str, wanted: str, seconds: float = 90) -> bool
    def sent(self, tag: str) -> list[RequestLine]; def invocations(self, run_id: str) -> str
Scenario = Callable[[InferenceRun, Cases], None]
SCENARIOS: tuple[Scenario, ...] = (switch_off, partial_config, happy_path, other_profile, reasoning,
                                   workflow, compaction, request_shapes, child_billing, rotation, ...)
def run_scenarios(ctx, cases, scenarios) -> None   # exception -> failed case; the rest -> not_run
```

### <a id="scrp-06"></a>SCRP-06: Qualifiers double as libraries, and the Stop hook's domain map ignores that import graph

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 4
- **Where:**
  - [scripts/qualify_identity.py:40-66](../../../../scripts/qualify_identity.py#L40): http, bootstrap_owner and password_token, used by 7 scripts
  - [scripts/qualify_operations.py:35-133](../../../../scripts/qualify_operations.py#L35): Checks, Ops, api_call, wait and exited, used by 6 scripts
  - [scripts/live_goal.py:30-46](../../../../scripts/live_goal.py#L30): constants and rows, used by persistent_install and qualify_release
  - [scripts/qualify_identity.py:30](../../../../scripts/qualify_identity.py#L30): a db qualifier imports qualify_web
  - [scripts/persistent_install.py:799](../../../../scripts/persistent_install.py#L799): lazy import of live_goal, which qualify_persistent_apply exercises
  - [scripts/harness_lib.py:51-57](../../../../scripts/harness_lib.py#L51): domain lists kept by hand
  - [scripts/harness_lib.py:145-157](../../../../scripts/harness_lib.py#L145): check_domains
  - [scripts/harness_lib.py:236-247](../../../../scripts/harness_lib.py#L236): evidence_state asks for a db report only for paths mapped to 'db'
- **Evidence:** qualify_identity is imported by 7 scripts for bootstrap_owner, password_token, http, PYTHON and STORAGE_SQL. qualify_operations is imported by 6 for Ops, api_call, wait, exited, Checks, conditions and durable_counts. live_goal provides constants to persistent_install and qualify_release, and qualify_web provides start, stop and BROWSERS to 3 scripts. For this review an ast walk computed the import closure of the db profile's five step scripts. It includes qualify_web and toolchain, which check_domains maps to {'python', 'web'}, and live_goal and qualify_operations, which it maps to {'harness'}. The path runs through persistent_install's `goal` branch, which qualify_persistent_apply's CLI cases execute and which imports live_goal, qualify_operations, qualify_identity and qualify_web.
- **Why it matters:** Editing a helper inside one qualifier silently changes six or seven others. An edit to qualify_web.py or qualify_operations.py, both on the db profile's import path, is accepted at Stop on a fast or harness report while the db evidence is stale. DB_CHECK_FILES has to follow the imports by hand, and only two of its entries are tested (test_final_review.py:60-62).
- **Recommendation:** Move the shared helpers out of the qualifiers into a library package (owners, ops processes, HTTP, report writing) whose files belong to every profile that imports them. Derive script domains from the import closure: compute the closure of each profile's step scripts with ast in harness_lib (stdlib only), or at least assert it in a harness test, so a new import cannot fall outside the db domain unnoticed.
- **Rule check:** DH-05: Stop inspects fresh evidence for the changed scope. Deriving domains from imports only adds required profiles and never removes one, and the hook stays a thin adapter over repository scripts.
- **Verification:** confirmed. Fan-in recomputed with an ast walk (qualify_identity 7, qualify_operations 6, qualify_web 3, live_goal 2, harness_lib 23 plus the hook). The db profile's closure includes qualify_web and toolchain ({'python', 'web'}) and live_goal and qualify_operations ({'harness'}), reached through persistent_install's goal branch at line 799, which qualify_persistent_apply drives.

```text
scripts/qualification/          # library only, no __main__
  owners.py   Owner, bootstrap_owner, password_token
  ops.py      Ops, api_call, wait, exited, conditions, durable_counts
  net.py      http(method, url, headers, body, *, follow_redirects=False)
# harness_lib.py
def profile_closure(root: Path, profile: str) -> set[str]   # ast import walk from verify's step scripts
def check_domains(relative): ... 'db' if relative in profile_closure(root, 'db') ...
# test: profile_closure('db') <= {p for p in scripts if 'db' in check_domains(p)}
```

### <a id="scrp-07"></a>SCRP-07: The disposable-stack skeleton is copied into 13 entry points, and only one copy checks its cleanup listing

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** medium · **Occurrences** 13
- **Where:**
  - [scripts/disposable_db.py:591-597](../../../../scripts/disposable_db.py#L591): the one copy that checks the listing's exit codes
  - [scripts/app_db.py:689-692](../../../../scripts/app_db.py#L689)
  - [scripts/qualify_identity.py:726-729](../../../../scripts/qualify_identity.py#L726)
  - [scripts/supabase_stack.py:312-315](../../../../scripts/supabase_stack.py#L312)
  - [scripts/qualify_operations.py:136-153](../../../../scripts/qualify_operations.py#L136): setup copy
  - [scripts/qualify_browse_goal.py:45-47](../../../../scripts/qualify_browse_goal.py#L45): an image probe stands in for a Docker probe
  - [scripts/qualify_mac_sleep.py:105-126](../../../../scripts/qualify_mac_sleep.py#L105): no Docker probe at all
  - [scripts/qualify_identity.py:733-738](../../../../scripts/qualify_identity.py#L733): hand-built report
- **Evidence:** 13 scripts repeat the same steps: a project name from PROJECT_PREFIX plus token_hex(4), chained free_port calls, `AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', ...)`, the migrator and runtime password pair, require_identity, a Docker probe, require_rendered and require_images, and an other_resources snapshot. Then come `finally: remove_stack`, the 'cleanup removed the owned containers and volumes' case, the 'other Docker resources are untouched' case and a hand-built JSON report. The copies diverge. 11 of the 12 cleanup checks join the stdout of `docker volume ls` and `docker ps` without checking exit codes, so a failed listing reads as 'none left'; only disposable_db.py:594 raises. The other_resources call that follows raises when Docker can list nothing, so the gap is a filtered listing that fails on its own. qualify_mac_sleep, qualify_release and the three browser scripts never probe the engine, so a stopped Docker is reported as an image that 'is not built' or 'is not on this machine'. Reports differ in their trailing newline, their project field and their transport labels.
- **Why it matters:** Fixes to setup or to the ownership proof land in one copy at a time, and how trustworthy a cleanup case is depends on which copy a script inherited. Each new qualifier starts by pasting about 30 lines.
- **Recommendation:** Provide one context manager that owns the lifecycle and records both cleanup cases, checking every listing's exit code, plus one report writer that writes atomically and includes the trailing newline, fingerprint, schema and not_established list.
- **Rule check:** Infrastructure rule: distinct disposable projects and ownership guards come before cleanup. The shared manager keeps require_identity and require_labels before any removal and makes the cleanup listing stricter, never looser.
- **Verification:** revised. 13 qualifier skeletons confirmed (15 scripts create a disposable project; disposable_db and supabase_stack use their own stack classes, and local_backup's AppStack serves a restore), and 12 cleanup listings, of which only disposable_db.py checks exit codes. Noted that other_resources(project) on the next line raises Unavailable when Docker is unreachable, which narrows that risk.

```text
@contextmanager
def disposable_app_stack(root: Path, cases: Cases, *, extra_ports: int = 0, wait: int = 240,
                         services: Sequence[str] = ()) -> Iterator[StackRun]:
    # project, ports, AppStack, passwords, require_identity, docker info, render, images, before snapshot
    try: yield StackRun(stack, ports, base, runtime_url)
    finally: remove_stack(stack); record_cleanup(cases, project, before)   # Unavailable on a failed listing
def write_report(root: Path, path: Path, schema: str, cases: Cases, started_at: float,
                 not_established: Sequence[str], **extra: object) -> int
```

### <a id="scrp-08"></a>SCRP-08: Two unrelated Unavailable classes break the exit-code contract where scripts mix them

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [scripts/toolchain.py:78-79](../../../../scripts/toolchain.py#L78)
  - [scripts/disposable_db.py:52-57](../../../../scripts/disposable_db.py#L52)
  - [scripts/qualify_identity.py:255](../../../../scripts/qualify_identity.py#L255): find_tools raises toolchain.Unavailable
  - [scripts/qualify_identity.py:742-750](../../../../scripts/qualify_identity.py#L742): catches only disposable_db.Unavailable
  - [scripts/qualify_release.py:155-156](../../../../scripts/qualify_release.py#L155)
  - [scripts/qualify_release.py:361-385](../../../../scripts/qualify_release.py#L361): the miss skips setting stopped, then the report is written
  - [scripts/persistent_install.py:706-717](../../../../scripts/persistent_install.py#L706): screens: the same mismatch
  - [scripts/qualify_github_connector.py:118-119](../../../../scripts/qualify_github_connector.py#L118): a second Refused class, mapped to exit 2
- **Evidence:** toolchain.Unavailable and disposable_db.Unavailable are separate classes. qualify_identity, qualify_release and persistent_install import the second but call find_tools and qualify_web.wait_until_up, which raise the first, so their `except Unavailable` never matches. In qualify_release the miss also skips `stopped = str(error)`, so the finally block writes report.json with 'stopped': '' and then the traceback follows. Refusals disagree too: persistent_install raises Refused for a missing --paid and exits 1 (lines 794-798), live_goal and qualify_release print REFUSED for the same missing flag and exit 2, and qualify_github_connector defines its own Refused for a missing prerequisite and maps it to 2. evidence.py record indexes a hand-written plan's keys directly (plan['profiles'], plan['runbook'], plan['retention'], lines 392-413), so a missing key ends in a traceback with exit 1 ('not complete') rather than 2 ('unusable request').
- **Why it matters:** A web server that never answers or a missing pinned tool is reported as a failed check (exit 1) instead of an unavailable prerequisite (exit 2), and verify.py and readers treat those differently. The identity report is lost, because it was deleted at the start. A paid-run report can say it stopped for no reason.
- **Recommendation:** Define Refused and Unavailable once, in harness_lib or a small errors module, and import them everywhere, including toolchain and qualify_github_connector. Give every CLI one wrapper that maps Refused to 1, Unavailable to 2 and anything else to 1 with a short message, and document once which code a paid script's missing --paid flag uses. Validate the shapes of the plan and install.json at the top of their commands.
- **Rule check:** AGENTS.md Commands: exit 0 passed, 1 a check failed, 2 a prerequisite is unavailable. The change restores that mapping and does not change any refusal condition.
- **Verification:** revised. Both Unavailable classes and the three mixing scripts confirmed: find_tools and wait_until_up raise toolchain.Unavailable, which the except clauses in qualify_identity, qualify_release and persistent_install never match. The Refused comparison is restated as the concrete missing --paid case.

```text
# scripts/errors.py (stdlib only)
class Refused(Exception): exit_code = 1
class Unavailable(Exception): exit_code = 2
def cli(main: Callable[[], int]) -> int   # prints 'REFUSED before any change: ...' or 'ERROR: ...'
# toolchain.py, disposable_db.py, qualify_github_connector.py: from errors import Refused, Unavailable
```

### <a id="scrp-09"></a>SCRP-09: Arrangements whose failures are never checked let qualifier cases pass vacuously

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** medium · **Occurrences** 36
- **Where:**
  - [scripts/qualify_identity.py:93-101](../../../../scripts/qualify_identity.py#L93): canary result discarded; the denial cases after it pass either way
  - [scripts/qualify_identity.py:104-107](../../../../scripts/qualify_identity.py#L104): a conjunct computed over 'where false'
  - [scripts/app_db.py:344-345](../../../../scripts/app_db.py#L344): escaped backslash-n in SQL and in the child's stdin
  - [scripts/qualify_identity.py:272](../../../../scripts/qualify_identity.py#L272): literal backslash-n appended to the arranged key in .env.local
  - [scripts/qualify_identity.py:275-277](../../../../scripts/qualify_identity.py#L275): escaped backslash-n in SQL, result discarded
  - [scripts/qualify_identity.py:461](../../../../scripts/qualify_identity.py#L461): the same on the member insert
  - [scripts/qualify_upgrade.py:207](../../../../scripts/qualify_upgrade.py#L207): arrangement result discarded
  - [scripts/qualify_upgrade.py:217](../../../../scripts/qualify_upgrade.py#L217): cleanup result discarded
- **Evidence:** 33 statement-level stack.sql, runtime or migrator calls in 7 files discard their result, arrangements and cleanups alike, 16 of them in qualify_identity.py (counted with an ast walk). If the canary tables at qualify_identity.py:93 fail to create, the PostgREST cases that follow still pass, because a missing table is also a 4xx. Six string literals double the backslash before n, so they write a literal backslash-n where a newline was meant: four SQL strings (psql runs the statement at its semicolon, then rejects an unknown meta-command, and the result is ignored), the arranged OPENROUTER_API_KEY line in .env.local, and the child's stdin at app_db.py:345, which works only because communicate() then closes stdin. qualify_identity.py:104 then asserts on a query that cannot return anything but 0:

  ```python
      grants = rows(stack, "select count(*) from information_schema.role_usage_grants where false;")
  ```
- **Why it matters:** A broken arrangement shows up as a confusing downstream failure or not at all, and a disposable 'passed' case can rest on a fixture that never existed.
- **Recommendation:** Route every arrangement through a helper that records 'arranged: &lt;label>' as a case, or raises Unavailable, when it fails, as qualify_identity.py:204-226 already does for the schema states. Replace the escaped sequences with real newlines and drop the vacuous query. Add a SQL literal helper for interpolated values, which are quoted by hand in only two places today (persistent_install.py:522 and 603).
- **Rule check:** AGENTS.md completion evidence: skipped tests or templates never count as passing. DH-07: synthetic fixtures in disposable environments only. Recording arrangements makes failures visible and touches no persistent target.
- **Verification:** revised. 33 discarded calls recounted with ast, the six doubled backslash-n literals and the always-zero query confirmed. The evidence now says the count includes cleanups, and the recommendation points at the schema-state block that already records its arrangement. psql's handling of the stray meta-command is inferred, not run.

```text
def arrange(cases: Cases, label: str, result: CompletedProcess[str]) -> bool:
    cases.check(f'arranged: {label}', 'exit 0', f'exit {result.returncode}: {result.stderr[-200:]}', result.returncode == 0)
    return result.returncode == 0
def sql_literal(value: str) -> str: ...   # wrap in single quotes, doubling any inside
```

### <a id="scrp-10"></a>SCRP-10: Case records and qualification reports are untyped dicts whose vocabulary drifts

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** low · **Occurrences** 8
- **Where:**
  - [scripts/evidence.py:27-28](../../../../scripts/evidence.py#L27): the only definition of classes and transports
  - [scripts/verify.py:34-40](../../../../scripts/verify.py#L34): STEP_CLASSES written as free strings
  - [scripts/disposable_db.py:337-349](../../../../scripts/disposable_db.py#L337): Cases writes {'status': ...} records
  - [scripts/qualify_operations.py:35-37](../../../../scripts/qualify_operations.py#L35): Checks defaults every case to transport 'none'
  - [scripts/qualify_worker_inference.py:460-468](../../../../scripts/qualify_worker_inference.py#L460): positional relabel, then 'fake' at report level
  - [scripts/live_goal.py:84](../../../../scripts/live_goal.py#L84): 'live OpenRouter'
  - [scripts/qualify_browser_executor.py:98-103](../../../../scripts/qualify_browser_executor.py#L98): report the service reads at runtime
  - [services/agent/src/autobots/adapters/browser_executor.py:489-500](../../../../services/agent/src/autobots/adapters/browser_executor.py#L489): executor_qualified() reads that report with .get()
- **Evidence:** The allowed classes and transports are defined only in evidence.py (CLASSES, TRANSPORTS). Qualifier reports use other words or keys: 'model_transport': 'fake' (qualify_worker_inference.py:468), 'live OpenRouter' (live_goal.py:84, persistent_install.py:347 and 560), 'scripted, over a fake HTTP transport' (qualify_mac_sleep.py:64), 'model': 'scripted, no provider' (qualify_browse_goal.py:104), and 'evidence_class' (qualify_release.py:105, qualify_github_connector.py:109). Checks() gives every operations, backup and upgrade case the transport 'none', although their fixture workers run a scripted model and verify.py classes those steps ('disposable', 'mock'). qualify_worker_inference relabels by position:

  ```python
  for record in cases.records[:-2]:
      record['model_transport'] = 'mock'
  ```

  Children report {'passed': bool} while parents record {'status': 'passed'}. The executor report is read by the service's executor_qualified() with no shared schema.
- **Why it matters:** Evidence readers cannot rely on one vocabulary, and a mislabelled transport is exactly the confusion DH-09.2 forbids. A renamed key or case id in the executor report would silently disable browsing (it fails closed), and nothing links its writer to its reader.
- **Recommendation:** Define the vocabulary and record shapes once and type them: Literal aliases for class and transport, and TypedDicts for a case record, a child report and a qualification report, used by Cases, verify.STEP_CLASSES and evidence.py. Give Cases its transport at construction instead of relabelling by position. Add a harness test that round-trips a report written by the qualifier's writer through executor_qualified() with REQUIRED_CASES.
- **Rule check:** DH-09.2 class and model-transport vocabulary, which docs/engineering/evidence/README.md extends with local_runtime. The change narrows free text to that vocabulary and touches only script records, not DTO, row or UI types.
- **Verification:** confirmed. Cases defaults to 'none' (disposable_db.py:338), Checks inherits it, verify.py classes the operations, backup, upgrade and app_db steps as 'mock', and qualify_worker_inference relabels all but the last two records. The service's own tests build an executor report from REQUIRED_CASES, but nothing ties the qualifier that writes it to that list.

```text
VerificationClass = Literal['static', 'mock', 'disposable', 'local_runtime', 'live']
ModelTransport = Literal['none', 'mock', 'openrouter_live']
CaseRecord = TypedDict('CaseRecord', {'id': str, 'class': VerificationClass, 'model_transport': ModelTransport,
                                      'expected': str, 'observed': str, 'status': Literal['passed', 'failed']})
class ChildCase(TypedDict): id: str; expected: str; observed: str; passed: bool
class QualificationReport(TypedDict): schema_version: str; status: str; cases: list[CaseRecord]; not_established: list[str]
```

### <a id="scrp-12"></a>SCRP-12: harness_lib is a grab bag, and each profile's checks are registered in five places

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 5
- **Where:**
  - [scripts/harness_lib.py:55-67](../../../../scripts/harness_lib.py#L55): DB_CHECK_FILES, DB_CHECKS, OPERATIONS_CHECKS
  - [scripts/verify.py:30-40](../../../../scripts/verify.py#L30): SELF_REPORTING_STEPS and STEP_CLASSES
  - [scripts/verify.py:132-143](../../../../scripts/verify.py#L132): the db and operations steps in tool_plan
  - [scripts/verify.py:223-229](../../../../scripts/verify.py#L223): scope and not_tested per profile
  - [scripts/harness_lib.py:160-165](../../../../scripts/harness_lib.py#L160): read_report
  - [scripts/harness_lib.py:193-200](../../../../scripts/harness_lib.py#L193): report_state reads the same file again itself
  - [scripts/harness_lib.py:230-231](../../../../scripts/harness_lib.py#L230): fingerprint and input_manifest walk the tree twice
  - [tests/harness/test_final_review.py:64-71](../../../../tests/harness/test_final_review.py#L64): tests that compare the registry's copies
- **Evidence:** harness_lib (520 lines, imported by 23 scripts and the hook) holds environment reduction, the input manifest, check-domain routing, report and evidence state, configuration validation and the Claude version probe. Adding a db qualifier means editing DB_CHECKS and DB_CHECK_FILES (harness_lib.py:55 and 65) and SELF_REPORTING_STEPS, STEP_CLASSES and tool_plan (verify.py:31, 38 and 136), plus the scope and not_tested dicts; 'identity_qualification' appears in all five places. Tests compare tool_plan with DB_CHECKS and OPERATIONS_CHECKS, and check two STEP_CLASSES entries. report_state reads the report itself instead of calling read_report, and it computes the manifest twice. Measured for this review, one evidence_state call computed the 723-file manifest 8 times at 0.11 to 0.16 s each, inside the hook's 9 s deadline.
- **Why it matters:** A step added in one place and missed in another changes what 'passed' means for a profile, and only tests that compare the copies notice. The hook's Stop path pays for repeated hashing that grows with the repository.
- **Recommendation:** Split harness_lib into focused modules behind the same import names, or keep it as a facade. Describe each profile once as data, with steps that carry id, argv, timeout, class, transport and self-reporting, and let verify.tool_plan, report_state and evidence consume it. Compute the manifest once per evaluation and pass it down.
- **Rule check:** DH-05: the hook stays a thin adapter and substantive checks live in repository scripts. DH-09.2 statuses are unchanged, and a single registry removes drift without removing any required check.
- **Verification:** confirmed. 'identity_qualification' sits in five registries (harness_lib.py:55 and 65, verify.py:31, 38 and 136). Re-measured one evidence_state call: 8 manifest computations of 723 files, 0.10 to 0.20 s each, about 0.95 s in all.

```text
@dataclass(frozen=True)
class CheckStep: id: str; argv: tuple[str, ...]; timeout: float; klass: VerificationClass; transport: ModelTransport; self_reporting: bool
@dataclass(frozen=True)
class Profile: steps: tuple[CheckStep, ...]; scope: str; not_tested: tuple[str, ...]
PROFILES: dict[str, Profile] = {'db': Profile(steps=(CheckStep('identity_qualification', ...), ...), ...)}
# scripts/harness/: manifest.py, domains.py, reports.py, config_check.py, adapter.py (harness_lib re-exports)
def evidence_state(root: Path, manifest: dict[str, str] | None = None) -> tuple[bool, str]
```

### <a id="scrp-15"></a>SCRP-15: scripts/ is a flat mix of entry points and libraries, without the scripts/db/ that DH-03 lays out

- **Severity** medium · **Dimension** structure · **Effort** L · **Risk** medium · **Occurrences** 1
- **Where:**
  - [PRD-Development-Harness.md:54](../../../PRD/PRD-Development-Harness.md#L54): DH-03: scripts/db/ for target-checked migration and seed operations
  - [scripts/disposable_db.py:622-656](../../../../scripts/disposable_db.py#L622): a CLI inside a module 16 scripts import
  - [scripts/app_db.py:705-717](../../../../scripts/app_db.py#L705): a CLI inside a module 14 scripts import
  - [scripts/supabase_stack.py:331-352](../../../../scripts/supabase_stack.py#L331)
  - [scripts/qualify_identity.py:742-750](../../../../scripts/qualify_identity.py#L742): a qualifier that 7 scripts import
  - [scripts/harness_lib.py:29-35](../../../../scripts/harness_lib.py#L29): ALLOWED_LINK_PATHS pins the entry-point paths
- **Evidence:** 28 modules sit side by side: harness entry points (verify, specs, evidence, toolchain, generate_contracts), plain libraries (harness_lib, release_scoring), libraries that are also CLIs (disposable_db, supabase_stack and app_db, imported by 16, 15 and 14 scripts, plus qualify_identity and qualify_operations), 13 qualify_ scripts of different kinds (disposable, mock, local runtime and paid), paid trials (live_goal, browse_trial, qualify_release and parts of persistent_install) and a shell helper (tool_keys_env). Only the qualify_ prefix and the docstrings tell them apart. DH-03 places target-checked migration and seed operations under scripts/db/, which does not exist.
- **Why it matters:** Nothing in the layout says which modules are safe to import, which spend money and which touch the persistent install, so new code lands next to whatever file it was copied from.
- **Recommendation:** Keep entry-point paths stable, because AGENTS.md, rule links, settings, runbooks and tests name them. Move shared code into packages: scripts/qualification/ for the disposable-run library, and scripts/db/ for target-checked migration and seed operations as DH-03 lays out, with thin compatibility shims. Mark paid entry points in one place, such as a PAID_SCRIPTS list that a harness test checks for a --paid refusal.
- **Rule check:** DH-03 lists scripts/db/ for target-checked migration and seed operations. harness_lib.ALLOWED_LINK_PATHS and AGENTS.md name scripts/verify.py and scripts/specs.py, so those entry points stay where they are. infrastructure.md's paths frontmatter names scripts/persistent_install.py and scripts/local_backup.py, so any move updates those globs and the harness tests that pin them.
- **Verification:** revised. DH-03's scripts/db/ (PRD-Development-Harness.md:54), the fan-in figures and ALLOWED_LINK_PATHS confirmed. The 13 qualify_ scripts are not all disposable (qualify_faults is mock, qualify_web local runtime, qualify_release paid), and the rule check now names the infrastructure.md globs a move must carry.

```text
scripts/
  verify.py specs.py evidence.py toolchain.py generate_contracts.py   # unchanged entry points
  harness/        manifest.py domains.py reports.py config_check.py adapter.py   (harness_lib re-exports)
  qualification/  stack.py children.py cases.py report.py owners.py ops.py net.py paid_run.py
  db/             disposable.py app.py supabase_stack.py persistent_apply.py   (DH-03)
  qualify_*.py    thin entry points: scenarios only
```

### <a id="scrp-11"></a>SCRP-11: config_errors validates six concerns in 91 lines, and its early returns drop errors

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [scripts/harness_lib.py:250-340](../../../../scripts/harness_lib.py#L250): config_errors
  - [scripts/harness_lib.py:264-266](../../../../scripts/harness_lib.py#L264): returns a fresh list, dropping errors already collected
  - [scripts/harness_lib.py:278-280](../../../../scripts/harness_lib.py#L278): returns early, skipping the asset, rule-link and AGENTS checks
  - [scripts/harness_lib.py:284-320](../../../../scripts/harness_lib.py#L284): event, group and handler checks nested five levels deep
- **Evidence:** One function reads both configuration files, then checks the interpreter, the document map, the settings keys, every hook event, group and handler (nested five levels deep), and skill and agent frontmatter, before calling the rule-link and AGENTS checks. A non-object `documents` returns a fresh list, discarding the activation and interpreter errors collected so far:

  ```python
  documents = config.get('documents')
  if not isinstance(documents, dict):
      return ['Document mappings must be an object.']
  ```

  A non-object `hooks` returns early and skips the frontmatter, rule-link and AGENTS checks.
- **Why it matters:** project_configuration is the harness gate that the hook and every profile rely on. Incomplete diagnostics turn one fix into several runs, and every new rule lengthens a function whose sections cannot be tested separately.
- **Recommendation:** Split it into independent validators that each return a list, and concatenate their results, so a malformed section never hides another.
- **Rule check:** AGENTS.md rule-check table: project_configuration in verify.py checks .claude/settings.json and the hook configuration CLAUDE.md describes. The split keeps every check and only stops early returns from hiding others.
- **Verification:** revised. Both early returns (harness_lib.py:264-266 and 278-280) and the 91-line span confirmed. Lowered to low: the lost diagnostics appear only with a malformed documents or hooks section, and the rest is size.

```text
def config_errors(root: Path) -> list[str]:
    config, settings, errors = load_config(root)          # unreadable or non-object -> errors
    return [*errors, *activation_errors(config), *interpreter_errors(config), *document_errors(root, config),
            *hook_errors(settings, interpreter=config.get('python_executable')),
            *asset_frontmatter_errors(root), *rule_link_errors(root), *agents_mapping_errors(root)]
def hook_errors(settings: Mapping, interpreter: object) -> list[str]   # flat helpers per event, group and handler
```

### <a id="scrp-13"></a>SCRP-13: Secret-file names are listed three times, and the input manifest's list is the shortest

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [.claude/hooks/dispatch.py:38-43](../../../../.claude/hooks/dispatch.py#L38): is_secret
  - [.claude/hooks/dispatch.py:104-106](../../../../.claude/hooks/dispatch.py#L104): install directory paths
  - [.claude/hooks/dispatch.py:118-122](../../../../.claude/hooks/dispatch.py#L118): Bash patterns, another subset
  - [scripts/harness_lib.py:128-137](../../../../scripts/harness_lib.py#L128): is_non_input
  - [scripts/persistent_install.py:35](../../../../scripts/persistent_install.py#L35): DEFAULT_DIR, repeated as text in the hook
- **Evidence:** dispatch.is_secret treats stack.env, app.env, owner.env, master.key, provider-master.key, backup.key and .env* as secret. The Bash patterns repeat a different subset plus the install path. harness_lib.is_non_input excludes only .env* and provider-master.key from the input manifest:

  ```python
  secret = (path.name.startswith('.env') and not path.name.endswith('.example')) or path.name == 'provider-master.key'
  ```

  So a master.key, backup.key or stack.env placed under an input directory would be hashed into .checks/&lt;profile>/latest.json.
- **Why it matters:** The three lists can only drift further apart, and the manifest's list, the one that feeds .checks/&lt;profile>/latest.json, is the one that falls behind, contrary to DH-09.2's rule against hashing secrets. No such file sits under an input directory today, because the install and the master key live outside the repository.
- **Recommendation:** Define SECRET_FILE_NAMES, the install-directory markers and an is_secret_name() function once in harness_lib, which the hook already imports, and use them in is_secret, the Bash guard and is_non_input. Add a harness test that every listed name is both refused by the hook and absent from input_manifest.
- **Rule check:** DH-05 secret guard and DH-09.2 'exclude raw secrets entirely'. The union of today's lists is kept, so nothing the hook refuses today becomes allowed.
- **Verification:** revised. All three lists confirmed. Lowered to low: the named files live outside the repository today, and a hash would reach only the ignored per-profile report, since versioned evidence stores digests of the manifest.

```text
# harness_lib.py
SECRET_FILE_NAMES = frozenset({'stack.env', 'app.env', 'owner.env', 'master.key', 'provider-master.key', 'backup.key'})
INSTALL_MARKERS = ('application support/autobots/secrets', '.local/share/autobots-install/')
def is_secret_name(name: str) -> bool: ...   # casefolded; .env and .env.* except .example
```

### <a id="scrp-14"></a>SCRP-14: Small helpers are re-implemented per script, often under the same name with different behavior

- **Severity** low · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 23
- **Where:**
  - [scripts/disposable_db.py:281-291](../../../../scripts/disposable_db.py#L281): free_port scans the disposable range
  - [scripts/qualify_web.py:40-43](../../../../scripts/qualify_web.py#L40): free_port binds port 0; imported elsewhere as any_port
  - [scripts/disposable_db.py:352-354](../../../../scripts/disposable_db.py#L352): rows returns a string
  - [scripts/live_goal.py:43-46](../../../../scripts/live_goal.py#L43): rows returns a list of dicts
  - [scripts/disposable_db.py:304-313](../../../../scripts/disposable_db.py#L304): http, copy 1
  - [scripts/supabase_stack.py:196-207](../../../../scripts/supabase_stack.py#L196): http, copy 2, without redirects
  - [scripts/qualify_identity.py:40-45](../../../../scripts/qualify_identity.py#L40): http, copy 3
  - [scripts/app_db.py:66-69](../../../../scripts/app_db.py#L66): repeats Stack.as_role verbatim
- **Evidence:** 11 helper names are defined in two or three modules, 23 definitions in all. Some share a name but not a contract: free_port (a fixed range or any port), rows (a string or a list of JSON rows), require_rendered and rendered_refusals (disposable_db or supabase_stack), and identity_refusals (a disposable target or the install). Others are copied with the same contract: three http helpers, alongside api_call and http_json; b64 twice, with two HS256 signers (disposable_db.jwt and qualify_web.session_token); utc and the EXIT_* constants in both verify and toolchain; the PYTHON path constant in 7 modules, plus 20 inline literals in app_db; and executor_fingerprint, identical in two files. There are also three pollers (wait_for, an untyped wait and wait_until_up). AppStack.as_role repeats Stack.as_role (disposable_db.py:94-99) verbatim, beside two local variants that only add a setup prefix (app_db.py:227 and 258).
- **Why it matters:** Readers must check which free_port or rows a module imported, and fixes to redirects, timeouts or the comment explaining why both JWT claim settings are set reach only one copy.
- **Recommendation:** Collect these helpers in the shared library proposed in the modules finding, with distinct names (disposable_free_port and any_free_port, rows_text and rows_json). Give Stack.as_role an optional setup prefix and delete the three copies.
- **Rule check:** No rule names these helpers. Distinct names keep every contract, and the db and operations profiles cover the callers that move.
- **Verification:** revised. An ast walk finds 18 top-level names defined in more than one script; 11 of them are helpers rather than per-area case or entry functions, with 23 definitions. AppStack.as_role (app_db.py:66-69) overrides Stack.as_role with the same body. Lowered to low: each copy works, and the cost is in reading and in fixes that reach one copy.

```text
qualification/net.py   any_free_port(), disposable_free_port(excluded), http(method, url, headers, body, *, redirects=False)
qualification/jwt.py   b64url(data), hs256(secret, claims)
qualification/wait.py  poll(check: Callable[[], bool], seconds: float, interval: float = 0.5, ignore=(OSError,)) -> bool
Stack.as_role(self, role: str, user: str | None, statement: str, *, setup: str = '') -> CompletedProcess[str]
```

### <a id="scrp-16"></a>SCRP-16: Three ad hoc dotenv parsers ignore the quoting and export rules the app's own parser applies

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** medium · **Occurrences** 3
- **Where:**
  - [scripts/local_backup.py:159-165](../../../../scripts/local_backup.py#L159)
  - [scripts/persistent_install.py:77-83](../../../../scripts/persistent_install.py#L77): reads stack.env, app.env and owner.env
  - [scripts/supabase_stack.py:91-99](../../../../scripts/supabase_stack.py#L91)
  - [scripts/tool_keys_env.py:22](../../../../scripts/tool_keys_env.py#L22): already reuses the service parser
  - [services/agent/src/autobots/application/credentials/precedence.py:24-39](../../../../services/agent/src/autobots/application/credentials/precedence.py#L24)
- **Evidence:** parse_env and read_values are the same split-on-'=' loop, and example_defaults is a third. The service's parse_dotenv, which tool_keys_env.py and qualify_github_connector.py already reuse, strips `export`, matching quotes and trailing comments. read_values reads the persistent install's stack.env, app.env and owner.env.
- **Why it matters:** A quoted or exported value hand-edited into the install's env files would be read with its quotes by the install tooling and without them by the app.
- **Recommendation:** Use the service's parse_dotenv in local_backup and persistent_install, which already require the venv interpreter. Give scripts that run on the plain interpreter one stdlib copy in harness_lib that mirrors it, tested against the same fixtures.
- **Rule check:** Infrastructure rule: persistent configuration stays target-guarded, and parsing changes no guard. Secret values are never printed.
- **Verification:** confirmed. parse_env and read_values are the same loop and example_defaults a third; tool_keys_env.py and qualify_github_connector.py already import parse_dotenv. local_backup.py and persistent_install.py both document the venv interpreter, so the service parser is importable there.

### <a id="scrp-17"></a>SCRP-17: Six Python programs are passed as -c strings and import service internals out of sight

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 6
- **Where:**
  - [scripts/app_db.py:303-312](../../../../scripts/app_db.py#L303)
  - [scripts/supabase_stack.py:233-240](../../../../scripts/supabase_stack.py#L233)
  - [scripts/qualify_upgrade.py:120-126](../../../../scripts/qualify_upgrade.py#L120)
  - [scripts/qualify_upgrade.py:208-215](../../../../scripts/qualify_upgrade.py#L208): imports autobots.application.goal_loop.execution_block
  - [scripts/qualify_browse_goal.py:34-41](../../../../scripts/qualify_browse_goal.py#L34)
  - [scripts/qualify_browser_executor.py:34-41](../../../../scripts/qualify_browser_executor.py#L34): identical to the qualify_browse_goal copy
- **Evidence:** These strings import autobots.application.goal_loop.execution_block, autobots.adapters.browser_executor.images_fingerprint, langgraph's PostgresSaver and psycopg. executor_fingerprint is the same 8 lines in two files. No linter, type checker or usage search sees these programs, unlike the 67 Python files already kept in tests/db/.
- **Why it matters:** Renaming a service function breaks a qualifier, and that only shows up when Docker runs it.
- **Recommendation:** Move each program into tests/db/, or into the shared library, as a file with a main(), so tooling and the db domain see it, and share executor_fingerprint.
- **Rule check:** No rule governs this. Kept as files in tests/db, the probes fall under the db domain's change detection and the service's lint.
- **Verification:** revised. Six -c programs confirmed; executor_fingerprint is identical in qualify_browse_goal.py:34-41 and qualify_browser_executor.py:34-41. tests/db holds 67 Python files, not 30-odd.

### <a id="scrp-18"></a>SCRP-18: verify runs checks two ways, with different timeout semantics and record shapes

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [scripts/verify.py:61-76](../../../../scripts/verify.py#L61): run_check
  - [scripts/toolchain.py:229-256](../../../../scripts/toolchain.py#L229): run_step
  - [scripts/harness_lib.py:454-482](../../../../scripts/harness_lib.py#L454): a third copy of the process-group kill
  - [scripts/evidence.py:367](../../../../scripts/evidence.py#L367): papers over the two record shapes
- **Evidence:** run_check uses subprocess.run(timeout=60) without a process group, so a timed-out unittest run can leave its children behind, and it records 'command_argv' with full paths. run_step starts a new session, kills the whole group on timeout and records 'argv' with only the executable's basename. probe_version is a third copy of the group-kill logic. evidence.py accepts either shape: `check.get('command_argv') or check.get('argv')`.
- **Why it matters:** Harness checks and toolchain checks in the same report behave differently on timeout and look different to every reader.
- **Recommendation:** Move the group-kill runner into harness_lib, the lower layer, and have run_check, run_step and probe_version all use it with one record shape.
- **Rule check:** DH-05 asks for deadlines and bounded output, and DH-09.2 for argv recorded per check. One runner satisfies both consistently.
- **Verification:** confirmed. run_check (subprocess.run with a 60 s timeout and no process group, full argv as command_argv), run_step (a new session, killpg, basename argv) and probe_version confirmed; evidence.py:367 reads either key.

### <a id="scrp-19"></a>SCRP-19: Schema facts are hard-coded where they will go stale

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 4
- **Where:**
  - [scripts/app_db.py:114-123](../../../../scripts/app_db.py#L114): reset lists all 24 public tables on one 578-character line
  - [scripts/qualify_upgrade.py:84](../../../../scripts/qualify_upgrade.py#L84): applied >= 24
  - [scripts/qualify_upgrade.py:151-153](../../../../scripts/qualify_upgrade.py#L151): cut at the literal '20261105000024_'
  - [scripts/app_db.py:522](../../../../scripts/app_db.py#L522): Path(\_\_file\_\_) instead of root / MIGRATIONS
- **Evidence:** The reset list matches the 24 tables created in supabase/migrations today (compared for this review), so every new public table must also be added to that line, or the upgrade case's reset will leave it behind. qualify_upgrade asserts at least 24 prior migrations and cuts its broken copy at a literal file name.
- **Why it matters:** These checks pass today and will fail confusingly later, far from the migration that caused the failure.
- **Recommendation:** Derive the drop list from the catalog (tables and functions in public owned by autobots_migrator), name the prior-release facts as constants next to PRIOR_REVISION, and use root / MIGRATIONS consistently.
- **Rule check:** AGENTS.md: no persistent reset. reset() is disposable-only behind require_marker, which stays, and no migration is edited.
- **Verification:** confirmed. The drop list holds 23 tables on line 117 and public.workspaces on line 118, the 24 public tables the migrations create; `applied >= 24`, the literal cut and the Path(\_\_file\_\_) lookup confirmed.

### <a id="scrp-20"></a>SCRP-20: specs.py validate_story fills in the Story while validating it, and fence parsing exists twice

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [scripts/specs.py:274-354](../../../../scripts/specs.py#L274): validate_story, 81 lines
  - [scripts/specs.py:301](../../../../scripts/specs.py#L301): sets status as a side effect
  - [scripts/specs.py:324-325](../../../../scripts/specs.py#L324): sets dependencies and qualified_dependency
  - [scripts/specs.py:247-249](../../../../scripts/specs.py#L247): closure inside the block loop (ruff B023)
  - [scripts/specs.py:98-132](../../../../scripts/specs.py#L98): outside_fences and fenced_blocks
  - [scripts/harness_lib.py:365-378](../../../../scripts/harness_lib.py#L365): unfenced_lines, with the same FENCE regex
- **Evidence:** validate_story sets story.status, dependencies, qualified_dependency, tasks and unresolved_questions as side effects of validation, so parse_document's dependency checks and promote depend on validation having run first. The closing-fence rule (`match[1][0] == opening[0] and len(match[1]) >= len(opening) and not match[2].strip()`) is written three times, in specs.py outside_fences and fenced_blocks and in harness_lib.unfenced_lines, with the same FENCE regex in both modules.
- **Why it matters:** This parser decides story status and promotion. Separating parsing from validation makes promote testable on its own, and one fence parser keeps SPECS parsing and rule-link checking in agreement.
- **Recommendation:** Split field parsing (sections into typed Story fields) from validation (issues), and move the fence and link Markdown helpers into one stdlib module that both use.
- **Rule check:** AGENTS.md: render changes only generated navigation. Validate, render and promote behavior must stay identical, as the 41 tests in tests/harness/test_specs.py check.
- **Verification:** confirmed. The side effects at specs.py:301, 324-325, 333 and 338, ruff's B023 at line 248 and the three copies of the closing-fence rule with two copies of FENCE confirmed.

### <a id="scrp-21"></a>SCRP-21: specs.py's module docstring understates what the tool writes

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [scripts/specs.py:1-8](../../../../scripts/specs.py#L1)
  - [scripts/specs.py:551-562](../../../../scripts/specs.py#L551): promote_text rewrites story Status lines
- **Evidence:** The docstring says rendering 'owns only the three navigation sections preceding Product Context, never story content', but the promote command rewrites story Status lines from BLOCKED to READY. Elsewhere in this area, module docstrings are accurate and state exit codes and limits.
- **Why it matters:** The docstring is what a reviewer reads to judge a tool's write scope, and promote is the one command that edits story content.
- **Recommendation:** Add promote to the docstring: it rewrites only a promotable story's Status line, under the rule in .claude/rules/ohmyorch-delivery.md.
- **Rule check:** .claude/rules/ohmyorch-delivery.md: promote moves BLOCKED to READY only when every dependency is DONE. Documenting that does not change it.
- **Verification:** confirmed. The docstring covers validation and rendering only, while promote_text (specs.py:551-562) rewrites story Status lines.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| None | | Every finding was kept. Corrections are recorded on each revised finding. |

## Not covered

mypy was not run, because it is not among the permitted read-only commands, so the type findings rest on reading the code rather than on checker output. No qualifier, profile or paid script was executed. Docker-backed behavior is inferred from the code and from documented tool behavior, not observed: this includes psql's handling of the stray backslash-n meta-command and the PostgREST status codes in the canary cases. Files outside this area were read only in part, where they test or are called by these scripts: tests/harness/test_final_review.py lines 52-110, test_hooks.py lines 395-410, test_verify_profiles.py lines 198-222, the stdin handling in tests/db/credential_store_check.py, services/agent's parse_dotenv and executor_qualified, and the ruff and mypy sections of services/agent/pyproject.toml. Other areas own those files. PRD-Development-Harness.md was read for DH-03 through DH-09.2 only, and metrics.md for its Python sections only. The Makefile wrapper around persistent_install.py and the runbooks were not reviewed. Measurements made for this review: ruff with the service configuration in check mode (outputs in .checks/reviews/review-2026-11-12-09-52-30/scripts/), plus an ast import-closure walk and a timed harness_lib.evidence_state call. Those two ran as read-only python3.12 -I scripts kept in the session scratchpad, outside the repository.

Verification re-ran `ruff format --check --no-cache` with the service configuration, recounted with grep and Python ast walks (fan-in, the db import closure, function spans, discarded results, duplicate helper names) and re-timed one evidence_state call, all as `python3.12 -I` scratch scripts outside the repository. No qualifier, profile, Docker command or paid script was run, and mypy was not run.
