## ADDED Requirements

### Requirement: A search palette over the workspace

One endpoint SHALL search the workspace's runs by goal, and its Experts, workflows and tools by name, returning typed results limited to the workspace. ⌘K SHALL open the palette unless focus is in a text field, and so SHALL a Search button placed after the skip link with its visible key hint. The palette SHALL be a dialog with a listbox, with arrow-key movement whose active option is announced, Enter to open a result, and Escape to close and return focus to where it was.

#### Scenario: Typed results within the workspace
- **GIVEN** runs, Experts, workflows and tools in this workspace, and runs and Experts in another workspace
- **WHEN** a member searches for a term that matches a run's goal and the names of an Expert, a workflow and a tool
- **THEN** one endpoint returns typed results of each kind from this workspace only, and nothing from the other workspace

#### Scenario: ⌘K and the shell button
- **GIVEN** focus outside any text field, on a screen where the skip link is the first tab stop
- **WHEN** the member presses ⌘K, and separately activates the Search button placed after the skip link with its visible key hint
- **THEN** each opens the palette as a dialog with a listbox, and with focus in a text field ⌘K does nothing

#### Scenario: Keyboard and focus
- **GIVEN** the open palette with results
- **WHEN** the member moves with the arrow keys, opens a result with Enter, then reopens the palette and closes it with Escape
- **THEN** the active option is announced, Enter navigates to that result, and Escape returns focus to where it was before the palette opened
