# local-identity Specification

## Purpose
TBD - created by archiving change us-2-3-local-identity-workspace-grants. Update Purpose after archive.

## Requirements

### Requirement: Local password ownership
With local Auth and public signup disabled, an owner bootstrapped through supported APIs SHALL sign in, and the BFF and Python service SHALL verify identity and workspace membership without an external identity provider.

#### Scenario: Use local password ownership
- **GIVEN** local Auth with public signup disabled
- **WHEN** the owner is bootstrapped through supported APIs and signs in
- **THEN** the BFF and Python service verify identity and workspace membership without an external identity provider

### Requirement: Rejected cross-boundary access
Anonymous, forged or other-workspace identities MUST be denied domain records, private schemas and private Storage objects, and app_private and agent_runtime MUST be absent from PostgREST and Realtime access.

#### Scenario: Reject cross-boundary access
- **GIVEN** anonymous, forged or other-workspace identities
- **WHEN** they request domain records, private schemas or private Storage objects
- **THEN** access is denied and app_private/agent_runtime are absent from PostgREST and Realtime access

### Requirement: A person has an editable display name

Each user SHALL have at most one display name of 1 to 60 characters, stored per user. A user SHALL be able to set only their own. The user and members of a workspace they share SHALL be able to read it, and nobody else SHALL. An empty or overlong name SHALL be refused with a typed code and leave the saved name unchanged. Without a saved name, the shown name SHALL be the part of the sign-in email before `@`.

#### Scenario: Edit my own display name
- **GIVEN** a signed-in member on Settings → Account
- **WHEN** they save a display name of 1 to 60 characters, and then try an empty name and one of 61 characters
- **THEN** the first is saved and shown in the shell footer, and the others are refused with a typed code and leave the saved name unchanged

#### Scenario: RLS bounds who reads and writes a name
- **GIVEN** on a disposable stack two users who share a workspace and a third user who belongs only to another workspace
- **WHEN** each, as the authenticated role, reads and tries to update the others' profile rows
- **THEN** each user can update only their own name, a member of the shared workspace can read the other's name, and the third user can neither read nor change either

#### Scenario: Fall back to the email's local part
- **GIVEN** a user signed in as ada@example.com who has never saved a display name
- **WHEN** the shell footer and the session summary load
- **THEN** the name shown is "ada"

### Requirement: The session names the person and their workspaces

The session summary SHALL return the display name, the email, and each workspace's ID, name and the user's role in it. The shell footer SHALL show the display name, the role in the current workspace and "this Mac", with a menu offering Settings → Account and Sign out. Settings → Account SHALL show the editable display name, the read-only email, the role and Sign out.

#### Scenario: Session summary and account footer
- **GIVEN** a user who is owner of one workspace and member of another
- **WHEN** the session summary is read through the BFF and the footer's menu is opened
- **THEN** the summary returns each workspace's name and the user's role in it, the footer shows the display name, the role in the current workspace and "this Mac", and its menu offers Settings → Account and Sign out

#### Scenario: Account page
- **GIVEN** Settings → Account
- **WHEN** it loads
- **THEN** it shows the display name as editable, the email as read-only, the role and Sign out
