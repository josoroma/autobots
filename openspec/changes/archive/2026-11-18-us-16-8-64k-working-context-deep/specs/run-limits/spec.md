## ADDED Requirements

### Requirement: Every run works in a 64K-token context

By Decision 0034 L6 to L8, a run's view SHALL be compacted toward 192,000 characters, tool output of up to 48,000 characters SHALL stay in view and longer output SHALL be offloaded and read back 4,000 characters a page, the latest 16 read-back pages SHALL stay in view, and each model call SHALL reserve 64,000 prompt tokens with its reply.

#### Scenario: Every run works in a 64K-token context
- **GIVEN** the worker's defaults
- **WHEN** a run's view is compacted and a model call is reserved
- **THEN** the view is compacted toward 192,000 characters, tool output of up to 48,000 characters stays in view, the latest 16 read-back pages stay in view, and the call reserves 64,000 prompt tokens with its 4,096-token reply

#### Scenario: Search results stay in view
- **GIVEN** a run whose google_search returned 28 results of about 14,000 characters, as the first live run's did
- **WHEN** its next model call is prepared
- **THEN** the results are in the model's view whole, not offloaded

#### Scenario: An offloaded output can be read back whole
- **GIVEN** a tool output of 60,000 characters, offloaded
- **WHEN** the model reads it back in 15 pages of 4,000 characters
- **THEN** all 15 pages are in its view on the next call
