## ADDED Requirements

### Requirement: Search covers the run's files only

`search_files` SHALL search only this run's files the scope grants, return matches, files or a count within its ceilings, cap each match line at 500 characters, flag truncation, and fail `invalid_pattern` for a pattern that doesn't compile.

#### Scenario: Search run files
- **GIVEN** a run with files
- **WHEN** search_files is called with a regex, a path prefix, a glob, an output mode and limits within the ceilings
- **THEN** it returns matches, files or a count from the run's files only, caps each match line at 500 characters, flags truncation, and an uncompilable pattern fails as invalid_pattern

### Requirement: A patch is exact or nothing

`patch_code_file` SHALL fail with a typed code and write nothing when `old_string` is absent, or found more than once without `replace_all`; otherwise it SHALL write a new version and return it with its sha256 and the number of replacements.

#### Scenario: Patch exactly or not at all
- **GIVEN** a file under outputs/
- **WHEN** patch_code_file is called with an absent old_string, or an ambiguous one without replace_all, and then with an exact one
- **THEN** the first two fail with a typed code and write nothing, and the last returns the new version, sha256 and number of replacements

### Requirement: Writes stay under outputs/

`write_code_file` and `patch_code_file` SHALL refuse a path outside `outputs/` with a typed code and write nothing.

#### Scenario: Writes stay under outputs/
- **GIVEN** write_code_file or patch_code_file
- **WHEN** the path is outside outputs/
- **THEN** the call is refused with a typed code and nothing is written
