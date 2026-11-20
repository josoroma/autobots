## ADDED Requirements

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
