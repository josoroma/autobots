# visual-evidence Specification

## Purpose
TBD - created by archiving change us-11-11-design-system-migration-final. Update Purpose after archive.

## Requirements

### Requirement: Forms use shared components

Each form control SHALL come from the shared components and use the input, border and ring tokens with visible keyboard focus.

#### Scenario: Move forms to shared components
- **GIVEN** the web app's forms
- **WHEN** each is checked after the migration
- **THEN** its controls come from the shared components and use the input, border and ring tokens with visible keyboard focus

### Requirement: Every named surface is captured once

Every DS-03 surface in use SHALL have, in dark and light, a retained screenshot, contrast measured in its actual states and an axe result, with the revision they came from.

#### Scenario: Capture every named surface once
- **GIVEN** the screens are final
- **WHEN** every DS-03 surface in use, including sign-in and key setup, is captured in dark and light
- **THEN** each has a retained screenshot, contrast measured in its actual states and an axe result, under docs/engineering/evidence/US-11.11/ with the revision they came from

### Requirement: Failures and absences are reported

A failure or an absent surface SHALL be recorded, the pairing, focus, label or structure corrected first, and any token change recorded as a proposal.

#### Scenario: Report what fails or is missing
- **GIVEN** a surface fails contrast or axe, or a named surface doesn't exist
- **WHEN** the evidence is reviewed
- **THEN** the failure or absence is recorded, the pairing, focus, label or structure is corrected first, and any token change is a recorded proposal rather than a silent substitution
