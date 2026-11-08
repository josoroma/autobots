# Tasks

## 1. API (Waiting and Decided with counts; Facts of a request; Sidebar badge from a count)

- [x] 1.1 Extend the approval read model with decided statuses, the run goal, the served plan task, the decider and time, and the arguments' size, plus counts
- [x] 1.2 Add `status=decided`, list `counts`, and `GET /v1/approvals/count`, then regenerate the contract and client

## 2. Web (all scenarios)

- [x] 2.1 Build the tabs, the list beside the detail, J and K, the Fields and JSON views with text-node markdown, and the two-press shortcuts with a live announcement
- [x] 2.2 Add the sidebar badge from the count endpoint
- [x] 2.4 Make the list one tab stop on the selected request (roving tabindex, arrows in the list), so keyboard focus never moves up into the detail (found by `slice-visual`)
- [x] 2.5 Arrange the task link as completion writes it (task and operation ID on the run's tool use), and wait for each selected detail in the long-request spec
- [x] 2.6 Clear the list when the tab changes, keeping the tabs and counts visible while the new list loads, so a stale request is never shown or clicked
- [x] 2.3 Cover the scenarios in `approvals.spec.ts` with axe on a disposable stack, after arranging a markdown request and a task link in `tests/db/approval_check.py`, and keep the other specs working with the selected-request layout
