# Browser suites

The Playwright specs here run against real local services that a runner starts and arranges. Every
value comes from the runner, so a spec run without its runner fails and names the missing variable
(`support/env.ts`). `npx playwright test --list --project <name>` needs no environment.

## Projects

Each project is one environment, and `projects.json` lists its spec files. `playwright.config.ts`
builds each project's `testMatch` from that list, and each runner passes its own project with
`--project`. A spec belongs to exactly one project. `tests/harness/test_suite_claims.py` fails when a
spec is in no project or in two, when a project isn't one `scripts/suites.py` names, or when a project
that no profile runs holds a spec `suites.MANUAL` doesn't list with its reason (R-58, TWEB-01).

| Project           | Runner                                           | Environment                                                                                                              |
| ----------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `web`             | `scripts/qualify_web.py` (`full`)                | The API with an arranged membership and minted sessions, and no Auth service                                             |
| `main`            | `scripts/qualify_identity.py` (`db`)             | A disposable Supabase stack with real Auth and the arranged workspaces, and no worker                                    |
| `arranged`        | `scripts/qualify_identity.py` (`db`)             | The same stack. Each test runs alone, selected with `-g <title>`, after the runner arranges that test's state            |
| `slice`           | `scripts/qualify_identity.py` (`db`)             | The same stack with the scripted worker running                                                                          |
| `release`         | `scripts/qualify_release.py --ui`, in no profile | US-10.1's timing on a disposable stack with the real API and the worker stopped                                          |
| `install-current` | `scripts/persistent_install.py screens`          | Read-only on the persistent install, as its owner (Decision 0023)                                                        |
| `install`         | By hand, in no profile                           | Read-only on the persistent install, run with `--project install` as US-11.3 ran it for its local app and upgrade checks |

Playwright runs one worker and sorts a project's files by name, so `main` runs its files in the same
order every time. Inside a file, tests run in the order they're written.

A failure in `web`, `main`, `arranged` or `slice` keeps its trace and a screenshot in the runner's
output directory under `.checks`, which is ignored (TWEB-15). The install projects keep neither,
since they sign in with the persistent owner's real password, and `release` keeps neither because it
measures timing.

## Shared state

Some `main` suites sign in to a workspace arranged for them alone. The rest share workspace A, and
`support/state.ts` makes explicit what they hand on (TWEB-01):

- A suite that needs a state checks it through the API in `beforeAll`, so a broken chain fails at
  its source. The hook sits in an untitled `test.describe` around only the tests that need the
  state, since Playwright runs a file's `beforeAll` again in the worker it restarts after a failure.
  In `settings.spec.ts`, `startsWithoutProviderKey` checks that workspace A has no saved key before
  the tests that need none. `qualification.spec.ts` checks that it has one that authenticated.
- A suite that changes a state restores it in `afterAll`, which runs whatever the tests' outcome. A
  restore reads the state first and writes only when it differs, so a run whose tests all pass writes
  nothing more than they do.

| State                 | Restored by                                                  | Restored to                             |
| --------------------- | ------------------------------------------------------------ | --------------------------------------- |
| Workspace A's key     | `experts.spec.ts`, `runs.spec.ts` (`removeProviderKeyIfAny`) | No saved key                            |
| Saved keys and values | `settings-keys-and-vars.spec.ts`                             | Nothing saved in Settings → Keys & vars |
| Worker heartbeats     | `operations-values.spec.ts`                                  | The two it starts are stopped           |
| Retention windows     | `operations.spec.ts` (`restoreRetentionIfSaved`)             | Keep everything                         |
| Model policy          | `slice-policy.spec.ts` (`restoreModelPolicyIfChanged`)       | Terra, with no role overrides           |

Tests that build on the one before them are grouped in an untitled `test.describe` with serial mode,
so a failure skips its dependents instead of failing them for its reason (TWEB-07). The group adds
nothing to the tests' titles. Tests that don't depend on each other stay out of these groups.

## Selectors

- Find by role and accessible name first, then by label: `getByRole("button", { name: "Save" })`,
  `getByLabel("API key")`. That checks what a person using a screen reader gets, too (DH-06).
- Find a message by its role, `getByRole("status")` or `getByRole("alert")`, filtered by its text,
  and scoped to the region it belongs to when another message could show beside it. For example,
  `providerMessage` in `support/keys.ts` finds the provider card by its `aria-labelledby` and the
  status inside it. A lookup by a hook doesn't show that a message is announced.
- The `data-message` and `data-policy-message` hooks that specs already read stay. Add a new message
  hook only where two live regions show at once and no labelled region separates them.
- Use `data-field="<name>"` for a value that has no accessible role or name, such as a status, a
  count or a version. A `data-field` hook is for tests only and never for styling. The components
  keep every hook these specs read, so renaming one means changing the specs in the same change.
- Use the other `data-*` hooks the components expose, such as `data-approval="<id>"` or
  `data-run-status`, to find a record by its ID or read a state.
- Scope inside a container by its role or hook, not by traversal. Don't add `xpath=..`,
  `locator("..")` or structural CSS such as `main li a`, which break on harmless markup changes.

## Waits

- Wait on a condition: a web-first assertion such as `toHaveText` or `toBeVisible`, a response, or
  `expect.poll`.
- When behavior depends on time, use `page.clock` rather than waiting it out. `settings-sections.spec.ts`
  moves the clock on to the notifier's next poll, and `home.spec.ts` fixes the time.
- Name long tests' phases with `test.step`, so a failure says which phase broke (TWEB-12). Titles
  don't change.
- `page.waitForTimeout` fails lint in `tests/browser` (`no-restricted-properties`, TWEB-06).
  `eslint-suppressions.json` records the sleeps that remain, each with a comment saying why, and a new
  one fails.

### What remains of TWEB-06

| Wait                                                                                                                                     | Why it stays                                                                                                       |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Short sleeps in `appearance` (2), `approvals`, `new-run`, `run-workspace` (3), `search`, `settings`, `slice-controls` and `slice-visual` | Negative observations: nothing may happen in that time, and no event marks the moment it would have                |
| `stream-result`: a 2.5 s offline window, and a 200 ms sampling loop                                                                      | The window is part of the scenario, and the loop samples the page until the helper ends                            |
| `networkidle` in `appearance` (9) and `slice-visual` (3), and in `support/visual/settle.ts`                                              | They wait for hydration, or for a page to settle before it's measured. The specs name no condition to wait on      |
| `networkidle` in `runs`, `boundary` and `search`                                                                                         | `runs` and `boundary` observe that nothing more arrives, and `search` lets the list arrive before focus is checked |
| A `setTimeout` inside a route handler in `composer`, `experts`, `workflow-list` and `run-workspace`                                      | It holds a reply in flight on purpose, as the arranged transport, so a second press or a held read can be observed |

`workflows.spec.ts`'s 84- and 73-line tests have no steps: the file is at 399 of its 400 counted
lines, and steps would pass the limit (TWEB-12).
