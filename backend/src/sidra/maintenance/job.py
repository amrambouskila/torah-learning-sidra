"""One maintenance job, as the screen sees it.

Progress is a pair rather than a percentage: "works 114 of 279" tells him something a bar alone
cannot, and a job with no natural tick -- rebuilding the catalog is one transaction -- reports its
phase and leaves ``total`` at zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sidra.maintenance.job_state import JobState


@dataclass(slots=True)
class Job:
    """A long operation the screen can watch. Mutated in place by the task running it."""

    kind: str
    """``seed``, ``calendar`` or ``refresh`` -- what the button said."""

    started_at: datetime
    state: JobState = JobState.RUNNING
    phase: str = ""
    """What it is doing now, in his words rather than the code's."""

    done: int = 0
    total: int = 0
    """Zero when the job has no natural tick; the screen shows the phase alone."""

    finished_at: datetime | None = None
    detail: str = ""
    """What it achieved, on success. Set once, at the end."""

    error: str = ""
    """Why it stopped, on failure. Empty otherwise."""

    @property
    def is_running(self) -> bool:
        return self.state is JobState.RUNNING

    def step(self, phase: str, done: int = 0, total: int = 0) -> None:
        """Report progress. Called from inside the work, so it stays cheap and never raises."""
        self.phase = phase
        self.done = done
        self.total = total

    def succeed(self, detail: str) -> None:
        self.state = JobState.DONE
        self.phase = ""
        self.detail = detail

    def fail(self, error: str) -> None:
        self.state = JobState.FAILED
        self.phase = ""
        self.error = error
