---
name: autobots-verify-change
description: Run the implemented portable Autobots check profiles appropriate to a change and interpret their evidence honestly, separating static, mock, disposable and live results.
---

# Verify behavior and evidence

Read `.claude/autobots.json`, the mapped contract, selected work record and harness verification contract. Inspect `verification.implemented_profiles` and the actual runner before choosing commands; configuration is not proof that an implementation exists.

From the repository root use `python3.12 scripts/verify.py --profile <profile>`. Profiles are `harness`, `fast`, `full`, `db`, `operations`. Exit codes: 0 passed, 1 a required check failed, 2 a prerequisite is unavailable or a check could not run. `harness`, `fast`, `full` and `db` are implemented, and `db` uses only a disposable target. An unavailable operations profile must fail as not implemented; never substitute another profile for it. A `fast` step recorded `not_run` was outside the changed scope, and did not pass.

- Match checks to acceptance and changed inputs, including untracked source, nonsecret config, locks, generated contracts and verifier code.
- Use prepared environments. No implicit package downloads, Docker startup, persistent SQL mutation, real credentials or external inference in ordinary checks.
- Database/operations coverage requires the qualified disposable target and ownership guards. Paid OpenRouter qualification is an explicitly initiated bounded task, not a side effect of verification.
- Inspect exit codes, assertions, test counts and artifacts. Missing tools, empty suites, errors, failures, skips and not-run checks remain distinct. Re-run affected checks when inputs change.
- Preserve reviewed redacted manifests/summaries under `docs/engineering/evidence/<work-item-id>/`; large raw results belong in ignored `.checks` with availability/retention declared. Never copy or hash raw `.env` secrets into evidence.

Return commands actually executed, expected/observed assertions, input fingerprint, verification class/model transport, results and gaps. Use [DH-W04–06](../../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract). Synthetic hook stdin proves script behavior; actual assistant event delivery requires separate evidence.
