# Verification — us-16-1-sober-control-borders

Change: us-16-1-sober-control-borders
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Scenarios

| Scenario | Result | Observed |
|---|---|---|
| One even border and no underline | PASS | The `db` profile's visual walk (`slice-visual.spec.ts`) measured 130 Input, Textarea and Select controls on 42 surfaces, in dark and light: none with an inset underline, none with uneven border sides or colors |
| The composer's goal field matches | PASS | Home's goal field, both themes: even border, no underline, 3.78:1 and 3.36:1. No `main section` on any surface had a box shadow, the composer and sign-in cards included. Home's dark screenshot looked at |
| Still accessible | PASS | Lowest control border 3.36:1 against its surroundings (DS-03 needs 3:1), 0 boundary failures, 642 focus stops with 0 focus failures, axe clean on every surface |

## Runs

- `python3.12 scripts/verify.py --profile fast`: exit 0.
- `python3.12 scripts/verify.py --profile db`: exit 0, inputs unchanged during the run. Results in `.checks/identity/visual/results.json`.

## Findings

None. The token values are set from computed contrast: light `oklch(0.64 0 0)`, dark `oklch(0.556 0 0)`, recorded in `docs/design/studio-extensions.css`. No independent review, by the delivery rule.
