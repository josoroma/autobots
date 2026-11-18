# STUDIO-UI-001 — Studio interface redesign

Status: COMPLETE
Evidence: STUDIO-UI-001

## Plan

DH-W01.

- **Source:** owner request to redesign the app from the [Studio concepts](../../imagine/README.md); [Decision 0021](../decisions/0021-studio-interface-redesign.md); [PRD-Design-System.md](../../PRD/PRD-Design-System.md) DS-01–DS-05; SP-014.
- **Intended behavior and invariants:** every screen takes the Studio look: grouped sidebar, serif page titles, hairline surfaces, one accent, an attention tone for what waits for a person. Behavior, API calls, product wording, accessible names, roles and `data-*` hooks are unchanged. Dark stays the default; the selector offers only Dark and Light.
- **Affected layers, contracts and states:** `apps/web` presentation only (`app/globals.css`, the shell and sidebar, `components/ui/*`, every page and panel component), plus the token extension file `docs/design/studio-extensions.css`. No API, contract, schema, worker or run-state change.
- **Migration and operational impact:** none.
- **Verification and recovery plan:** `harness`, `full` and `db` profiles of `scripts/verify.py`, the last including `slice-visual`'s measurement of every surface in both themes on disposable stacks. Screenshots read for layout. Independent read-only review. Recovery: revert the commit.

## Implementation

DH-W02. Uncommitted on branch `studio-ui-redesign`, from `bef0c66`.

- **Revision and changed paths:**
  - Foundation, by the coordinator: `apps/web/app/globals.css`, `components/app-shell.tsx`, `components/sidebar-nav.tsx`, `components/ui/{button,badge,card,field,page-header}.tsx`, and `docs/design/studio-extensions.css`.
  - Screens, by six `autobots-nextjs` workers with disjoint files: Home and sign-in; the runs list and approvals; the run workspace and inspector; Experts, sessions and workflows; Operations and tools; Settings and Models. 46 files under `apps/web` in all.
- **Actual behavior:**
  - The sidebar groups the nine links into the daily work, **Build** and **System**. Tools stays directly before Settings, so it sits under System.
  - Each section opens with a serif title through `PageHeader`.
  - Lists and facts use hairline rows and bordered fact grids. States show as a dot or icon beside their unchanged words.
  - Light surfaces keep muted text off tinted fills; tints are dark-only.
  - The attention tone (R3) marks pending approvals and their expiry, requested input, unpublished workflows, unknown outcomes, and a tool whose every call waits for a person. That last one is a person-gated wait, which is how this item reads R3.
- **Contract, migration and configuration changes:** none. No dependency was added.
- **Stubs, deferred work and deviations from the plan:**
  - Concept elements without data are left out, as listed in Decision 0021 R6. These include a "New run" sidebar shortcut, which `appearance.spec.ts`'s keyboard flow rules out.
  - Home's "The app and your data stay on this Mac" predates this item and reads stronger than the run disclosure. It is left for its own item.
  - `/tools` isn't in `slice-visual`'s zoom paths.

## Review

DH-W03.

- **Author and reviewer:** the main session and its six delegated workers; `autobots-reviewer`, in a separate read-only context, over two passes.
- **Reviewed fingerprint:** the source manifest in [the evidence manifest](../evidence/STUDIO-UI-001/STUDIO-UI-001.json). The second pass read every file changed after the first.
- **Findings and dispositions:**
  - Three blocking findings, all resolved: color literals in `globals.css`, a link before Home in the tab order, and a shadow that replaced the focus ring.
  - Should-fix findings resolved: the tools toolbar at 320px, non-Luma preview grays, alpha-dimmed link text, the version and Queued tones, and a constant "Waiting for a decision" badge. The second pass found nothing blocking or new.
  - Kept: the attention tone on approval expiry and on the person-gated tool property (see above). The pre-existing Home sentence is deferred.

## Verification

DH-W04. [Summary](../evidence/STUDIO-UI-001/summary.md) and [manifest](../evidence/STUDIO-UI-001/STUDIO-UI-001.json).

- **Classes and model transport:** static, local runtime, and real browser on disposable stacks with a scripted worker. Model transport: none.
- **Failures, errors, skips and limits:** the first runs failed `appearance.spec.ts` (three tests) and `slice-visual` on every light surface, all corrected before the passing runs. The limits are in the summary.

## Runbook

DH-W05. Operating behavior is unchanged. The [development harness runbook](../runbooks/development-harness.md)'s verification profiles were exercised; the `db` run's visual capture is the recorded exercise.
