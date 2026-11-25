"""Each verification profile, once, as data (refactor plan R-65, SCRP-12).

verify.py builds every plan from these steps, harness_lib.report_state reads which checks a passing report
holds, harness_lib.check_domains follows the scripts a profile runs, and evidence.py holds a cited check to
the class and transport declared here. A step's class and model transport are DH-09.2's
(PRD-Development-Harness DH-09.2), in the vocabulary of qualification/records.py.

An argument written `{name}` is filled in by verify.py: `{python}` is the verifier's interpreter, `{node}`
the pinned Node, `{web_bin}` the web app's package binaries, and the test selections are scripts/suites.py's.
A step with no arguments is built by toolchain.check_steps from the tools it found.
"""
from __future__ import annotations

from dataclasses import dataclass

from qualification.records import ModelTransport, VerificationClass

# A step's deadline unless it names its own; the harness suite has used up to 27 of its 60 seconds (XTOL-16).
SHORT = 120.0
LONG = 600.0
# The identity qualifier runs every browser suite and the slice; it took 615 seconds alone on 2026-11-25.
IDENTITY_SECONDS = 900.0
HARNESS_SECONDS = 60.0
# A step whose test selection is a tuple takes each item as its own argument.
SPREAD = '{toolchain_offline}'


@dataclass(frozen=True)
class CheckStep:
    """One check of a profile. `domains` are the change domains for which `fast` runs it; none means only `full`
    does. A self-reporting step exits 2 for a missing prerequisite, which is recorded as an error, not a failure."""

    id: str
    argv: tuple[str, ...] | None = None
    cwd: str = '.'
    timeout: float = SHORT
    klass: VerificationClass = 'static'
    transport: ModelTransport = 'none'
    self_reporting: bool = False
    domains: frozenset[str] = frozenset()
    commanded: bool = True

    @property
    def script(self) -> str | None:
        """The scripts/ file this step runs with the verifier's interpreter, or None."""
        argv = self.argv or ()
        return argv[1] if len(argv) > 1 and argv[0] == '{python}' and argv[1].startswith('scripts/') else None


@dataclass(frozen=True)
class Profile:
    """A profile's own steps, after the harness checks every profile runs. `selects_by_change` lets a step outside
    the changed scope be recorded `not_run`; `docker` steps get HOME for the Docker CLI and need a prepared tree."""

    id: str
    steps: tuple[CheckStep, ...]
    scope: str
    not_tested: tuple[str, ...]
    selects_by_change: bool = False
    docker: bool = False

    @property
    def step_ids(self) -> frozenset[str]:
        return frozenset(step.id for step in self.steps)

    def in_domain(self, domain: str) -> frozenset[str]:
        return frozenset(step.id for step in self.steps if domain in step.domains)

    @property
    def scripts(self) -> tuple[str, ...]:
        return tuple(script for step in self.steps if (script := step.script) is not None)


HARNESS_STEPS = (
    CheckStep('project_configuration', commanded=False),
    CheckStep('backlog_validation', ('{python}', 'scripts/specs.py', 'validate'), timeout=HARNESS_SECONDS),
    CheckStep('harness_behavior_tests', ('{python}', '-m', 'unittest', 'discover', '-s', 'tests/harness', '-p', '{harness_pattern}', '-v'),
              timeout=HARNESS_SECONDS, klass='mock'),
)
# Recorded by the verifier after every profile but harness: nothing was installed or rewritten.
GUARD = CheckStep('non_mutation_guard', commanded=False)

PYTHON, WEB, REPO_PYTHON = frozenset({'python'}), frozenset({'web'}), frozenset({'repo_python'})
APPLICATION_STEPS = (
    CheckStep('python_lock', domains=PYTHON),
    CheckStep('python_env', domains=PYTHON),
    CheckStep('ruff_check', domains=PYTHON),
    CheckStep('ruff_format', domains=PYTHON),
    CheckStep('mypy', timeout=LONG, domains=PYTHON),
    CheckStep('pytest', timeout=LONG, klass='mock', transport='mock', domains=PYTHON),
    # R-07: repository Python, from the root, under ruff.toml and mypy.ini.
    CheckStep('repo_ruff_check', domains=REPO_PYTHON),
    CheckStep('repo_mypy', timeout=LONG, domains=REPO_PYTHON),
    CheckStep('node_lock', domains=WEB),
    CheckStep('node_version', domains=WEB),
    CheckStep('lint', timeout=LONG, domains=WEB),
    CheckStep('format_check', domains=WEB),
    CheckStep('typegen', domains=WEB),
    CheckStep('typecheck', timeout=LONG, domains=WEB),
    CheckStep('build', timeout=LONG),
    CheckStep('contract_drift', ('{python}', 'scripts/generate_contracts.py', 'check'), self_reporting=True, domains=PYTHON | WEB),
    CheckStep('api_client_typecheck', ('{web_bin}/tsc', '-p', 'packages/api-client'), domains=WEB),
    # Globs, which Node expands itself, so a new test file can't be left out (R-01).
    CheckStep('api_client_tests', ('{node}', '--test', '{api_client_tests}'), klass='mock', domains=WEB),
    CheckStep('web_unit_tests', ('{node}', '--test', '{web_unit_tests}'), klass='mock', domains=WEB),
    CheckStep('browser_qualification', ('{python}', 'scripts/qualify_web.py'), timeout=LONG, klass='local_runtime', self_reporting=True),
    CheckStep('fault_qualification', ('{python}', 'scripts/qualify_faults.py'), timeout=LONG, klass='mock', transport='mock',
              self_reporting=True),
    # The offline part of tests/toolchain: scope, manifest pins and launchers. suites.MANUAL says why the rest stays manual.
    CheckStep('toolchain_scope_tests', ('{python}', '-m', 'unittest', SPREAD), cwd='tests/toolchain'),
)


def qualifier(step_id: str, script: str, *arguments: str, transport: ModelTransport = 'none', timeout: float = LONG) -> CheckStep:
    """A disposable qualifier: it starts and removes its own Docker projects, and says when one can't start."""
    return CheckStep(step_id, ('{python}', script, *arguments), timeout=timeout, klass='disposable', transport=transport,
                     self_reporting=True)


# What no harness or application profile tests. The operations list is what its three qualifiers each record as not
# established, plus what the runner adds.
NOT_TESTED =('Claude event delivery', 'Supabase', 'Docker', 'OpenRouter inference', 'complete H0/H1')
PROFILES: dict[str, Profile] = {profile.id: profile for profile in (
    Profile('harness', (), 'Project configuration, backlog structure and deterministic harness fixtures only',
            ('application', *NOT_TESTED)),
    Profile('fast', APPLICATION_STEPS,
            'Harness checks plus local static checks, focused tests and, for full, the production build and the shell and appearance browser specs',
            NOT_TESTED, selects_by_change=True),
    Profile('full', APPLICATION_STEPS,
            'Harness checks plus local static checks, focused tests and, for full, the production build and the shell and appearance browser specs',
            NOT_TESTED),
    # The children of app_db and qualify_identity drive runs with a scripted model.
    Profile('db', (qualifier('disposable_qualification', 'scripts/disposable_db.py', 'qualify'),
                   qualifier('supabase_stack_qualification', 'scripts/supabase_stack.py', 'qualify'),
                   qualifier('app_db_qualification', 'scripts/app_db.py', 'qualify', transport='mock'),
                   qualifier('identity_qualification', 'scripts/qualify_identity.py', transport='mock', timeout=IDENTITY_SECONDS),
                   qualifier('persistent_apply_qualification', 'scripts/qualify_persistent_apply.py')),
            'Harness checks plus the pinned release and the application migrations and seeds, on disposable targets',
            ('the persistent database', 'Claude event delivery', 'OpenRouter inference', 'complete H0/H1'), docker=True),
    # Their fixture workers run a scripted model.
    Profile('operations', (qualifier('operations_qualification', 'scripts/qualify_operations.py', transport='mock'),
                           qualifier('backup_qualification', 'scripts/qualify_backup.py', transport='mock'),
                           qualifier('upgrade_qualification', 'scripts/qualify_upgrade.py', transport='mock')),
            'Harness checks plus the operations, backup and upgrade runbooks, on disposable Compose projects with a '
            'scripted model. Disposable evidence only, not H1 or product acceptance',
            ('H1', 'product acceptance', 'the persistent stack', 'a real model call', 'a real credential',
             'a real image or framework version change', 'Mac sleep', 'resource use under load',
             'protection from losing this Mac', 'Claude event delivery', 'OpenRouter inference'), docker=True),
)}

HARNESS_CHECKS = frozenset(step.id for step in HARNESS_STEPS)
UNCOMMANDED_CHECKS = frozenset(step.id for step in (*HARNESS_STEPS, GUARD) if not step.commanded)
# fast's selection by change domain, and each profile's own steps.
PYTHON_STEPS = PROFILES['full'].in_domain('python')
WEB_STEPS = PROFILES['full'].in_domain('web')
REPO_PYTHON_STEPS = PROFILES['full'].in_domain('repo_python')
FULL_CHECKS = PROFILES['full'].step_ids
FULL_ONLY_CHECKS = FULL_CHECKS - PYTHON_STEPS - WEB_STEPS - REPO_PYTHON_STEPS
DB_CHECKS = PROFILES['db'].step_ids
OPERATIONS_CHECKS = PROFILES['operations'].step_ids


def every_step() -> dict[str, CheckStep]:
    """Each registered step by its id. A step two profiles share is the same object."""
    found = {step.id: step for step in (*HARNESS_STEPS, GUARD)}
    for profile in PROFILES.values():
        found.update((step.id, step) for step in profile.steps)
    return found


STEPS = every_step()


def required_checks(profile: str) -> frozenset[str]:
    """What a passing report of `profile` holds, each passed: the harness checks, the guard after any other profile,
    and every own step unless the profile may leave one out."""
    definition = PROFILES[profile]
    required = set(HARNESS_CHECKS)
    if profile != 'harness':
        required.add(GUARD.id)
    if not definition.selects_by_change:
        required |= definition.step_ids
    return frozenset(required)


def declared(step_id: str) -> tuple[VerificationClass, ModelTransport]:
    """A step's class and model transport. An unregistered id is a static check with no model."""
    step = STEPS.get(step_id)
    return (step.klass, step.transport) if step is not None else ('static', 'none')
