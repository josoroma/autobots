## 1. Portable profiles and evidence freshness

- [x] 1.1 Add `fast` and `full` to `scripts/verify.py` with exit codes 0, 1 and 2, and keep `db` and `operations` not implemented (Run independently of Claude)
- [x] 1.2 Widen report fingerprints to application inputs, and make `report_state` and `Stop` read the profile the changed scope needs (Run independently of Claude)
- [x] 1.3 Add fixtures for pass, failure, prerequisite error, scope selection and stale reports (Run independently of Claude)

## 2. Bounded event-to-check adapter

- [x] 2.1 Add the deadline, broad fail-closed handling, tool validation and symlink-aware secret checks to `.claude/hooks/dispatch.py` (Handle unsafe hook input)
- [x] 2.2 Map `PostToolUse` paths to check domains and run the bounded `ruff` diagnostic (Handle unsafe hook input)
- [x] 2.3 Add fixtures for malformed input, metacharacters, symlinks, timeout and a missing executable (Handle unsafe hook input)

## 3. Documentation

- [x] 3.1 Update the runbook, `AGENTS.md`, delivery rule, verify skill, `.claude/autobots.json` and `CODEBASE.md`, and exercise the runbook commands (Run independently of Claude)
