# Design

## Decisions

- **Where it is rendered.** `application/typed_results.rendered` is pure. It takes the validated result and the layout.
- **Where it is written.** `application/run_files.write`, the one writer of run files, with the lease. A browse is dispatched as a read, so it has no operation ID. Its version is bound to `use:<tool-use id>` in `run_files.operation_id`, which is unique.
- **Path grants.** Version 4 declares `resources`, so the gateway refuses a path outside the grants before admission.
- **What can't be saved.** `not_saved` and version 3's result. A lost lease is caught, so the call still reports what it read.
- **Public fields.** `saved_path` and `saved_items`, and nothing of the file's text.

## Risks

- **Too large.** A file past 256,000 characters comes back as the result, which often passes the 300,000-byte reply cap and fails `output_too_large`, as version 3 does today.
