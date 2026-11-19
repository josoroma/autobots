## ADDED Requirements

### Requirement: Deep research runs live on the install, documented

On the owner's persistent install (Decision 0034 R1, R2), the Deep research writer and its workflow SHALL each run once on "langchain for deep agents", started from the Studio with a US$5.00 budget and never more, and a README SHALL document what they did as observed. No key SHALL appear in their artifacts.

#### Scenario: The install runs the new code and seed
- **GIVEN** the owner's persistent install, rebuilt and restarted by the owner with this code and inference on, and seeded again
- **WHEN** the Studio's Experts and Workflows pages are read
- **THEN** the Deep research writer and the Deep research content writer are there, and what was there before is unchanged

#### Scenario: A live Expert run
- **GIVEN** the owner's OpenRouter and SerpApi keys
- **WHEN** the coordinator starts the Deep research writer on "langchain for deep agents" from the Studio with a US$5.00 budget
- **THEN** the run ends with its real outcome and published artifacts, its cost stays within US$5.00, and no key appears in its artifacts

#### Scenario: A live workflow execution
- **GIVEN** the same keys
- **WHEN** the coordinator starts the Deep research content writer on "langchain for deep agents" with a US$5.00 budget, and the owner decides its gate
- **THEN** the execution ends with its real outcome, both steps' artifacts are published, and its cost stays within US$5.00

#### Scenario: The README documents the runs
- **GIVEN** the two runs' records
- **WHEN** README-Deep-Research-Content-Writer.md is written and linked from README.md and README-DEV.md
- **THEN** it explains the reference, how Autobots runs it as an Expert and as a workflow, and what each run did, with counts and costs as observed, and every link resolves
