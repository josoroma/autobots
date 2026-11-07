# Tasks

## 1. Agent File Input (Attach files to a goal)

- [x] 1.1 Give input documents a media type and a 1 MiB limit, store the type at admission, and let run creation through the BFF carry them
- [x] 1.2 Attach up to 5 text files in the goal composer, refusing others with a reason, in keyboard order after the model choice
- [x] 1.3 Cover attachment, refusals, stored inputs and the unchanged catalog in a browser spec on a disposable stack

## 2. Reading (Read run files in pages)

- [x] 2.1 Register `read_run_file` version 2 beside version 1, and add `read_csv`
- [x] 2.2 Cover paging, CSV, the record's digests and a pinned version 1 on a disposable stack

## 3. Storing (Store a remote file through the guard)

- [x] 3.1 Add `store_remote_file` through the URL guard, text only and 1 MiB, saved with a receipt; check the connected peer too
- [x] 3.2 Cover a stored file and each refusal with a fake transport on a disposable stack
