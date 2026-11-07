## Why

US-14.15 and [Decision 0019](../../../docs/engineering/decisions/0019-sol-profile-and-browser-use.md) S1 to S4: the owner chose Sol (`openai/gpt-6.1-sol-20260929`) as a third approved profile, the `researcher` role's default for browsing, offered only after its route is qualified live.

## What Changes

- `openrouter_sol` joins the approved profiles (canonical `openai/gpt-6.1-sol-20260929`, request ID `openai/gpt-6.1-sol`). A refused profile's reason now names it: "Sol isn't offered for new runs until its route is qualified." DeepSeek's reason is unchanged, and a workflow refusal carries the same reason.
- MP-01's last step becomes the role's built-in default: Sol for `researcher` once Sol is offered, Terra for every other role. Every explicit choice still wins.
- Migration 40 widens the three profile checks and adds Sol's row; the seed carries it too.
- The route runner has Sol's route and its US$1.20 cap. Sol's route was qualified live (39 calls, US$0.011 reported, US$0.14 counted), and migration 41 records the result for Settings. Sol is then offered, and the Expert editor lists it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `model-policy`: Sol, and the researcher default.

## Impact

`domain/models.py`, `application/workflows.py`, `api/workflow_routes.py`, `operations/route_qualification.py`, migrations 40 and 41, `supabase/seeds/reference.sql`, `apps/web/components/expert-editor.tsx`, the generated contract and client, `tests/db/sol_profile_check.py`, `scripts/app_db.py`, `scripts/qualify_upgrade.py`, and unit and browser tests. **The persistent install needs migrations 38 to 41 applied before it runs this code.**
