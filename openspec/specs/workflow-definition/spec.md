# workflow-definition Specification

## Purpose
TBD - created by archiving change us-6-1-typed-immutable-workflow-definition. Update Purpose after archive.

## Requirements

### Requirement: Validation before publication
When publication is requested for a proposal using the documented input, output, transform, condition, foreach, join, read, artifact, approval and agent subset, types, links, iteration bounds and versions SHALL validate, or typed errors SHALL be returned, before an immutable version is published.

#### Scenario: Validate before publication
- **GIVEN** a proposal using the documented input/output/transform/condition/foreach/join/read/artifact/approval/agent subset
- **WHEN** publication is requested
- **THEN** types, links, iteration bounds and versions validate or typed errors are returned before an immutable version is published

### Requirement: Exact execution bindings
When a run is created from a published workflow or model-generated proposal, it SHALL reference the exact validated graph and block versions, and unsupported arbitrary cycles MUST be rejected.

#### Scenario: Preserve exact execution bindings
- **GIVEN** a published workflow or model-generated proposal
- **WHEN** a run is created
- **THEN** it references the exact validated graph/block versions and unsupported arbitrary cycles are rejected

### Requirement: Workflows have an optional description and nodes an optional label at a new IR version

A workflow SHALL have an optional description. Graph nodes SHALL accept an optional `label`, and a graph carrying labels SHALL be stored at IR version 2. A graph at the previous IR version, with no labels, SHALL still validate, publish and run, stored and hashed exactly as before, and versions published before the change SHALL bind with the same version and hash.

#### Scenario: Optional description
- **GIVEN** one workflow saved with a description and another saved without one
- **WHEN** both are read through the BFF
- **THEN** the first returns its description, the second returns none, and both stay valid

#### Scenario: Labels bump the IR version
- **GIVEN** a graph whose nodes carry optional labels, and a graph at the previous IR version with no labels
- **WHEN** each is validated and published
- **THEN** the first is stored at the new IR version with its labels, and the second still validates, publishes and runs unchanged

#### Scenario: Versions published before the change are untouched
- **GIVEN** a version published before the migration
- **WHEN** a run binds it after the migration
- **THEN** the run references the same version and hash as before

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

### Requirement: A workflow's owner can rename it, changing only its name

The workspace owner SHALL be able to rename a workflow, and a member who isn't the owner SHALL be refused with `owner_required` (Decision 0037 N1). A name SHALL follow creation's rule: 1 to 100 characters, unique within the workspace. A name another workflow of the workspace holds SHALL be refused with `workflow_name_taken`, including when two renames race for one name, and a refused rename SHALL change nothing. Renaming a workflow to its own name SHALL succeed and change nothing (N2, N5). A rename SHALL change no version, graph, hash, draft, description or execution, and executions and routines SHALL keep binding the workflow by its id and version (N3). Everything that shows a workflow SHALL show its current name. A run's goal SHALL keep the name its execution started under, and a search of the runs list SHALL still find the run by that name (N4). The editor SHALL trim the name it sends and SHALL send no blank name.

#### Scenario: The owner renames a workflow and only its name changes
- **GIVEN** a published workflow with a saved draft and a description, whose agent step names an Expert that grants a tool
- **WHEN** the owner renames it through the BFF
- **THEN** the reply is the workflow's view with the new name, its id, versions, graph hashes, draft and description are unchanged, and the workflow list, the workflow's read and the tool's Granted to give the new name

#### Scenario: A name another workflow holds is refused
- **GIVEN** two workflows in one workspace
- **WHEN** the owner renames the first to the second's name, and then to its own name
- **THEN** the first rename is refused with workflow_name_taken and nothing changes, and the second succeeds and changes nothing

#### Scenario: Two renames race for one name
- **GIVEN** two workflows in one workspace, and a name neither holds
- **WHEN** the owner renames both to that name at once
- **THEN** one rename succeeds, the other is refused with workflow_name_taken, and the refused workflow keeps its name

#### Scenario: The name follows creation's rule
- **GIVEN** a workflow
- **WHEN** the owner renames it to an empty name, and then to a name of 101 characters
- **THEN** each is refused as an invalid request, and the name is unchanged

#### Scenario: Only the owner renames
- **GIVEN** a workflow, and a member of its workspace who isn't the owner
- **WHEN** the member reads the workflow and then renames it
- **THEN** the read gives its name, the rename is refused with owner_required, and the name is unchanged

#### Scenario: Runs keep the name they ran under
- **GIVEN** a published workflow with an execution started before it is renamed, and a scripted model
- **WHEN** the owner renames it, and an execution of the same published version is started after
- **THEN** the earlier run's goal keeps the old name, the later run's goal names the new name, the runs list labels both runs with the new name and their version, searching the runs list for the old name finds the earlier run, and the later execution binds the same version and hash as the earlier one

#### Scenario: Executions and routines keep binding by id and version
- **GIVEN** a published workflow, a routine saved before the rename that targets its id and published version, and a scripted model
- **WHEN** the owner renames it, the published version is executed, and the routine's occurrence is admitted
- **THEN** the execution runs that version to its end, the occurrence's run binds the same version and hash, and the routine is unchanged

#### Scenario: The owner renames a workflow in the editor
- **GIVEN** the owner's editor open on a published workflow
- **WHEN** the owner types a new name with spaces around it and saves it
- **THEN** the rename sends the name trimmed, the heading shows it with the same version, and the workflows list and the workflow's preview show it

#### Scenario: The editor sends no blank name and shows a taken one's refusal
- **GIVEN** the owner's editor open on a workflow, and another workflow in the workspace
- **WHEN** the owner clears the name and saves, and then types the other workflow's name and saves
- **THEN** no rename is sent for the cleared name, and the taken name's refusal is shown while the heading and the stored name stay as they were
