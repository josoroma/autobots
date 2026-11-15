"""What a run's transition does to its job, as one pure rule (PRUN-06, SP-010, SP-012).

A queued run waits for a claim. A run that is running or verifying stays with the worker holding its
lease. A run being cancelled stays with a live owner, which settles it, and is queued for one
otherwise. A pause by a person or by the system leaves a live owner its job until its next check,
while the worker's own suspension ends its claim. In every other state no worker owns the run.
"""

import pytest

from autobots.domain.runs import Actor, JobStatus, LockedJob, RunStatus, job_status_after

JOBS = {
    "no row": LockedJob(None, None, False),
    "queued": LockedJob(JobStatus.QUEUED, 2, False),
    "live claim": LockedJob(JobStatus.CLAIMED, 3, True),
    "expired claim": LockedJob(JobStatus.CLAIMED, 3, False),
    "done": LockedJob(JobStatus.DONE, 3, False),
}
Q, D, KEEP = JobStatus.QUEUED, JobStatus.DONE, None
EVERY_ACTOR = tuple(Actor)
# Per status and actor, what each job in JOBS becomes, in order. KEEP leaves it as it is.
TABLE: dict[RunStatus, dict[Actor, tuple[JobStatus | None, ...]]] = {
    RunStatus.QUEUED: dict.fromkeys(EVERY_ACTOR, (Q, Q, Q, Q, Q)),
    RunStatus.RUNNING: dict.fromkeys(EVERY_ACTOR, (KEEP, KEEP, KEEP, KEEP, KEEP)),
    RunStatus.VERIFYING: dict.fromkeys(EVERY_ACTOR, (KEEP, KEEP, KEEP, KEEP, KEEP)),
    RunStatus.CANCELLING: dict.fromkeys(EVERY_ACTOR, (Q, Q, KEEP, Q, Q)),
    RunStatus.PAUSED: {
        Actor.USER: (D, D, KEEP, D, D),
        Actor.SYSTEM: (D, D, KEEP, D, D),
        Actor.WORKER: (D, D, D, D, D),
    },
    RunStatus.WAITING_INPUT: dict.fromkeys(EVERY_ACTOR, (D, D, D, D, D)),
    RunStatus.WAITING_APPROVAL: dict.fromkeys(EVERY_ACTOR, (D, D, D, D, D)),
    RunStatus.SUCCEEDED: dict.fromkeys(EVERY_ACTOR, (D, D, D, D, D)),
    RunStatus.FAILED: dict.fromkeys(EVERY_ACTOR, (D, D, D, D, D)),
    RunStatus.CANCELLED: dict.fromkeys(EVERY_ACTOR, (D, D, D, D, D)),
}


def test_the_table_covers_every_status_and_actor() -> None:
    assert set(TABLE) == set(RunStatus)
    for row in TABLE.values():
        assert set(row) == set(Actor)
        assert all(len(expected) == len(JOBS) for expected in row.values())


@pytest.mark.parametrize("following", list(RunStatus))
@pytest.mark.parametrize("actor", list(Actor))
def test_the_job_after_each_transition(following: RunStatus, actor: Actor) -> None:
    observed = tuple(job_status_after(following, actor, job) for job in JOBS.values())
    assert observed == TABLE[following][actor], dict(zip(JOBS, observed, strict=True))


def test_an_approval_expirys_pause_leaves_a_live_owner_its_job() -> None:
    """The expiry is the system's pause (Decision 0029 F5). It keeps the rule a person's pause had:
    a live owner sees the pause at its next check, saves its step and lets go itself."""
    live = JOBS["live claim"]
    assert job_status_after(RunStatus.PAUSED, Actor.SYSTEM, live) is None
    assert job_status_after(RunStatus.PAUSED, Actor.USER, live) is None
    assert job_status_after(RunStatus.PAUSED, Actor.SYSTEM, JOBS["expired claim"]) is D


def test_only_a_live_claim_at_the_generation_holds_the_run() -> None:
    live = JOBS["live claim"]
    assert live.live_claim and live.held_by(3)
    assert not live.held_by(2) and not live.held_by(4)
    for name in ("no row", "queued", "expired claim", "done"):
        job = JOBS[name]
        assert not job.live_claim and not job.held_by(3), name
