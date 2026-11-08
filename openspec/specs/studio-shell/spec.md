# studio-shell Specification

## Purpose
TBD - created by archiving change us-15-1-sidebar-groups-tools-under. Update Purpose after archive.

## Requirements

### Requirement: The sidebar groups the sections

The sidebar SHALL list its links in three groups, each named in text: the work group (Home, Runs, Approvals), **Build** (Experts, Workflows, Tools) and **System** (Operations, Models, Settings). The current page SHALL be marked by more than color. The skip link SHALL stay the first tab stop and move focus to the main content.

#### Scenario: Three named groups
- **GIVEN** a signed-in workspace member on any screen
- **WHEN** the sidebar renders
- **THEN** its links read, in order, Home, Runs and Approvals in the work group, Experts, Workflows and Tools under Build, and Operations, Models and Settings under System, each group is named in text, and the current page is marked by more than color

#### Scenario: The skip link stays first
- **GIVEN** a fresh load of any screen
- **WHEN** the person presses Tab once
- **THEN** the skip link has focus, and activating it moves focus to the main content

### Requirement: Home greets the member and shows what needs them and recent runs

Home SHALL greet the member by the workspace's timezone, with "Good morning" from 05:00 to 11:59, "Good afternoon" from 12:00 to 17:59 and "Good evening" from 18:00 to 04:59, followed by the display name and the heading "What should we work on?". Needs you SHALL list pending approvals, linking to their Review, and runs waiting for input, linking to Reply on the run, and SHALL NOT list paused runs. Recent runs SHALL list the five newest runs with state, progress or spend, and relative time.

#### Scenario: Greeting by the workspace's timezone
- **GIVEN** a workspace whose timezone is America/Costa_Rica and a member whose display name is Ada
- **WHEN** Home loads at 09:00, 14:00 and 20:00 local time
- **THEN** it reads "Good morning", "Good afternoon" and "Good evening" in turn, each followed by "Ada", and then the heading "What should we work on?"

#### Scenario: Needs you
- **GIVEN** a pending approval, a run in waiting_input and a paused run
- **WHEN** Home loads
- **THEN** Needs you lists the approval with a link to its Review and the waiting run with a link to Reply on the run, and doesn't list the paused run

#### Scenario: Recent runs
- **GIVEN** seven runs in the workspace
- **WHEN** Home loads
- **THEN** Recent runs lists the five newest, each with its state, its progress or spend, and a relative time

#### Scenario: Greeting boundaries
- **GIVEN** the workspace timezone and local times 04:59, 05:00, 11:59, 12:00, 17:59 and 18:00
- **WHEN** Home renders at each time
- **THEN** it reads evening, morning, morning, afternoon, afternoon and evening

### Requirement: Settings sections, notifications, data and keyboard

Settings SHALL list Appearance, Notifications, Account, Data on this Mac and Keyboard, and link to Models and Operations.
- **Notifications:** while the app is open, with "Tell me when a run waits for me" on and the browser's permission, the app SHALL show a browser notification for each run that enters `waiting_approval` or `waiting_input`, sending nothing off the Mac. With the permission denied or the setting off it SHALL show none.
- **Data on this Mac:** SHALL show the retention summary read-only to any member, with a link to Operations for the owner only.
- **Keyboard:** SHALL list each shortcut the app offers, with its keys and what it does.

#### Scenario: Sub-navigation
- **GIVEN** a member signed in
- **WHEN** they open Settings
- **THEN** the sub-navigation lists Appearance, Notifications, Account, Data on this Mac and Keyboard, and links to Models and Operations

#### Scenario: Notify while the app is open
- **GIVEN** "Tell me when a run waits for me" turned on and the browser's permission granted
- **WHEN** one run enters waiting_approval and another enters waiting_input while the app is open
- **THEN** the browser shows a notification for each, nothing is sent off the Mac, and with the permission denied or the setting off none is shown

#### Scenario: Data on this Mac
- **GIVEN** a member who isn't the owner, and the owner
- **WHEN** each opens Data on this Mac
- **THEN** both read the retention summary with no way to change it, and only the owner sees the link to Operations

#### Scenario: Keyboard
- **GIVEN** Settings → Keyboard
- **WHEN** it opens
- **THEN** it lists each shortcut the app offers, with its keys and what it does

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
