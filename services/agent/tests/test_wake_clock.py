"""What a real sleep looks like to a process, from its two clocks."""

from autobots.application.worker_leases import WAKE_WINDOW_SECONDS, WakeClock


class Clocks:
    def __init__(self) -> None:
        self.wall = 1000.0
        self.mono = 500.0

    def clock(self) -> WakeClock:
        return WakeClock(wall=lambda: self.wall, mono=lambda: self.mono)


def test_time_passing_normally_is_not_a_sleep() -> None:
    clocks = Clocks()
    wake = clocks.clock()
    clocks.wall += 500
    clocks.mono += 500
    assert wake.check() == 0
    assert not wake.just_woke()


def test_a_stall_with_both_clocks_running_is_not_a_sleep() -> None:
    """SIGSTOP or a hung process: the monotonic clock keeps running, so nothing is forgiven."""
    clocks = Clocks()
    wake = clocks.clock()
    clocks.wall += 600
    clocks.mono += 600
    assert wake.check() == 0


def test_a_short_gap_is_not_a_sleep() -> None:
    clocks = Clocks()
    wake = clocks.clock()
    clocks.wall += 10
    assert wake.check() == 0


def test_the_wall_clock_running_ahead_is_a_sleep_for_a_while() -> None:
    clocks = Clocks()
    wake = clocks.clock()
    clocks.wall += 300
    assert wake.check() == 300
    assert wake.just_woke()
    clocks.mono += WAKE_WINDOW_SECONDS + 1
    clocks.wall += WAKE_WINDOW_SECONDS + 1
    assert not wake.just_woke()
