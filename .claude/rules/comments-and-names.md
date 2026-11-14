# Comments and names

Applies to all source, tests, scripts and migrations. The [code-quality standards](../../docs/reviews/review-2026-11-12-09-52-30/standards.md#std-23) give the reasons; [Decision 0027](../../docs/engineering/decisions/0027-refactor-decisions-delegated.md) adopted this.

## Comments

- State what holds now, then cite its source after the statement: `(Decision 0026 G2)`, `PRD-Studio SR-01`, `US-14.19`. Cite a decision with rows by its row. Name the document, never a bare "PRD x.y", since three PRDs number their sections.
- No delivery narrative ("a later story", "first", "nothing else exists yet") and no IDs from a transient review round, such as B1 or M21. IDs from a review committed under `docs/reviews/`, such as WSYS-01 or R-13, resolve there and may be cited. When a decision amends a requirement row, update every comment that cites the row in the same change.
- A suppression names a code and a reason: `# noqa: RUF009 - frozen, so sharing the default is safe.`, `# type: ignore[attr-defined]  # <reason>`, `// eslint-disable-next-line <rule> -- <reason>`. Remove one that nothing needs.

## Names

- Files, tests and migrations are named for the behavior they cover, never for the story or review round that added them. Provenance goes in the docstring or the opening comment.
- Python files are snake_case, TypeScript files kebab-case. Exception names state the outcome, such as `ProfileNotOffered`.

## Migrations

- Applied migrations keep their names and bytes.
- Every migration newer than `20261108000053_routine_removal.sql` opens with its traceability comment, then three lines: `-- Locks:` (what it locks, and for how long on the largest table), `-- Data:` (rows it rewrites, or none) and `-- Recovery:` (the forward fix if it fails midway).

## Check and review

Check: `tests/harness/test_migration_headers.py` and `test_rule_scopes.py`, run by the harness profile of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
