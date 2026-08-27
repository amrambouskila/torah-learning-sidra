# Status

**Complete.** P1 (catalog and alignment), P2 (ledger and API), P3 (the UI) and P4 (Pace, Stats,
Sequence, export) all shipped, and so did the two things using the app surfaced afterwards:
correcting a position or a schedule backwards, and the Maintenance screen. **Version:** 0.6.0
(unreleased).

```
backend    950 offline tests at 100% coverage  ·  ruff clean  ·  pip-audit clean
frontend   416 tests at 100% coverage          ·  eslint clean  ·  tsc strict clean
live       78 tests green against the real Sefaria and Hebcal APIs, 2026-08-27
running    UI on 5285  ·  API on 8285  ·  PostgreSQL on 5524  ·  host 5432 untouched
```

The live suite is the acceptance gate, and it is the one that matters: a fixture can encode the
same wrong belief as the code that reads it, and only the real API contradicts it. Running it on
2026-08-27 found exactly that — see below.

## CI

`.github/workflows/ci.yml` — six stages, each gating the next: lint, sast, test, coverage, build,
docker-build. `.gitlab-ci.yml` is the same pipeline for GitLab and is kept in step. Every command
either runs green locally today or is one a fresh clone can run; `gitleaks.toml` exists so the
secret scan agrees between a workstation and CI's empty checkout.

Porting it found four failures that had never surfaced because the project had never been pushed
anywhere that runs CI: `ruff format --check` (eleven files), `uv build` (a `force-include` that
duplicated every override file into the wheel), `pip-audit --strict` (the local package is not on
PyPI), and 54 semgrep findings — of which the useful ones were two root containers, a generated
`frontend/coverage/` that was never gitignored, and four invisible bidi characters now written as
escapes. All clean.

## Image hardening

`docker-build` failed on the first push and was right to. Everything Trivy found with a fix
available is now fixed in the Dockerfiles — `apt-get upgrade` on the backend, `apk upgrade` on the
nginx stage, and the removal of the base image's bundled pip, which this image never uses and whose
*vendored* msgpack was the only Python finding. What is left is 16 Debian entries with no fix
released, which `--ignore-unfixed` skips in both pipelines. The frontend now reports zero findings
even without the flag.

## The last thing found: Sefaria moved under us

Two live tests failed on a change upstream, not on anything in this repo. Sefaria no longer serves
Even HaEzer's two one-node appendices — Seder HaGet and Seder Halitzah — as child works, so the
crawl now yields **four** Shulchan Aruch works and **1,705** simanim where the tests expected six
and 1,707.

The tests were the only holdouts. `expected_counts.json` already gated on four works and 1,705
simanim; `CLAUDE.md` §1 already documented 697 + 403 + 178 + 427 = 1,705 with the appendices
excluded; and `test_live_sidra.py` asserted a track total of 1,705 four lines above the line that
asked for ordinal 1,707. Both assertions were corrected to the measured values, and the whole live
suite is green.

That drift is also why the catalog totals moved: **277 works and 27,250 derivable units**, not the
279 / 27,252 recorded before, which counted the two appendix works. Measured against the seeded
database and confirmed by `POST /api/maintenance/verify`.

## Just built: the Maintenance screen

Amram's words: *"i want it to be so that i can only use the app and everything that would be a cli
command would be replaced with a button in the ui."* Six of `sidra-db`'s nine verbs are buttons
now — status, verify, export, seed, calendar, refresh — on a new Maintenance screen.

**Three stay in the CLI on purpose.** `init` the launcher already runs on boot. `seed-tracks` and
`import` both call `clear_ledger`: putting either behind a button in the app where he taps
*Advance* every morning would leave "erase every advance you have recorded" two clicks from the
daily gesture. The one narrow exception is **Restore**, which reads the correction safety copy and
no other file — the only button in the app that can destroy learning, and it exists to undo the
only other one that can. It is typed, not clicked.

**The job system is one mutable slot, and it is that small for a reason.** Every slow operation is
atomic: `seed` is one transaction, `calendar` fetches then stores in one, and `refresh` writes its
snapshot only once the crawl has returned. So a job that dies with the container leaves nothing
half-finished — nothing to resume, nothing to clean up, and progress the only thing left to
provide. No table, no ids, no history: one job at a time, a second start is a 409, and a restart
loses the job and says so rather than pretending.

Two optional progress hooks were added, both defaulting to nobody watching so every existing caller
is unchanged: `crawl_catalog` ticks once per corpus, and `fetch_calendar_range` once per day —
which is where the time actually goes, since `CRAWL_PAUSE_SECONDS = 0.4` means a 400-day span
spends over two minutes pausing before a single response is counted.

Every blocking call inside a job goes through `asyncio.to_thread`. `write_snapshot` writing 656 MB
synchronously would block the event loop past the container's 10-second healthcheck, and
`restart: unless-stopped` would then restart the backend in the middle of the crawl it was running.

## Just built: going backwards

Amram's words: *"I don't have the ability to go backwards in my Sidra… and for some reason it
thinks I'm supposed to be at chapter fifty when I'm at chapter forty nine."* Two faults, and
neither had a lever. Both are two new sibling endpoints; `POST /advance` and `PATCH /tracks/{id}`
were not touched, which is why every one of the ten tests pinning forward-only motion stayed green
without an edit.

**`PUT /api/tracks/{id}/position` — where he actually is.** It **truncates**: every advance row
past the chosen point is deleted and the row that straddles it is trimmed to end there, so
`actual_ordinal` stays `MAX(to_ordinal)` and Stats, the streak, the pace projection, the rail and
both ceilings needed no changes at all. A correction below the earliest row writes one synthetic
opening row in the seeder's own idiom — without it the earliest `from_ordinal` would be a floor no
correction could pass. `confirm` is required, and the refusal names the cost in his own units
rather than asking a blank "are you sure".

**Every correction is recoverable.** Before a truncation deletes anything, the whole ledger goes to
`backend/data/ledger.before-correction.json`, and a copy that cannot be written refuses the
correction outright. Recovery is the import path that already existed:
`uv run sidra-db import --source data/ledger.before-correction.json`. Not the portable
`data/ledger.json`, which the launcher imports into an empty ledger — leaving the pre-correction
state there would restore the very thing he had corrected away. `./backend/data` gained a bind
mount for it: the image bakes that directory in, so the copy was landing inside the container and
would have died on the next `[r]` restart.

**`PUT /api/tracks/{id}/schedule` — where he is supposed to be.** `scheduled` is
`anchor_ordinal + f(calendar)`, so a miscalibration is in one of two operands, and **they disagree
about the past**. Moving `anchor_date` leaves every earlier day reading a flat `anchor_ordinal`;
shifting `anchor_ordinal` restates them:

| route | 24 Aug | 27 Aug | opening debt Stats reports |
|---|---|---|---|
| `started_on` → 25 Aug | Jeremiah 47 · *before the origin* | Jeremiah 49 | **3** |
| target → Jeremiah 49 | Jeremiah 46 | Jeremiah 49 | **2** |

Both land on the same place today. Choosing between them silently would have rewritten the measured
opening debt of three perakim without anyone asking, so the endpoint takes `started_on` **or** a
target and never guesses. `tests/api/test_schedule_history.py` pins both rows of that table.

**His Neviim case needs both.** The seeder stamped `anchor_date` with its own run day and billed it
as a learning day; his reading is that Jeremiah 47 was already true *for* the 24th. So:
`{"started_on": "2026-08-25"}` puts the schedule on Jeremiah 49, and
`{"to_ordinal": 262, "confirm": true}` trims today's two-perek entry to one.

Also in this change: `AdvanceResult` gained `resolved_ordinal`, so a replay says where it aimed
instead of only that it went nowhere — without it the dialog could not name a backwards reference
without resolving it twice. The track router split, reads staying in `tracks.py` and every mutation
moving to `track_writes.py`, same prefix and same paths. And a malformed `occurred_on` on
`POST /advance` was parsed outside the try and surfaced as a 500; it is a 422 now.

On the screens: the Advance dialog's picker opens twenty units *behind* him as well as ahead, in a
group labelled so the direction is unmissable, and relabels its button to **Correct position** with
the cost spelled out. A reference typed by hand only reveals its direction once the server has
resolved it, so a replay that landed behind him is now an offer to correct rather than a shrug. A
rail node behind the marker takes the same path. The Track screen gained a **Schedule** button
opening a dialog that puts the two operands side by side, with an **I'm up to date** shortcut that
fills in his current position.

## Just built: the Rambam picks the masechta

`GET /api/sequence/{track_id}` and a Sequence screen. The Gemara follows the Mishneh Torah rather
than Shas order, and a hilchos section with no masechta of its own does not move him. A section
counts as having one only when a masechta holds a quarter of its citations and leads the runner-up
by half again — measured across all 84 books, which is why Teshuvah, Deos and Talmud Torah name
none and Hilchos Avoda Zara names Avodah Zarah.

## Just built: tagging a track

`PUT /api/tracks/{id}/tags` and a Tags row on the Track screen. Until now nothing but the seeder
could write the track↔tag link, so a tag made in the app could never actually be worn.

## Just built: Stats

`GET /api/stats` and the screen over it. Each cell is `billed − learned` for one track on one day,
signed — the ledger's question, not a habit tracker's. Debt over time is reconstructed exactly
rather than stored, and reproduces the spec's measured 20 amudim and 3 perakim. The window clamps
to the ledger's age and says so; today it draws three columns.

## Just built: the parsha calendar reads real parshiyos

`ParshaIndex` resolves a calendar label against the catalog's fifty-four rather than splitting it
on a hyphen. `Lech-Lecha` is one parsha, not two; `Rosh Hashana I` and `Sukkot I` supply none.
Both were billing weeks that are never read. The calendar has been re-crawled and the Chumash's
2026-09-18 debt drops from 31 to 24.

Sefaria never names V'Zot HaBerachah — read on Simchat Torah, never a Shabbos in the diaspora — so
`close_the_cycle` adds it to the week that already carries Bereshit, which is what that morning is.
A real crawled year now bills **378 aliyot across all 54 parshiyos**, pinned by a live test.

Parsha tracks now **wrap**. Their ordinals are cumulative and unbounded; only the address folds,
so debt carries across Simchat Torah rather than freezing. A cycle track is never "finished", one
`reachable_ceiling` bounds the endpoint, the rail and the picker alike, and a typed reference is
never lifted into the next turn — a correction backwards stays a replay.

## Just built: advancing by reference

An advance is recorded by saying where he stopped — `5:7`, `38b`, `Siman 12` — not by counting
units. `POST /api/tracks/{id}/advance` takes `to_ref` or `to_ordinal`, exactly one; the dialog
offers the next 200 units as a dropdown grouped by sefer, showing no ordinal anywhere. A unit
picked off the list travels as its ordinal, because a track spanning books repeats its addresses
in each of them — `1:1` appears twice on the Mishneh Torah track, and as a ref both would resolve
to the first. A bare address he types resolves against the work he is standing in first.

## Verified in a browser, not only in tests

The whole stack was brought up and driven on 2026-08-25 against the real seeded sidra:

```
Today       21 amudim behind (Gemara), 4 perakim behind (Neviim) — the ledger a day past its anchor
Track       the Avodah Zarah rail, lit to 28b, ghost at 39a, 36% · 54 of 150 amudim
Roadmap     Gemara finishes 2026-11-29, Ketuvim 2027-08-06 — within a day of the spec's estimates
Chavrusas   all five, staleness "yesterday", session logs with Hebrew dates
Alignment   Hilchos Avoda Zara ranks Avodah Zarah first at 42% (200 links), Sanhedrin 27%
Advance     typed 5:8 on David Cohen — Mishneh Torah, read back as a replay, ledger unmoved
Picker      200 units over 3 hilchos books; Torah Study 1:1 carries ordinal 160, not 89
```

## The acceptance gate

Two live suites hold the numbers. `tests/test_reference_values.py` crawls the real API and asserts
every seed ref resolves. `tests/test_live_sidra.py` then seeds the real sidra on top and asserts
the debts Amram measured off his Obsidian note.

```
Gemara   Avodah Zarah 28b -> 38b        debt 20 amudim      label כ״ח ע״ב
Neviim   Jeremiah 44 -> 47              debt 3 perakim
Chumash  378 aliyot, never the 432 rows Parashat HaShavua holds
SA       opens at Orach Chaim 1, not Choshen Mishpat 1
Rambam   Deos before Avoda Zara — the Rambam's order, two independent chavrusa tracks
Sidra    20 tracks: 6 daily, 9 Shabbat, 5 chavrusa; parsha tag spans two categories
Calendar Shabbos Bereishis 2026 = 10 October; Nitzavim-Vayeilech detected as combined
```

## What P3 built

| Screen | Answers |
|---|---|
| Today | what do I owe, grouped and debt-ordered, one click to advance |
| Track | the full two-marker rail — the gap between the markers is the debt, drawn |
| Roadmap | when does each track finish, and what a yearly cycle would cost |
| Chavrusas | how long has it been, and what did we cover |
| Tags | the labels that cut across the three fixed categories |
| Alignment | which masechtos sit behind the hilchos this track is in |

The rail is windowed: it fetches 100-unit spans as they scroll into view, so a 15,143-halachah
track never becomes 15,143 DOM nodes. Everything else is a plain render over the P2 endpoints.

## What P2 built

| Piece | Where |
|---|---|
| Debt ledger | `ledger/schedule.py` — `scheduled - actual`, surplus banks as "N days ahead" |
| Position resolution | `ledger/position.py` — an ordinal to a real ref, across a whole corpus |
| Hebrew calendar | `calendar/` — parsha from Sefaria, Hebrew date and Yom Tov from Hebcal |
| Parsha schedules | `ledger/parsha_schedule.py` — a combined week owes two a day, not one |
| The seeded sidra | `data/tracks.yaml` + `ledger/seed_tracks.py` |
| Per-track state | `ledger/track_state.py` — one function, dispatching on track kind |
| REST API | `api/` — FastAPI on 8285, nine endpoints plus `/health` |

The clock ticks every calendar day, Shabbos and Yom Tov included. Nothing derived is stored: the
Today view recomputes every debt per request, so the screen cannot drift from the ledger.

## Measured catalog

| Corpus | Works | Units |
|---|---:|---:|
| Torah (5 chumashim + parsha cycle) | 6 | 619 |
| Neviim | 21 | 380 |
| Ketuvim | 13 | 362 |
| Mishnah | 63 | 525 |
| Talmud Bavli | 37 | 5,349 |
| Mishneh Torah | 84 | 15,143 |
| Shulchan Aruch | 4 | 1,705 |
| Mussar | 34 | 572 |
| Chassidus | 11 | 1,396 |
| Midrash | 1 | 1,037 |
| Parsha-weekly | 3 | 162 |
| **Total** | **279** | **27,252** |

Plus 432 stored units, 4,235 aliases, 121,289 topic links.

## Defects the live tests caught that fixtures never would

P1's nine, plus three more from P2:

10. **The Shulchan Aruch was in alphabetical order.** Sefaria's shape returns Choshen Mishpat
    first, so a one-siman-a-day cycle would have opened at CM 1 instead of Orach Chaim 1.
    `shulchan_aruch_order.yaml` fixes it, the same way `ketuvim_order.yaml` fixes Koheles.
11. **Shulchan Aruch is the 1,705 simanim of the four chalakim.** Even HaEzer's two one-node
    appendices, Seder HaGet and Seder Halitzah, are excluded: procedural orders, not simanim
    anybody learns one a day. The exclusion runs after Even HaEzer is expanded, because a complex
    node's children only carry their own titles once it has been split.
12. **The coverage gate was measuring less than it reported.** `coverage` loses its tracer across
    the greenlet switch SQLAlchemy's async bridge makes, so every line after the first `await` on
    the database inside a request handler went unrecorded — the API routers read as 100% while
    barely a third was traced. `concurrency = ["thread", "greenlet"]` restored it.

## Start dates

A track can declare the day its schedule begins. Until then it waits — no debt, just a countdown —
and on that day it owes exactly one period's worth, because the start day is a learning day.

Setting one **forgives** whatever the track ran up while it sat unopened. That is the point for a
sefer not started yet and it would be vandalism on one already being learned, so the endpoint
refuses a track that has been opened while its schedule is running. The two measured debts are
unreachable from it by construction.

Finding this feature also found a bug: the schedule used to count from the anchor date rather than
the start date, so all three parsha-weekly works would have opened **seven units behind** on
Shabbos Bereishis. Verified fixed against the live ledger: debt 0 on 9 October, debt 1 on the 10th.

## Open questions for Amram

- **Twenty tracks, not twenty-one.** The P2 plan said twenty-one; spec §6 lists 6 + 9 + 5 = 20 and
  the seed matches the spec. If a track is missing, it is missing from the spec too.

## Portability — what travels with the folder

The catalog is reproducible; the ledger is not. Every advance exists nowhere but the database, and
that database lives in the Docker named volume `sidra_postgres_data`, which is in Docker's storage
rather than in the project directory. So two files carry the app:

| File | Holds | Rebuilt by |
|---|---|---|
| `backend/data/snapshots/p1.jsonl` | 279 works, 27,252 units, 121,289 links (19 MB) | `sidra-db refresh` (network) |
| `backend/data/ledger.json` | 20 tracks, every advance, 5 chavrusas, tags, 400 calendar days | `sidra-db export` |

**Moving to another machine:** run `uv run sidra-db export`, copy the whole folder, run the
launcher. It creates the schema, seeds the catalog from the snapshot, and imports the ledger — all
offline. Rehearsed end to end on 2026-08-25 by wiping the ledger and calendar and restoring from
the export: all 20 tracks, positions, advances, tags and chavrusas came back identical.

**The one thing to remember:** export before copying. Without a fresh export the copy carries the
sidra as of the last one.

## Environment notes

- uv pins Python **3.13** (`backend/.python-version`); the system has 3.14, whose asyncpg wheels
  are not yet reliable.
- pytest-asyncio **1.4.0** needs both `asyncio_default_fixture_loop_scope` and
  `asyncio_default_test_loop_scope` set to `"session"`.
- The `db_session` fixture uses `join_transaction_mode="create_savepoint"`.
- Coverage needs `concurrency = ["thread", "greenlet"]`. Without it the gate silently under-reports
  everything behind an `await` on the database.
- `live`-marked tests hit the network and stream ~656 MB; excluded from CI, run deliberately with
  `uv run pytest -m live`. The default suite runs with `-m "not live"`.

## Not yet done

- **Nothing is committed to git — the project is not a git repository yet.** `p1.jsonl` and
  `ledger.json` both exist and neither is gitignored, so `git init` will pick them up.
- **Maftir** is deferred: the index alt-struct carries seven aliyot, and the eighth lives only in
  `/api/calendars`.
- **The calendar runs to 2027-09-27.** Extend it before then with
  `uv run sidra-db calendar --start 2027-09-28`, or the Chumash track starts returning 409.
- **Export is a manual step.** Run `uv run sidra-db export` before copying the folder anywhere, or
  the copy carries the sidra as of the last export.

## Not doing: Obsidian

Built on 2026-08-25 and removed the same day. Amram is moving off Obsidian and wants the app
itself; the app was always meant to *replace* the note, so writing it back was circular.

**The consequence, unsolved:** the app is desktop-only and localhost-only. There is no way to read
the sidra away from this machine. If that matters, the answer is a read-only view reachable from a
phone — not a file.

## Next

**Stats**, the last P4 item — advance heatmap, per-track pace, streaks. Designed and adversarially
reviewed; the review broke the first design three ways and the repairs are recorded:
1. `GET /api/stats` would 409 for every caller today, because four live tracks have a start date in
   the future and `periods_elapsed` raises on a future origin. Gate `starts_on` before any origin
   arithmetic, as `ledger_state` and `track_state` already do.
2. `window_days` goes negative on those same rows.
3. Re-deriving the window's requirement from `rate` double-counts by one day and would label square
   tracks "slipping", contradicting the debt badge beside them. Diff the schedule the ledger already
   computes instead, so pace agrees with debt by construction.

**Superseded — P4 as originally scoped.** The Pace Explorer (set a horizon of 1 / 3 / 7 / 18 years and see the required
daily rate, or set a rate and see the horizon), Stats (advance heatmap, per-track pace, streaks),
and the **Obsidian export** — the app writing the note that started this whole project. JSON
export/import already landed early in P2.
