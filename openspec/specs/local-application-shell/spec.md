# local-application-shell Specification

## Purpose
TBD - created by archiving change us-2-5-native-fastapi-next-js. Update Purpose after archive.

## Requirements

### Requirement: Bounded native services
The Next.js BFF and FastAPI app factory SHALL keep lifespan-managed pools and clients server-side, and long-running work MUST NOT be owned by a browser or request.

#### Scenario: Start bounded native services
- **GIVEN** the prepared package layout and local configuration
- **WHEN** the Next.js BFF and FastAPI app factory start
- **THEN** lifespan-managed pools/clients remain server-side and long-running work is not owned by a browser or request

### Requirement: Guarded same-origin boundary
Host/Origin/CSRF and identity checks SHALL reject a forged origin, workspace or internal request without exposing privileged credentials.

#### Scenario: Guard the same-origin boundary
- **GIVEN** an authenticated local application route
- **WHEN** a forged origin, workspace or internal request is submitted
- **THEN** Host/Origin/CSRF and identity checks reject the request without exposing privileged credentials

### Requirement: Dark Luma first visit
A first visit with no valid saved appearance SHALL use the exact Luma dark tokens under either operating-system preference, without a light flash or hydration mismatch.

#### Scenario: Render Luma dark on a fresh visit
- **GIVEN** no valid saved appearance preference and either a light or dark operating-system preference
- **WHEN** the user first opens the local app
- **THEN** the first rendered interface uses the exact Luma dark tokens without a light flash or hydration mismatch

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

### Requirement: Accessible semantic styling
Shared Luma semantic tokens SHALL apply in both modes, and focus, labels, contrast and non-color state meaning SHALL satisfy DS-03 and DS-04.

#### Scenario: Share accessible semantic styling
- **GIVEN** the shell and available screens in both supported modes
- **WHEN** the user operates controls by keyboard and inspects statuses, overlays and forms
- **THEN** shared Luma semantic tokens apply and focus, labels, contrast and non-color state meaning satisfy DS-03 and DS-04

### Requirement: Retained visual evidence
First-visit, persisted-choice and representative screen evidence SHALL be retained under DS-05, and generated concepts MUST NOT count as passing runtime tests.

#### Scenario: Retain visual acceptance evidence
- **GIVEN** the implemented shell and theme behavior
- **WHEN** the browser acceptance checks run against the identified revision
- **THEN** first-visit, persisted-choice and representative screen evidence is retained under DS-05 without treating generated concepts as passing runtime tests

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
