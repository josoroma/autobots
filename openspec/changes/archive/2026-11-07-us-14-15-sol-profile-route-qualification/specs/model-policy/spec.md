## ADDED Requirements

### Requirement: Sol is refused until its route is qualified

Sol SHALL be an approved profile that new work can't choose until its route is qualified: a new run, workspace default, role override or Expert binding naming it SHALL be refused `model_not_offered` with a reason naming Sol, with no substitute and nothing stored changed, and Settings SHALL list it as approved and not offered.

#### Scenario: Approved, and refused for new runs until qualified
- **GIVEN** Sol in the registry with no stored qualification of its route
- **WHEN** a new run, the workspace default, a role override or an Expert's role binding names it
- **THEN** it is refused with model_not_offered and a reason saying Sol isn't offered for new runs until its route is qualified, no run starts, no other model is substituted and nothing stored changes, no picker lists it, and Settings lists it as approved and says it isn't offered

### Requirement: Sol's route is qualified live within its cap

Sol's route SHALL be qualified with US-3.4's runner and suite within US$1.20 counted at worst case, with no retry and no other model, and its result SHALL be stored and shown in Settings.

#### Scenario: Qualify the route live within its cap
- **GIVEN** an authorized live qualification of Sol's route with US-3.4's runner and suite and a cap of US$1.20
- **WHEN** the suite runs
- **THEN** each call is counted at its worst case before it is sent, no call is sent that wouldn't fit in what's left of the cap, no call is retried and no other model is tried, the route's actual results and reported usage are stored as Sol's qualification apart from mocks with unsupported capabilities left disabled, and Settings shows that qualification with its date, configuration and limits

### Requirement: Researcher defaults to Sol once offered

Once Sol is offered, a run with no model choice SHALL freeze `researcher` on Sol and every other role on Terra, and any explicit choice SHALL win over that default.

#### Scenario: Offered once qualified, with researcher on Sol by default
- **GIVEN** Sol's route qualified and a workspace with no saved model policy
- **WHEN** a run is admitted with no model choice, a run naming Sol is admitted, and runs are admitted with a run role override, a run-wide profile, a workspace role override or a workspace default, each naming Terra for researcher
- **THEN** the first freezes researcher on Sol and every other role on Terra, the second is admitted, Sol is listed in the pickers, and each of the others freezes researcher on Terra

### Requirement: Frozen runs keep Sol

A run frozen on Sol SHALL keep it on resume and in its children, and SHALL stop rather than move to another model if Sol is removed or repointed.

#### Scenario: Frozen runs keep Sol, and removing it stops them
- **GIVEN** a run admitted with researcher frozen on Sol
- **WHEN** it resumes or a child is admitted under its frozen policy, and then when Sol is removed from the approved set by migration on a disposable stack and the run resumes
- **THEN** it keeps its frozen route in the first case, and in the second it stops with no call sent, no other model is put in its place and its saved policy isn't rewritten
