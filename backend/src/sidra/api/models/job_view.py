from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from sidra.maintenance.job import Job
from sidra.maintenance.job_state import JobState


class JobView(BaseModel):
    """The one job, as the screen polls it.

    There is no id: the app holds a single slot, because every job it runs is atomic and so a job
    lost to a restart leaves nothing half-finished to go back to.
    """

    kind: str
    state: JobState
    phase: str
    done: int
    total: int
    started_at: datetime
    finished_at: datetime | None
    detail: str
    error: str

    @classmethod
    def of(cls, job: Job) -> JobView:
        return cls(
            kind=job.kind,
            state=job.state,
            phase=job.phase,
            done=job.done,
            total=job.total,
            started_at=job.started_at,
            finished_at=job.finished_at,
            detail=job.detail,
            error=job.error,
        )
