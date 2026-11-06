## Why

US-10.2's finding B3: PRD 12.1's Operations screen lacks delayed schedules, OpenRouter availability, restore history and qualification evidence, so the local install's state can't be read in one place.

## What Changes

- `local_backup.py` records each restore and its verification result in `restores.jsonl` beside the backup, with a date, a result and counts.
- The status contract adds those, delayed routine occurrences, OpenRouter's availability from its public catalog, and each route's stored qualification.
- The Operations screen shows them, and says what's unknown or unavailable.

## Capabilities

### New Capabilities

- `operations-status`: the facts Operations shows, and how it says what's unknown or unavailable.

### Modified Capabilities

None.

## Impact

`contracts/operations.py`, `application/operations.py`, `api/operation_routes.py`, `application/provider_settings.py`, `scripts/local_backup.py`, generated clients, the Operations panel, two runbooks and tests. No migration and no model call. A page load now makes one catalog request, bounded to 3 seconds.
