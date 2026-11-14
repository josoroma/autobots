# Code quality review prompt

This prompt reviews the Autobots code for standards, modules, file and function size, structure, approaches, comments, types and maintainability. It proposes best practices and a refactoring plan. Each run writes a new folder, `docs/reviews/review-<yyyy-mm-dd-hh-mm-ss>/`, and changes no source file.

- **With several agents (recommended):** ask Claude Code to "run the code-quality-review workflow". The workflow, [`.claude/workflows/code-quality-review.js`](../../.claude/workflows/code-quality-review.js), splits the repository into areas and lenses, and every agent it starts reads this file. It takes an optional `{"timestamp": "yyyy-mm-dd-hh-mm-ss"}` argument. Without one, it uses the current time. A run starts about 45 agents and can take one to two hours.
  - A session started before the workflow file existed does not list it by name. Ask for it by path instead: `.claude/workflows/code-quality-review.js`.
  - If a run stops early, for example at a usage limit, start the workflow again with the same timestamp and `"resume": true`. Each reviewer saves its review under `.checks/reviews/review-<timestamp>/reviews/`. The resumed run keeps every part whose findings files exist, verifies the saved reviews, and reviews only what is missing.
  - Do not resume by run ID. That cache replays agent calls in order, and parallel agents finish in a different order each time, so it redoes finished work.
  - An agent that returns nothing gets one retry within a run. Optional `"notes": ["..."]` lines are added to the run facts that the README reports.
- **In one session:** paste everything from "Goal" down. One context cannot read the whole repository closely, so expect less depth per area.

Change the rules, rubrics and formats here. Change the areas, lenses and number of agents in the workflow.

## Goal

Review the code for quality and maintainability, then propose how to improve it. Cover these dimensions:

| Dimension | What to look at |
|---|---|
| `standards` | Conventions, lint, format and type configuration, and whether the code meets the project's own standards: DH-06 in `PRD-Development-Harness.md` and `.claude/rules/*.md` |
| `modules` | Boundaries, cohesion, coupling, dependency direction and public surface |
| `size` | File length, function length, cyclomatic complexity, nesting and parameter counts |
| `functions` | Single responsibility, level of abstraction, side effects, parameter objects, pure versus effectful code |
| `structure` | Folder and file layout, placement and file naming, compared with DH-03 |
| `approach` | Architecture and design patterns, state management, data fetching, concurrency and framework use |
| `comments` | Comments, docstrings and READMEs. Comments that explain why, versus comments that restate code. Traceability references |
| `types` | Type safety, assertions, casts and `Any`, runtime validation at trust boundaries, and use of generated contracts |
| `errors` | Error types, handling, logging, cancellation and user-facing error states |
| `tests` | Test design, size, fixtures, duplication and coverage of risky logic |
| `duplication` | Logic, data or setup repeated where a shared helper belongs |
| `naming` | Identifiers, readability, magic values and consistency |

Deliver three things: verified findings for each area, proposed standards that make best practices measurable and enforceable, and a prioritized refactoring plan.

## Output

- **Folder:** `docs/reviews/review-<timestamp>/`, with `<timestamp>` from `date +%Y-%m-%d-%H-%M-%S` at the start of the run. Stop if the folder already holds files.
- **Raw tool output:** `.checks/reviews/review-<timestamp>/`, which Git ignores. It also holds each reviewer's saved review, in `reviews/`, for resuming a stopped run.
- **Files in the folder:**
  - `README.md`: scope, method, executive summary, scorecard, top recommendations, counts, coverage and limitations, and the comparison with the previous review.
  - `standards.md`: the proposed standards.
  - `refactor-plan.md`: the prioritized plan.
  - `metrics.md`: the measurements and the exact commands that produced them.
  - `findings/<area>.md` and `findings/<area>.json`: the verified findings for each area and lens.
  - `PROMPT.md` and `workflow.js`: copies of this prompt and of the workflow that produced the run.

## Ground rules

1. **Read only.** Write nothing outside the two output folders. Install nothing, start no service, touch no database and call no model. Do not run `scripts/verify.py`. Read its latest reports in `.checks/<profile>/latest.json` instead.
2. **Project rules bind every recommendation.** Read `AGENTS.md`, the `.claude/rules/*.md` files that apply, DH-03 and DH-06 in `PRD-Development-Harness.md`, and `docs/engineering/option-b-contract.md` where states or recovery are involved. Search `docs/engineering/decisions/` before recommending a change that a decision may govern. Never recommend:
   - editing an applied migration. Propose a forward migration instead.
   - merging domain, row, DTO, graph-state and UI types, which the rules keep apart. Propose clearer mapping instead.
   - hand-editing generated files: `packages/api-client/src/generated.ts`, `packages/db-types/src/generated.ts` and `contracts/generated/`.
   - a fallback or alternative model provider, a local model or hosted tracing.
   - moving business state transitions or scheduling into Next.js.
   - weakening a guardrail, check, lease, fence or approval that a rule or decision requires.
   - dropping the practice of citing decisions and stories in comments. Judge individual comments instead.
3. **Out of scope for style and size:** the generated files above, the vendored `infra/supabase/upstream/`, `openspec/`, `docs/`, `research/`, the PRDs and `SPECS.md`. Review how generated code is consumed, not its contents.
4. **`CODEBASE.md` is a map, not proof.** Use it to find your way, then confirm in the code.
5. **Balance.** Record strengths worth keeping and spreading, not only problems.
6. **Honest evidence.** Metrics come from tools and findings come from reading code. The review is static. It is not runtime evidence, and it establishes no H1 or product acceptance.

## Scope

The review covers all tracked source under `apps/web`, `packages/api-client` and `packages/db-types` (without generated files), `services/agent`, `scripts`, `.claude/hooks`, `tests`, `supabase` and `infra` (without vendored files), plus the `Makefile` and the root `package.json`. The workflow assigns every file to exactly one area and lists any file it could not assign.

| Area | Covers |
|---|---|
| `web-run` | Run screens: workspace, list, panel, inspector, controls, disclosure, tool uses, unknown effects, and their pages |
| `web-composer` | Goal composer, home page and activity, jobs chart, search palette, sessions and the waiting notifier |
| `web-build` | Workflow editor, workflows panel and monitor, Experts panel and editor, and their pages |
| `web-tools-approvals` | Tool catalog and approvals, and their pages |
| `web-system` | Operations, model policy, provider settings, keys and vars, appearance, and the settings pages |
| `web-shell` | Shell, navigation, UI primitives, small components, layout, BFF route handlers, `lib/`, web configuration, unit tests and the `packages/api-client` runtime |
| `py-domain` | `domain/`, `contracts/`, `persistence/` and the package configuration |
| `py-run` | Application: run admission, goal loop, plans, compaction, model admission and attempts, worker inference, leases and run projection |
| `py-tools` | Application: tool gateway, catalog, grants, uses, code and browsing tools, approvals, reconciliation, the cronjob tool and tool keys |
| `py-product` | Application: Experts, assignments, workflows, routines, memory, improvements, artifacts and search |
| `py-adapters` | `adapters/`, including the model and external tool clients |
| `py-api` | `api/`: app factory, routes, security, membership and errors |
| `py-ops` | `operations/`, plus application operations, retention, provider settings, credentials and schema release |
| `py-tests` | `services/agent/tests/` |
| `db-tests` | `tests/db/`, `tests/web/`, `tests/faults/` and `tests/qualification/` |
| `web-tests` | `apps/web/tests/browser/` and the Playwright configuration |
| `harness-tests` | `tests/harness/`, `tests/toolchain/` and other `tests/` files |
| `scripts` | `scripts/`, `.claude/hooks/` and the root `package.json` |
| `sql-infra` | `supabase/`, non-vendored `infra/`, `packages/db-types/` and the `Makefile` |

Seven lenses then read across all areas. Each reports patterns that span several files or areas, and leaves single-file issues to the areas.

| Lens | Question |
|---|---|
| `sweep-boundaries` | Do dependencies point the intended way, and does the layout match DH-03? |
| `sweep-duplication` | What is repeated that should be shared? |
| `sweep-types` | Where do types stop protecting a boundary? |
| `sweep-docs-naming` | Do comments, docstrings and names tell readers what they need? |
| `sweep-errors` | Are errors typed, handled, logged and shown consistently? |
| `sweep-tooling` | Which standards does a tool enforce, and where does enforcement stop? |
| `sweep-web-architecture` | Do the screens share one approach to data, state, forms and view states? |

## Method

1. **Measure** with installed tools only. Collect line counts, Python function lengths and docstring coverage with `ast`, and ruff's complexity, branch, return and argument rules. Add ruff `ALL` statistics as an exploratory superset, the repository-level Python under the service's own ruff rules, and ESLint with extra size, complexity and assertion rules passed on the command line. Record every command in `metrics.md`.
2. **Review each area** across all dimensions. Read every file in scope in full. Use metrics as leads, never as findings on their own.
3. **Sweep each lens** across the repository.
4. **Verify adversarially.** Re-open every cited location. Reject findings whose code is missing or does something else, findings that break a ground rule, duplicates and pure taste. Recount claimed occurrences. Calibrate severity, effort and risk.
5. **Synthesize** `standards.md`, `refactor-plan.md` and `README.md` from verified findings only.
6. **Check completeness.** Every area and lens has its two findings files. Every dimension appears in `standards.md`. Every link, anchor and `file:line` resolves. Every cited finding ID exists. Every high finding is planned or explicitly deferred. Remaining gaps go to "Coverage and limitations".
7. **Compare** with the newest earlier `docs/reviews/review-*/findings/*.json`, when one exists. Report resolved, persisting and new findings.

## Rubrics

**Severity**

- `high`: makes change in the area slow or risky now, hides contract drift at a trust boundary, or is likely to cause defects. It needs a planned refactor.
- `medium`: real friction or inconsistency. Fix it in planned cleanup or when the code is next touched.
- `low`: polish. Fix it opportunistically.

**Effort:** `S` is up to half a day, `M` is half a day to three days, and `L` is more than three days or cross-cutting.

**Risk of the change:** `low` is mechanical and covered by tests. `medium` is behavior-sensitive, so tests come first. `high` touches durable state, contracts, migrations, security boundaries or paid paths.

**Scores** per dimension, from 1 to 5: 5 is a model for the rest of the repository, 4 is good with minor issues, 3 is adequate with notable friction, 2 is weak and causes recurring cost, and 1 blocks safe change. Scores use the dimensions above, plus `maintainability` as the overall judgment.

## Evidence standard

- Every finding cites at least one `file:line` opened during this run.
- A pattern finding cites up to eight locations, and states the total count and how it was counted.
- Excerpts stay within eight lines.
- No generic advice without a location, and no finding from a metric alone.
- About twenty findings per area at most. Merge repeated instances into one pattern finding. Prefer findings that change what an engineer does next.
- Every `high` finding and every size finding gives a target shape as a short sketch: the components, hooks, functions or modules to extract, each with its responsibility.

## Finding format

Finding IDs use the area's four-letter prefix and a two-digit number, such as `WRUN-03`. The anchor is the lowercase ID.

`findings/<area>.json`:

```json
{
  "schema": "autobots.code-review/v1",
  "area": "web-run",
  "title": "Web: run screens",
  "kind": "area",
  "timestamp": "2026-11-12-09-40-00",
  "revision": "<full git commit>",
  "summary": "One paragraph.",
  "scores": [{"dimension": "size", "score": 2, "why": "One line."}],
  "strengths": [{"title": "...", "evidence": "..."}],
  "findings": [{
    "id": "WRUN-01", "title": "...", "dimension": "size", "severity": "high",
    "locations": [{"file": "apps/web/components/run-workspace.tsx", "line": 152, "endLine": 830, "note": "..."}],
    "occurrences": 1, "evidence": "...", "impact": "...", "recommendation": "...", "sketch": "...",
    "effort": "M", "risk": "medium", "ruleCheck": "...", "verdict": "confirmed", "verifierNote": "..."
  }],
  "rejected": [{"id": "WRUN-07", "title": "...", "reason": "..."}],
  "notCovered": ""
}
```

`kind` is `area` or `lens`. Kept findings are sorted by severity, high first, then by ID.

`findings/<area>.md`, with source links relative to the file, as `../../../../<path>#L<line>`:

````markdown
# Web: run screens

One-paragraph summary. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|

## Strengths

- **Title.** Evidence, with links.

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [WRUN-01](#wrun-01) | high | size | ... | M | medium |

### <a id="wrun-01"></a>WRUN-01: Title

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:** [apps/web/components/run-workspace.tsx:152](../../../../apps/web/components/run-workspace.tsx#L152)
- **Evidence:** ...
- **Why it matters:** ...
- **Recommendation:** ...
- **Rule check:** ...
- **Verification:** confirmed. Verifier note.

```tsx
// Optional sketch of the target shape.
```

## Rejected during verification

| ID | Title | Reason |
|---|---|---|
````

## Standards document

`standards.md` proposes the standards. DH-06 states principles, and this document makes them measurable and enforceable. It cites existing rules instead of restating them.

- Open with a summary table: ID (`STD-01`), rule, what enforces it (a tool and rule, review, or nothing yet), and current compliance.
- Use these sections, in this order: repository structure and modules; file size; function size and complexity; function design; types and contracts for TypeScript and Python; errors and logging; comments and documentation; naming and formatting; React and Next.js; Python service layers; SQL and migrations; tests; scripts and tooling; enforcement and ratchet.
- Each standard gives the rule (MUST or SHOULD), why it matters here, the current state with numbers and linked finding IDs, the enforcement as an exact configuration snippet or check, and the adoption path: warn, then baseline, then error, and what to fix first.
- Calibrate every threshold against `metrics.md`, and state how much code is over it today.
- Mark which standards are already enforced and which are proposed.

## Refactor plan

`refactor-plan.md` turns verified findings into bounded work.

- **Principles:** changes preserve behavior. Each change is one bounded work item under the project's delivery process. Tests come first when risk is `medium` or higher. Generated artifacts are regenerated, never edited. Migrations only move forward. Each item names the `scripts/verify.py` profile that proves it. The review edits no backlog, so it suggests stories instead of adding them to `SPECS.md`.
- **Waves:** 0 is guardrails, so new code meets the standards. 1 is quick wins (`S`, low risk). 2 is hotspot refactors (`M`). 3 is structural moves (`L`).
- **Each item:** an ID (`R-01`), title, the finding IDs it addresses (linked), why now, numbered steps, files, risk and mitigations, verification, effort and dependencies.
- Open with a table of all items. End with "Suggested backlog entries" and "Considered and not recommended", which explains notable rejected ideas.
- Every `high` finding is addressed by an item or deferred with a reason.

## README

`README.md` opens with the title "Code quality review, <date and time>". Its sections are:

- scope and method: revision, working-tree state, areas, lenses, agents, and what was measured versus read;
- an executive summary in five to eight bullets;
- a scorecard by area and dimension, and the lenses' repository-wide scores;
- the top eight to ten recommendations, linked to plan items and findings;
- strengths to keep;
- finding counts by severity and area;
- the documents in the folder;
- coverage and limitations;
- changes since the previous review;
- how to rerun.
