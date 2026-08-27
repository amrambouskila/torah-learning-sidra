"""The one job slot.

Not a table and not a queue. Every operation this runs is atomic -- the catalog rebuild is a single
transaction, the calendar stores in one after fetching, and the crawl writes its snapshot only once
it has finished -- so a job that dies with the container leaves nothing half-written. There is
nothing to resume and nothing to clean up, which leaves progress as the only thing a job system has
to provide here, and one mutable slot provides it.

One at a time is a feature rather than a limitation: it stops two crawls hammering Sefaria at once
and two rebuilds fighting over the same catalog.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sidra.maintenance.job import Job


class JobRegistry:
    """Holds the current or last job. Lives on ``app.state``, and dies with the process."""

    def __init__(self) -> None:
        self._job: Job | None = None

    @property
    def current(self) -> Job | None:
        """The running job, or the last one to finish, or None if none has ever run."""
        return self._job

    @property
    def is_busy(self) -> bool:
        return self._job is not None and self._job.is_running

    def start(self, kind: str) -> Job:
        """Claim the slot. The caller must have checked ``is_busy`` and answered 409 if it was."""
        if self.is_busy:
            raise ValueError(f"a {self._job.kind if self._job else '?'} job is already running")
        self._job = Job(kind=kind, started_at=datetime.now(UTC))
        return self._job

    def finish(self, job: Job, detail: str) -> None:
        job.succeed(detail)
        job.finished_at = datetime.now(UTC)

    def abandon(self, job: Job, error: str) -> None:
        job.fail(error)
        job.finished_at = datetime.now(UTC)
