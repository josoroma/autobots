# Design

## Decisions

- **One lock for an add.** `run_files.append` takes the run's lease and the path's advisory lock, reads the latest version and inserts the next in the same transaction. `write` shares the lock helper, so the one writer of run files stays one.
- **Receipts.** `append_to_file` is a `reversible_internal_write` with `reconcile` by operation and `safe_to_repeat`, like `save_artifact`. The gateway names an operation by its arguments, so the same content twice in one run is one call.
- **Sections.** The reader reads 60 lines a time with `read_run_file` version 2 and adds one section per read, so a section stays well inside one reply.
- **Seed.** `save_artifact` leaves the reader's tools. The seed keeps an Expert that exists.

## Risks

- **Faithfulness.** A model can drop or change a sentence. The timed file is published beside it.
- **Long videos.** Two calls per 60 lines against 64 model calls a run.
