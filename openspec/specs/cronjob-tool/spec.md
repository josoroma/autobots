# cronjob-tool Specification

## Purpose
TBD - created by archiving change us-14-19-cronjob-tool-manages-workspace. Update Purpose after archive.

## Requirements

### Requirement: The catalog lists cronjob under Automation

The cronjob tool SHALL behave so that cronjob v1 appears exactly once, in the group Automation described as "Scheduled tasks that start goals and workflows", with provider autobots, operation class reversible_internal_write, cost class free_local, no network, approval by_action and grantable only to an Expert.

#### Scenario: The catalog lists cronjob under Automation
- **GIVEN** a disposable stack and a workspace member
- **WHEN** the member reads the catalog and filters it by the Automation group
- **THEN** cronjob v1 appears exactly once, in the group Automation described as "Scheduled tasks that start goals and workflows", with provider autobots, operation class reversible_internal_write, cost class free_local, no network, approval by_action and grantable only to an Expert

### Requirement: list runs without approval and stays in the run's workspace

The cronjob tool SHALL behave so that it returns the first workspace's routines, no approval request is created, and the other workspace's routine isn't listed.

#### Scenario: list runs without approval and stays in the run's workspace
- **GIVEN** a disposable database, a workspace with two routines, another workspace with one routine, and a run in the first workspace whose Expert grants cronjob, dispatched through the gateway with no model
- **WHEN** the run calls cronjob with the action list
- **THEN** it returns the first workspace's routines, no approval request is created, and the other workspace's routine isn't listed

### Requirement: Every other action waits for a person's approval

The cronjob tool SHALL behave so that each call creates an approval request bound to its arguments that shows the action, the routine and its schedule, no routine changes and no occurrence is admitted before approval, the rejected call changes nothing, and the approval doesn't authorize the call with different arguments.

#### Scenario: Every other action waits for a person's approval
- **GIVEN** the same run and an existing routine in its workspace
- **WHEN** it calls cronjob with each of create, update, pause, resume, run and remove, one call is rejected, and an approval granted for one call is presented for a call with different arguments
- **THEN** each call creates an approval request bound to its arguments that shows the action, the routine and its schedule, no routine changes and no occurrence is admitted before approval, the rejected call changes nothing, and the approval doesn't authorize the call with different arguments

### Requirement: create and update follow the routine service's validation

The cronjob tool SHALL behave so that each invalid call is refused with the routine service's typed code and saves nothing, the valid create saves a routine whose creator is the run's starter, and the valid update saves a new routine version.

#### Scenario: create and update follow the routine service's validation
- **GIVEN** approved cronjob calls in a run of the first workspace, a target Expert in that workspace, and one in the other workspace
- **WHEN** create names the other workspace's target, grants tools beyond its target's, or sets an invalid trigger or timezone, update sends a stale expected_version, and then a valid create and a valid update are approved
- **THEN** each invalid call is refused with the routine service's typed code and saves nothing, the valid create saves a routine whose creator is the run's starter, and the valid update saves a new routine version

### Requirement: pause and resume set enabled

The cronjob tool SHALL behave so that pause sets enabled to false, run is refused routine_paused and admits nothing, and resume sets enabled to true.

#### Scenario: pause and resume set enabled
- **GIVEN** an enabled routine
- **WHEN** an approved pause is applied, an approved run of the paused routine is attempted, and then an approved resume is applied
- **THEN** pause sets enabled to false, run is refused routine_paused and admits nothing, and resume sets enabled to true

### Requirement: run admits one occurrence now, by the scheduled path's rules

The cronjob tool SHALL behave so that the first admits exactly one occurrence through the same admission as a scheduled one and returns its run_id, the second is skipped for overlap and says so, the third is blocked and says why, and no model call is made.

#### Scenario: run admits one occurrence now, by the scheduled path's rules
- **GIVEN** a disposable database, a routine with no active run, a routine whose earlier run is still active, and a routine whose workspace has no usable key
- **WHEN** an approved cronjob run is applied to each
- **THEN** the first admits exactly one occurrence through the same admission as a scheduled one and returns its run_id, the second is skipped for overlap and says so, the third is blocked and says why, and no model call is made

### Requirement: remove marks a routine removed and keeps its history

The cronjob tool SHALL behave so that the routine has removed_at set and enabled false, it appears in neither list, no occurrence is admitted for it, the other action is refused routine_not_found, its versions and occurrences remain, and the new routine with the same name is saved.

#### Scenario: remove marks a routine removed and keeps its history
- **GIVEN** a routine with versions and occurrences on a disposable database migrated through migration 53
- **WHEN** an approved remove is applied, the routines are then listed through cronjob and through the routine service, routines are evaluated, another action names the removed routine, and an approved create reuses its name
- **THEN** the routine has removed_at set and enabled false, it appears in neither list, no occurrence is admitted for it, the other action is refused routine_not_found, its versions and occurrences remain, and the new routine with the same name is saved

### Requirement: Granted only through an Expert

The cronjob tool SHALL behave so that the first is refused expert_grant_required before any approval request or routine change, and the Expert's call proceeds to its action's rule.

#### Scenario: Granted only through an Expert
- **GIVEN** a run with no Expert behind it that names cronjob, and a run whose Expert grants cronjob
- **WHEN** each proposes a cronjob call
- **THEN** the first is refused expert_grant_required before any approval request or routine change, and the Expert's call proceeds to its action's rule

### Requirement: Only public fields reach the tool-use record

The cronjob tool SHALL behave so that each tool use shows only action, routine_id and name as inputs and the outcome's routine_id, status and run_id as outputs, and the fake goal text and inputs appear in none of them.

#### Scenario: Only public fields reach the tool-use record
- **GIVEN** approved cronjob create and update calls whose goal text and inputs hold distinctive fake strings, and a list call
- **WHEN** their tool-use rows, tool.use events and the tool-use listing are read
- **THEN** each tool use shows only action, routine_id and name as inputs and the outcome's routine_id, status and run_id as outputs, and the fake goal text and inputs appear in none of them
