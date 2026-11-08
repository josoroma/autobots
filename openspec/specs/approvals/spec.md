# approvals Specification

## Purpose
TBD - created by archiving change us-5-3-argument-bound-approvals-durable. Update Purpose after archive.

## Requirements

### Requirement: Decisions bound to the proposal
When a reviewer approves or rejects a persisted tool, version, normalized arguments hash, scope and expiry, only the matching authorized current proposal SHALL be released, and changed, expired or replayed decisions MUST NOT authorize other work.

#### Scenario: Bind the review decision
- **GIVEN** a persisted tool/version, normalized arguments hash, scope and expiry
- **WHEN** the reviewer approves or rejects
- **THEN** only the matching authorized current proposal is released and changed/expired/replayed decisions cannot authorize other work

### Requirement: Restart during an approval wait
When a worker that persisted a proposal and stopped restarts and receives a decision, proposal persistence SHALL remain idempotent, no pre-approval effect SHALL occur, and rejection SHALL permit only replanning or failure handling.

#### Scenario: Restart during approval wait
- **GIVEN** a worker has persisted the proposal and interrupted
- **WHEN** the worker restarts and receives a decision
- **THEN** proposal persistence remains idempotent, no pre-approval effect occurs and rejection permits only replanning or failure handling

### Requirement: The approvals inbox decides one exact request at a time

Approvals SHALL list Waiting and Decided requests with server counts, beside the selected request's detail: who asked, the run's goal, the plan task served, relative and absolute expiry, and for a decided one who decided it, when and the outcome. It SHALL show the exact stored arguments whole with their hash and size, in a JSON view and a Fields view that renders markdown safely. ⌘↵ and ⌘⌫ SHALL need a second press within 2 s and SHALL never act while a text field has focus. The sidebar SHALL show the pending count from a count endpoint.

#### Scenario: Waiting and Decided with counts
- **GIVEN** pending, approved, rejected, expired and withdrawn requests in this workspace
- **WHEN** a reviewer opens Approvals and presses J and K with focus outside any text field
- **THEN** Waiting lists the pending requests and Decided lists the rest, each tab shows its count, the list sits beside the selected request's detail, and J and K move the selection between requests

#### Scenario: Facts of a request
- **GIVEN** a decided request whose operation ID matches a tool use made for a plan task
- **WHEN** the request is selected
- **THEN** the detail shows who requested it, the run's goal, that plan task's title, the expiry as both relative and absolute time, and who decided it, when, and the outcome

#### Scenario: The exact request, whole
- **GIVEN** a pending request whose arguments contain markdown, and another too long to show whole
- **WHEN** each is shown in the Fields view and the JSON view
- **THEN** the first shows the full stored arguments with their hash and byte size, the Fields view lists the parsed keys and shows markdown both as text and rendered and sanitized, neither view hides, reorders or truncates content, and the second request can't be approved

#### Scenario: Shortcuts need a second press
- **GIVEN** a focused pending request and focus outside any text field
- **WHEN** the reviewer presses ⌘↵ once and waits more than 2 s, then presses ⌘⌫ twice within 2 s
- **THEN** the single ⌘↵ is announced as needing a second press and decides nothing, the ⌘⌫ pair rejects the request bound to the hash shown, and with focus in a text field neither shortcut acts

#### Scenario: Sidebar badge from a count
- **GIVEN** two pending approvals and more approvals in total than fit on one page
- **WHEN** any screen renders the sidebar
- **THEN** the Approvals link shows 2 with the accessible text "2 waiting", read from a count endpoint rather than from a listed page
