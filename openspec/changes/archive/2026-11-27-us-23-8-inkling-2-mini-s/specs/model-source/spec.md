# Spec Delta

## Purpose

The Local source offers both qualified local profiles, either as the Local default, with one answering every role (Decision 0041 A1, A8; US-23.8).

## ADDED Requirements

### Requirement: The Local source offers every qualified local profile
The Local source SHALL offer each local profile whose stored qualification is `qualified_with_limits`, each with its own date and limits, and either SHALL be choosable as the Local default, which answers every role.

#### Scenario: The Local source offers both local profiles
- **GIVEN** Bonsai 2.5's stored qualification from migration 70 and Inkling 2 Mini's from the new migration, each qualified_with_limits
- **WHEN** the profiles offered on the Local source are read, and the owner opens Settings → Models
- **THEN** Bonsai 2.5 and Inkling 2 Mini are each offered with their own qualification's date and limits, Inkling 2 Mini's listing schema_nested, and the Model source panel shows each as offered

#### Scenario: Either can be the Local default, and it answers every role
- **GIVEN** Bonsai 2.5 and Inkling 2 Mini offered, and a workspace on OpenRouter with an Expert that grants browse_goal
- **WHEN** the owner switches Model source to Local with Inkling 2 Mini as the Local default and a run is admitted, then saves Bonsai 2.5 as the Local default and another run is admitted
- **THEN** the switch is accepted, every role of the first run resolves to Inkling 2 Mini's profile with its route's 8,192 output tokens, every role of the second resolves to Bonsai 2.5's with 4,096, saving a workspace role override is refused, and a run that names a role override is refused model_not_offered

#### Scenario: Neither is offered on OpenRouter
- **GIVEN** Bonsai 2.5 and Inkling 2 Mini offered on the Local source, in a workspace on OpenRouter
- **WHEN** a new run, the workspace default, a role override or an Expert's role binding names either
- **THEN** it is refused model_not_offered, no run starts, no other model is substituted, nothing stored changes, and no picker lists either
