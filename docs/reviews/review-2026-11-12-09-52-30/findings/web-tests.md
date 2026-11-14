# Tests: browser suites

The 41 Playwright specs (10,283 lines, 199 test declarations) test real behavior and say plainly what they cover. They drive the built app against disposable stacks and mostly use role and label queries (610, against 590 data-attribute selectors). They inject lost replies, dropped streams and offline periods, and they check that keys and private reasoning stay out of the browser. They verify DS-02 first paint frame by frame and test the visual instrument against a page broken on purpose. The cost comes from having no shared test layer. Every file re-implements sign-in, CSRF headers, provider-key setup, axe scans and Python helper calls, about 747 copied lines in 38 files. The specs read 232 API responses as untyped any, although the generated client exports 170 parsers, and they read 104 environment variables, nearly all defaulting to empty strings. Suites also depend on one another. Four Python runners pick specs by filename substrings, Playwright runs files in alphabetical order, cleanup sits in test bodies, and some of the comments that describe the order are already wrong. Within files, two specs have undeclared order dependence, and three hold tests that are valid only one at a time. slice-visual.spec.ts fits a 116-line untyped in-page script, an arranger, a surface table with stale 'absent' notes and a 10-minute loop test into 1,057 lines. Accessibility checks vary by file: there are four axe tag sets, and 21 of 35 scans fall below Decision 0010's WCAG 2.1 A and AA. About 50 seconds of fixed sleeps and 16 networkidle waits remain, although page.clock is already used once. A support module with role fixtures, a typed API helper built on the generated parsers, one axe helper and Playwright projects would remove most of this friction without changing what is tested. [Back to the review](../README.md)

## Scores

| Dimension | Score | Why |
|---|---|---|
| standards | 3 | Specs compile under the app's strict tsconfig and Prettier, with forbidOnly and zero retries. But nothing lints Playwright-specific patterns, there are 49 type assertions, the sleeps go unchecked and the axe tag sets drift from Decision 0010. |
| modules | 2 | There is no support module and no fixture: 41 self-contained files re-implement auth, CSRF, key setup, axe, leak checks and subprocess calls. |
| size | 2 | One spec has 1,057 lines and 9 files exceed 300 lines. 34 functions run over 60 lines, 30 of them test bodies (the longest has 155), and 39 have more than 25 statements. |
| functions | 3 | Local helpers are mostly small and well named (cardOf, openPanel, expectState, presentation). Several mix arrangement with action, and some tests verify five behaviors at once. |
| structure | 2 | The directory is flat. Four Python scripts route specs by filename substrings, and state passes between files in alphabetical order. Settings → Models is spread over five files by environment. |
| approach | 3 | Real-stack flows with fault injection, offline emulation, keyboard walks and leak checks. Fixed sleeps, networkidle waits, string-injected scripts and the lack of fixtures and projects weaken it. |
| comments | 4 | Comments explain why, cite story and decision IDs, and name the script that arranges each suite's data. A few notes on cross-file order and on evidence have gone stale. |
| types | 2 | 232 API reads are implicit any, typed only by inline shapes and casts, while the 170 generated parsers go unused. |
| errors | 3 | Five try/finally blocks and slice-visual's settle diagnostics are good. Against them: arrangement writes go unchecked, subprocess helpers have no timeout and fail with unhelpful errors, cleanup sits in test bodies and leak checks race their reads. |
| tests | 3 | Behavior and boundary coverage is broad and runs in both themes. But order dependence is undeclared, some leak checks can pass without inspecting anything, and the visual inventory misses seven routes. |
| maintainability | 2 | A change to the sign-in UI or an API contract, a new spec or a rename touches many files or breaks unrelated suites. |

## Strengths

- **Behavior-named tests with traceable sources.** Titles state the observable outcome. Header comments name the story, the decision and the script that arranges the data: composer.spec.ts:6-8, home.spec.ts:4-8, operations-jobs.spec.ts:5-9, run-panel.spec.ts:5-6, search.spec.ts:4-5. Sources: [apps/web/tests/browser/composer.spec.ts:6-8](../../../../apps/web/tests/browser/composer.spec.ts#L6), [apps/web/tests/browser/home.spec.ts:4-8](../../../../apps/web/tests/browser/home.spec.ts#L4), [apps/web/tests/browser/operations-jobs.spec.ts:5-9](../../../../apps/web/tests/browser/operations-jobs.spec.ts#L5), [apps/web/tests/browser/run-panel.spec.ts:5-6](../../../../apps/web/tests/browser/run-panel.spec.ts#L5), [apps/web/tests/browser/search.spec.ts:4-5](../../../../apps/web/tests/browser/search.spec.ts#L4).
- **Accessible queries and real keyboard paths.** 610 getByRole, getByLabel, getByText and getByPlaceholder calls. Tests check the skip link, New run and Search order (appearance.spec.ts:292-307, search.spec.ts:72-88), focus return after Escape (tools.spec.ts:223-239, search.spec.ts:147-157) and aria-activedescendant movement (search.spec.ts:117-128). Sources: [apps/web/tests/browser/appearance.spec.ts:292-307](../../../../apps/web/tests/browser/appearance.spec.ts#L292), [apps/web/tests/browser/search.spec.ts:72-88](../../../../apps/web/tests/browser/search.spec.ts#L72), [apps/web/tests/browser/tools.spec.ts:223-239](../../../../apps/web/tests/browser/tools.spec.ts#L223), [apps/web/tests/browser/search.spec.ts:147-157](../../../../apps/web/tests/browser/search.spec.ts#L147), [apps/web/tests/browser/search.spec.ts:117-128](../../../../apps/web/tests/browser/search.spec.ts#L117).
- **Failure paths injected on purpose.** Aborted streams reconnect without duplicates (run-workspace.spec.ts:107-137). Committed but lost replies reuse the idempotency key (slice-run-details.spec.ts:330-366, 402-426). Also covered: malformed replies (slice-workflows.spec.ts:152-166), real offline periods (slice-closure.spec.ts:162-183) and request rewriting to reach server-side refusals (composer.spec.ts:97-103, slice-run-details.spec.ts:261-267). Sources: [apps/web/tests/browser/run-workspace.spec.ts:107-137](../../../../apps/web/tests/browser/run-workspace.spec.ts#L107), [apps/web/tests/browser/slice-run-details.spec.ts:330-366](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L330), [apps/web/tests/browser/slice-run-details.spec.ts:402-426](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L402), [apps/web/tests/browser/slice-workflows.spec.ts:152-166](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L152), [apps/web/tests/browser/slice-closure.spec.ts:162-183](../../../../apps/web/tests/browser/slice-closure.spec.ts#L162), [apps/web/tests/browser/composer.spec.ts:97-103](../../../../apps/web/tests/browser/composer.spec.ts#L97), [apps/web/tests/browser/slice-run-details.spec.ts:261-267](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L261).
- **The measuring instrument is tested against a broken page.** slice-visual.spec.ts:860-917 proves that the keyboard, motion and disabled-name probes catch deliberate breakage, matching DH-09's known-bad checker fixtures. A page that never settles names its pending requests (slice-visual.spec.ts:787-815). Sources: [apps/web/tests/browser/slice-visual.spec.ts:860-917](../../../../apps/web/tests/browser/slice-visual.spec.ts#L860), [apps/web/tests/browser/slice-visual.spec.ts:787-815](../../../../apps/web/tests/browser/slice-visual.spec.ts#L787).
- **DS-02 verified at first paint.** appearance.spec.ts records every animation frame from before hydration (13-23, 52-64) and compares the consumed tokens with the canonical luma.css as the browser resolves them (129-182). It also checks the server HTML with JavaScript disabled (107-127) and the case of unavailable storage (247-271). Sources: [apps/web/tests/browser/appearance.spec.ts:13-23](../../../../apps/web/tests/browser/appearance.spec.ts#L13), [apps/web/tests/browser/appearance.spec.ts:52-64](../../../../apps/web/tests/browser/appearance.spec.ts#L52), [apps/web/tests/browser/appearance.spec.ts:129-182](../../../../apps/web/tests/browser/appearance.spec.ts#L129), [apps/web/tests/browser/appearance.spec.ts:107-127](../../../../apps/web/tests/browser/appearance.spec.ts#L107), [apps/web/tests/browser/appearance.spec.ts:247-271](../../../../apps/web/tests/browser/appearance.spec.ts#L247).
- **Event-based waits and a controlled clock where they matter.** waitForResponse and waitForRequest appear in 10 places, with the reason stated (runs.spec.ts:311-318). page.clock.setFixedTime drives the time-of-day logic (home.spec.ts:29-40). Sources: [apps/web/tests/browser/runs.spec.ts:311-318](../../../../apps/web/tests/browser/runs.spec.ts#L311), [apps/web/tests/browser/home.spec.ts:29-40](../../../../apps/web/tests/browser/home.spec.ts#L29).
- **State isolation and cleanup in newer suites.** The composer, home, models, workflow-list and ops suites use dedicated arranged workspaces (composer.spec.ts:9-11, home.spec.ts:9-12, models.spec.ts:7-9, workflow-list.spec.ts:7-11). Arranged files and keys are removed in finally blocks (operations-history.spec.ts:30-48, readiness.spec.ts:80-98, settings.spec.ts:173-189). Sources: [apps/web/tests/browser/composer.spec.ts:9-11](../../../../apps/web/tests/browser/composer.spec.ts#L9), [apps/web/tests/browser/home.spec.ts:9-12](../../../../apps/web/tests/browser/home.spec.ts#L9), [apps/web/tests/browser/models.spec.ts:7-9](../../../../apps/web/tests/browser/models.spec.ts#L7), [apps/web/tests/browser/workflow-list.spec.ts:7-11](../../../../apps/web/tests/browser/workflow-list.spec.ts#L7), [apps/web/tests/browser/operations-history.spec.ts:30-48](../../../../apps/web/tests/browser/operations-history.spec.ts#L30), [apps/web/tests/browser/readiness.spec.ts:80-98](../../../../apps/web/tests/browser/readiness.spec.ts#L80), [apps/web/tests/browser/settings.spec.ts:173-189](../../../../apps/web/tests/browser/settings.spec.ts#L173).
- **Strict runner and compiler settings.** forbidOnly, zero retries and one worker keep flakiness visible, and the JSON report feeds the Python harness (playwright.config.ts:4-18). Specs compile under the app's strict tsconfig with noUncheckedIndexedAccess and exactOptionalPropertyTypes (apps/web/tsconfig.json). Sources: [apps/web/playwright.config.ts:4-18](../../../../apps/web/playwright.config.ts#L4), [apps/web/tsconfig.json:7-10](../../../../apps/web/tsconfig.json#L7).

## Findings

| ID | Severity | Dimension | Title | Effort | Risk |
|---|---|---|---|---|---|
| [TWEB-01](#tweb-01) | high | structure | Suites hand workspace state to each other through alphabetical file order and filename-based selection | L | medium |
| [TWEB-02](#tweb-02) | high | duplication | No shared test layer: 38 specs carry about 747 lines of copied sign-in, CSRF, key and axe helpers | M | low |
| [TWEB-03](#tweb-03) | high | size | slice-visual.spec.ts packs an untyped in-page script, an arranger, a surface table and a 10-minute loop test into 1,057 lines | M | medium |
| [TWEB-04](#tweb-04) | medium | types | API reads and writes are untyped and unchecked, although the generated client parses every response | M | low |
| [TWEB-05](#tweb-05) | medium | standards | Axe scans use four tag sets, and 21 of 35 fall short of the WCAG 2.1 A and AA that Decision 0010 says they apply | S | medium |
| [TWEB-06](#tweb-06) | medium | approach | Fixed sleeps and networkidle stand in for waits, adding about 50 seconds of sleep across the runs | M | medium |
| [TWEB-07](#tweb-07) | medium | tests | Tests depend on earlier tests in the same file without serial mode, and arranged-state files hold tests that cannot pass together | S | low |
| [TWEB-08](#tweb-08) | medium | tests | Leak checks read response bodies in async listeners and can pass before the bodies arrive | S | low |
| [TWEB-09](#tweb-09) | medium | tests | The visual walk's inventory says the app has no dialogs or charts and leaves seven page routes unmeasured | S | low |
| [TWEB-10](#tweb-10) | medium | duplication | Eleven leak deny-lists in nine files disagree on what counts as private | S | low |
| [TWEB-11](#tweb-11) | medium | errors | Seven hand-rolled Python helper calls run without a timeout and fail with unhelpful errors | S | low |
| [TWEB-12](#tweb-12) | medium | size | 34 functions exceed 60 lines, 30 of them test bodies that wrap several behaviors in arrangement code | M | low |
| [TWEB-13](#tweb-13) | medium | duplication | Run payloads, workflow graphs and the scripted worker's goal keywords are copied as literals | S | low |
| [TWEB-14](#tweb-14) | low | errors | 104 environment variables default to empty strings, so a missing prerequisite reads as a product failure | S | low |
| [TWEB-15](#tweb-15) | low | approach | Failures keep no trace or screenshot, only the report's error text and an ARIA snapshot | S | low |
| [TWEB-16](#tweb-16) | low | errors | 22 browser contexts are created inline and never closed | S | low |
| [TWEB-17](#tweb-17) | low | standards | Selector conventions are unwritten: data-field hooks, attribute lookups for role=status messages, and parent traversal | S | low |
| [TWEB-18](#tweb-18) | low | naming | The same concepts go by different names across specs | S | low |
| [TWEB-19](#tweb-19) | low | functions | Some local helpers take long positional lists or do several things at once | S | low |

### <a id="tweb-01"></a>TWEB-01: Suites hand workspace state to each other through alphabetical file order and filename-based selection

- **Severity** high · **Dimension** structure · **Effort** L · **Risk** medium · **Occurrences** 14
- **Where:**
  - [apps/web/playwright.config.ts:3-24](../../../../apps/web/playwright.config.ts#L3): No projects or tags. The comment names qualify_web.py, but four scripts choose specs by filename substrings.
  - [scripts/qualify_identity.py:317](../../../../scripts/qualify_identity.py#L317): Chooses the main suite by substrings, spelling out 'browser/workflows.spec' to avoid slice-workflows. The slice suite is every path containing 'slice' (376).
  - [apps/web/tests/browser/experts.spec.ts:267-275](../../../../apps/web/tests/browser/experts.spec.ts#L267): afterAll removes the key because 'the settings spec, which runs after this one, expects no key'.
  - [apps/web/tests/browser/run-workspace.spec.ts:302-303](../../../../apps/web/tests/browser/run-workspace.spec.ts#L302): Removes the key for settings.spec.ts, with the same comment.
  - [apps/web/tests/browser/run-workspace.spec.ts:443](../../../../apps/web/tests/browser/run-workspace.spec.ts#L443): The file's last test saves the key again through admitted() and never removes it.
  - [apps/web/tests/browser/runs.spec.ts:21](../../../../apps/web/tests/browser/runs.spec.ts#L21): Says the last test removes the key. The removal is actually the test at 224-229, and the last test (245) signs in to another workspace.
  - [apps/web/tests/browser/settings.spec.ts:67](../../../../apps/web/tests/browser/settings.spec.ts#L67): Expects no key, which holds only because runs.spec.ts happens to run between run-workspace.spec.ts and this file.
  - [apps/web/tests/browser/operations-values.spec.ts:69-72](../../../../apps/web/tests/browser/operations-values.spec.ts#L69): Stops the arranged heartbeats because operations.spec.ts:30 expects no worker. operations.spec.ts:57-61 also resets retention in a test body for later suites.
- **Evidence:** Playwright 1.64.1 sorts spec files with localeCompare, and the config runs one worker, so the main suite always runs experts, run-workspace, runs and then settings. Fourteen comments in 12 files (found with grep for 'later suite', 'runs after', 'expects no key', 'puts it with the slice' and similar) describe what another file must leave behind or which runner a filename routes to. Settings → Models alone is tested from five files (models, settings, saved-choice, qualification, slice-policy), each placed by the environment it needs rather than by screen.

  ```ts
  // experts.spec.ts:268  The settings spec, which runs after this one, expects no key.
  // runs.spec.ts:21  Admission needs a usable key. The last test here removes it, and the settings spec expects none.
  // slice-visual.spec.ts:13-14  Its name puts it with the slice suites, so the scripted worker can finish a run.
  ```

- **Why it matters:** Adding a test to the end of run-workspace.spec.ts, renaming a file, or adding a spec that saves a key between runs.spec.ts and settings.spec.ts changes what settings.spec.ts sees, and the failure shows up in the wrong file. The no-key chain already holds only by accident, and two of the comments that describe it are wrong. A new spec whose name contains 'settings', 'runs' or 'slice' silently joins another runner's selection, and a spec run on its own starts from whatever the previous file left behind.
- **Recommendation:** Make environments and preconditions explicit instead of relying on file order. Declare one Playwright project per environment (web, main, slice, release, install), each with its own testMatch, and have the scripts pass --project instead of substrings. Give each piece of shared state a fixture that arranges it and restores it in teardown, which runs even when a test fails: provider key, worker heartbeats, retention and model policy. Alternatively, move the remaining owner-A suites to dedicated arranged workspaces, as composer, home, models and workflow-list already do. Each spec that needs a state checks it through the API in beforeAll, so a broken chain fails at its source with a clear message.
- **Rule check:** AGENTS.md and nextjs.md keep the qualification scripts and the db profile as the runners on disposable targets. Only how a script selects specs changes; no arranged fixture, guard or check is removed. Teardown fixtures restore exactly the states the comments promise today.
- **Verification:** confirmed. The installed runner sorts files with localeCompare (playwright 1.64.1, lib/runner/index.js:2281). Four scripts select by substring (qualify_identity.py:317 and 376, qualify_web.py:169, qualify_release.py:342, persistent_install.py:720). The 14 order comments in 12 files include qualification.spec.ts:8. run-workspace.spec.ts:443 saves the key again, and runs.spec.ts:224-229 removes it.

```ts
// playwright.config.ts: one project per environment; scripts pass --project instead of substrings
projects: [
  { name: 'web', testMatch: /(appearance|boundary|tools)\.spec\.ts$/ },
  { name: 'main', testMatch: MAIN_SPECS },   // the list lives here, not in qualify_identity.py
  { name: 'slice', testMatch: /slice(-[a-z-]+)?\.spec\.ts$/ },
  { name: 'release', testMatch: /release-latency\.spec\.ts$/ },
  { name: 'install', testMatch: /install(-current)?\.spec\.ts$/ },  // read-only, persistent
],
// support/fixtures.ts: state a test needs is arranged and restored by a fixture
providerKey: async ({ asOwner }, use) => { await ensureProviderKey(asOwner); await use(); await disconnectProviderKey(asOwner); },
// settings.spec.ts: preconditions are asserted, not assumed
test.beforeAll(async ({ browser }) => expectNoProviderKey(browser, users.owner));
```

### <a id="tweb-02"></a>TWEB-02: No shared test layer: 38 specs carry about 747 lines of copied sign-in, CSRF, key and axe helpers

- **Severity** high · **Dimension** duplication · **Effort** M · **Risk** low · **Occurrences** 36
- **Where:**
  - [apps/web/tests/browser/approvals.spec.ts:23-51](../../../../apps/web/tests/browser/approvals.spec.ts#L23): The signIn and write helpers as they are copied: signIn is defined in 36 files, the CSRF header builder in 17.
  - [apps/web/tests/browser/slice-closure.spec.ts:32-45](../../../../apps/web/tests/browser/slice-closure.spec.ts#L32): ensureKey, with a different key string ('sk-or-valid-arranged-closure').
  - [apps/web/tests/browser/experts.spec.ts:23-36](../../../../apps/web/tests/browser/experts.spec.ts#L23): The same block, named saveKey.
  - [apps/web/tests/browser/runs.spec.ts:22-37](../../../../apps/web/tests/browser/runs.spec.ts#L22): The same block inside signInWithKey.
  - [apps/web/tests/browser/slice.spec.ts:7-26](../../../../apps/web/tests/browser/slice.spec.ts#L7): The same block inside signIn.
  - [apps/web/tests/browser/slice-policy.spec.ts:19-30](../../../../apps/web/tests/browser/slice-policy.spec.ts#L19): A write() variant whose idempotency key is optional.
  - [apps/web/tests/browser/composer.spec.ts:22-27](../../../../apps/web/tests/browser/composer.spec.ts#L22): One of eight local axe helpers (seven named noViolations, one named axe).
- **Evidence:** A script over the function definitions counts: 36 signIn (339 lines); 14 write, 2 csrf and 1 headers (157 lines); 10 provider-key blocks under six names (saveKey, ensureKey, signInWithKey, admitted, signIn, arrange); 8 axe helpers; and 4 copies of admit or finishedRun. That is about 747 lines in 38 of 41 files. No spec imports anything except @playwright/test, @axe-core/playwright and Node built-ins. There is no support module, no test.extend fixture and no test.use. The copied sign-in:

  ```ts
  async function signIn(page: Page, email: string, password: string): Promise<void> {
    await page.goto("/sign-in");
    await page.getByLabel("Email").fill(email);
    ...
    await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  }
  ```

- **Why it matters:** A change to the sign-in form or its confirmation text, the CSRF route or header, or the provider-key form means editing 36, 17 or 10 files, and the copies already differ in key strings, optional parameters and assertion style. The header helper has no default key, so 48 calls pick literal idempotency keys by hand. Specs that reuse a goal or a fixed string as the key (slice.spec.ts:45) therefore cannot be rerun against the same stack. Every test also pays for a full sign-in through the form.
- **Recommendation:** Create apps/web/tests/browser/support/ and migrate file by file. auth.ts holds signIn and a users map. api.ts holds writeHeaders(page, key = crypto.randomUUID()). keys.ts holds ensureProviderKey and disconnectProviderKey. a11y.ts holds one axe helper. fixtures.ts extends test with role pages whose contexts it closes. Consider a setup project that signs each disposable role in once and stores storageState under the ignored output directory, as tools.spec.ts:10-15 already does with a minted session cookie. Keep identity.spec.ts signing in through the form.
- **Rule check:** DH-06 asks for small cohesive modules and no duplicated rules. The support code lives under apps/web/tests, outside the app bundle. storageState files for disposable roles go to the ignored output directory. The install project keeps signing in through the form, so no real owner session is written to disk.
- **Verification:** confirmed. Recounted with a brace-matching script over the 41 specs: 36 signIn definitions (339 lines), 17 header builders (157 lines), 10 provider-key blocks, 8 axe helpers and 4 admit or finishedRun copies. The only imports are @playwright/test, @axe-core/playwright and node: built-ins, and 48 header calls pass a literal string key.

```ts
// support/fixtures.ts
export const test = base.extend<{ asOwner: Page; asOwnerB: Page; asMember: Page; asReader: Page }>({
  asOwner: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await signIn(page, users.owner);
    await use(page);
    await context.close();
  },
  // asOwnerB, asMember and asReader alike
});
// support/api.ts   writeHeaders(page, key?), expectRefusal(reply, status, code)
// support/keys.ts  ensureProviderKey(page), disconnectProviderKey(page)
// support/a11y.ts  expectNoA11yViolations(page)
```

### <a id="tweb-03"></a>TWEB-03: slice-visual.spec.ts packs an untyped in-page script, an arranger, a surface table and a 10-minute loop test into 1,057 lines

- **Severity** high · **Dimension** size · **Effort** M · **Risk** medium · **Occurrences** 1
- **Where:**
  - [apps/web/tests/browser/slice-visual.spec.ts:94-210](../../../../apps/web/tests/browser/slice-visual.spec.ts#L94): A 116-line JavaScript library in a template string, with no type check or lint, doubled regex escapes (176) and TypeScript constants interpolated into its source (163).
  - [apps/web/tests/browser/slice-visual.spec.ts:679-685](../../../../apps/web/tests/browser/slice-visual.spec.ts#L679): Results are read by evaluating strings and then cast (as Text[], as Boundary[], as string[]). The file has 16 type assertions.
  - [apps/web/tests/browser/slice-visual.spec.ts:245-329](../../../../apps/web/tests/browser/slice-visual.spec.ts#L245): arrange(): 85 lines that create a run, an Expert, a session, a workflow, a version and an execution. No HTTP status is checked, and the response of the publish at 312-315 is ignored.
  - [apps/web/tests/browser/slice-visual.spec.ts:335-496](../../../../apps/web/tests/browser/slice-visual.spec.ts#L335): surfaces(): a 162-line data table built inside a function.
  - [apps/web/tests/browser/slice-visual.spec.ts:761-858](../../../../apps/web/tests/browser/slice-visual.spec.ts#L761): One 95-line test with a 600-second timeout loops over 2 themes and 21 surfaces. A surface that never becomes ready ends the walk before results.json is written.
  - [apps/web/tests/browser/slice-visual.spec.ts:824-841](../../../../apps/web/tests/browser/slice-visual.spec.ts#L824): A failure predicate of complexity 16; the assertion at 857 reports only 'surface-theme' names.
  - [apps/web/tests/browser/slice-visual.spec.ts:647-659](../../../../apps/web/tests/browser/slice-visual.spec.ts#L647): sidewaysAtZoom duplicates the zoom test at 948-984, with the same widths at 649 and 952.
- **Evidence:** The largest web file: 1,057 lines, with 5 functions over 60 lines, one of complexity 16, and 16 type assertions by ESLint. The measurement code is a string injected with addScriptTag and read back by name. The result shapes are declared twice, once in the string and once as local types inside measure(), and nothing links the two.

  ```ts
  const text = (await page.evaluate("window.__contrast.text()")) as Text[];
  const boundaries = (await page.evaluate(
    "window.__contrast.boundaries()",
  )) as Boundary[];
  ```

- **Why it matters:** This file produces the evidence for DS-05 and US-11.11, and it is the hardest test file to change safely. A typo in the measurement string shows up only at runtime, in a 10-minute slice run. A failing run reports 'run-dark' without naming which check failed (contrast, focus, axe, zoom, motion or keyboard) until someone opens results.json. One surface that never settles discards the evidence for all 42 surface and theme pairs.
- **Recommendation:** Split the file by responsibility. Move the in-page code into typed, self-contained functions passed to page.evaluate, so the compiler checks it and each result type is declared once. Keep one zoom implementation. Move the surface table and the absent list into data, and use a shared arranger that checks each HTTP status. Name each surface and theme in the report and keep partial evidence: wrap each one in test.step with expect.soft checks, record a surface that never becomes ready as a named finding instead of ending the walk, and write results.json in a finally block. Avoid serial mode here, since it skips every later test after the first failure. Compute named findings instead of a boolean chain. Keep the self-test for the page broken on purpose (860-917) in this file.
- **Rule check:** Decision 0010 stays the pass line. The results.json schema (autobots.visual-evidence/v1), both themes and the known-bad self-test are kept. This is a structural change to test code, verified with the db profile and by comparing results.json before and after.
- **Verification:** revised. The 116-line string, the casts at 679-685, the unchecked publish at 312-315, the 21 surfaces and the duplicated zoom widths (649 and 952) are as cited. Revised the recommendation and sketch, which proposed test.describe.serial: serial mode skips everything after the first failure, which defeats keeping partial evidence. Named steps with soft assertions keep both goals in one walk.

```text
support/visual/contrast.ts  export function measureContrast(min: Minimums): ContrastReport   // self-contained, run via page.evaluate
support/visual/probes.ts    walkKeyboard, readDisabled, readMotion, sidewaysAtZoom (one zoom helper)
support/visual/surfaces.ts  SURFACES: { name, context, path: (ids) => string, arrange?, ready }[] and ABSENT
support/arrange.ts          createFinishedRun, createExpert, createSession, createWorkflowExecution (status-checked, parsed)
slice-visual.spec.ts        for each theme and surface: await test.step(`${surface.name} in ${theme}`, ...)
                            findingsOf(m): string[], e.g. 'text 3.1 < 4.5 at Cancel'; expect.soft(findings, label).toEqual([])
                            a surface that never settles is recorded as a finding; finally: write results.json
```

### <a id="tweb-04"></a>TWEB-04: API reads and writes are untyped and unchecked, although the generated client parses every response

- **Severity** medium · **Dimension** types · **Effort** M · **Risk** low · **Occurrences** 232
- **Where:**
  - [apps/web/tests/browser/approvals.spec.ts:118-129](../../../../apps/web/tests/browser/approvals.spec.ts#L118): find((item: { id: string }) => ...), then fields read on any.
  - [apps/web/tests/browser/experts.spec.ts:486-492](../../../../apps/web/tests/browser/experts.spec.ts#L486): A local Tool type re-declares the catalog, then catalog.tools as Tool[].
  - [apps/web/tests/browser/settings-keys-and-vars.spec.ts:45-63](../../../../apps/web/tests/browser/settings-keys-and-vars.spec.ts#L45): A local Item type, JSON.parse(text) as { items: Item[] }, and a non-null assertion.
  - [apps/web/tests/browser/workspace-choice.spec.ts:103-110](../../../../apps/web/tests/browser/workspace-choice.spec.ts#L103): Casts on the error body and on the CSRF token.
  - [apps/web/tests/browser/slice-visual.spec.ts:312-315](../../../../apps/web/tests/browser/slice-visual.spec.ts#L312): A version publish whose response is ignored. About 23 write chains read .json() without checking the status.
  - [packages/api-client/src/generated.ts:7390](../../../../packages/api-client/src/generated.ts#L7390): parseApprovalList. The specs use none of the 170 generated parse functions, such as parseToolCatalog (8892), parseKeysAndVars (7987) and parseErrorResponse (7698), although the components do.
- **Evidence:** 232 response.json() reads return any. On top of them sit 31 inline element shapes, 49 type assertions and 6 non-null assertions (ESLint), and 52 '.code).toBe(' checks on untyped error bodies.

  ```ts
  const listed = await (await page.request.get("/api/v1/approvals")).json();
  const shown = listed.approvals.find(
    (item: { id: string }) => item.id === APPROVE,
  );
  expect(shown.argument_hash).toBe(HASH);
  ```

- **Why it matters:** Strict TypeScript checks nothing at these points. A renamed or removed field fails at runtime in the db profile as 'undefined', far from its cause, and a failed arrangement shows up later as navigation to /runs/undefined. The screens parse what they read with the generated parsers, but the specs' own API reads and arrangement writes never check the contract, so a drifted reply is caught only where a screen happens to read the same field.
- **Recommendation:** Add support/api.ts with three helpers that each take one options object: getJson(page, { path, parse }); send(page, { method, path, data, parse, status }), which asserts the status before parsing; and expectRefusal(reply, { status, code }), built on parseErrorResponse. Replace the inline shapes, the locally re-declared types and the casts with the generated parse functions. Keep one small local parser for the BFF-only /api/csrf reply.
- **Rule check:** DH-06 and nextjs.md ask for generated API types with runtime parsing at untrusted boundaries and no blanket assertions. The specs consume the generated client and never edit packages/api-client/src/generated.ts; DTO types stay DTOs and are not merged with view models.
- **Verification:** revised. Recounted 232 .json() reads, 31 inline element shapes, 52 '.code).toBe(' checks and 23 write chains read without a status check; ESLint reports 49 assertions and 6 non-null assertions. Revised the impact, since the screens themselves parse with the generated client, and gave the helpers an options object so they don't repeat TWEB-19's long positional lists.

```ts
export async function getJson<T>(page: Page, { path, parse }: { path: string; parse: (value: unknown) => T }): Promise<T> {
  const reply = await page.request.get(path);
  expect(reply.status(), path).toBe(200);
  return parse(await reply.json());
}
const { approvals } = await getJson(page, { path: '/api/v1/approvals', parse: parseApprovalList });
```

### <a id="tweb-05"></a>TWEB-05: Axe scans use four tag sets, and 21 of 35 fall short of the WCAG 2.1 A and AA that Decision 0010 says they apply

- **Severity** medium · **Dimension** standards · **Effort** S · **Risk** medium · **Occurrences** 35
- **Where:**
  - [apps/web/tests/browser/composer.spec.ts:22-27](../../../../apps/web/tests/browser/composer.spec.ts#L22): wcag2a and wcag2aa only, asserting whole violation objects. 14 scans use this set.
  - [apps/web/tests/browser/new-run.spec.ts:54-57](../../../../apps/web/tests/browser/new-run.spec.ts#L54): wcag21aa and wcag22aa without wcag21a. 7 scans use this set.
  - [apps/web/tests/browser/readiness.spec.ts:23-28](../../../../apps/web/tests/browser/readiness.spec.ts#L23): The WCAG 2.1 A and AA set, asserting ids only. 13 scans use this set.
  - [apps/web/tests/browser/appearance.spec.ts:478-484](../../../../apps/web/tests/browser/appearance.spec.ts#L478): The 2.1 set plus wcag22aa, reported as id and node count (1 scan).
  - [apps/web/tests/browser/slice-inspector.spec.ts:112-115](../../../../apps/web/tests/browser/slice-inspector.spec.ts#L112): WCAG 2.0 only, on the run list.
  - [docs/engineering/decisions/0010-contrast-pass-line.md:7](../../../../docs/engineering/decisions/0010-contrast-pass-line.md#L7): Says WCAG 2.1 AA 'is what the browser suites' axe checks already apply'.
- **Evidence:** 35 new AxeBuilder calls in 26 files, counted with grep on withTags: 14 use [wcag2a, wcag2aa]; 7 use [wcag2a, wcag2aa, wcag21aa, wcag22aa]; 13 use [wcag2a, wcag2aa, wcag21a, wcag21aa]; 1 uses that last set plus wcag22aa. In the pinned axe-core 4.14.0, wcag21a selects label-content-name-mismatch, and wcag21aa selects autocomplete-valid and avoid-inline-spacing. Failures are reported three ways: whole objects, ids only, or 'id: node count'.
- **Why it matters:** The accessibility check differs from screen to screen. On 21 scans it is weaker than the decision states, including Home, Experts, Approvals, workflows and the run list, so a WCAG 2.1 regression there can pass. Whole-object diffs are hard to read, and ids alone don't say which element failed.
- **Recommendation:** Put one helper and one constant in support/a11y.ts: WCAG_PASS_LINE = [wcag2a, wcag2aa, wcag21a, wcag21aa], with failures reported as id, impact and the first target selectors. Replace the 35 calls. The 8 scans that also select wcag22aa keep it through an extra-tags option, so no scan loses a rule it runs today. Forbid importing @axe-core/playwright outside the support folder with no-restricted-imports scoped to tests/browser. Adding wcag22aa to every scan would extend Decision 0010, so that needs the owner's decision.
- **Rule check:** Decision 0010 (WCAG 2.1 AA) and DS-04/DS-05. The helper raises 21 scans to the decided line, keeps wcag22aa on the 8 scans that select it and leaves WCAG 2.2 everywhere to the owner, so no check is weakened. The lint rule goes in apps/web's ESLint config, which runs separately from builds as nextjs.md requires.
- **Verification:** revised. Recounted the 35 calls by tag set with a script (14, 7, 13 and 1), and confirmed the rule tags in the installed axe-core 4.14.0. Revised the recommendation: replacing all 35 with the 2.1 set alone would drop the WCAG 2.2 rules, such as target-size, from 8 scans that the US-15.17 to US-15.22 verification records cite as passing WCAG 2.2 AA.

```ts
export const WCAG_PASS_LINE = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] as const;  // Decision 0010
export async function expectNoA11yViolations(page: Page, { label = page.url(), extraTags = [] }: { label?: string; extraTags?: string[] } = {}): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).withTags([...WCAG_PASS_LINE, ...extraTags]).analyze();
  expect(violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(', ')}`), label).toEqual([]);
}
```

### <a id="tweb-06"></a>TWEB-06: Fixed sleeps and networkidle stand in for waits, adding about 50 seconds of sleep across the runs

- **Severity** medium · **Dimension** approach · **Effort** M · **Risk** medium · **Occurrences** 30
- **Where:**
  - [apps/web/tests/browser/settings-sections.spec.ts:228](../../../../apps/web/tests/browser/settings-sections.spec.ts#L228): Sleeps 5 seconds after each of three sign-ins to let one 4-second notifier poll pass, plus 5 seconds at 265 and 10 seconds at 283 (run twice): 40 seconds in this file.
  - [apps/web/tests/browser/approvals.spec.ts:417](../../../../apps/web/tests/browser/approvals.spec.ts#L417): Sleeps 2.5 seconds for the 2-second shortcut window to lapse.
  - [apps/web/tests/browser/slice-controls.spec.ts:175](../../../../apps/web/tests/browser/slice-controls.spec.ts#L175): Sleeps 3 seconds before re-reading the state.
  - [apps/web/tests/browser/settings.spec.ts:116](../../../../apps/web/tests/browser/settings.spec.ts#L116): Sleeps 200 milliseconds so async body reads land before a leak check.
  - [apps/web/tests/browser/appearance.spec.ts:36-40](../../../../apps/web/tests/browser/appearance.spec.ts#L36): visit() waits for networkidle; there are 16 such waits in 5 files.
  - [apps/web/tests/browser/home.spec.ts:35](../../../../apps/web/tests/browser/home.spec.ts#L35): page.clock.setFixedTime: the clock API is already in use, once.
  - [apps/web/components/waiting-notifier.tsx:71](../../../../apps/web/components/waiting-notifier.tsx#L71): The 4-second poll is a setTimeout (EVERY_MS at 13), which page.clock controls.
  - [apps/web/components/approvals-panel.tsx:279](../../../../apps/web/components/approvals-panel.tsx#L279): The shortcut window is Date.now() + 2_000, which page.clock also controls.
- **Evidence:** grep finds 14 waitForTimeout calls in 9 files and 16 waitForLoadState('networkidle') calls in 5 files.

  ```ts
  await page.goto("/");
  // One poll notes what already waits, so only what newly waits is told.
  await page.waitForTimeout(5_000);
  ```

- **Why it matters:** The sleeps cost about 50 seconds. A fixed sleep is too short on a loaded machine and wasted on an idle one. A negative check after a short sleep, such as 'no request within 300 ms', can pass only because the window was too short. Playwright discourages networkidle, and it never settles on pages with live streams, which is why slice-visual needs its own diagnostics around it.
- **Recommendation:** Install the clock where time drives behavior: page.clock.install, then runFor(4_000) for a notifier poll or fastForward(2_500) for the shortcut window. Wait on responses, requests or web-first assertions instead of networkidle. Keep a sleep only for a documented negative observation, through one named helper. Enforce this in apps/web/eslint.config.mjs for tests/browser.
- **Rule check:** nextjs.md: lint runs separately from Next.js builds, so the rule goes in apps/web's own ESLint config. DH-06 asks tests to use controlled clocks rather than real time. The notification, shortcut and stream behavior under test does not change.
- **Verification:** confirmed. Recounted 14 waitForTimeout calls in 9 files and 16 networkidle waits in 5. The settings-sections sleeps sum to 40 s because watching() runs three times and the 10-second wait twice. waiting-notifier.tsx:71 and approvals-panel.tsx:279 use setTimeout and Date.now(), which page.clock controls. DH-06 states the controlled-clock rule in its Python section; it applies here by analogy.

```js
{ files: ['tests/browser/**/*.ts'], rules: {
  'no-restricted-properties': ['error', { property: 'waitForTimeout', message: 'Wait on a response, an assertion or page.clock.' }],
  'no-restricted-syntax': ['error', { selector: "Literal[value='networkidle']", message: 'Wait on a locator or a response.' }],
} }
```

### <a id="tweb-07"></a>TWEB-07: Tests depend on earlier tests in the same file without serial mode, and arranged-state files hold tests that cannot pass together

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [apps/web/tests/browser/approvals.spec.ts:206-219](../../../../apps/web/tests/browser/approvals.spec.ts#L206): Approves APPROVE. The test at 179-204 must run before this one, and the test at 352-373 after it.
  - [apps/web/tests/browser/settings.spec.ts:136-147](../../../../apps/web/tests/browser/settings.spec.ts#L136): Expects credential_version 1, saved by the test at 91; the test at 165-181 then expects version 2.
  - [apps/web/tests/browser/qualification.spec.ts:22](../../../../apps/web/tests/browser/qualification.spec.ts#L22): This test and the one at 47 need opposite database states. The runner arranges each state and selects the test by title with -g (scripts/qualify_identity.py:329).
  - [apps/web/tests/browser/saved-choice.spec.ts:28](../../../../apps/web/tests/browser/saved-choice.spec.ts#L28): A 155-line test, because one title equals one arranged state (qualify_identity.py:346).
  - [apps/web/tests/browser/readiness.spec.ts:4-5](../../../../apps/web/tests/browser/readiness.spec.ts#L4): Each test runs alone, after a different arrangement (qualify_identity.py:360).
  - [apps/web/tests/browser/composer.spec.ts:41](../../../../apps/web/tests/browser/composer.spec.ts#L41): Declares serial mode, as only 6 of 41 files do.
- **Evidence:** approvals.spec.ts and settings.spec.ts carry state from test to test without test.describe.configure({ mode: 'serial' }). qualification, saved-choice and readiness are valid only one test at a time, and only a header comment says so. No spec groups tests in a test.describe block or uses tags; six files only call test.describe.configure.

  ```ts
  // approvals.spec.ts:211-215
  await (await open(page, APPROVE)).getByRole("button", { name: "Approve" }).click();
  // approvals.spec.ts:369-371, a later test
  await expect(card.locator("[data-approval-decided]")).toContainText("Approved by you at");
  ```

- **Why it matters:** When settings.spec.ts:91 fails, the tests at 136, 165 and 213 also fail with misleading messages instead of being skipped as dependents. Running one test with --grep, or reordering tests, breaks others. Running qualification.spec.ts or saved-choice.spec.ts as a whole file always fails. Renaming a title breaks the runner's -g selection, and run_problems then reports 'no tests ran' for that run, far from the rename.
- **Recommendation:** Declare serial mode in approvals.spec.ts and settings.spec.ts, or make each test arrange its own approval and key. Wrap each arranged state in a test.describe named after the state and tagged, for example with { tag: '@arranged' }, and have the runner select by tag or describe title. Give each describe a beforeAll that reads the state through the API and fails with a clear message when it is not arranged. Then split saved-choice's long test into focused tests inside its state's describe.
- **Rule check:** ohmyorch-delivery.md and AGENTS.md: a skipped check never counts, so a missing arrangement fails instead of skipping. scripts/qualify_identity.py keeps arranging the states.
- **Verification:** revised. Verified the order dependence (approvals 179, 206 and 352; settings 91, 136, 165 and 213) and the one-state files run by -g at qualify_identity.py:329, 346 and 360. Revised the rename impact: qualify_web.run_problems fails a run with no tests, so the break is reported, not silent.

### <a id="tweb-08"></a>TWEB-08: Leak checks read response bodies in async listeners and can pass before the bodies arrive

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 3
- **Where:**
  - [apps/web/tests/browser/settings.spec.ts:97-117](../../../../apps/web/tests/browser/settings.spec.ts#L97): Bodies are pushed from an async listener; after a 200-millisecond sleep, the test checks that the saved key never appears.
  - [apps/web/tests/browser/identity.spec.ts:27-31](../../../../apps/web/tests/browser/identity.spec.ts#L27): Same listener, checked at 54-57 with no wait. Only non-fetch responses are kept, which excludes API replies and client-side RSC payloads.
  - [apps/web/tests/browser/boundary.spec.ts:144-157](../../../../apps/web/tests/browser/boundary.spec.ts#L144): Same pattern after networkidle; the only guard is a count of at least two bodies.
- **Evidence:** Each listener pushes a body only after an awaited read that turns a failure into an empty string:

  ```ts
  page.on("response", async (response) =>
    bodies.push(await response.text().catch(() => "")),
  );
  await page.waitForTimeout(200);
  for (const body of bodies) expect(body).not.toContain(VALID);
  ```

- **Why it matters:** A body still being read when the loop runs is never inspected, and a failed read becomes an empty string that passes. So the checks that the provider key, the service key and the owner password never reach the browser can pass without seeing some responses. The credential save reply itself is skipped if its read is still pending.
- **Recommendation:** Keep the read promises and await them before asserting. Collect response.text() promises in the listener, await Promise.all, and treat an unreadable body as a failure, except for redirects. Assert that the specific response under test, such as the credential PUT, was inspected. Put this in support/leaks.ts next to the shared deny-list.
- **Rule check:** nextjs.md: server keys and private reasoning never reach props, caches, bundles or public events. This makes the existing checks complete and adds no new requirement.
- **Verification:** confirmed. Verified in all three files. identity.spec.ts keeps only non-fetch responses and checks with no wait, and boundary.spec.ts relies on networkidle and a count of at least two bodies.

```ts
export function captureBodies(page: Page, keep: (r: Response) => boolean): () => Promise<{ url: string; body: string }[]> {
  const reads: Promise<{ url: string; body: string }>[] = [];
  page.on('response', (r) => { if (keep(r)) reads.push(r.text().then((body) => ({ url: r.url(), body }))); });
  return () => Promise.all(reads);   // rejects on an unreadable body
}
```

### <a id="tweb-09"></a>TWEB-09: The visual walk's inventory says the app has no dialogs or charts and leaves seven page routes unmeasured

- **Severity** medium · **Dimension** tests · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/tests/browser/slice-visual.spec.ts:31-36](../../../../apps/web/tests/browser/slice-visual.spec.ts#L31): 'dialogs and portals: The app has none' and 'charts: The app has none'; both are written into results.json at 850.
  - [apps/web/tests/browser/search.spec.ts:61](../../../../apps/web/tests/browser/search.spec.ts#L61): The Search palette is a dialog (US-15.22).
  - [apps/web/tests/browser/tools.spec.ts:181-185](../../../../apps/web/tests/browser/tools.spec.ts#L181): The tool modal is a <dialog> element (US-14.20).
  - [apps/web/tests/browser/appearance.spec.ts:317](../../../../apps/web/tests/browser/appearance.spec.ts#L317): The About local services dialog.
  - [apps/web/tests/browser/operations-jobs.spec.ts:82-106](../../../../apps/web/tests/browser/operations-jobs.spec.ts#L82): The Operations jobs chart (US-15.19), with a legend and patterns.
  - [apps/web/tests/browser/slice-visual.spec.ts:343-495](../../../../apps/web/tests/browser/slice-visual.spec.ts#L343): 21 surfaces covering 15 of the 22 page routes. Missing: /tools, /tools/[toolId] and five Settings sections (account, data, keyboard, keys-and-vars, notifications).
  - [apps/web/tests/browser/slice-visual.spec.ts:957-966](../../../../apps/web/tests/browser/slice-visual.spec.ts#L957): The zoom test's eight paths omit the same screens.
- **Evidence:** The search palette (4871520) and the jobs chart (6dbe64a) were delivered on 2026-11-08, before this file's last change (747bc88) that same day, so the list was not revisited.

  ```ts
  "dialogs and portals":
    "The app has none. Choices are inline, and selects are native.",
  ...
  charts: "The app has none, so no chart token is in use.",
  ```

- **Why it matters:** The DS-05 evidence file states that dialogs, portals and charts don't exist, so no reader looks for their contrast, focus and keyboard evidence in either theme. The seven routes the walk skips get none of its measurements (non-text and focus contrast, keyboard reachability, zoom or motion); most have only an axe scan in their own spec. The chart also colors its series with status tokens rather than chart-1 to chart-5 (DS-03), which a walk of the chart would have surfaced; that issue belongs to the web-system area.
- **Recommendation:** Add surfaces for the Search dialog (opened by its shortcut), the tool modal (/tools?tool=calculate), the About dialog and the seven missing routes, and delete the stale absent entries. Add a check that every app/**/page.tsx route is either a surface or listed as absent with a reason, so a new screen can't be skipped silently.
- **Rule check:** DS-03 and DS-05 ask for dialogs, portals and charts in both themes. Decision 0010 stays the pass line, and AGENTS.md requires evidence to state its limitations truthfully.
- **Verification:** revised. Verified the stale ABSENT entries (written into results.json at 850), 21 surfaces covering 15 of the 22 page.tsx routes, and the commit order. Revised the impact: tools.spec.ts, settings-sections.spec.ts and settings-keys-and-vars.spec.ts run axe on most skipped routes, so they are not wholly unmeasured. Moved to the tests dimension, since the gap is coverage.

```ts
const routes = readdirSync('app', { recursive: true }).map(String).filter((f) => f.endsWith('page.tsx')).map(toRoutePattern);
expect(routes.filter((r) => !SURFACE_ROUTES.has(r) && !(r in ABSENT_ROUTES))).toEqual([]);
```

### <a id="tweb-10"></a>TWEB-10: Eleven leak deny-lists in nine files disagree on what counts as private

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 11
- **Where:**
  - [apps/web/tests/browser/operations.spec.ts:34](../../../../apps/web/tests/browser/operations.spec.ts#L34): 127.0.0.1, postgres, sk-or- and eyj, checked against lowercased text.
  - [apps/web/tests/browser/operations-history.spec.ts:9](../../../../apps/web/tests/browser/operations-history.spec.ts#L9): Adds /users/ and a UUID pattern.
  - [apps/web/tests/browser/operations-values.spec.ts:143-155](../../../../apps/web/tests/browser/operations-values.spec.ts#L143): Two different lists in one test, with '/', localhost, postgres:// and /private/.
  - [apps/web/tests/browser/install-current.spec.ts:48](../../../../apps/web/tests/browser/install-current.spec.ts#L48): Three markers and no database marker; repeated at 116 in a different order.
  - [apps/web/tests/browser/install.spec.ts:62](../../../../apps/web/tests/browser/install.spec.ts#L62): Four markers.
  - [apps/web/tests/browser/slice-inspector.spec.ts:154-162](../../../../apps/web/tests/browser/slice-inspector.spec.ts#L154): Private-reasoning and checkpoint markers.
  - [apps/web/tests/browser/slice-run-details.spec.ts:243](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L243): Three markers.
  - [apps/web/tests/browser/run-workspace.spec.ts:215-221](../../../../apps/web/tests/browser/run-workspace.spec.ts#L215): Checkpoint, object path and policy snapshot markers.
- **Evidence:** grep on 'for (const leak of', NOT_ALLOWED and 'for (const secret of' finds 11 lists in 9 files. They have 9 different compositions and two case conventions: eyJ matched against raw text, eyj against lowercased text.

  ```ts
  // install-current.spec.ts:48
  for (const leak of ["127.0.0.1", "sk-or-", "eyJ"]) {
  // operations.spec.ts:34
  for (const leak of ["127.0.0.1", "postgres", "sk-or-", "eyj"]) {
  ```

- **Why it matters:** The no-leak rule is applied unevenly. Install screens are not checked for database URLs or local paths, and Operations screens are not checked for private reasoning. Adding a new secret prefix or marker needs edits in nine files.
- **Recommendation:** Create support/leaks.ts with one canonical PRIVATE_MARKERS list grouped by kind: provider keys, JWTs, loopback and database URLs, local paths, and private-reasoning and checkpoint fields. Expose expectNoPrivateValues(text, { extra, allow }) and call it from the 11 places, keeping per-test extras such as 'Total: 5' and explicit allowances where a screen legitimately shows a marker.
- **Rule check:** nextjs.md and AGENTS.md boundaries on secrets, addresses and private reasoning. The shared list adds markers where fewer were checked and removes none.
- **Verification:** confirmed. Recounted 11 lists in 9 files with the stated grep. The case conventions and the install screens' missing database marker are as cited.

### <a id="tweb-11"></a>TWEB-11: Seven hand-rolled Python helper calls run without a timeout and fail with unhelpful errors

- **Severity** medium · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 7
- **Where:**
  - [apps/web/tests/browser/stream-result.spec.ts:20-56](../../../../apps/web/tests/browser/stream-result.spec.ts#L20): spawn whose promises never reject: no exit or error handler, no kill, and JSON.parse can throw inside the line listener.
  - [apps/web/tests/browser/run-workspace.spec.ts:417-437](../../../../apps/web/tests/browser/run-workspace.spec.ts#L417): Finds run_files_probe.py by string-replacing tool_use_live.py in another variable.
  - [apps/web/tests/browser/settings-sections.spec.ts:183-204](../../../../apps/web/tests/browser/settings-sections.spec.ts#L183): Finds notify_live.py by replacing operations_live.py the same way.
  - [apps/web/tests/browser/operations-values.spec.ts:36-50](../../../../apps/web/tests/browser/operations-values.spec.ts#L36): Same environment assembly. The '{}' fallback after split('\n').at(-1) never applies, so an empty last line throws a bare JSON error.
  - [apps/web/tests/browser/operations-jobs.spec.ts:23-36](../../../../apps/web/tests/browser/operations-jobs.spec.ts#L23): Same assembly, with the output ignored.
  - [apps/web/tests/browser/run-panel.spec.ts:39-58](../../../../apps/web/tests/browser/run-panel.spec.ts#L39): Same assembly, with three arguments taken from separate variables.
  - [apps/web/tests/browser/run-workspace.spec.ts:349-368](../../../../apps/web/tests/browser/run-workspace.spec.ts#L349): Same assembly, inline in a test.
- **Evidence:** Six files call tests/db helpers with execFileSync or spawn, seven calls in all. Each rebuilds AUTOBOTS_DATABASE_URL and PYTHONPATH from the test variables, sets no timeout and parses the last line of stdout. split("\n").at(-1) always returns a string, so the ?? fallbacks never apply.

  ```ts
  const script = (process.env.AUTOBOTS_TEST_TOOL_HELPER ?? "").replace(
    "tool_use_live.py",
    "run_files_probe.py",
  );
  ...
  return JSON.parse(printed.trim().split("\n").at(-1) ?? "[]");
  ```

- **Why it matters:** The six execFileSync calls block the worker's event loop, so if a helper hangs, Playwright's own test timeout can't fire, and the run ends only at the runner's subprocess timeout (660 seconds for the main suite) with no report. If the streaming helper exits early, await runId waits out the 90-second test timeout, and the child can outlive the test. An empty or non-JSON last line throws a SyntaxError that names neither the helper nor its output; only a non-zero exit carries stderr, in execFileSync's error. An unset interpreter variable produces a spawn error about an empty command instead of naming the variable. Renaming a helper file breaks the string replacement without warning.
- **Recommendation:** Create one support/db-helpers.ts. helperPath(name) resolves tests/db from the repository, the way appearance.spec.ts:7-10 resolves luma.css. runDbHelper(name, args, parse) checks prerequisites, applies a timeout, puts stderr in thrown errors and guards the JSON parse. A streamDbHelper fixture rejects on exit or error and kills the child in teardown.
- **Rule check:** AGENTS.md: helpers act only on the disposable target the runner provides. The helpers' own behavior is unchanged, and the db profile remains the check.
- **Verification:** revised. The reviewer said an empty or non-JSON last line becomes {} or []. In fact ''.split('\n').at(-1) is '', so JSON.parse throws, and execFileSync already throws with stderr on a non-zero exit. The larger risk is the missing timeout, since a blocking execFileSync stops the in-worker test timeout. Seven call sites in six files confirmed.

```ts
export function runDbHelper<T>(name: string, args: string[], parse: (value: unknown) => T): T   // throws with stderr and the helper name
streamHelper: async ({}, use) => { const children = new Set<ChildProcess>(); await use((name, args) => start(name, args, children)); for (const child of children) child.kill(); }
```

### <a id="tweb-12"></a>TWEB-12: 34 functions exceed 60 lines, 30 of them test bodies that wrap several behaviors in arrangement code

- **Severity** medium · **Dimension** size · **Effort** M · **Risk** low · **Occurrences** 34
- **Where:**
  - [apps/web/tests/browser/saved-choice.spec.ts:28-192](../../../../apps/web/tests/browser/saved-choice.spec.ts#L28): 155 lines covering settings, admission, intent, the Home disclosure, two workflow versions and the settings fix.
  - [apps/web/tests/browser/workflows.spec.ts:217-369](../../../../apps/web/tests/browser/workflows.spec.ts#L217): 141 lines. The same file has tests of 84 and 73 lines at 49 and 136.
  - [apps/web/tests/browser/slice-workflows.spec.ts:57-204](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L57): 137 lines.
  - [apps/web/tests/browser/settings-keys-and-vars.spec.ts:86-225](../../../../apps/web/tests/browser/settings-keys-and-vars.spec.ts#L86): 126 lines, with its cleanup at the end of the body (212-219).
  - [apps/web/tests/browser/settings.spec.ts:298-401](../../../../apps/web/tests/browser/settings.spec.ts#L298): 103 lines of API-only policy refusals.
  - [apps/web/tests/browser/slice-controls.spec.ts:149-263](../../../../apps/web/tests/browser/slice-controls.spec.ts#L149): 102 lines.
- **Evidence:** ESLint (step 5 of the metrics run) reports 34 max-lines-per-function hits in this area: 30 test bodies and 4 helpers in slice-visual.spec.ts (arrange, surfaces, walkKeyboard and measure). It also reports 39 max-statements hits and 9 files over 300 lines. No spec names phases with test.step or groups tests in a test.describe block. A typical passage is arrangement:

  ```ts
  const flow = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, `saved-flow-${stamp}`),
      data: { name: `Saved ${stamp}` },
    })
  ).json();
  ```

- **Why it matters:** A failure report names the whole scenario and a line number, so the reader has to work out which of several behaviors broke. JSON literals, header building and response unwrapping make up most of each test and hide the assertions that map to the story.
- **Recommendation:** Once the support helpers exist, wrap each phase in a test.step with a story-language name. That keeps one arranged state per test while naming which phase failed. Move cleanup into fixtures or finally blocks, and turn sequences of API refusals into table-driven loops or separate tests, as settings-keys-and-vars.spec.ts:140-150 already does.
- **Rule check:** The 60-line threshold is this review's measurement, not yet a project rule. DH-09 asks tests to prove behavior, which named steps make visible without changing what is asserted.
- **Verification:** revised. Corrected the count: 4 of eslint.json's 34 max-lines-per-function hits in tests/browser are helpers, not tests. The six cited tests and their lengths (155, 141, 137, 126, 103 and 102 lines) match.

```ts
test('a saved default naming DeepSeek ...', async ({ asOwner: page }) => {
  await test.step('Settings says it is not offered', () => expectNotOffered(page));
  await test.step('admission and intent refuse and rewrite nothing', () => expectAdmissionRefused(page));
  await test.step('Home says Run would start nothing', () => expectHomeDisclosure(page));
  await test.step('a workflow version that calls a model says so', () => expectWorkflowDisclosure(page));
  await test.step('choosing an offered model clears it', () => chooseOffered(page, TERRA));
});
```

### <a id="tweb-13"></a>TWEB-13: Run payloads, workflow graphs and the scripted worker's goal keywords are copied as literals

- **Severity** medium · **Dimension** duplication · **Effort** S · **Risk** low · **Occurrences** 11
- **Where:**
  - [apps/web/tests/browser/slice-controls.spec.ts:47-63](../../../../apps/web/tests/browser/slice-controls.spec.ts#L47): The two-counts run payload. Also in slice-inspector.spec.ts:51-74, slice.spec.ts:43-61, slice-visual.spec.ts:260-273 and slice-run-details.spec.ts:193-205.
  - [apps/web/tests/browser/slice-run-details.spec.ts:107-120](../../../../apps/web/tests/browser/slice-run-details.spec.ts#L107): The in-to-out graph. Also in slice-visual.spec.ts:298-311 and saved-choice.spec.ts:105-130, with a three-node variant in workflows.spec.ts:32-47.
  - [apps/web/tests/browser/slice-workflows.spec.ts:21-37](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L21): node() and link() builders: the shape worth sharing.
  - [tests/web/fixture_worker.py:74-147](../../../../tests/web/fixture_worker.py#L74): The scripted worker branches on 'slice-*' substrings in the goal text.
  - [apps/web/tests/browser/slice-controls.spec.ts:156](../../../../apps/web/tests/browser/slice-controls.spec.ts#L156): 'slice-uncertain' as a bare string. 19 goal literals in 6 specs carry such keywords.
  - [apps/web/tests/browser/slice-closure.spec.ts:123](../../../../apps/web/tests/browser/slice-closure.spec.ts#L123): 'slice-delegate expert=<id>', a format the worker matches with a regex.
  - [apps/web/tests/browser/slice-policy.spec.ts:87-94](../../../../apps/web/tests/browser/slice-policy.spec.ts#L87): Cancels unless the run is terminal; slice-run-details.spec.ts:177-183 repeats this with the same status list.
- **Evidence:** There are 5 copies of the two-counts payload, 4 hand-written graphs (3 in-to-out and a three-node variant) and 2 copies of the terminal-status list. The worker protocol appears as 19 goal literals in 6 specs that carry a keyword tests/web/fixture_worker.py matches, with no named definition.

  ```ts
  goal_text: `${goal}: report the total of the two counts`,
  limit_micro_usd: 1000000,
  acceptance_criteria: ["The report states the correct total"],
  required_artifacts: [{ name: "report.md", must_contain: ["Total: 5"] }],
  ```

- **Why it matters:** Changing the run request contract or the workflow IR means finding every literal. A typo in a scenario keyword produces a plain run that fails much later, for a reason that looks unrelated. Nothing in the specs points to fixture_worker.py as the place that defines 'slice-uncertain' or 'slice-only-claims'.
- **Recommendation:** Create support/fixtures-data.ts containing twoCountsRun(scenario, { total? }), the graph builders (node, link, inToOut) taken from slice-workflows.spec.ts, TERMINAL_STATES, and a WorkerScenario constant object whose comment names tests/web/fixture_worker.py. Better still, keep one JSON list of scenario keywords that both the worker and the specs read.
- **Rule check:** DH-06 and the Option B contract: terminal states come from the canonical state set, never a second enum, so TERMINAL_STATES is typed against the generated run status rather than redefined. Making fixture_worker.py read a shared list touches tests/web, outside this area.
- **Verification:** revised. Recounted with a script: 23 string literals in 6 specs contain a 'slice-' keyword, and 19 of them are goals the worker matches (3 are the 'slice-private' leak marker and 1 is an idempotency key). The fourth graph is a three-node variant. The 5 payload copies and the 2 terminal lists are as cited.

### <a id="tweb-14"></a>TWEB-14: 104 environment variables default to empty strings, so a missing prerequisite reads as a product failure

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 256
- **Where:**
  - [apps/web/tests/browser/approvals.spec.ts:4-19](../../../../apps/web/tests/browser/approvals.spec.ts#L4): 16 variables, each defaulting to an empty string.
  - [apps/web/tests/browser/identity.spec.ts:59](../../../../apps/web/tests/browser/identity.spec.ts#L59): No fallback, so the screenshot goes to undefined/signed-in.png when the variable is unset. Same at 79 and at settings.spec.ts:72, 127 and 257.
  - [apps/web/tests/browser/saved-choice.spec.ts:239-240](../../../../apps/web/tests/browser/saved-choice.spec.ts#L239): Values that may be undefined are sent as request data.
  - [apps/web/tests/browser/boundary.spec.ts:18-30](../../../../apps/web/tests/browser/boundary.spec.ts#L18): Presence is checked in a separate test, which the other tests don't wait for.
  - [apps/web/tests/browser/operations-jobs.spec.ts:55-58](../../../../apps/web/tests/browser/operations-jobs.spec.ts#L55): Presence is checked in beforeAll.
  - [apps/web/tests/browser/run-panel.spec.ts:63](../../../../apps/web/tests/browser/run-panel.spec.ts#L63): Presence is checked inside each test.
- **Evidence:** 256 process.env reads of 104 distinct variables: 244 default to an empty string and 7 have no fallback at all. Presence is checked in 12 places across 10 files, in three styles.

  ```ts
  const APPROVE = process.env.AUTOBOTS_TEST_APPROVAL_APPROVE ?? "";
  ...
  path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/signed-in.png`,
  ```

- **Why it matters:** A missing variable surfaces as a locator timeout on [data-approval-item=""] or as a 404, not as 'AUTOBOTS_TEST_APPROVAL_APPROVE is not set'. Running a spec by hand writes screenshots into a directory literally named undefined. AGENTS.md separates an unavailable prerequisite (exit 2) from a failed check (exit 1), and these cases read as failed checks.
- **Recommendation:** Create support/env.ts with need(name), which throws '<name> is not set; run this spec through its runner' on first use, and optional(name, fallback) for output directories. Build the users map from need(), and remove the scattered presence tests.
- **Rule check:** The AGENTS.md exit-code convention distinguishes a missing prerequisite from a failed check. The runner scripts still supply every value.
- **Verification:** confirmed. Recounted with a script over the specs: 256 reads of 104 variables, 244 empty-string defaults and 7 with no fallback (identity.spec.ts:59 and 79, saved-choice.spec.ts:239-240, settings.spec.ts:72, 127 and 257), and 12 presence checks in 10 files.

### <a id="tweb-15"></a>TWEB-15: Failures keep no trace or screenshot, only the report's error text and an ARIA snapshot

- **Severity** low · **Dimension** approach · **Effort** S · **Risk** low · **Occurrences** 1
- **Where:**
  - [apps/web/playwright.config.ts:20-23](../../../../apps/web/playwright.config.ts#L20): use sets only the device and baseURL.
  - [scripts/qualify_identity.py:379](../../../../scripts/qualify_identity.py#L379): Prints the last 2,500 characters of the slice suite's output, and 1,500 at 333, 350 and 364.
  - [scripts/persistent_install.py:719](../../../../scripts/persistent_install.py#L719): The install suite signs in with the install owner's real password.
- **Evidence:** The config's use block sets only the device and baseURL. On a failure, the runner's JSON report under .checks keeps each error's message and stack, Playwright 1.64.1 writes an ARIA snapshot to error-context.md in the output directory, and the runner prints the last 1,500 to 2,500 characters of output. Nothing records the network, the console, DOM states over time or a screenshot.

  ```ts
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.AUTOBOTS_WEB_URL ?? "http://127.0.0.1:3000",
  },
  ```

- **Why it matters:** When a two-minute slice test fails against a disposable stack that has since been removed, what remains is an error message and the accessibility tree of one page. Diagnosing a timing, network or rendering failure means rebuilding the stack and rerunning, and intermittent failures can't be inspected at all.
- **Recommendation:** Enable trace: 'retain-on-failure' and screenshot: 'only-on-failure' for the disposable projects only, writing to the ignored output directory the runners already set (AUTOBOTS_WEB_OUTPUT, under .checks), and note the retention in the runbook. Never enable them for the install project, whose traces would record the owner's real password.
- **Rule check:** AGENTS.md: bulky raw results go to the ignored .checks directory, and secrets stay out of evidence. Traces of disposable stacks hold only fixture values, and the persistent install is excluded.
- **Verification:** revised. Corrected the claim that only a truncated log tail remains: the runners keep the JSON report (read by qualify_web.summarize), and the installed Playwright writes error-context.md with an ARIA snapshot on failure. The finding stands for traces and screenshots, and the install suite's real password still rules out tracing that run.

### <a id="tweb-16"></a>TWEB-16: 22 browser contexts are created inline and never closed

- **Severity** low · **Dimension** errors · **Effort** S · **Risk** low · **Occurrences** 22
- **Where:**
  - [apps/web/tests/browser/effects.spec.ts:37](../../../../apps/web/tests/browser/effects.spec.ts#L37): Three pages from inline contexts (37, 47, 58); the third stays on a run page.
  - [apps/web/tests/browser/experts.spec.ts:237-258](../../../../apps/web/tests/browser/experts.spec.ts#L237): Three more in one test, and six in the file.
  - [apps/web/tests/browser/workflows.spec.ts:52](../../../../apps/web/tests/browser/workflows.spec.ts#L52): Also at 119 and 124.
  - [apps/web/tests/browser/appearance.spec.ts:90-104](../../../../apps/web/tests/browser/appearance.spec.ts#L90): A context made by hand for an option test.use could set; it is closed only if the test passes.
- **Evidence:** 22 '(await browser.newContext()).newPage()' calls in 8 files discard the context handle. Across all files there are 45 newContext calls and 28 close calls, none in finally.

  ```ts
  const page = await (await browser.newContext()).newPage();
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto(`/runs/${RUN}`);
  ```

- **Why it matters:** These pages stay open for the rest of the single-worker run, some on run screens that keep event streams open, and nothing tears them down when a test fails.
- **Recommendation:** Use role fixtures from the shared support module, which close their contexts. Use test.use({ colorScheme, javaScriptEnabled, reducedMotion }) inside a describe instead of hand-made contexts. Where a context must be made by hand, close it in finally.
- **Rule check:** none
- **Verification:** confirmed. Recounted 22 inline contexts in 8 files, 45 newContext calls and 28 close calls, none in a finally block. Playwright closes only the contexts its own fixtures create, so these stay open until the worker closes the browser.

### <a id="tweb-17"></a>TWEB-17: Selector conventions are unwritten: data-field hooks, attribute lookups for role=status messages, and parent traversal

- **Severity** low · **Dimension** standards · **Effort** S · **Risk** low · **Occurrences** 590
- **Where:**
  - [apps/web/tests/browser/approvals.spec.ts:216-218](../../../../apps/web/tests/browser/approvals.spec.ts#L216): Finds the decision message by data-message.
  - [apps/web/components/approvals-panel.tsx:354-356](../../../../apps/web/components/approvals-panel.tsx#L354): That element has role=status.
  - [apps/web/tests/browser/settings-keys-and-vars.spec.ts:160](../../../../apps/web/tests/browser/settings-keys-and-vars.spec.ts#L160): Uses getByRole('status') for the same kind of message.
  - [apps/web/tests/browser/models.spec.ts:28-33](../../../../apps/web/tests/browser/models.spec.ts#L28): Finds label[for=...], then uses xpath=.. to reach a sibling.
  - [apps/web/tests/browser/slice-workflows.spec.ts:87](../../../../apps/web/tests/browser/slice-workflows.spec.ts#L87): Parent traversal with locator('..').
  - [apps/web/tests/browser/experts.spec.ts:562](../../../../apps/web/tests/browser/experts.spec.ts#L562): Structural CSS: main li a[href^='/experts/'].
- **Evidence:** The specs make 610 getByRole, getByLabel, getByText and getByPlaceholder calls and 590 data-attribute selectors (grep -o '\[data-[a-z-]+'), 227 of them on data-field with 102 distinct values. data-field appears 127 times in 31 app and component files and in no stylesheet, so it is a test-hook convention that is written down nowhere. 27 message lookups use data-message or data-policy-message, although nearly all of those elements have role=status or role=alert.
- **Why it matters:** A lookup by attribute doesn't prove that a message is announced, which matters for DH-06's accessible-label requirement and for DS-04. Parent traversal and structural CSS break on harmless markup changes. A component author can rename a data-field without knowing that tests depend on it.
- **Recommendation:** Write the convention down in a tests/browser README: role and label first, data-field only for values that have no accessible role, and never for styling. Consider setting use.testIdAttribute = 'data-field' so hooks read as getByTestId. Find messages with getByRole('status' | 'alert') filtered by text. Replace xpath=.. with a role-scoped locator or a hook on the row, and ban 'xpath=' with no-restricted-syntax.
- **Rule check:** DH-06 and nextjs.md ask to verify accessible flows and labels; the existing data-field hooks stay.
- **Verification:** revised. Recounted with grep: 590 data-attribute selectors (not 560), 227 on data-field (not 217) and 127 data-field uses in app and components (not 125); the shortcut message is aria-live without a role. The cited lookups, the role=status element at approvals-panel.tsx:354-356 and the xpath=.. traversal are as described.

### <a id="tweb-18"></a>TWEB-18: The same concepts go by different names across specs

- **Severity** low · **Dimension** naming · **Effort** S · **Risk** low · **Occurrences** 17
- **Where:**
  - [apps/web/tests/browser/slice-closure.spec.ts:22](../../../../apps/web/tests/browser/slice-closure.spec.ts#L22): write() returns CSRF headers and writes nothing (defined in 14 files).
  - [apps/web/tests/browser/settings.spec.ts:29](../../../../apps/web/tests/browser/settings.spec.ts#L29): The same headers without an idempotency key, named csrf().
  - [apps/web/tests/browser/run-workspace.spec.ts:28](../../../../apps/web/tests/browser/run-workspace.spec.ts#L28): Here the same helper is named headers().
  - [apps/web/tests/browser/slice.spec.ts:7](../../../../apps/web/tests/browser/slice.spec.ts#L7): signIn() that also saves a provider key.
  - [apps/web/tests/browser/settings-sections.spec.ts:14-18](../../../../apps/web/tests/browser/settings-sections.spec.ts#L14): EMAIL_C and EMAIL_F for the member and the reader. identity.spec.ts says MEMBER_EMAIL, readiness.spec.ts READER_EMAIL and settings-keys-and-vars.spec.ts EMAIL_READER.
  - [apps/web/tests/browser/install-current.spec.ts:7](../../../../apps/web/tests/browser/install-current.spec.ts#L7): AUTOBOTS_TEST_SCREENSHOTS, where the other suites read AUTOBOTS_WEB_SCREENSHOTS.
- **Evidence:** One header builder has three names: 14 write, 2 csrf and 1 headers. The owner's email is bound as EMAIL, EMAIL_A or OWNER_EMAIL across 28 files, and the reader's email has three names. Two variables name the screenshots directory.
- **Why it matters:** A call such as write(other, "foreign") doesn't say that it only builds headers. signIn(page) in slice.spec.ts silently changes the key state. Letter-coded constants such as EMAIL_C reflect the order in which fixtures were written, not the user's role.
- **Recommendation:** Name by intent in the shared support module: writeHeaders(page, key?); users.owner, users.ownerB, users.member, users.reader and users.ops; signIn kept separate from ensureProviderKey; and one screenshots variable.
- **Rule check:** DH-06 asks for readable names; no rule constrains test identifiers further.
- **Verification:** confirmed. Verified 14 write, 2 csrf and 1 headers builders; the owner's email is EMAIL_A in 22 files, EMAIL in 4 and OWNER_EMAIL in 2; the reader's email is READER_EMAIL, EMAIL_READER or EMAIL_F. install-current.spec.ts reads AUTOBOTS_TEST_SCREENSHOTS, which persistent_install.py:718 sets.

### <a id="tweb-19"></a>TWEB-19: Some local helpers take long positional lists or do several things at once

- **Severity** low · **Dimension** functions · **Effort** S · **Risk** low · **Occurrences** 5
- **Where:**
  - [apps/web/tests/browser/run-workspace.spec.ts:63-74](../../../../apps/web/tests/browser/run-workspace.spec.ts#L63): command(page, id, name, version, key): five positional parameters.
  - [apps/web/tests/browser/run-workspace.spec.ts:41-61](../../../../apps/web/tests/browser/run-workspace.spec.ts#L41): admitted() both saves a provider key and admits a run.
  - [apps/web/tests/browser/settings-sections.spec.ts:206-230](../../../../apps/web/tests/browser/settings-sections.spec.ts#L206): watching() creates a context, installs a spy, signs in, toggles a setting and sleeps 5 seconds.
  - [apps/web/tests/browser/settings.spec.ts:170-171](../../../../apps/web/tests/browser/settings.spec.ts#L170): A no-op page.evaluate, and a dynamic import of node:fs although line 1 already imports it statically.
  - [apps/web/tests/browser/run-workspace.spec.ts:306-311](../../../../apps/web/tests/browser/run-workspace.spec.ts#L306): noViolations is declared after tests that inline the same scan (241-244, 483-486).
- **Evidence:** Two calls from run-workspace.spec.ts:115-116:

  ```ts
  expect((await command(page, id, "resume", 2, "l2")).status()).toBe(200);
  expect((await command(page, id, "pause", 3, "l3")).status()).toBe(200);
  ```

- **Why it matters:** Calls like command(page, id, 'resume', 2, 'l2') read as magic numbers, and helpers that both arrange state and act hide a test's preconditions from the call site.
- **Recommendation:** Use parameter objects, for example runCommand(page, { run, command: 'resume', expectedVersion: 2 }) with a generated key. Split ensureProviderKey from admitRun. Turn watching() into a fixture for the spied context plus a clock-driven poll. Delete the dead lines, and declare helpers before the tests that use them.
- **Rule check:** DH-06: small cohesive functions and readable names.
- **Verification:** confirmed. Verified command()'s five parameters (ESLint max-params), admitted() saving a key before admitting, watching()'s five steps, the no-op evaluate and dynamic node:fs import at settings.spec.ts:170-171, and the inline scans at run-workspace.spec.ts:241-244 and 483-486. Function declarations are hoisted, so the late helper is a readability point only.

## Rejected during verification

None. Every finding was confirmed or revised.

## Not covered

This is a static review: no spec, runner or stack was run. Flakiness, durations and pass or fail state therefore come from reading the code; the figure of about 50 seconds of sleeps is summed from the source, and the latest db profile report was not re-verified. The Python runners (scripts/qualify_identity.py, qualify_web.py, qualify_release.py and persistent_install.py), the tests/db arrangers and tests/web/fixture_worker.py were read only where they select or feed these specs; their own quality belongs to the scripts and db-tests areas. Components were opened only to confirm timers, roles and data-field usage. Only the DH-03, DH-06 and DH-09 sections of PRD-Development-Harness.md were read. Per-file ESLint counts come from the measurement step's eslint.json, whose run did not include playwright.config.ts. No command was refused.
