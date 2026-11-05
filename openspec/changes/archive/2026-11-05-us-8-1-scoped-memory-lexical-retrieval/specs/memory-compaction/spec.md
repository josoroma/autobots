## ADDED Requirements

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
