"""The superuser's bootstrap files keep a history as migrations do (R-56, SQLI-07).

`storage.sql` applies first and stays unchanged, then each ordered file by name, each once with its
checksum, for `persistent_install.py` and `app_db.py` alike. Also the disposable reset's catalog list
(SQLI-16), the exposure query behind the row types (SQLI-06, Decision 0029 F6) and the schema
snapshot's normalization (SQLI-09). The database side runs in the `db` profile.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import app_db  # noqa: E402 - importable only once the scripts folder is on sys.path, just above.
from disposable_db import Refused  # noqa: E402 - the same scripts folder.

# What app_private.applied_migration_count() counts, as migration 49 writes it.
COUNTED = r'^[0-9]{14}_[a-z0-9_]+\.sql$'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap_root(folder: str, *names: str) -> Path:
    """A repository root whose supabase/bootstrap holds roles.sql, storage.sql and `names`."""
    root = Path(folder)
    bootstrap = root / app_db.BOOTSTRAP
    bootstrap.mkdir(parents=True)
    for name in ('roles.sql', 'storage.sql', *names):
        (bootstrap / name).write_text(f'-- {name}\nselect 1;\n')
    return root


def rows(pending: list[tuple[Path, str, str]]) -> list[str]:
    return [row for _, row, _ in pending]


class BootstrapOrder(unittest.TestCase):
    def test_storage_comes_first_then_the_ordered_files_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder, '20261115000002_later.sql', '20261115000001_first.sql')
            self.assertEqual([path.name for path in app_db.bootstrap_files(root)],
                             ['storage.sql', '20261115000001_first.sql', '20261115000002_later.sql'])
            pending, refusal = app_db.bootstrap_plan(root, {})
            self.assertIsNone(refusal)
            self.assertEqual(rows(pending), ['bootstrap/storage.sql', 'bootstrap/20261115000001_first.sql',
                                             'bootstrap/20261115000002_later.sql'])
            self.assertEqual([checksum for path, _, checksum in pending], [digest(path) for path, _, _ in pending])

    def test_the_roles_file_runs_once_at_setup_and_keeps_no_history_row(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder)
            self.assertNotIn('roles.sql', [path.name for path in app_db.bootstrap_files(root)])

    def test_an_applied_file_is_not_applied_again(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder, '20261115000001_first.sql')
            storage = root / app_db.STORAGE_SQL
            # Migration rows share the history, and are none of the bootstrap plan's business.
            recorded = {'bootstrap/storage.sql': digest(storage), '20261105000001_workspaces.sql': 'any'}
            pending, refusal = app_db.bootstrap_plan(root, recorded)
            self.assertIsNone(refusal)
            self.assertEqual(rows(pending), ['bootstrap/20261115000001_first.sql'])

    def test_upto_applies_only_the_first_files(self) -> None:
        """The prior release shipped storage.sql alone, which the upgrade qualifier applies first."""
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder, '20261115000001_first.sql')
            pending, refusal = app_db.bootstrap_plan(root, {}, upto=1)
            self.assertIsNone(refusal)
            self.assertEqual(rows(pending), ['bootstrap/storage.sql'])


class BootstrapRefusals(unittest.TestCase):
    def test_an_edited_applied_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder, '20261115000001_first.sql')
            recorded = {'bootstrap/storage.sql': digest(root / app_db.STORAGE_SQL), 'bootstrap/20261115000001_first.sql': 'edited'}
            pending, refusal = app_db.bootstrap_plan(root, recorded)
            self.assertEqual(pending, [])
            self.assertEqual(refusal, 'bootstrap/20261115000001_first.sql changed after it was applied; never edit an applied file')

    def test_a_changed_storage_file_is_refused_in_the_words_the_install_qualifier_reads(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder)
            _, refusal = app_db.bootstrap_plan(root, {'bootstrap/storage.sql': 'arranged'})
            self.assertIn('changed after it was applied', refusal or '')

    def test_an_applied_file_this_checkout_lacks_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder)
            _, refusal = app_db.bootstrap_plan(root, {'bootstrap/29991231000000_a_later_release.sql': 'x'})
            self.assertEqual(refusal, 'bootstrap/29991231000000_a_later_release.sql was applied and is not in this '
                                      'checkout, so this is an older revision')

    def test_a_badly_named_file_is_refused_even_past_upto(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = bootstrap_root(folder, 'narrow_storage.sql')
            pending, refusal = app_db.bootstrap_plan(root, {}, upto=1)
            self.assertEqual(pending, [])
            self.assertEqual(refusal, 'bootstrap/narrow_storage.sql is not named <14 digit timestamp>_<description>.sql')


class CheckedInBootstrap(unittest.TestCase):
    def test_this_checkout_s_files_plan_cleanly_with_storage_first(self) -> None:
        pending, refusal = app_db.bootstrap_plan(ROOT, {})
        self.assertIsNone(refusal)
        self.assertEqual(rows(pending)[0], 'bootstrap/storage.sql')
        self.assertGreater(len(pending), 1)

    def test_bootstrap_rows_are_never_counted_as_migrations(self) -> None:
        counted = (ROOT / 'supabase/migrations/20261108000049_applied_migration_count.sql').read_text()
        self.assertIn(f"'{COUNTED}'", counted)
        for path in app_db.bootstrap_files(ROOT):
            self.assertIsNone(re.match(COUNTED, app_db.BOOTSTRAP_ROW + path.name), path.name)

    def test_storage_sql_keeps_its_applied_bytes(self) -> None:
        """The install refuses a changed storage.sql, so its digest stays the one every install recorded:
        `git show be2efe9:supabase/bootstrap/storage.sql | shasum -a 256`, the commit that added it."""
        self.assertEqual(digest(ROOT / app_db.STORAGE_SQL), 'cab6e411b1b0cfc51f818932af2a84ef56a303e6894c7cc8cc01c10433a84125')


class HistoryStack:
    """The two connections guarded_apply uses: the migration role's and the superuser's. Each statement
    is kept, and the history listing answers from `recorded`."""

    def __init__(self, recorded: dict[str, str]) -> None:
        self.recorded = recorded
        self.sent: list[tuple[str, str]] = []

    def reply(self, role: str, statements: str) -> subprocess.CompletedProcess[str]:
        self.sent.append((role, statements))
        listing = ''.join(f'{name}|{checksum}\n' for name, checksum in self.recorded.items())
        return subprocess.CompletedProcess([], 0, listing if statements.startswith('select name, sha256') else '', '')

    def migrator(self, statements: str) -> subprocess.CompletedProcess[str]:
        return self.reply('migrator', statements)

    def sql(self, statements: str) -> subprocess.CompletedProcess[str]:
        return self.reply('superuser', statements)


class GuardedApply(unittest.TestCase):
    """persistent_install.guarded_apply keeps the same bootstrap history, after the migrations and the seed."""

    def setUp(self) -> None:
        import persistent_install
        self.install = persistent_install
        self.record = persistent_install.Record('autobots-install', 'id', 1, 2, 3, 4, Path('/nowhere'))
        patcher = mock.patch.object(persistent_install, 'require_install')
        patcher.start()
        self.addCleanup(patcher.stop)

    def apply(self, stack: HistoryStack) -> dict[str, Any]:
        """guarded_apply on the fake, which offers only the two connections it uses, not a whole AppStack."""
        return cast(dict[str, Any], self.install.guarded_apply(cast(Any, stack), ROOT, self.record, 'autobots-install'))

    def applied_history(self, root: Path) -> dict[str, str]:
        recorded = {path.name: digest(path) for path in (root / app_db.MIGRATIONS).glob('*.sql')}
        recorded['bootstrap/storage.sql'] = digest(root / app_db.STORAGE_SQL)
        return recorded

    def test_an_install_with_storage_applied_gets_only_the_newer_bootstrap_files_last(self) -> None:
        stack = HistoryStack(self.applied_history(ROOT))
        result = self.apply(stack)
        ordered = [app_db.BOOTSTRAP_ROW + path.name for path in app_db.bootstrap_files(ROOT)[1:]]
        self.assertEqual(result['applied'], [])
        self.assertEqual(result['bootstrap_applied'], ordered)
        self.assertEqual(result['already_applied'], len(list((ROOT / app_db.MIGRATIONS).glob('*.sql'))))
        roles = [role for role, _ in stack.sent]
        # The listing, the seed as the migration role, then each bootstrap file as the superuser.
        self.assertEqual(roles, ['migrator', 'migrator', *['superuser'] * len(ordered)])
        for (_, statements), row in zip(stack.sent[2:], ordered, strict=True):
            self.assertIn(f"insert into autobots_install.migrations (name, sha256) values ('{row}', ", statements)

    def test_an_edited_bootstrap_file_is_refused_before_any_change(self) -> None:
        recorded = self.applied_history(ROOT)
        recorded['bootstrap/storage.sql'] = 'arranged'
        stack = HistoryStack(recorded)
        with self.assertRaises(Refused) as refused:
            self.apply(stack)
        self.assertIn('changed after it was applied', str(refused.exception))
        self.assertEqual([statements[:20] for _, statements in stack.sent], ['select name, sha256 '])

    def test_bootstrap_rows_are_not_mistaken_for_missing_migrations(self) -> None:
        recorded = self.applied_history(ROOT)
        for path in app_db.bootstrap_files(ROOT)[1:]:
            recorded[app_db.BOOTSTRAP_ROW + path.name] = digest(path)
        result = self.apply(HistoryStack(recorded))
        self.assertEqual((result['applied'], result['bootstrap_applied']), ([], []))


class BackupHistory(unittest.TestCase):
    """A backup manifest lists every history row (local_backup.read_facts), bootstrap rows included, and
    restore checks that list whole. The backup qualifier counts its migrations only, so a manifest written
    before the ordered bootstrap files, or by an install that recorded storage.sql alone, reads the same."""

    def test_only_migration_rows_are_counted(self) -> None:
        import qualify_backup
        migrations = sorted(path.name for path in (ROOT / app_db.MIGRATIONS).glob('*.sql'))
        bootstrap = [app_db.BOOTSTRAP_ROW + path.name for path in app_db.bootstrap_files(ROOT)]
        for label, listed, counted in (('a disposable backup from before R-56', migrations[:56], migrations[:56]),
                                       ('an install backup from before R-56', [*migrations[:56], 'bootstrap/storage.sql'], migrations[:56]),
                                       ('a backup from this release', [*migrations, *bootstrap], migrations)):
            with self.subTest(label):
                self.assertEqual(qualify_backup.recorded_migrations(listed), counted)
                self.assertEqual(qualify_backup.recorded_bootstrap(listed), [name for name in listed if name.startswith('bootstrap/')])


class DisposableReset(unittest.TestCase):
    def test_the_reset_names_no_public_table_or_function(self) -> None:
        """SQLI-16: a migration that adds a public table or function needs no second edit here."""
        text = ' '.join(path.read_text() for path in sorted((ROOT / app_db.MIGRATIONS).glob('*.sql')))
        created = set(re.findall(r'create (?:table|function) public\.(\w+)', text))
        self.assertGreater(len(created), 20)
        for name in created:
            self.assertNotIn(f'public.{name}', app_db.RESET)
        self.assertIn("'autobots_migrator'::regrole", app_db.RESET)
        self.assertIn('truncate autobots_disposable.migrations', app_db.RESET)

    def test_the_marker_is_checked_before_anything_is_dropped(self) -> None:
        stack = mock.Mock()
        with mock.patch.object(app_db, 'require_marker', side_effect=Refused('no marker')), self.assertRaises(Refused):
            app_db.reset(stack)
        stack.sql.assert_not_called()


class Exposure(unittest.TestCase):
    def test_row_types_come_from_the_columns_authenticated_can_select(self) -> None:
        self.assertIn("has_column_privilege('authenticated'", app_db.EXPOSED_COLUMNS)
        self.assertIn("'SELECT'", app_db.EXPOSED_COLUMNS)
        self.assertIn('authenticated can select', app_db.HEADER)


class SchemaSnapshot(unittest.TestCase):
    def test_lines_that_differ_between_dumps_are_dropped(self) -> None:
        dumped = ('--\n-- PostgreSQL database dump\n--\n\n\\restrict Zq81abc\n\n-- Dumped from database version 17.6\n'
                  '-- Dumped by pg_dump version 17.6\n\nSET statement_timeout = 0;\nSELECT pg_catalog.set_config(\'search_path\', \'\', false);\n'
                  '\n\n\nCREATE TABLE public.runs (\n    id uuid NOT NULL\n);\n\n\n\\unrestrict Zq81abc\n\n')
        text = app_db.normalized_dump(dumped)
        self.assertTrue(text.startswith(app_db.SNAPSHOT_HEADER))
        self.assertNotIn('restrict', text)
        self.assertNotIn('Dumped', text)
        self.assertNotIn('SET ', text)
        self.assertNotIn('set_config', text)
        self.assertIn('CREATE TABLE public.runs (\n    id uuid NOT NULL\n);\n', text)
        self.assertNotIn('\n\n\n', text)
        self.assertTrue(text.endswith(';\n'))

    def test_the_same_schema_dumps_to_the_same_text(self) -> None:
        first = app_db.normalized_dump('\\restrict one\nCREATE SCHEMA app_private;\n\\unrestrict one\n')
        second = app_db.normalized_dump('\\restrict two\nCREATE SCHEMA app_private;\n\\unrestrict two\n')
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
