# file-tools Specification

## Purpose
TBD - created by archiving change us-14-9-agent-file-input-read. Update Purpose after archive.

## Requirements

### Requirement: Text files attach to a goal

The goal composer SHALL attach up to 5 plain text, markdown, JSON or CSV files of at most 1 MiB each as run inputs under `inputs/` with their media type, and SHALL refuse any other with a reason. Attaching SHALL NOT add a catalog tool.

#### Scenario: Attach files to a goal
- **GIVEN** the goal composer
- **WHEN** the owner attaches up to 5 plain text, markdown, JSON or CSV files of at most 1 MiB each, and then tries a sixth file, a larger file or another type
- **THEN** the accepted files become run inputs under inputs/ with their media type, the others are refused with a reason, and no catalog tool is added

### Requirement: Run files are read in pages

`read_run_file` version 2 SHALL return requested lines with media type, version, sha256, total lines and a cut flag, and `read_csv` SHALL return columns with inferred types, at most 500 rows and a cut flag. Their tool-use records SHALL keep digests and sizes of content, never content.

#### Scenario: Read run files in pages
- **GIVEN** a run with a text file and a CSV under inputs/
- **WHEN** read_run_file version 2 is called with an offset and limit, and read_csv with max_rows within 500
- **THEN** they return the requested lines with media type, version, sha256, total lines and a truncation flag, and columns with inferred types, rows and a truncation flag, and the tool-use record keeps only digests and sizes of the content

### Requirement: Remote files are stored through the guard

`store_remote_file` SHALL fetch through the URL guard and store only text of at most 1 MiB under `outputs/`, returning path, version, sha256, size and media type. Any other request SHALL be refused with a typed code and write nothing.

#### Scenario: Store a remote file through the guard
- **GIVEN** store_remote_file and a fake transport
- **WHEN** it is asked to store a guarded text URL under outputs/, then a refused URL, a non-text type, a body over 1 MiB or a path outside outputs/
- **THEN** the first returns path, version, sha256, size and media type, and each of the others is refused with a typed code and writes nothing
