## ADDED Requirements

### Requirement: A person controls a run from its page

The run page SHALL offer pause, resume and cancel according to the run's state, and show each resulting state in text that matches the API.

#### Scenario: Control a run from its page
- **GIVEN** a running run on a disposable stack with a scripted model
- **WHEN** a person pauses it, resumes it and then cancels it from the run page
- **THEN** the page shows each resulting state in text, and it matches the state the API reports

#### Scenario: Offer no control a terminal run can't take
- **GIVEN** a succeeded, failed or cancelled run
- **WHEN** the run page loads
- **THEN** it offers no pause, resume or cancel, and nothing on the page can reopen the run

### Requirement: An uncertain call is reconciled before resuming

The page SHALL show a refusal and its reason when a run with an uncertain model call is resumed, and the owner SHALL be able to record the charge seen in the provider's own records.

#### Scenario: Refuse resume until a call is reconciled
- **GIVEN** a paused run with an uncertain model call
- **WHEN** a person presses resume
- **THEN** the page shows the refusal and its reason, the run stays paused, and no model call starts

#### Scenario: Reconcile an uncertain call
- **GIVEN** a paused run with an uncertain model call
- **WHEN** the owner enters the charge seen in the provider's own records
- **THEN** that charge is recorded against the call, and resume is accepted once no uncertain call remains
