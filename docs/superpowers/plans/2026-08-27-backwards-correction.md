# Correcting a Sidra — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the ledger two levers it has never had — one that moves a track's *actual* position backwards to correct a mistyped advance, and one that moves a track's *scheduled* position to correct a miscalibrated anchor.

**Architecture:** `actual_ordinal` stays `MAX(Advance.to_ordinal)`; a backwards correction truncates advance rows so they tell the truth, which leaves every downstream consumer (Stats, streak, pace, rail, ceilings) untouched. The schedule side exposes the two operands of `scheduled = anchor_ordinal + f(calendar)` as two named routes, because they disagree about the past. Both arrive as new sibling endpoints so `POST /advance` and `PATCH /tracks/{id}` are not modified at all.

**Tech Stack:** Python 3.13 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 async + asyncpg · PostgreSQL 16 · uv · ruff · pytest + pytest-asyncio + pytest-cov · React 18 + TypeScript strict + Vite + pnpm + Redux Toolkit + Vitest

**Spec:** `docs/superpowers/specs/2026-08-27-backwards-correction-design.md` — read it before Task 1. The plan argues from it.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **NEVER run any git command that changes state.** No `git add`, `git commit`, `git checkout`, `git branch`, `git stash`, `git reset`, `git restore`, `git tag`, `git push`, `git pull`, `git merge`, `git rebase`. Amram manages git himself. Each task ends by *reporting* changed files and a **suggested** commit message. Read-only git (`status`, `diff`, `log`, `show`) is permitted. This overrides the commit steps that normally appear in plans.
- `from __future__ import annotations` at the top of every Python module.
- Full type annotations on every function. **No `Any` in signatures.** No bare `except`.
- **One concept per file.** No `utils.py` grab-bags.
- ruff: `line-length = 120`, `select = ["E","F","I","N","UP","ANN","S"]`; `tests/*` ignores `S101`, `S105`, `S106`.
- Coverage is gated at **100%** (`fail_under = 100` in `[tool.coverage.report]`). `addopts` carries no `--cov`, so the gate only fires when `--cov` is passed — never add `--cov-fail-under` to `addopts`.
- **No mocking of the database.** Integration tests use the real compose Postgres via the `db_session` fixture. Start it with `docker compose up -d postgres` from the project root before running them.
- **No test touches the network** except tests marked `live`. Run backend suites with `-m "not live"`.
- Hebrew is never hand-encoded — it comes verbatim from Sefaria or from `to_gematria`. No numeric character references. Nothing in this plan authors Hebrew.
- **Never adjust a measured constant to make a test pass** (`CLAUDE.md` §1). If a measured fact appears contradicted, stop and say so.
- Ports are unchanged: frontend 5285, backend 8285, Postgres host 5524.

### Commands

| Purpose | Command |
|---|---|
| Backend one file | `cd backend && uv run pytest tests/path/test_x.py -v -m "not live"` |
| Backend one test | `cd backend && uv run pytest tests/path/test_x.py::test_name -v -m "not live"` |
| Backend full + coverage gate | `cd backend && uv run pytest -m "not live" --cov=src/sidra --cov-report=term-missing` |
| Backend lint | `cd backend && uv run ruff check .` |
| Frontend tests | `cd frontend && pnpm test` |
| Frontend coverage | `cd frontend && pnpm coverage` |
| Frontend lint | `cd frontend && pnpm lint` |
| Frontend typecheck + build | `cd frontend && pnpm build` |

### Test-fixture arithmetic you will need repeatedly

`tests/api/conftest.py` seeds the miniature sidra from `tests/db/test_seed_tracks.py`. Its Neviim catalog is Joshua 24, Judges 21, I Samuel 31, Jeremiah 52 perakim, concatenated:

```
Joshua      1 – 24
Judges     25 – 45
I Samuel   46 – 76
Jeremiah   77 – 128       so Jeremiah N == 76 + N
```

| Thing | Value |
|---|---|
| `AS_OF` | `date(2026, 8, 24)` |
| Neviim `anchor_date` | `AS_OF` |
| Neviim `anchor_ordinal` | **123** (`scheduled_ref: Jeremiah 47`) |
| Neviim opening advance row | `from_ordinal 119 → to_ordinal 120`, `unit_count 1`, `note = SEED_NOTE` |
| Neviim `actual_ordinal` on day 0 | **120** (`current_ref: Jeremiah 44`) |
| Neviim debt on day 0 | **3** — the measured fact |
| Jeremiah 43 / 44 / 47 / 48 / 49 / 50 | 119 / 120 / 123 / 124 / 125 / 126 |
| `SEED_NOTE` | `"Opening position, from the Obsidian sidra."` (`sidra/ledger/seed_tracks.py:36`) |
| Chavrusa track in the fixture | `"David Hadar — Brachot"`, `period = none` |
| Not-yet-begun track in the fixture | `"Likutei Sichot"`, `starts_on = 2026-10-10` |

`on(n)` from `tests/api/conftest.py` returns `{"on": (AS_OF + n days).isoformat()}`.

### Deviations from the spec, decided while planning

Three, all noted here so no reviewer has to rediscover them:

1. **Test locations.** The spec put `test_truncate.py` under `tests/ledger/`. `truncate_to` takes an `AsyncSession`, and this repo puts session-taking ledger tests under `tests/db/` (`tests/db/test_track_state.py`, `tests/db/test_transfer.py`) and keeps `tests/ledger/` for pure functions. So `truncate_to` is tested in `tests/db/test_truncate.py`; `reanchor` and `recalibrate` are pure and stay in `tests/ledger/`.
2. **The unconfirmed-422 message carries no date.** The spec's example named "27 August". Producing it needs an extra query for the straddling row, and the message is already precise without it. It names the delta and both positions instead.
3. **The §5 acceptance test lives in `tests/api/test_schedule_history.py`.** The spec said `tests/stats/test_scheduled_series.py`, but `tests/stats/` holds pure tests and this one needs a seeded session, a calendar and the Stats endpoint.

---

## File Structure

**Backend — created**

| File | Responsibility |
|---|---|
| `backend/src/sidra/ledger/truncation.py` | The frozen dataclass describing what a truncation did. |
| `backend/src/sidra/ledger/truncate.py` | `truncate_to` — rewrite advance rows so `MAX(to_ordinal)` equals a chosen target. |
| `backend/src/sidra/ledger/reanchor.py` | `reanchor` — move `anchor_date` (and `starts_on` when set). |
| `backend/src/sidra/ledger/recalibrate.py` | `recalibrate` — shift `anchor_ordinal` so today's scheduled equals a chosen ordinal. |
| `backend/src/sidra/api/models/position_write.py` | `PositionUpdate` request body. |
| `backend/src/sidra/api/models/schedule_write.py` | `ScheduleUpdate` request body. |
| `backend/src/sidra/api/models/correction_result.py` | `CorrectionResult` response body. |
| `backend/src/sidra/api/routers/track_writes.py` | Every mutating track route. |

**Backend — modified**

| File | Change |
|---|---|
| `backend/src/sidra/api/routers/tracks.py` | Writes move out; keeps `GET ""`, `GET /{id}`, `GET /{id}/rail`, `_rail_span`. |
| `backend/src/sidra/api/app.py` | Mount the new router. |
| `backend/src/sidra/api/models/advance_result.py` | Gains `resolved_ordinal: int`. |
| `backend/src/sidra/ledger/reachable.py` | Docstring — its premise ("there is no undo") is now false. |
| `backend/src/sidra/ledger/cycle.py` | `align_to` docstring — same premise. |

**Frontend — created:** `src/types/CorrectionResult.ts`, `src/utils/correctionPhrase.ts`, `src/components/ScheduleDialog.tsx`
**Frontend — modified:** `src/api/endpoints.ts`, `src/stores/tracksSlice.ts`, `src/types/AdvanceResult.ts`, `src/components/AdvanceDialog.tsx`, `src/screens/TrackScreen.tsx`, `src/screens/TodayScreen.tsx`

**Docs — modified:** `CLAUDE.md` (§4, §8), `docs/status.md`, `docs/versions.md`

---

## Task 1: `truncate_to` — rewriting advance rows

**Files:**
- Create: `backend/src/sidra/ledger/truncation.py`
- Create: `backend/src/sidra/ledger/truncate.py`
- Test: `backend/tests/db/test_truncate.py`

**Interfaces:**
- Consumes: `sidra.db.models.Advance`, `sidra.db.models.Track`, `sidra.ledger.seed_tracks.actual_ordinal`, `sidra.ledger.seed_tracks.SEED_NOTE`
- Produces:
  - `Truncation(from_ordinal: int, to_ordinal: int, removed_advances: int, removed_units: int)` — frozen, slots
  - `async def truncate_to(session: AsyncSession, track: Track, target: int) -> Truncation`

- [ ] **Step 1: Start the database**

```bash
docker compose up -d postgres
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/db/test_truncate.py`:

```python
"""Rewriting advance rows so the ledger's position tells the truth."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Track
from sidra.ledger.seed_tracks import SEED_NOTE, actual_ordinal, seed_tracks
from sidra.ledger.tracks_file import parse_tracks_file
from sidra.ledger.truncate import truncate_to
from tests.db.test_seed_tracks import AS_OF, HEBREW_AS_OF, TRACKS_YAML, _catalog

pytestmark = pytest.mark.integration

JEREMIAH_43 = 119
JEREMIAH_44 = 120
JEREMIAH_48 = 124
JEREMIAH_49 = 125


async def _neviim(session: AsyncSession) -> Track:
    """The seeded Neviim track, standing at Jeremiah 44 with one opening row."""
    await _catalog(session)
    await seed_tracks(session, parse_tracks_file(TRACKS_YAML))
    return (await session.execute(select(Track).where(Track.name_en == "Neviim"))).scalar_one()


async def _advance(session: AsyncSession, track: Track, start: int, end: int) -> None:
    session.add(
        Advance(
            track_id=track.id,
            from_ordinal=start,
            to_ordinal=end,
            unit_count=end - start,
            occurred_at=datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, tzinfo=UTC),
            hebrew_date=HEBREW_AS_OF,
            note=None,
        )
    )
    await session.flush()


async def _rows(session: AsyncSession, track: Track) -> list[Advance]:
    result = await session.execute(
        select(Advance).where(Advance.track_id == track.id).order_by(Advance.from_ordinal)
    )
    return list(result.scalars().all())


async def test_a_straddling_row_is_trimmed_rather_than_deleted(db_session: AsyncSession) -> None:
    """The everyday correction: he said Jeremiah 49 and meant Jeremiah 48."""
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, JEREMIAH_48)

    assert await actual_ordinal(db_session, track) == JEREMIAH_48
    assert result.from_ordinal == JEREMIAH_49
    assert result.to_ordinal == JEREMIAH_48
    assert result.removed_units == 1
    assert result.removed_advances == 0
    rows = await _rows(db_session, track)
    assert [(row.from_ordinal, row.to_ordinal, row.unit_count) for row in rows] == [
        (JEREMIAH_43, JEREMIAH_44, 1),
        (JEREMIAH_44, JEREMIAH_48, 4),
    ]


async def test_a_row_that_already_ends_at_the_target_is_left_alone(db_session: AsyncSession) -> None:
    """No synthetic row is written when the ledger can already say where he is."""
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, JEREMIAH_44)

    assert await actual_ordinal(db_session, track) == JEREMIAH_44
    assert result.removed_advances == 1
    assert result.removed_units == 5
    rows = await _rows(db_session, track)
    assert [(row.from_ordinal, row.to_ordinal) for row in rows] == [(JEREMIAH_43, JEREMIAH_44)]


async def test_correcting_below_the_opening_row_writes_a_new_one(db_session: AsyncSession) -> None:
    """Without this the earliest row's from_ordinal would be a floor no correction could pass."""
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, JEREMIAH_43)

    assert await actual_ordinal(db_session, track) == JEREMIAH_43
    assert result.removed_advances == 2
    rows = await _rows(db_session, track)
    assert len(rows) == 1
    assert (rows[0].from_ordinal, rows[0].to_ordinal, rows[0].unit_count) == (JEREMIAH_43 - 1, JEREMIAH_43, 1)
    # The seeder's note, so Stats keeps excluding it from days learned.
    assert rows[0].note == SEED_NOTE
    # The date of the earliest row it replaces, so history gains no entry dated today.
    assert rows[0].occurred_at.date() == AS_OF
    assert rows[0].hebrew_date == HEBREW_AS_OF


async def test_correcting_to_zero_leaves_the_track_unopened(db_session: AsyncSession) -> None:
    track = await _neviim(db_session)
    await _advance(db_session, track, JEREMIAH_44, JEREMIAH_49)

    result = await truncate_to(db_session, track, 0)

    assert await actual_ordinal(db_session, track) == 0
    assert await _rows(db_session, track) == []
    assert result.to_ordinal == 0
    assert result.removed_units == JEREMIAH_49
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd backend && uv run pytest tests/db/test_truncate.py -v -m "not live"
```

Expected: `ModuleNotFoundError: No module named 'sidra.ledger.truncate'`

- [ ] **Step 4: Write `Truncation`**

Create `backend/src/sidra/ledger/truncation.py`:

```python
"""What one backwards correction did."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Truncation:
    """The shape of a correction, for the toast that reports it."""

    from_ordinal: int
    """Where the track stood before."""

    to_ordinal: int
    """Where it stands now."""

    removed_advances: int
    """Rows deleted outright. A row trimmed rather than deleted is not counted here."""

    removed_units: int
    """How far the position dropped, which is what he wants told: ``from_ordinal - to_ordinal``."""
```

- [ ] **Step 5: Write `truncate_to`**

Create `backend/src/sidra/ledger/truncate.py`:

```python
"""Move a track's actual position backwards by rewriting the rows behind it.

``actual_ordinal`` is ``MAX(Advance.to_ordinal)``, and every consumer of the ledger -- Stats, the
streak, the pace projection, the rail, both ceilings -- is built on advances that only ever move
forward. Rather than teach all of them about backwards motion, a correction makes the rows tell the
truth: what was never learned stops being recorded.

The synthetic opening row in the last branch is the seeder's own idiom, and it is what lets a
correction pass below the earliest row's ``from_ordinal`` instead of treating it as a floor.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sidra.db.models import Advance, Track
from sidra.ledger.seed_tracks import SEED_NOTE, actual_ordinal
from sidra.ledger.truncation import Truncation


async def truncate_to(session: AsyncSession, track: Track, target: int) -> Truncation:
    """Rewrite the track's advances so its position is exactly ``target``.

    Rows are contiguous -- each opens where the previous closed -- so a target inside any row's
    span is trimmed by the second branch and ends there. The third branch is therefore reached only
    once every row has gone, which is why ``doomed`` is never empty when it runs.
    """
    before = await actual_ordinal(session, track)
    rows = list(
        (
            await session.execute(
                select(Advance).where(Advance.track_id == track.id).order_by(Advance.from_ordinal)
            )
        )
        .scalars()
        .all()
    )

    doomed = [row for row in rows if row.from_ordinal >= target]
    survivors = [row for row in rows if row.from_ordinal < target]
    for row in doomed:
        await session.delete(row)

    straddler = next((row for row in survivors if row.to_ordinal > target), None)
    if straddler is not None:
        straddler.to_ordinal = target
        straddler.unit_count = target - straddler.from_ordinal
    elif target > 0 and not any(row.to_ordinal == target for row in survivors):
        opening = max(0, target - track.rate)
        session.add(
            Advance(
                track_id=track.id,
                from_ordinal=opening,
                to_ordinal=target,
                unit_count=target - opening,
                occurred_at=doomed[0].occurred_at,
                hebrew_date=doomed[0].hebrew_date,
                note=SEED_NOTE,
            )
        )

    await session.flush()
    return Truncation(
        from_ordinal=before,
        to_ordinal=target,
        removed_advances=len(doomed),
        removed_units=before - target,
    )
```

- [ ] **Step 6: Run the test to verify it passes**

```bash
cd backend && uv run pytest tests/db/test_truncate.py -v -m "not live"
```

Expected: 4 passed

- [ ] **Step 7: Lint**

```bash
cd backend && uv run ruff check src/sidra/ledger/truncate.py src/sidra/ledger/truncation.py tests/db/test_truncate.py
```

Expected: `All checks passed!`

- [ ] **Step 8: Report — do not commit**

Print the created files and this suggested message for Amram:

```
feat(ledger): truncate advances to move a position backwards
```

---

## Task 2: `reanchor` and `recalibrate` — the two schedule operands

**Files:**
- Create: `backend/src/sidra/ledger/reanchor.py`
- Create: `backend/src/sidra/ledger/recalibrate.py`
- Test: `backend/tests/ledger/test_reanchor.py`
- Test: `backend/tests/ledger/test_recalibrate.py`

**Interfaces:**
- Consumes: `sidra.db.models.Track`
- Produces:
  - `def reanchor(track: Track, started_on: date) -> None`
  - `def recalibrate(track: Track, desired: int, scheduled_today: int) -> None`

Both mutate the `Track` in place and return `None`, exactly as `rebase_start` does (`sidra/ledger/rebase.py:31`). Neither validates — guards live in the router, which is where `set_start_date` puts them (`sidra/api/routers/tracks.py:161-197`).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/ledger/test_reanchor.py`:

```python
"""Moving the day a track's schedule began counting."""

from __future__ import annotations

from datetime import date

from sidra.db.models import Track
from sidra.ledger.category import Category
from sidra.ledger.period import Period
from sidra.ledger.reanchor import reanchor
from sidra.ledger.schedule import periods_elapsed, scheduled_ordinal
from sidra.ledger.track_kind import TrackKind


def _track(*, anchor: date, ordinal: int, starts_on: date | None = None) -> Track:
    return Track(
        name_en="Neviim",
        name_he="נביאים",
        category=Category.DAILY,
        kind=TrackKind.CORPUS,
        corpus_id="neviim",
        rate=1,
        period=Period.DAY,
        anchor_date=anchor,
        anchor_ordinal=ordinal,
        starts_on=starts_on,
    )


def test_it_moves_the_anchor_date() -> None:
    track = _track(anchor=date(2026, 8, 24), ordinal=260)
    reanchor(track, date(2026, 8, 25))
    assert track.anchor_date == date(2026, 8, 25)
    assert track.anchor_ordinal == 260
    assert track.starts_on is None


def test_the_neviim_case_lands_on_jeremiah_49() -> None:
    """One day later means one fewer period billed, which is the whole correction."""
    track = _track(anchor=date(2026, 8, 24), ordinal=260)
    today = date(2026, 8, 27)
    assert scheduled_ordinal(track.anchor_ordinal, 1, periods_elapsed(track.anchor_date, today, Period.DAY)) == 263

    reanchor(track, date(2026, 8, 25))

    assert scheduled_ordinal(track.anchor_ordinal, 1, periods_elapsed(track.anchor_date, today, Period.DAY)) == 262


def test_a_start_date_moves_with_the_anchor() -> None:
    """``effective_anchor`` takes the later of the two, so leaving one behind would be a no-op."""
    track = _track(anchor=date(2026, 9, 5), ordinal=1, starts_on=date(2026, 9, 5))
    reanchor(track, date(2026, 9, 7))
    assert track.anchor_date == date(2026, 9, 7)
    assert track.starts_on == date(2026, 9, 7)
```

Create `backend/tests/ledger/test_recalibrate.py`:

```python
"""Shifting the opening position so today's scheduled ordinal is what it should be."""

from __future__ import annotations

import pytest

from sidra.ledger.recalibrate import recalibrate
from tests.ledger.test_reanchor import _track

from datetime import date


@pytest.mark.parametrize(
    ("anchor_ordinal", "scheduled_today", "desired", "expected"),
    [
        (260, 263, 262, 259),  # the Neviim case, one back
        (260, 263, 263, 260),  # already right, a no-op
        (260, 263, 270, 267),  # forwards is just as legal
        (100, 118, 100, 82),  # a rate-3 weekly track, six periods in
    ],
)
def test_the_anchor_absorbs_the_whole_difference(
    anchor_ordinal: int, scheduled_today: int, desired: int, expected: int
) -> None:
    track = _track(anchor=date(2026, 8, 24), ordinal=anchor_ordinal)
    recalibrate(track, desired, scheduled_today)
    assert track.anchor_ordinal == expected


def test_the_anchor_date_is_never_touched() -> None:
    """Moving it would make periods_elapsed raise for every earlier day, and take Stats with it."""
    track = _track(anchor=date(2026, 8, 24), ordinal=260)
    recalibrate(track, 262, 263)
    assert track.anchor_date == date(2026, 8, 24)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd backend && uv run pytest tests/ledger/test_reanchor.py tests/ledger/test_recalibrate.py -v -m "not live"
```

Expected: `ModuleNotFoundError: No module named 'sidra.ledger.reanchor'`

- [ ] **Step 3: Write `reanchor`**

Create `backend/src/sidra/ledger/reanchor.py`:

```python
"""Move the day a track's schedule began counting.

The seeder stamps ``anchor_date`` with the day it ran, and bills that day as a learning day. When
the position it was given was already true *for* that day, the day is billed twice and the schedule
runs one period ahead of the truth for ever after.

This is the operand to move when the error is the start rather than the position: every day before
the new origin falls back to a flat ``anchor_ordinal`` in ``stats/scheduled_series.py``, so the
opening debt the ledger was seeded with survives the correction intact. Shifting the ordinal
instead would restate it.
"""

from __future__ import annotations

from datetime import date

from sidra.db.models import Track


def reanchor(track: Track, started_on: date) -> None:
    """Set the origin, keeping ``starts_on`` alongside it when the track has one.

    ``effective_anchor`` takes the later of the pair, so moving only one of them would be a silent
    no-op in one direction and would break the conforming-row invariant in the other.
    """
    track.anchor_date = started_on
    if track.starts_on is not None:
        track.starts_on = started_on
```

- [ ] **Step 4: Write `recalibrate`**

Create `backend/src/sidra/ledger/recalibrate.py`:

```python
"""Shift a track's opening position so today's scheduled ordinal is what it should be.

Every schedule in the app has the shape ``anchor_ordinal + f(calendar)`` -- flat-rate in
``schedule.py``, calendar-driven in ``parsha_schedule.py`` -- so one subtraction serves both
without branching on the kind, and it is exact at any delta rather than quantised to whole periods
the way moving the anchor date is.

``anchor_date`` is never touched here. Moving it would make ``periods_elapsed`` raise for every
earlier day and take the Stats reconstruction with it.
"""

from __future__ import annotations

from sidra.db.models import Track


def recalibrate(track: Track, desired: int, scheduled_today: int) -> None:
    """Absorb the whole difference into the anchor, leaving the calendar half alone."""
    track.anchor_ordinal += desired - scheduled_today
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd backend && uv run pytest tests/ledger/test_reanchor.py tests/ledger/test_recalibrate.py -v -m "not live"
```

Expected: 8 passed

- [ ] **Step 6: Lint**

```bash
cd backend && uv run ruff check src/sidra/ledger/reanchor.py src/sidra/ledger/recalibrate.py tests/ledger/
```

Expected: `All checks passed!`

- [ ] **Step 7: Report — do not commit**

```
feat(ledger): name the two operands of a track's schedule
```

---

## Task 3: Split the track router — writes move out

**Files:**
- Create: `backend/src/sidra/api/routers/track_writes.py`
- Modify: `backend/src/sidra/api/routers/tracks.py`
- Modify: `backend/src/sidra/api/app.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `sidra.api.routers.track_writes.router` — an `APIRouter(prefix="/api/tracks", tags=["tracks"])`

**This task changes no behaviour.** Every existing test must pass untouched, which is how you know the move was clean. Do it before the new routes so their diff is legible.

- [ ] **Step 1: Record the baseline**

```bash
cd backend && uv run pytest tests/api -v -m "not live"
```

Write down the passing count. It must be identical at Step 6.

- [ ] **Step 2: Create `track_writes.py`**

Move these three route functions **verbatim** out of `tracks.py` into a new `backend/src/sidra/api/routers/track_writes.py`, together with the module constants they use (`ADVANCE_HOUR`, `MAX_START_YEARS_AHEAD`) and the private helper `_one_row`:

- `set_track_tags` — `@router.put("/{track_id}/tags", response_model=TrackRow)`
- `set_start_date` — `@router.patch("/{track_id}", response_model=TrackRow)`
- `advance` — `@router.post("/{track_id}/advance", response_model=AdvanceResult)`

Header for the new module:

```python
"""Everything that changes a track: its tags, its start date, and where it stands.

Split from ``tracks.py`` so the read routes and the write routes can be read separately. Both
mount under ``/api/tracks``, so no path moves and no client can tell.
"""

from __future__ import annotations
```

Then the imports each moved function actually needs, and:

```python
router = APIRouter(prefix="/api/tracks", tags=["tracks"])
```

- [ ] **Step 3: Trim `tracks.py`**

`tracks.py` keeps `list_tracks`, `get_track`, `get_rail` and `_rail_span`, plus `DEFAULT_RAIL_RADIUS`, `MAX_RAIL_RADIUS` and `MAX_RAIL_SPAN`. Delete every import it no longer uses — ruff's `F401` will name them. Update its docstring:

```python
"""The track list and one track's rail. Mutations live in ``track_writes.py``."""
```

`_one_row` is used by `get_track`, so `tracks.py` keeps its own copy — **no**. Read `get_track` first: it calls `_one_row`. Move `_one_row` to `track_writes.py` only if `tracks.py` no longer calls it; otherwise leave `_one_row` in `tracks.py` and import it into `track_writes.py`:

```python
from sidra.api.routers.tracks import _one_row
```

Prefer the import — one definition, and `tracks.py` is the module that already owns row-building for reads.

- [ ] **Step 4: Mount the new router**

`app.py` registers every router through one loop, so this is a two-line change. Add the module to
the import at `backend/src/sidra/api/app.py:15`:

```python
from sidra.api.routers import (
    alignment,
    chavrusas,
    pace,
    roadmap,
    sequence,
    stats,
    tags,
    today,
    track_writes,
    tracks,
)
```

and to the tuple in `create_app`:

```python
    for module in (today, tracks, track_writes, roadmap, chavrusas, tags, alignment, pace, stats, sequence):
        app.include_router(module.router)
```

`track_writes` sits next to `tracks` because they share a prefix; ruff's `I` rules will sort the
import block, so run `uv run ruff check --fix` on the file if the manual ordering is off.

- [ ] **Step 5: Fix test imports**

```bash
cd backend && uv run grep -rn "routers.tracks\|routers import tracks" tests/ || true
```

Any test importing a moved symbol updates its import path. **No test assertion changes.** If an assertion needs changing, stop — the move was not verbatim.

- [ ] **Step 6: Run the whole API suite**

```bash
cd backend && uv run pytest tests/api -v -m "not live"
```

Expected: the exact count from Step 1, all passing.

- [ ] **Step 7: Verify the OpenAPI surface is unchanged**

```bash
cd backend && uv run python -c "from sidra.api.app import create_app; print(sorted((r.path, tuple(sorted(r.methods))) for r in create_app().routes if hasattr(r, 'methods')))"
```

Expected: every `/api/tracks*` path present exactly as before the split.

- [ ] **Step 8: Lint**

```bash
cd backend && uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 9: Report — do not commit**

```
refactor(api): split track writes out of the track router
```

---

## Task 4: `resolved_ordinal`, and the `occurred_on` 500

**Files:**
- Modify: `backend/src/sidra/api/models/advance_result.py`
- Modify: `backend/src/sidra/api/routers/track_writes.py`
- Test: `backend/tests/api/test_advance_by_ref.py`

**Interfaces:**
- Produces: `AdvanceResult.resolved_ordinal: int` — where the request resolved to, whether or not anything was written. On a real advance it equals `to_ordinal`; on a replay it is the destination that was refused.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/api/test_advance_by_ref.py`:

```python
async def test_a_replay_reports_where_it_aimed(client: httpx.AsyncClient) -> None:
    """Without this the UI cannot say "Jeremiah 48 is 1 perek behind you" without another call."""
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "Jeremiah 43"})).json()
    assert body["was_replay"] is True
    assert body["advance_id"] is None
    assert body["to_ordinal"] == 120
    assert body["resolved_ordinal"] == 119


async def test_a_real_advance_reports_the_same_ordinal_it_recorded(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (await client.post(f"/api/tracks/{track_id}/advance", json={"to_ref": "Jeremiah 45"})).json()
    assert body["was_replay"] is False
    assert body["to_ordinal"] == 121
    assert body["resolved_ordinal"] == 121


async def test_a_malformed_date_is_refused_rather_than_crashing(client: httpx.AsyncClient) -> None:
    """It was parsed outside the try, so it surfaced as a 500."""
    track_id = await _track_id(client, "Neviim")
    response = await client.post(
        f"/api/tracks/{track_id}/advance", json={"to_ordinal": 121, "occurred_on": "not-a-date"}
    )
    assert response.status_code == 422
    assert "not-a-date" in response.json()["detail"]
```

If `_track_id` does not already exist in this file, copy it from `tests/api/test_start_date.py:20-22`.

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_advance_by_ref.py -v -m "not live"
```

Expected: the two `resolved_ordinal` tests fail with `KeyError: 'resolved_ordinal'`; the date test fails with a `ValueError` escaping as a 500.

- [ ] **Step 3: Add the field**

In `backend/src/sidra/api/models/advance_result.py`, after `advance_id`:

```python
    resolved_ordinal: int
    """Where the request resolved to, written or not.

    On a replay ``from_ordinal`` and ``to_ordinal`` both report where he already was, which says
    nothing about where he aimed -- so a caller could not describe a backwards reference without
    resolving it a second time."""
```

- [ ] **Step 4: Fix the date parse and populate the field**

In `track_writes.py`'s `advance`, move the `occurred_on` parse inside a guarded block. Replace:

```python
    occurred_on = date.fromisoformat(body.occurred_on) if body.occurred_on else default_day
```

with:

```python
    try:
        occurred_on = date.fromisoformat(body.occurred_on) if body.occurred_on else default_day
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"{body.occurred_on!r} is not a date") from error
```

Then add `resolved_ordinal=destination` to **both** `AdvanceResult(...)` constructions — the replay return and the recorded return.

- [ ] **Step 5: Run to verify they pass**

```bash
cd backend && uv run pytest tests/api/test_advance_by_ref.py -v -m "not live"
```

Expected: all passing.

- [ ] **Step 6: Run the whole API suite**

```bash
cd backend && uv run pytest tests/api -v -m "not live"
```

Expected: all passing. `AdvanceResult` gained a required field, so any test constructing one directly needs it — fix those, and only those.

- [ ] **Step 7: Report — do not commit**

```
feat(api): a replay reports the ordinal it resolved to

Also fixes a malformed occurred_on surfacing as a 500 rather than a 422.
```

---

## Task 5: `PUT /api/tracks/{id}/position`

**Files:**
- Create: `backend/src/sidra/api/models/position_write.py`
- Create: `backend/src/sidra/api/models/correction_result.py`
- Modify: `backend/src/sidra/api/routers/track_writes.py`
- Modify: `backend/src/sidra/ledger/reachable.py` (docstring)
- Modify: `backend/src/sidra/ledger/cycle.py` (docstring)
- Test: `backend/tests/api/test_position.py`

**Interfaces:**
- Consumes: `truncate_to`, `Truncation` (Task 1); `resolve_position`, `align_to`, `fold`, `cycle_length`, `actual_ordinal`, `_one_row`
- Produces: `PUT /api/tracks/{track_id}/position` returning `CorrectionResult`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_position.py`:

```python
"""Correcting where a track actually stands."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

JEREMIAH_43 = 119
JEREMIAH_44 = 120
JEREMIAH_48 = 124
JEREMIAH_49 = 125


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _at(client: httpx.AsyncClient, track_id: str) -> int:
    rows = (await client.get("/api/tracks")).json()
    return next(row["actual_ordinal"] for row in rows if row["id"] == track_id)


async def test_a_confirmed_correction_moves_the_position_back(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})

    body = (
        await client.put(
            f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_48, "confirm": True}
        )
    ).json()

    assert body["from_ordinal"] == JEREMIAH_49
    assert body["to_ordinal"] == JEREMIAH_48
    assert body["removed_units"] == 1
    assert body["moved"] is True
    assert body["track"]["actual_ordinal"] == JEREMIAH_48
    assert await _at(client, track_id) == JEREMIAH_48


async def test_it_refuses_without_confirmation_and_says_what_it_would_remove(
    client: httpx.AsyncClient,
) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})

    response = await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_48})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Jeremiah 48" in detail
    assert "Jeremiah 49" in detail
    assert "1 perek" in detail
    assert await _at(client, track_id) == JEREMIAH_49


async def test_a_forward_destination_is_sent_to_the_advance_endpoint(client: httpx.AsyncClient) -> None:
    """Keeping each endpoint's name true: this one never records learning."""
    track_id = await _track_id(client, "Neviim")
    response = await client.put(
        f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_49, "confirm": True}
    )
    assert response.status_code == 422
    assert "advance" in response.json()["detail"]
    assert await _at(client, track_id) == JEREMIAH_44


async def test_correcting_to_where_he_already_is_writes_nothing(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (
        await client.put(
            f"/api/tracks/{track_id}/position", json={"to_ordinal": JEREMIAH_44, "confirm": True}
        )
    ).json()
    assert body["moved"] is False
    assert body["removed_units"] == 0
    assert await _at(client, track_id) == JEREMIAH_44


async def test_a_typed_reference_resolves_the_same_way_an_advance_does(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    await client.post(f"/api/tracks/{track_id}/advance", json={"to_ordinal": JEREMIAH_49})

    body = (
        await client.put(
            f"/api/tracks/{track_id}/position", json={"to_ref": "Jeremiah 48", "confirm": True}
        )
    ).json()

    assert body["track"]["at"]["ref"] == "Jeremiah 48"


async def test_an_unresolvable_reference_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(
        f"/api/tracks/{track_id}/position", json={"to_ref": "Habakkuk 9", "confirm": True}
    )
    assert response.status_code == 422


async def test_zero_returns_the_track_to_unopened(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (
        await client.put(f"/api/tracks/{track_id}/position", json={"to_ordinal": 0, "confirm": True})
    ).json()
    assert body["track"]["actual_ordinal"] == 0
    assert body["track"]["at"] is None


async def test_giving_both_a_ref_and_an_ordinal_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(
        f"/api/tracks/{track_id}/position",
        json={"to_ordinal": JEREMIAH_44, "to_ref": "Jeremiah 44", "confirm": True},
    )
    assert response.status_code == 422


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.put(
        "/api/tracks/00000000-0000-0000-0000-000000000000/position",
        json={"to_ordinal": 1, "confirm": True},
    )
    assert response.status_code == 404


async def test_the_ceiling_retreats_with_the_position_on_a_cycle_track(client: httpx.AsyncClient) -> None:
    """After a correction the corrected position is the truth, so the rail must follow it."""
    track_id = await _track_id(client, "Chumash")
    rows = (await client.get("/api/tracks")).json()
    before = next(row for row in rows if row["id"] == track_id)

    body = (
        await client.put(
            f"/api/tracks/{track_id}/position",
            json={"to_ordinal": before["actual_ordinal"] - 1, "confirm": True},
        )
    ).json()

    assert body["track"]["reachable_to"] < before["reachable_to"]
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_position.py -v -m "not live"
```

Expected: every test 405 or 404 — the route does not exist.

- [ ] **Step 3: Write the request model**

Create `backend/src/sidra/api/models/position_write.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PositionUpdate(BaseModel):
    """Correct where a track actually stands.

    Say **where you really are**, the same way an advance says where you got to. This endpoint only
    goes backwards: a destination ahead belongs to ``POST /advance``, which records learning rather
    than erasing it.

    ``confirm`` is the seatbelt. Correcting backwards deletes recorded learning and there is no
    undo, so it is refused without an explicit acknowledgement -- the same shape as ``forgive`` on
    the start-date endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    to_ordinal: int | None = Field(default=None, ge=0)
    """Zero means the track has not been opened at all."""

    to_ref: str | None = Field(default=None, min_length=1, max_length=256)
    confirm: bool = False

    @model_validator(mode="after")
    def _one_destination(self) -> PositionUpdate:
        if (self.to_ordinal is None) == (self.to_ref is None):
            raise ValueError("give either to_ordinal or to_ref, not both and not neither")
        return self
```

- [ ] **Step 4: Write the response model**

Create `backend/src/sidra/api/models/correction_result.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from sidra.api.models.track_row import TrackRow


class CorrectionResult(BaseModel):
    """What one backwards correction did, and the track as it now stands."""

    from_ordinal: int
    to_ordinal: int
    removed_units: int
    """How far the position dropped, which is what the toast reports."""

    removed_advances: int
    """Rows deleted outright. A row trimmed rather than deleted is not counted."""

    moved: bool
    """False when the destination was already the position and nothing was written."""

    track: TrackRow
```

- [ ] **Step 5: Write the route**

Add to `backend/src/sidra/api/routers/track_writes.py`:

```python
@router.put("/{track_id}/position", response_model=CorrectionResult)
async def correct_position(
    track_id: uuid.UUID,
    body: PositionUpdate,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> CorrectionResult:
    """Move a track's actual position backwards, rewriting the rows behind it.

    Only backwards. A destination ahead is an advance, and sending it here would make an endpoint
    named for correction record learning instead.
    """
    track = await track_or_404(session, track_id)
    current = await actual_ordinal(session, track)
    cycle_len = await cycle_length(session, track)

    try:
        if body.to_ref is not None:
            here = current if cycle_len is None or current < 1 else fold(current, cycle_len)
            base = await resolve_position(session, track, body.to_ref, current_ordinal=here)
            destination = base if cycle_len is None else align_to(base, current, cycle_len)
        else:
            assert body.to_ordinal is not None  # noqa: S101 - the model guarantees one or the other
            destination = body.to_ordinal
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if destination > current:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en}: {destination} is ahead of where you are; record it as an advance",
        )

    if destination == current:
        return CorrectionResult(
            from_ordinal=current,
            to_ordinal=current,
            removed_units=0,
            removed_advances=0,
            moved=False,
            track=await _one_row(session, track_id, default_day),
        )

    if not body.confirm:
        raise HTTPException(status_code=422, detail=await _correction_warning(session, track, current, destination))

    result = await truncate_to(session, track, destination)
    try:
        row = await _one_row(session, track_id, default_day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return CorrectionResult(
        from_ordinal=result.from_ordinal,
        to_ordinal=result.to_ordinal,
        removed_units=result.removed_units,
        removed_advances=result.removed_advances,
        moved=True,
        track=row,
    )
```

And the private helper that composes the refusal, beside it:

```python
async def _correction_warning(session: AsyncSession, track: Track, current: int, destination: int) -> str:
    """Name both positions and the cost, so the confirmation is never a blank "are you sure"."""
    cycle_len = await cycle_length(session, track)
    here = await position_at(session, track, current if cycle_len is None else fold(current, cycle_len))
    there = await position_at(session, track, destination if cycle_len is None else fold(destination, cycle_len))
    dropped = current - destination
    singular, plural = unit_nouns(here.granularity)
    noun = singular if dropped == 1 else plural
    return (
        f"{track.name_en}: {there.ref} is {dropped} {noun} behind {here.ref}; "
        f"this removes {dropped} {noun} of recorded learning. There is no undo."
    )
```

Add the imports this needs: `PositionUpdate`, `CorrectionResult`, `truncate_to`, `position_at`, `unit_nouns`, `Track`.

**Note:** `_correction_warning` calls `position_at` with `destination`, which is at least 1 here because `destination < current` and the zero case is handled by `truncate_to` only after confirmation. If `destination` is 0 the caller has confirmed, so the warning is never built for it. Verify this by reading the branch order above before implementing.

- [ ] **Step 6: Run to verify they pass**

```bash
cd backend && uv run pytest tests/api/test_position.py -v -m "not live"
```

Expected: 10 passed.

- [ ] **Step 7: Rewrite the two docstrings this falsifies**

In `backend/src/sidra/ledger/reachable.py`, replace the `CYCLES_AHEAD` docstring's last sentence. It currently reads *"There is no undo, so the ceiling is what stands between a mistyped ordinal and a year of phantom learning."* Replace with:

```
Undoing one is now possible but deliberate and confirmed, so the ceiling still stands between a
mistyped ordinal and a year of phantom learning -- it just no longer has to be the only thing that
does.
```

In `backend/src/sidra/ledger/cycle.py`, `align_to`'s docstring ends *"...and there is no undo."* Replace that closing clause with:

```
because a bare address cannot distinguish "I got further" from "no, I stopped back there". The
second of those is a correction, and it is ``PUT /position`` that hears it.
```

- [ ] **Step 8: Run the whole backend suite with the coverage gate**

```bash
cd backend && uv run pytest -m "not live" --cov=src/sidra --cov-report=term-missing
```

Expected: all passing, `Required test coverage of 100% reached`. If a branch of `correct_position` is uncovered, add the test that covers it — do not add `pragma: no cover`.

- [ ] **Step 9: Lint**

```bash
cd backend && uv run ruff check .
```

- [ ] **Step 10: Report — do not commit**

```
feat(api): correct a track's position backwards

PUT /api/tracks/{id}/position truncates the advance rows behind a chosen
point, so actual_ordinal stays MAX(to_ordinal) and no consumer of the
ledger has to learn about backwards motion.
```

---

## Task 6: `PUT /api/tracks/{id}/schedule`

**Files:**
- Create: `backend/src/sidra/api/models/schedule_write.py`
- Modify: `backend/src/sidra/api/routers/track_writes.py`
- Test: `backend/tests/api/test_schedule.py`

**Interfaces:**
- Consumes: `reanchor`, `recalibrate` (Task 2); `ordinal_for_ref`/`resolve_position`, `track_state`, `reachable_ceiling`, `_one_row`
- Produces: `PUT /api/tracks/{track_id}/schedule` returning `TrackRow`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/api/test_schedule.py`:

```python
"""Correcting what a track is supposed to be up to."""

from __future__ import annotations

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration

JEREMIAH_46 = 122
JEREMIAH_47 = 123
JEREMIAH_50 = 126


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _row(client: httpx.AsyncClient, name: str, params: dict[str, str] | None = None) -> dict[str, object]:
    rows = (await client.get("/api/tracks", params=params or {})).json()
    return next(row for row in rows if row["name_en"] == name)


# --- "it started on ___" ------------------------------------------------------------------------


async def test_moving_the_start_day_moves_the_schedule_by_one_period(client: httpx.AsyncClient) -> None:
    """Amram's case: the seeder billed its own run day, so the schedule ran a day ahead."""
    track_id = await _track_id(client, "Neviim")
    assert (await _row(client, "Neviim", on(3)))["scheduled_at"]["corpus_ordinal"] == JEREMIAH_50

    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"started_on": on(1)["on"]})).json()

    assert body["id"] == track_id
    assert (await _row(client, "Neviim", on(3)))["scheduled_at"]["corpus_ordinal"] == JEREMIAH_50 - 1


async def test_a_start_day_after_today_is_refused(client: httpx.AsyncClient) -> None:
    """periods_elapsed raises on an anchor ahead of the day being asked about."""
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"started_on": on(5)["on"]})
    assert response.status_code == 422
    assert "today" in response.json()["detail"]


async def test_a_track_that_has_not_begun_is_sent_to_the_start_date_endpoint(
    client: httpx.AsyncClient,
) -> None:
    track_id = await _track_id(client, "Likutei Sichot")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"started_on": on(0)["on"]})
    assert response.status_code == 422
    assert "start date" in response.json()["detail"]


# --- "it should be at ___ today" ----------------------------------------------------------------


async def test_naming_the_target_shifts_the_opening_position(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (
        await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": JEREMIAH_46})
    ).json()
    assert body["scheduled_at"]["corpus_ordinal"] == JEREMIAH_46
    assert body["debt"] == JEREMIAH_46 - 120


async def test_a_typed_reference_names_the_target_too(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    body = (
        await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ref": "Jeremiah 46"})
    ).json()
    assert body["scheduled_at"]["ref"] == "Jeremiah 46"


async def test_up_to_date_is_the_current_position_as_the_target(client: httpx.AsyncClient) -> None:
    """The UI's "I'm up to date" button is this request, not a second code path."""
    track_id = await _track_id(client, "Neviim")
    row = await _row(client, "Neviim")
    body = (
        await client.put(
            f"/api/tracks/{track_id}/schedule", json={"to_ordinal": row["actual_ordinal"]}
        )
    ).json()
    assert body["debt"] == 0


async def test_a_target_past_the_end_is_refused(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": 9999})
    assert response.status_code == 422


async def test_a_target_that_would_drive_the_anchor_below_one_is_refused(
    client: httpx.AsyncClient,
) -> None:
    track_id = await _track_id(client, "Neviim")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": 1})
    assert response.status_code == 422
    assert "before its first unit" in response.json()["detail"]


async def test_it_works_on_a_parsha_track(client: httpx.AsyncClient) -> None:
    """The calendar-driven schedule shares the anchor_ordinal + f(calendar) shape."""
    track_id = await _track_id(client, "Chumash")
    row = await _row(client, "Chumash")
    target = row["scheduled_at"]["corpus_ordinal"] - 1
    body = (await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": target})).json()
    assert body["scheduled_at"]["corpus_ordinal"] == target


# --- refusals shared by both routes --------------------------------------------------------------


async def test_a_chavrusa_track_has_no_schedule_to_correct(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "David Hadar — Brachot")
    response = await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": 5})
    assert response.status_code == 422
    assert "staleness" in response.json()["detail"]


async def test_exactly_one_of_the_three_is_required(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    assert (await client.put(f"/api/tracks/{track_id}/schedule", json={})).status_code == 422
    both = {"started_on": on(0)["on"], "to_ordinal": JEREMIAH_47}
    assert (await client.put(f"/api/tracks/{track_id}/schedule", json=both)).status_code == 422


async def test_an_unknown_track_is_a_404(client: httpx.AsyncClient) -> None:
    response = await client.put(
        "/api/tracks/00000000-0000-0000-0000-000000000000/schedule", json={"to_ordinal": 1}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && uv run pytest tests/api/test_schedule.py -v -m "not live"
```

Expected: 405 or 404 throughout.

- [ ] **Step 3: Write the request model**

Create `backend/src/sidra/api/models/schedule_write.py`:

```python
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScheduleUpdate(BaseModel):
    """Correct what a track is supposed to be up to.

    Two operands, named rather than chosen silently, because they disagree about the past.
    ``started_on`` moves the day the schedule began counting, which leaves every earlier day
    reading the opening position it was seeded with. A target -- ``to_ordinal`` or ``to_ref`` --
    shifts the opening position itself, which is exact at any delta but restates those days.

    No acknowledgement flag: nothing is destroyed, and sending the previous value back restores it
    exactly.
    """

    model_config = ConfigDict(extra="forbid")

    started_on: date | None = None
    to_ordinal: int | None = Field(default=None, ge=1)
    to_ref: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def _one_correction(self) -> ScheduleUpdate:
        given = [self.started_on, self.to_ordinal, self.to_ref]
        if sum(value is not None for value in given) != 1:
            raise ValueError("give exactly one of started_on, to_ordinal or to_ref")
        return self
```

- [ ] **Step 4: Write the route**

Add to `backend/src/sidra/api/routers/track_writes.py`:

```python
@router.put("/{track_id}/schedule", response_model=TrackRow)
async def correct_schedule(
    track_id: uuid.UUID,
    body: ScheduleUpdate,
    session: AsyncSession = Depends(get_session),
    default_day: date = Depends(today),
) -> TrackRow:
    """Correct what a track is supposed to be up to, by whichever operand was wrong."""
    track = await track_or_404(session, track_id)
    if track.period is Period.NONE:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en} is a chavrusa track; it carries staleness, not a schedule to correct",
        )

    if body.started_on is not None:
        _check_start_day(track, body.started_on, default_day)
        reanchor(track, body.started_on)
    else:
        await _shift_opening_position(session, track, body, default_day)

    await session.flush()
    try:
        return await _one_row(session, track_id, default_day)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
```

And the two private helpers beside it:

```python
def _check_start_day(track: Track, started_on: date, today_is: date) -> None:
    """A schedule cannot begin in the future, and one that has not begun is not this endpoint's."""
    if started_on > today_is:
        raise HTTPException(
            status_code=422,
            detail=f"{started_on} is after today; a schedule cannot begin in the future",
        )
    if track.starts_on is not None and track.starts_on > today_is:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en} has not begun; move its start date with PATCH instead",
        )


async def _shift_opening_position(
    session: AsyncSession, track: Track, body: ScheduleUpdate, today_is: date
) -> None:
    """Solve the anchor backwards from the ordinal the schedule should read today."""
    try:
        state = await track_state(session, track, today_is)
        if body.to_ref is not None:
            here = state.actual_ordinal
            desired = await resolve_position(session, track, body.to_ref, current_ordinal=here)
        else:
            assert body.to_ordinal is not None  # noqa: S101 - the model guarantees exactly one
            desired = body.to_ordinal
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    ceiling = reachable_ceiling(
        actual=state.actual_ordinal,
        scheduled=None if state.ledger is None else state.ledger.scheduled,
        total=state.total,
        cycle_length=state.cycle_length,
    )
    if desired > ceiling:
        raise HTTPException(
            status_code=422, detail=f"{track.name_en}: {desired} is past the end of the track"
        )

    assert state.ledger is not None  # noqa: S101 - Period.NONE was refused above
    recalibrate(track, desired, state.ledger.scheduled)
    if track.anchor_ordinal < 1:
        raise HTTPException(
            status_code=422,
            detail=f"{track.name_en}: that would put the schedule's origin before its first unit",
        )
```

Add the imports: `ScheduleUpdate`, `reanchor`, `recalibrate`, `track_state`, `reachable_ceiling`, `Period`.

**Note on the `anchor_ordinal < 1` guard:** `recalibrate` has already mutated the track when the check runs. The session dependency wraps the whole request in one transaction — `async with factory() as session, session.begin():` at `sidra/api/deps.py:18` — so raising rolls the mutation back rather than leaving a half-applied anchor. Verified while planning; re-read `deps.py` before implementing in case it has moved.

- [ ] **Step 5: Run to verify they pass**

```bash
cd backend && uv run pytest tests/api/test_schedule.py -v -m "not live"
```

Expected: 12 passed.

- [ ] **Step 6: Run the whole backend suite with the coverage gate**

```bash
cd backend && uv run pytest -m "not live" --cov=src/sidra --cov-report=term-missing
```

Expected: all passing, coverage 100%.

- [ ] **Step 7: Lint**

```bash
cd backend && uv run ruff check .
```

- [ ] **Step 8: Report — do not commit**

```
feat(api): correct what a track is supposed to be up to

PUT /api/tracks/{id}/schedule, with the two operands of the schedule
formula named separately: started_on moves the origin, to_ordinal/to_ref
shifts the opening position.
```

---

## Task 7: The acceptance gate — what a correction does to the past

**Files:**
- Test: `backend/tests/api/test_schedule_history.py`

This task adds no production code. It pins the claim the whole of §5 rests on: the two operands produce the same schedule today and **different histories**, which is why neither may be chosen silently. If it fails, the design is wrong, not the test.

**Interfaces:**
- Consumes: `PUT /api/tracks/{id}/schedule` (Task 6), `GET /api/stats`

- [ ] **Step 1: Confirm the two names this test depends on**

```bash
cd backend && grep -n "debt_then" src/sidra/api/models/stats_track.py && grep -n "window: int" src/sidra/api/routers/stats.py
```

Both were verified while planning and are recorded here so the test below is not guesswork:

| What | Where | Value |
|---|---|---|
| The debt on the window's first day | `StatsTrack.debt_then` (`api/models/stats_track.py`) | `int \| None` |
| The window parameter | `GET /api/stats?window=` (`api/routers/stats.py:35`) | `ge=MIN_WINDOW_DAYS`, and `MIN_WINDOW_DAYS = 1` (`stats/window.py:8`), so `window=4` is legal |

`TrackReport` is the internal dataclass; `StatsTrack` is what the endpoint returns. The test reads
the JSON, so `StatsTrack` is the one that matters. If either has moved, fix the helper — not the
assertions.

- [ ] **Step 2: Write the test**

Create `backend/tests/api/test_schedule_history.py`:

```python
"""The two schedule operands agree about today and disagree about the past.

This is the whole reason ``PUT /schedule`` names them rather than picking one. Moving the origin
leaves every earlier day reading the seeded opening position, so the debt the ledger opened with
survives; shifting the opening position restates it. A lever that chose silently would rewrite a
measured fact -- Neviim opening three perakim behind -- without anyone asking it to.
"""

from __future__ import annotations

import httpx
import pytest

from tests.api.conftest import on

pytestmark = pytest.mark.integration

OPENING_DEBT = 3
"""Jeremiah 44 against Jeremiah 47 on the seed day. Measured; see CLAUDE.md section 1."""


async def _track_id(client: httpx.AsyncClient, name: str) -> str:
    rows = (await client.get("/api/tracks")).json()
    return next(row["id"] for row in rows if row["name_en"] == name)


async def _debt_then(client: httpx.AsyncClient, name: str, window: int) -> int:
    body = (await client.get("/api/stats", params={"window": window})).json()
    return next(row["debt_then"] for row in body["tracks"] if row["name_en"] == name)


async def _scheduled_today(client: httpx.AsyncClient, name: str, offset: int) -> int:
    rows = (await client.get("/api/tracks", params=on(offset))).json()
    return next(row["scheduled_at"]["corpus_ordinal"] for row in rows if row["name_en"] == name)


async def test_moving_the_origin_leaves_the_opening_debt_standing(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    before = await _scheduled_today(client, "Neviim", 3)

    await client.put(f"/api/tracks/{track_id}/schedule", json={"started_on": on(1)["on"]})

    assert await _scheduled_today(client, "Neviim", 3) == before - 1
    assert await _debt_then(client, "Neviim", 4) == OPENING_DEBT


async def test_shifting_the_opening_position_restates_it(client: httpx.AsyncClient) -> None:
    track_id = await _track_id(client, "Neviim")
    before = await _scheduled_today(client, "Neviim", 3)

    await client.put(f"/api/tracks/{track_id}/schedule", json={"to_ordinal": before - 1})

    assert await _scheduled_today(client, "Neviim", 3) == before - 1
    assert await _debt_then(client, "Neviim", 4) == OPENING_DEBT - 1
```

**If `debt_then` or the window parameter differ from what Step 1 found, fix the helpers — not the two assertions.** `OPENING_DEBT` is a measured constant and does not move.

- [ ] **Step 3: Run it**

```bash
cd backend && uv run pytest tests/api/test_schedule_history.py -v -m "not live"
```

Expected: 2 passed. If the first test reports `OPENING_DEBT - 1`, stop: `reanchor` is shifting the ordinal somewhere it should not, or `scheduled_series.py`'s pre-origin fallback is not firing. Report it rather than adjusting the constant.

- [ ] **Step 4: Report — do not commit**

```
test(api): pin what each schedule operand does to the past
```

---

## Task 8: Frontend — types, endpoints, thunks

**Files:**
- Create: `frontend/src/types/CorrectionResult.ts`
- Modify: `frontend/src/types/AdvanceResult.ts`
- Modify: `frontend/src/api/endpoints.ts`
- Modify: `frontend/src/stores/tracksSlice.ts`
- Test: `frontend/tests/api/endpoints.test.ts`
- Test: `frontend/tests/stores/slices.test.ts`

**Interfaces:**
- Consumes: the two endpoints from Tasks 5 and 6
- Produces:
  - `CorrectionResult` — `{ from_ordinal, to_ordinal, removed_units, removed_advances, moved, track }`
  - `api.correctPosition(id: string, destination: AdvanceDestination, confirm: boolean): Promise<CorrectionResult>`
  - `api.correctSchedule(id: string, correction: ScheduleCorrection): Promise<TrackRow>`
  - `ScheduleCorrection = { readonly startedOn: string } | AdvanceDestination`
  - Thunks `correctPosition` and `correctSchedule`, both updating the row in `tracksSlice`

- [ ] **Step 1: Write the failing tests**

Read `frontend/tests/api/endpoints.test.ts` first and follow its existing idiom exactly — how it stubs `fetch`, how it asserts the URL, method and body. Then add cases asserting:

- `api.correctPosition("t1", { toOrdinal: 262 }, true)` issues `PUT /api/tracks/t1/position` with body `{ to_ordinal: 262, confirm: true }`
- `api.correctPosition("t1", { toRef: "Jeremiah 49" }, false)` issues body `{ to_ref: "Jeremiah 49", confirm: false }`
- `api.correctSchedule("t1", { startedOn: "2026-08-25" })` issues `PUT /api/tracks/t1/schedule` with body `{ started_on: "2026-08-25" }`
- `api.correctSchedule("t1", { toOrdinal: 262 })` issues body `{ to_ordinal: 262 }`

In `frontend/tests/stores/slices.test.ts`, following its existing idiom, add cases asserting that a fulfilled `correctPosition` replaces the matching row in `state.tracks.data` with `payload.track`, and a fulfilled `correctSchedule` replaces it with `payload`.

- [ ] **Step 2: Run to verify they fail**

```bash
cd frontend && pnpm test
```

Expected: failures naming `correctPosition` / `correctSchedule` as undefined.

- [ ] **Step 3: Add `CorrectionResult`**

Create `frontend/src/types/CorrectionResult.ts`:

```typescript
import type { TrackRow } from "./TrackRow";

/** What one backwards correction did, and the track as it now stands. */
export interface CorrectionResult {
  readonly from_ordinal: number;
  readonly to_ordinal: number;
  /** How far the position dropped — what the toast reports. */
  readonly removed_units: number;
  /** Rows deleted outright. A row trimmed rather than deleted is not counted. */
  readonly removed_advances: number;
  /** False when the destination was already the position and nothing was written. */
  readonly moved: boolean;
  readonly track: TrackRow;
}
```

- [ ] **Step 4: Extend `AdvanceResult`**

In `frontend/src/types/AdvanceResult.ts`, after `advance_id`:

```typescript
  /** Where the request resolved to, written or not. On a replay this is what was refused. */
  readonly resolved_ordinal: number;
```

- [ ] **Step 5: Add the two endpoints**

In `frontend/src/api/endpoints.ts`, above `pace`, and importing `CorrectionResult`:

```typescript
  /** Say where he really is. Backwards only — the server refuses anything ahead. */
  correctPosition: (
    id: string,
    destination: AdvanceDestination,
    confirm: boolean,
  ): Promise<CorrectionResult> =>
    request<CorrectionResult>(`/api/tracks/${id}/position`, {
      method: "PUT",
      body: {
        ...("toRef" in destination ? { to_ref: destination.toRef } : { to_ordinal: destination.toOrdinal }),
        confirm,
      },
    }),

  /** Say what he is supposed to be up to — by the day it started, or by the place itself. */
  correctSchedule: (id: string, correction: ScheduleCorrection): Promise<TrackRow> =>
    request<TrackRow>(`/api/tracks/${id}/schedule`, {
      method: "PUT",
      body:
        "startedOn" in correction
          ? { started_on: correction.startedOn }
          : "toRef" in correction
            ? { to_ref: correction.toRef }
            : { to_ordinal: correction.toOrdinal },
    }),
```

Declare `ScheduleCorrection` in its own file, `frontend/src/types/ScheduleCorrection.ts`, because it is a concept the dialog and the thunk both name:

```typescript
import type { AdvanceDestination } from "./AdvanceDestination";

/**
 * Which operand of the schedule was wrong.
 *
 * The day it began counting, or the place it should have reached by now. They agree about today
 * and disagree about every day before it, so the caller says which rather than the server guessing.
 */
export type ScheduleCorrection = { readonly startedOn: string } | AdvanceDestination;
```

- [ ] **Step 6: Add the two thunks**

In `frontend/src/stores/tracksSlice.ts`, following the shape of `setTrackStart` exactly:

```typescript
export interface CorrectPositionRequest {
  readonly trackId: string;
  readonly destination: AdvanceDestination;
  /** Acknowledge that this deletes recorded learning. There is no undo. */
  readonly confirm: boolean;
}

export interface CorrectScheduleRequest {
  readonly trackId: string;
  readonly correction: ScheduleCorrection;
}

export const correctPosition = createAsyncThunk<CorrectionResult, CorrectPositionRequest, ThunkConfig>(
  "tracks/correctPosition",
  async ({ trackId, destination, confirm }, { rejectWithValue }) => {
    try {
      return await api.correctPosition(trackId, destination, confirm);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);

export const correctSchedule = createAsyncThunk<TrackRow, CorrectScheduleRequest, ThunkConfig>(
  "tracks/correctSchedule",
  async ({ trackId, correction }, { rejectWithValue }) => {
    try {
      return await api.correctSchedule(trackId, correction);
    } catch (error) {
      return rejectWithValue(asFailure(error));
    }
  },
);
```

And in `extraReducers`, beside the existing two:

```typescript
    // A correction answers with the track as it now stands, for the same reason an advance does.
    builder.addCase(correctPosition.fulfilled, (state, action) => {
      const updated = action.payload.track;
      return { ...state, data: state.data.map((row) => (row.id === updated.id ? updated : row)) };
    });
    builder.addCase(correctSchedule.fulfilled, (state, action) => ({
      ...state,
      data: state.data.map((row) => (row.id === action.payload.id ? action.payload : row)),
    }));
```

- [ ] **Step 7: Run tests, lint and typecheck**

```bash
cd frontend && pnpm test && pnpm lint && pnpm build
```

Expected: all passing. `AdvanceResult` gained a required field, so any test fixture constructing one needs `resolved_ordinal` — `tsc` will name every site.

- [ ] **Step 8: Report — do not commit**

```
feat(frontend): wire the two correction endpoints
```

---

## Task 9: `AdvanceDialog` opens backwards

**Files:**
- Modify: `frontend/src/components/AdvanceDialog.tsx`
- Create: `frontend/src/utils/correctionPhrase.ts`
- Modify: `frontend/src/screens/TrackScreen.tsx`
- Modify: `frontend/src/screens/TodayScreen.tsx`
- Test: `frontend/tests/correction.test.tsx`

**Interfaces:**
- Consumes: `correctPosition` thunk, `AdvanceResult.resolved_ordinal` (Task 8)
- Produces: `correctionPhrase(track: TrackRow, from: number, to: number): string`

- [ ] **Step 1: Write `correctionPhrase` and its test**

Create `frontend/src/utils/correctionPhrase.ts`:

```typescript
import type { TrackRow } from "@/types/TrackRow";

/**
 * What a backwards correction is about to cost, in his own units.
 *
 * Spelled out rather than left to a bare "are you sure": the operation deletes recorded learning
 * and cannot be undone, so the number and the noun both belong in front of him.
 */
export function correctionPhrase(track: TrackRow, from: number, to: number): string {
  const dropped = from - to;
  const noun = dropped === 1 ? track.unit_singular : track.unit_plural;
  return `That is ${dropped} ${noun} behind where you are. Correcting removes ${dropped} ${noun} of recorded learning, and there is no undo.`;
}
```

Add to `frontend/tests/utils.test.ts`, following its existing idiom:

```typescript
describe("correctionPhrase", () => {
  it("uses the singular for one unit and the plural beyond", () => {
    const row = track({ unit_singular: "perek", unit_plural: "perakim" });
    expect(correctionPhrase(row, 263, 262)).toContain("1 perek behind");
    expect(correctionPhrase(row, 263, 260)).toContain("3 perakim behind");
  });

  it("says there is no undo", () => {
    expect(correctionPhrase(track({}), 5, 4)).toContain("no undo");
  });
});
```

- [ ] **Step 2: Run it**

```bash
cd frontend && pnpm test tests/utils.test.ts
```

Expected: the two new cases pass once `correctionPhrase` exists.

- [ ] **Step 3: Write the dialog test**

Create `frontend/tests/correction.test.tsx`, following the idiom of `frontend/tests/start-date.test.tsx` — the same `render`, `userEvent`, `Provider`/`MemoryRouter` wrappers and the `./fixtures` helpers. Cover:

1. **The picker offers units behind.** Stub `api.rail` and assert it was called with a `from` of `actual_ordinal - 20` clamped at 1, not `actual_ordinal + 1`.
2. **Choosing a unit behind relabels the button.** Select an option whose ordinal is below `actual_ordinal`; assert the submit button reads `Correct position`, not `Record`, and that `correctionPhrase`'s text is on screen.
3. **Choosing a unit ahead leaves it as `Record`.**
4. **Submitting a backwards pick calls `correctPosition`, not `advance`.** Spy on both; assert `api.correctPosition` received `{ toOrdinal }` with `confirm` true and `api.advance` was never called.
5. **A typed ref that comes back a replay offers the correction.** Stub `api.advance` to resolve with `was_replay: true` and `resolved_ordinal` below the current position; assert the confirmation text appears and that confirming calls `api.correctPosition`.

- [ ] **Step 4: Run to verify it fails**

```bash
cd frontend && pnpm test tests/correction.test.tsx
```

- [ ] **Step 5: Open the picker's window backwards**

In `frontend/src/components/AdvanceDialog.tsx`, add beside the existing `AHEAD` constant:

```typescript
/**
 * How far back the list reaches. Far enough for any correction he would make by eye, and short
 * enough that the ordinary case — the next unit — is still what the dialog opens on.
 */
const BEHIND = 20;
```

Change the window. `first` currently is `track.actual_ordinal + 1` (`:64`); it becomes the low end of the span, while the dialog still *opens* on the next unit:

```typescript
  const next = track.actual_ordinal + 1;
  const first = Math.max(1, track.actual_ordinal - BEHIND);
```

Update the `api.rail` call and its `useEffect` dependencies to use the new `first`, and change the default selection from `ahead[0]` to the unit whose `ordinal === next` — otherwise the dialog would open twenty units behind him, which would be a trap rather than a feature.

- [ ] **Step 6: Group, relabel, and route**

In `bySefer`'s output, units with `ordinal <= track.actual_ordinal` belong in a group labelled so their direction is unmissable — prefix the `optgroup` label with `Behind — `. Then:

```typescript
  const chosenOrdinal = "unit" in chosen ? chosen.unit.ordinal : null;
  const isCorrection = chosenOrdinal !== null && chosenOrdinal < track.actual_ordinal;
```

Render `correctionPhrase(track, track.actual_ordinal, chosenOrdinal)` when `isCorrection`, and make the submit button read `Correct position` instead of `Record`. `onConfirm`'s signature gains the direction so the screen knows which thunk to dispatch — change it to:

```typescript
  readonly onConfirm: (
    destination: AdvanceDestination,
    label: string,
    note: string | undefined,
    isCorrection: boolean,
  ) => void;
```

- [ ] **Step 7: Rewrite the comment that is now false**

`AdvanceDialog.tsx:136` reads *"A closed select shows only the address, and the address repeats across sefarim. There is no way to undo an advance, so what is about to be recorded is spelled out in full."* Replace the second sentence:

```
A correction can undo one, but only deliberately and only backwards, so what is about to be
recorded is still spelled out in full.
```

- [ ] **Step 8: Wire both screens**

In `TrackScreen.tsx` and `TodayScreen.tsx`, the `onConfirm` handler dispatches `correctPosition({ trackId, destination, confirm: true })` when `isCorrection` and `advanceTrack` otherwise. On success, the correction's toast reads:

```typescript
`Back to ${result.track.at?.ref ?? "the start"} — ${result.removed_units} removed.`
```

Replace the `"Already there."` / `"<track> was already there."` replay branches: when `result.was_replay` and `result.resolved_ordinal < track.actual_ordinal`, show the correction confirmation instead of the info toast. Keep the info toast for `resolved_ordinal === track.actual_ordinal`, which is a genuine no-op.

- [ ] **Step 9: Run tests, lint and typecheck**

```bash
cd frontend && pnpm test && pnpm lint && pnpm build
```

- [ ] **Step 10: Coverage**

```bash
cd frontend && pnpm coverage
```

Expected: 100%. Add tests for any uncovered branch.

- [ ] **Step 11: Report — do not commit**

```
feat(frontend): say where you really are, backwards included
```

---

## Task 10: `ScheduleDialog`

**Files:**
- Create: `frontend/src/components/ScheduleDialog.tsx`
- Modify: `frontend/src/screens/TrackScreen.tsx`
- Test: `frontend/tests/schedule-dialog.test.tsx`

**Interfaces:**
- Consumes: `correctSchedule` thunk, `ScheduleCorrection` (Task 8)
- Produces: `ScheduleDialog` with props `{ track: TrackRow; today: string; onConfirm: (correction: ScheduleCorrection) => void; onCancel: () => void }`

- [ ] **Step 1: Write the test**

Create `frontend/tests/schedule-dialog.test.tsx`, following `frontend/tests/start-date.test.tsx`'s idiom. Cover:

1. **The date field prefills with nothing and accepts a past day**, since a schedule that began earlier is the whole point.
2. **The "I'm up to date" button fills the target with the track's current position** — assert the ref of `track.at` appears in the target field.
3. **Submitting the date field emits `{ startedOn }`**, and submitting the target emits `{ toOrdinal }` for a picked unit or `{ toRef }` for a typed one.
4. **Only one is sent.** Fill both, submit, and assert exactly one key is on the emitted correction.
5. **The per-kind hint is shown** — a daily rate-1 track reads "one day is 1 perek here"; the Chumash reads the aliyah wording.
6. **A chavrusa track never reaches the dialog** — assert the Track screen renders no button to open it when `track.period === "none"`.

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && pnpm test tests/schedule-dialog.test.tsx
```

- [ ] **Step 3: Write the dialog**

Create `frontend/src/components/ScheduleDialog.tsx`. Follow `StartDateDialog.tsx` for the overlay, form and footer markup — read it first and match it. The body carries the two named operands:

```tsx
/**
 * Corrects what a track is supposed to be up to.
 *
 * Two operands, put side by side rather than one chosen for him. They agree about today and
 * disagree about every day before it: moving the day it started leaves the opening position the
 * ledger was seeded with standing, while naming the place it should have reached restates it. Only
 * he knows which was wrong, so only he picks.
 */
```

Two radio-selected fields — a date input labelled `It started on`, and a picker plus free-text ref labelled `It should be at` with an `I'm up to date` button that fills in `track.at?.ref`. The picker reuses `api.rail` around `track.scheduled_at?.corpus_ordinal`, exactly as `AdvanceDialog` reuses it around the position.

The per-kind hint sits under the date field. Derive it from `track.kind`, `track.rate` and `track.unit_singular` — no new endpoint:

```typescript
function dayWorth(track: TrackRow): string {
  if (track.kind === "parsha_aliyah") return "one day is 1 aliyah, 2 in a combined week";
  if (track.kind === "parsha_weekly") return "one week is 1 unit, 2 in a combined week";
  const noun = track.rate === 1 ? track.unit_singular : track.unit_plural;
  const span = track.period === "week" ? "week" : "day";
  return `one ${span} is ${track.rate} ${noun} here`;
}
```

Put `dayWorth` in its own file, `frontend/src/utils/dayWorth.ts`, per the one-concept-per-file rule, and test it in `frontend/tests/utils.test.ts`.

- [ ] **Step 4: Wire the Track screen**

In `TrackScreen.tsx`, beside the existing start-date button and under the same `track.period !== "none"` guard, add a button opening the dialog. Its handler dispatches `correctSchedule({ trackId, correction })` and on success sets the returned row and pushes a toast naming where the schedule now reads:

```typescript
`Scheduled to ${row.scheduled_at?.ref ?? "the start"}.`
```

- [ ] **Step 5: Run tests, lint and typecheck**

```bash
cd frontend && pnpm test && pnpm lint && pnpm build
```

- [ ] **Step 6: Coverage**

```bash
cd frontend && pnpm coverage
```

Expected: 100%.

- [ ] **Step 7: Report — do not commit**

```
feat(frontend): say what a track is supposed to be up to
```

---

## Task 11: Documentation and contracts

**Files:**
- Modify: `CLAUDE.md` (§4 data contracts, §8 security)
- Modify: `docs/status.md`
- Modify: `docs/versions.md`

- [ ] **Step 1: Amend `CLAUDE.md` §4**

Find the paragraph beginning *"**A typed reference is never lifted into the next cycle.**"* It ends *"...and there is no undo."* The first half stands; the finality does not. Replace the closing clause so it reads:

```
Wrapping forward is the picker's job. Correcting backwards is `PUT /api/tracks/{id}/position`,
which truncates the advance rows behind a chosen point rather than writing a negative one — so
`actual_ordinal` stays `MAX(to_ordinal)` and no consumer of the ledger has to learn about
backwards motion.
```

Add a new contract paragraph after it:

```
**The schedule has two operands and they disagree about the past.** `scheduled` is
`anchor_ordinal + f(calendar)`. Moving `anchor_date` leaves every earlier day reading a flat
`anchor_ordinal`, so the opening debt the ledger was seeded with survives; shifting
`anchor_ordinal` restates it. `PUT /api/tracks/{id}/schedule` therefore takes `started_on` **or** a
target, never guessing which was wrong. Choosing silently would rewrite a measured fact.
```

- [ ] **Step 2: Amend `CLAUDE.md` §8**

Add two rows to the boundary table:

```
| `PUT /tracks/{id}/position` body | deserialization, SQL | Pydantic `extra="forbid"`, `to_ref` bounded at 256 chars, `to_ordinal` `ge=0`; SQLAlchemy bound parameters on the delete and update, no string-built SQL |
| `PUT /tracks/{id}/schedule` body | deserialization | Pydantic `extra="forbid"`, exactly-one-of validator, `to_ref` bounded at 256 chars |
```

- [ ] **Step 3: Run the local SAST set**

Read the `Local commands` section of `CLAUDE.md` for the project's exact invocation, then run it. At minimum:

```bash
cd backend && uv run pip-audit && uv run ruff check .
```

Expected: clean. Record the output for the self-audit.

- [ ] **Step 4: Add the `docs/versions.md` entry**

**Stop here and ask Amram which heading to use.** The evidence points both ways and the plan will not guess:

- `backend/pyproject.toml` still reads `version = "0.1.0"` — the release pipeline has never run.
- **Every** heading in `docs/versions.md` says "unreleased": `v0.5.0`, `v0.4.0`, `v0.3.0`, `v0.2.0`, `v0.1.0`. So the file's own practice has been to open a new heading per body of work regardless of the release state.
- The one-unreleased-version rule in `CLAUDE.md` §6, read strictly, says this work belongs *under* the existing `v0.5.0` as a subsection.
- The spec assumed `v0.6.0`.

Ask which he wants, then write it. Do not write a version number he has not confirmed.

The entry itself, in the house voice:

```markdown
### Going backwards
Amram's words: *"I don't have the ability to go backwards in my Sidra… and for some reason it
thinks I'm supposed to be at chapter fifty when I'm at chapter forty nine."* Two faults, and
neither had a lever.

- `PUT /api/tracks/{id}/position` corrects where a track actually stands. It **truncates** the
  advance rows behind the chosen point — deleting what lies past it and trimming the row that
  straddles it — so `actual_ordinal` stays `MAX(to_ordinal)` and Stats, the streak, the pace
  projection, the rail and both ceilings need no changes at all. A correction below the earliest
  row writes a synthetic opening row in the seeder's own idiom, which is what lets it pass a floor
  that would otherwise be permanent. `confirm` is required: it deletes, and there is no undo.
- `PUT /api/tracks/{id}/schedule` corrects what a track is supposed to be up to, and it names the
  two operands rather than choosing between them. `started_on` moves the origin; a target shifts
  the opening position. They agree about today and disagree about the past — moving the origin
  leaves Neviim's seeded three-perek opening debt standing, shifting the position rewrites it to
  two. Pinned by `tests/api/test_schedule_history.py`.
- `AdvanceResult` gains `resolved_ordinal`, so a replay says where it aimed instead of only that it
  went nowhere. Without it the dialog could not name a backwards reference without resolving it
  twice.
- The track router split: reads stay in `tracks.py`, every mutation moves to `track_writes.py`.
  Same prefix, same paths, no client can tell.
- Fixed on the way past: a malformed `occurred_on` on `POST /advance` was parsed outside the try
  and surfaced as a 500 rather than a 422.
```

- [ ] **Step 5: Rewrite `docs/status.md`'s lede**

Add a `## Just built: going backwards` section at the top of the "Just built" run, in the same voice as the sections already there. It must say what the two levers are, that `actual_ordinal` is still a MAX, and that the two schedule operands disagree about the past. Update the counts block at the top of the file with the real numbers from Step 6.

- [ ] **Step 6: Run everything and record the counts**

```bash
docker compose up -d postgres
cd backend && uv run pytest -m "not live" --cov=src/sidra --cov-report=term-missing && uv run ruff check .
cd ../frontend && pnpm test && pnpm lint && pnpm build
```

Put the resulting test counts into `docs/status.md`'s header block. **Do not write numbers you did not just read off the output.**

- [ ] **Step 7: Report — do not commit**

Report every file changed across all eleven tasks, and this suggested message:

```
docs: record the correction levers and their contracts
```

Then run the §9 self-audit from `CLAUDE.md`: summary, reuse check, tech-debt check, file-organization check, data-contract check, docs check, test check, measured-facts check, git state, security check.

---

## Self-Review

**Spec coverage.** Every section of the spec maps to a task: §3's MAX decision and §4's algorithm → Task 1; §5a and §5b → Task 2, exposed by Tasks 5–6; §6's position endpoint → Task 5, its schedule endpoint → Task 6, `resolved_ordinal` and the `occurred_on` fix → Task 4; §7's frontend → Tasks 8–10; §8's router split → Task 3; §9's three docstrings → Tasks 5 and 9 (code) and Task 11 (`CLAUDE.md`); §10's test table → Tasks 1, 2, 5, 6, 7, 9, 10; §12's docs → Task 11. §11's out-of-scope list is built by nothing, correctly.

**Two things the plan corrects in the spec**, both flagged in *Deviations* above: the test files move from `tests/ledger/` to `tests/db/` where they take a session, and the unconfirmed-422 message drops the calendar date.

**One thing the plan escalates rather than decides.** The spec targets version 0.6.0; `docs/versions.md` opens with an unreleased v0.5.0, and the project's one-unreleased-version rule says new work goes underneath it. Task 11 Step 4 stops and asks rather than guessing.

**Type consistency.** `Truncation`'s four fields are produced in Task 1 and consumed unchanged by `CorrectionResult` in Task 5 and `CorrectionResult` in TypeScript in Task 8. `AdvanceDestination` is reused rather than re-declared. `ScheduleCorrection` is declared once in Task 8 and consumed in Task 10. `correctionPhrase(track, from, to)` is defined in Task 9 Step 1 and called in Step 6 with the same argument order.

**Known risk, called out in-task.** Task 6's `anchor_ordinal < 1` guard raises *after* `recalibrate` has mutated the track, relying on `session.begin()` in `deps.py:68` to roll it back. The step tells the implementer to verify that transaction shape and restructure if it has changed.
