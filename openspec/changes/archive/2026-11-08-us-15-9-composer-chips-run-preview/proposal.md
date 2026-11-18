## Why

US-15.9, [PRD-Studio HM-02 and HM-03](../../../../docs/PRD/PRD-Studio.md#home) and [Decision 0022 D11](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). Home's composer has a model select, a fixed US$1.00 disclosure and file chips that show a path and type. A person can't choose an Expert or a budget there, and can't see which profiles and tools the run would use.

## What Changes

- A pure `domain/budgets.py` sets the D11 rules: US$0.25 to US$5.00 in US$0.25 steps, US$1.00 by default, never above what's left of the daily cap.
  - `remaining_daily_micro_usd` reads that from the ledger, counting as admission does.
- `RunRequest.budget_micro_usd` (optional) becomes the run's frozen limit.
  - A budget outside the range is refused with 422 `budget_out_of_range`, and one off the step with 422 `budget_off_step`.
  - A budget above the remaining cap is refused with 409 `budget_above_daily_cap`.
  - A budget sent together with an explicit limit is refused with 422 `budget_conflict`.
  - `limit_micro_usd` stays for operator tooling.
- `RunIntentCheck.budget` and the new `GET /v1/run-preview` (`run_profile`, `expert_id`) return the allowed budget range. The preview also returns the profiles each role would resolve to, as admission would resolve them, and the tools the run would be granted. It creates nothing and calls no model.
- A migration raises the ledger's per-run ceiling from US$1.00 to US$5.00, the highest D11 budget.
  - Admission reserves against the lower of that ceiling and the run's frozen limit.
  - Without that change every chosen budget above US$1.00 would be cut.
  - No screen or command ever set the ceiling, so rows still at the old default move with it.
- The composer adds a chip row: Model for this run, Expert ("No Expert, a goal run" or one Expert) and Budget, with what's left of today's cap.
  - The disclosure follows the chosen budget and the Expert's bindings.
  - Preview chips read, for example, "Terra · 13 roles" and "Sol · researcher", followed by the tools.
  - Run starts a direct session first when an Expert is chosen.
  - File chips show the name, type and size.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `run-disclosure`: composer chips, run preview and chosen budget.

## Impact

- New `domain/budgets.py`, plus changes to `application/model_admission.py`, `contracts/settings.py`, `contracts/run_commands.py`, `api/run_routes.py` and `api/settings_routes.py`.
- A migration for the per-run ceiling.
- The generated contract and client.
- `goal-composer.tsx`.
- `scripts/qualify_identity.py` (a composer owner with US$2.10 left and one Expert).
- `test_budgets.py` and `composer.spec.ts`.
