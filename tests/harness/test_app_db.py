"""Static guards for the application schema. Real replay runs in the `db` profile on a disposable target."""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import app_db  # noqa: E402

PRIVATE_RUN_COLUMNS = ('lease_generation', 'checkpoint_thread_id')
GRANT = re.compile(r'grant\s+(.*?)\s+on\s+(?:table\s+)?(.*?)\s+to\s+(.*?);', re.I | re.S)


def run_grants(files: list[Path]) -> list[tuple[str, str]]:
    """R-10: every grant on public.runs to authenticated, in name order, as (file, privileges)."""
    found = []
    for path in files:
        for privileges, tables, grantees in GRANT.findall(path.read_text()):
            if ('public.runs' in {name.strip() for name in tables.split(',')}
                    and 'authenticated' in {name.strip() for name in grantees.split(',')}):
                found.append((path.name, privileges))
    return found


def private_run_grants(files: list[Path]) -> list[str]:
    problems = []
    for name, privileges in run_grants(files):
        if '(' not in privileges:
            problems.append(f'{name}: every column')
        problems += [f'{name}: {column}' for column in PRIVATE_RUN_COLUMNS if column in privileges]
    return problems


class Migrations(unittest.TestCase):
    def test_names_are_ordered_and_well_formed(self):
        names = sorted(path.name for path in (ROOT / app_db.MIGRATIONS).glob('*.sql'))
        self.assertTrue(names)
        for name in names:
            self.assertRegex(name, app_db.MIGRATION_NAME)

    def test_the_shipped_record_matches_the_migration_files(self):
        """Decision 0023 E2: readiness compares the applied count with this record, so it can't drift."""
        names = sorted(path.name for path in (ROOT / app_db.MIGRATIONS).glob('*.sql'))
        text = (ROOT / 'services/agent/src/autobots/application/schema_release.py').read_text()
        shipped = re.search(r'^SHIPPED_MIGRATIONS = (\d+)$', text, re.MULTILINE)
        newest = re.search(r'^NEWEST_MIGRATION = "([^"]+)"$', text, re.MULTILINE)
        self.assertIsNotNone(shipped)
        self.assertIsNotNone(newest)
        self.assertEqual((int(shipped.group(1)), newest.group(1)), (len(names), names[-1]))

    def test_seeds_hold_no_ddl_secrets_or_jobs(self):
        text = (ROOT / app_db.SEEDS).read_text()
        self.assertEqual(app_db.seed_violations(text), [])
        self.assertIn('on conflict', text.lower())

    def test_each_forbidden_seed_term_is_caught(self):
        for term, line in (('create table', 'CREATE TABLE public.x (id int);'), ('alter table', 'alter table x add y int;'),
                           ('drop ', 'drop table x;'), ('password', "values ('password')"),
                           ('api_key', "values ('api_key')"), ('runs', 'insert into public.runs values (1);'),
                           ('run_jobs', 'insert into app_private.run_jobs values (1);'), ('job', "values ('job')")):
            with self.subTest(term):
                self.assertIn(term, app_db.seed_violations(line))

    def test_every_public_table_enables_row_level_security(self):
        text = ' '.join(path.read_text() for path in sorted((ROOT / app_db.MIGRATIONS).glob('*.sql')))
        tables = re.findall(r'create table public\.(\w+)', text)
        self.assertTrue(tables)
        for table in tables:
            self.assertIn(f'alter table public.{table} enable row level security', text, table)

    def test_private_run_columns_are_not_granted_to_authenticated(self):
        files = sorted((ROOT / app_db.MIGRATIONS).glob('*.sql'))
        self.assertGreater(len(run_grants(files)), 4, 'later migrations grant run columns too')
        self.assertEqual(private_run_grants(files), [])

    def test_a_later_private_grant_is_caught(self):
        with tempfile.TemporaryDirectory() as folder:
            first, later, table = (Path(folder) / name for name in ('0001_runs.sql', '0060_more.sql', '0061_all.sql'))
            first.write_text('grant select (id, status) on public.runs to authenticated;\n')
            later.write_text('grant select (goal_summary, checkpoint_thread_id) on public.runs to authenticated;\n')
            table.write_text('grant select on public.runs, public.run_events to authenticated, service_role;\n')
            self.assertEqual(private_run_grants([first, later, table]),
                             ['0060_more.sql: checkpoint_thread_id', '0061_all.sql: every column'])

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
