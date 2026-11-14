# Tests: harness and toolchain

The harness and toolchain tests cover 20 files and about 4,240 lines. The harness profile runs 290 tests in about 26 s, and tests/toolchain adds 36 more. The tests focus on behaviour and say honestly what kind of evidence they give. They drive hooks and CLIs at the process boundary with fakes on PATH, and they cover DH-05's whole hook fixture list. Keep unittest. The harness profile runs `python3.12 -m unittest discover` in a reduced environment before any bootstrap, and judge_unittest parses unittest's summary to refuse empty or skipped suites. pytest exists only in the service venv, so switching would tie the harness to bootstrap. The gains come from modern unittest habits (enterContext, subTest, a shared base and support module), not from a new runner. Two guards do not guard. The private run-column check reads only the first grant of the first runs migration, while five later migrations add grants to the same role. The offline pin and launcher tests in tests/toolchain run in no profile, though they pass in 0.08 s. The two largest files are arranged by when tests were added, not by what they test. test_hooks.py is one 45-test class covering seven subjects in 703 lines. test_assistant_assets.py packs eight suites and about 165 lines of checker code into 783 lines. Fixture plumbing (stub executables, Git repositories, config roots, report records) is rewritten in each file, and the Git setups are hardened differently. Failures are hard to read: 47 of 60 `assertTrue(any(...))` calls carry no message. Fourteen child processes have no timeout, under one 60-second cap for the whole suite. Five tests assert source text rather than behaviour. No lint or format configuration covers these files: the service's own ruff rules report 456 issues, and 20 of 20 files would be reformatted. test_evidence.py, test_specs.py and test_verify_profiles.py are over 300 lines but each tests one module. They need shared helpers, not splitting. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 2 | No lint, format or type configuration covers these files; the service's own ruff rules give 456 findings, 20 of 20 files would be reformatted, and two quote styles and two import orders coexist. |
| modules | 3 | About 165 lines of checker code live in a test module beside a second frontmatter parser in harness_lib; tests/toolchain has a support module but tests/harness has none. |
| size | 3 | No function exceeds 40 lines, but test_hooks.py and test_assistant_assets.py each pack six to eight subjects into 700 to 780 lines. |
| functions | 4 | Helpers are short builders with one job each; a few tests run several phases while their names describe only the first. |
| structure | 3 | Files follow when tests were added (test_final_review.py, appended classes) rather than the unit under test; fingerprint and config_errors tests are spread over three files. |
| approach | 4 | unittest suits the install-free harness; tests run at the process boundary with fakes on PATH and mutate one valid baseline, though some assert source text and some are lint rules in disguise. |
| comments | 4 | Module docstrings state the evidence class and its limits, and comments explain why; a few test names promise more than the test checks. |
| types | 3 | Helpers are partly annotated (bare dicts, untyped callbacks) and no type checker runs on them; the run-state oracle is a hand copy instead of the generated contract. |
| errors | 3 | Error paths of the code under test are covered thoroughly, but 14 child processes have no timeout and a hang shows up as an anonymous suite error. |
| tests | 3 | Strong behavioural coverage of DH-05's fixture list, weakened by a grant guard that misses later migrations, unwired static guards, unreadable failure messages and one order-dependent test. |
| maintainability | 3 | Each test reads well on its own, but extending the suite is costly: fixtures are duplicated, two files are oversized and no style is enforced. |

## Strengths

- **One valid baseline, one change, one exact error.** valid_root in tests/harness/test_assistant_assets.py:173-198 is documented as making 'each negative fixture change one thing', and tests built on it assert the exact error list (test_assistant_assets.py:306, :313). test_evidence.py:77-112 builds valid_manifest from the real template, and its rejected() helper prints the error list on failure. test_disposable_guard.py:61-77 and test_supabase_stack.py:69-89 use named one-line mutators, with change.__name__ as the subTest label. Sources: [tests/harness/test_assistant_assets.py:173-198](../../../../tests/harness/test_assistant_assets.py#L173), [tests/harness/test_assistant_assets.py:306](../../../../tests/harness/test_assistant_assets.py#L306), [tests/harness/test_assistant_assets.py:313](../../../../tests/harness/test_assistant_assets.py#L313), [tests/harness/test_evidence.py:77-112](../../../../tests/harness/test_evidence.py#L77), [tests/harness/test_disposable_guard.py:61-77](../../../../tests/harness/test_disposable_guard.py#L61), [tests/harness/test_supabase_stack.py:69-89](../../../../tests/harness/test_supabase_stack.py#L69).
- **DH-05's hook fixture list is covered at the process boundary.** tests/harness/test_hooks.py covers malformed JSON (170-176), the input cap at its exact boundary (188-194), unsupported events and tools without echo (290-299), the deadline (301-311), a missing library (319-327), symlink loops and unusable paths (339-346), secret names before and after links (348-358), and shell metacharacters kept as data (360-377). Sources: [tests/harness/test_hooks.py:170-176](../../../../tests/harness/test_hooks.py#L170), [tests/harness/test_hooks.py:188-194](../../../../tests/harness/test_hooks.py#L188), [tests/harness/test_hooks.py:290-299](../../../../tests/harness/test_hooks.py#L290), [tests/harness/test_hooks.py:301-311](../../../../tests/harness/test_hooks.py#L301), [tests/harness/test_hooks.py:319-327](../../../../tests/harness/test_hooks.py#L319), [tests/harness/test_hooks.py:339-346](../../../../tests/harness/test_hooks.py#L339), [tests/harness/test_hooks.py:348-358](../../../../tests/harness/test_hooks.py#L348), [tests/harness/test_hooks.py:360-377](../../../../tests/harness/test_hooks.py#L360).
- **Fakes on PATH show that refusals happen before any side effect.** test_disposable_guard.py:80-113 puts a recording fake docker on PATH and asserts it was never called. test_assistant_assets.py:438-444 shows the version probe inherits no credential. test_hooks.py:578-592 shows Git is asked only when an edit needs it. test_verify_profiles.py:121-126 makes find_tools raise if it is looked up. Sources: [tests/harness/test_disposable_guard.py:80-113](../../../../tests/harness/test_disposable_guard.py#L80), [tests/harness/test_assistant_assets.py:438-444](../../../../tests/harness/test_assistant_assets.py#L438), [tests/harness/test_hooks.py:578-592](../../../../tests/harness/test_hooks.py#L578), [tests/harness/test_verify_profiles.py:121-126](../../../../tests/harness/test_verify_profiles.py#L121).
- **Docstrings say honestly what kind of evidence each suite gives.** test_hooks.py:1 says 'not proof of Claude event delivery', test_verify_profiles.py:1 says they 'prove no real toolchain run', and test_evidence.py:1 says they 'qualify no real work item'. test_non_mutating.py:1-6 classifies each result as disposable, mock or static, and test_reproducible.py:1-5 says 'Neither absence is a skip'. Sources: [tests/harness/test_hooks.py:1](../../../../tests/harness/test_hooks.py#L1), [tests/harness/test_verify_profiles.py:1](../../../../tests/harness/test_verify_profiles.py#L1), [tests/harness/test_evidence.py:1](../../../../tests/harness/test_evidence.py#L1), [tests/toolchain/test_non_mutating.py:1-6](../../../../tests/toolchain/test_non_mutating.py#L1), [tests/toolchain/test_reproducible.py:1-5](../../../../tests/toolchain/test_reproducible.py#L1).
- **unittest suits the install-free harness, and the runner refuses empty or skipped suites.** scripts/verify.py:84-101 runs stdlib unittest in a reduced environment with no bootstrap. judge_unittest fails a suite that is empty or skips a test, and test_verify_profiles.py:260-283 tests that judgement itself. Sources: [scripts/verify.py:84-101](../../../../scripts/verify.py#L84), [tests/harness/test_verify_profiles.py:260-283](../../../../tests/harness/test_verify_profiles.py#L260).
- **Readable fixture builders and one shared arrangement.** test_specs.py:21-70 builds stories and documents with keyword-argument builders (story(), document()). forward_arrangement.py:45-96 is used by both the runbook and ArrangementTests. Each anchor must match exactly once, and the copy is built beside its destination, so a failed run leaves nothing behind. Sources: [tests/harness/test_specs.py:21-70](../../../../tests/harness/test_specs.py#L21), [tests/harness/forward_arrangement.py:45-96](../../../../tests/harness/forward_arrangement.py#L45).
- **tests/toolchain/support.py is the pattern to spread.** support.py:20-35 centralises paths and constants, :56-62 builds a credential-free environment, and :86-107 owns the copy lifecycle with guarded removal. Test modules import `from support import REPO_ROOT, toolchain` (test_manifests.py:14), and setUpClass cleans up when bootstrap fails (test_non_mutating.py:83-90, test_reproducible.py:27-37). Sources: [tests/toolchain/support.py:20-35](../../../../tests/toolchain/support.py#L20), [tests/toolchain/support.py:56-62](../../../../tests/toolchain/support.py#L56), [tests/toolchain/support.py:86-107](../../../../tests/toolchain/support.py#L86), [tests/toolchain/test_manifests.py:14](../../../../tests/toolchain/test_manifests.py#L14), [tests/toolchain/test_non_mutating.py:83-90](../../../../tests/toolchain/test_non_mutating.py#L83), [tests/toolchain/test_reproducible.py:27-37](../../../../tests/toolchain/test_reproducible.py#L27).
- **Test names and comments say what is tested and why.** Names read as sentences, such as test_hooks.py:459 test_a_forged_cwd_never_chooses_a_root_outside_the_home_checkout. Comments explain why, at test_hooks.py:51 ('Naming a key isn't reading it.'), :352-355 and :605, and test_assistant_assets.py:364. Sources: [tests/harness/test_hooks.py:459](../../../../tests/harness/test_hooks.py#L459), [tests/harness/test_hooks.py:51](../../../../tests/harness/test_hooks.py#L51), [tests/harness/test_hooks.py:352-355](../../../../tests/harness/test_hooks.py#L352), [tests/harness/test_hooks.py:605](../../../../tests/harness/test_hooks.py#L605), [tests/harness/test_assistant_assets.py:364](../../../../tests/harness/test_assistant_assets.py#L364).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [THRN-01](#thrn-01) | high | tests | Private run-column guard reads only the first grant of one migration | S | low |
| [THRN-02](#thrn-02) | high | tests | Static pin and launcher guards in tests/toolchain run in no profile | S | low |
| [THRN-03](#thrn-03) | medium | size | test_hooks.py is one 45-test class covering seven subjects | M | low |
| [THRN-04](#thrn-04) | medium | size | test_assistant_assets.py bundles eight suites and the checks they test | M | low |
| [THRN-05](#thrn-05) | medium | modules | Instruction-file checks live in a test module beside a second frontmatter parser | M | medium |
| [THRN-06](#thrn-06) | medium | tests | Three hook tests' names and assertions disagree | S | low |
| [THRN-07](#thrn-07) | medium | errors | Fourteen child processes have no timeout under a shared 60-second cap | S | low |
| [THRN-08](#thrn-08) | medium | duplication | Stub executables, Git fixture repos and script copies are rewritten in each file | M | low |
| [THRN-09](#thrn-09) | medium | duplication | Config roots and harness reports are built four ways, which weakens assertions | S | low |
| [THRN-10](#thrn-10) | medium | duplication | Two seed scanners have drifted apart, and only one looks for jobs | S | low |
| [THRN-11](#thrn-11) | medium | tests | Most error-list assertions fail with only "False is not true" | S | low |
| [THRN-12](#thrn-12) | medium | approach | Five tests assert source text instead of behaviour | S | medium |
| [THRN-13](#thrn-13) | medium | types | The canonical run states are typed by hand instead of read from the generated RunStatus | S | low |
| [THRN-14](#thrn-14) | medium | standards | No lint, format or type configuration covers the harness and toolchain tests | M | low |
| [THRN-15](#thrn-15) | low | structure | test_final_review.py groups tests by the review that found them | S | low |
| [THRN-16](#thrn-16) | low | tests | N4 only works if it runs last against a shared prepared copy | S | low |
| [THRN-17](#thrn-17) | low | tests | launch_env leaves a temporary .env directory behind on every call | S | low |
| [THRN-18](#thrn-18) | low | approach | Two lint rules are enforced only as tests | S | low |
| [THRN-19](#thrn-19) | low | naming | Mutation lambdas and unexplained counts hide intent | S | low |

### <a id="thrn-01"></a>THRN-01: Private run-column guard reads only the first grant of one migration

- **Severity** high · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [tests/harness/test_app_db.py:44-49](../../../../tests/harness/test_app_db.py#L44): Reads 20261105000002_runs.sql only, and re.search keeps the first grant
  - [supabase/migrations/20261105000007_run_admission.sql:7](../../../../supabase/migrations/20261105000007_run_admission.sql#L7): A later column grant to authenticated on public.runs that the guard never reads
  - [supabase/migrations/20261105000023_operations.sql:30](../../../../supabase/migrations/20261105000023_operations.sql#L30): Another later grant the guard never reads
  - [scripts/app_db.py:208-209](../../../../scripts/app_db.py#L208): The db profile denies lease_generation at runtime; nothing checks checkpoint_thread_id
- **Evidence:** Five later migrations (…0003:19, …0007:7, …0012:3, …0014:34, …0023:30) add `grant select (...) on public.runs to authenticated`, and the test reads none of them. A table-level grant would also pass, because the pattern needs a column list.

  ```python
  text = (ROOT / app_db.MIGRATIONS / '20261105000002_runs.sql').read_text()
  grant = re.search(r'grant select \(([^)]*)\) on public\.runs to authenticated', text)
  self.assertNotIn('lease_generation', grant[1])
  self.assertNotIn('checkpoint_thread_id', grant[1])
  ```

- **Why it matters:** The test is named to promise that the private lease and checkpoint columns never reach the authenticated role. Yet a forward migration that grants checkpoint_thread_id passes it, and the db profile's runtime probe covers only lease_generation. So drift at the grant boundary, which this guard exists to catch, goes unseen.
- **Recommendation:** Scan every migration in name order for column-level and table-level grants on public.runs to authenticated. Collect the granted columns and assert they never include the private set or a table-level grant. Add a known-bad fixture (a later grant of checkpoint_thread_id) to show the scan fails on it. Separately, ask the owner of scripts/app_db.py to add a checkpoint_thread_id denial beside the lease_generation case.
- **Rule check:** AGENTS.md and .claude/rules/database.md say migrations only move forward. The fix only reads migrations and edits none. It makes a guard stronger and leaves the db profile's runtime role checks in place.
- **Verification:** confirmed. Verified: the test reads only 20261105000002_runs.sql, and five later migrations grant run columns to authenticated. None grants a private column today. app_db.py:208-209 denies only lease_generation at runtime, and no db check reads checkpoint_thread_id as authenticated.

```python
PRIVATE_RUN_COLUMNS = {'lease_generation', 'checkpoint_thread_id'}

def authenticated_run_columns(sql: str) -> set[str]:
    """Columns granted to authenticated on public.runs across all migrations; '*' marks a table-level grant."""
    found: set[str] = set()
    for columns, roles in GRANT_ON_RUNS.findall(sql):  # optional '(cols)', 'on public.runs', 'to <roles>;'
        if 'authenticated' in roles:
            found |= {c.strip() for c in columns.split(',')} if columns else {'*'}
    return found

# test 1: all migrations joined in name order -> assertFalse(found & (PRIVATE_RUN_COLUMNS | {'*'}), found)
# test 2: base + 'grant select (checkpoint_thread_id) on public.runs to authenticated;' -> caught
```

### <a id="thrn-02"></a>THRN-02: Static pin and launcher guards in tests/toolchain run in no profile

- **Severity** high · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [scripts/verify.py:154-156](../../../../scripts/verify.py#L154): toolchain_scope_tests discovers only test_scaffold_scope.py
  - [tests/toolchain/test_manifests.py:118-207](../../../../tests/toolchain/test_manifests.py#L118): 15 offline pin, lock and runbook tests; run read-only here, all pass in 0.08 s
  - [tests/toolchain/test_non_mutating.py:19-46](../../../../tests/toolchain/test_non_mutating.py#L19): The static N7 launcher ban shares a module with tests that need registry downloads
  - [scripts/toolchain.py:203](../../../../scripts/toolchain.py#L203): check_steps relies on it: 'Tests scan this list for install launchers'
  - [docs/engineering/runbooks/toolchains.md:129](../../../../docs/engineering/runbooks/toolchains.md#L129): The runbook relies on test_manifests.py to catch a pin it does not name
  - [docs/engineering/evidence/US-1.8/summary.md:73](../../../../docs/engineering/evidence/US-1.8/summary.md#L73): Precedent: an unwired toolchain test broke and nobody noticed
- **Evidence:** verify.py builds Step('toolchain_scope_tests', (..., 'unittest', 'discover', '-s', 'tests/toolchain', '-p', 'test_scaffold_scope.py'), root). Its comment says 'Its copies bootstrap from registries, so the rest stays manual'. But test_manifests.py makes no copy: it only reads pyproject.toml, the package.json files, both locks and the runbook. `python3.12 -I -B -m unittest discover -s tests/toolchain -p test_manifests.py` ran 15 tests in 0.079 s, all passing, and wrote nothing. The N7 Launchers class is static too. Nothing else checks that manifests hold exact pins: toolchain check verifies lock freshness and runtime pins, not dependency ranges.
- **Why it matters:** A `^` range in apps/web/package.json with a matching lock, an unqualified dependency bump, or a new `npx` or `uv run` in a package script passes harness, fast and full. DH-09's ban on download-at-runtime launchers and the runbook's pin procedure rest on tests that run only when someone remembers. US-1.8 already records this failure mode for the scope test.
- **Recommendation:** Run the offline toolchain modules in the existing scope step. Move the N7 Launchers class into its own module, and give the offline modules one filename pattern that the step discovers, or list them explicitly. Because they take under a tenth of a second, consider running them in fast as well as full. Add a harness test that fails when a tests/toolchain module is neither matched by that pattern nor on an explicit manual list. Correct the verify.py comment and the development-harness runbook line that say the rest needs registries.
- **Rule check:** DH-09 bans download-at-runtime launchers and never counts a skipped check as green. AGENTS.md says full uses prepared environments and installs nothing. These modules are offline and stdlib-only, so wiring them in adds no install, network call or service.
- **Verification:** confirmed. Verified verify.py:154-156 discovers only test_scaffold_scope.py. Reran test_manifests.py read-only (python3.12 -I -B): 15 tests in 0.089 s, working tree unchanged. The Launchers class reads only manifests and check_steps with a placeholder. The development-harness runbook (line 58) and US-1.8's summary repeat the 'needs registries' claim.

```text
tests/toolchain/
  test_offline_scope.py      (today test_scaffold_scope.py)      toolchain_scope_tests
  test_offline_manifests.py  (today test_manifests.py)           toolchain_scope_tests
  test_offline_launchers.py  (N7, out of test_non_mutating.py)   toolchain_scope_tests
  test_non_mutating.py       N1-N6 on a bootstrapped copy        manual, registries
  test_reproducible.py       fresh-cache bootstrap               manual, registries
verify.py: discover -s tests/toolchain -p 'test_offline_*.py'   (or list the modules and keep today's names)
tests/harness: offline pattern + MANUAL_TOOLCHAIN_MODULES must cover every tests/toolchain/test_*.py
```

### <a id="thrn-03"></a>THRN-03: test_hooks.py is one 45-test class covering seven subjects

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [tests/harness/test_hooks.py:25-699](../../../../tests/harness/test_hooks.py#L25): HookTests: 45 tests and 10 helpers in one class
  - [tests/harness/test_hooks.py:83-137](../../../../tests/harness/test_hooks.py#L83): report_state and fingerprint tests that exercise harness_lib, not the hook
  - [tests/harness/test_hooks.py:139-168](../../../../tests/harness/test_hooks.py#L139): config_errors cases
  - [tests/harness/test_hooks.py:420-436](../../../../tests/harness/test_hooks.py#L420): Git and worktree helpers in the middle of the class
  - [tests/harness/test_hooks.py:552](../../../../tests/harness/test_hooks.py#L552): EDIT_EVENT constant defined after 30 tests
  - [tests/harness/test_hooks.py:695-699](../../../../tests/harness/test_hooks.py#L695): A scripts/verify.py test
- **Evidence:** The file is 703 lines with one class. By subject it holds: PreToolUse guard 6, Stop 1, report freshness and fingerprints 9 (harness_lib), hook-settings config_errors 3 (harness_lib), dispatcher process contract 6, PostToolUse diagnostics 3, worktree session roots and Git failures 16, and verify.py 1. 39 of the 45 tests open their temporary directory inline (`with tempfile.TemporaryDirectory() as ...: root = Path(...)`). The class grew by appending: commit 9a9b60a alone added 277 lines of worktree tests.
- **Why it matters:** To find the tests for a function you search a 700-line class. Because 13 of the tests exercise harness_lib or verify.py, a fingerprinting change has tests here, in test_verify_profiles.py and in test_final_review.py. Each new hook behaviour lands in the same class, and the repeated temp-directory block adds an indentation level and two lines to almost every test.
- **Recommendation:** Split by unit under test into focused modules that share a harness support module. Move the harness_lib and verify.py tests to their own modules. Give each class a setUp that uses `self.enterContext(tempfile.TemporaryDirectory())` (Python 3.11+) instead of a with-block in every test.
- **Rule check:** DH-05 requires these hook fixtures (malformed JSON, metacharacters, symlinks, timeouts, missing executable, unsupported events). The split moves every case and drops none, and DH-03 keeps them under tests/harness/.
- **Verification:** confirmed. Verified one class with 45 tests and 10 helpers; an ast count finds 39 tests opening TemporaryDirectory inline, and 9a9b60a added 277 lines to the file.

```text
tests/harness/harness_support.py   ROOT, load_dispatch(), dispatch(raw, script=None, env=None), executable_stub(),
                                   fixture_repo(..., worktrees=()), copy_dispatcher(home), valid_report(root)
test_hook_guard.py         PreToolUse path and command policy, Stop once                         7 tests
test_hook_process.py       malformed/oversized input, unsupported events, deadlines, no library  6 tests
test_hook_diagnostics.py   PostToolUse domains and ruff outcomes                                 3 tests
test_hook_worktrees.py     session_root, Git failure and timeout, per-root Stop                 16 tests
test_inputs.py             input_manifest, fingerprint, report_state (+2 from test_verify_profiles.py, +1 from test_final_review.py)
config_errors cases -> test_config_errors.py on valid_root; unknown profile -> test_verify_profiles.py
base setUp: self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
```

### <a id="thrn-04"></a>THRN-04: test_assistant_assets.py bundles eight suites and the checks they test

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 1
- **Where:**
  - [tests/harness/test_assistant_assets.py:75-240](../../../../tests/harness/test_assistant_assets.py#L75): About 165 lines of checker and fixture helpers before the first test
  - [tests/harness/test_assistant_assets.py:243](../../../../tests/harness/test_assistant_assets.py#L243): RuleLinkTests, then AgentsMappingTests at 290 (config_errors)
  - [tests/harness/test_assistant_assets.py:350](../../../../tests/harness/test_assistant_assets.py#L350): AdapterStatusTests: version probing with stub executables
  - [tests/harness/test_assistant_assets.py:546](../../../../tests/harness/test_assistant_assets.py#L546): ReportTests: verify.main
  - [tests/harness/test_assistant_assets.py:574](../../../../tests/harness/test_assistant_assets.py#L574): InstructionAssetTests and IngestionAssetTests on the real tree
  - [tests/harness/test_assistant_assets.py:705](../../../../tests/harness/test_assistant_assets.py#L705): ArrangementTests for forward_arrangement.py
- **Evidence:** The file has 783 lines, 8 classes and 53 tests. They cover rule links, the AGENTS.md mapping, assistant adapter status, activation refusals, the verify report, real instruction assets, the ingestion grammar and the forward arrangement. Lines 75-240 hold the frontmatter parser and policy, the link checker, a hand-written glob matcher, the grammar check, the synthetic root builder, the stub writers and the specs CLI wrapper. The file name fits the instruction-asset classes but not the adapter, report or arrangement tests.
- **Why it matters:** Someone looking for the adapter-status or arrangement tests must know they sit under 'assistant assets'. Any change to valid_root or the stub helpers touches five classes in one file. And the checker code shares a module with the tests that exercise it.
- **Recommendation:** Split into one module per subject. Move the fixture helpers to the harness support module, and move the checker functions into scripts (see the finding on instruction-file checks).
- **Rule check:** The DH-09 harness scope (configuration and frontmatter validation, known-good and known-bad fixtures) stays the same. Tests move and none is dropped.
- **Verification:** confirmed. Verified 8 classes and 53 tests in 783 lines, with module-level checker and fixture helpers at 75-240.

```text
scripts/instruction_checks.py (or harness_lib)  frontmatter(), frontmatter_errors(), broken_links(),
                                                rule_globs(), glob_matches(), ingestor_grammar_errors()
tests/harness/harness_support.py                valid_root(), valid_agents(), edit_json(), write_stub(),
                                                version_stub(), specs_cli(), sha256(), story_body()
test_config_errors.py        RuleLinkTests, AgentsMappingTests, ActivationRefusalTests (+ hook-settings cases from test_hooks.py)
test_adapter_status.py       AdapterStatusTests, ReportTests
test_instruction_assets.py   InstructionAssetTests, IngestionAssetTests
test_forward_arrangement.py  ArrangementTests
```

### <a id="thrn-05"></a>THRN-05: Instruction-file checks live in a test module beside a second frontmatter parser

- **Severity** medium · **Dimension** modules · **Effort** M · **Risk** medium · **Occurrences** 8
- **Where:**
  - [tests/harness/test_assistant_assets.py:75-105](../../../../tests/harness/test_assistant_assets.py#L75): frontmatter() and frontmatter_errors(): allowed keys, name matches path, model must be inherit
  - [tests/harness/test_assistant_assets.py:115-130](../../../../tests/harness/test_assistant_assets.py#L115): broken_links(): link and fragment resolution
  - [tests/harness/test_assistant_assets.py:133-154](../../../../tests/harness/test_assistant_assets.py#L133): rule_globs() and a hand-written glob matcher
  - [tests/harness/test_assistant_assets.py:161-170](../../../../tests/harness/test_assistant_assets.py#L161): ingestor_grammar_errors()
  - [scripts/harness_lib.py:321-335](../../../../scripts/harness_lib.py#L321): config_errors parses frontmatter again, in a different way
- **Evidence:** A missing name or description is a named project_configuration error. Allowed keys, the name-to-path match and `model: inherit` are checked only by unittest assertions on the real tree (test_assistant_assets.py:594-597). The two readers split the header differently:

  ```python
  # test_assistant_assets.py:79
  header = text[4:].split('\n---\n', 1)[0]
  # scripts/harness_lib.py, inside config_errors
  header = text.split('---', 2)[1]
  if not any(line.startswith('name:') for line in header.splitlines()):
  ```

- **Why it matters:** Two readers of the same frontmatter can disagree: harness_lib's split ends the header at the first '---' anywhere, even inside a value, while the test's reader needs a line of its own. A policy violation shows up as a failing test inside harness_behavior_tests, not as a named project_configuration error in the report. And because only the test calls these checks, no skill or other validator can reuse them.
- **Recommendation:** Move the eight functions into scripts, in harness_lib or a scripts/instruction_checks.py that it imports. Share one frontmatter parser, and have config_errors report their errors. Keep the known-good and known-bad fixtures as tests. Point those tests at the moved functions before switching config_errors over.
- **Rule check:** DH-05 says substantive checks live in repository scripts. AGENTS.md's rule table names project_configuration in scripts/verify.py as the configuration check. Every check is kept; only where it lives and how it is reported change.
- **Verification:** revised. Verified the eight module-level functions and the second parser in config_errors, at harness_lib.py:321-335 (location corrected from 320-334). Revised the impact: the unittest output names the failing test, so a violation is not anonymous, only reported under harness_behavior_tests rather than project_configuration. harness_lib's rule_link_errors checks only that each rule links a check target, so broken_links is the only check that resolves every link.

```text
scripts/instruction_checks.py
  parse_frontmatter(text) -> dict[str, str] | None   one parser for skills, agents and rules
  frontmatter_errors(root) -> list[str]               keys, name/path, model inherit, name/description present
  broken_link_errors(paths, root) -> list[str]
  ingestor_grammar_errors(text) -> list[str]
harness_lib.config_errors(root): errors += frontmatter_errors(root) + broken_link_errors(...)
tests/harness/test_instruction_checks.py: fixtures and assertions only
```

### <a id="thrn-06"></a>THRN-06: Three hook tests' names and assertions disagree

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [tests/harness/test_hooks.py:35-53](../../../../tests/harness/test_hooks.py#L35): Named 'without echo', but only the deny decision is asserted
  - [tests/harness/test_hooks.py:61-73](../../../../tests/harness/test_hooks.py#L61): Named 'does not execute command input', but mostly asserts the command denylist
  - [tests/harness/test_hooks.py:75-81](../../../../tests/harness/test_hooks.py#L75): Named 'never claims live proof', but the reason is never read
  - [.claude/hooks/dispatch.py:106](../../../../.claude/hooks/dispatch.py#L106): The denial reason is a fixed string today, so 'no echo' holds only by construction
  - [.claude/hooks/dispatch.py:199](../../../../.claude/hooks/dispatch.py#L199): Stop's 'does not certify application completion' text, which no test reads
- **Evidence:** test_stop_blocks_once_and_never_claims_live_proof asserts only `response['decision'] == 'block'` and that the retry carries no decision. The secret-file test asserts only the deny decision:

  ```python
  def test_secret_files_rejected_without_echo(self):
      ...
          response = hook.handle(root, {'hook_event_name': 'PreToolUse',
                                       'tool_name': 'Read', 'tool_input': {'file_path': name}})
          self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')
  ```

- **Why it matters:** A change that puts the path into the denial reason, or drops Stop's statement that it certifies nothing, still passes the tests named after those guarantees. When the mixed test fails, its name points at the wrong behaviour.
- **Recommendation:** Assert what each name promises. For each secret name and command, assert `name not in reason` inside a subTest. Read Stop's reason and assert it says the hook certifies no completion. Move the denylist cases out of the non-execution test into their own test driven by subTest.
- **Rule check:** DH-05 says stdout carries only the documented response and diagnostics are redacted. The change only adds assertions and loosens nothing.
- **Verification:** confirmed. Verified: the three tests assert only the decision fields; dispatch.py:106 returns a fixed denial reason, and dispatch.py:197-199 ends Stop's reason with 'This hook does not certify application completion', which no test reads.

### <a id="thrn-07"></a>THRN-07: Fourteen child processes have no timeout under a shared 60-second cap

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 14
- **Where:**
  - [scripts/verify.py:67-73](../../../../scripts/verify.py#L67): One timeout=60 covers the whole harness suite; on expiry only 'TimeoutExpired' is kept
  - [tests/harness/test_specs.py:265](../../../../tests/harness/test_specs.py#L265): One of 8 specs.py runs in this file without a timeout
  - [tests/harness/test_verify_profiles.py:47](../../../../tests/harness/test_verify_profiles.py#L47): git in setUp without a timeout, run for each of 28 tests
  - [tests/harness/test_tool_keys_env.py:32](../../../../tests/harness/test_tool_keys_env.py#L32): /bin/sh running Makefile lines, no timeout
  - [tests/harness/forward_arrangement.py:92](../../../../tests/harness/forward_arrangement.py#L92): specs.py render with no timeout
  - [tests/toolchain/support.py:83](../../../../tests/toolchain/support.py#L83): git with no timeout while setting up a copy
  - [tests/harness/test_assistant_assets.py:229-231](../../../../tests/harness/test_assistant_assets.py#L229): specs_cli: the same call, with timeout=30
- **Evidence:** An ast scan of the 20 files finds 14 subprocess.run calls with no timeout argument, 8 of them in test_specs.py. The harness reports from 2026-11-12 ran 290 tests in 25.4 to 26.6 s against verify.py's `timeout=60`. When that timeout expires, run_check records status 'error' with output 'TimeoutExpired' and exits 2 ('could not run'), discarding everything the suite printed.
- **Why it matters:** A hang in any of these children, such as Git waiting on a prompt or a regression in specs.py, uses up the whole budget. It then shows as an error that names no test, and the Stop hook blocks on a missing harness pass. As stories add more process-level tests, the suite creeps toward the cap and nothing shows which tests cost most.
- **Recommendation:** Route every child process through one support helper, `run_cli`, with a default timeout of 30 s (as specs_cli already uses), so a hang fails the test that caused it. Ask the scripts owner to add unittest's `--durations 10` (Python 3.12) to the harness command and to keep the tail of partial output when the suite times out.
- **Rule check:** DH-05 asks for deadlines and bounded output, and DH-09 never counts a timed-out check as green. Per-test timeouts turn an anonymous suite error into a named failure.
- **Verification:** revised. Recounted 14 subprocess.run calls without a timeout; the one Popen waits with timeout=10. The newest harness report, written after the reviewer read the 15:53Z one, ran the same 290 tests in 25.4 s, so the evidence now cites both. The 60-second cap and the discarded output are as cited (verify.py:67-73).

### <a id="thrn-08"></a>THRN-08: Stub executables, Git fixture repos and script copies are rewritten in each file

- **Severity** medium · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 12
- **Where:**
  - [tests/harness/test_assistant_assets.py:216-222](../../../../tests/harness/test_assistant_assets.py#L216): write_stub: shell stub that records argv
  - [tests/harness/test_hooks.py:278-283](../../../../tests/harness/test_hooks.py#L278): fake_ruff
  - [tests/harness/test_hooks.py:540-543](../../../../tests/harness/test_hooks.py#L540): fake git
  - [tests/harness/test_disposable_guard.py:87-89](../../../../tests/harness/test_disposable_guard.py#L87): fake docker
  - [tests/harness/test_hooks.py:420-422](../../../../tests/harness/test_hooks.py#L420): git with reduced_env(): no HOME, so no global config
  - [tests/harness/test_verify_profiles.py:42-47](../../../../tests/harness/test_verify_profiles.py#L42): git with the inherited environment and only gpgsign off; repeated at :249
  - [tests/toolchain/support.py:79-83](../../../../tests/toolchain/support.py#L79): git with HOME kept, gpgsign off and core.hooksPath=/dev/null
  - [tests/harness/test_hooks.py:535-539](../../../../tests/harness/test_hooks.py#L535): Copies dispatch.py and harness_lib.py; again at :665 and test_generate_contracts.py:63
- **Evidence:** Counted by reading the 20 files: 4 stub writers, 4 Git repository setups in 3 variants, and 4 blocks that copy scripts into a temp root. In addition, 12 files repeat ROOT and the sys.path insert, and scripts/specs.py is loaded under two module names (test_specs.py:14, test_assistant_assets.py:42).

  ```python
  # test_hooks.py:421, env=reduced_env()
  ['git', '-C', dir, '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', ...]
  # test_verify_profiles.py:42, inherited environment
  ['git', '-C', root, '-c', 'user.name=t', '-c', 'user.email=t@invalid', '-c', 'commit.gpgsign=false']
  ```

- **Why it matters:** When the suite runs outside verify.py, for example `python3.12 -m unittest` from a shell, the 28 setUp commits in test_verify_profiles.py read the developer's global Git config, so a global core.hooksPath or template hooks run inside the fixture. support.py's extra hardening never reached that file. Every fix to a stub or repository recipe must be found and repeated by hand.
- **Recommendation:** Add tests/harness/harness_support.py, modelled on tests/toolchain/support.py, which already re-exports `toolchain` and owns the copy lifecycle. It should provide one hardened `fixture_repo()`, `executable_stub()`, `copy_scripts()` and `run_cli()` with a default timeout, and re-export the script modules so test files stop editing sys.path.
- **Rule check:** AGENTS.md says harness checks install nothing; the module uses only the standard library. verify.py:63 says tests receive no inherited configuration, and one hardened recipe extends that to direct runs.
- **Verification:** confirmed. Verified 4 stub writers, 3 Git recipes (reduced_env without HOME in test_hooks.py, the inherited environment in test_verify_profiles.py, HOME kept with hooksPath off in support.py), 4 script-copy blocks, 12 files inserting scripts/ into sys.path, and specs.py loaded as autobots_specs and autobots_specs_for_assets.

```python
# tests/harness/harness_support.py (standard library only)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib, verify            # tests: from harness_support import ROOT, verify
GIT_ENV = {**harness_lib.reduced_env(), 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
def fixture_repo(root: Path, *, worktrees: Sequence[str] = ()) -> Path: ...   # hooksPath and gpgsign off
def executable_stub(path: Path, body: str, *, record: Path | None = None) -> Path: ...
def copy_scripts(home: Path, *relative: str) -> None: ...
def run_cli(argv: Sequence[str], *, input: bytes | None = None, env=None, timeout: float = 30): ...
```

### <a id="thrn-09"></a>THRN-09: Config roots and harness reports are built four ways, which weakens assertions

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 8
- **Where:**
  - [tests/harness/test_assistant_assets.py:173-198](../../../../tests/harness/test_assistant_assets.py#L173): valid_root: a complete synthetic root, so one change gives one error
  - [tests/harness/test_hooks.py:139-151](../../../../tests/harness/test_hooks.py#L139): Partial root built inline; asserts a count of matching errors
  - [tests/harness/test_hooks.py:153-168](../../../../tests/harness/test_hooks.py#L153): The same inline root; asserts with any()
  - [tests/harness/test_hooks.py:329-337](../../../../tests/harness/test_hooks.py#L329): A third inline root; asserts with any()
  - [tests/harness/test_hooks.py:26-33](../../../../tests/harness/test_hooks.py#L26): valid_report
  - [tests/harness/test_verify_profiles.py:20-23](../../../../tests/harness/test_verify_profiles.py#L20): harness_records: the same three check records, retyped
  - [tests/harness/test_evidence.py:267-277](../../../../tests/harness/test_evidence.py#L267): write_report and passed_record
  - [tests/harness/test_assistant_assets.py:551-553](../../../../tests/harness/test_assistant_assets.py#L551): passing_check
- **Evidence:** The inline roots in test_hooks.py copy autobots.json and settings.json but create no rules, skills, agents or AGENTS.md. config_errors therefore returns many unrelated errors, so those tests can only check `any('only the reviewed hooks' in error ...)` or count matches. Tests built on valid_root assert the exact list instead, e.g. `self.assertEqual(config_errors(self.root), ['AGENTS.md: missing the "## Rule checks and review" section.'])` (test_assistant_assets.py:306). The three passing harness check records are typed out twice, at test_hooks.py:30-33 and test_verify_profiles.py:21-23.
- **Why it matters:** The inline-root tests would still pass if the edit also caused a second, wrong error. Any change to the report schema or to the required checks has to be made in four builders.
- **Recommendation:** Move valid_root, valid_agents and edit_json into the support module, and rebuild the three test_hooks.py cases on valid_root with exact-list assertions. Provide one `harness_report(root, **overrides)` builder for test_hooks.py, test_verify_profiles.py and test_evidence.py.
- **Rule check:** DH-09 asks the harness for known-good and known-bad checker fixtures. One valid baseline per check makes each known-bad case differ by exactly one change.
- **Verification:** confirmed. Verified: the inline roots at test_hooks.py:139-168 and 329-337 copy only autobots.json and settings.json, so their tests count or any() matches, while the valid_root tests assert exact lists (test_assistant_assets.py:306 and 313); the three passing records are typed twice.

### <a id="thrn-10"></a>THRN-10: Two seed scanners have drifted apart, and only one looks for jobs

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [tests/harness/test_app_db.py:31-35](../../../../tests/harness/test_app_db.py#L31): Reference seeds: checks 'runs' and 'api_key', but no 'job'
  - [tests/harness/test_disposable_guard.py:127-131](../../../../tests/harness/test_disposable_guard.py#L127): Fixture seeds: checks 'job', but no 'runs' or 'api_key'
  - [scripts/app_db.py:175-189](../../../../scripts/app_db.py#L175): db seed cases check repeatability and profiles, not jobs
- **Evidence:** Pending inference jobs live in app_private.run_jobs. No term in the reference-seed scan matches that table name, because 'run_jobs' does not contain 'runs'.

  ```python
  # test_app_db.py:33, supabase/seeds/reference.sql
  for word in ('create table', 'alter table', 'drop ', 'password', 'api_key', 'runs'):
  # test_disposable_guard.py:129, tests/db/seeds/fixtures.sql
  for word in ('create table', 'alter table', 'drop ', 'password', 'job'):
  ```

- **Why it matters:** The 'no pending inference jobs in seeds' rule is checked directly for fixture seeds but only indirectly for reference seeds, and a fix to one list never reaches the other. Bare substrings also reject harmless comments that contain 'drop ' or 'runs'.
- **Recommendation:** Write one `seed_violations(text)` helper with the union of both term lists plus `run_jobs`, apply it to both seed files, and give each term a known-bad fixture string. Keep the secret terms (`password`, `api_key`) as plain substrings. If a bare table term rejects a harmless comment, narrow only that term to statement shapes (`insert into app_private.run_jobs`, `insert into public.runs`), with a known-bad fixture proving the insert is still caught.
- **Rule check:** AGENTS.md and .claude/rules/database.md forbid DDL, real credentials and pending inference jobs in seeds. The helper keeps every current term, adds the missing ones and narrows a term only with a fixture that proves the guard still holds.
- **Verification:** revised. Verified both term lists and that 'run_jobs' does not contain 'runs'; the db seed cases (app_db.py:175-189) check repeatability and profiles only. Revised the recommendation so the secret terms stay plain substrings: matching only statement shapes would let a password or key in a value pass.

### <a id="thrn-11"></a>THRN-11: Most error-list assertions fail with only "False is not true"

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 50
- **Where:**
  - [tests/harness/test_specs.py:99](../../../../tests/harness/test_specs.py#L99): One of 31 message-less any() assertions in this file
  - [tests/harness/test_evidence.py:155](../../../../tests/harness/test_evidence.py#L155): One of 8 here, while rejected() at :107 already prints the list
  - [tests/harness/test_assistant_assets.py:283](../../../../tests/harness/test_assistant_assets.py#L283): Message-less any() over config_errors
  - [tests/harness/test_hooks.py:38-42](../../../../tests/harness/test_hooks.py#L38): 11 names in a loop, with no subTest and no message
  - [tests/toolchain/test_manifests.py:128-135](../../../../tests/toolchain/test_manifests.py#L128): Five mutations without subTest; a failure doesn't say which one
  - [tests/harness/test_verify_profiles.py:52](../../../../tests/harness/test_verify_profiles.py#L52): stdout and stderr replaced by mocks, so an unexpected exit code comes with no output
- **Evidence:** An ast count finds 47 of the 60 `assertTrue(any(...))` calls without a message, plus 3 loops over cases with no subTest or message (test_hooks.py:38, test_manifests.py:128 and :141).

  ```python
  self.assertTrue(any("stale" in issue for issue in self.errors(document(), navigation=True)))
  # compare test_evidence.py:112
  self.assertTrue(any(needle in error for error in errors), f'{needle!r} not in {errors}')
  ```

- **Why it matters:** When a checker's wording or behaviour changes, the failure shows neither what the checker produced nor which case failed. Each such failure needs a rerun with print statements before anyone can see what went wrong.
- **Recommendation:** Add a shared assertion to a harness TestCase base that prints the list when no error mentions the expected text. Use subTest in every loop over cases. Capture verify output with contextlib.redirect_stdout(io.StringIO()) so it can be attached to a failure.
- **Rule check:** none
- **Verification:** confirmed. Recounted with ast: 60 assertTrue(any(...)) calls, 47 without a message (31 in test_specs.py, 8 in test_evidence.py), plus the three loops without subTest; test_verify_profiles.py:52 patches stdout and stderr.

```python
class HarnessTestCase(unittest.TestCase):
    def assertMentions(self, errors: Sequence[str], needle: str) -> None:
        if not any(needle in error for error in errors):
            self.fail(f'{needle!r} not in {list(errors)}')
```

### <a id="thrn-12"></a>THRN-12: Five tests assert source text instead of behaviour

- **Severity** medium · **Dimension** approach · **Effort** S · **Risk** medium · **Occurrences** 5
- **Where:**
  - [tests/harness/test_release_qualification.py:159-163](../../../../tests/harness/test_release_qualification.py#L159): Expects the argparse call spelled with single quotes
  - [tests/harness/test_supabase_stack.py:120-122](../../../../tests/harness/test_supabase_stack.py#L120): Expects the choices tuple spelled with single quotes
  - [tests/harness/test_final_review.py:91-93](../../../../tests/harness/test_final_review.py#L91): Reads inspect.getsource(persistent_install.goal)
  - [tests/harness/test_fault_fixtures.py:80-85](../../../../tests/harness/test_fault_fixtures.py#L80): Expects double-quoted state literals in check.py
  - [tests/harness/test_app_db.py:21-29](../../../../tests/harness/test_app_db.py#L21): Regex over schema_release.py, since the service package can't be imported here
- **Evidence:** Found by grepping for `.py').read_text()` and `inspect.getsource`:

  ```python
  source = (ROOT / 'scripts/qualify_release.py').read_text()
  self.assertIn("'--authorized-micro-usd', type=int, required=True", source)
  ...
  source = (ROOT / 'scripts/supabase_stack.py').read_text()
  self.assertIn("choices=('preflight', 'qualify')", source)
  ```

- **Why it matters:** These tests fail when quotes change or a line wraps, even though behaviour is the same. They pass when behaviour changes but the text stays, for example if the refusal moved after the paid call. They also stop ruff format, whose default quote style is double, from being adopted for scripts without breaking two of them.
- **Recommendation:** Test behaviour where the code allows it. `stack.main(['start'])` raising SystemExit works today, because supabase_stack.main accepts argv. For qualify_release, expose a build_parser() and check in-process that parsing without --authorized-micro-usd exits 2; never launch the paid-path script from a test. For persistent_install, extract the pre-goal refusal into a function that goal calls first, and test it with a stub `sql`. Keep the schema_release regex, since the harness can't import the service, and say why in its docstring.
- **Rule check:** DH-09 says to avoid tests that merely restate implementation. The paid-run cap and the pre-goal refusal stay required. The two script refactors should be their own bounded work items, not edits made as part of this review.
- **Verification:** confirmed. Verified the five source-text assertions. supabase_stack.main(argv) parses before any side effect, so main(['start']) raises SystemExit(2), while qualify_release.main() reads sys.argv and needs a build_parser() first.

```python
def test_no_persistent_start_exists(self):
    with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
        stack.main(['start'])
    self.assertEqual(raised.exception.code, 2)
```

### <a id="thrn-13"></a>THRN-13: The canonical run states are typed by hand instead of read from the generated RunStatus

- **Severity** medium · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [tests/harness/test_fault_fixtures.py:80-86](../../../../tests/harness/test_fault_fixtures.py#L80): Ten states typed into the test
  - [contracts/generated/openapi.json:4916](../../../../contracts/generated/openapi.json#L4916): RunStatus enum, generated from the Pydantic contract
  - [tests/faults/state/check.py:10-19](../../../../tests/faults/state/check.py#L10): TERMINAL and PERMITTED hold the checker's states
  - [tests/faults/state/check.py:65](../../../../tests/faults/state/check.py#L65): Unguarded main() call, so the test can't import the checker
- **Evidence:** The test types the ten states by hand and looks for each one in the checker's source text:

  ```python
  states = {'queued', 'running', 'waiting_input', 'waiting_approval', 'paused', 'verifying', 'cancelling',
            'succeeded', 'failed', 'cancelled'}
  source = (STATE / 'check.py').read_text()
  for state in states:
      self.assertIn(f'"{state}"', source)
  ```

- **Why it matters:** The test exists to keep the fault checker in step with the canonical states, but its reference list is a third hand copy. If RunStatus gains a state, neither list changes and the test still passes. It also checks only one direction, so a stale extra state left in the checker goes unnoticed.
- **Recommendation:** Read the RunStatus enum from contracts/generated/openapi.json with json. Read the checker's states from TERMINAL and PERMITTED with ast.literal_eval, or import them once check.py guards its main() in its own work item. Assert the two sets are equal.
- **Rule check:** AGENTS.md says to use the canonical states from the preserved Option B contract, and DH-06 makes the generated OpenAPI the public source. The test only reads the generated file and edits nothing generated.
- **Verification:** confirmed. Verified the hand-typed set, RunStatus at openapi.json:4916 with the same ten values, TERMINAL and PERMITTED as literals at check.py:10-19, and the unguarded main() at line 65; the sketched literal_eval read yields the ten states today.

```python
contract = json.loads((ROOT / 'contracts/generated/openapi.json').read_text())
run_status = set(contract['components']['schemas']['RunStatus']['enum'])
values = {t.id: ast.literal_eval(n.value) for n in ast.parse((STATE / 'check.py').read_text()).body
          if isinstance(n, ast.Assign) for t in n.targets if getattr(t, 'id', '') in ('TERMINAL', 'PERMITTED')}
known = values['TERMINAL'] | set(values['PERMITTED']) | set().union(*values['PERMITTED'].values())
self.assertEqual(known, run_status)
```

### <a id="thrn-14"></a>THRN-14: No lint, format or type configuration covers the harness and toolchain tests

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 20
- **Where:**
  - [services/agent/pyproject.toml:41](../../../../services/agent/pyproject.toml#L41): The only ruff configuration, and it covers the service alone
  - [tests/harness/test_specs.py:184](../../../../tests/harness/test_specs.py#L184): 194-character line; this file uses double quotes (299 to 5)
  - [tests/harness/test_hooks.py:70](../../../../tests/harness/test_hooks.py#L70): 141-character line; this file uses single quotes (664 to 1)
  - [tests/harness/test_disposable_guard.py:4](../../../../tests/harness/test_disposable_guard.py#L4): Unused import json
  - [tests/harness/test_assistant_assets.py:254](../../../../tests/harness/test_assistant_assets.py#L254): Trailing whitespace
  - [tests/harness/test_assistant_assets.py:656](../../../../tests/harness/test_assistant_assets.py#L656): Re-imports verify, already imported at :31
  - [tests/harness/test_tool_keys_env.py:9-15](../../../../tests/harness/test_tool_keys_env.py#L9): The one module that orders imports differently from the others
- **Evidence:** The service's own rules (E, F, W, I, B, UP, ASYNC, RUF; line length 100), run isolated over tests/harness and tests/toolchain, give 456 findings. 431 are E501, and 132 remain even at 120 columns. There are also 20 I001 and one each of F401, W291, RUF012, RUF059 and E402. `ruff format --check` would reformat all 20 files. With `force-sort-within-sections = true`, the I001 count drops from 20 to 7, so the import style most files already follow can be written down as a rule.
- **Why it matters:** Two quote styles, two import orders and lines up to 194 characters make the files slower to read and review. Nothing stops an unused import or a duplicate import from landing. With no type checker, the helpers' annotations are documentation only.
- **Recommendation:** Give root Python (scripts/, tests/, .claude/hooks/) one ruff configuration. Run it check-only in fast and full with the prepared ruff, so the harness profile stays install-free. Tighten in steps: first F, W, B, UP and I with force-sort-within-sections; then E501 at 120 with a per-file baseline. Adopt the formatter with quote-style single only after the source-text tests stop depending on quoting.
- **Rule check:** DH-06 calls for Ruff for lint and format, with check and format as separate gates and autofix as an explicit operation. AGENTS.md keeps the harness profile install-free, so the gate runs in fast and full with the prepared ruff.
- **Verification:** revised. Reran ruff 0.17.3 read-only with --no-cache --isolated: 456 findings (431 E501, 20 I001 and one each of F401, W291, RUF012, RUF059 and E402), 132 E501 at 120 columns, and 20 of 20 files to reformat. Corrected the force-sort count from 6 to 7 and the quote counts (tokenize) to 299 to 5 and 664 to 1.

```toml
# ruff.toml at the repository root; services/agent keeps its own [tool.ruff]
target-version = "py312"
line-length = 120
[lint]
select = ["E", "F", "W", "I", "B", "UP", "RUF"]
[lint.isort]
force-sort-within-sections = true
[format]
quote-style = "single"
```

### <a id="thrn-15"></a>THRN-15: test_final_review.py groups tests by the review that found them

- **Severity** low · **Dimension** structure · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [tests/harness/test_final_review.py:1](../../../../tests/harness/test_final_review.py#L1): Docstring: 'What US-11.12's review of the harness found, held in place.'
  - [tests/harness/test_final_review.py:29](../../../../tests/harness/test_final_review.py#L29): qualify_web.run_problems
  - [tests/harness/test_final_review.py:52](../../../../tests/harness/test_final_review.py#L52): Fingerprint test; others live in test_hooks.py and test_verify_profiles.py
  - [tests/harness/test_final_review.py:74](../../../../tests/harness/test_final_review.py#L74): persistent_install refusals
  - [tests/harness/test_final_review.py:96](../../../../tests/harness/test_final_review.py#L96): qualify_worker_inference.request_shape_problems
  - [tests/harness/test_final_review.py:112](../../../../tests/harness/test_final_review.py#L112): toolchain.snapshot
  - [tests/harness/test_final_review.py:120](../../../../tests/harness/test_final_review.py#L120): generate_contracts.main, while test_generate_contracts.py tests the same module
- **Evidence:** Seven classes test seven different scripts: qualify_web, harness_lib, verify, persistent_install, qualify_worker_inference, toolchain and generate_contracts. No test_qualify_web.py, test_persistent_install.py or test_qualify_worker_inference.py exists, so these are those scripts' only harness tests. ContractDrift sits apart from test_generate_contracts.py.
- **Why it matters:** Someone changing qualify_web.py or persistent_install.py won't find these tests by file name. The next review is likely to add another file of the same mixed kind.
- **Recommendation:** Use one test module per script under test. Move ContractDrift into test_generate_contracts.py, Domains into test_verify_profiles.py and Fingerprint into the inputs module. Give BrowserRuns, PaidWorkerGuard, RequestShape and NonMutationGuard modules named after their scripts. Keep 'found by US-11.12's review' in each class docstring.
- **Rule check:** The review's ground rules keep story citations in comments, so the US-11.12 note moves into class docstrings rather than staying in the file name. DH-03 fixes only tests/harness/ as the location.
- **Verification:** revised. Verified seven classes for seven scripts and no test module named after qualify_web, persistent_install or qualify_worker_inference. Lowered to low: grep finds these tests, and the cost is discoverability in a 146-line file, not risk to a change.

### <a id="thrn-16"></a>THRN-16: N4 only works if it runs last against a shared prepared copy

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [tests/toolchain/test_non_mutating.py:79](../../../../tests/toolchain/test_non_mutating.py#L79): Docstring: 'Test names set the order: drift goes last'
  - [tests/toolchain/test_non_mutating.py:187-196](../../../../tests/toolchain/test_non_mutating.py#L187): test_zz_n4 uninstalls idna and never restores it
  - [tests/toolchain/test_non_mutating.py:100-111](../../../../tests/toolchain/test_non_mutating.py#L100): edit() already restores by bootstrapping again
- **Evidence:** PreparedCopy bootstraps one copy in setUpClass. test_zz_n4 runs `uv pip uninstall idna` and leaves the environment drifted. It relies on unittest's alphabetical method order to run last.
- **Why it matters:** Running with -k, under a runner that reorders tests, or after adding a test whose name sorts after zz, gives later tests a drifted environment, so they fail for the wrong reason.
- **Recommendation:** Restore the environment in a cleanup, as edit() does for pyproject changes (`self.addCleanup(support.bootstrap_copy, self.root)`), and drop the zz prefix. Alternatively, give N4 its own class and its own copy.
- **Rule check:** none
- **Verification:** confirmed. Verified test_zz_n4 uninstalls idna and restores nothing, relying on unittest's alphabetical order, while edit() restores through bootstrap_copy.

### <a id="thrn-17"></a>THRN-17: launch_env leaves a temporary .env directory behind on every call

- **Severity** low · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 8
- **Where:**
  - [tests/harness/test_tool_keys_env.py:22-35](../../../../tests/harness/test_tool_keys_env.py#L22): Creates the directory with mkdtemp and never removes it
  - [tests/harness/test_tool_keys_env.py:44-47](../../../../tests/harness/test_tool_keys_env.py#L44): Five calls in one loop
- **Evidence:** The fixtures are key-shaped values such as `OPENROUTER_API_KEY=sk-or-fixture` and `GITHUB_TOKEN='github_pat_fixture; touch pwned4'`. Each run makes 8 calls (6 in the first test, 1 in each of the next two), and nothing deletes the directories.

  ```python
  work = Path(tempfile.mkdtemp(prefix='tool-keys-env-'))
  (work / '.env').write_text(dotenv)
  ```

- **Why it matters:** Every harness run leaves eight directories with .env files in the temp directory, and their key-shaped values can trip local secret scanners. Every other harness test cleans up after itself.
- **Recommendation:** Let the test own the directory: pass `Path(self.enterContext(tempfile.TemporaryDirectory()))` into launch_env, or make launch_env a context manager.
- **Rule check:** none
- **Verification:** confirmed. Verified launch_env uses mkdtemp with no cleanup and runs 8 times per suite (6, 1 and 1).

### <a id="thrn-18"></a>THRN-18: Two lint rules are enforced only as tests

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [tests/harness/test_shared_form_controls.py:9-19](../../../../tests/harness/test_shared_form_controls.py#L9): Regex over raw TSX text
  - [tests/toolchain/test_scaffold_scope.py:13-44](../../../../tests/toolchain/test_scaffold_scope.py#L13): AST scan for banned SDK imports, run only in full
  - [apps/web/eslint.config.mjs:4-8](../../../../apps/web/eslint.config.mjs#L4): No restricted-syntax rule for raw form controls
- **Evidence:** RAW = re.compile(r'<(input|select|textarea)\b') is searched in each .tsx file's raw text, so it matches inside comments and strings and misses createElement('input'). The SDK import ban runs only in full, as toolchain_scope_tests. Neither rule appears in apps/web/eslint.config.mjs or in the service's ruff selection.
- **Why it matters:** A developer learns about a raw `<input>` or an `anthropic` import only from a harness or full run, not from the editor or the web lint step. The TSX regex can also fail on a harmless comment.
- **Recommendation:** Express the form-control rule as an ESLint `no-restricted-syntax` rule on JSXOpeningElement names, with an exception for components/ui/field.tsx. Express the import ban with ruff's flake8-tidy-imports banned-api in services/agent. Keep each test's known-bad cases until the lint rule has its own fixture, so no guard is lost during the move.
- **Rule check:** DH-06 calls for pinned ESLint with Next.js, React and TypeScript rules, and Ruff for the service. Per the ground rules no guard is weakened: the tests stay until the lint rules are proven.
- **Verification:** confirmed. Verified the raw-text regex over TSX files and the AST import scan that only full runs; apps/web/eslint.config.mjs has no restricted-syntax rule.

### <a id="thrn-19"></a>THRN-19: Mutation lambdas and unexplained counts hide intent

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 13
- **Where:**
  - [tests/harness/test_assistant_assets.py:503-512](../../../../tests/harness/test_assistant_assets.py#L503): Lambdas calling __setitem__, with default-argument capture
  - [tests/harness/test_assistant_assets.py:533](../../../../tests/harness/test_assistant_assets.py#L533): Nested __setitem__ on a hook's type
  - [tests/toolchain/test_manifests.py:128-132](../../../../tests/toolchain/test_manifests.py#L128): Five __setitem__ and append lambdas
  - [tests/harness/test_assistant_assets.py:596-597](../../../../tests/harness/test_assistant_assets.py#L596): Pins 13 skills and 7 agents with no message
  - [tests/harness/test_disposable_guard.py:62-77](../../../../tests/harness/test_disposable_guard.py#L62): Named one-line mutators: the readable pattern already in use
- **Evidence:** That is 11 __setitem__ lambdas and 2 bare counts, for example:

  ```python
  self.assert_refused(f'plugin {value}', config,
                      lambda data, v=value: data['upstream']['delivery_plugin'].__setitem__('event_delivery_qualification', v),
                      'upstream.delivery_plugin.event_delivery_qualification', 'configuration_invalid')
  self.assertEqual(len(list((ROOT / '.claude/skills').glob('*/SKILL.md'))), 13)
  ```

- **Why it matters:** Readers must decode dunder calls and default-argument capture to see what each negative case changes. Adding a skill fails with '13 != 14' and no word on why the count is pinned.
- **Recommendation:** Use named one-line mutators, with the name as the subTest label, as test_disposable_guard.py and test_supabase_stack.py already do. Alternatively, use a small `setting(path, value)` helper that returns a labelled mutator. For the pinned counts, add a message saying why they are pinned, or compare against an explicit list of names.
- **Rule check:** none
- **Verification:** confirmed. Verified 11 __setitem__ lambdas (6 in test_assistant_assets.py, 5 in test_manifests.py) and the two bare counts at test_assistant_assets.py:596-597.

## Rejected during verification

None. Every finding was confirmed or revised.

## Not covered

I did not run the harness or toolchain suites. They write under .checks and the system temp directory, outside this review's write scope, and most toolchain tests download from package registries. The one exception is tests/toolchain/test_manifests.py, which I ran read-only with -B: 15 tests passed in 0.08 s and the working tree was unchanged. Per-test durations are therefore unknown. Remarks about slow or process-heavy tests come from reading the code and from the latest harness report's total (290 tests, 26.6 s). I read only the parts of the code under test that the findings needed: scripts/verify.py (60-200), .claude/hooks/dispatch.py (90-200), scripts/harness_lib.py (77-84, 250-345), scripts/app_db.py (175-216), scripts/qualify_release.py (20-62), tests/faults/state/check.py (1-30 and its last lines), the runs migration (1-40) and the service's ruff section. Their own quality belongs to the scripts, sql-infra and db-tests areas. I read the PRD-Development-Harness.md sections DH-03, DH-05, DH-06 and DH-09, not the whole document.
