"""Static guards for the application schema. Real replay runs in the `db` profile on a disposable target."""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import app_db  # noqa: E402


class Migrations(unittest.TestCase):
    def test_names_are_ordered_and_well_formed(self):
        names = sorted(path.name for path in (ROOT / app_db.MIGRATIONS).glob('*.sql'))
        self.assertTrue(names)
        for name in names:
            self.assertRegex(name, app_db.MIGRATION_NAME)

    def test_seeds_hold_no_ddl_secrets_or_jobs(self):
        text = (ROOT / app_db.SEEDS).read_text().lower()
        for word in ('create table', 'alter table', 'drop ', 'password', 'api_key', 'runs'):
            self.assertNotIn(word, text)
        self.assertIn('on conflict', text)

    def test_every_public_table_enables_row_level_security(self):
        text = ' '.join(path.read_text() for path in sorted((ROOT / app_db.MIGRATIONS).glob('*.sql')))
        tables = re.findall(r'create table public\.(\w+)', text)
        self.assertTrue(tables)
        for table in tables:
            self.assertIn(f'alter table public.{table} enable row level security', text, table)

    def test_private_run_columns_are_not_granted_to_authenticated(self):
        text = (ROOT / app_db.MIGRATIONS / '20261105000002_runs.sql').read_text()
        grant = re.search(r'grant select \(([^)]*)\) on public\.runs to authenticated', text)
        self.assertIsNotNone(grant)
        self.assertNotIn('lease_generation', grant[1])
        self.assertNotIn('checkpoint_thread_id', grant[1])

    def test_service_code_owns_no_schema(self):
        for path in (ROOT / 'services/agent/src').rglob('*.py'):
            self.assertIsNone(app_db.FORBIDDEN_DDL.search(path.read_text()), path)
        self.assertIsNotNone(app_db.FORBIDDEN_DDL.search('checkpointer.setup()'))
        self.assertIsNotNone(app_db.FORBIDDEN_DDL.search('import alembic'))


class RowTypes(unittest.TestCase):
    def test_mapping(self):
        text = app_db.row_types([('runs', 'id', 'uuid', 'NO'), ('runs', 'parent_run_id', 'uuid', 'YES'),
                                 ('run_events', 'payload', 'jsonb', 'NO'), ('runs', 'spent', 'bigint', 'NO')])
        self.assertIn('export interface RunsRow {', text)
        self.assertIn('export interface RunEventsRow {', text)
        self.assertIn('  parent_run_id: string | null;', text)
        self.assertIn('  payload: unknown;', text)
        self.assertIn('  spent: number;', text)

    def test_an_unmapped_type_is_an_error_not_any(self):
        with self.assertRaises(ValueError):
            app_db.row_types([('runs', 'x', 'money', 'NO')])


if __name__ == '__main__':
    unittest.main()
