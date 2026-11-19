# memory-compaction Specification

## Purpose
TBD - created by archiving change us-8-1-scoped-memory-lexical-retrieval. Update Purpose after archive.

## Requirements

### Requirement: Critical state survives compaction
When a run with long source or tool outputs and pending tool or approval context offloads and summarizes using its snapshotted role, goal, criteria, permissions and unresolved waits SHALL remain outside lossy summaries, and citations SHALL point to retrievable original evidence.

#### Scenario: Preserve critical state through compaction
- **GIVEN** long source/tool outputs and pending tool/approval context
- **WHEN** the run offloads and summarizes using its snapshotted role
- **THEN** goal, criteria, permissions and unresolved waits remain outside lossy summaries and citations point to retrievable original evidence

### Requirement: Scoped local memory
When another workspace requests stored memory or lexical evidence, authorization SHALL prevent leakage, and no extra embedding or reranking endpoint SHALL be introduced.

#### Scenario: Keep memory scoped and local
- **GIVEN** another workspace requests stored memory or lexical evidence
- **WHEN** retrieval executes
- **THEN** authorization prevents leakage and no extra embedding/reranking endpoint is introduced

### Requirement: The plan is pinned through compaction

A compacted call's state block (Decision 0034 C1) SHALL hold the run's current plan, read fresh from its records: the plan's version and each task's ID, title and criteria, marked done or open. It SHALL tell the model to continue that plan, completing open tasks with `complete_task`, and to revise it only with a reason that keeps completed tasks unchanged. A run without a plan SHALL be told it has none.

#### Scenario: A compacted call sees the run's plan
- **GIVEN** a run with plan version 1 of search, collect and write, whose search task is complete
- **WHEN** its state block is built for a compacted call
- **THEN** it lists plan version 1 with search done and collect and write open, each with its title and criteria, and says to continue the plan with complete_task and to revise it only with a reason that keeps completed tasks

#### Scenario: A run without a plan says so
- **GIVEN** a run that hasn't proposed a plan
- **WHEN** its state block is built
- **THEN** it says there is no plan yet, and lists the goal, criteria, tools and paths as before
