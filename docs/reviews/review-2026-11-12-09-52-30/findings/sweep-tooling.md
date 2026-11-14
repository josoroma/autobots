# Lens: standards enforcement and tooling

Where tools run, they are strict and unusually well engineered. services/agent has ruff, ruff format, strict mypy and strict pytest. apps/web has strict TypeScript (with noUncheckedIndexedAccess and exactOptionalPropertyTypes), zero-warning ESLint, Prettier and a production build. Every check runs offline, cannot change the tree, counts skips and empty suites as failures, and is proven by known-bad fixtures. Enforcement stops at directory boundaries rather than where the rules intend. The 133 repository-level Python files (25,788 lines, 42% of all Python, including the verifier, the hooks, the qualifiers and the persistent install) have no lint, format or type gate. They follow a second house style and carry 295 dead suppressions, and the 881 service names they import are checked only when a slow profile runs them. packages/api-client's runtime and contract test, and the infra JavaScript, fall outside lint and format. Tests are selected from hand-kept lists, so schema-value.test.ts and the static manifest suite run in no profile. Nothing documents the five test mechanisms or why the web unit runner departs from DH-06. Neither language sets size or complexity limits. No rule stops the 28 type assertions on response bodies, most of which skip an available generated parser. Layering is clean but unguarded, and one web import cycle exists. Nothing runs any profile automatically, and no test guards the gates' own settings. Most fixes are configuration with zero or small baselines. Ruff's RUF100 and ESLint's bulk suppressions make those baselines shrink-only.

[Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Strict, pinned, fault-proven gates cover services/agent and apps/web. 42% of Python (133 files) and the infra JS run under none, packages/api-client is type-checked but not linted or format-checked, nothing triggers the gates, and their settings are unguarded. |
| modules | 3 | Web layering and domain/ are clean today (0 hits under the proposed zones and bans). One web import cycle exists, adapters and application import each other (26 and 21 statements), and no rule holds any direction. |
| size | 2 | No limit is configured. 33 service functions exceed lenient thresholds (41 hits), web functions reach 677 lines and files 829 counted lines, and a script holds a 410-line function. |
| functions | 3 | 62 service functions take more than five parameters (8 take more than eight). Pure helpers such as valueFor and draftOf live inside component files, out of unit-test reach. |
| structure | 3 | Directory boundaries, not intent, decide coverage. Tests span five mechanisms in six places, and packages/api-client falls between the web's lint and format paths. |
| approach | 4 | The verification design is a model: offline, pinned, non-mutating, fingerprinted, skip-is-failure and fault-proven. Hand-kept test lists and the lack of any automatic trigger undercut it. |
| comments | 3 | Service suppressions carry codes and reasons. 295 noqa comments in tests/db and scripts are unused, and 25 type: ignore comments target a type checker that never runs. |
| types | 3 | Strict mypy and strict TypeScript where applied. No rule stops 28 type assertions on response bodies and 2 on JSON.parse, type-aware lint is off, and 881 service names imported by checks and scripts go unchecked statically. |
| errors | 3 | Tooling shares one 0/1/2 exit contract and never passes a timeout or missing tool. Nothing lints the service's 22 broad catches (BLE001), and verify.run_check leaves descendant processes alive on timeout. |
| tests | 3 | Skip-as-failure and known-bad fixtures are exemplary. Selection is hand-kept (one unit test and a static suite run in no profile), the five runners are undocumented, and component logic has no unit-test path. |
| maintainability | 3 | Strong gates cover about half the code. The rest, the gates' settings and the triggers are unguarded, and most fixes are configuration with small, shrink-only baselines. |

## Strengths

- **Verification cannot install or mutate, and proves it.** scripts/toolchain.py:187-188 sets UV_OFFLINE, UV_NO_SYNC and COREPACK_ENABLE_NETWORK=0 for checks. run_guarded (scripts/toolchain.py:299-321) fails a run whose locks, manifests, changed files or installed package names differ, even when every step passed. scripts/verify.py:184-187 records the same guard as non_mutation_guard. Use this as the template for every new step. Sources: [scripts/toolchain.py:187-188](../../../../scripts/toolchain.py#L187), [scripts/toolchain.py:299-321](../../../../scripts/toolchain.py#L299), [scripts/verify.py:184-187](../../../../scripts/verify.py#L184).
- **Skips, empty suites, timeouts and missing tools never pass.** scripts/verify.py:91-107 turns an empty unittest suite or any skip into a failure and reads pytest's skip summary. scripts/harness_lib.py:221-229 refuses reports with skipped tests or failed commands. verify.py, toolchain.py and qualify_faults.py share one exit contract: 0 passed, 1 failed, 2 unavailable. Sources: [scripts/verify.py:91-107](../../../../scripts/verify.py#L91), [scripts/harness_lib.py:221-229](../../../../scripts/harness_lib.py#L221), [scripts/qualify_faults.py:119-140](../../../../scripts/qualify_faults.py#L119).
- **Known-bad fixtures prove each checker bites.** scripts/qualify_faults.py:55-75 runs ruff, mypy, pytest, tsc and ESLint on good and bad fixtures. A bad fixture counts only if it fails with its expected marker (F401, return-value, TS2322, no-explicit-any), so a crashed tool is not a detected fault. Add a bad fixture with every new rule. Sources: [scripts/qualify_faults.py:55-75](../../../../scripts/qualify_faults.py#L55).
- **Strict typing where it is applied.** services/agent/pyproject.toml:49-59 sets mypy strict over src and tests, pytest --strict-markers --strict-config and strict asyncio mode. All 62 service type: ignore comments carry an error code. apps/web/tsconfig.json:7-9 adds noUncheckedIndexedAccess and exactOptionalPropertyTypes to strict, and apps/web/package.json:6 fails lint on any warning. Sources: [services/agent/pyproject.toml:49-59](../../../../services/agent/pyproject.toml#L49), [apps/web/tsconfig.json:7-9](../../../../apps/web/tsconfig.json#L7), [apps/web/package.json:6](../../../../apps/web/package.json#L6).
- **Repository conventions as small stdlib tests that check themselves.** tests/toolchain/test_scaffold_scope.py:41-50 bans the unused provider SDKs and proves each import form is detected. tests/harness/test_shared_form_controls.py:14-23 bans raw form controls and fails if it no longer sees more than 20 screens. Reuse this shape for test ownership and import contracts. Sources: [tests/toolchain/test_scaffold_scope.py:41-50](../../../../tests/toolchain/test_scaffold_scope.py#L41), [tests/harness/test_shared_form_controls.py:14-23](../../../../tests/harness/test_shared_form_controls.py#L14).
- **Generated validators and server-only guards at the web boundary.** 25 component files use generated parse functions at 60 sites, e.g. apps/web/components/approvals-panel.tsx:143. Five server modules begin with import "server-only" (apps/web/lib/bff.ts:1). All 237 internal imports in app, components and lib use the @/ alias, with none relative, which makes path-based layering rules easy to write. Sources: [apps/web/components/approvals-panel.tsx:143](../../../../apps/web/components/approvals-panel.tsx#L143), [apps/web/lib/bff.ts:1](../../../../apps/web/lib/bff.ts#L1).
- **Exact, hashed pins, refused when inexact.** scripts/toolchain.py:109-121 refuses any pin that is not an exact version, and a pnpm packageManager without its sha512. pnpm-workspace.yaml sets engineStrict, strictPeerDependencies and verifyDepsBeforeRun: error. Sources: [scripts/toolchain.py:109-121](../../../../scripts/toolchain.py#L109), [pnpm-workspace.yaml:8-10](../../../../pnpm-workspace.yaml#L8).
- **Habits that already meet lockable rules.** DTZ, S602, S604 and S605 report 0 across all 318 Python files, and so do S110 and S112. The web reports 0 floating or misused promises (rerun with type information over 95 files) and 0 layering violations under the proposed zones. These rules can start as errors with no baseline. Sources: [apps/web/eslint.config.mjs:4-8](../../../../apps/web/eslint.config.mjs#L4), [services/agent/pyproject.toml:46-47](../../../../services/agent/pyproject.toml#L46).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [XTOL-01](#xtol-01) | high | standards | Repository-level Python runs under no lint, format or type gate | M | low |
| [XTOL-02](#xtol-02) | high | tests | Hand-kept test lists let tests drop out unseen, and two suites already run in no profile | S | low |
| [XTOL-03](#xtol-03) | medium | types | Service internals used by the database checks and scripts are never checked statically | M | low |
| [XTOL-04](#xtol-04) | medium | standards | Two Python house styles, and only the service's is checked | M | low |
| [XTOL-05](#xtol-05) | medium | size | No size or complexity limit is configured in either language | S | low |
| [XTOL-06](#xtol-06) | medium | types | No rule stops JSON casts at the web boundary, though generated parsers exist | M | medium |
| [XTOL-07](#xtol-07) | medium | modules | Layering is clean but unguarded, and one web import cycle has formed | S | low |
| [XTOL-08](#xtol-08) | medium | standards | Rules the code already follows are enforced only by review | S | low |
| [XTOL-09](#xtol-09) | medium | standards | The gates' own settings have no regression check | S | low |
| [XTOL-10](#xtol-10) | medium | tests | Five test mechanisms, and the web unit runner departs from DH-06 without a decision | M | low |
| [XTOL-11](#xtol-11) | medium | standards | No CI or Git hook runs any profile, and make check covers only the harness | S | low |
| [XTOL-12](#xtol-12) | low | standards | packages/api-client and infra JavaScript sit outside lint and format, and the contract test outside any type check | S | low |
| [XTOL-13](#xtol-13) | low | standards | Prettier runs on implicit defaults, and no editor settings are shared | S | low |
| [XTOL-14](#xtol-14) | low | comments | 295 suppression comments are dead, written for a linter that never runs there | S | low |
| [XTOL-15](#xtol-15) | low | types | apps/web omits erasableSyntaxOnly although its unit tests run through Node type stripping | S | low |
| [XTOL-16](#xtol-16) | low | duplication | verify.py keeps a weaker subprocess runner beside toolchain.run_step | S | low |

### <a id="xtol-01"></a>XTOL-01: Repository-level Python runs under no lint, format or type gate

- **Severity** high · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 133
- **Where:**
  - [scripts/toolchain.py:210-213](../../../../scripts/toolchain.py#L210): ruff check, ruff format --check and mypy run from services/agent with no path arguments
  - [services/agent/pyproject.toml:41-53](../../../../services/agent/pyproject.toml#L41): Ruff run without paths checks the services/agent directory, and mypy's files are src and tests
  - [scripts/harness_lib.py:145-157](../../../../scripts/harness_lib.py#L145): tests/harness and .claude/hooks fall to the harness domain, which runs no static check
  - [.claude/hooks/dispatch.py:161-164](../../../../.claude/hooks/dispatch.py#L161): the edit-time ruff diagnostic runs only for the python domain
  - [scripts/persistent_install.py:31](../../../../scripts/persistent_install.py#L31): F401: other_resources imported and unused, one of 5,775 hits
  - [scripts/qualify_backup.py:89](../../../../scripts/qualify_backup.py#L89): F841: workspace_b assigned and never used
- **Evidence:** toolchain.py:210-213 runs `ruff check`, `ruff format --check` and `mypy` from services/agent with no paths, and pyproject.toml:52 sets mypy `files = ["src", "tests"]`. Whatever domain check_domains gives a script, the Python steps lint only services/agent. tests/harness and .claude/hooks map to the harness domain, which runs only unittest. The PostToolUse hook runs ruff only for the python domain. So 133 files and 25,788 lines (42% of all Python) have no static check. They include verify.py, harness_lib.py, dispatch.py, the qualifiers and persistent_install.py. Under the service's own rules (metrics.md section 6) they give 5,775 hits: 5,269 E501, 295 RUF100, 119 I001, 34 UP017, 9 B023, 7 F401, 7 RUF012, 7 RUF059, 4 B905, 3 ASYNC240 and 2 F841. 458 of them have safe autofixes.
- **Why it matters:** DH-06 asks for Ruff and strict mypy on owned modules, and DH-09 treats check infrastructure as the most conservative scope. Yet the code that decides whether every other check passed, and the guarded persistent install, has no static check. Its defects surface as wrong verdicts or as runtime failures on the real install. The unused workspace_b at qualify_backup.py:89, a second owner's workspace that nothing reads, may already mark a check the backup qualifier never makes.
- **Recommendation:** Create one shared Python standard. Add a root ruff.toml and have services/agent extend it. Add a repo_ruff_check step over scripts, tests and .claude/hooks to fast and full, and a check_domains domain for those paths so fast, the Stop hook and the PostToolUse diagnostic cover them. Adoption path:
  1. Report only, with `ruff check --exit-zero --statistics`.
  2. One explicit commit applying the 458 safe fixes and `--select RUF100 --fix`, after the rule selection is settled (XTOL-14).
  3. Gate with E501 ignored for these paths.
  4. Reformat separately (XTOL-04).
  5. Drop the E501 ignore.

  Land the import-contract check (XTOL-03) before considering mypy there.
- **Rule check:** DH-06 (Ruff lint and format, mypy strict for owned modules; safe autofix is an explicit operation) and DH-05 (substantive checks live in repository scripts; no formatter rewrites in hooks). The change only adds checks, and the hook stays diagnostic.
- **Verification:** revised. 133 files and 25,788 lines recounted from files.txt (42% of 61,654 Python lines), and both cited hits reproduce; the 9 B023 hits look benign. Revised: the RUF100 cleanup waits until the rule selection is settled, so the reasoned BLE001 markers survive (XTOL-14).

```text
# ruff.toml (repository root): the shared Python standard
target-version = "py312"
line-length = 100
src = ["scripts", "services/agent/src"]
extend-exclude = ["tests/faults/python/bad_*"]   # deliberately bad fixtures
[lint]
select = ["E", "F", "W", "I", "B", "UP", "ASYNC", "RUF"]
[lint.per-file-ignores]
"scripts/**" = ["E501"]          # until the one-time reformat
"tests/**" = ["E501"]
".claude/hooks/**" = ["E501"]

# services/agent/pyproject.toml: inherit instead of restating; no own select
[tool.ruff]
extend = "../../ruff.toml"
src = ["src", "tests"]

# scripts/toolchain.py check_steps, run from the root
Step('repo_ruff_check', (str(venv_bin / 'ruff'), 'check', 'scripts', 'tests', '.claude/hooks'), root)
# scripts/harness_lib.py: a domain that fast and the Stop hook require
REPO_PYTHON_STEPS = frozenset({'repo_ruff_check'})
```

### <a id="xtol-02"></a>XTOL-02: Hand-kept test lists let tests drop out unseen, and two suites already run in no profile

- **Severity** high · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 2
- **Where:**
  - [scripts/verify.py:161-162](../../../../scripts/verify.py#L161): web_unit_tests names two of the three unit test files
  - [apps/web/tests/unit/schema-value.test.ts:1-17](../../../../apps/web/tests/unit/schema-value.test.ts#L1): US-16.2's test, run by no profile
  - [scripts/verify.py:154-156](../../../../scripts/verify.py#L154): only test_scaffold_scope.py runs; the comment says the rest bootstrap copies from registries
  - [tests/toolchain/test_manifests.py:1-3](../../../../tests/toolchain/test_manifests.py#L1): offline static tests of pins, locks and the runbook, run by no profile
  - [scripts/qualify_identity.py:317](../../../../scripts/qualify_identity.py#L317): 19 of the 28 Playwright name filters, kept inline
  - [scripts/qualify_web.py:169](../../../../scripts/qualify_web.py#L169): three more filters in another script
  - [apps/web/tests/browser/install.spec.ts:4-5](../../../../apps/web/tests/browser/install.spec.ts#L4): manual by design, recorded only in a comment
- **Evidence:** verify.py:161-162 passes only request-guard.test.ts and credential-precedence.test.ts to `node --test`. schema-value.test.ts, added by US-16.2, is in no list, and .checks/full/latest.json records exactly those two files in web_unit_tests' argv. The archived US-16.2 verification.md cites schema-value.test.ts for a PASS row and says fast passed its 'web unit tests'. test_manifests.py calls itself 'Static tests of pins, locks and the runbook' and makes no network call. toolchain_scope_tests discovers only test_scaffold_scope.py, so no report's check argv names test_manifests.py. Playwright specs are chosen by 28 name filters spread over qualify_identity.py (including its -g runs at 329-376), qualify_web.py, qualify_release.py:342 and persistent_install.py:720. All 41 specs match one today except install.spec.ts, which is manual by design, but nothing would notice a new spec that matches none.
- **Why it matters:** The profiles' skip-is-failure rules cannot see an unrun test, and evidence records can cite one as passing. That has already happened once. A pin changed without its runbook row also goes uncaught.
- **Recommendation:** Select tests by glob, not by name: Node 22 expands `--test` patterns itself. Add test_manifests.py to the offline toolchain step. Move the Playwright filters into one module the qualifiers import. Add a stdlib harness test that every test file is claimed by a runner or listed as manual with a reason, plus a self-check that an unclaimed file is detected (the test_shared_form_controls.py pattern).
- **Rule check:** DH-09 (no passing badge for an empty suite; skipped checks never count) and the OhMyOrch delivery rule (never report a scenario as passing without observing it). The change adds coverage and a guard and removes no check.
- **Verification:** confirmed. verify.py and the full report argv list two of the three unit files, and test_manifests.py only reads repository files. The archived US-16.2 record cites schema-value.test.ts in PASS rows (verification.md:13, 17) and line 22 says fast passed its web unit tests. Filter coverage simulated with regular expressions.

```text
# scripts/verify.py: globs, so a new test file cannot be missed
Step('web_unit_tests', (node, '--test', 'apps/web/tests/unit/**/*.test.ts'), root)
Step('api_client_tests', (node, '--test', 'packages/api-client/tests/**/*.test.ts'), root)
Step('toolchain_manifest_tests', (sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/toolchain',
                                  '-p', 'test_manifests.py'), root)

# scripts/test_suites.py: the one list the qualifiers import
BROWSER_FILTERS = {'qualify_web': ('appearance', 'boundary', 'browser/tools.spec'), ...}
MANUAL = {'apps/web/tests/browser/install.spec.ts': 'run by hand on the persistent install'}

# tests/harness/test_test_ownership.py
def unclaimed(paths, filters, manual):
    return [p for p in paths if p not in manual and not any(re.search(f, p) for f in filters)]
class TestOwnership(unittest.TestCase):
    def test_every_spec_has_a_runner(self): self.assertEqual(unclaimed(specs(), all_filters(), MANUAL), [])
    def test_an_unclaimed_spec_is_seen(self): self.assertEqual(unclaimed(['x.spec.ts'], ['y'], {}), ['x.spec.ts'])
```

### <a id="xtol-03"></a>XTOL-03: Service internals used by the database checks and scripts are never checked statically

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** low · **Occurrences** 881
- **Where:**
  - [scripts/harness_lib.py:147-148](../../../../scripts/harness_lib.py#L147): a services/agent change affects only the python domain
  - [tests/db/wake_check.py:16](../../../../tests/db/wake_check.py#L16): imports the private _keep_lease
  - [tests/db/assignment_check.py:21](../../../../tests/db/assignment_check.py#L21): imports the private _finish
  - [scripts/persistent_install.py:288-292](../../../../scripts/persistent_install.py#L288): returns tuple[object, dict] to keep a lazy import
  - [scripts/persistent_install.py:437-449](../../../../scripts/persistent_install.py#L437): type: ignore[attr-defined] on Ledger.settle and committed in the paid goal
  - [services/agent/src/autobots/operations/route_qualification.py:167](../../../../services/agent/src/autobots/operations/route_qualification.py#L167): the signature those calls rely on
  - [scripts/app_db.py:421-423](../../../../scripts/app_db.py#L421): the checks run only as subprocesses inside the db profile
- **Evidence:** A stdlib resolver written for this review checked the 881 names that 68 files in tests/ and scripts/ import from autobots. Those include 473 import lines in 60 tests/db files and 18 imports of 13 private names, such as _keep_lease and _finish. All resolve today, but no tool checks them on change. mypy covers only services/agent, and check_domains sends services/agent/ to the python domain alone. A rename therefore passes fast, the PostToolUse diagnostic and the Stop hook, and breaks only inside the next db run (about 610 s with Docker in the latest report). The 25 type: ignore comments in scripts and tests serve a type checker that never runs there; 14 of them are in persistent_install.py, all caused by reserve_goal's object return type.

  ```python
  # scripts/persistent_install.py:288 and 437
  def reserve_goal(ledger_path: Path, limit: int) -> tuple[object, dict]:
          ledger.settle(entry, 0, 'not_started')  # type: ignore[attr-defined]
  ```

- **Why it matters:** A service refactor can silently break the database and qualification suites. It can also break settlement of the shared spending cap after a paid install goal. The failure appears late, in the slowest profile or on the real install.
- **Recommendation:** Add an import-contract test to the fast profile, in the style of tests/toolchain/test_scaffold_scope.py. It resolves every `from autobots... import name` in tests/ and scripts/ against services/agent/src. The review's resolver is about 60 lines and runs in under a second. Include a fixture proving a missing name is reported. Type reserve_goal with a TYPE_CHECKING import of Ledger and drop its 14 ignores. Once the lint gate lands, consider mypy with a non-strict override over scripts and tests/db.
- **Rule check:** DH-06 (mypy for owned modules; keep typing exceptions narrow and documented) and python-worker.md (checks use prepared environments and do not install). The check is static and needs no services.
- **Verification:** revised. An AST recount gives 881 names in 68 files and 473 statements in 60 tests/db files, and all 14 ignores in persistent_install.py follow from the object type. Revised: the 18 private-name imports cover 13 distinct names.

```text
# tests/toolchain/test_import_contract.py (stdlib, offline, run by fast)
def unresolved(sources: dict[str, str], defined: Callable[[str], set[str] | None]) -> list[str]:
    """Every name imported from autobots that the source tree does not define."""
class ImportContract(unittest.TestCase):
    def test_tests_and_scripts_import_only_existing_names(self): self.assertEqual(unresolved(sources(), defined), [])
    def test_a_missing_name_is_reported(self): self.assertTrue(unresolved({'x.py': 'from autobots.domain.runs import Gone'}, defined))

# scripts/persistent_install.py
if TYPE_CHECKING:
    from autobots.operations.route_qualification import Ledger
def reserve_goal(ledger_path: Path, limit: int) -> tuple['Ledger', dict[str, Any]]: ...
```

### <a id="xtol-04"></a>XTOL-04: Two Python house styles, and only the service's is checked

- **Severity** medium · **Dimension** standards · **Effort** M · **Risk** low · **Occurrences** 133
- **Where:**
  - [services/agent/pyproject.toml:41-44](../../../../services/agent/pyproject.toml#L41): 100 columns and ruff format defaults (double quotes)
  - [scripts/toolchain.py:31-35](../../../../scripts/toolchain.py#L31): repository scripts use single quotes
  - [scripts/specs.py:236-249](../../../../scripts/specs.py#L236): a scripts/ file in the service style
  - [tests/harness/test_specs.py:13](../../../../tests/harness/test_specs.py#L13): a harness test in the service style
  - [scripts/app_db.py:117](../../../../scripts/app_db.py#L117): a 578-character line
- **Evidence:** String literals, counted with tokenize including f-strings: services/agent/src has 7,369 double-quoted and 47 single-quoted; scripts 8,648 single and 978 double; tests/db 9,432 single and 711 double; and tests/harness 2,978 single and 360 double. Nine repository-level files follow the service, among them scripts/specs.py, tests/harness/test_specs.py and tests/db/tool_keys_check.py. Lines over 100 columns: 11 in the service (src and tests, longest 116); 2,060 in scripts (626 over 140, longest 578 at app_db.py:117); 2,763 in tests/db (1,117 over 140). `ruff format --line-length 100` would change 121 of 134 files: 43,508 diff lines, or 34,007 with quote-style preserve. On a scratch copy it grows them from 25,788 to 47,666 lines (41,473 at 120 columns) and leaves 1,015 E501 hits (437 at 120).
- **Why it matters:** Reviewers read two dialects. Very long lines hide logic in diffs. Formatting nearly doubles the true size of this code, which any Python size limit must account for.
- **Recommendation:** Adopt the service's style everywhere through the shared root ruff.toml: double quotes, 100 columns. After the lint gate lands, and with no story open on those files, reformat repository-level Python in one mechanical commit listed in .git-blame-ignore-revs. Then add `ruff format --check` for those paths, drop their E501 ignore and wrap the remaining long strings. Calibrate Python size limits after the reformat, and prefer statement and complexity limits to line counts.
- **Rule check:** DH-06 (Ruff check and formatting are separate gates; safe autofix is an explicit operation) and DH-05 (no formatter rewrites on ordinary edits). The reformat is one reviewed commit, never a hook action. It needs harness, db and operations reruns because tests/db and the qualifiers change.
- **Verification:** revised. Single-quote and long-line counts reproduce, and the three named files are double-quoted. Revised: the double-quote counts include f-strings here, so they are higher; the format churn comes from the reviewer's scratch copy and was not rerun (metrics.md records 121 of 134 files to reformat).

```text
# ruff.toml (root)
[format]
quote-style = "double"   # the service's style; "preserve" would cut the churn by about 22%

# .git-blame-ignore-revs
<sha>  # one mechanical ruff format of scripts/, tests/ and .claude/hooks/

# scripts/toolchain.py, after the reformat
Step('repo_ruff_format', (str(venv_bin / 'ruff'), 'format', '--check', 'scripts', 'tests', '.claude/hooks'), root)
```

### <a id="xtol-05"></a>XTOL-05: No size or complexity limit is configured in either language

- **Severity** medium · **Dimension** size · **Effort** S · **Risk** low · **Occurrences** 86
- **Where:**
  - [services/agent/pyproject.toml:46-47](../../../../services/agent/pyproject.toml#L46): lint.select has no C90 or PLR09 rules
  - [apps/web/eslint.config.mjs:4-8](../../../../apps/web/eslint.config.mjs#L4): Next presets only
  - [apps/web/package.json:6](../../../../apps/web/package.json#L6): --max-warnings=0, so a warn-level rule fails lint
  - [services/agent/src/autobots/adapters/github_pulls.py:68](../../../../services/agent/src/autobots/adapters/github_pulls.py#L68): complexity 37, 92 statements
  - [apps/web/components/run-workspace.tsx:152](../../../../apps/web/components/run-workspace.tsx#L152): 677-line component, complexity 39
  - [apps/web/components/goal-composer.tsx:113](../../../../apps/web/components/goal-composer.tsx#L113): 527 lines, complexity 37
  - [scripts/qualify_worker_inference.py:65](../../../../scripts/qualify_worker_inference.py#L65): 410-line function
- **Evidence:** Counted in this review over the service's src and tests at the proposed thresholds. C901 at 15: 5 (at 12: 17; at 10: 26). PLR0911 at 8 returns: 6. PLR0912 at 15 branches: 2. PLR0913 at 8 arguments: 8 (at 5: 62). PLR0915 at 60 statements: 3. PLR0917 at 6 positional arguments: 17 (at 5: 38). That makes 41 hits on 33 functions in 25 files. Repository-level C901 at 15: scripts 18, tests/db 6, tests/harness 1. Web, non-test: complexity at 15: 11; max-lines-per-function at 150: 24; max-lines at 400: 10, with 6 more in tests/browser.
- **Why it matters:** Hotspots grow without any signal. Because lint fails on any warning, a new limit cannot be introduced at warn level inside the gate.
- **Recommendation:** Enable calibrated limits now, with baselines that can only shrink. Ruff: enable the rules, then run `ruff check --add-noqa` once. RUF100, already on through RUF, then fails on any suppression that is no longer needed. ESLint: enable the rules as errors and baseline them with `eslint --suppress-rule`, which writes eslint-suppressions.json and, by default, fails on entries that no longer match. For a report-only look first, use `ruff check --exit-zero --statistics` and a separate `lint:report` script with --max-warnings=-1. As baselines empty, tighten C901 from 15 to 12 to 10 and function length from 150 to 100. Relax file length for tests/browser.
- **Rule check:** DH-06 (small cohesive modules) and DH-09 (no speculative frameworks or arbitrary quotas). Thresholds are calibrated to today's counts and only tighten; DH-04 forbids raising one to pass a gate.
- **Verification:** confirmed. Every Python count reproduces with ruff 0.17.3, where PLR0917 is stable, and the web counts match eslint_proposed.json. ESLint 9.39.5 has --suppress-rule, and stale suppressions fail unless --pass-on-unpruned-suppressions is set.

```text
# services/agent/pyproject.toml
[tool.ruff.lint]
extend-select = ["C90", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "PLR0917"]
[tool.ruff.lint.mccabe]
max-complexity = 15        # 5 today; then 12 (17) and 10 (26)
[tool.ruff.lint.pylint]
max-args = 8               # 8 today
max-positional-args = 6    # 17
max-branches = 15          # 2
max-statements = 60        # 3
max-returns = 8            # 6

// apps/web/eslint.config.mjs
{ files: ["**/*.{ts,tsx}"], rules: {
    complexity: ["error", 15],                                                                    // 11
    "max-lines-per-function": ["error", { max: 150, skipBlankLines: true, skipComments: true }],  // 24
    "max-lines": ["error", { max: 400, skipBlankLines: true, skipComments: true }] } },           // 10
{ files: ["tests/**"], rules: { "max-lines": "off", "max-lines-per-function": "off" } },

# baselines, once each
(cd services/agent && .venv/bin/ruff check --add-noqa)
(cd apps/web && node_modules/.bin/eslint --suppress-rule complexity --suppress-rule max-lines-per-function --suppress-rule max-lines .)
```

### <a id="xtol-06"></a>XTOL-06: No rule stops JSON casts at the web boundary, though generated parsers exist

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** medium · **Occurrences** 30
- **Where:**
  - [apps/web/components/approvals-panel.tsx:216-218](../../../../apps/web/components/approvals-panel.tsx#L216): error body cast to { code?: string }
  - [apps/web/components/approvals-panel.tsx:143](../../../../apps/web/components/approvals-panel.tsx#L143): the same file parses its list with parseApprovalList
  - [apps/web/components/goal-composer.tsx:311](../../../../apps/web/components/goal-composer.tsx#L311): success body cast to { run_id: string }
  - [apps/web/components/session-panel.tsx:65](../../../../apps/web/components/session-panel.tsx#L65): the same cast, inline
  - [apps/web/components/run-workspace.tsx:224](../../../../apps/web/components/run-workspace.tsx#L224): JSON.parse(...) as { cursor: number }
  - [packages/api-client/src/generated.ts:7698](../../../../packages/api-client/src/generated.ts#L7698): parseErrorResponse exists
  - [packages/api-client/src/generated.ts:8534](../../../../packages/api-client/src/generated.ts#L8534): parseRunAccepted exists
  - [apps/web/eslint.config.mjs:4-8](../../../../apps/web/eslint.config.mjs#L4): no rule covers this
- **Evidence:** A no-restricted-syntax selector for a type assertion over a `.json()` call flags 28 non-test sites in 17 files: 19 read error bodies and 9 read success bodies. It also flags 2 `JSON.parse(...) as T` sites, and 10 more sites in tests. Meanwhile 25 component files already use generated parsers (60 sites), and the client exports parseErrorResponse and parseRunAccepted.

  ```tsx
  // components/approvals-panel.tsx:216-218
  const failure = (await reply?.json().catch(() => null)) as {
    code?: string;
  } | null;
  ```

- **Why it matters:** DH-06 asks for explicit response parsing at untrusted boundaries. Today a renamed error code or response field reaches the screen as undefined instead of failing with a ContractError.
- **Recommendation:** Add the selector rule now, scoped to app, components and lib; it needs no type information. Baseline today's 30 sites in eslint-suppressions.json. Then replace the error-body casts with one shared helper around parseErrorResponse, and the success casts with the matching generated parse function, showing a ContractError as the unavailable state. Two sites have no generated parser: workflow-editor.tsx:81 deep-clones an already parsed graph, where structuredClone fits, and lib/csrf-fetch.ts:6 reads the BFF's own /api/csrf, so fix those in place.
- **Rule check:** DH-06 Next.js (explicit response parsing at untrusted boundaries; no blanket type assertions) and nextjs.md (generated API types plus runtime parsing). Generated files are consumed, never edited.
- **Verification:** revised. A regex recount over app, components and lib gives the same 28 sites in 17 files plus 2 over JSON.parse, and eslint_proposed.json shows 30 with 10 more in tests. Revised: the rule is scoped to non-test code, and the deep clone and the /api/csrf read, which have no generated parser, are handled in place.

```text
const PARSE = "Parse response bodies with a generated parse* function (DH-06), not a type assertion.";
"no-restricted-syntax": ["error",
  { selector: "TSAsExpression:has(CallExpression[callee.property.name='json'])", message: PARSE },
  { selector: "TSAsExpression > CallExpression[callee.object.name='JSON'][callee.property.name='parse']", message: PARSE }],
// scoped with files: ["app/**", "components/**", "lib/**"]
// lib/error-body.ts
export async function errorCode(reply: Response | null): Promise<string | null> // wraps parseErrorResponse
```

### <a id="xtol-07"></a>XTOL-07: Layering is clean but unguarded, and one web import cycle has formed

- **Severity** medium · **Dimension** modules · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/components/run-list.tsx:8](../../../../apps/web/components/run-list.tsx#L8): imports RunPanel
  - [apps/web/components/run-panel.tsx:9](../../../../apps/web/components/run-panel.tsx#L9): imports StateLine back from run-list
  - [apps/web/components/home-activity.tsx:13](../../../../apps/web/components/home-activity.tsx#L13): STATUS_TEXT comes from the run-list screen
  - [apps/web/components/workflows-panel.tsx:17](../../../../apps/web/components/workflows-panel.tsx#L17): the same
  - [tests/toolchain/test_scaffold_scope.py:13](../../../../tests/toolchain/test_scaffold_scope.py#L13): the only import rule today, run in full only
  - [services/agent/src/autobots/adapters/loop_middleware.py:34](../../../../services/agent/src/autobots/adapters/loop_middleware.py#L34): adapters import application
  - [services/agent/src/autobots/application/provider_settings.py:14](../../../../services/agent/src/autobots/application/provider_settings.py#L14): application imports adapters
- **Evidence:** Run in check mode for this review, import/no-cycle reports run-list.tsx:8 and run-panel.tsx:9. import/no-restricted-paths with the three zones below reports 0; an inverted zone reported 59, so the @/ alias resolves. no-restricted-imports patterns for components/ui, components and lib also report 0. In Python, an AST scan finds domain/ importing only the standard library. On a scratch tree, ruff TID251 in a nested domain/ruff.toml that extends the service config and uses extend-banned-api flagged module, submodule and function-level imports. adapters and application import each other: 26 and 21 import statements.
- **Why it matters:** Clean boundaries erode one import at a time when nothing checks them. The cycle ties two run screens together and leaves shared run status without a clear home.
- **Recommendation:** Turn on import/no-cycle and the zones as errors. Break the cycle by moving StateLine and STATUS_TEXT into a small shared run-status module. Add the domain ban, which has 0 hits and needs TID251 selected (see XTOL-08). Decide the adapters-application direction in a decision record before banning either way.
- **Rule check:** DH-06 (keep domain decisions independent of HTTP, Supabase clients and LangGraph internals) and python-worker.md (pure domain types separate from DTOs). The bans only add checks; the adapters-application direction is left to a decision.
- **Verification:** confirmed. Rerun with the exact zones as command-line rules: 2 cycle hits and 0 zone hits, while an inverted zone gives 59. An AST scan confirms domain/ imports only the standard library and itself, and the 26 and 21 cross-layer statements.

```text
// apps/web/eslint.config.mjs
"import/no-cycle": ["error", { maxDepth: 10 }],   // 2 today
"import/no-restricted-paths": ["error", { zones: [
  { target: "./components/ui/**/*", from: ["./components/*.tsx", "./app/**/*"], message: "UI primitives stay feature-free." },
  { target: "./lib/**/*", from: ["./components/**/*", "./app/**/*"], message: "lib/ never imports UI." },
  { target: "./components/**/*", from: ["./app/**/*"], message: "Screens never import route modules." } ] }],  // 0

# services/agent/src/autobots/domain/ruff.toml
extend = "../../../pyproject.toml"
[lint.flake8-tidy-imports.extend-banned-api]
"autobots.application".msg = "domain/ stays independent of the other layers (DH-06)."
"autobots.adapters".msg = "domain/ stays independent of the other layers (DH-06)."
"autobots.api".msg = "domain/ stays independent of the other layers (DH-06)."
"fastapi".msg = "domain/ is framework-free (DH-06)."
"psycopg".msg = "domain/ is framework-free (DH-06)."
"langgraph".msg = "domain/ is framework-free (DH-06)."
"pydantic".msg = "DTOs live in contracts/ (python-worker.md)."
```

### <a id="xtol-08"></a>XTOL-08: Rules the code already follows are enforced only by review

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 27
- **Where:**
  - [.claude/rules/python-worker.md:11](../../../../.claude/rules/python-worker.md#L11): Use explicit UTC
  - [PRD-Development-Harness.md:116](../../../../PRD-Development-Harness.md#L116): subprocess argument arrays, never shell code
  - [AGENTS.md:27](../../../../AGENTS.md#L27): OpenRouter only, no alternative provider
  - [tests/toolchain/test_scaffold_scope.py:13](../../../../tests/toolchain/test_scaffold_scope.py#L13): the SDK ban, as a test
  - [scripts/verify.py:154-156](../../../../scripts/verify.py#L154): that test runs in full only
  - [services/agent/src/autobots/application/tool_gateway.py:372-373](../../../../services/agent/src/autobots/application/tool_gateway.py#L372): a broad catch that neither logs nor re-raises
  - [PRD-Development-Harness.md:129](../../../../PRD-Development-Harness.md#L129): preserve causes; avoid swallowed exceptions
- **Evidence:** Counted over all 318 Python files in this review. DTZ (naive datetimes): 0. S602, S604 and S605 (shell execution): 0. TID251, banning the unused and non-OpenRouter SDKs: 0. The SDK ban exists only as a test that only the full profile runs, so an edit gets no warning. BLE001 finds 22 broad catches in services/agent/src, 3 in scripts and 2 in .claude/hooks, none annotated. Ruff cannot see log_event, so it also flags handlers that do log: about 10 of the 22 log a named event and 2 raise a new error. The silent ones include `except Exception: return _denied("review_unavailable")`.
- **Why it matters:** Rules a pinned linter checks in milliseconds depend on reviewers noticing, and nothing marks which broad catches are deliberate.
- **Recommendation:** Select DTZ, S602, S604, S605 and TID251 in the shared config as errors. They need no baseline and then also run in the PostToolUse diagnostic. Add BLE001 and run `ruff check --add-noqa`, then write the reason on each of the 27 current sites, so each kept broad catch says why and any new one needs a reason. Keep test_scaffold_scope.py.
- **Rule check:** python-worker.md (explicit UTC), DH-05 (argument arrays, never shell), AGENTS.md and the 2026-11-05 SDK decision recorded in test_scaffold_scope.py (OpenRouter only), and DH-06 (no swallowed exceptions). The lint rules complement the existing test, which stays.
- **Verification:** revised. DTZ, S602/S604/S605 and every banned SDK import give 0 on rerun. Revised: BLE001 cannot see log_event, so the 22 src hits are not all silent, and with the hooks the baseline is 27 sites, not 25.

```text
# ruff.toml (root), inherited by services/agent
[lint]
select = ["E", "F", "W", "I", "B", "UP", "ASYNC", "RUF",
          "DTZ", "S602", "S604", "S605", "TID251", "BLE001"]   # new: 0, 0, 0, 0, 0, 27
[lint.flake8-tidy-imports.banned-api]
"anthropic".msg = "Application inference is OpenRouter only (AGENTS.md)."
"langchain_anthropic".msg = "Locked for deepagents only; owned code never imports it."
"google".msg = "Locked for deepagents only; owned code never imports it."
"langchain_google_genai".msg = "Locked for deepagents only; owned code never imports it."
"openai".msg = "Application inference is OpenRouter only (AGENTS.md)."
"langchain_openai".msg = "Application inference is OpenRouter only (AGENTS.md)."
```

### <a id="xtol-09"></a>XTOL-09: The gates' own settings have no regression check

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [scripts/qualify_faults.py:46-47](../../../../scripts/qualify_faults.py#L46): tsc fault cases pass their own flags, not the project tsconfig
  - [scripts/qualify_faults.py:64-65](../../../../scripts/qualify_faults.py#L64): the typescript_type cases
  - [apps/web/tsconfig.json:7-9](../../../../apps/web/tsconfig.json#L7): strict, noUncheckedIndexedAccess, exactOptionalPropertyTypes
  - [apps/web/package.json:6](../../../../apps/web/package.json#L6): --max-warnings=0
  - [services/agent/pyproject.toml:46-59](../../../../services/agent/pyproject.toml#L46): ruff select, mypy strict, pytest strict options
  - [scripts/harness_lib.py:276-320](../../../../scripts/harness_lib.py#L276): settings.json is guarded down to each hook key
- **Evidence:** No file under tests/ or scripts/ mentions noUncheckedIndexedAccess, exactOptionalPropertyTypes, --max-warnings or mypy strict. project_configuration checks .claude/settings.json key by key. Deleting `strict = true`, a select code or `--max-warnings=0` would still pass every profile. The TypeScript fault cases run `tsc --noEmit --strict ...` on the fixture, so they prove tsc catches TS2322, not that apps/web/tsconfig.json is strict. The ESLint, ruff and mypy cases do use the project configs.
- **Why it matters:** DH-04 forbids approving a failed gate by changing thresholds. Today a weakened setting is visible only to a reviewer who reads the config diff.
- **Recommendation:** Add a static test asserting the agreed settings, next to test_manifests.py, which already parses these files, and schedule it in a profile (test_manifests.py itself runs in none, XTOL-02). Include altered copies proving each weakening is caught. Run the TypeScript fault cases through `tsc -p` on a fixture tsconfig that extends apps/web/tsconfig.json, and add a fixture that only noUncheckedIndexedAccess catches.
- **Rule check:** DH-04 (no agent approves its own failed gate by changing thresholds) and nextjs.md (never suppress build type errors). This adds a check.
- **Verification:** revised. rg finds none of the four settings named in tests/ or scripts/; the tsc cases pass their own flags while ruff and mypy use CONFIG = services/agent/pyproject.toml (qualify_faults.py:25). Revised: the new test must be scheduled in a profile, since test_manifests.py, its proposed neighbor, runs in none.

```text
# tests/toolchain/test_gate_settings.py (static; scheduled with the manifest tests)
REQUIRED_TS = {'strict': True, 'noUncheckedIndexedAccess': True, 'exactOptionalPropertyTypes': True}
def gate_errors(tsconfig: dict, web_package: dict, pyproject: dict) -> list[str]:
    errors = [f'tsconfig {k} must be {v}' for k, v in REQUIRED_TS.items() if tsconfig['compilerOptions'].get(k) is not v]
    if '--max-warnings=0' not in web_package['scripts']['lint']: errors.append('lint must fail on warnings')
    if pyproject['tool']['mypy'].get('strict') is not True: errors.append('mypy must stay strict')
    return errors   # plus ruff select and pytest addopts
# one altered copy per setting, as test_manifests.py does for pins
```

### <a id="xtol-10"></a>XTOL-10: Five test mechanisms, and the web unit runner departs from DH-06 without a decision

- **Severity** medium · **Dimension** tests · **Effort** M · **Risk** low · **Occurrences** 5
- **Where:**
  - [services/agent/pyproject.toml:55-59](../../../../services/agent/pyproject.toml#L55): pytest: services/agent/tests
  - [scripts/verify.py:84-86](../../../../scripts/verify.py#L84): unittest: tests/harness
  - [scripts/verify.py:160-162](../../../../scripts/verify.py#L160): node --test: api-client and web unit tests
  - [apps/web/playwright.config.ts:3-5](../../../../apps/web/playwright.config.ts#L3): Playwright, only through the qualifier scripts
  - [scripts/app_db.py:421-427](../../../../scripts/app_db.py#L421): tests/db scripts print JSON cases that app_db.py relays
  - [apps/web/lib/bff.ts:1-8](../../../../apps/web/lib/bff.ts#L1): server-only and @/ imports, which node --test cannot load
  - [apps/web/components/operations-panel.tsx:121](../../../../apps/web/components/operations-panel.tsx#L121): pure valueFor (complexity 17) inside a component file
  - [apps/web/components/expert-editor.tsx:59](../../../../apps/web/components/expert-editor.tsx#L59): pure draftOf (complexity 13), likewise
- **Evidence:** Five mechanisms run the tests. pytest runs services/agent/tests. unittest runs tests/harness and tests/toolchain on the standard library, so harness needs no prepared environment. node --test runs the api-client contract test and two of the three web unit files (XTOL-02) through Node type stripping. Playwright runs 40 of the 41 specs through four qualifier scripts; install.spec.ts is run by hand. 44 tests/db *_check.py scripts print JSON cases that app_db.py and the qualifiers relay. DH-06 names Vitest and React Testing Library for pure and client behavior. US-1.3's proposal deferred them to 'the story that first has behavior to test', and later stories used node --test with no decision record. node --test loads only modules with no @/ alias, no server-only import and no JSX. So valueFor and draftOf, pure helpers inside component files, are reachable only through Playwright, as is the decision logic in the onKey handler at approvals-panel.tsx:229 (complexity 27).
- **Why it matters:** Contributors cannot tell where a new test belongs, and the riskiest client logic has no fast test path.
- **Recommendation:** Record a short decision naming each mechanism's scope and the reason for it, as DH-09 asks for exceptions. Then either move pure component logic into leaf lib/ modules covered by node --test, or adopt Vitest and React Testing Library in a scoped story with pinned versions. Document the tests/db JSON-case protocol in the harness runbook.
- **Rule check:** DH-06 Next.js testing and DH-09 (keep decisions and exceptions in concise ADRs; no speculative frameworks). The decision makes the deviation explicit and mandates no framework. A Vitest adoption would be a repo-local, pinned install inside its own story.
- **Verification:** revised. The mechanisms, the US-1.3 deferral (proposal.md:28), the 44 check scripts and the complexity figures (eslint.json) confirmed. Revised: node --test runs two web unit files, Playwright 40 specs, and onKey is a handler closure rather than a pure helper.

```text
docs/engineering/decisions/00xx-test-runners.md
- pytest: services/agent (async, fake transports)
- unittest: tests/harness, tests/toolchain (stdlib, so harness runs unprepared)
- node --test: pure TypeScript leaf modules (apps/web/lib, packages/*), selected by glob
- Playwright: browser flows, from the qualifiers' shared suite list
- JSON-case scripts: tests/db on disposable targets
apps/web/lib/operations-values.ts  <- valueFor, tested by node --test
apps/web/lib/expert-draft.ts       <- draftOf, tested by node --test
```

### <a id="xtol-11"></a>XTOL-11: No CI or Git hook runs any profile, and make check covers only the harness

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [Makefile:232-234](../../../../Makefile#L232): validate, then the harness profile
  - [scripts/verify.py:79-88](../../../../scripts/verify.py#L79): the harness profile validates the backlog a second time
  - [PRD-Development-Harness.md:123](../../../../PRD-Development-Harness.md#L123): Git hooks may call the same runner
- **Evidence:** .github does not exist, core.hooksPath is unset and .git/hooks holds only samples; CODEBASE.md also notes no CI. `make check` runs `specs.py validate` and then the harness profile, which runs `specs.py validate` again as backlog_validation and runs no lint, type check or application test. Latest durations: harness 28 s, fast 44 s (Python scope), full 95 s, db 610 s, operations 266 s.
- **Why it matters:** Commits made outside an assistant session reach main with no gate. The Stop hook is the only trigger, and DH-05 says bypassable hooks cannot be the only completion check.
- **Recommendation:** Track `.githooks/pre-commit` running the fast profile (changed scope; no services, network or model), and document the explicit opt-in `git config core.hooksPath .githooks`. Run full before merging, either as a pre-push opt-in or as a job on a self-hosted Apple Silicon runner after `scripts/toolchain.py bootstrap`, keeping `.checks/full/latest.json` as the artifact. Keep db and operations manual, because they start disposable Docker projects. Drop make check's duplicate `specs.py validate`, and add a fast target beside it: fast exits 2 on a checkout that was never bootstrapped, so check can stay on harness for unprepared checkouts.
- **Rule check:** DH-05 (Git hooks may call the same runner; bypassable hooks are not the only completion check) and AGENTS.md (no installs or services in hooks). The hook runs fast only, and the opt-in is explicit, not a silent settings change.
- **Verification:** revised. .github is absent, core.hooksPath is unset, .git/hooks holds only samples, and make check validates the backlog twice; durations match the latest reports within a second. Revised: fast needs a prepared toolchain, so the Makefile gains a target instead of repointing check.

```text
#!/bin/sh
# .githooks/pre-commit. Opt in with: git config core.hooksPath .githooks
# DH-05: the same runner as the assistant hooks; bypassable, so never the completion check.
exec python3.12 scripts/verify.py --profile fast

# Makefile
check:        # harness only, so it works before bootstrap; it already validates the backlog
	python3.12 scripts/verify.py --profile harness
check-fast:   # needs scripts/toolchain.py bootstrap
	python3.12 scripts/verify.py --profile fast

# CI, if adopted: pinned node, python3.12 and uv on PATH
#   -> python3.12 scripts/toolchain.py bootstrap -> python3.12 scripts/verify.py --profile full
```

### <a id="xtol-12"></a>XTOL-12: packages/api-client and infra JavaScript sit outside lint and format, and the contract test outside any type check

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/package.json:6-7](../../../../apps/web/package.json#L6): lint and format paths cover apps/web only
  - [packages/api-client/tsconfig.json:19-21](../../../../packages/api-client/tsconfig.json#L19): includes src only
  - [packages/api-client/src/runtime.ts:1](../../../../packages/api-client/src/runtime.ts#L1): the hand-written validator behind every parse function
  - [packages/api-client/tests/contract.test.ts:5-6](../../../../packages/api-client/tests/contract.test.ts#L5): run by node, never type-checked
  - [infra/browser/browser-entrypoint.js:8-11](../../../../infra/browser/browser-entrypoint.js#L8): the DevTools forwarder, with no check at all
- **Evidence:** `lint` is `eslint --max-warnings=0 .` run in apps/web, and `format:check` lists apps/web paths only, so runtime.ts (172 lines) is neither linted nor format-checked. The api-client tsconfig includes only `src/**/*.ts`, so contract.test.ts (40 lines) runs but is never type-checked. infra/browser/browser-entrypoint.js (69 lines) has no lint or type check. Linted from the root with the web config in this review, runtime.ts and contract.test.ts pass.
- **Why it matters:** The module that validates every response at the trust boundary has looser checks than the screens that consume it. Its drift would show only at runtime.
- **Recommendation:** Extend lint and format to packages/api-client, excluding generated.ts. Include tests/**/*.ts in its tsconfig. Give infra/browser/*.js `// @ts-check` and a checkJs type check.
- **Rule check:** contracts.md (generated TypeScript consumes the contract; runtime parsing validates it) and DH-06 (Prettier for supported formats). generated.ts stays excluded and unedited.
- **Verification:** confirmed. The lint and format scripts, the src-only include and the missing @ts-check confirmed, with line counts 172, 40 and 69; api_client_typecheck does type-check runtime.ts itself.

```text
// packages/api-client/tsconfig.json
"include": ["src/**/*.ts", "tests/**/*.ts"]

# scripts/toolchain.py check_steps
Step('api_client_lint', (eslint, '--config', 'apps/web/eslint.config.mjs', '--max-warnings=0',
                         'packages/api-client/src/runtime.ts', 'packages/api-client/tests'), root)
Step('api_client_format', (prettier, '--check', 'packages/api-client/src/runtime.ts', 'packages/api-client/tests'), root)
```

### <a id="xtol-13"></a>XTOL-13: Prettier runs on implicit defaults, and no editor settings are shared

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/package.json:7](../../../../apps/web/package.json#L7): format:check with no config file
  - [apps/web/package.json:34](../../../../apps/web/package.json#L34): the style lives in this pin
- **Evidence:** git ls-files finds no .prettierrc, prettier.config.*, .prettierignore or .editorconfig, and no prettier key in any package.json. format:check passes on Prettier 3.9.10's defaults (80 columns, double quotes, trailing commas everywhere), while Python uses 100 columns.
- **Why it matters:** An upgrade that changes a default would reformat the app, and editors cannot pick up either language's width or indentation.
- **Recommendation:** Commit a `.prettierrc.json` stating today's effective options, which changes no file, and a small `.editorconfig` for both languages.
- **Rule check:** DH-06 (pinned ESLint and Prettier for supported text formats).
- **Verification:** confirmed. git ls-files finds no Prettier or editor configuration and only one prettier entry, the 3.9.10 pin; the stated options are Prettier 3 defaults.

```text
// .prettierrc.json
{ "printWidth": 80, "singleQuote": false, "semi": true, "trailingComma": "all" }

# .editorconfig
root = true
[*]
end_of_line = lf
insert_final_newline = true
[*.py]
indent_size = 4
max_line_length = 100
[*.{ts,tsx,mjs,json,css}]
indent_size = 2
max_line_length = 80
```

### <a id="xtol-14"></a>XTOL-14: 295 suppression comments are dead, written for a linter that never runs there

- **Severity** low · **Dimension** comments · **Effort** S · **Risk** low · **Occurrences** 295
- **Where:**
  - [tests/db/assignment_check.py:16-24](../../../../tests/db/assignment_check.py#L16): E402 suppressions ruff does not need after a sys.path change
  - [tests/db/wake_check.py:16](../../../../tests/db/wake_check.py#L16): names PLC2701, a preview rule no config enables
  - [tests/db/restore_check.py:71](../../../../tests/db/restore_check.py#L71): names BLE001, enabled nowhere
  - [scripts/persistent_install.py:291-292](../../../../scripts/persistent_install.py#L291): names PLC0415, enabled nowhere
  - [services/agent/src/autobots/application/goal_loop.py:127](../../../../services/agent/src/autobots/application/goal_loop.py#L127): the service's form: a code and a reason
- **Evidence:** RUF100 over scripts and tests reports 295 unused suppressions, 290 of them in tests/db. 272 are unused E402 suppressions, because ruff exempts imports that follow a sys.path change; 6 of those also name PLC2701. Another 14 name PLC0415, 8 name BLE001 and 1 names PLC2701. The service's three suppressions are all used, and two give a reason after ' - '.
- **Why it matters:** Dead suppressions suggest rules are active where none are, and they hide the few that will matter once a linter runs.
- **Recommendation:** When the shared config lands, settle its rule selection first, then run `ruff check --select RUF100 --fix scripts tests` once, as an explicit commit. Selecting BLE001 first (XTOL-08) keeps the 8 BLE001 markers, which already carry reasons; selecting PLC0415 would keep its 14. The 272 E402 markers and the PLC2701 mentions, for a preview rule, can go. Keep a suppression only with a code and a reason, as the service does.
- **Rule check:** DH-06 (keep exceptions narrow and documented) and the ground rule to keep decision and story citations. Only lint directives are removed.
- **Verification:** revised. A RUF100 rerun reproduces 295 hits (290 in tests/db; 272 E402, 14 PLC0415, 8 BLE001, 7 PLC2701 mentions), and ruff 0.17.3 marks PLC2701 as preview. Revised: the cleanup follows the rule selection, so reasoned BLE001 markers are not deleted only to be re-added.

### <a id="xtol-15"></a>XTOL-15: apps/web omits erasableSyntaxOnly although its unit tests run through Node type stripping

- **Severity** low · **Dimension** types · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [packages/api-client/tsconfig.json:15](../../../../packages/api-client/tsconfig.json#L15): set here
  - [apps/web/tsconfig.json:2-18](../../../../apps/web/tsconfig.json#L2): absent here
  - [apps/web/tests/unit/request-guard.test.ts:4](../../../../apps/web/tests/unit/request-guard.test.ts#L4): imports a lib file by its .ts path under node --test
- **Evidence:** node --test strips types and cannot run enums, namespaces or parameter properties. packages/api-client sets erasableSyntaxOnly for this reason. apps/web does not, though its unit tests load lib files the same way. No such syntax exists in apps/web today (a grep finds none), so the flag costs nothing.
- **Why it matters:** A lib file using an enum would type-check and lint cleanly, then fail only when the unit runner loads it.
- **Recommendation:** Add `"erasableSyntaxOnly": true` to apps/web/tsconfig.json, so tsc rejects what the unit runner cannot execute.
- **Rule check:** nextjs.md (strict TypeScript). It only tightens a compiler option.
- **Verification:** confirmed. The flag sits at packages/api-client/tsconfig.json:15 and is absent from apps/web; rg finds no enum, namespace, parameter property or import-equals in apps/web, and TypeScript is 6.0.3.

### <a id="xtol-16"></a>XTOL-16: verify.py keeps a weaker subprocess runner beside toolchain.run_step

- **Severity** low · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [scripts/verify.py:61-76](../../../../scripts/verify.py#L61): subprocess.run with a literal 60-second timeout
  - [scripts/verify.py:24-25](../../../../scripts/verify.py#L24): run_step is already imported
  - [scripts/toolchain.py:229-256](../../../../scripts/toolchain.py#L229): new session, group kill, bounded output
  - [scripts/harness_lib.py:454-482](../../../../scripts/harness_lib.py#L454): a third copy of the group-kill logic
  - [scripts/verify.py:27](../../../../scripts/verify.py#L27): exit codes and utc() are also defined twice (toolchain.py:48 and :225)
- **Evidence:** run_check calls `subprocess.run(argv, ..., timeout=60)`. On timeout CPython kills only the direct child, so processes a test started keep running, whereas toolchain.run_step starts a new session and kills the whole group. The harness suite uses 24 to 27 s of that fixed 60 s in the latest reports. EXIT_* and utc() are defined in both verify.py and toolchain.py.
- **Why it matters:** Two runners in one verifier time out differently. As the harness suite grows, it will hit an unnamed limit and may leave stray processes behind.
- **Recommendation:** Move the group-kill process runner into one helper that run_step, run_check and probe_version share, with a named timeout constant for the harness checks, and keep each report's fields (command_argv, duration_seconds). Import the exit codes and utc() from one module.
- **Rule check:** DH-05 (deadlines and bounded output for checks). Behavior is unchanged except that a timeout also ends descendants.
- **Verification:** revised. The literal 60-second timeout, the two group-kill copies and the duplicated constants confirmed; harness_behavior_tests took 23.7 to 26.2 s. Revised: the reports carry fields run_step does not write, so share the process helper rather than swap the runner.

## Rejected during verification

No finding was rejected. All 16 were kept, 10 of them revised.

Verification re-opened every cited location and recounted each pattern with rg, ruff 0.17.3 (isolated, no cache), AST and tokenize scans, command-line ESLint rules and the installed library sources. It changed no file outside this folder.

## Not covered

mypy, tsc and Prettier are not in this lens's command list, so I ran none of them. How many errors a relaxed mypy over scripts and tests/db would report is not measured, and the import-contract claim rests on a stdlib resolver written for this review. I did not run scripts/verify.py. Durations, argv and statuses come from `.checks/<profile>/latest.json`, whose fast (2026-11-09) and full (2026-11-08) runs may predate HEAD; verify.py itself last changed on 2026-11-06. The type-aware ESLint counts used --parser-options projectService:true on the command line, not a committed config. Playwright filter coverage was simulated with Python regular expressions against spec paths, which may differ from Playwright's matching in edge cases. The format-churn and residual-E501 numbers come from a scratch copy formatted outside the repository. SQL (64 files), YAML, Dockerfiles and the Makefile have no static tooling; I evaluated no SQL linter, because adopting one needs a new dependency and a decision. PRD-Development-Harness.md, the toolchains runbook, qualify_faults.py, test_manifests.py, persistent_install.py and app_db.py were read only in the sections cited. Code quality beyond the cited lines is left to the area reviewers. Scratch ESLint outputs are in .checks/reviews/review-2026-11-12-09-52-30/sweep-tooling/.
