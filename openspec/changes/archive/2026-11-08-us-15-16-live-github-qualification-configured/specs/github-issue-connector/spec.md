## ADDED Requirements

### Requirement: An owner-authorized live qualification of the Studio GitHub tools

The GitHub qualification runner SHALL qualify the four read tools, labelled issues and the pull-request connector once against the configured repository. It SHALL run only with the owner's token in the environment it is given and a recorded authorization naming that repository and a request cap. It SHALL count each request before sending and send none beyond the cap. It SHALL open the pull request only after the owner approves its diff, and SHALL record a redacted report that holds no token. It SHALL be in no verification profile.

#### Scenario: One live pass per tool on the owner's repository
- **GIVEN** the owner's fine-grained token for josoroma/bot-test in the worker environment and the owner's capped authorization
- **WHEN** the qualification runner calls each read tool, creates one labelled issue, and opens one pull request after approval
- **THEN** each returns validated output from GitHub, the issue and the pull request carry their operation markers, a retry of the pull request returns the existing one, and the redacted record holds no token

#### Scenario: Not run without the owner
- **GIVEN** no recorded authorization or no token in the environment
- **WHEN** the runner starts
- **THEN** it refuses before any request to GitHub
