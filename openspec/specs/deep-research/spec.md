# deep-research Specification

## Purpose
TBD - created by archiving change us-16-6-deep-research-runs-like. Update Purpose after archive.

## Requirements

### Requirement: The Deep research writer works in two roles

The seeded Deep research writer (Decision 0034 E1 to E5) SHALL carry instructions that follow Deep-Research-Content-Writer's phases: plan, search, collect, synthesize, write, check and publish. Given a topic, it SHALL save and publish `research/sources.md`, `research/synthesis.md`, `content.md` and `report.md` under the outputs folder it may write: `outputs/` in a direct run, `outputs/child-N/` as a workflow step. Given a previous step's result, a JSON object with `artifact_ids`, it SHALL review instead: read those artifacts with `read_artifact`, check the document's citations against the sources, and publish its review, without searching again.

#### Scenario: The workflow's review step reads the first step's artifacts
- **GIVEN** a disposable stack and a scripted model
- **WHEN** the Deep research content writer runs on "langchain for deep agents", its first step publishes sources, synthesis, a document and a report, and the owner approves its gate
- **THEN** the second step reads each of them with read_artifact and publishes its review, and the execution succeeds with the approved value as its output

### Requirement: A workflow's agent steps get their Experts' tools

A workflow execution's run SHALL be granted the workflow tools and the tools of the Experts its agent steps name, at each Expert's current version, so each agent step's child gets its Expert's tools (Decision 0034 F3). A requested tool list SHALL narrow those tools as it narrows the workflow tools, and the workflow's own blocks SHALL NOT call them.

#### Scenario: An agent step gets its Expert's tools
- **GIVEN** a published workflow whose agent step names an Expert granted read_artifact and google_extract
- **WHEN** an execution is created, without and then with a requested tool list naming only read_artifact
- **THEN** the first execution's grant holds the workflow tools, read_artifact and google_extract, and the second holds read_artifact but not google_extract

### Requirement: Deep research runs live on the install, documented

On the owner's persistent install (Decision 0034 R1, R2), the Deep research writer and its workflow SHALL each run once on "langchain for deep agents", started from the Studio with a US$5.00 budget and never more, and a README SHALL document what they did as observed. No key SHALL appear in their artifacts.

#### Scenario: The install runs the new code and seed
- **GIVEN** the owner's persistent install, rebuilt and restarted by the owner with this code and inference on, and seeded again
- **WHEN** the Studio's Experts and Workflows pages are read
- **THEN** the Deep research writer and the Deep research content writer are there, and what was there before is unchanged

#### Scenario: A live Expert run
- **GIVEN** the owner's OpenRouter and SerpApi keys
- **WHEN** the coordinator starts the Deep research writer on "langchain for deep agents" from the Studio with a US$5.00 budget
- **THEN** the run ends with its real outcome and published artifacts, its cost stays within US$5.00, and no key appears in its artifacts

#### Scenario: A live workflow execution
- **GIVEN** the same keys
- **WHEN** the coordinator starts the Deep research content writer on "langchain for deep agents" with a US$5.00 budget, and the owner decides its gate
- **THEN** the execution ends with its real outcome, both steps' artifacts are published, and its cost stays within US$5.00

#### Scenario: The README documents the runs
- **GIVEN** the two runs' records
- **WHEN** README-Deep-Research-Content-Writer.md is written and linked from README.md and README-DEV.md
- **THEN** it explains the reference, how Autobots runs it as an Expert and as a workflow, and what each run did, with counts and costs as observed, and every link resolves
