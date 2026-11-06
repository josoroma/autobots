# test-closure Specification

## Purpose
TBD - created by archiving change us-12-2-close-what-test-can. Update Purpose after archive.

## Requirements

### Requirement: Inspect the goal after a compaction

The release SHALL observe this where a test can: inspect the goal after a compaction.

#### Scenario: Inspect the goal after a compaction
- **GIVEN** a run on a disposable stack that compacts through the real SDK on a fake transport
- **WHEN** a person opens the run in a browser before and after the compaction
- **THEN** the original request and its normalized criteria read the same both times

### Requirement: Return partial results across descendants

The release SHALL observe this where a test can: return partial results across descendants.

#### Scenario: Return partial results across descendants
- **GIVEN** a run tree with a finished child and a limit exhausted across the tree
- **WHEN** the limit stops dispatch
- **THEN** no new model or tool call starts in any descendant, and the finished child's results can be read from the run

### Requirement: See delegation on the Assignments card

The release SHALL observe this where a test can: see delegation on the assignments card.

#### Scenario: See delegation on the Assignments card
- **GIVEN** a run with a child, on a disposable stack with a scripted model
- **WHEN** a person opens the run page in a browser
- **THEN** the Assignments card shows the child's Expert and its state or outcome, its link opens the child run, and the child's result links to its parent

### Requirement: Rebuild across a disconnect

The release SHALL observe this where a test can: rebuild across a disconnect.

#### Scenario: Rebuild across a disconnect
- **GIVEN** a run with a plan, a pending approval and a published artifact, on a disposable stack with a scripted model
- **WHEN** the browser's connection drops and returns while events are committed
- **THEN** the plan, approval, artifact and status are rebuilt on screen with no gap or duplicate

### Requirement: Use local files with no key

The release SHALL observe this where a test can: use local files with no key.

#### Scenario: Use local files with no key
- **GIVEN** a published artifact and a workspace with no OpenRouter key
- **WHEN** a person opens the artifact list and downloads the artifact
- **THEN** both work, and any attempt at inference reports credentials_required with no model call

### Requirement: Inventory each dispatch

The release SHALL observe this where a test can: inventory each dispatch.

#### Scenario: Inventory each dispatch
- **GIVEN** instrumentation at the model factory's boundary, and a fake-transport run that dispatches through its executor, a matching summarizer during compaction and a child
- **WHEN** the run finishes
- **THEN** the inventory lists every dispatch by role and route and matches the frozen role map, and a dispatch outside the factory or from an SDK implicit model fails the test

### Requirement: Check the shape of Terra's requests

The release SHALL observe this where a test can: check the shape of terra's requests.

#### Scenario: Check the shape of Terra's requests
- **GIVEN** requests for Terra captured on a fake transport
- **WHEN** each body is checked
- **THEN** it carries no unadvertised sampler or parallel-tool flag and no reasoning-off, `reasoning` has a checked shape, and a request that breaks either fails the check

### Requirement: Walk each surface in both themes

The release SHALL observe this where a test can: walk each surface in both themes.

#### Scenario: Walk each surface in both themes
- **GIVEN** every DS-03 surface in use, in dark and light
- **WHEN** keyboard order, disabled controls, zoom and reduced motion are checked on each
- **THEN** each result is retained under docs/engineering/evidence/US-12.2/ with the revision it came from, a surface that doesn't exist is listed as absent, and a failure is recorded and corrected first in its pairing, focus, label or structure

### Requirement: Fix round 5's small findings

The release SHALL observe this where a test can: fix round 5's small findings.

#### Scenario: Fix round 5's small findings
- **GIVEN** findings R5-1 to R5-7
- **WHEN** the fixes are checked
- **THEN** R5-1's browser test is named for what it asserts
- **AND** R5-2's runbook row says the refusal counts bytes, and that its remedy isn't available for a child or workflow run
- **AND** R5-3's report can't read an unread count as 0, and its not_checked catches a blank value
- **AND** R5-4's lone surrogate is shown unreachable, or is refused with a stated reason before any reservation
- **AND** R5-5's text is gone once the outcome is known
- **AND** R5-6's hidden picker after a lost reply, and the key cleared by a refusal, each have a test
- **AND** R5-7's guard names `grep . master.key` and piped forms among its limits

### Requirement: State what a test can't settle

The release SHALL observe this where a test can: state what a test can't settle.

#### Scenario: State what a test can't settle
- **GIVEN** a part of a row that needs a live route, a real interruption or a person, such as a real compaction, live request bodies, real host downtime for LC-15, a cut TCP connection that wasn't arranged, or a screen reader
- **WHEN** the row is reported
- **THEN** that part is named as a limit and never as passing, fake-transport and disposable results keep their own class, and this story makes no paid call or persistent change
