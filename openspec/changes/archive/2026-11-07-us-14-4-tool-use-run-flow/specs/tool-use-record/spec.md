## ADDED Requirements

### Requirement: The run workspace shows tools used

The run workspace SHALL list a run's tool uses once each, in order, with time and duration, tool and group, the plan task's title, public inputs, public outputs or a size, and outcome. New uses SHALL appear live and SHALL be announced politely, and a reload SHALL show the same list. The list SHALL keep heading and table semantics.

#### Scenario: Live and reloaded tool use
- **GIVEN** a running run that calls tools
- **WHEN** the owner watches its workspace, then reloads it
- **THEN** Tools used shows each use once, in order, with time and duration, tool and group, the plan task's title, public inputs, outputs or digests, and outcome

#### Scenario: Accessible list
- **GIVEN** the Tools used list is open
- **WHEN** a new use arrives
- **THEN** it is announced politely, the list keeps heading and table semantics, and axe reports no violations

### Requirement: The workflow monitor shows tool uses by node

The workflow monitor SHALL show each tool use under the node instance that made it.

#### Scenario: Flow view
- **GIVEN** a workflow execution whose nodes call tools
- **WHEN** the workflow monitor is opened
- **THEN** each tool use appears under the run of the node that made it
