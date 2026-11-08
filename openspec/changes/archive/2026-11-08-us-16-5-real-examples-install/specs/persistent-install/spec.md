## ADDED Requirements

### Requirement: Real examples on the install

A guarded, paid command SHALL put the concept Experts and workflows, two real goal runs and one real workflow execution into the install's owner workspace, under a reservation from the shared ledger that it never exceeds. It SHALL keep what the owner already had, leave the workflow's approval pending, and leave no key in stored rows or logs.

#### Scenario: Experts and workflows
- **GIVEN** the install's owner workspace
- **WHEN** the concept seed runs
- **THEN** the Experts and workflows of SD-02 are there, and what the owner already had is unchanged

#### Scenario: Real runs under a cap
- **GIVEN** US$0.45 reserved from the shared ledger
- **WHEN** two goal runs limited to US$0.10 each and one workflow execution limited to US$0.25 run live
- **THEN** the runs end with their real outcome and artifacts, the spend stays within the reservation, and no key appears in stored rows or logs

#### Scenario: A pending approval
- **GIVEN** the workflow execution reaching its approval gate
- **WHEN** the owner opens Approvals
- **THEN** the request is waiting, with its requester, run and exact fields
