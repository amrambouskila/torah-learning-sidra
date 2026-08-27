"""The one job slot, and why it is only one."""

from __future__ import annotations

import pytest

from sidra.maintenance.job_registry import JobRegistry
from sidra.maintenance.job_state import JobState


def test_it_starts_empty() -> None:
    registry = JobRegistry()
    assert registry.current is None
    assert registry.is_busy is False


def test_a_started_job_is_running_and_claims_the_slot() -> None:
    registry = JobRegistry()
    job = registry.start("refresh")
    assert job.kind == "refresh"
    assert job.state is JobState.RUNNING
    assert registry.is_busy is True
    assert registry.current is job


def test_a_second_job_is_refused_while_one_runs() -> None:
    """Two crawls at once would hammer Sefaria; two rebuilds would fight over the catalog."""
    registry = JobRegistry()
    registry.start("refresh")
    with pytest.raises(ValueError, match="refresh job is already running"):
        registry.start("seed")


def test_the_slot_frees_when_a_job_succeeds_and_keeps_what_it_did() -> None:
    registry = JobRegistry()
    job = registry.start("seed")
    job.step("writing the catalog", 4, 11)

    registry.finish(job, "277 works, 27,250 units")

    assert registry.is_busy is False
    assert job.state is JobState.DONE
    assert job.detail == "277 works, 27,250 units"
    assert job.phase == ""
    assert job.finished_at is not None
    assert registry.current is job  # still readable, so the screen can report it


def test_the_slot_frees_when_a_job_fails_and_keeps_why() -> None:
    registry = JobRegistry()
    job = registry.start("calendar")

    registry.abandon(job, "Hebcal answered 429")

    assert registry.is_busy is False
    assert job.state is JobState.FAILED
    assert job.error == "Hebcal answered 429"
    assert job.finished_at is not None


def test_a_finished_job_is_replaced_by_the_next() -> None:
    """One slot, no history. The screen shows what is happening now, or what happened last."""
    registry = JobRegistry()
    first = registry.start("seed")
    registry.finish(first, "done")

    second = registry.start("refresh")

    assert registry.current is second
    assert second.state is JobState.RUNNING


def test_progress_reports_a_pair_rather_than_a_percentage() -> None:
    """ "works 114 of 279" says something a bar alone cannot."""
    registry = JobRegistry()
    job = registry.start("refresh")
    job.step("crawling Bavli", 4, 11)
    assert (job.phase, job.done, job.total) == ("crawling Bavli", 4, 11)


def test_a_job_with_no_natural_tick_reports_a_phase_alone() -> None:
    registry = JobRegistry()
    job = registry.start("seed")
    job.step("reading the snapshot")
    assert (job.done, job.total) == (0, 0)
