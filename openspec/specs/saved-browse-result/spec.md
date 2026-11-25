# saved-browse-result Specification

## Purpose

`browse_goal` version 4 saves a browse's validated typed result straight to a run file, so the model never retypes a long one (Decision 0039, US-21.1).

## Requirements

### Requirement: Every line, in order, and none typed by the model

When a version 4 call with a `save` ends done with a valid result, the worker SHALL write every item in order, one line each, or the result as indented JSON with no layout, and the output SHALL name the file and hold no result.

#### Scenario: Every line, in order, and none typed by the model
- **GIVEN** a run granted browse_goal version 4 under YOLO, a scripted model, and a scripted browse that ends done with a valid result of more lines than a model reply could hold, past 48,000 characters, one of whose values holds a line break
- **WHEN** the model calls it with a save whose layout names the lines and holds a brace that names nothing, and again with a save to another path and no layout
- **THEN** the first file is the text above the items with that brace as text, and then every item in order, one line each, as it came but for the line break as one space, the second file is the result as indented JSON, no line reached the model or came from it, and the first output holds saved_path, saved_version, saved_sha256, saved_items and saved_characters as its file has them and no result

### Requirement: Refused before any container

A `save` without an `output_schema`, one naming what the schema doesn't have, and one outside the run's path grants SHALL be refused before any container starts.

#### Scenario: Refused before any container
- **GIVEN** a run granted browse_goal version 4 whose path grant is outputs/child-1, and an executor that fails if it is touched
- **WHEN** the model calls it with a save and no output_schema, with a save whose items, line or before names what the schema doesn't have, and with a save path under outputs/ outside that grant
- **THEN** the save with no schema and each unknown name are refused invalid_arguments, the path is refused resource_not_granted, and no container starts

### Requirement: When it isn't saved

A call that isn't saved SHALL write no file, and when it ended done SHALL say why in `not_saved` and return the result as version 3 does.

#### Scenario: When it isn't saved
- **GIVEN** scripted version 4 calls with a save: one whose array is empty, one whose file would pass 256,000 characters, one whose attempt has ended, one whose use was never recorded, and some that end other than done
- **WHEN** each call ends
- **THEN** none writes a file, the first four say no_items, too_large, lease_lost and lease_lost in not_saved with the result as version 3 returns it, and the rest save nothing

### Requirement: A repeat browses again

A repeated call SHALL browse again and save a new version, leaving the earlier one as it was.

#### Scenario: A repeat browses again
- **GIVEN** a version 4 call that saved its file, and an attempt that ended before the call's outcome was recorded
- **WHEN** the run's next attempt makes the same call
- **THEN** it browses again and saves a new version, the earlier version stays as it was, and the output names the version this call wrote

### Requirement: Earlier versions keep their schemas

Versions 1 to 3 SHALL stay registered with their published schemas, runs that pinned one SHALL keep it, and new grants SHALL take version 4.

#### Scenario: Earlier versions keep their schemas
- **GIVEN** the pinned schema digests of browse_goal versions 1 to 3, and a run that pinned version 3 before the change
- **WHEN** the tools are registered, that run makes a browse_goal call, and an Expert that grants browse_goal starts a run
- **THEN** versions 1 to 3 keep their digests beside version 4, the earlier run's call runs as version 3 and returns its result, and the new run is granted version 4

### Requirement: A published transcript nothing retyped

The seeded Transcript reader SHALL publish the file browse_goal saved, with no transcript line in any call the model makes, and the seed SHALL leave an Expert already seeded unchanged.

#### Scenario: A published transcript nothing retyped
- **GIVEN** YOLO on, a workspace seeded before the change, a new one where the concept seed runs and its owner then adds youtube.com, ytimg.com, ggpht.com and gstatic.com to the Transcript reader's domains, a scripted model, and a scripted browse that returns a video's title and a transcript too long for a model reply
- **WHEN** the seed runs again in the earlier workspace, and the Transcript workflow is executed in the new one with that video's https watch address
- **THEN** transcript.md is published from the saved file with the title, the source address and every line with its timestamp in order, no call the model made holds a transcript line, the new Transcript reader was seeded with the same tools, no browse domains and the box's browser, and the earlier workspace's Transcript reader is unchanged

### Requirement: The tool row shows the path and the count

A saved browse's tool row SHALL show the path and the item count, and no row or event SHALL hold the file's text.

#### Scenario: The tool row shows the path and the count
- **GIVEN** a saved browse of a run, whose result holds a planted text
- **WHEN** a member reads the run's tool uses
- **THEN** the browse's row shows saved_path and saved_items, and the planted text is in no row or event
