# tool-switches Specification

## Purpose
Per-workspace on/off switches for tools and tool groups on the Tools page, so an owner can turn a provider's tools off at once or one at a time (Decision 0033 W1 to W5).

## Requirements

### Requirement: Every switchable tool and group shows its switch

Every Expert-grantable tool, and every group that holds one, SHALL carry a switch, on at version 0 until changed. The plan, delegation and workflow approval tools, and a group that holds only them, SHALL carry none.

#### Scenario: Every switchable tool and group shows its switch
- **GIVEN** a disposable stack and a workspace member
- **WHEN** the member reads GET /v1/tools
- **THEN** every Expert-grantable tool and every group that holds one carries a switch that is on at version 0, and the plan, delegation and workflow approval tools, and the groups that hold only them, carry none

### Requirement: Turning a tool off makes it unavailable in that workspace only

A tool turned off SHALL read `disabled_by_policy` with reason `turned_off` in its workspace only, with a repair saying to turn it on in Tools.

#### Scenario: Turning a tool off makes it unavailable in that workspace only
- **GIVEN** an owner of one workspace and a second workspace
- **WHEN** the owner turns google_crawl off and the catalog is read in both workspaces
- **THEN** google_crawl is disabled_by_policy with reason turned_off in the first workspace, its repair says to turn it on in Tools, and it is unchanged in the second

### Requirement: Turning a group off turns off its tools

A tool SHALL be on only while its own switch and its group's are on. While its group is off, it SHALL read `disabled_by_policy` with reason `group_turned_off`.

#### Scenario: Turning a group off turns off its tools
- **GIVEN** the google group with all four tools on
- **WHEN** the owner turns the group off, turns google_search on individually, and then turns the group back on
- **THEN** while the group is off all four read disabled_by_policy with reason group_turned_off, google_search stays off despite its own switch, and turning the group on makes all four available again

### Requirement: Admission and Expert saves refuse a tool that is off

A run or routine granting a tool that is off SHALL be refused `tool_unavailable`, and an Expert granting one SHALL be refused `expert_tool_unavailable`, before anything is created.

#### Scenario: Admission and Expert saves refuse a tool that is off
- **GIVEN** google_search turned off in a workspace
- **WHEN** a run that grants it is admitted and an Expert that grants it is saved
- **THEN** the run is refused tool_unavailable and the Expert expert_tool_unavailable, and nothing is created

### Requirement: A run in progress can't call a tool that is turned off

The gateway SHALL refuse each call to a tool that is off with `tool_turned_off`, before any request, and admit the next call once it is on.

#### Scenario: A run in progress can't call a tool that is turned off
- **GIVEN** a disposable database, a running run whose scope grants google_search, and a fake SerpApi transport
- **WHEN** google_search is turned off, the run calls it, google_search is turned back on, and the run calls it again
- **THEN** the first call is refused tool_turned_off before any request, and the second succeeds

### Requirement: Only the owner changes a switch, at its version

Only the workspace owner SHALL change a switch, with its expected version. A stale version SHALL be refused `stale_version`, and a member's change SHALL be refused, changing nothing.

#### Scenario: Only the owner changes a switch, at its version
- **GIVEN** an owner and a member of a workspace
- **WHEN** the member turns a tool off, the owner sends a stale version, and then the owner sends the current version
- **THEN** the member is refused and nothing changes, the stale change is refused stale_version, and the owner's change is saved with the next version

### Requirement: Migration 64 adds the private switch table

Migration 64 SHALL add `app_private.tool_switches` with no anon or authenticated access, readable and writable by the runtime role. Readiness SHALL ship 64 migrations.

#### Scenario: Migration 64 adds the private switch table
- **GIVEN** a disposable database migrated through migration 63
- **WHEN** migration 64 is applied
- **THEN** app_private.tool_switches exists with no anon or authenticated access, the runtime role can read, insert and update it, readiness ships 64 migrations, and the schema snapshot matches

### Requirement: The Tools page switches

The Tools page SHALL show the owner an accessible on/off switch on each switchable tool and group, with each state in words. A member SHALL see each state without a switch to change, and the page SHALL pass axe in both themes.

#### Scenario: The Tools page switches
- **GIVEN** an owner and a member signed in on the Tools page of a disposable stack
- **WHEN** the owner turns the Google group off and back on with the keyboard, and the member opens the page
- **THEN** each switchable tool and group shows an on or off switch with its state in words, the four Google tools read off while the group is off, the member sees each state but no switch they can change, and axe reports no violations in either theme
