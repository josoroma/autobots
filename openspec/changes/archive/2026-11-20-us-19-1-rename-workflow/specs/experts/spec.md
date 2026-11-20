## ADDED Requirements

### Requirement: The concept seed keeps a renamed workflow as the owner named it

The concept seed SHALL keep a workflow that holds a seeded name, including one the owner renamed to it, and SHALL add nothing for that name (Decision 0037 N6, Decision 0034 S1). A seeded workflow the owner renamed away from its seeded name SHALL keep its new name, versions, hashes and draft. Seeding again SHALL add the seeded workflow beside it, published or as a draft as the seed would leave it on a new workspace, and SHALL never replay an earlier seed's write onto the renamed workflow.

#### Scenario: A workflow renamed to a seeded name is kept by the seed
- **GIVEN** a workspace seeded before "Monthly FX note" was seeded, whose "Monthly FX and inflation note" the owner renames "Monthly FX note"
- **WHEN** the concept seed runs again
- **THEN** the workspace holds one "Monthly FX note", the renamed workflow with its id and versions unchanged, and the seed adds nothing for that name

#### Scenario: A seeded workflow renamed away keeps its new name
- **GIVEN** a workspace where the concept seed ran, whose published "Weekly competitor brief" and draft "Interview synthesis" the owner renames
- **WHEN** the concept seed runs again
- **THEN** each renamed workflow keeps its new name, versions, hashes and draft, and the seed adds a published "Weekly competitor brief" and a draft "Interview synthesis" beside them
