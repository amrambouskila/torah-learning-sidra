# The Maintenance Screen — Design Specification

**Date:** 2026-08-27
**Status:** Approved in session
**Author:** Design session with Amram
**Extends:** `2026-08-24-torah-sidra-design.md`

---

## 1. Purpose

Amram's words: *"i want it to be so that i can only use the app and everything that would be a cli
command would be replaced with a button in the ui."*

`sidra-db` holds nine commands. They are not equivalent, and the design turns on that:

| command | what it does | risk | becomes a button? |
|---|---|---|---|
| `status` | are the catalog and ledger seeded | read-only | yes |
| `verify` | catalog against the expected counts | read-only | yes |
| `export` | ledger → `data/ledger.json` | writes one file | yes |
| `seed` | rebuild the catalog from the committed snapshot | offline, catalog only | yes, as a job |
| `calendar` | fetch a span of the Hebrew calendar | network, additive | yes, as a job |
| `refresh` | re-crawl Sefaria, write a new snapshot | network, ~94s, ~656 MB | yes, as a job |
| `init` | create the schema | idempotent | no — the launcher runs it on boot |
| `seed-tracks` | rewrite the sidra from `tracks.yaml` | **clears the ledger** | **no** |
| `import` | replace the ledger from a file | **clears the ledger** | **no**, except §6 |

`seed_tracks.py:73` and `transfer.py:126` both call `clear_ledger`. Putting either behind a button
in the app where he taps *Advance* every morning would put "erase every advance you have recorded"
two clicks from the daily gesture. They stay in the CLI.

---

## 2. One job slot, no job table, no ids

Every slow operation is **atomic**, and that single fact removes most of what a job system usually
needs:

- `seed` runs inside `async with factory() as session, session.begin()` — killed halfway, it rolls
  back (`cli/sidra_db.py:71-74`).
- `calendar` fetches first and stores in one transaction afterwards (`cli/sidra_db.py:141-146`).
- `refresh` calls `write_snapshot` only after the crawl returns, so a killed crawl writes no file
  (`cli/sidra_db.py:93-99`).

So a job that dies with the container leaves nothing half-finished. There is nothing to resume and
nothing to clean up — only progress to report while it runs. That makes the whole apparatus **one
mutable slot on `app.state`**:

- **No database table**, no migration, and nothing derived is stored — the app's standing rule.
- **No job ids.** One slot means one job; `GET /api/maintenance/job` returns it.
- **One at a time.** Starting a second while one runs is a **409**, which also stops two crawls
  hammering Sefaria or two seeds fighting over the catalog.
- **A restart loses the job, and the screen says so** rather than pretending. That is honest, and
  it costs nothing, because nothing partial survived it either.

The cost, stated: he cannot start a crawl and a calendar fetch at once, and closing the tab loses
sight of a running job until he reopens the screen. Both are right for a single-user desktop app.

---

## 3. Progress

Nothing in the codebase reports progress today. Two optional callbacks, both defaulting to `None`
so every existing caller is unchanged:

- `crawl_catalog(..., on_progress=None)` — called once per corpus, eleven of them.
- `fetch_calendar_range(..., on_progress=None)` — called once per day, which is where the time
  actually goes: `CRAWL_PAUSE_SECONDS = 0.4` means a 400-day fetch spends **160 seconds pausing**
  before a single response is counted.

`seed` reports phases rather than a count — reading the snapshot, then writing it — because it is
one transaction with no natural tick.

---

## 4. The event loop must stay responsive

The backend's healthcheck runs every 10s with a 5s timeout, and `restart: unless-stopped` is set.
`write_snapshot` writing 656 MB synchronously would block the event loop long enough to fail that
probe, and Docker would restart the backend **in the middle of the crawl it was running**.

Every blocking call inside a job goes through `asyncio.to_thread`: `read_snapshot`,
`write_snapshot`, and `write_ledger`.

---

## 5. Surface

```
GET  /api/maintenance           catalog and ledger state, counts, last export time
POST /api/maintenance/export    fast, synchronous → counts written
POST /api/maintenance/verify    fast, synchronous → the mismatch list, empty when good
POST /api/maintenance/seed      job
POST /api/maintenance/calendar  job — {start, days}
POST /api/maintenance/refresh   job — {include_links}
POST /api/maintenance/restore   §6 — the safety copy only
GET  /api/maintenance/job       the current or last job
```

No logic is duplicated. The CLI commands are already thin wrappers over `export_ledger`,
`check_catalog`, `seed_from_snapshot`, `crawl_catalog` and `fetch_calendar_range`; the API becomes
a second caller of the same functions rather than a second implementation of them.

---

## 6. Restore, narrowly

Keeping `import` out of the app leaves a gap exactly where it hurts: `import` is how a bad
correction is undone, and the safety copy written by `PUT /position` is useless without it.

So one narrow button: **restore from the safety copy**, and only from that file.
`POST /api/maintenance/restore` takes no path — it reads `SAFETY_COPY_PATH` and nothing else, so
the general "replace my ledger from any file on disk" power stays in the CLI where it belongs. It
requires a typed confirmation (`confirm: "RESTORE"`), refuses when the file is absent, and reports
what it replaced.

This is the one button in the app that can destroy learning, and it exists only to undo the one
other thing that can.

---

## 7. Explicitly out of scope

- `init`, `seed-tracks` and general `import` stay CLI-only.
- No job history — one slot, overwritten by the next job.
- No cancellation. Every job is atomic and short of a container restart there is nothing safe to
  interrupt; a killed job is the restart, and it is already clean.
- No scheduling.
