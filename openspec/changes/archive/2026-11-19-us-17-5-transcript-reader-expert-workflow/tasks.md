# Tasks

## 1. The input pattern (Only a YouTube watch address is accepted)

- [x] 1.1 `domain/workflows.py`: `InputConfig.pattern`, `input_pattern_invalid` in graph validation, and `input_pattern_mismatch` for a value that doesn't match or is longer than 2,048 characters. Checked by pytest under `services/agent/tests`

## 2. The seed (Seeded with no domains; Seeded once, and as a draft without browsing)

- [x] 2.1 The Transcript reader's purpose and instructions, its grants and empty domain list, and the Transcript workflow, published when browse_goal is available and a draft otherwise. Checked by pytest on the seed's definitions and by `transcript_check`
- [x] 2.2 `concept_seed_check` expects the eighth Expert and workflow. Checked by the identity qualification in the db profile

## 3. Execution (A watch address in, transcript.md out; The video host isn't allowed; No transcript offered; A bot check stops it)

- [x] 3.1 `tests/db/checks/transcript_check.py`, in the db profile, covers each of the following with scripted browses and a scripted model, and no request to YouTube:
  - seeding twice into both workspaces;
  - the empty domain list refusing the browse;
  - the input pattern;
  - a transcript published with every line;
  - the browse's domains within the Expert's and never googlevideo.com, with no approval;
  - no transcript offered;
  - a bot check.

  Checked by the db profile

## 4. The Experts page

- [x] 4.1 The Expert card shows an Expert's browse domains, or that it has none yet. Checked by web unit tests and the settings-browsing browser suite under `apps/web/tests/browser`

## 5. Documents

- [x] 5.1 Amend PRD-Studio SD-01 and SD-02 for the Transcript reader and its workflow, and update `CODEBASE.md`. Checked by reading them against Decision 0035 Y14 and Y17
