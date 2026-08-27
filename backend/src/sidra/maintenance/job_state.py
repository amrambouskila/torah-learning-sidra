"""Where a maintenance job has got to."""

from __future__ import annotations

from enum import StrEnum


class JobState(StrEnum):
    """The three ends a job can be in, and the one it passes through."""

    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
