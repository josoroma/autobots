# Tasks

## 1. Storage (Migration 64 adds the private switch table)

- [x] 1.1 Add migration 64 with `app_private.tool_switches`, ship 64 in readiness, and regenerate the schema snapshot and row types on a disposable stack. Checked by the migration-header test and the `db` profile

## 2. Rules and enforcement (Every switchable tool and group shows its switch; Turning a tool off; Turning a group off; Admission and Expert saves refuse; A run in progress can't call)

- [x] 2.1 Add `domain/tool_switches.py` and `application/tool_switches.py`, put the switches in the workspace view, apply them in `describe` and the groups, and refuse calls in the gateway with `tool_turned_off`. Checked by unit tests and a disposable database check through admission, Expert save and the gateway

## 3. API and contract (Only the owner changes a switch, at its version)

- [x] 3.1 Add the switch DTOs, `viewer_can_switch` and the two owner-only PUT routes. Regenerate OpenAPI and the client. Checked by API tests (owner, member, stale) and `generate_contracts.py check`

## 4. Tools page (The Tools page switches)

- [x] 4.1 Add accessible switches on tool rows and group headers, words for each state, and repair text. Checked by web unit tests and `tools.spec.ts` in the `db` profile, with axe in both themes

## 5. Docs

- [x] 5.1 Update `CODEBASE.md` and the operations runbook

## 6. Verify findings

- [x] 6.1 The first scenario says every group carries a switch, but by Decision 0033 W1 and W5 only a group holding a switchable tool does. The planning and delegation groups hold none. Correct the scenario in SPECS.md and the change's spec to "every group that holds a switchable tool", and assert it for every group in `test_tool_switches.py`
