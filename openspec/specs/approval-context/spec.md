# approval-context Specification

## Purpose
TBD - created by archiving change us-11-7-approval-reason-target. Update Purpose after archive.

## Requirements

### Requirement: Each approval shows the policy's reason and its target

An approval request SHALL record the policy's reason and the resource target, and the inbox SHALL show both as text with the exact proposed action and expiry. The reason SHALL come from the server's policy, not from model output.

#### Scenario: Show the policy's reason and the target
- **GIVEN** a pending approval whose request records the policy's reason and a resource target
- **WHEN** the reviewer opens the inbox
- **THEN** both appear as text with the exact proposed action and expiry, and the reason comes from the server's policy, not from model output

### Requirement: The inbox doesn't invent what wasn't recorded

A request saved before these fields existed SHALL say which is not recorded, and any decision SHALL stay bound to the argument hash the reviewer saw.

#### Scenario: Don't invent what wasn't recorded
- **GIVEN** a pending approval saved before these fields existed
- **WHEN** the reviewer opens the inbox
- **THEN** it says which is not recorded, and any decision stays bound to the argument hash the reviewer saw

### Requirement: An approval request records its requester, scope snapshot and policy version

When a tool call needs approval, the request stored before the wait SHALL hold the requester, the scope snapshot and the policy version as immutable fields, alongside its argument hash. The requester SHALL be the person who started the run, when a person did, and the proposing agent: an Expert's ID and version, or the coordinator. The scope snapshot SHALL be the granted tools with their versions and the granted paths, and SHALL hash to the stored scope hash. The policy version SHALL name the gateway's versioned approval policy and the rule that fired. The database SHALL refuse any later change to these fields. The inbox SHALL show them as text.

#### Scenario: Record the three fields with the proposal
- **GIVEN** a tool call that needs approval
- **WHEN** its approval request is stored before the wait
- **THEN** it holds the requester, scope snapshot and policy version as immutable fields, alongside its arguments hash

### Requirement: Missing fields read as not recorded

A request saved before these fields existed SHALL show each missing field as not recorded, nothing SHALL fill them in, and any decision SHALL stay bound to the argument hash the reviewer saw.

#### Scenario: Don't invent what wasn't recorded
- **GIVEN** an approval request saved before these fields existed
- **WHEN** a reviewer opens it
- **THEN** the missing fields read as not recorded, and any decision stays bound to the argument hash the reviewer saw
