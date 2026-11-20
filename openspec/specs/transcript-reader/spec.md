# transcript-reader Specification

## Purpose
TBD - created by archiving change us-17-5-transcript-reader-expert-workflow. Update Purpose after archive.

## Requirements

### Requirement: A watch address in, transcript.md out

Executed with a YouTube watch address, the Transcript workflow SHALL publish `transcript.md` with the video's title, its source address and every transcript line with its timestamp.

#### Scenario: A watch address in, transcript.md out
- **GIVEN** YOLO on, the Transcript reader with youtube.com, ytimg.com, ggpht.com and gstatic.com as its domains, the Transcript workflow, a disposable stack, a scripted model, and a scripted browse that returns a video's title and its transcript lines with their timestamps
- **WHEN** the workflow is executed with that video's https watch address
- **THEN** transcript.md is published with the video's title, its source address and every transcript line with its timestamp, and its line count equals the transcript's

### Requirement: The video host isn't allowed

The Transcript reader's browse_goal call SHALL start without approval, and its allowed domains SHALL be within the Transcript reader's, none of them googlevideo.com.

#### Scenario: The video host isn't allowed
- **GIVEN** the same execution
- **WHEN** its browse_goal call is made
- **THEN** the call starts without approval, and its allowed domains are within the Transcript reader's, none of them googlevideo.com

### Requirement: Seeded with no domains

The seeded Transcript reader SHALL have an empty browse domain list, and its browse_goal call SHALL be refused before any container starts, naming the missing list.

#### Scenario: Seeded with no domains
- **GIVEN** a workspace where browse_goal is available
- **WHEN** the concept seed runs, the owner opens the Transcript reader, and a run of it makes its browse_goal call
- **THEN** its browse domain list is empty, and the call is refused before any container starts, naming the missing list

### Requirement: Seeded once, and as a draft without browsing

The concept seed SHALL save the Transcript reader without browse_goal, saying so in its purpose, and the Transcript workflow as a draft where browse_goal isn't available, publish the workflow where it is, and add or change nothing on a second run.

#### Scenario: Seeded once, and as a draft without browsing
- **GIVEN** a workspace where browse_goal isn't available, and another where it is
- **WHEN** the concept seed runs twice in each
- **THEN** in the first the Transcript reader is saved without browse_goal and says so in its purpose, and the Transcript workflow is a draft, in the second the workflow is published, and the second seed run adds or changes nothing in either

### Requirement: Only a YouTube watch address is accepted

The Transcript workflow SHALL refuse, before it starts, an execution whose video input is not an https YouTube watch or youtu.be address, naming the input.

#### Scenario: Only a YouTube watch address is accepted
- **GIVEN** the Transcript workflow
- **WHEN** its video input is not an https YouTube watch or youtu.be address
- **THEN** the execution is refused before it starts, naming the input

### Requirement: No transcript offered

When a video offers no transcript, the Transcript reader's run SHALL end saying so, and SHALL publish no file.

#### Scenario: No transcript offered
- **GIVEN** a video whose description has no transcript section
- **WHEN** the Transcript reader browses it
- **THEN** the run ends saying no transcript is offered, and publishes no file

### Requirement: A bot check stops it

When YouTube answers with a bot check, the browse SHALL stop with `bot_check`, nothing SHALL try to pass it, and no file SHALL be published.

#### Scenario: A bot check stops it
- **GIVEN** YouTube answers with a bot check
- **WHEN** the Transcript reader meets it
- **THEN** the browse stops with bot_check, nothing tries to pass it, and no file is published
