"""R-04: a migration newer than the last applied-before-the-convention one states its locks, data and recovery.

Applied migrations keep their bytes, so the files up to `LAST_UNHEADED` are exempt by name.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAST_UNHEADED = '20261108000053_routine_removal.sql'  # applied files keep their bytes
HEADER = ('-- Locks:', '-- Data:', '-- Recovery:')


def missing_lines(path: Path) -> list[str]:
    opening = []
    for line in path.read_text().splitlines():
        if not line.startswith('--'):
            break
        opening.append(line)
    return [label for label in HEADER if not any(line.startswith(label) and line[len(label):].strip() for line in opening)]


def header_errors(migrations: Path) -> list[str]:
    errors = []
    for path in sorted(migrations.glob('*.sql')):
        if path.name <= LAST_UNHEADED:
            continue
        missing = missing_lines(path)
        if missing:
            errors.append(f'{path.name}: its opening comment has no {", ".join(missing)} line')
    return errors


def bootstrap_header_errors(bootstrap: Path) -> list[str]:
    """R-56 (SQLI-07): an ordered bootstrap file runs on the install like a migration, so it states the same
    three lines. roles.sql and storage.sql keep their applied bytes."""
    errors = []
    for path in sorted(bootstrap.glob('[0-9]*_*.sql')):
        missing = missing_lines(path)
        if missing:
            errors.append(f'{path.name}: its opening comment has no {", ".join(missing)} line')
    return errors


class MigrationHeaders(unittest.TestCase):
    def test_new_migrations_state_locks_data_and_recovery(self) -> None:
        self.assertEqual(header_errors(ROOT / 'supabase/migrations'), [])

    def test_ordered_bootstrap_files_state_locks_data_and_recovery(self) -> None:
        bootstrap = ROOT / 'supabase/bootstrap'
        self.assertTrue(list(bootstrap.glob('[0-9]*_*.sql')))
        self.assertEqual(bootstrap_header_errors(bootstrap), [])

    def test_a_bootstrap_file_without_the_header_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            bootstrap = Path(folder)
            (bootstrap / 'storage.sql').write_text('-- Applied, so exempt.\nselect 1;\n')
            (bootstrap / '20261115000001_good.sql').write_text('-- Why.\n-- Locks: brief.\n-- Data: none.\n-- Recovery: rerun.\nselect 1;\n')
            (bootstrap / '20261115000002_bad.sql').write_text('-- Why.\nselect 1;\n')
            self.assertEqual(bootstrap_header_errors(bootstrap),
                             ['20261115000002_bad.sql: its opening comment has no -- Locks:, -- Data:, -- Recovery: line'])

    def test_a_new_migration_without_the_header_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            migrations = Path(folder)
            (migrations / LAST_UNHEADED).write_text('alter table public.routines add column x int;\n')
            (migrations / '20261114000054_good.sql').write_text(
                '-- R-17: why.\n-- Locks: catalog only.\n-- Data: none.\n-- Recovery: rerun.\nselect 1;\n')
            (migrations / '20261114000055_bad.sql').write_text('-- R-17: why.\n-- Locks: catalog only.\nselect 1;\n'
                                                               '-- Data: too late, after the statement.\n')
            (migrations / '20261114000056_empty.sql').write_text('-- Why.\n-- Locks:\n-- Data: none.\n'
                                                                 '-- Recovery: rerun.\nselect 1;\n')
            self.assertEqual(header_errors(migrations),
                             ['20261114000055_bad.sql: its opening comment has no -- Data:, -- Recovery: line',
                              '20261114000056_empty.sql: its opening comment has no -- Locks: line'])


if __name__ == '__main__':
    unittest.main()
