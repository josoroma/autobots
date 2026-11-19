# Spec Delta

## Purpose
A workspace setting, "Let browsing type and submit (YOLO)", that lets a `browse_goal` call start without approval, within the browse domains the owner lists on each Expert (Decision 0035 Y1 to Y4, Y13 and Y15).

## ADDED Requirements

### Requirement: The setting is on by default

Every workspace SHALL read the YOLO setting as on until its owner turns it off, and Settings → Browsing SHALL show it as a checkbox with one line saying what it allows.

#### Scenario: On by default
- **GIVEN** a new workspace
- **WHEN** the owner opens Settings → Browsing
- **THEN** "Let browsing type and submit (YOLO)" is checked, with one line saying what it allows

### Requirement: Existing workspaces get it on, with a notice once

A workspace that existed before the setting shipped SHALL read it as on, and Home SHALL show its owner a notice saying so, once.

#### Scenario: Existing workspaces get it on, with a notice once
- **GIVEN** a workspace that existed before the setting shipped
- **WHEN** its owner opens Home after the change, and again later
- **THEN** the setting is on, and Home shows a notice saying so the first time only

### Requirement: A YOLO call starts without approval

A `browse_goal` call SHALL start without waiting for approval while it is YOLO: the run's frozen setting and the workspace's current setting are both on. Its tool row SHALL record `typing: on` beside its domains.

#### Scenario: No approval while it is on
- **GIVEN** the checkbox is on when a run is admitted, and an Expert whose browse domains include every domain its call names
- **WHEN** the Expert's browse_goal call is made
- **THEN** it starts without waiting for approval, and the tool row shows typing on and its domains

### Requirement: A YOLO call's domains come from its Expert

Under YOLO, a `browse_goal` call SHALL be refused before any container starts:
- when a domain it names isn't inside its Expert's browse domains;
- when its Expert lists no browse domains, with a reason that names the missing list.

#### Scenario: The domains come from the Expert
- **GIVEN** the checkbox is on, and an Expert whose grant allows browsing google.com and gstatic.com
- **WHEN** its browse_goal call names any other domain
- **THEN** the call is refused before any container starts

#### Scenario: An Expert with no domains can't browse
- **GIVEN** the checkbox is on, and an Expert that grants browse_goal with no domains listed
- **WHEN** its browse_goal call is made
- **THEN** the call is refused before any container starts, with a reason that names the missing list

### Requirement: The owner keeps each Expert's browse domains

An Expert that grants `browse_goal` SHALL carry a browse domain list, edited in the Expert editor. A change to it SHALL make a new Expert version and leave earlier versions unchanged.

#### Scenario: The owner lists an Expert's browse domains
- **GIVEN** an Expert that grants browse_goal
- **WHEN** the owner adds en.wikivoyage.org to its browse domains in the Expert editor and saves
- **THEN** a new Expert version holds the list, and the earlier version is unchanged

### Requirement: Turning it off applies at once, turning it on to new runs

The setting SHALL be frozen at a run's admission. Turning it off SHALL apply at the next `browse_goal` call of any run. Turning it on SHALL apply only to runs admitted afterwards.

#### Scenario: Turning it off is immediate
- **GIVEN** a run admitted with the checkbox on
- **WHEN** the owner unchecks it and the run makes another browse_goal call
- **THEN** that call waits for approval and runs read-only on Autobots' own loop

#### Scenario: Turning it on applies to new runs
- **GIVEN** a run admitted with the checkbox off
- **WHEN** the owner checks it, the run makes another browse_goal call, and a new run is admitted and makes one
- **THEN** the first run's call waits for approval, and the new run's call starts without approval

### Requirement: Only the owner changes it

Only the workspace owner SHALL change the setting. Any other member's change SHALL be refused, leaving it unchanged.

#### Scenario: Only the owner changes it
- **GIVEN** a signed-in workspace member who isn't the owner
- **WHEN** they try to change the checkbox
- **THEN** the request is refused and the setting is unchanged
