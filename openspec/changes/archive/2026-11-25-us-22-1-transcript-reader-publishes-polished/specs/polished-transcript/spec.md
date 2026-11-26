## ADDED Requirements

### Requirement: Adds to the end, as a new version

append_to_file SHALL add its text to the end of the latest version of a run file under the run's grants as a new version, creating a missing file as Markdown and keeping an existing file's media type.

#### Scenario: Adds to the end, as a new version
- **GIVEN** a run granted append_to_file through an Expert, whose path grant is outputs/child-1, and an existing text/plain run file under that grant
- **WHEN** the model adds to a missing file under outputs/child-1, adds to it again, adds to the text/plain file, and adds to a path outside outputs/ and to one under outputs/ outside the grant
- **THEN** the missing file is created as text/markdown at version 1, the next add makes version 2 with version 1's text followed by the new text, the text/plain file keeps its media type, each output holds the path, version, sha256 and characters its file has, the path outside outputs/ is refused invalid_arguments and the one outside the grant resource_not_granted, and neither writes

### Requirement: Two adds never lose one

Adds to one file made at once SHALL each land once, in consecutive versions.

#### Scenario: Two adds never lose one
- **GIVEN** a run file under outputs/ and two adds to it with different text, made at once on two connections under the run's lease
- **WHEN** both commit
- **THEN** the file has two new consecutive versions, and the latest holds the earlier text followed by both added texts, each once

### Requirement: Too large changes nothing

An add that would take a file past 256,000 characters SHALL fail file_too_large and write nothing.

#### Scenario: Too large changes nothing
- **GIVEN** a run file under outputs/ whose characters, with an add's text, would pass 256,000
- **WHEN** the model makes that add
- **THEN** it fails file_too_large, no version is written, and the file's latest version is as it was

### Requirement: Read back after an interruption

An add whose write committed SHALL be read back from its row, and the same add again SHALL write no other version.

#### Scenario: Read back after an interruption
- **GIVEN** an add whose write committed before its attempt ended without recording the outcome, and a run that makes one add to a file and then the same add again
- **WHEN** the run's next attempt makes the interrupted add again, and the repeated add is made
- **THEN** each returns the path, version, sha256 and characters of the version the first write made, read back from the file's row, no other version is written, and each file holds that text once

### Requirement: Only an Expert grants it

append_to_file SHALL be granted only through an Expert.

#### Scenario: Only an Expert grants it
- **GIVEN** the tool catalog, a plain goal's run, and a run started from an Expert version that grants append_to_file
- **WHEN** the catalog is read and each run calls append_to_file
- **THEN** the catalog lists append_to_file version 1 in the Files group, grantable only to an Expert, the plain goal's call is refused tool_not_granted and writes nothing, and the Expert's run is granted version 1 and its call adds

### Requirement: A polished transcript in sections

The Transcript reader SHALL save the timed captions as transcript-timed.md, add polished prose to transcript.md one section per 60 lines read, and publish both.

#### Scenario: A polished transcript in sections
- **GIVEN** YOLO on, a new workspace where the concept seed runs and its owner then adds youtube.com, ytimg.com, ggpht.com and gstatic.com to the Transcript reader's domains, a scripted model, and a scripted browse that returns a video's title and over 180 caption lines
- **WHEN** the Transcript workflow is executed with that video's https watch address
- **THEN** the browse saved transcript-timed.md as the title, the source address, the captions note and every line with its timestamp in order, the model read it with read_run_file 60 lines at a time from the first line to the last and added one section to transcript.md with append_to_file after each read, transcript.md's first section starts with the title, the source address and a note that the text is edited from YouTube's own captions, both files are published, no call holds more than one section, and the instructions the model was given say to continue a cut sentence in the next section, to keep every point, example, number and name in the speaker's words and order, to remove filler words, stutters and false starts, to fix punctuation, capitals and plainly misheard words, to break paragraphs where the topic turns, and never to summarise, shorten an argument, add anything or guess who is speaking

### Requirement: The seed and an Expert that exists

The seeded Transcript reader SHALL grant browse_goal, read_run_file, append_to_file and publish_artifact, and the seed SHALL keep a reader that exists.

#### Scenario: The seed and an Expert that exists
- **GIVEN** a workspace seeded before the change, and a new workspace where browse_goal is available
- **WHEN** the concept seed runs in the new workspace, and again in the earlier one
- **THEN** the new Transcript reader grants browse_goal, read_run_file, append_to_file and publish_artifact and not save_artifact, with no browse domains and the box's browser, and the earlier workspace's Transcript reader is unchanged
