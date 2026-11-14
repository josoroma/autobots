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
# Whoever is granted reads, as a role or through PUBLIC.
READERS = frozenset({'authenticated', 'public'})
GRANT = re.compile(r'grant (?P<privileges>.+?) on (?P<objects>.+?) to (?P<grantees>.+?)'
                   r'(?P<option> with grant option)?(?: granted by \S+)?')
DEFAULT_GRANT = re.compile(r'alter default privileges(?P<scope>.*?) grant (?P<privileges>.+?) on tables to (?P<grantees>.+?)'
                           r'(?P<option> with grant option)?')
NOT_TABLES = ('function', 'functions', 'all functions', 'procedure', 'all procedures', 'routine', 'all routines', 'schema',
              'sequence', 'all sequences', 'type', 'domain', 'database', 'language', 'large object', 'foreign', 'tablespace')
Privilege = tuple[str, tuple[str, ...] | None]


def statements(text: str) -> list[str]:
    """Each statement in lower case on one line, without comments or identifier quotes."""
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'--[^\n]*', ' ', text)
    return [' '.join(part.replace('"', '').lower().split()) for part in text.split(';')]


def privileges(text: str) -> list[Privilege]:
    """Each privilege with its column list, or None when it covers every column."""
    items, depth, current = [], 0, ''
    for char in text:
        if char == ',' and depth == 0:
            items.append(current)
            current = ''
            continue
        depth += (char == '(') - (char == ')')
        current += char
    items.append(current)
    parsed: list[Privilege] = []
    for item in items:
        name, _, columns = item.partition('(')
        parsed.append((name.strip(), tuple(column.strip() for column in columns.rstrip(') ').split(',')) if columns else None))
    return parsed


def covers_runs(objects: str) -> bool:
    objects = objects.removeprefix('table ').strip()
    if objects.startswith(NOT_TABLES):
        return False
    if objects.startswith('all tables in schema '):
        return 'public' in {name.strip() for name in objects.removeprefix('all tables in schema ').split(',')}
    return bool({'runs', 'public.runs'} & {name.strip() for name in objects.split(',')})


def run_grants(files: list[Path]) -> list[tuple[str, list[Privilege], bool]]:
    """R-10: every grant that reaches public.runs for authenticated, in name order, as (file, privileges, grant option).

    Schema-wide and default grants reach it too, as do unqualified, quoted and PUBLIC forms.
    """
    found = []
    for path in files:
        for statement in statements(path.read_text()):
            grant, default = GRANT.fullmatch(statement), DEFAULT_GRANT.fullmatch(statement)
            if grant and covers_runs(grant['objects']):
                match = grant
            elif default and (' in schema ' not in default['scope'] or 'public' in default['scope'].split()):
                match = default
            else:
                continue
            if READERS & {name.strip() for name in match['grantees'].split(',')}:
                found.append((path.name, privileges(match['privileges']), match['option'] is not None))
    return found


def private_run_grants(files: list[Path]) -> list[str]:
    problems = []
    for name, granted, option in run_grants(files):
        if option:
            problems.append(f'{name}: with grant option')
        if any(columns is None for _, columns in granted):
            problems.append(f'{name}: every column')
        problems += [f'{name}: {column}' for column in PRIVATE_RUN_COLUMNS
                     if any(columns and column in columns for _, columns in granted)]
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

    def test_each_form_that_reaches_the_runs_table_is_caught(self):
        forms = {
            'grant select on all tables in schema public to authenticated;': ['every column'],
            'alter default privileges in schema public grant select on tables to authenticated;': ['every column'],
            'alter default privileges grant all on tables to public;': ['every column'],
            'grant select, update (status) on public.runs to authenticated;': ['every column'],
            'grant select (id) on public.runs to authenticated with grant option;': ['with grant option'],
            'grant select on runs to authenticated;': ['every column'],
            'GRANT SELECT\n  ON TABLE "public"."runs"\n  TO "authenticated";': ['every column'],
            'grant select ("checkpoint_thread_id") on "public"."runs" to authenticated;': ['checkpoint_thread_id'],
            'grant select on public.runs to public;': ['every column'],
            'grant update (lease_generation) on public.runs to service_role, authenticated;': ['lease_generation'],
            # None of these reaches it.
            '-- grant select on public.runs to authenticated;': [],
            'grant execute on function public.runs_view() to authenticated;': [],
            'grant select on public.runs_archive to authenticated;': [],
            'grant select on all tables in schema app_private to authenticated;': [],
            'grant select on public.runs to service_role;': [],
            'grant select (id, status) on public.runs to authenticated;': [],
        }
        with tempfile.TemporaryDirectory() as folder:
            for index, (form, expected) in enumerate(forms.items()):
                with self.subTest(form):
                    path = Path(folder) / f'{index:04d}_form.sql'
                    path.write_text(form + '\n')
                    self.assertEqual(private_run_grants([path]), [f'{path.name}: {problem}' for problem in expected])

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
