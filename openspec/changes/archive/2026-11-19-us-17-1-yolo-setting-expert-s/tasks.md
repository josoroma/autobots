# Tasks

## 1. Data and admission

- [x] 1.1 Add migration `20261119000065_browsing_yolo.sql` with its traceability header. It holds `app_private.browsing_settings` (no row means on) and `runs.browsing_yolo` (default `false`), granted to the runtime role only. Checked by `tests/harness/test_migration_headers.py` and the db profile's migration apply.
- [x] 1.2 Freeze the setting at admission. A child takes its parent's value, otherwise the workspace's row, otherwise `true`. Checked by the db profile's new `browsing_yolo_check.py`, for a fresh run, a child and a run admitted before the setting existed.

## 2. The setting and the YOLO test

- [x] 2.1 Add `application/browsing_settings.py`: read, change at the expected version for the owner, mark the notice seen, `call_is_yolo` (frozen AND current), and the Expert's browse domains for a run. Checked by pytest under `services/agent/tests` (`test_browsing_settings.py`) and `browsing_yolo_check.py`.
- [x] 2.2 Add `contracts/browsing_settings.py` and the routes: `GET` (member) and `PUT` (owner) `/v1/settings/browsing`, and `POST /v1/settings/browsing/notice` (owner). They refuse `stale_version` and `owner_required` and leave the setting unchanged. Checked by `browsing_yolo_check.py` through the API with an owner and a member.

## 3. Approval and the browse

- [x] 3.1 Add `waived` to `ApprovalPolicy` and read it first in `hold_for_approval`, never for a consequential external write. Add the catalog label `unless_yolo`. Checked by pytest under `services/agent/tests`.
- [x] 3.2 Give `browse_goal` the waiver `call_is_yolo`. Under YOLO, refuse `browse_domains_missing` or `browse_domain_not_granted` before the executor is touched. Checked by pytest with a fake executor (no container started), and by `browsing_yolo_check.py` with a scripted model, covering four cases:
  - a YOLO call starts with no approval row;
  - turned off mid-run, the next call waits;
  - frozen off, a later run starts;
  - an outside or missing domain is refused with no container.
- [x] 3.3 Add `public_context` to `ToolDefinition`, merged into `input_public` by `begin_use`, with `browse_goal` recording `typing: on` for a YOLO call. Checked by pytest and by `browsing_yolo_check.py` reading the tool row.

## 4. Experts

- [x] 4.1 Add `browse_domains` to `ExpertConfig` and its view. A change makes a new version and leaves the earlier one as it was. Checked by pytest and by `browsing_yolo_check.py` (versions 1 and 2 compared).

## 5. Contracts and Studio

- [x] 5.1 Regenerate OpenAPI and the TypeScript client with `scripts/generate_contracts.py write`. Checked by `contract_drift` in the fast profile.
- [x] 5.2 Add Settings → Browsing: the checkbox, its line, owner-only writes and the Settings navigation entry. Checked by a new `settings-browsing.spec.ts` browser suite under `apps/web/tests/browser`, with axe, for an owner and a member.
- [x] 5.3 Add Home's one-time notice. Checked by the same suite: it shows on the first visit and not on the second.
- [x] 5.4 Add the Expert editor's browse domain list, shown while the draft grants `browse_goal`. Checked by the Experts browser suite: save it, then see version 2.
- [x] 5.5 Show `typing: on` in the run's tool row (TV-01 public fields), and "every call, unless YOLO is on" for `browse_goal` on the Tools page and in the Expert cards' approval note. Checked by the web unit tests for the texts, and the Tools and Experts browser suites.

## 6. Words and documents

- [x] 6.1 Update `browse_goal`'s guide and approval reason. Approval on every call applies with YOLO off. Under YOLO, the domains come from the Expert. An Expert browsing a wiki or forum tells it never to edit or post (Y13). Checked by pytest under `services/agent/tests` (the guide's text).
- [x] 6.2 Amend PRD-Tool-Catalog AB-01, AB-02 and TC-02, and PRD-Studio SE-02 and Home, per Decision 0035. Checked by reading each against Decision 0035 Y1 to Y4.
- [x] 6.3 Update `README.md` (the opening paragraph and "Asks before it acts"), `README-DEV.md`, the operations runbook's "Turning on browse_goal" and `CODEBASE.md`. Checked by reading each against Decision 0035 Y1 to Y4.

## 7. Verification

- [x] 7.1 Run `python3.12 scripts/verify.py --profile fast`, then the db profile, and score each scenario from what was observed. Checked by their exit codes and reports.
