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

MANUAL = {
    'apps/web/tests/browser/install.spec.ts': 'Read-only on the persistent install, run by hand as the upgrade and '
                                              'operations runbooks say.',
    'apps/web/tests/browser/install-current.spec.ts': 'Read-only on the persistent install, run by '
                                                      '`persistent_install.py screens` (Decision 0023).',
    'apps/web/tests/browser/release-latency.spec.ts': "US-10.1's timing, run only by `qualify_release.py --ui` "
                                                      'against the real API with the worker stopped.',
    'tests/toolchain/test_reproducible.py': 'Builds copies from package registries, so it needs the network.',
    'tests/toolchain/test_non_mutating.py': 'Only its launcher checks (N7) are offline. The rest bootstrap '
                                             'disposable copies from package registries.',
}
