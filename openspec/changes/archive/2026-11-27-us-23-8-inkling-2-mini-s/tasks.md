# Tasks: US-23.8, Inkling 2 Mini's route qualified at its own output cap, and offered on Local

## 1. The runner and the live run

- [x] 1.1 Build each local call with `limits_for(profile).output_tokens`, keep the truncation fixture's cap, and record `output_tokens` in the report. Checked by `test_each_call_gets_the_routes_own_output_cap` for both local profiles, and the fake suite tests' loopback-only assertions.
- [x] 1.2 On the owner's request, after `llama-server --version` and the weights' SHA-256 against the pin and the manifest, run the suite on Inkling 2 Mini at its cap. Keep the 512-token run in `.checks/route-qualification/inkling-512/`, then stop the server. Checked by the live report.

## 2. Storing and offering

- [x] 2.1 Add migration `20261127000072_inkling_local_route_qualified.sql` with its header lines, and set `SHIPPED_MIGRATIONS` to 72. Checked by the harness migration-header test, `test_schema_release.py` and the db profile.
- [x] 2.2 Update `local_offering_check.py`, the SQLI-12 check in `scripts/app_db.py` and `models.spec.ts` to expect Inkling 2 Mini offered. Checked by the db profile.
- [x] 2.3 Show a switch to Local with Inkling 2 Mini as the Local default, a run on it with 8,192 output tokens, then Bonsai 2.5 saved as the Local default and a run on it with 4,096, with role overrides refused, in `model_source_check.py` on a real database and in pytest. Show that neither is offered on OpenRouter. Checked by pytest and the db profile.

## 3. Docs and checks

- [x] 3.1 Amend Decision 0041's measurements row for Inkling 2 Mini, the local app runbook and `CODEBASE.md`. Checked by reading each against A8, A11 and the code.
- [x] 3.2 The fast, db and harness profiles pass. Checked by `scripts/verify.py`.
