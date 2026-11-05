# US-1.2 evidence

**Scope:** shared instructions, project assistant assets, derived adapter status and a forward ingestion exercise. Requirements: SP-001, SP-017, DH-03, DH-04, SP-020 H0-02. This does not establish H0, H1, product acceptance, assistant event delivery or adapter qualification. [Work record](../../work-items/US-1.2.md). Change: `us-1-2-h0-shared-instructions-development`.

**Evidence kinds:** static and local checks. Disposable: scratch copies, the arranged adapter runs (a reduced `PATH`, a stub CLI) and the synthetic forward fixture. Live, narrowly: the real `claude --version` and `claude plugin validate` output, CLI 2.1.314. Mock: none beyond the stub. No product code, service, database or application model call. The ingestor ran as a developer-assistant delegation, which is not application inference.

## Reviewed inputs

`reviewed-manifest.json`: 34 files, fingerprint `88121c61d7a9bf19371dae19b8893624865c2438c2170323be84fa05cf97f51b`. `review.md`, `test-report.md` and the manifest state the same value. `test-report.md` records `story_manifest.py compare` passing first and last; `review.md` records it before the review, and the reviewer reported it first and last in its handback. The two tables here are excluded from the manifest and were handed to the reviewer directly: [DH-04 table](dh-04-table.md), [common-rules table](common-rules-table.md).

## Scenario results, by `ohmyorch:tester`

| Scenario | Result | Rests on |
|---|---|---|
| Keep development policy portable | PASS | **Observed:** asset tests, harness (122 tests), `project_configuration` no errors, negative controls on real text copies. **By reading:** rule links, the `AGENTS.md` mapping, 12 common-rule rows, DH-04 tables. **Decisions:** coordinator decisions 1 and 8 below |
| Separate optional assistant activation | PASS, **on arranged conditions** | **Observed:** `inactive` / `unavailable` with a reduced `PATH`; `inactive` / `version_below_minimum` with a stub; `configuration_invalid` or `minimum_unknown` on scratch configurations; real state `configured_unqualified` / `delivery_unverified`. No provider or `claude -p` added. **No real adapter was inactive on this machine.** **Decision:** scoring from an arranged Given is the user's, 2026-11-05. "Incompatible" covering presence, version and configuration is the coordinator's, and the developer client's model route was not checked |
| Ingest without inventing product behavior | PASS, **on a synthetic fixture** | **Observed by the tester:** the persisted output against the result fixed in the runbook before the run; render, validate, hash bindings, identity, SP and dependency diffs; stale-navigation recovery; other sources unchanged; real `SPECS.md` not written. **By reading:** new story traces to sources; the seven-retry prototype did not become a requirement; the summary claims no delivery. One run shows one output, not that the ingestor is reliable. The definition loaded by this session is unproven, because the session started before the ingestor edit. **Provenance limit:** the tester did not observe the delegation or persistence, only their artifacts; `raw-response.md` being the literal response rests on the coordinator's report. **The coordinator's prompt also shaped the output:** it told the agent to preserve existing statuses, `Change:` lines, dependencies and SP coverage, and to say it ran no validator. So that preservation, including the `Change:` line, cannot be credited to the ingestor's definition alone, and the check that the summary says no validation ran does not discriminate. It also had the agent resolve the paths itself, where runbook step 2 passes them. That it claims no delivery was not prompted. The prompt, raw response and copies are retained in [forward-fixture/](forward-fixture/) |

## Runbook exercise status

The [development harness runbook](../../runbooks/development-harness.md) is the DH-W05 procedure, and this is the record it links to.

- **Last exercised:** 2026-11-05, working tree on base revision `97149303f46b133bac57638d91113f8d06b55663` with this story's reviewed inputs, fingerprint above.
- **Result:** passed for the tester-exercised steps below. `verify.py --profile harness` exit 0, `specs.py validate` exit 0, pending profiles exit 2.
- **Exercised by the tester:** validate; harness verification; `--profile db`; adapter status; arranged unavailable and incompatible blocks; both forward tester blocks; stale-navigation recovery; the arrangement's refusal of an existing destination.
- **Performed by the coordinator, by design, not a pass result:** forward steps 1 to 4 (arrange, hash, delegate, inspect, persist verbatim). The tester's result for these is "artifacts consistent". Step 3's record, written after the exercise and the coordinator's own account: the coordinator read the returned headings and `INGESTION SUMMARY`, saw one added story, US-1.5, with the existing four preserved, a document starting at its title with no preamble, and made no edits.
- **Untested:** `render` on the real `SPECS.md`; `version_unknown` as a full run (unit tests only); `minimum_unknown` and `configuration_invalid` as a full verifier run (helper on a scratch root only); `verify.lock`; the completion hook block; secret and destructive-command denial; live event delivery; the whole "Inspect or use the assistant integration" section beyond adapter status; and these failure and recovery rows: "Stale harness report", "Missing source or malformed scenario" and "READY story with unfinished dependency" (negative controls show detection only, not recovery), the missing-anchor branch (unit test only), and "Forward ingestion output fails".

## CLI control

With CLI 2.1.314, the plugin-shaped pair under `--strict` discriminates on one skill fault, and the `.claude`-shaped pair does not. The reviewer confirmed that reading and re-ran both pairs. **Records disagree on wording, and this is their reconciliation:** the review says DH-04's "qualified CLI" clause is "met within these limits", using "qualified" to mean only a recorded version at or above the minimum. The adaptation page says this "claims no qualification", and the test report says the output "qualifies nothing". **The coordinator's reading, not a user decision:** a recorded version was used for a check that discriminates one fault. The sources use "qualified" more strongly elsewhere (DH-05, contract line 21), so this should not be read as qualification. The pair counts only on one reading, with the fault in `warnings`, `errors` empty and `--strict` promoting it; if that is rejected, DH-04's clause is not met. The reviewer also found `name: [unclosed` passes the CLI under `--strict`, so it catches some malformed YAML, not all. The harness frontmatter test catches that case only through its name comparison: it does not parse YAML, so malformed values in other fields are not shown to be caught. The final-tree copies on the adaptation page predate the two agent edits; the review's rerun gave the same results.

## Decisions

**By the user, 2026-11-05:** scoring from an arranged Given. The user answered a question stating the coordinator's sentence as a standing rule by choosing "Score from arranged test (Recommended)". Plan line 38 names only this scenario; the bridge and Decision 0002 state the general rule, as the question did. If overturned, the score and records change, not the code or observations.

**By the coordinator, not put to the user, and open to be overturned:** "each rule" granularity (1); "incompatible" scope, with the model route unchecked (3); the fallback in decision 4, which did not apply; the coordinator as the ingestor's paired caller (5); leaving the two qualification literals unchanged (6); carrying uncommitted edits at `select` (7); the runbook linking to this record for exercise status (8). **Decision 8 departs from SP-018's literal wording** and is supported for location only; the bridge applies it to later stories. The user should confirm or reject it.

Decision 3 is narrower than the sources, and "incompatible" was exercised for version and configuration only. Decision 7 departs from a bridge "must" with no source permitting it.

Plan and proposal lines saying Decision 2 is unconfirmed, including plan lines 35, 255, 439, 440, 483 and 492 and proposal lines 59 and 92, predate the user's confirmation and are superseded. They are in the manifest and were not edited.

**Qualification literals:** the two stored values are not a complete list of observations. One plugin `PreToolUse` refusal, later hook runs and this story's delegated agents were observed, and none qualifies delivery.

**Label mapping:** the plan and test report map the harness report's `static_or_fixture` label to `disposable`. This summary departs from that, by the coordinator's reading: it is read as static or disposable, because `backlog_validation` runs on the real `SPECS.md`. US-1.4 owns that label.

## Corrections to the verdicts

Found by adversarial checks, which edit nothing. All were non-blocking, and no conclusion changed.

- `test-report.md` line 23 says raw output is under `.checks/US-1.2/test/` and `forward/`. For several results that is not so: the arranged adapter runs (only the stub's argument records remain, and `latest.json` was overwritten by the final real run), the scratch-configuration, mutation and negative-control probes (only copies were retained), forward `render` and `validate`, the stale run, doctor, `workflow-status`, `compare` and the pending-profile runs. Those exist only as text in the report.
- "No difference" from the fixed forward result overstates slightly: US-1.5 also cites `PRD.md#req-02-local-storage`, beyond the fixed `req-06` citation. It traces to REQ-06's own text, and the report records it.
- The ingestor's own summary flagged that the sources do not state the fixture's US-1.3 dependency on US-1.2, which comes from the existing backlog and was preserved. The test report's list omits that flag.
- `review.md` and the upstream gate should not be read as OpenSpec verification of the ingestion scenario: no verification ran after the forward exercise, and `completion-gate.sh`'s text match also accepts "not verified".
- `tests/harness` uses `tempfile.TemporaryDirectory()` with no directory, so test runs do create temporary directories outside the project, in the system temporary location, apart from two that use `.checks` or the destination's parent. Removal was read in cleanup code, not observed. The report left this unconfirmed.
- `status.md` was stale when these checks ran. It is derived, and the coordinator refreshes it before relying on it.

## Limits

User decisions are known to specialists only from project records. Valid syntax does not show that rules, skills or agents load in a live session, or that hook events are delivered. Whether `claude --version` or `claude plugin validate` reach the network is unknown. Link presence does not make a check exist: four linked profiles exit 2, so review is what applies to those layers today. The delegation's route and cost were not observed. The tables' verbatim persistence was not confirmed by the reviewer, and the common-rules "final-tree run" relies on the first run for unchanged files, though reviewer and tester reread the final tree. `assistant_adapter` reads the project file, not effective settings across scopes, and does not separate project hooks from plugin hooks. DH-04 tables, rule aptness and common-rule rows are inspection. `README.md` still links HARNESS-ADAPT-001 as "Evidence"; `PRD-Development-Harness.md` line 123 still says `python3 scripts/verify.py`. Neither was changed. Files unchanged since the first common-rules run were not reread line by line.

## Retained artifacts

**Versioned here:** [forward-fixture/](forward-fixture/) holds `before/` (the arranged copy and untouched comparison), `run-1/` (the ingestor's output after the tester's render), the raw response and summary, definition hashes and the delegation prompt. [adversarial-checks.json](adversarial-checks.json) holds the three adversarial results. **Ignored, local and not retained beyond this machine:** `.checks/US-1.2/`, including tester output, scratch roots and CLI control copies, kept until someone clears them. Results listed under Corrections as existing only as report text are retained in the verdicts, not in `.checks`.

**Failure history:** round 1 review at fingerprint `bdf741ed…` requested changes (`history/review-r1.md`). Final verification values are in the [manifest](verification.json), written at `mark-done`.

## Archive conditions

Before `archive`: `python3.12 scripts/story_manifest.py compare US-1.2` printed `PASS: compare: US-1.2: 34 files match the reviewed manifest`, exit 0. `verify.py --profile harness` exit 0 (harness evidence only). `test-report.md` has no `UNVERIFIED` row.
