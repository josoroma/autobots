"""Which verification step runs each test file (R-01).

tests/harness/test_suite_claims.py reads this module, so a test file that no step runs, and that
isn't listed below as manual with a reason, fails the harness. Profiles and qualifiers import their
selections from here rather than keeping their own copies.
"""

# unittest discovery pattern for tests/harness.
HARNESS_PATTERN = 'test_*.py'

# Node's test runner expands these globs itself (Node 22). Decision 0027 keeps web unit tests on
# `node --test` over modules without JSX.
WEB_UNIT_TESTS = 'apps/web/tests/unit/**/*.test.ts'
API_CLIENT_TESTS = 'packages/api-client/tests/**/*.test.ts'

# The offline part of tests/toolchain, run by module name from that folder. The rest builds copies
# from package registries, so it stays manual.
TOOLCHAIN_OFFLINE = ('test_scaffold_scope', 'test_manifests', 'test_non_mutating.Launchers')

# Playwright filters. Each one selects the spec files whose path contains it.
WEB_SUITES = ('appearance', 'boundary', 'browser/tools.spec')
IDENTITY_SUITES = ('browser/workflows.spec', 'browser/operations', 'approvals', 'effects', 'experts', 'models',
                   'composer', 'home', 'workflow-list', 'identity', 'settings', 'runs', 'run-panel', 'search',
                   'new-run', 'stream-result', 'workspace-choice', 'artifacts', 'run-workspace')
# Run one test at a time, by title, while qualify_identity arranges each one's state.
QUALIFICATION_SUITE = 'browser/qualification'
SAVED_CHOICE_SUITE = 'browser/saved-choice'
READINESS_SUITE = 'browser/readiness'
IDENTITY_TITLED_SUITES = (QUALIFICATION_SUITE, SAVED_CHOICE_SUITE, READINESS_SUITE)
SLICE_SUITES = ('slice',)

# The qualifiers the db and operations profiles run, as (step id, script, arguments...). verify.py
# builds those steps from these, and the claim test follows them and their imports, and nothing
# else, to see which tests/db checks run.
DB_QUALIFIERS = (
    ('disposable_qualification', 'scripts/disposable_db.py', 'qualify'),
    ('supabase_stack_qualification', 'scripts/supabase_stack.py', 'qualify'),
    ('app_db_qualification', 'scripts/app_db.py', 'qualify'),
    ('identity_qualification', 'scripts/qualify_identity.py'),
    ('persistent_apply_qualification', 'scripts/qualify_persistent_apply.py'),
)
OPERATIONS_QUALIFIERS = (
    ('operations_qualification', 'scripts/qualify_operations.py'),
    ('backup_qualification', 'scripts/qualify_backup.py'),
    ('upgrade_qualification', 'scripts/qualify_upgrade.py'),
)
# full's qualifiers, which verify.py names in tool_plan.
FULL_QUALIFIERS = ('scripts/qualify_faults.py', 'scripts/qualify_web.py')

MANUAL = {
    'tests/db/browser_executor_check.py': 'Run by `qualify_browser_executor.py`, live: it needs the browser images and '
                                          'outbound network (Decision 0018).',
    'tests/db/browse_goal_check.py': 'Run by `qualify_browse_goal.py`, a live check of browse_goal through the real '
                                     'gateway and the isolated browser (Decision 0020).',
    'tests/db/product_inference_check.py': 'Run by `qualify_worker_inference.py` and `qualify_mac_sleep.py`, which '
                                           'qualify the worker entry point and a real Mac sleep, on purpose.',
    'apps/web/tests/browser/install.spec.ts': 'Read-only on the persistent install, run by hand as the upgrade and '
                                              'operations runbooks say.',
    'apps/web/tests/browser/install-current.spec.ts': 'Read-only on the persistent install, run by '
                                                      '`persistent_install.py screens` (Decision 0023).',
    'apps/web/tests/browser/release-latency.spec.ts': "US-10.1's timing, run only by `qualify_release.py --ui` "
                                                      'against the real API with the worker stopped.',
    'tests/toolchain/test_reproducible.py': 'Builds copies from package registries, so it needs the network.',
    'tests/toolchain/test_non_mutating.py': 'Its launcher checks (N7) run offline in full. Its other classes '
                                             'build or need a prepared disposable copy, so they stay manual.',
}
