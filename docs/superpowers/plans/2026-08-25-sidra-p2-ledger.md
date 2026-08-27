# Torah Learning Sidra — P2 (Ledger & Engine) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the catalog into a tracker — tracks with positions, a debt ledger that knows how far behind you are, dated projections, and a REST API the UI will consume.

**Architecture:** The debt engine is **pure arithmetic over the catalog** (spec §5). A track holds a rate, a period and an anchor; everything else is computed per request and never stored, so derived state cannot drift from the ledger. Calendar-driven tracks (Chumash) get their scheduled position from a snapshotted Hebrew calendar rather than a live call.

**Tech Stack:** As P1, plus FastAPI + uvicorn. No new data sources at runtime — nothing in P2 re-reads Sefaria.

**Spec:** `docs/superpowers/specs/2026-08-24-torah-sidra-design.md` — §4.2 (ledger), §5 (schedule engine), §6 (track inventory).

**Prerequisite:** **P1 complete and green.** P2 consumes exactly three things: `unit_at`, `Work.unit_count`, and `TopicLink` + `rank_masechtos`.

**Scope:** Seven tasks. Ends with Amram's twenty-one real tracks seeded, his two real debts computed correctly, and an API serving a Today view.

---

## Global Constraints

Unchanged from P1. The ones that bite here:

- **Derived state is never stored.** Scheduled position, debt and projections are computed per request.
- **No mocking of the database.** Real compose Postgres.
- **No test touches the network** except `live`-marked ones.
- **Full type annotations, no `Any` in signatures, one concept per file.**
- **Git is Amram's.** Commit points only.

---

## The model, restated

```
scheduled = anchor_ordinal + rate x periods_elapsed(anchor_date -> today)
actual    = ordinal of the latest Advance
debt      = scheduled - actual        negative debt = credit, and it banks
```

| Decision | Value |
|---|---|
| Clock | ticks **every calendar day**, Shabbos and Yom Tov included |
| Surplus | **banks**, displayed as "N days ahead", never as a negative |
| Chumash | weekly parsha, **missed aliyot are owed**, **two a day** in a combined-parsha week |
| Chavrusa | `period = NONE` — no debt, staleness only |
| Future tracks | `starts_on` accrues no debt before its date |
| Shulchan Aruch | one **siman** a day |

Amram's two measured debts, which the acceptance gate asserts:

```
Gemara   actual Avodah Zarah 28b,  scheduled 38b   ->  20 amudim
Neviim   actual Jeremiah 44,       scheduled 47    ->   3 perakim
```

---

# Task 1: The ledger models

**Delivers:** the six tables that hold Amram's data.

**Files:** `backend/src/sidra/db/models/{track,advance,chavrusa,tag,track_tag,track_alignment}.py` · tests

**Produces:**

- `TrackKind(StrEnum)` — `CORPUS CURATED_QUEUE PARSHA_ALIYAH PARSHA_WEEKLY OPEN`
- `Period(StrEnum)` — `DAY WEEK NONE`
- `Category(StrEnum)` — `DAILY SHABBAT CHAVRUSA`
- `Track` — `id, name_en, name_he, category, kind, corpus_id | None, work_ref_title | None, rate, period, anchor_date, anchor_ordinal, starts_on | None, chavrusa_id | None, is_active`
- `Advance` — `id, track_id, from_ordinal, to_ordinal, unit_count, occurred_at (tz-aware), hebrew_date, note | None`
- `Chavrusa` — `id, name, notes | None`
- `Tag` — `id, name (unique), name_he | None, color | None`
- `track_tags` — association table
- `TrackAlignment` — `follower_track_id, leader_track_id, mode`

**Contracts:** `category` is exactly one of three and is a display grouping; `chavrusa_id` is a
relation. A track can be a chavrusa track *and* sit in the Chavrusa category, but the two are
independent columns. Tags are pure labels with no cadence and no side effects.

- [ ] **Step 1: TDD the three enums** — every value is its lowercased name; the member sets are exactly as listed.

- [ ] **Step 2: TDD the six models** — one round-trip integration test each. Assert `occurred_at` comes back timezone-aware; a duplicate `Tag.name` is rejected; deleting a tag removes the association and not the track; `Advance.note` survives Hebrew.

- [ ] **Commit point** — models and tests. Suggested message: `feat(ledger): tracks, advances, chavrusas and tags`

---

# Task 2: The debt engine

**Delivers:** the arithmetic. Pure functions, no database, no calendar.

**Files:** `backend/src/sidra/ledger/{period,schedule,ledger_state}.py` · tests

**Produces:**

```python
def periods_elapsed(anchor: date, today: date, period: Period) -> int
def scheduled_ordinal(anchor_ordinal: int, rate: int, periods: int) -> int


@dataclass(frozen=True, slots=True)
class LedgerState:
    scheduled: int
    actual: int
    debt: int              # positive = behind
    days_ahead: int        # max(0, -debt) // rate; the display form
    starts_in_days: int | None


def ledger_state(track, actual_ordinal, today, periods_override=None) -> LedgerState
```

**Contract:**

- `DAY` counts calendar days inclusive of the anchor; `WEEK` counts whole weeks; `NONE` raises.
- Surplus **banks**: a negative debt is real and carries forward.
- `days_ahead` is `max(0, -debt) // rate`, so it is never negative and never implies licence to stop.
- A track with `starts_on` in the future has `debt == 0` and a `starts_in_days` count.
- `scheduled` never exceeds the track's unit total — a finished track is finished.

- [ ] **Step 1: TDD `periods_elapsed`** — same day is 1; a week later is 8 for `DAY` and 2 for `WEEK`; a date before the anchor raises; `NONE` raises naming the period.

- [ ] **Step 2: TDD `ledger_state` against the two measured debts**

Build a Gemara track anchored so that today's scheduled ordinal is 38b's seq, with actual at 28b's seq, and assert `debt == 20`. Same for Jeremiah: `debt == 3`. Derive both seqs through `real_amudim` — never hard-code, since `seq` is not the shape index.

Then: a track exactly on schedule has `debt == 0` and `days_ahead == 0`; three extra units on a 1/day track give `debt == -3` and `days_ahead == 3`; two missed days after that return it to zero; a `starts_on` two weeks out gives `debt == 0` and `starts_in_days == 14`.

- [ ] **Commit point** — `feat(ledger): debt engine with banking and projections`

---

# Task 3: Position resolution

**Delivers:** turning a track ordinal into a real ref, across a corpus that spans many works.

**Files:** `backend/src/sidra/ledger/position.py` · tests

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class Position:
    work_ref_title: str
    seq_in_work: int
    ref: str
    label_en: str
    label_he: str
    corpus_ordinal: int


async def position_at(session, track, corpus_ordinal) -> Position
async def track_total(session, track) -> int
```

A `CORPUS` track's ordinal runs across every work in its corpus in `corpus_seq` order — this is what makes Neviim one 380-perek stream rather than 21 separate ones. `position_at` walks the works, finds the one holding that ordinal, and delegates to `unit_at`.

- [ ] **Step 1: TDD against a seeded catalog** — ordinal 1 of Neviim is Joshua 1; the ordinal for Jeremiah 44 resolves to `Jeremiah 44`; ordinal 76 of Mishnah is `Mishnah Shabbat 1`; the last ordinal of a corpus is its final work's final unit; an ordinal past the end raises naming the total.

- [ ] **Step 2: TDD a `CURATED_QUEUE` track** — Gemara runs one masechta at a time, so its ordinal is within the current work rather than across a corpus.

- [ ] **Commit point** — `feat(ledger): resolve a track ordinal to a catalog ref`

---

# Task 4: The Hebrew calendar

**Delivers:** the parsha for any date, the Hebrew date, and Yom Tov — snapshotted, not fetched at runtime.

**Files:** `backend/src/sidra/calendar/{calendar_day,calendar_source,snapshot}.py` · `backend/src/sidra/db/models/calendar_day.py` · tests

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class CalendarDay:
    civil_date: date
    hebrew_date: str
    parsha_en: tuple[str, ...]     # one entry, or two in a combined week
    is_yom_tov: bool


async def fetch_calendar_range(client, start: date, end: date) -> list[CalendarDay]
async def calendar_day(session, on: date) -> CalendarDay
```

**Sources:** parsha from Sefaria `/api/calendars?year=&month=&day=&diaspora=1`, which is dateable
for any date. Hebrew date and Yom Tov from Hebcal's HTTP API (CC-BY, no key). **`@hebcal/core` is
deliberately not bundled** — it is GPL-2.0, and copyleft in the frontend should be a decision
rather than an accident.

A combined week returns **two** parsha names; the Chumash track then owes 14 aliyot across 7 days.

- [ ] **Step 1: TDD the parsers** against recorded payloads — a single parsha week; a combined week yielding two names; a Yom Tov day.

- [ ] **Step 2: TDD the snapshot** — a year of days persists and reads back; a missing day raises naming the date rather than returning a default.

- [ ] **Step 3: `live` verification** — fetch a real year and assert Shabbos Bereishis 2026 falls on 10 October, and that at least one week in the year is combined.

- [ ] **Commit point** — `feat(calendar): snapshotted Hebrew calendar with parsha and Yom Tov`

---

# Task 5: Chumash and the parsha-weekly tracks

**Delivers:** the two calendar-driven track kinds.

**Files:** `backend/src/sidra/ledger/parsha_schedule.py` · tests

**Contract:**

- `PARSHA_ALIYAH` — the week's parsha supplies seven aliyot, one a day. **Missed aliyot are owed**, so the track carries a debt ledger like any other. A combined week supplies fourteen, two a day.
- `PARSHA_WEEKLY` — one unit per parsha week; `starts_on` 2026-10-10 for all three works.

- [ ] **Step 1: TDD the aliyah schedule** — a normal week assigns Rishon through Shvi'i across seven days; a combined week assigns two a day; a missed day accrues one unit of debt; the track never silently rolls past an unfinished parsha.

- [ ] **Step 2: TDD the weekly schedule** — before `starts_on`, debt is zero and `starts_in_days` counts down; after it, one unit accrues per parsha week.

- [ ] **Commit point** — `feat(ledger): calendar-driven Chumash and parsha-weekly schedules`

---

# Task 6: Seed the real sidra

**Delivers:** Amram's twenty-one actual tracks, with his real positions.

**Files:** `backend/src/sidra/ledger/seed_tracks.py` · `backend/data/tracks.yaml` · tests

The full inventory is spec §6. Daily at one a day: Chumash (aliyah), Neviim (perek), Ketuvim
(perek), Mishna (perek), Gemara (amud), Shulchan Aruch (siman). Shabbat at one a week: seven
sefarim plus three parsha-weekly works starting 2026-10-10. Chavrusa with no rate: Rabbi Jacob,
David Cohen, David Hadar, Yosef Mendelson & David Gofman, Nesher.

One tag, `parsha`, on Chumash plus the three parsha-weekly works.

- [ ] **Step 1: Write `tracks.yaml`** with every track, its rate, period, anchor and current position.
- [ ] **Step 2: TDD the seeder** — twenty-one tracks; positions resolve to real catalog units; the `parsha` tag lands on four tracks across two categories.
- [ ] **Step 3: `live` acceptance** — seed a real catalog and assert the Gemara track owes 20 amudim and the Neviim track owes 3 perakim, on the real dates.

- [ ] **Commit point** — `feat(ledger): seed the real sidra`

---

# Task 7: The REST API

**Delivers:** FastAPI on port 8285, serving what the P3 UI needs.

**Files:** `backend/src/sidra/api/{app,routers/{today,tracks,chavrusas,tags,alignment}}.py` · Pydantic response models · tests

**Endpoints:**

| Method | Path | Returns |
|---|---|---|
| `GET` | `/api/today` | every active track with position, debt and staleness, grouped by category |
| `GET` | `/api/tracks` | the track list |
| `GET` | `/api/tracks/{id}` | one track with its full unit rail and both markers |
| `POST` | `/api/tracks/{id}/advance` | record an advance, optionally with a note |
| `GET` | `/api/roadmap` | dated projections per track |
| `GET` | `/api/chavrusas` | per person, staleness-sorted, with session history |
| `GET`/`POST`/`PATCH`/`DELETE` | `/api/tags` | tag CRUD |
| `GET` | `/api/alignment/{track_id}` | ranked masechtos with concentration, inferred edges marked |

Every response model is Pydantic v2. `/api/today` is the one that has to be fast; it computes
`ledger_state` per track and does not store anything.

- [ ] **Step 1: TDD the response models** — a track row carries Hebrew and Latin labels, debt, and a rail with two markers.
- [ ] **Step 2: TDD each endpoint** against a seeded database with `httpx.ASGITransport`.
- [ ] **Step 3: Advance is idempotent under replay** — posting the same advance twice does not double-count.
- [ ] **Commit point** — `feat(api): REST surface for the Today view, tracks, chavrusas and tags`

---

## Definition of Done for P2

- [ ] The Gemara track reports **20 amudim behind**; Neviim reports **3 perakim behind**.
- [ ] Surplus banks and displays as "N days ahead", never as a negative.
- [ ] The clock ticks on Shabbos and Yom Tov.
- [ ] A combined-parsha week assigns two aliyot a day.
- [ ] The three parsha-weekly tracks show "starts in N weeks" until 2026-10-10 and accrue no debt.
- [ ] Chavrusa tracks carry no debt, only staleness.
- [ ] The `parsha` tag spans Daily and Shabbat.
- [ ] `GET /api/today` returns every active track with a correct debt.
- [ ] 100% coverage; ruff clean; SAST green; `-m live` green.
