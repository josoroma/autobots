"""R-04: a migration newer than the last applied-before-the-convention one states its locks, data and recovery.

Applied migrations keep their bytes, so the files up to `LAST_UNHEADED` are exempt by name.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAST_UNHEADED = '20261108000053_routine_removal.sql'
HEADER = ('-- Locks:', '-- Data:', '-- Recovery:')


def header_errors(migrations: Path) -> list[str]:
    errors = []
    for path in sorted(migrations.glob('*.sql')):
        if path.name <= LAST_UNHEADED:
            continue
        opening = []
        for line in path.read_text().splitlines():
            if not line.startswith('--'):
                break
            opening.append(line)
        missing = [label for label in HEADER if not any(line.startswith(label) for line in opening)]
        if missing:
            errors.append(f'{path.name}: its opening comment has no {", ".join(missing)} line')
    return errors


class MigrationHeaders(unittest.TestCase):
    def test_new_migrations_state_locks_data_and_recovery(self) -> None:
        self.assertEqual(header_errors(ROOT / 'supabase/migrations'), [])

    def test_a_new_migration_without_the_header_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            migrations = Path(folder)
            (migrations / LAST_UNHEADED).write_text('alter table public.routines add column x int;\n')
            (migrations / '20261114000054_good.sql').write_text(
                '-- R-17: why.\n-- Locks: catalog only.\n-- Data: none.\n-- Recovery: rerun.\nselect 1;\n')
            (migrations / '20261114000055_bad.sql').write_text('-- R-17: why.\n-- Locks: catalog only.\nselect 1;\n'
                                                               '-- Data: too late, after the statement.\n')
            self.assertEqual(header_errors(migrations),
                             ['20261114000055_bad.sql: its opening comment has no -- Data:, -- Recovery: line'])


if __name__ == '__main__':
    unittest.main()
