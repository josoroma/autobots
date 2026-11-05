## 1. Interfaces (scenarios: Start and stop without data loss; Expose safe operational evidence)

- [x] 1.1 Worker process with heartbeat, bounded drain and reconnection
- [x] 1.2 Local status route, and an admission gate on database, schema, Storage and disk
- [x] 1.3 JSON logs with redaction, and inherited tracing turned off at bootstrap
- [x] 1.4 Local Operations page

## 2. Retention (scenario: Apply declared retention without erasing recovery evidence)

- [x] 2.1 Per-workspace policy, default keep everything
- [x] 2.2 Purge and key expiry functions with their refusals, and objects removed after commit

## 3. Exercise (all scenarios)

- [x] 3.1 `scripts/qualify_operations.py` on a disposable stack: drain, cut-short drain, degraded services, stop and start, resume, retention, logs
- [x] 3.2 Operations runbook with the qualified commands, symptoms and recovery
