# Verification — us-11-11-design-system-migration-final

Change: us-11-11-design-system-migration-final
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Move forms to shared components | PASS | A harness test finds no raw control under `apps/web/app` or `components`, including forms only a state reaches. In the browser, all 98 text controls across 42 captures carry the shared `data-slot`, with `border-input`, and focus is visible at 14.5:1 or better on 557 stops |
| Capture every named surface once | PASS | 21 surfaces in dark and light, each with a retained screenshot, contrast from default, hover and focus states, and axe at WCAG 2.1 AA with 0 violations, under `docs/engineering/evidence/US-11.11/` with `revision.json` |
| Report what fails or is missing | PASS | The first capture failed on input boundaries and the light focus ring. Both were corrected in pairing, with no token changed, so no proposal is needed. Eight DS-03 names with no screen are listed as absent, in `results.json` and the summary |

Task 3's checks are in the summary: keyboard, zoom at 200% and 400%, reduced motion, and appearance sending no request and changing no state. I read a sample of the screenshots myself: `home-light`, `approvals-dark` and `state-local-only-light`.

Checks on the final code: `full`, `db` and `harness` all exit 0, and `openspec validate` is clean. `full` runs `qualify_web.py`'s 32 browser tests, and `db` runs the identity qualifier's 369 cases.

## Findings

- **Input boundaries and the light focus ring failed 3:1,** as `--input` and `--ring` alone. Corrected as above. The tokens themselves still measure below 3:1.
- **A defect from US-11.9, found by the `full` profile.** The disclosure left a refused reply unread, which held its connection open, so 14 of `qualify_web.py`'s 32 tests timed out on a signed-out Home. `full` hadn't run since that story. Each new panel now reads a refusal, and all 32 pass.
- **A false message on Home.** "Inference is not configured yet" stayed after inference existed. It's corrected, the same kind of error as finding B6.
- **400% zoom:** the shell's sidebar now stacks at narrow widths.

## Limits

Listed in [the evidence summary](../../../../../docs/engineering/evidence/US-11.11/summary.md#limits). **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
