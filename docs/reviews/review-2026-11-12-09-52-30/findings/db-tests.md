# Tests: database, worker and fault checks

This area holds the repository's strongest behavioral evidence in its least maintained code. tests/db has 75 files and 10,793 lines: 43 scripts that print JSON cases for scripts/app_db.py and the scripts/qualify_*.py qualifiers, plus the workers they kill, browser-suite arrangements, scripted models and the SQL fixtures for two disposable stacks. tests/web, tests/qualification and tests/faults add fixture servers, workers and deliberate-fault samples. What the checks exercise is excellent: real Postgres through the runtime role, real Storage with member tokens, real SIGKILL and SIGSTOP at chosen points, scripted models over fake transports, and leak scans of stored state and logs. How they are built is weak. No shared check module exists, so the case protocol and setup are copied: 42 check() copies in 6 variants, 24 value() helpers and 39 inline statements that release every job in the database. Mains run 150 to 316 lines, one exception skips every later scenario, and 26 of the 43 scripts then print nothing. 14 files depend on 21 private product names in a folder that no linter, formatter or type checker reads. 80 checks compute the shown value and the verdict with separate calls, and with one arrangement that never isolates its guard, three claim cases can pass with the guard they test broken. Comments, docstrings and case names are a model for the rest of the repository. A small shared check module, a lint and type gate for tests/, and public names for the private helpers would make this evidence cheap to keep. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 2 | No lint, format or type gate covers these files: 72 files would be reformatted, with 2,759 long lines and 307 suppressions for tools that never run here. |
| modules | 2 | No shared check module; 14 files bind to 21 private product names, and an install helper for the real key lives in tests/db. |
| size | 2 | 35 functions run over 80 lines, 19 over 150 and 10 over 200; most are mains made of long scenario lists. |
| functions | 2 | Each main arranges, acts, asserts and emits browser state in one body, and each file recreates its closures over db; the small helpers are clear. |
| structure | 2 | 75 files share one flat folder across six roles, and the _check, _live, _worker and _script suffixes don't reliably name the role. |
| approach | 3 | Real stores, processes, scripted models and fake transports are right; isolating checks by ending every job, and a hand-rolled JSON protocol in every file, are not. |
| comments | 4 | Every file states its story, decision and scope, and 'Arranged' marks constructed preconditions; review IDs lack their source path. |
| types | 2 | No type checker runs; value() returns Any, and SimpleNamespace stand-ins and 10 type: ignore comments appear, three hiding values the product types forbid. |
| errors | 2 | 26 of 43 scripts drop observed cases on a crash, one exception skips every later scenario, and some refusal checks accept any exception. |
| tests | 3 | The riskiest behavior (fencing, crashes, reconciliation, leakage) is exercised for real, but 80 checks evaluate twice and three claim cases can pass when broken. |
| maintainability | 2 | Valuable, well-explained evidence sits in copy-pasted, unlinted 200 to 300 line scripts tied to private internals. |

## Strengths

- **Real crashes at chosen points.** tests/db/assignment_worker.py:21-30, tests/db/effect_tools.py:42-43, tests/db/worker_process.py:21-23 and tests/db/workflow_worker.py:22-24 SIGKILL a real worker inside a model call, after an effect or after a commit. tests/db/recovery_check.py:262-281 stops one with SIGSTOP past its lease. The parents then check exit -9, fencing and no repeated effect (tests/db/goal_loop_check.py:194-217, tests/db/worker_ownership_check.py:186-213), as .claude/rules/python-worker.md asks. Sources: [tests/db/assignment_worker.py:21-30](../../../../tests/db/assignment_worker.py#L21), [tests/db/effect_tools.py:42-43](../../../../tests/db/effect_tools.py#L42), [tests/db/worker_process.py:21-23](../../../../tests/db/worker_process.py#L21), [tests/db/workflow_worker.py:22-24](../../../../tests/db/workflow_worker.py#L22), [tests/db/recovery_check.py:262-281](../../../../tests/db/recovery_check.py#L262), [tests/db/goal_loop_check.py:194-217](../../../../tests/db/goal_loop_check.py#L194), [tests/db/worker_ownership_check.py:186-213](../../../../tests/db/worker_ownership_check.py#L186).
- **One shared scripted model, with a planted key.** tests/db/goal_loop_script.py:17-39 is the one fixture the checks really share, built 68 times across the folder. It holds a planted api_key (line 20), so tests/db/goal_loop_check.py:81-85 can prove a client key never reaches checkpoint tables. tests/db/stream_script.py extends it for streaming. Sources: [tests/db/goal_loop_script.py:17-39](../../../../tests/db/goal_loop_script.py#L17), [tests/db/goal_loop_script.py:20](../../../../tests/db/goal_loop_script.py#L20), [tests/db/goal_loop_check.py:81-85](../../../../tests/db/goal_loop_check.py#L81), [tests/db/stream_script.py:1](../../../../tests/db/stream_script.py#L1).
- **Leak scans of stored state and of the check's own output.** tests/db/keys_and_vars_check.py:276-298 and tests/db/tool_keys_check.py:304-338 scan durable rows, log lines and ciphertext for every fixture token, name fixtures without their values (tool_keys_check.py:74-83), and refuse to print if a fixture secret reached the output. Sources: [tests/db/keys_and_vars_check.py:276-298](../../../../tests/db/keys_and_vars_check.py#L276), [tests/db/tool_keys_check.py:304-338](../../../../tests/db/tool_keys_check.py#L304), [tests/db/tool_keys_check.py:74-83](../../../../tests/db/tool_keys_check.py#L74).
- **Authorization through real member tokens.** tests/db/artifact_check.py:43-50 and 121-128 query PostgREST and Storage as members of two workspaces instead of the service role, which DH-07 requires for RLS evidence. Sources: [tests/db/artifact_check.py:43-50](../../../../tests/db/artifact_check.py#L43), [tests/db/artifact_check.py:121-128](../../../../tests/db/artifact_check.py#L121).
- **Readable evidence vocabulary.** Every module docstring names its story or decision (tests/db/cronjob_check.py:1-2, tests/db/browse_goal_check.py:1-5). Case IDs are behavior sentences with expected text, and 'Arranged:' marks preconditions built by hand rather than reached (tests/db/approval_check.py:237, tests/db/goal_loop_check.py:201, tests/db/upgrade_check.py:150). Sources: [tests/db/cronjob_check.py:1-2](../../../../tests/db/cronjob_check.py#L1), [tests/db/browse_goal_check.py:1-5](../../../../tests/db/browse_goal_check.py#L1), [tests/db/approval_check.py:237](../../../../tests/db/approval_check.py#L237), [tests/db/goal_loop_check.py:201](../../../../tests/db/goal_loop_check.py#L201), [tests/db/upgrade_check.py:150](../../../../tests/db/upgrade_check.py#L150).
- **A phase-split check to copy.** tests/db/browser_executor_check.py:85, 205, 237 and 304 split the work into containment, isolation and ownership functions. Each removes its containers in finally (175-177, 233-234). It is the shape the long mains elsewhere should take. Sources: [tests/db/browser_executor_check.py:85](../../../../tests/db/browser_executor_check.py#L85), [tests/db/browser_executor_check.py:205](../../../../tests/db/browser_executor_check.py#L205), [tests/db/browser_executor_check.py:237](../../../../tests/db/browser_executor_check.py#L237), [tests/db/browser_executor_check.py:304](../../../../tests/db/browser_executor_check.py#L304), [tests/db/browser_executor_check.py:175-177](../../../../tests/db/browser_executor_check.py#L175), [tests/db/browser_executor_check.py:233-234](../../../../tests/db/browser_executor_check.py#L233).
- **A network guard that proves itself.** tests/db/product_inference_worker.py:39-70 refuses non-loopback lookups and connections with getaddrinfo and an audit hook. Before the product starts, leave_on_purpose (214-226) sends three stray requests, so the record shows the guard saw them. Sources: [tests/db/product_inference_worker.py:39-70](../../../../tests/db/product_inference_worker.py#L39), [tests/db/product_inference_worker.py:214-226](../../../../tests/db/product_inference_worker.py#L214).
- **Targeted claims without global cleanup.** tests/db/task_timing_check.py:72 and 86 claim only their own run with claim_run, which scripts/qualify_identity.py:170 relies on. tests/db/review_check.py:98 and tests/db/browser_runs.py:53 do the same; this is the pattern to spread. Sources: [tests/db/task_timing_check.py:72](../../../../tests/db/task_timing_check.py#L72), [tests/db/task_timing_check.py:86](../../../../tests/db/task_timing_check.py#L86), [scripts/qualify_identity.py:170](../../../../scripts/qualify_identity.py#L170), [tests/db/review_check.py:98](../../../../tests/db/review_check.py#L98), [tests/db/browser_runs.py:53](../../../../tests/db/browser_runs.py#L53).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [TDBC-01](#tdbc-01) | high | tests | Checks compute the shown value and the verdict with separate calls, so some can pass broken | S | low |
| [TDBC-02](#tdbc-02) | high | modules | Db checks import and patch 21 private product names that no fast check reads | M | medium |
| [TDBC-03](#tdbc-03) | high | duplication | No shared check module: the case protocol and setup are copied into every script | M | low |
| [TDBC-04](#tdbc-04) | medium | errors | A crash ends every later scenario, and 26 of 43 scripts then print nothing | S | low |
| [TDBC-05](#tdbc-05) | medium | approach | Checks end every job in the database so claim_next picks their own run | M | medium |
| [TDBC-06](#tdbc-06) | medium | size | Check mains are 150 to 316 line scenario lists | L | medium |
| [TDBC-07](#tdbc-07) | medium | errors | Refusal checks accept any exception as the expected refusal | S | low |
| [TDBC-08](#tdbc-08) | medium | standards | No lint, format or type gate covers tests/db, tests/web or tests/qualification, yet the code carries 307 suppressions | M | low |
| [TDBC-09](#tdbc-09) | medium | structure | tests/db mixes six kinds of file, and the suffixes don't say which | M | medium |
| [TDBC-10](#tdbc-10) | medium | functions | Checks also arrange browser-suite state and run static scans | M | medium |
| [TDBC-11](#tdbc-11) | medium | modules | An install helper that handles the real OpenRouter key lives in tests/db | S | medium |
| [TDBC-12](#tdbc-12) | low | types | type: ignore replaces annotations and hides values the product types forbid | S | low |
| [TDBC-13](#tdbc-13) | low | tests | Patched product globals and scratch keys aren't always cleaned up | S | low |
| [TDBC-14](#tdbc-14) | low | naming | Files named after review rounds hide which behavior they test | S | low |
| [TDBC-15](#tdbc-15) | low | naming | Goal text is an untyped command channel to fixture models | S | low |

### <a id="tdbc-01"></a>TDBC-01: Checks compute the shown value and the verdict with separate calls, so some can pass broken

- **Severity** high · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 80
- **Where:**
  - [tests/db/worker_ownership_check.py:144](../../../../tests/db/worker_ownership_check.py#L144): a paused run is not claimable: its run keeps a live owner, so this passes even with the pause guard removed
  - [tests/db/worker_ownership_check.py:146](../../../../tests/db/worker_ownership_check.py#L146): claim_next twice after the owner's lease expires: a wrongful first claim makes the second return None, so the case passes
  - [tests/db/worker_ownership_check.py:164](../../../../tests/db/worker_ownership_check.py#L164): the same, for a job whose available_at is in the future
  - [tests/db/worker_ownership_check.py:74](../../../../tests/db/worker_ownership_check.py#L74): shows one claim_next result and judges another
  - [tests/db/approval_check.py:185](../../../../tests/db/approval_check.py#L185): expire_due twice: the first call does the work the second is judged on
  - [tests/db/assignment_check.py:268](../../../../tests/db/assignment_check.py#L268): read-only example: the same generation query in both arguments
  - [tests/db/verification_check.py:97](../../../../tests/db/verification_check.py#L97): expected text says '1 check', but the predicate never checks it
  - [services/agent/src/autobots/application/runs.py:468-476](../../../../services/agent/src/autobots/application/runs.py#L468): a user pause leaves a live owner's lease in place, which shields line 144
- **Evidence:** check(name, expected, observed, passed) takes the shown value and the verdict as independent expressions. An ast count finds 80 calls in 20 files whose two arguments await the same call, and 5 of those calls change state: claim_next at worker_ownership_check.py:74, 144, 146 and 164, and expire_due at approval_check.py:185.
  check('a paused run is not claimable', 'no claim', await claim_next(db, worker_id='x') is None, await claim_next(db, worker_id='x') is None)
  At 146 and 164 only the guard under test stands between the run and a claim. If it broke, the first call would claim the run, the second would find it held and return None, and the case would show False and pass. At 144 the paused run still has a live owner, because a user pause keeps a live owner's lease (runs.py:468-476), so the case passes even with the pause guard removed. An earlier review already found 'tests that couldn't fail' (docs/engineering/evidence/REVIEW-US-5.1-to-US-9.3/fixes-majors.md:58).
- **Why it matters:** These cases are the lease and claim evidence that python-worker.md asks for, and claim_next's eligibility lives in SQL (worker_leases.py:79-81), so these disposable cases are what proves it. Three of them (lines 144, 146 and 164) can pass with the guard they name broken, and approval_check.py:185 cannot fail at all. The other 75 double reads cost an extra query each, and can show a value other than the one judged.
- **Recommendation:** Evaluate once and judge that value. Change check to take the value and a predicate, or assign the value to a variable first. Fix the five state-changing cases now, and give line 144 an arrangement in which only the pause guard stands between the run and a claim (line 146 already is one). Convert the rest when the shared module (TDBC-03) lands. Make each predicate assert what the expected text claims, which verification_check.py:97 does not for its '1 check'.
- **Rule check:** python-worker.md asks for tests of stale ownership and duplicate delivery. The change lets those cases fail when the guard breaks; no guard, lease or check is weakened.
- **Verification:** revised. Recounted with ast: 80 calls in 20 files, 5 of them state-changing. Corrected why line 144 passes: a user pause keeps the live owner's lease (runs.py:468-476), so the double call is not the cause there.

```python
def check(self, name: str, expected: str, actual: T, ok: Callable[[T], bool] | bool) -> T:
    passed = ok(actual) if callable(ok) else ok
    self.records.append(Case(id=name, expected=expected, observed=short(actual), passed=bool(passed)))
    return actual

taken = await claim_next(db, worker_id='x')   # one call, shown and judged
cases.check('a paused run is not claimable', 'no claim', taken, lambda lease: lease is None)
```

### <a id="tdbc-02"></a>TDBC-02: Db checks import and patch 21 private product names that no fast check reads

- **Severity** high · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 14
- **Where:**
  - [tests/db/review_check.py:21](../../../../tests/db/review_check.py#L21): imports goal_loop._drive and _settle_children
  - [tests/db/verification_check.py:25](../../../../tests/db/verification_check.py#L25): imports goal_loop._settle_candidate
  - [tests/db/wake_check.py:16](../../../../tests/db/wake_check.py#L16): imports goal_loop._keep_lease, a C901 hotspot
  - [tests/db/blocker_check.py:26](../../../../tests/db/blocker_check.py#L26): imports tool_gateway._record; line 168 reassigns ToolGateway._replay
  - [tests/db/workflow_run_check.py:164](../../../../tests/db/workflow_run_check.py#L164): imports workflow_runner._commit inside main; line 266 replaces _pass
  - [tests/db/major_check.py:27](../../../../tests/db/major_check.py#L27): imports routines._admit; also calls gateway._effect and guard._guard
  - [services/agent/src/autobots/application/goal_loop.py:417](../../../../services/agent/src/autobots/application/goal_loop.py#L417): _drive, one of six goal_loop privates used by 9 files
  - [scripts/harness_lib.py:147](../../../../scripts/harness_lib.py#L147): a services/agent change maps to the python domain only
- **Evidence:** 11 files import 13 private names: from goal_loop, _drive, _finish, _settle_candidate, _settle_children, _keep_lease and _scope_guidance; from tool_gateway, _record; from workflow_runner, _Stop, _tool and _commit; plans._evidence_exists, routines._admit and event_routes._live_frame. 3 more files reach private attributes: BrowserExecutor._docker, InferenceSource._browsing and loop_middleware._MIDDLEWARE. Files already counted also patch or call ToolGateway._replay, ToolGateway._effect, LoopMiddleware._guard, workflow_runner._pass and workflow_runner._complete. That makes 14 files and 21 names, counted by grep. check_domains (harness_lib.py:147-148) maps a services/agent change to the python domain only, and no profile lints, compiles or type-checks tests/db: ruff, ruff format and mypy run only from services/agent (scripts/toolchain.py:210-212).
- **Why it matters:** goal_loop.py (782 lines, with C901 hits at _keep_lease:491 and _finish:697) and workflow_runner.py are the likeliest refactors. Renaming or changing the signature of one of these helpers passes fast and full. It then breaks a db or operations qualifier that runs only with Docker, where most of these scripts report a single 'check ran: exit 1' line.
- **Recommendation:** Give the seams these checks drive public, documented names: drive a claimed lease, settle a candidate, settle children, finish with a code, keep a lease and commit an instance. Where the private step isn't the subject, go through process_next and run_goal instead. Patch only module-level seams, with unittest.mock.patch.object. Meanwhile, add tests/db to a non-strict mypy run in fast, so a missing name fails within seconds. Ask the scripts owners to mark the db checks dirty when services/agent/src changes.
- **Rule check:** DH-06 asks for narrow interfaces. The renames keep behavior; leases, fences, receipts and approvals are unchanged. The verify.py domain mapping belongs to the scripts area.
- **Verification:** revised. Recounted 14 files and 21 names (13 imported, 8 reached as attributes), and the evidence now lists all 21. goal_loop.py has 782 lines with C901 hits at 491 and 697, and its six privates are used by 9 files.

```text
goal_loop.py       drive_lease (was _drive), settle_candidate, settle_children, finish, keep_lease, scope_guidance
workflow_runner.py commit_instance (was _commit), complete, run_pass (was _pass)
tool_gateway.py    documented test seams for admission after a passed check (_effect) and receipt writes (_record)
tests/db           import public names only; mock.patch.object(module, 'name', fake) for swaps
fast profile       mypy --follow-imports=silent tests/db, with MYPYPATH=services/agent/src:tests/db
```

### <a id="tdbc-03"></a>TDBC-03: No shared check module: the case protocol and setup are copied into every script

- **Severity** high · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 42
- **Where:**
  - [tests/db/admission_check.py:24](../../../../tests/db/admission_check.py#L24): one of 42 check() copies
  - [tests/db/approval_check.py:17](../../../../tests/db/approval_check.py#L17): one of 32 sys.path inserts
  - [tests/db/approval_check.py:66](../../../../tests/db/approval_check.py#L66): one of 24 value() helpers
  - [tests/db/review_check.py:50](../../../../tests/db/review_check.py#L50): OnePool, defined again at schema_release_check.py:37
  - [tests/db/tool_use_check.py:64](../../../../tests/db/tool_use_check.py#L64): table scan, copied verbatim from provider_key_check.py:91
  - [tests/db/keys_and_vars_check.py:277](../../../../tests/db/keys_and_vars_check.py#L277): token leak scan; connector_check, pull_request_check and tool_keys_check each have another form
  - [tests/db/verification_check.py:173](../../../../tests/db/verification_check.py#L173): run version hard-coded instead of read; 14 such literals in 4 files
  - [scripts/disposable_db.py:342](../../../../scripts/disposable_db.py#L342): the parent's Cases.check has the same four fields and truncates again
- **Evidence:** 42 files define check(name, expected, observed, passed), in 6 truncation variants (none, 300, 400, 600, 700, 900), and the parent truncates again at disposable_db.py:345. 24 files define the same value() helper (26 copies), and 32 insert their own folder into sys.path. 16 files hold 67 try/except blocks that record an expected refusal with two check() calls. 71 admit_run calls in 40 files (70 in 39 under tests/db) spell out at least six keyword arguments. The fixture ModelRoute literal is defined 4 times (goal_loop_script.py:13, wake_check.py:26, workflow_worker.py:19, tests/web/fixture_worker.py:32), and 14 apply_command calls in 4 files hard-code the run version. Counted by grep and ast.
- **Why it matters:** A change to the case shape, to admit_run's signature or to claim handling means editing about 40 files by hand, in code no tool checks. Each new check starts by copying about 40 lines, which is how the variants drifted apart.
- **Recommendation:** Add tests/db/checklib.py with:
  - the typed case protocol;
  - a refusal helper;
  - a wrapper that runs the check and always prints its cases;
  - a Db wrapper with value, admit, claim, command (which reads the current version), expire and approve;
  - a leak scan, one_pool and a killed-worker helper.
  Require the module for new checks, and migrate each file when it is next touched, largest first. Delete the 32 sys.path inserts and their E402 noqa now: every invoker runs these files as scripts, so Python already puts tests/db first on sys.path. The invokers need tests/db on PYTHONPATH only if the files move into subfolders (TDBC-09).
- **Rule check:** DH-W04 expected and observed records keep their shape, so app_db.py and the qualifiers parse them unchanged. No guard, lease or approval changes.
- **Verification:** revised. Counts reproduced with ast and grep. Corrected admit_run to 71 calls in 40 files once tests/qualification is included, and a probe confirmed that a script run directly already has its own folder first on sys.path.

```text
tests/db/checklib.py
  Case (TypedDict) and Cases: check(), refused(name, code, awaitable, *errors), emit(**extra)
  run_check(main): always emits what was observed, then re-raises; Cases.scenario() isolates one failure
  Db(conn): value() raising NoRow(sql), admit(workspace, tools=..., expert=...), claim(run), command(run, cmd, actor),
            expire(run), approve(run, decision), quiesce()
  direct_binding(tools, expert=None), leaked(db, secrets, tables), one_pool(conn), killed_worker(script, *args)
Invokers: unchanged while the folder stays flat; PYTHONPATH=services/agent/src:tests/db once files move into subfolders
```

### <a id="tdbc-04"></a>TDBC-04: A crash ends every later scenario, and 26 of 43 scripts then print nothing

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 43
- **Where:**
  - [tests/db/blocker_check.py:284](../../../../tests/db/blocker_check.py#L284): bare asyncio.run: a crash discards every case observed so far
  - [tests/db/major_check.py:481](../../../../tests/db/major_check.py#L481): same, for the review round 1 majors
  - [tests/db/approval_check.py:274](../../../../tests/db/approval_check.py#L274): the second style: print partial cases, then re-raise
  - [tests/db/connector_check.py:242](../../../../tests/db/connector_check.py#L242): a third style: print in finally
  - [tests/db/approval_check.py:67](../../../../tests/db/approval_check.py#L67): value() indexes fetchone()[0], so a missing row is a bare TypeError
  - [tests/db/assignment_check.py:219](../../../../tests/db/assignment_check.py#L219): a worker that must die is started without checking its exit; also lines 245 and 296
  - [scripts/app_db.py:367-369](../../../../scripts/app_db.py#L367): returns before parsing any partial output
  - [scripts/qualify_identity.py:183](../../../../scripts/qualify_identity.py#L183): parses whatever the check printed
- **Evidence:** The 43 case-printing scripts end in three ways. 26 print nothing if they crash: 23 call asyncio.run or main() bare, and 3 are CLIs that print only on success. 15 print partial cases and re-raise, and 2 print in finally. No script isolates a scenario, so one exception skips the rest. All 26 value() copies return (await (await db.execute(sql, values)).fetchone())[0]. assignment_check.py:219-221 starts a worker that must die, never checks its exit code, and then reads child_run_id from a row that may not exist. keys_and_vars_check.py and tool_keys_check.py also refuse to print when a fixture secret reached their output (tool_keys_check.py:336-338).
- **Why it matters:** When blocker_check.py or major_check.py crashes, the db evidence holds one 'the X check ran: exit 1' line instead of dozens of observed results. The run fails, so nothing is counted as green, but the cases observed before the crash are lost and the later scenarios are neither run nor named, which are the gaps DH-W04 asks evidence to report. For the checks app_db.py runs, partial output is discarded anyway (app_db.py:367-369).
- **Recommendation:** Use one wrapper that always prints the collected cases, after the same leak scan that keys_and_vars_check.py and tool_keys_check.py run today, so a crash can never print a fixture secret. Run each independent scenario under a guard that records its exception as a failed case and moves on. Make value() raise a NoRow error that names its SQL, and record each killed worker's exit code as a case. Ask the scripts owners to parse partial output in app_db.py, as qualify_identity.py:183 already does.
- **Rule check:** DH-09: skipped checks never count as green, and DH-W04 records failures, errors and gaps. AGENTS.md keeps secrets out of evidence, so the wrapper keeps today's leak refusal before printing.
- **Verification:** revised. Endings recounted (23 bare, 3 success-only CLIs, 15 print and re-raise, 2 finally). Added the leak refusal the wrapper must keep and app_db.py's early return at 367-369, and moved the connector citation to its finally (242).

```python
def run_check(main: Callable[[Cases], Awaitable[dict | None]]) -> None:
    cases = Cases()
    try:
        extra = asyncio.run(main(cases)) or {}
    except BaseException:
        cases.emit()          # what was observed, always one JSON line
        raise
    cases.emit(**extra)
```

### <a id="tdbc-05"></a>TDBC-05: Checks end every job in the database so claim_next picks their own run

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 39
- **Where:**
  - [tests/db/worker_ownership_check.py:45](../../../../tests/db/worker_ownership_check.py#L45): 'Only this run's job is eligible': the release before each admission
  - [tests/db/approval_check.py:70](../../../../tests/db/approval_check.py#L70): the same statement, 3 times in this file
  - [tests/db/web_tools_check.py:90](../../../../tests/db/web_tools_check.py#L90): 5 times in one main
  - [tests/db/artifact_check.py:87](../../../../tests/db/artifact_check.py#L87): uses whatever claim_next returned, without checking which run it is
  - [scripts/qualify_identity.py:170](../../../../scripts/qualify_identity.py#L170): orders checks around it: 'Last, so no later check's cleanup ends the runs they leave claimed'
  - [tests/db/tool_use_view_check.py:78](../../../../tests/db/tool_use_view_check.py#L78): holds a run for the browser with an 1800-second lease that the release would end
  - [tests/db/task_timing_check.py:72](../../../../tests/db/task_timing_check.py#L72): claims only its own run with claim_run: the pattern to spread
- **Evidence:** This statement runs 39 times in 27 files, counted by regex over joined string literals, and a shorter variant without the lease columns runs 3 more times in improvement_check.py:
  update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'
  It runs mid-scenario, and it also ends live leases that other checks hold for browser suites. Only 6 of the 29 files that call claim_next assert that the claimed run is the one they admitted.
- **Why it matters:** Adding or reordering a check can end another check's browser arrangement, as the ordering comment in qualify_identity.py shows. If an eligible job from another check survives, a scenario silently drives the wrong run. Isolation lives in 39 SQL strings instead of one named place.
- **Recommendation:** Name the isolation step once. It should end only what claim_next could take, meaning queued jobs and expired leases, so live leases stay, and then assert the claimed run. Where the worker's own claim isn't under test, claim the run with claim_run and drive it with run_goal, as task_timing_check.py does.
- **Rule check:** DH-07 requires explicit fixture ownership, and DH-08 says cleanup proves ownership first. The narrower release touches only jobs that no live owner holds, on disposable targets only.
- **Verification:** revised. Recounted 39 exact copies in 27 files plus 3 shorter ones, and 6 of 29 claim_next callers that assert the claimed run. The ordering comment is at qualify_identity.py:170, not 169.

```text
Db.quiesce(): end only jobs claim_next could take; live leases, including browser arrangements, stay
  update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null
  where status = 'queued' or (status = 'claimed' and lease_expires_at < clock_timestamp())
Db.claim(run): claim_run(run) when the worker's claim isn't the subject; otherwise quiesce(), process_next(),
  then a case asserting the run under test is the one that moved
```

### <a id="tdbc-06"></a>TDBC-06: Check mains are 150 to 316 line scenario lists

- **Severity** medium · **Dimension** size · **Effort** L · **Risk** medium · **Occurrences** 35
- **Where:**
  - [tests/db/verification_check.py:52-367](../../../../tests/db/verification_check.py#L52): 316 lines, about 14 commented sections
  - [tests/db/assignment_check.py:49-338](../../../../tests/db/assignment_check.py#L49): 290 lines
  - [tests/db/recovery_check.py:46-315](../../../../tests/db/recovery_check.py#L46): 270 lines
  - [tests/db/tool_keys_check.py:86-339](../../../../tests/db/tool_keys_check.py#L86): 254 lines
  - [tests/db/workflow_run_check.py:75-321](../../../../tests/db/workflow_run_check.py#L75): 247 lines
  - [tests/db/improvement_check.py:42-284](../../../../tests/db/improvement_check.py#L42): 243 lines
  - [tests/db/blocker_check.py:51-277](../../../../tests/db/blocker_check.py#L51): 227 lines
  - [tests/db/major_check.py:64-259](../../../../tests/db/major_check.py#L64): effects_and_assignments, 196 lines
- **Evidence:** Measured from py_functions.json: 35 functions in the area exceed 80 lines (30 of them named main), 19 exceed 150 and 10 exceed 200. verification_check.main runs 316 lines through about 14 sections separated only by comments. It defines value, admit, candidate, scope_of and state as closures over db, and rebinds run, lease, model and result in each section. browser_executor_check.py already splits its work into containment, isolation and ownership functions.
- **Why it matters:** A scenario can't be named, run or failed alone. Readers must track variable rebinding across hundreds of lines, and the first exception decides how much of the file ever runs.
- **Recommendation:** Split each main into module-level scenario functions that take the shared Db and Cases, list them in a SCENARIOS tuple, and pass state between dependent scenarios explicitly. Start with the eight largest, each when it is next touched.
- **Rule check:** DH-06 asks for small cohesive modules. No rule fixes the layout of these scripts, and the JSON cases keep their shape.
- **Verification:** confirmed. py_functions.json gives 35 functions over 80 lines (30 named main), 19 over 150 and 10 over 200, and verification_check.main defines the five closures and about 14 comment-separated sections described.

```python
SCENARIOS = (publish_is_required, superseded_copy_fails, unknown_effect_blocks, stale_verifier_writes_nothing,
             backoff_retry_is_fenced, pause_lets_call_finish, interrupted_internal_writes, hung_call_is_bounded,
             exception_type_is_logged, inputs_are_read_only)   # 15 to 40 lines each

async def main(cases: Cases) -> None:
    async with Db.connect(WORKSPACE) as db:
        for scenario in SCENARIOS:
            await cases.scenario(scenario.__name__, scenario(db, cases))   # a crash is one failed case
```

### <a id="tdbc-07"></a>TDBC-07: Refusal checks accept any exception as the expected refusal

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 8
- **Where:**
  - [tests/db/restore_check.py:71](../../../../tests/db/restore_check.py#L71): any exception counts as 'the database alone cannot open it'
  - [tests/db/run_admission_check.py:140](../../../../tests/db/run_admission_check.py#L140): any exception counts as losing the race
  - [tests/db/recovery_check.py:185](../../../../tests/db/recovery_check.py#L185): any exception becomes a class name, so an unexpected error passes when the other side wins; also line 192
  - [tests/db/run_list_check.py:41](../../../../tests/db/run_list_check.py#L41): falls back to a second Expert on any exception, so the arrangement never states the rule it relies on
  - [tests/db/credential_store_check.py:69](../../../../tests/db/credential_store_check.py#L69): compares type(error).__name__ with a string instead of catching the class
  - [services/agent/src/autobots/application/credentials/crypto.py:14](../../../../services/agent/src/autobots/application/credentials/crypto.py#L14): CredentialDecryptionError exists to catch
  - [services/agent/src/autobots/application/credentials/store.py:25](../../../../services/agent/src/autobots/application/credentials/store.py#L25): CredentialStorageUnavailable exists to catch
  - [services/agent/src/autobots/application/experts.py:232-233](../../../../services/agent/src/autobots/application/experts.py#L232): create_session refuses only a direct session without exactly one Expert
- **Evidence:** 8 broad except clauses don't re-raise. At 4 of them, in 3 files, any exception satisfies the case, and at a 5th, run_list_check.py:41, any exception selects a fallback arrangement. restore_check.py:67-73 records 'refused' whenever load_active raises anything, including a TypeError from a changed signature:
  except Exception as error:  # noqa: BLE001 - only the type is reported, never a message.
      outcome = type(error).__name__
  check(f'the database alone cannot open it: {label}', 'refused', outcome, outcome != 'opened')
  The race checks (run_admission_check.py:140, recovery_check.py:185 and 192) count any exception as losing. run_list_check.py hedges against a refusal create_session never makes for a coordinator: it refuses only a direct session without exactly one Expert (experts.py:232-233).
- **Why it matters:** A backup property (the key is kept separately) and a concurrency property (one command applies once) can be reported as holding when the code under test crashed for some other reason.
- **Recommendation:** Catch the documented types: CredentialDecryptionError and CredentialStorageUnavailable for the restore, and VersionConflict and CommandRefused for the races. Record anything else as a failed case that names its type. In run_list_check.py, drop the fallback, or catch ExpertRefused with the code it expects.
- **Rule check:** DH-06 rules out swallowed exceptions, and DH-08 requires backup tests to restore the separate key into an isolated instance. Narrowing the catch tightens that evidence; no guard changes.
- **Verification:** revised. All 8 broad catches reopened: 4, in 3 files, accept any exception as the expected outcome. run_list_check.py's fallback guards against a refusal that experts.py:232-233 does not make for coordinators.

### <a id="tdbc-08"></a>TDBC-08: No lint, format or type gate covers tests/db, tests/web or tests/qualification, yet the code carries 307 suppressions

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 307
- **Where:**
  - [tests/db/approval_check.py:18](../../../../tests/db/approval_check.py#L18): one of 272 noqa: E402 comments that ruff reports as unused
  - [tests/db/tool_keys_check.py:40](../../../../tests/db/tool_keys_check.py#L40): the only ruff-formatted, double-quoted file among single-quoted neighbours
  - [tests/db/run_admission_check.py:32](../../../../tests/db/run_admission_check.py#L32): type: ignore[no-untyped-def] for a mypy that never reads the file
  - [tests/db/memory_check.py:158](../../../../tests/db/memory_check.py#L158): assert run_goal and AIMessage keeps two unused imports alive
  - [tests/db/verification_check.py:366](../../../../tests/db/verification_check.py#L366): assert ToolFailed and ModelRoute, the same hack
  - [tests/db/major_check.py:259](../../../../tests/db/major_check.py#L259): _ = json, although json is used at line 478
  - [tests/db/upgrade_check.py:127](../../../../tests/db/upgrade_check.py#L127): _ = second silences an unused parameter
  - [services/agent/pyproject.toml:52](../../../../services/agent/pyproject.toml#L52): mypy files = src and tests of the service only; ruff src matches at line 44
- **Evidence:** The area has 297 noqa comments in 37 files and 10 type: ignore comments, counted by grep. Ruff run with the service's rule set (output in .checks/reviews/review-2026-11-12-09-52-30/db-tests/ruff_area.txt) reports 2,759 E501, 290 unused noqa, 70 unsorted imports and 5 unused imports. ruff format would rewrite 72 files. 272 noqa: E402 comments are unused, because ruff allows imports after a sys.path change. 24 more name PLC0415, PLC2701 and BLE001, which no configuration enables. goal_loop_check.py:232 also makes a call whose result is discarded.
- **Why it matters:** Suppressions with no tool behind them hide nothing and mislead readers. Unused imports, dead calls and type mismatches build up unseen, and two formatting styles coexist in one folder.
- **Recommendation:** Add a root ruff configuration for tests/ with the service's rules, ignoring E501 at first and excluding the deliberate bad fault samples. Run the formatter once. Delete the unused noqa comments and the keep-alive hacks. Add a non-strict mypy pass for tests/db, and move both to errors in fast once clean.
- **Rule check:** DH-06 calls for Ruff lint and format and mypy on owned modules, with check and format as separate gates. The deliberate bad fixtures stay excluded, as tests/faults/README.md requires.
- **Verification:** confirmed. Reran ruff 0.17.3 read-only (--no-cache --isolated): 290 RUF100, made of 272 unused E402 and 24 directives naming non-enabled codes, plus 2,759 E501, and 72 files to reformat. tool_keys_check.py is the only formatted file outside tests/faults, and toolchain.py:210-212 runs ruff and mypy only in services/agent.

```text
# ruff.toml at the repository root
target-version = 'py312'
line-length = 100
extend-exclude = ['tests/faults/python/bad_*', 'tests/faults/typescript']
[lint]
select = ['E', 'F', 'W', 'I', 'B', 'UP', 'ASYNC', 'RUF']
[lint.per-file-ignores]
'tests/**' = ['E501']   # baseline: warn, format once, then remove
# fast: ruff check tests; ruff format --check tests; mypy --follow-imports=silent tests/db
```

### <a id="tdbc-09"></a>TDBC-09: tests/db mixes six kinds of file, and the suffixes don't say which

- **Severity** medium · **Dimension** structure · **Effort** M · **Risk** medium · **Occurrences** 75
- **Where:**
  - [tests/db/product_inference_check.py:105](../../../../tests/db/product_inference_check.py#L105): named _check, but a CLI of six arrangement commands that prints no cases
  - [tests/db/operations_check.py:179](../../../../tests/db/operations_check.py#L179): half CLI (admit, cancel, resume), half retention check
  - [tests/db/notify_live.py:1](../../../../tests/db/notify_live.py#L1): a browser arrangement with a _live suffix
  - [tests/db/browser_runs.py:1](../../../../tests/db/browser_runs.py#L1): a browser arrangement without one, like model_sources.py and run_files_probe.py
  - [tests/db/worker_process.py:1](../../../../tests/db/worker_process.py#L1): a killed worker, where the others are *_worker.py
  - [tests/db/goal_loop_script.py:1](../../../../tests/db/goal_loop_script.py#L1): an importable scripted model, named _script
  - [tests/db/migrations/0001_workspaces.sql:1](../../../../tests/db/migrations/0001_workspaces.sql#L1): the synthetic H1 stack's schema, beside the application fixtures
  - [scripts/app_db.py:34](../../../../scripts/app_db.py#L34): invokers hard-code these paths
- **Evidence:** 44 files end in _check.py: 43 print cases, product_inference_check.py prints none, and operations_check.py is part CLI. Browser arrangements and live actions are spread across _live.py and unsuffixed names. *_worker.py covers both killed children and long-running serve loops, and worker_process.py is a killed worker. The synthetic H1 stack (migrations/, seeds/, bad_migrations/, worker_fixture.sql, storage_policies.sql, schema app) sits beside the application stack's app_fixture.sql and app_bad_migrations/. Paths are referenced from app_db.py, the qualify_*.py scripts and, in comments, 6 Playwright specs.
- **Why it matters:** Readers can't tell what runs where (app_db, a qualifier or a Playwright spec), or what a new file should be called. The flat folder works only because each file runs as a script with its own folder first on sys.path, so a move into subfolders also has to give the invokers tests/db on PYTHONPATH.
- **Recommendation:** Group files by role: checks/, workers/, arrange/ (browser-suite setup and live actions), fixtures/ (scripted models, sinks, graphs and the shared module), sql/h1/ and sql/app/. Add a README table mapping each file to its invoker. Give product_inference_check.py an arrangement name, and split operations_check.py's CLI from its check. Move everything in one change, together with the invoker paths and tests/db on the invokers' PYTHONPATH.
- **Rule check:** DH-03 lists tests/harness/ but not a layout for tests/db, so subfolders don't conflict. The SQL fixtures stay synthetic and disposable.
- **Verification:** revised. Roles and counts confirmed (44 _check.py files; the 6 specs name these paths in comments). Dropped the claim that the flat layout forces the 32 sys.path inserts: they are redundant for scripts run directly.

### <a id="tdbc-10"></a>TDBC-10: Checks also arrange browser-suite state and run static scans

- **Severity** medium · **Dimension** functions · **Effort** M · **Risk** medium · **Occurrences** 9
- **Where:**
  - [tests/db/approval_check.py:222](../../../../tests/db/approval_check.py#L222): arranges five runs and returns ten AUTOBOTS_TEST_* values for the inbox suite
  - [tests/db/approval_check.py:277](../../../../tests/db/approval_check.py#L277): the failure path prints cases without those values
  - [tests/db/effect_check.py:188](../../../../tests/db/effect_check.py#L188): 'Left unknown for the browser'
  - [tests/db/blocker_check.py:99](../../../../tests/db/blocker_check.py#L99): 'Left pending, for the browser suite to read'
  - [tests/db/task_timing_check.py:148](../../../../tests/db/task_timing_check.py#L148): returns panel values for the browser suite
  - [tests/db/memory_check.py:155](../../../../tests/db/memory_check.py#L155): scans service source for 'embedding', with a hard-coded exemption string
  - [tests/db/concept_seed_check.py:54](../../../../tests/db/concept_seed_check.py#L54): scans migrations and seeds; lines 108-110 scan source for secrets
  - [scripts/qualify_identity.py:170](../../../../scripts/qualify_identity.py#L170): these checks must run last so their arrangements survive
- **Evidence:** 7 checks leave state, or return browser_env values, for Playwright suites: approval, blocker, effect, provider_key, result_stream, task_timing and tool_use_view. 2 checks run source scans that need no database: memory and concept_seed. approval_check.py prints its browser values only when every scenario passes. browser_runs.py and model_sources.py already show the alternative: stand-alone arrangement scripts that print only what the browser needs.
- **Why it matters:** A failing check also breaks unrelated browser suites, which then start without their values. The order of checks in the qualifier becomes load-bearing, and static policies run only when Docker is up.
- **Recommendation:** Move each arrangement into an arrange/ script like browser_runs.py that prints only browser_env. Move the source scans to tests/harness, which runs in the harness and fast profiles.
- **Rule check:** DH-09 puts static checks in the harness and fast profiles and keeps db for disposable-target behavior, and DH-07 asks for explicit fixture ownership. Moving the scans and arrangements changes no assertion.
- **Verification:** revised. Confirmed 7 checks that leave browser state (approval_check.py arranges 5 runs and returns 10 values) and 2 file scans. Filled in the rule check and corrected the qualify_identity line to 170.

### <a id="tdbc-11"></a>TDBC-11: An install helper that handles the real OpenRouter key lives in tests/db

- **Severity** medium · **Dimension** modules · **Effort** S · **Risk** medium · **Occurrences** 1
- **Where:**
  - [tests/db/live_goal_helper.py:1](../../../../tests/db/live_goal_helper.py#L1): 'What scripts/live_goal.py does with the real key'
  - [tests/db/live_goal_helper.py:24](../../../../tests/db/live_goal_helper.py#L24): saves the real key through the product's path, including OpenRouter's key check
  - [tests/db/live_goal_helper.py:34](../../../../tests/db/live_goal_helper.py#L34): reads the key's spend from openrouter.ai
  - [scripts/persistent_install.py:40](../../../../scripts/persistent_install.py#L40): HELPER = 'tests/db/live_goal_helper.py'
  - [scripts/persistent_install.py:338](../../../../scripts/persistent_install.py#L338): the persistent install runs it; again at line 550
  - [scripts/live_goal.py:33](../../../../scripts/live_goal.py#L33): the live goal runs it too
  - [scripts/harness_lib.py:55-57](../../../../scripts/harness_lib.py#L55): persistent_install.py and tests/db/ both map to the db domain
  - [docs/engineering/evidence/US-12.4/measure_two_calls.py:34](../../../../docs/engineering/evidence/US-12.4/measure_two_calls.py#L34): an archived evidence script names the same path
- **Evidence:** persistent_install.py (lines 338 and 550) and live_goal.py run tests/db/live_goal_helper.py. It reads the real OpenRouter key from a file, saves it through ProviderSettings including OpenRouter's key check, reads the key's usage from openrouter.ai and counts leaks in durable tables. harness_lib.py:55-57 maps tests/db/ to the db check domain, as it maps persistent_install.py itself, but no path-scoped rule covers tests/db: infrastructure.md names scripts/persistent_install.py, and database.md names supabase/**. ruff and mypy never read the file.
- **Why it matters:** Operational code that handles the real key sits in a test folder that no lint, format or type gate reads and no rule file loads for, and a test cleanup could break the persistent install.
- **Recommendation:** Move the helper into the product's operations package as a small CLI, for example autobots.operations.live_key beside route_qualification, which already reads the key file, so ruff, mypy and pytest cover it. Update the two HELPER constants, and keep its output limited to numbers and counts. The archived US-12.4 script stays as recorded evidence.
- **Rule check:** .claude/rules/infrastructure.md covers persistent_install.py; moving the helper changes no persistent behavior. Secret handling from AGENTS.md is unchanged, since the helper still prints only numbers, and its key metadata calls are free and are not inference.
- **Verification:** revised. Callers confirmed at persistent_install.py:338 and 550 and live_goal.py:33. Corrected the impact: persistent_install.py maps to the same db domain (harness_lib.py:55-56), so the real gap is that no rule or lint gate covers the helper.

### <a id="tdbc-12"></a>TDBC-12: type: ignore replaces annotations and hides values the product types forbid

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 22
- **Where:**
  - [tests/db/approval_check.py:123](../../../../tests/db/approval_check.py#L123): an Inheritance with session_id, expert_id and version set to None, silenced with arg-type
  - [services/agent/src/autobots/application/runs.py:61](../../../../services/agent/src/autobots/application/runs.py#L61): Inheritance types those fields as UUID and int
  - [tests/db/keys_and_vars_check.py:250](../../../../tests/db/keys_and_vars_check.py#L250): a SimpleNamespace standing in for a Lease
  - [tests/db/keys_and_vars_check.py:257](../../../../tests/db/keys_and_vars_check.py#L257): passed to a private method, silenced with arg-type
  - [tests/db/approval_check.py:71](../../../../tests/db/approval_check.py#L71): one of 12 SimpleNamespace bindings
  - [services/agent/src/autobots/application/runs.py:185](../../../../services/agent/src/autobots/application/runs.py#L185): admit_run takes binding: Any, the root cause
  - [tests/db/admission_check.py:33](../../../../tests/db/admission_check.py#L33): one of 7 no-untyped-def ignores that need only annotations
  - [tests/db/run_admission_check.py:37](../../../../tests/db/run_admission_check.py#L37): an unannotated helper, silenced instead of typed
- **Evidence:** The 22 occurrences are 10 type: ignore comments and 12 SimpleNamespace bindings. Of the ignores, 3 hide argument types that the product forbids. The other 7 are no-untyped-def ignores on helpers in admission_check, run_admission_check, worker_ownership_check and tests/web/fixture_upstream_api.py. The bindings mirror admit_run's binding: Any. No type checker reads these files.
- **Why it matters:** When product types tighten, the tests keep exercising shapes that no production path can produce, and nothing reports it.
- **Recommendation:** Annotate the seven helpers. Build bindings through one typed builder in the shared module. Ask the py-run owners to type binding as a Protocol, so tests, routines.py and workflows.py share one definition.
- **Rule check:** .claude/rules/contracts.md keeps domain, row and DTO types distinct; one typed test builder merges none of them. Typing admit_run's binding belongs to the py-run area.
- **Verification:** confirmed. 10 type: ignore comments (3 arg-type, 7 no-untyped-def) and 13 SimpleNamespace uses (12 bindings, 1 Lease) confirmed. assignments.py:90-91 refuses delegation without a session, so a None-filled Inheritance is a shape production never builds.

### <a id="tdbc-13"></a>TDBC-13: Patched product globals and scratch keys aren't always cleaned up

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 14
- **Where:**
  - [tests/db/review_check.py:178](../../../../tests/db/review_check.py#L178): swaps operations.REQUIRED_COLUMNS and restores it without finally
  - [tests/db/keys_and_vars_check.py:228](../../../../tests/db/keys_and_vars_check.py#L228): sets browsing_tool.executor_qualified and never restores it
  - [tests/db/keys_and_vars_check.py:268](../../../../tests/db/keys_and_vars_check.py#L268): sets it again, still without restoring
  - [tests/db/major_check.py:346](../../../../tests/db/major_check.py#L346): a hand-written try/finally swap of worker.evaluate_routines
  - [tests/db/workflow_run_check.py:235](../../../../tests/db/workflow_run_check.py#L235): three hand-written swaps in one main
  - [tests/db/keys_and_vars_check.py:90](../../../../tests/db/keys_and_vars_check.py#L90): creates a master key and a .env in a mkdtemp folder that is never removed
  - [tests/db/tool_keys_check.py:91](../../../../tests/db/tool_keys_check.py#L91): the same, with fixture provider keys
  - [tests/db/credential_store_check.py:34](../../../../tests/db/credential_store_check.py#L34): TemporaryDirectory: the pattern to use
- **Evidence:** There are 10 hand-written patch sites in 6 files, counted by grep. 8 restore in try/finally, 1 restores without finally, and 1 never restores. 4 mkdtemp folders are never removed (keys_and_vars_check.py:90, tool_keys_check.py:91, effect_check.py:42, browser_runs.py:47). Two of them hold a generated master key and .env files with fixture tokens.
- **Why it matters:** A failure leaves patched globals in place for the rest of the process, and every db run leaves generated keys and fixture .env files in the system temp folder.
- **Recommendation:** Use unittest.mock.patch.object as a context manager for every swap, and tempfile.TemporaryDirectory for every scratch home folder.
- **Rule check:** AGENTS.md keeps provider master keys out of workspaces and evidence. These are fixture keys, and removing them after use keeps to that rule.
- **Verification:** confirmed. Ten product swaps in 6 files: 8 restore in finally, review_check.py:178-180 restores without finally, and keys_and_vars_check.py:228 and 268 never restore. Four mkdtemp folders are never removed.

### <a id="tdbc-14"></a>TDBC-14: Files named after review rounds hide which behavior they test

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [tests/db/blocker_check.py:1](../../../../tests/db/blocker_check.py#L1): 'Blockers B1, B2, B6, B8 and B9 from review round 1'
  - [tests/db/blocker_check.py:69](../../../../tests/db/blocker_check.py#L69): # B1, with no path to where B1 is defined
  - [tests/db/major_check.py:1](../../../../tests/db/major_check.py#L1): 'Majors from review round 1'
  - [tests/db/major_check.py:87](../../../../tests/db/major_check.py#L87): # M1
  - [tests/db/review_check.py:1](../../../../tests/db/review_check.py#L1): 'US-11.12's review findings'
  - [tests/db/review_check.py:81](../../../../tests/db/review_check.py#L81): # N-9
  - [docs/engineering/evidence/REVIEW-US-5.1-to-US-9.3/fixes-r1.md:11](../../../../docs/engineering/evidence/REVIEW-US-5.1-to-US-9.3/fixes-r1.md#L11): where B1 is defined
  - [docs/engineering/evidence/US-11.12/review-r1-open-findings.md:46](../../../../docs/engineering/evidence/US-11.12/review-r1-open-findings.md#L46): where N-9 is defined
- **Evidence:** blocker_check.py, major_check.py and review_check.py are named after the review that found each bug. Their IDs are defined in evidence documents that the checks never name. Coverage of one behavior is split across these files and behavior-named checks: receipt monotonicity sits in blocker_check B2 and in tool_gateway_check, and approval expiry in approval_check and major_check M2.
- **Why it matters:** A reader looking for every test of a behavior must know which review found it, and an ID can only be resolved by searching docs.
- **Recommendation:** Keep the IDs, and add the evidence path to each module docstring now. Put new regression cases in the behavior's own check, with their review ID in a comment.
- **Rule check:** The ground rules keep citations of decisions and stories in comments; this adds the source path and removes no ID.
- **Verification:** confirmed. The three docstrings name review rounds without a path. B1 is defined at fixes-r1.md:11 and N-9 at review-r1-open-findings.md:46, and none of the three files cites either document.

### <a id="tdbc-15"></a>TDBC-15: Goal text is an untyped command channel to fixture models

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 20
- **Where:**
  - [tests/web/fixture_worker.py:74](../../../../tests/web/fixture_worker.py#L74): branches on 'slice-only-claims' in the goal
  - [tests/web/fixture_worker.py:106](../../../../tests/web/fixture_worker.py#L106): 'slice-wrong-total' changes the saved total
  - [tests/web/fixture_worker.py:138](../../../../tests/web/fixture_worker.py#L138): 'slice-slow'
  - [tests/db/product_inference_worker.py:161](../../../../tests/db/product_inference_worker.py#L161): branches on '[malformed]'; also '[dropped]', '[limited]', '[cutoff]' and others
  - [tests/db/product_inference_check.py:34](../../../../tests/db/product_inference_check.py#L34): wraps the qualifier's bare tag in brackets
  - [scripts/qualify_worker_inference.py:333](../../../../scripts/qualify_worker_inference.py#L333): passes 'malformed' as a bare word
  - [apps/web/tests/browser/slice-controls.spec.ts:127](../../../../apps/web/tests/browser/slice-controls.spec.ts#L127): 'slice-finishes' is a label the fixture doesn't handle
  - [apps/web/tests/browser/slice-inspector.spec.ts:179](../../../../apps/web/tests/browser/slice-inspector.spec.ts#L179): 'slice-private', another label in the same namespace
- **Evidence:** fixture_worker.py handles 11 slice-* markers, and product_inference_worker.py handles 9 bracket tags. Both are found by substring search in the goal text. The same namespace also carries plain labels, so a misspelled command looks like a label and takes the default happy path.
- **Why it matters:** A typo in a spec or qualifier changes what is tested without anything failing.
- **Recommendation:** Define the markers once per language: a Python constants module shared by the fixtures and qualifiers, and a TypeScript module for the specs. Give commands a distinct prefix, and make the fixtures fail on an unknown command.
- **Rule check:** .claude/rules/model-gateway.md keeps fake transports as the default test path; this is unchanged.
- **Verification:** confirmed. Counted 11 slice-* markers in fixture_worker.py and 9 bracket tags in product_inference_worker.py; the specs' 'slice-finishes' and 'slice-private' reach the default path unhandled.

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
| TDBC-16 | The fault checker's copy of the transition table already differs from the product | The copied table matches NORMAL_EXITS exactly. The one difference, cancelling after cancelling, follows SP-010's 'valid from every nonterminal state', where the product applies 'repeated cancellation is idempotent'. No fault fixture contains that pair (good_cancel.json runs queued, running, cancelling, cancelled), and tests/faults/README.md keeps this fixture checker apart from the product's state machine, so the proposed coupling test would guard an edge nothing reaches. |

## Not covered

This review is static: no check, worker or fixture was run, and no Docker stack was started. mypy and pytest were not run, because they are not among the permitted read-only tools. Ruff was run in check mode with --isolated settings, and its raw output is in .checks/reviews/review-2026-11-12-09-52-30/db-tests/ruff_area.txt. Several files were read only in the parts that run or classify these checks: scripts/app_db.py (lines 1-80 and 320-620), scripts/qualify_identity.py (150-200), scripts/disposable_db.py (the Cases class and fixture references), scripts/harness_lib.py (120-175), scripts/verify.py (100-160), PRD-Development-Harness.md (DH-03 to DH-08) and services/agent/src/autobots/domain/runs.py. The Playwright specs that consume browser_env and the slice markers were grepped, not read. tests/qualification/tasks.json, tests/qualification/dev_tasks.json and the fault expectation JSON files are outside the listed scope and were not read. Whether each bad fault fixture still fails for its stated reason was not re-run.
