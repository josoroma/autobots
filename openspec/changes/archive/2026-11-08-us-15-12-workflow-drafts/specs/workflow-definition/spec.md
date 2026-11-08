## ADDED Requirements

### Requirement: A workflow holds one saved draft that only published versions outrank

A workflow SHALL hold at most one saved draft graph, which only an owner can save, publish or discard. Publishing it SHALL validate it and create the next immutable version under the expected version, refusing a stale one and creating nothing. Discarding it SHALL leave every published version and hash unchanged. Runs and routines SHALL bind published versions only, refusing a draft with a typed code.

#### Scenario: One saved draft
- **GIVEN** a published workflow in a workspace
- **WHEN** the owner saves a draft graph twice and a member who isn't the owner tries to save one
- **THEN** the workflow holds one draft with the owner's second graph, and the member's save is refused with a typed code

#### Scenario: Publish from the draft
- **GIVEN** a draft beside published version 3
- **WHEN** the owner publishes it with expected version 3, and another publish names expected version 2
- **THEN** the first validates the draft and creates immutable version 4, and the second is refused as stale and creates nothing

#### Scenario: Discard leaves published versions alone
- **GIVEN** a draft beside published versions
- **WHEN** the owner discards the draft
- **THEN** the draft is gone, and every published version and its hash is unchanged

#### Scenario: Runs bind only published versions
- **GIVEN** a workflow with a draft
- **WHEN** a run or a routine names the draft, and an execution names a published version
- **THEN** the first two are refused with a typed code, and the execution binds the published version's hash
