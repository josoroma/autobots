## ADDED Requirements

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
