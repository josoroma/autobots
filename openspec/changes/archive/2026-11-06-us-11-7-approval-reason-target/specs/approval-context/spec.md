## ADDED Requirements

### Requirement: Each approval shows the policy's reason and its target

An approval request SHALL record the policy's reason and the resource target, and the inbox SHALL show both as text with the exact proposed action and expiry. The reason SHALL come from the server's policy, not from model output.

#### Scenario: Show the policy's reason and the target
- **GIVEN** a pending approval whose request records the policy's reason and a resource target
- **WHEN** the reviewer opens the inbox
- **THEN** both appear as text with the exact proposed action and expiry, and the reason comes from the server's policy, not from model output

### Requirement: The inbox doesn't invent what wasn't recorded

A request saved before these fields existed SHALL say which is not recorded, and any decision SHALL stay bound to the argument hash the reviewer saw.

#### Scenario: Don't invent what wasn't recorded
- **GIVEN** a pending approval saved before these fields existed
- **WHEN** the reviewer opens the inbox
- **THEN** it says which is not recorded, and any decision stays bound to the argument hash the reviewer saw
