## MODIFIED Requirements

### Requirement: Preserved appearance choice
An explicit System, Light or Dark selection SHALL apply before paint across navigation and reload, with no model request or durable run-state mutation. System SHALL follow the operating system only once chosen, including when the operating system switches while the page is open. A missing, invalid or unreadable saved value SHALL render dark without crashing.

#### Scenario: Preserve an explicit appearance choice
- **GIVEN** the user explicitly selects light or dark mode
- **WHEN** the user navigates and reloads the app
- **THEN** the saved choice applies before paint and no model request or durable run-state mutation occurs

#### Scenario: System follows the OS only once chosen
- **GIVEN** a fresh browser whose OS prefers light
- **WHEN** the app loads, the person picks System, the OS switches to dark, and the page reloads
- **THEN** the first load renders dark, choosing System renders light, the switch renders dark, and the reload restores System before paint

#### Scenario: Invalid or unavailable storage falls back to dark
- **GIVEN** an invalid stored theme value, or browser storage that can't be written
- **WHEN** the app loads
- **THEN** it renders dark without crashing

## ADDED Requirements

### Requirement: Presentation preferences in this browser
Settings → Appearance SHALL offer:
- serif for documents, on by default;
- Comfortable or Compact density;
- reduced motion that follows the OS and can be forced on.

Each choice SHALL be stored in the browser, applied before paint, and changes presentation only.

#### Scenario: Presentation preferences
- **GIVEN** Settings → Appearance in a fresh browser, with serif documents on
- **WHEN** the person turns serif documents off, picks Compact density, forces reduced motion on and reloads
- **THEN** documents use the non-serif stack, spacing is compact, motion stops even though the OS allows it, each choice survives the reload, and with nothing forced, motion follows the OS

#### Scenario: Presentation only
- **GIVEN** a running run and a pending approval
- **WHEN** the person changes every appearance preference
- **THEN** no model or task request is issued, and no run, approval or workflow state changes
