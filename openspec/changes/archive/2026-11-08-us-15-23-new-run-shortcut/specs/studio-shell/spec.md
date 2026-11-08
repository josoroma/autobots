## ADDED Requirements

### Requirement: A New run shortcut in the shell

A New run button with the visible hint ⇧⌘O SHALL follow the skip link, which stays the first tab stop. The button and ⇧⌘O SHALL open Home's composer with focus in the goal, sending nothing. With focus in a text field, ⇧⌘O SHALL do nothing, and the field SHALL keep its content and focus.

#### Scenario: New run from the shell
- **GIVEN** any screen, with the skip link as the first tab stop
- **WHEN** the person activates the New run button that follows it and shows its key hint
- **THEN** Home's composer opens with focus in the goal, and nothing is sent

#### Scenario: Not in a text field
- **GIVEN** focus in a text field
- **WHEN** the person presses the New run shortcut
- **THEN** the app takes no action and the field keeps its content and focus

#### Scenario: The shortcut is shift-command-O
- **GIVEN** focus outside a text field
- **WHEN** the person presses ⇧⌘O
- **THEN** Home's composer opens with focus in the goal, and the button's hint reads ⇧⌘O
