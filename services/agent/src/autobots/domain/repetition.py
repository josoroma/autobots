"""How often a recurring failure is worth a log line, by `autobots.operations.logs` conventions.

Pure, so the run lifecycle uses it without importing the operations layer (STD-01, R-33).
"""

from dataclasses import dataclass


@dataclass
class Repeated:
    """A failure that can recur on every pass, such as a lost connection. Its first occurrence and
    every `every`-th are worth a line; `cleared` starts the count again once it works."""

    every: int = 30
    count: int = 0

    def failed(self) -> bool:
        self.count += 1
        return self.count == 1 or self.count % self.every == 0

    def cleared(self) -> None:
        self.count = 0
