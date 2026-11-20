# Proposal

## Why

US-17.5 in SPECS.md: [Decision 0035](../../../docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md#decision) Y3, Y10, Y13, Y14, Y17 and Y18. The owner wants a video's words as a clean, timestamped Markdown file. browse_goal can now press, type and submit on browser-use and return a typed result (US-17.3, US-17.4). What's missing is a seeded Expert and workflow that use it for a YouTube video, and a workflow input that accepts only a watch address.

## What Changes

- **The Transcript reader.** A concept Expert with a purpose and instructions:
  - open the watch address, press "...more" and "Show transcript", and read every line through browse_goal's typed result;
  - publish `transcript.md` with the title, the source address, a note that the lines are YouTube's own captions, and each line with its timestamp;
  - stop, publishing nothing, when no transcript is offered or a bot check appears;
  - never sign in, comment or post.

  It is granted `browse_goal`, `save_artifact` and `publish_artifact`, with an empty browse domain list. Its purpose says it browses only once the owner adds youtube.com, ytimg.com, ggpht.com and gstatic.com, never googlevideo.com, and that adding them is where the owner accepts YouTube's terms (Y14).
- **The Transcript workflow.** Input `video` → the Transcript reader → output. It is published when `browse_goal` is available and a draft otherwise (SD-01). The seed keeps anything already named (Decision 0034 S1).
- **A workflow input's pattern (Y17).** A `string` input may declare `pattern`, a regular expression the whole value must match. An execution whose value doesn't match is refused before it starts, as `workflow_inputs_invalid` naming the input. The Transcript workflow's `video` requires an https YouTube watch or youtu.be address. Inputs that declare no pattern are unchanged.
- **The Experts page.** An Expert that grants `browse_goal` shows its browse domains, or that it has none yet and so can't browse.
- **Documents.** PRD-Studio SD-01 and SD-02, and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `transcript-reader`: the seeded Transcript reader and Transcript workflow, the workflow input pattern, and the Experts page's browse domains.

### Modified Capabilities
- None as requirements. The concept seed's existing requirements stand, with one more Expert and workflow.

## Impact

- **Python:**
  - `domain/workflows.py` (the input pattern);
  - `operations/concept_seed.py` (the Expert and workflow);
  - checks: `tests/db/checks/concept_seed_check.py` (its expected sets) and a new `tests/db/checks/transcript_check.py` (in the db profile, with a scripted model and scripted browses, never YouTube, by Y18).
- **Web:** `lib/experts/card.ts` and the Expert card; the settings-browsing browser suite.
- **No migration and no paid call.**
