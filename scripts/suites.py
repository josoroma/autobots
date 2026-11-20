"""Which verification step runs each test file (R-01).

tests/harness/test_suite_claims.py reads this module, so a test file that no step runs, and that
isn't listed below as manual with a reason, fails the harness. Profiles and qualifiers import their
selections from here rather than keeping their own copies. Which scripts each profile runs is
qualification/profiles.py's, and the claim test follows them and their imports, and nothing else, to see
which tests/db checks run (R-65).
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

# Playwright projects, one per environment (R-58). BROWSER_PROJECTS lists each project's spec files, which
# apps/web/playwright.config.ts turns into its testMatch, and each runner passes its project with --project.
BROWSER_PROJECTS = 'apps/web/tests/browser/projects.json'
WEB_PROJECT = 'web'
IDENTITY_PROJECT = 'main'
# Run one test at a time, by title, while qualify_identity arranges each one's state.
ARRANGED_PROJECT = 'arranged'
SLICE_PROJECT = 'slice'
# The projects the full and db profiles run, through qualify_web and qualify_identity.
PROFILE_PROJECTS = (WEB_PROJECT, IDENTITY_PROJECT, ARRANGED_PROJECT, SLICE_PROJECT)
# In no profile: qualify_release.py --ui, persistent_install.py screens, and by hand. MANUAL says why.
RELEASE_PROJECT = 'release'
INSTALL_CURRENT_PROJECT = 'install-current'
INSTALL_PROJECT = 'install'
MANUAL_PROJECTS = (RELEASE_PROJECT, INSTALL_CURRENT_PROJECT, INSTALL_PROJECT)

MANUAL = {
    'tests/db/checks/browser_executor_check.py': 'Run by `qualify_browser_executor.py`, live: it needs the browser images '
                                                 'and outbound network (Decision 0018).',
    'tests/db/checks/browse_goal_check.py': 'Run by `qualify_browse_goal.py`, a live check of browse_goal through the '
                                            'real gateway and the isolated browser (Decision 0020).',
    'tests/db/checks/browser_use_check.py': 'Run by `qualify_browser_executor.py`, live: browse_goal on browser-use in '
                                            'the box needs the three images and outbound network (Decision 0035 Y8).',
    'apps/web/tests/browser/install.spec.ts': 'Read-only on the persistent install, run by hand with `--project '
                                              'install`, as US-11.3 ran it for its local app and upgrade checks.',
    'apps/web/tests/browser/install-current.spec.ts': 'Read-only on the persistent install, run by '
                                                      '`persistent_install.py screens` with `--project '
                                                      'install-current` (Decision 0023).',
    'apps/web/tests/browser/release-latency.spec.ts': "US-10.1's timing, run only by `qualify_release.py --ui` "
                                                      'with `--project release`, against the real API with the '
                                                      'worker stopped.',
    'tests/toolchain/test_reproducible.py': 'Builds copies from package registries, so it needs the network.',
    'tests/toolchain/test_non_mutating.py': 'Its launcher checks (N7) run offline in full. Its other classes '
                                             'build or need a prepared disposable copy, so they stay manual.',
}
