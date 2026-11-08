## ADDED Requirements

### Requirement: Sober control borders

Input, Textarea and Select SHALL draw one even border on all four sides, with no inset underline, in a token that reaches 3:1 against the surrounding surface in both themes. The composer's goal field SHALL use the same rounded border, and the composer and sign-in cards SHALL have no drop shadow. Keyboard focus SHALL stay visible.

#### Scenario: One even border and no underline
- **GIVEN** any Input, Textarea or Select in either theme
- **WHEN** it is shown without keyboard focus
- **THEN** it has no inset bottom line, and its border is the same width and color on all four sides

#### Scenario: The composer's goal field matches
- **GIVEN** Home's composer
- **WHEN** it is shown
- **THEN** the goal field has the same rounded, even border as the other controls, and the composer card, like the sign-in card, has no drop shadow, as other cards don't

#### Scenario: Still accessible
- **GIVEN** every screen the visual walk covers, in dark and light
- **WHEN** control boundaries and focus are measured
- **THEN** each control's border reaches 3:1 against what is around it, and keyboard focus stays visible
