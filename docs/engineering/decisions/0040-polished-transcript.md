# Decision 0040: The Transcript reader publishes polished prose

**Date:** 2026-11-25. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **The request:** "the output is the transcript without time and the content glued together with coherence".
- **The form:** "Model-polished prose", over paragraphs of the captions' words as they are, or one block of text.
- **Where:** "Replace, keep the timed file too". The Transcript reader publishes the prose as `transcript.md`, and the timed lines as `transcript-timed.md`, from one browse.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0035 to 0039. Where two options were close, the choice adds the least or is easier to reverse. The owner can change any of them under US-22.1.

This amends [Decision 0039](0039-browse-result-saved-to-a-file.md) V8 and V9, [Decision 0035](0035-browser-use-typing-and-transcripts.md) Y14, and the PRD rows below. It schedules EPIC-22.

## Context

- **A reply is too small for a whole transcript.** A model reply holds 4,096 output tokens, about 2,500 words. The owner's 44-minute video has 320 caption lines and 8,074 words. So the prose has to be written a section at a time.
- **Nothing adds to a file.** `save_artifact`, `write_code_file` and `patch_code_file` each write a whole file or replace text that is already there. Decision 0039 V9 left adding to a file to its own decision.
- **The captions are punctuated.** In the owner's file, 353 sentence ends span 320 lines, and 203 lines start mid-sentence.

## Decision

| # | Choice |
|---|---|
| **P1. `append_to_file`** | A Files tool, version 1: it adds `content` to the end of a run file under `outputs/`, as a new version. A missing file is created as `text/markdown`, and an existing one keeps its media type. It returns the path, version, SHA-256 and the file's characters. It is granted only through an Expert |
| **P2. Like any run-file write** | It writes through `run_files`, which reads the latest version and writes the next one under one lock and the run's lease, so two adds to one file never lose one. A whole file past 256,000 characters is refused `file_too_large`, and nothing changes. It keeps a receipt, and a call interrupted after its write is read back from the file's row, as `save_artifact` is. The same content added twice by one run is one call, added once |
| **P3. The timed file** | The browse saves `transcript-timed.md` by Decision 0039's layout, as before but under that name. It is published too |
| **P4. In sections** | The model reads the timed file with `read_run_file` 60 lines at a time, writes polished prose for those lines only, and adds it to `transcript.md` with `append_to_file`, until the last line. The first section starts with the title, the source address and a note that the text is edited from YouTube's own captions. A sentence cut between sections continues in the next. The timed file is published first and the prose last, so the run's result, the newest published file, is the prose |
| **P5. What polishing may change** | It keeps every point, example, number and name, in the speaker's own words and order. It removes filler words, stutters and false starts, fixes punctuation and capitals, fixes a word the captions plainly misheard, and breaks paragraphs where the topic turns. It never summarises, shortens an argument, adds anything, or guesses who is speaking |
| **P6. The Transcript reader's tools** | `browse_goal`, `read_run_file`, `append_to_file` and `publish_artifact`, in the seed. `save_artifact` is left out, so the model has no way to write a transcript whole. Its browse domains and `box` browser are unchanged. The seed keeps an Expert that exists (Decision 0034 S1), so an install's reader changes only when its owner saves a new version |
| **P7. Cost** | One model call reads each section and one writes it, so a 44-minute video takes about a dozen more calls than before. The run's budget still caps them |
| **P8. Not in this decision** | Speaker labels, translation, summaries, and polishing any other Expert's output |

## Requirements revised

The story amends these in its own change:
- **PRD-Tool-Catalog:** "Files" gains `append_to_file` (P1, P2).
- **PRD-Studio SD-02:** the Transcript reader's row names its tools and both files (P3 to P6).
- **Decision 0035 Y14** and **Decision 0039 V8:** the reader publishes the prose and the timed file. **Decision 0039 V9:** adding to a file is decided here.

## What this gives up

- **The captions' exact words in `transcript.md`.** The timed file keeps them.
- **A cheap run.** Polishing costs model calls the timed file didn't.
- **Very long videos.** Each 60 lines take two model calls, and a run has 64 (Decision 0034 L2). A video over about three hours reaches that limit before its last section.
- **Certainty.** A model can still drop or alter a sentence. The timed file is there to check against.

## What this doesn't establish

That a polished transcript is faithful. The checks use scripted models and scripted browses, and reach no YouTube (Y18). Nothing here establishes H1 or product acceptance.

## Reversal

Save a Transcript reader version with Decision 0039's instructions. `append_to_file` stays registered for runs that granted it.
