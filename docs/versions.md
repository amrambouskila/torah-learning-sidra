# Versions

## v0.6.0 — unreleased

### CI, and what porting it found
`.gitlab-ci.yml` ported to `.github/workflows/ci.yml` for a public GitHub repo: the six stages
become a `needs:` graph, CodeQL joins semgrep in the sast stage, and both test jobs publish JUnit
through `dorny/test-reporter`, which is how GitHub shows a per-test-case breakdown at all.

Running every command locally first found four things that would have made the first push red, none
of which had been noticed because the project had never been pushed anywhere that runs CI:

- **`ruff format --check` failed on eleven files.** The gate has always been there; this session had
  been running `ruff check` alone. Formatted.
- **`uv build` failed outright.** `[tool.hatch.build.targets.wheel] packages = ["src/sidra"]` already
  carries the YAML overrides, and the `force-include` of the same directory added every one of them
  a second time at the same archive path, which hatchling refuses. The force-include is gone and the
  wheel still ships all five override files.
- **`pip-audit --strict` failed on the local package**, which is not on PyPI and never will be.
  `--strict` counts an un-auditable distribution as a failure, so it now audits
  `uv export --no-emit-project` — the locked dependencies, which is what an audit is about.
- **semgrep found 54 blocking issues** on the rulesets CLAUDE.md §19 names. Two were real ERRORs
  (both images run as root, deliberately, now documented and excluded by rule), one was a generated
  `frontend/coverage/` directory that was never gitignored and would have been committed, and four
  were bidi characters in the advance dialog — genuine RTL isolates, now written as `⁧`
  escapes so the file contains nothing invisible. Zero findings today.

An adversarial review of the port then caught three more: every `pnpm/action-setup` step lacked
`package_json_file`, and with no `package.json` at the repository root the action throws
"No pnpm version is specified" — which would have failed `eslint` and, through the `needs` graph,
every job after it. Trivy had picked up an `ignore-unfixed: true` the GitLab original does not
have, which quietly weakened the image gate on exactly the Debian CVEs it most often sees. And
`gitleaks-action` scans a push's commit range without redacting, where the original scans the tree
with `--redact` — which on a public repository is the difference between finding a secret and
printing it.

### The first push, and the images it hardened
`docker-build` was the one stage that failed on GitHub, and it was right to. Trivy on
`python:3.13-slim` and `nginx:alpine` found HIGH/CRITICAL findings of two very different kinds, and
the fix is different for each:

- **Fixable, so fixed.** `nginx:alpine` carried openssl 3.5.7-r0 against a published 3.5.8-r0, so
  the runtime stage now runs `apk upgrade --no-cache` and reports **zero** findings. The backend
  reported msgpack 1.1.2 and setuptools — neither a dependency of this project: they live inside
  the base image's bundled **pip**, which an image that runs `uv` never uses. `apt-get upgrade`
  plus removing pip clears them.
- **Unfixable, so ignored deliberately.** What remains on the backend is 16 Debian findings, every
  one `fix_deferred` or `affected` — no fix released, nothing to upgrade to. `--ignore-unfixed` is
  back in both pipelines with that measurement written beside it. A gate that stays red for
  something no commit can address is a gate that stops being read.

Verified after the change: both images build, the stack comes up healthy, and the API answers 277
works and 25 advances through the hardened backend.

Then it failed a second time, on `Unable to resolve action aquasecurity/trivy-action@0.28.0`. That
action publishes `0.x.y` releases rather than the vendor-maintained major tag every other action in
the workflow uses, so pinning it meant naming a version that had to be checked to exist -- and it
did not. Both scans now run the plain `docker run aquasec/trivy` command instead: byte-for-byte
what `.gitlab-ci.yml` runs, nothing to resolve, and the invocation that had already been verified
locally. Every remaining action tag was then checked against the GitHub API; all eight return 200.

### Sefaria moved under us, and the live gate caught it
Running the live suite to certify the release found two failures — upstream drift, not a regression.
Sefaria no longer serves Even HaEzer's two one-node appendices, Seder HaGet and Seder Halitzah, as
child works, so the crawl yields **four** Shulchan Aruch works and **1,705** simanim where the tests
expected six and 1,707.

Every other authority in the repo already said 1,705: `expected_counts.json` gates on four works and
1,705 units, `CLAUDE.md` §1 documents 697 + 403 + 178 + 427 with the appendices excluded, and
`test_live_sidra.py` asserted a track total of 1,705 four lines above the line asking for ordinal
1,707 — an internal contradiction the extra works had been masking. Both assertions were corrected
to the measured values and all 78 live tests pass.

The catalog totals in `CLAUDE.md` §1 moved with it: **277 works, 27,250 derivable units, 4,167
aliases**, re-measured against the seeded database. The old 279 / 27,252 counted the two appendix
works.

### The Maintenance screen
Amram's words: *"i want it to be so that i can only use the app and everything that would be a cli
command would be replaced with a button in the ui."*

Six of `sidra-db`'s nine verbs are buttons now — `status`, `verify`, `export`, `seed`, `calendar`,
`refresh` — behind `/api/maintenance`. No logic is duplicated: the CLI verbs were already thin
wrappers over `export_ledger`, `check_catalog`, `seed_from_snapshot`, `crawl_catalog` and
`fetch_calendar_range`, so the routes are a second caller rather than a second implementation.

**Three stay in the CLI, deliberately.** `init` the launcher runs on boot. `seed-tracks`
(`seed_tracks.py:73`) and `import` (`transfer.py:126`) both call `clear_ledger`, and neither
belongs two clicks from the button he taps every morning.

**The job system is one mutable slot on `app.state`.** That is the whole apparatus, and it is that
small because every job is atomic — `seed` is one transaction, `calendar` fetches then stores in
one, `refresh` writes its snapshot only after the crawl returns. A job that dies with the container
leaves nothing half-finished, so there is nothing to resume and nothing to clean up, and progress
is the only thing left to provide. No table, no migration, no ids, no history. One at a time, which
also stops two crawls hammering Sefaria; a second start is a 409; a restart loses the job and the
screen says so instead of pretending.

- Two optional progress hooks, both defaulting to `None` so every existing caller is untouched:
  `crawl_catalog` ticks once per corpus, `fetch_calendar_range` once per day. The second is where
  the time actually is — `CRAWL_PAUSE_SECONDS = 0.4` means a 400-day span waits over two minutes
  before a single response is counted.
- Every blocking call inside a job goes through `asyncio.to_thread`. `write_snapshot` writing
  656 MB synchronously blocks the event loop past the container's 10-second healthcheck, and with
  `restart: unless-stopped` Docker would restart the backend mid-crawl.
- **Restore**, narrowly. Keeping `import` out left the gap exactly where it hurts: `import` is how
  a bad correction is undone. So `POST /api/maintenance/restore` takes **no path** — it reads
  `SAFETY_COPY_PATH` and nothing else, requires `RESTORE` typed in full, and is the only button in
  the app that can destroy learning. `tests/api/test_maintenance.py` pins the whole loop: advance,
  correct backwards, restore, back where he was.
- `DEFAULT_SNAPSHOT_PATH` now has one definition in `catalog/snapshot.py` rather than the same
  expression in the CLI and the API.
- `ledger_path` joins `safety_copy_path` as a dependency, so a test pressing Export cannot
  overwrite the committed ledger.

### Going backwards
Amram's words: *"I don't have the ability to go backwards in my Sidra… and
for some reason it thinks I'm supposed to be at chapter fifty when I'm at chapter forty nine."*
Two faults, independent of each other, and neither had a lever.

### Correcting where a track actually stands
`PUT /api/tracks/{id}/position` **truncates**: every advance row past the chosen point is deleted
and the row that straddles it is trimmed to end there. That is the whole design decision. Nine
consumers of the ledger — Stats, the streak, the pace projection, the rail, both ceilings,
`is_finished`, `cycle_index` — are built on advances that only move forward, so rather than teach
all of them about backwards motion, a correction makes the rows tell the truth and
`actual_ordinal` stays `MAX(to_ordinal)`. Not one of them changed.

- A correction below the earliest row writes one synthetic opening row in the seeder's own idiom
  (`from_ordinal = max(0, target - rate)`). Without it the earliest row's `from_ordinal` was a
  floor no correction could pass, and rolling back past it would have reported the track as never
  opened.
- `confirm` is required, and the refusal names the cost in the track's own units rather than
  asking a blank "are you sure": *"Jeremiah 49 is 1 perek behind Jeremiah 50; this removes 1 perek
  of recorded learning. There is no undo."*
- A destination *ahead* is refused and pointed at `POST /advance`, so an endpoint named for
  correction never quietly records learning.
- **The ledger is written to disk before anything is deleted.** `write_safety_copy` exports the
  whole thing to `backend/data/ledger.before-correction.json` first, and a copy that cannot be
  written refuses the correction rather than being skipped past — skipping it would defeat the only
  reason to take one. Recovery is the import path that already existed:
  `uv run sidra-db import --source data/ledger.before-correction.json`. Deliberately not the
  portable `data/ledger.json`: the launcher imports that into an empty ledger, so the
  pre-correction state living there would restore the state he had just corrected away. One deep,
  which is the right depth for a gesture noticed immediately.
- `./backend/data` is now bind-mounted into the backend container. The image bakes that directory
  in, so the safety copy was landing in the container's own filesystem and would have been
  destroyed by the next `[r]` restart — found by checking `docker-compose.yml` rather than by a
  test, because no test runs in the container.
- The reachable ceiling retreats with the position, and a correction may cross a cycle turn —
  confining it would have reproduced the bug it exists to fix.

### Correcting what a track is supposed to be up to
`scheduled` is `anchor_ordinal + f(calendar)`, so a miscalibration sits in one of two operands —
and **they disagree about the past**. Run both through the day-by-day billing in `build_report`:

| route | 24 Aug | 27 Aug | opening debt Stats reports |
|---|---|---|---|
| `started_on` → 25 Aug | Jeremiah 47 · *before the origin* | Jeremiah 49 | **3** |
| target → Jeremiah 49 | Jeremiah 46 | Jeremiah 49 | **2** |

Both land on the same place today. `scheduled_series` returns a flat `anchor_ordinal` for any day
before the origin, so moving the *date* leaves the seeded opening debt of three perakim standing
while shifting the *ordinal* rewrites it to two. A lever that chose silently would have rewritten a
measured fact without anyone asking, so `PUT /api/tracks/{id}/schedule` takes `started_on` **or** a
target and never guesses. `tests/api/test_schedule_history.py` pins both rows of that table.

The Neviim case needs both: the seeder stamped `anchor_date` with its own run day and billed it as
a learning day, and Amram's reading is that Jeremiah 47 was already true *for* the 24th.

### Also in this version
- `AdvanceResult` gained `resolved_ordinal` — a replay reported `from == to == current`, which says
  nothing about where the caller aimed, so the dialog could not describe a backwards reference
  without resolving it twice. Additive; nothing that reads the model breaks.
- The track router split: reads stay in `tracks.py`, every mutation moves to `track_writes.py`.
  Same prefix, same paths, no client can tell. `one_row` moved to `api/track_rows.py`, which both
  routers already depended on, rather than being imported privately across modules.
- A malformed `occurred_on` on `POST /advance` was parsed outside the `try` and surfaced as a 500.
  It is a 422 now.
- Two dead branches removed rather than covered: the advance dialog's `first > reachable_to` guard,
  whose reason disappeared once the picker's window stopped starting past the end of a finished
  track, and an unreachable `?? ""` on the "I'm up to date" shortcut.

### On the screens
The Advance dialog's picker opens twenty units *behind* him as well as ahead, in a group labelled
so the direction is unmissable, and relabels its button to **Correct position** with the cost
spelled out above it. A reference typed by hand only reveals its direction once the server has
resolved it, so a replay that landed behind him is now an offer to correct rather than the old
"already there" shrug; a rail node behind the marker takes the same path without posting an advance
first. The Track screen gained a **Schedule** button whose dialog puts the two operands side by
side, with an **I'm up to date** shortcut that fills in his current position — that button is a
preset on the same request, not a second code path.

---

## v0.5.0 — unreleased

**P4 complete.** The Pace Explorer and Stats. The Obsidian export was built and then removed — see
below. Also in this version: the parsha calendar repairs, the annual cycle wrap, and advancing by
reference rather than by unit count.

### Removed before it shipped: the Obsidian export
Built, then taken out the same day on Amram's decision — he is moving off Obsidian and wants the
app itself. The app was designed to *replace* the hand-edited note, so writing the note back out
was circular. `sidra-db export` already writes the same ledger to `backend/data/ledger.json`, so
nothing was lost on the backup side.

The adversarial pass that ran against it was still worth having: it clobbered an unrelated file
three ways, and the lesson generalises — deriving a temp path from an already-checked target with
`with_name` proves nothing, because that is string manipulation and performs no I/O.

**The open consequence:** the app is desktop-only and localhost-only, so there is now no way to
read the sidra away from this machine. Recorded in the spec, not solved.

### Advancing by reference, not by count
Amram's words: *"i learned three halachot in mishna torah today going from 5:4 to 5:7 and then i
had to advance 3 units which is awkward when i advance from unit 286 to 289."* He knows where he
stopped. He does not know, and should never have to work out, that 5:7 is unit 289 of the corpus.

- `POST /api/tracks/{id}/advance` takes `to_ref` **or** `to_ordinal`, exactly one, enforced by a
  model validator. The ordinal form stays because the Track screen's rail already knows it.
- `resolve_position()` tries the bare address against **the work he is standing in first**, then
  every other work in the track. Without that, `"5:11"` on a Mishneh Torah track resolved against
  the corpus's first book and silently returned a replay — found by typing it, not by a test.
- `AdvanceDialog` no longer shows an ordinal anywhere. It fetches the twelve units in front of him
  from the rail and offers them by their real addresses — `5:9`, `5:10`, `5:11` with the gematria
  above each — plus a field for a reference typed by hand. The list is a convenience; the field is
  the guarantee, and it still works when the rail cannot be reached.
- `AdvanceDestination` is now a named type shared by the endpoint and the thunk, rather than a
  `toRef?`/`toOrdinal?` pair the thunk had to reassemble behind a `?? 0` that could never fire.

### The Rambam picks the masechta
Amram's Gemara does not follow Shas order. It follows his Mishneh Torah: whatever hilchos he is up
to, the Gemara is the masechta that section draws on — and **where a section has no masechta of its
own, the Gemara does not move.** He stays on Avoda Zara through Teshuvah and switches only when the
Rambam reaches Kriyas Shema and Berakhot.

The apparatus already knew this; nothing here is invented. `dominant()` calls a section's masechta
only when one holds **a quarter of its citations and leads the runner-up by half again** — measured
against all 84 hilchos books, and the ratio is what does the work:

| | | |
|---|---|---|
| Teshuvah | Yoma 19 v Sanhedrin 16 | **x1.19 — none**, exactly as he said |
| Deos | Berakhot 25 v Shabbat 21 | x1.19 — none |
| Maachalos Assuros | Chullin 318 v Avodah Zarah 288 | x1.10 — none; genuinely split, and neither owns it |
| Hilchos Avoda Zara | Avodah Zarah 200 v Sanhedrin 128 | x1.56 — **Avodah Zarah** |
| Kriyas Shema | Berakhot 106 v Shabbat 9 | x11.8 — **Berakhot** |
| Eruvin | Eruvin 303 v Shabbat 8 | x37.9 — **Eruvin** |

One correction to his sketch, which he invited: tefillin and tzitzis point at **Menachot**, not
Berakhot. That is where those sugyos are.

- `GET /api/sequence/{track_id}` — the code's order collapsed into stages, each a run of hilchos
  books sharing a masechta. A book with none joins the stage already running; a run that opens
  with none adopts the first masechta that turns up, because that is what it was waiting for.
- The map is a property of the catalog rather than the ledger, so it is built once per snapshot
  and cached. A re-seed invalidates it by key rather than by hand.
- Distances are in halachos, not dates: the code is learned with a chavrusa and a chavrusa has no
  rate, so a date would be an invented number. The screen pairs the two instead — *Gemara has 96
  amudim left and 171 halachos of runway, one amud for every 1.8 halachos.*
- Every stage carries its share, its link count and its runner-up, so a close call stays visible.
  A masechta the code returns to later — Berakhot again at Hilchos Brachos — is marked rather than
  folded away, because whether to learn it twice is his call.

### Four things found by using it
**Seder HaGet and Seder Halitzah are gone.** They are appendices to Even HaEzer — the procedural
orders for writing a get and for chalitzah — each a single undivided node rather than a siman
anybody learns one a day. They put the Shulchan Aruch at 1,707 against the measured 1,705 and
inserted two phantom units between Even HaEzer and Choshen Mishpat. Excluded in `corpora.py`
alongside the introduction. The exclusion also had to run **after** a complex node is expanded:
Even HaEzer's children only carry their own titles once it has been split, so a filter on the
parent let both straight through.

**The card name column was too narrow**, clipping "Yosef Mendelson & David Gofman — Bereishit
Rabbah". Widened from 14rem to 21rem; nothing on Today is clipped now.

**A roadmap row now names the work it is actually projecting.** "Gemara finishes 2026-11-30" was
Avoda Zara finishing, labelled Gemara — an overclaim by a factor of thirty-five. Rows read
`Gemara · Avodah Zarah`, and a track that is one work of a larger body gains the honest second
scale: *all of Talmud Bavli at this pace: 14.7 years*. Two guards decide when that applies: same
granularity, because the Torah corpus holds perakim and aliyot at once; and more than one work of
that kind, because the Chumash over Parashat HaShavua has no wider body to be part of.

**Alignment was not broken — it was mis-presented.** Ein Mishpat maps the codes to their Talmudic
sources, so only a Rambam or Shulchan Aruch track can be asked; the picker offered all twenty and
answered seventeen of them with a blank screen. It now offers only what it can answer, opens on
the first rather than on "Choose a track…", explains what the apparatus is, and says why the rest
are absent.

### A tag can finally be put on a track
Amram, trying to use it: *"how do i add a tag to a specific learning thing?"* You could not. The
Tags screen created, renamed and deleted tags and Today filtered by them, but **nothing wrote the
track↔tag link except the seeder** — the four `parsha` tags came from `tracks.yaml` and no tag made
in the app could ever be worn by anything.

- `PUT /api/tracks/{id}/tags` takes the **whole set** the track should wear rather than add/remove
  verbs, because the editor is a row of toggles: sending what it shows cannot drift from what he
  is looking at, and two quick toggles cannot interleave into a state neither meant. It answers
  with the recomputed row, so the pills cannot disagree with the ledger in between.
- The Track screen grows a Tags row: every tag there is, lit when this track wears it. Unknown tag
  ids are a 404 that changes nothing; a repeated id is a 422.
- `PUT` joins the allowed methods on both sides. The API is proxied same-origin through nginx, so
  CORS is not in the path, but the two are kept in step.

### Stats
The spec's whole specification is nine words: *"Advance heatmap, per-track pace, streaks."* The
shape those take here follows from what this app is. A habit tracker asks "did you show up?"; a
debt ledger asks whether the gap is opening or closing, so every cell carries a **signed quantity**
rather than a tick.

- `GET /api/stats?on=&window=` — read-only, stores nothing. One row per begun track, one cell per
  day, carrying `billed − learned`. Positive opened the gap, negative closed it, zero held.
- **Debt over time is not stored, and does not need to be.** Both sides of `debt = scheduled −
  actual` are closed forms of the day, so the series is reconstructed exactly: `actual(d)` is the
  greatest `to_ordinal` dated on or before `d`, and `scheduled(d)` runs through the same schedule
  functions the live ledger uses. Verified against the two headline measured facts — the
  reconstruction puts Gemara at **20 amudim** and Neviim at **3 perakim** on 2026-08-24.
- **The window is clamped to the ledger's own age and says so.** A ninety-column grid with three
  lit columns is not a report. Today it draws three columns and prints "showing 3 — the ledger is
  not older than that".
- **Standing counts tracks, never units.** Twenty-one amudim plus four perakim is not twenty-five
  of anything.
- The **seeder's opening rows are excluded**: a track sitting at its first unit has an advance row
  but has learned nothing, and counting those would have credited thirteen sessions that never
  happened.
- A streak counts today **or yesterday**, because one that resets at midnight describes the same
  ledger differently at 23:00 and at 09:00.

Four defects recorded from the rejected first design are avoided by construction rather than by
care: no status code is returned for a track that has not begun (they are simply not rows); the
window length is a `len()` behind an outer `min`, so it cannot go negative; there is no pace ratio
at all, so nothing on schedule can be labelled "slipping"; and the streak is rendered rather than
carried as dead payload.

### The parsha calendar was billing weeks that were never read
Found by the adversarial pass over the Stats design, then verified against the live database
before anything was changed. Two of the three findings are repaired here; the third is the cycle
wrap, which is a contract change and is being designed separately.

**Sefaria's calendar label was being split on its hyphen.** `Lech-Lecha` became two parshiyos, so
that week billed the Chumash fourteen aliyot instead of seven and every parsha-weekly track two
sichos instead of one. The `_KNOWN_HYPHENATED` guard written for exactly this was **dead code** —
zero references anywhere in the tree — and did not list Lech-Lecha in any case.

**Festival weeks were billing as sidros.** The calendar carries `Rosh Hashana I`, `Sukkot I`,
`Shmini Atzeret`, `Pesach Shabbat Chol haMoed` and `Shavuot II` in the Parashat Hashavua slot.
These *displace* the weekly reading rather than supplying one, and each was billing a full week.

- `ParshaIndex` resolves a calendar label against the catalog's own fifty-four parshiyos instead
  of guessing from punctuation. One parsha, two, or none — and only the index can tell the three
  apart. `Shmini Atzeret` is the sharp case: `Shmini` is a real parsha and the label must not be
  mistaken for it.
- The names and their Hebrew come from `learnable_unit`, so nothing is hand-written and no Hebrew
  is hand-encoded. `load_parsha_index` refuses a short catalog rather than resolving against a
  partial list, because a missing parsha would silently turn its week into a festival.
- `parsha_key` treats a hyphen and a space as the same separator but an apostrophe as no
  separator at all, so `Lech-Lecha` matches the catalog's `Lech Lecha` while `Ha'Azinu` and
  `Haazinu` are one name.
- Measured on the live ledger after re-crawling all 400 days: the Chumash on 2026-09-18 goes from
  scheduled 378 / debt 31 to **scheduled 371 / debt 24**, and nothing accrues across Sukkot and
  Shmini Atzeret. Today's numbers are unchanged — the first festival week is 2026-09-06.
- A live test now pins both bugs against the real API.

### Closing the cycle: the parsha the calendar never names
Zeroing the festival weeks exposed what they had been accidentally covering for. **Sefaria never
names V'Zot HaBerachah at all** — it is read on Simchat Torah, 23 Tishrei, which in the diaspora
can never fall on Shabbos, so it is never anybody's *upcoming* sidra. Only 53 of the 54 appeared
anywhere in 400 stored days, and 2026-10-04 — Simchat Torah itself — was labelled `Bereshit`.

Left alone, a cycle would bill 53 parshiyos against a modulus of 54 and the Chumash would slip a
whole parsha behind the shul every year, cumulatively and for good.

- `close_the_cycle` adds it to the week that already carries Bereshit, so that week bills both.
  That is not a workaround: it is what Simchat Torah morning *is* — the Torah finished and begun
  again — and it goes through the same combined-week path Nitzavim-Vayeilech already takes.
- Simchat Torah is found from the numbered Hebrew date (23 Tishrei, 22 in Israel), not from a
  festival title, for the same reason Yom Tov already is: a title is English and can change.
- The name and its Hebrew are the catalog's last parsha, taken because it is **last** rather than
  by its name.
- **Measured over a real crawled year (2026-10-04 → 2027-10-23): 378 aliyot, 54 distinct
  parshiyos.** That is now a live test rather than an arithmetic claim — it is the fact the annual
  wrap will rest on, and the earlier design was rejected for assuming it without measuring.

### CI covers the frontend at last
`.gitlab-ci.yml` predated the UI entirely: nothing but me running the gates by hand stood behind
any frontend change since P3. It now has `eslint`, `pnpm audit`, `vitest` publishing JUnit,
a 100% coverage gate, `pnpm build` (which runs the strict `tsc -b`, stricter than a root
`--noEmit`), and a frontend image build scanned by Trivy alongside the backend's.

Also: `ruff format --check` had drifted and would have failed the pipeline. The tree is formatted
again — 25 files, of which 8 I had not otherwise touched.

### Two things the crawl needed
- 429 joins the retryable statuses. A year of calendar is hundreds of sequential calls and both
  upstreams rate-limit a run that long; being told to slow down is not a reason to abandon a crawl.
  `Retry-After` is honoured when it is given in seconds and is sane, capped at a minute.
- Hebrew dates now come from **one** ranged Hebcal call instead of one per day, and the per-day
  Sefaria calls are throttled. Unthrottled, the crawl died at HTTP 429 partway through. Hebcal
  answers a *one-day* range with its single-date shape rather than a map, which the live tests
  caught: both shapes are accepted.

### The annual wrap
With the cycle length established, the wrap itself. A parsha track's ordinals become **cumulative
and unbounded**; only the address folds. Debt carries across the turn by construction, because
both sides of `scheduled − actual` keep counting in one coordinate system. Nothing is stored,
nothing is migrated, no column is added.

- `cycle_length` is `total` when **every** work a track runs through is named in the new
  `data/cycles.yaml` — the work repeats, not the track, so two tracks over Likutei Sichot would
  both repeat.
- A cycle track is **never finished**. That was the failure due to arrive first: at one aliyah a
  day the Chumash reaches 378 in credit, and `is_finished` would have disabled Advance and emptied
  `up_next` at exactly the moment the new cycle begins.
- **A typed reference is never lifted into the next turn.** It names a place in the turn he is
  standing in, so a correction backwards stays a replay and writes nothing. The rejected design
  lifted it, which turned "no, I stopped there" into a 375-aliyah advance with no undo. Wrapping
  forward is the picker's job, because a bare address cannot tell the two apart.
- **One ceiling**, `reachable_ceiling`, shared by the advance endpoint, the rail and the picker.
  Three that disagreed let the dropdown offer units the endpoint refused.
- `get_track` now caps its span. At `radius=0` — which the Track screen uses — the span *was* the
  debt, and an uncapped debt would walk `position_at` once per unit owed on every load.
- Verified against the live ledger across two wraps: the scheduled aliyah lands in the calendar's
  own parsha in Bereshit, Mishpatim, Bamidbar and Shoftim weeks, a year apart, with no drift. Rail
  ordinal 378 is `Deuteronomy 34:1-12` and 379 is `Genesis 1:1-2:3`.

### The picker is a dropdown, and the defect that exposed
Amram: *"what if i learn more than 8 units uknow?"* — fair. The twelve-button grid became a real
dropdown reaching **200 units**, past any sitting and inside the rail's 500-unit span.

Widening it surfaced a live defect the grid had been hiding. His Mishneh Torah track spans three
hilchos books, so the list offers `1:1` twice and `5:9` three times. Sent as a ref, every one of
them would have resolved to the first — a silently wrong advance, on an app with no undo.

- **A unit picked off the list now travels as its ordinal**, which is exact. Only what he typed
  himself travels as a ref. This is why the endpoint takes either, and the reason is now the
  dialog's own docstring rather than a note in a changelog.
- **`RailUnit` gains `work_title_en` / `work_title_he`** — additive, and taken from `Position`,
  which already carried both. Deriving the sefer by parsing it back off the front of a ref is the
  same class of mistake as synthesising a range ref, so it is not done.
- The options group under their sefer, so two `1:1`s are told apart at a glance, and a line under
  the picker spells out what is about to be recorded: `Recording Mishneh Torah, Torah Study 1:1`.
- An aliyah is named by its ref rather than its label, because "Chamishi" is every parsha's fifth.

### The Pace Explorer
- `GET /api/pace?years=&per_day=` — every row carries both answers, because they are two knobs
  rather than two modes. Read-only, and it reads no ledger: no position, no debt, and the horizon
  is a duration rather than a date, so it cannot be mistaken for the Roadmap.
- Twenty rows from `data/pace_scopes.yaml`, counted off the catalog rather than hard-coded. A row
  is a (body, unit) pair: Shas appears by amud and by daf, the Rambam by perek and by halachah.
- Seventeen of twenty reproduce the spec's table exactly. The three that do not are footnoted on
  the screen rather than fudged: Bavli daf is 2,684 that carry text against a traditional 2,711,
  and the Shulchan Aruch's 1,707 simanim / 13,567 seifim include Even HaEzer's two appendices.
- `DAYS_PER_YEAR` lifted out of the roadmap router into `constants.py`, shared by both.


## v0.4.0 — unreleased

**Editable start dates**, and the bug that asking for them uncovered. Minor bump: `TrackRow` gains
a field and the API gains a verb, both additive.

### The bug
A track's schedule counted periods from its **anchor date**, not its **start date**. Measured on
the live ledger before the fix: Likutei Sichot reported debt 0 on 9 October and **debt 7 on 10
October, its first day**. All three parsha-weekly works would have opened seven units behind on
Shabbos Bereishis. Now they open owing exactly one sicha, which is what a first day owes.

- `effective_anchor(anchor_date, starts_on)` — the later of the two, because a schedule cannot have
  run before it began. A no-op on every row this codebase writes; a seatbelt for rows that arrive
  from an older ledger export or a hand-edited `tracks.yaml`.
- `LedgerState.not_started` — the countdown state, previously built byte-identically in three
  places. The third copy, in `parsha_schedule`, was unreachable in production and is deleted.
- `seed_tracks` anchors a track that declares `starts_on` on that day, at one unit past where it
  stands: the start day is a learning day.

### Setting one from the UI
- `PATCH /api/tracks/{id}` with `starts_on`, or `null` to clear. Returns the recomputed row,
  because rebasing moves the debt and the screen should see that in the same round trip.
- Rebasing **forgives** what a track ran up while it sat unopened — the point of the feature for a
  sefer not started yet, and vandalism on one already being learned. So it is refused (422) when a
  track has been opened *and* its schedule is running. The measured 20 amudim and 3 perakim are
  unreachable from this endpoint by construction, and a test asserts the debt survives the refusal.
- The ordinal is rewritten only on the **first** declaration. A later move or a clear carries it
  forward, so a track advanced during its own countdown keeps its banked credit.
- Also refused: a chavrusa track (it carries staleness, not a schedule), a date in the past, a date
  more than two years out, and an unknown key.
- `StartDateDialog` on Today and on the Track screen, with tomorrow / a week / two weeks / a month
  presets and a "Start it now" that clears the date.
- A countdown inside its first week now reads "3 days away" rather than rounding up to "1 week
  away" — invisible while every start date was seven weeks out, wrong once a date can be picked.

### Fixed
- The roadmap projected a not-yet-started track as though it began today.
- A spec declaring both a start date and a scheduled position is now refused rather than having the
  scheduled position silently swallowed.


## v0.3.0 — unreleased

**P3 — The UI. Complete.** Minor bump: additive. Six screens over the nine P2 endpoints, plus one
new endpoint the rail needs.

### The screens
- **Today** — debt-ordered within Daily / Shabbat / Chavrusa, filterable by tag. Each row carries
  the Hebrew name, the position, a compressed two-marker rail and a debt badge that names its own
  units: `21 amudim behind`, not `21 behind`.
- **Track** — the signature. The full spine, windowed, with the lit segment ending at the actual
  position and a dashed ghost at the scheduled one. The gap between them *is* the debt.
- **Roadmap** — dated projections, sortable, with the yearly-cycle rate the Pace Explorer needs.
- **Chavrusas** — staleness-sorted, longest first, with the full session log.
- **Tags** — create, rename, delete; a delete says plainly that it removes the label, not the track.
- **Alignment** — the masechta ranking as a distribution, with inferred edges visibly distinct.

### The design language
- Dark, hairline construction; structure in `rgba(255,255,255,.07)` rules, shadows only on overlays.
- **David Libre** for Hebrew, **Spectral** for Latin, **IBM Plex Mono** with `tabular-nums` for every
  countable value. Hebrew gets its own type scale ~10% above the Latin and sets weight 500, because
  David runs optically small and its thin strokes drop out at 400.
- Hebrew is primary everywhere, the transliteration sits beneath it, and every Hebrew string renders
  inside an RTL isolate.
- One accent per fixed category; `prefers-reduced-motion` collapses all animation.

### Backend additions
- `GET /api/tracks/{id}/rail?from=&to=` — one span of a rail, capped at 500 units, clamped at the
  end. The Mishneh Torah chavrusa tracks are 15,143 halachos; no single call carries a whole spine.
- `TrackRow.unit_singular` / `unit_plural`, from the position's granularity, so a badge can say
  "amudim" rather than "units".
- `sidra-db init` — the real database had no schema; P1 only ever created tables in `sidra_test`.

### Fixed
- `unwrap()` on a thunk rejected with `rejectWithValue` throws the *payload*, not an `Error`, so an
  `instanceof Error` check silently swapped the backend's own sentence for a generic one. One
  `failureMessage` helper now handles both shapes.
- A rejected thunk whose error carried an empty message rendered an empty banner.
- RTL spans stretched across a grid column pushed their text to the far edge, which read as a gap
  rather than a label.
- The frontend image pinned `pnpm@9.15.9`: corepack otherwise pulls a version needing a newer Node
  than the base image, which fails with `No such built-in module: node:sqlite`.


## v0.2.0 — unreleased

**P2 — The Ledger. Complete.** Minor bump: additive throughout — the debt engine, the calendar,
the seeded sidra and the REST surface are all new, and no P1 contract changed shape.

### The debt engine
- `LedgerState` / `ledger_state` — `scheduled = anchor + rate x periods_elapsed`, `debt =
  scheduled - actual`. Surplus banks and displays as "N days ahead", never as a negative.
- The clock ticks every calendar day, Shabbos and Yom Tov included.
- `position_at` / `track_total` — a track ordinal resolved through the catalog, streaming across a
  whole corpus for a `CORPUS` track.

### The Hebrew calendar
- Parsha from Sefaria's `/api/calendars` (dateable); Hebrew date and Yom Tov from Hebcal, which
  publishes a real `yomtov` boolean. `@hebcal/core` is deliberately not bundled — it is GPL-2.0.
- `calendar_span` refuses a gap rather than under-accruing.
- `retrying_get` — one bounded-retry helper now shared by Sefaria and Hebcal. A year of calendar is
  ~800 sequential calls and both upstreams answer some of them with a 504.

### The calendar-driven schedules
- `parsha_aliyah_state` — one aliyah per parsha per day, so a combined week owes fourteen across
  seven days rather than halving the text.
- `parsha_weekly_state` — one unit per parsha, which is the only way 54 parshiyos fit ~50 weeks.

### The seeded sidra
- `data/tracks.yaml` — twenty tracks, six daily, nine Shabbat, five chavrusa, with positions
  written the way Amram writes them and resolved against the catalog at seed time.
- `seed_tracks` — idempotent; a scheduled ref becomes the anchor, a current ref becomes the opening
  advance, and the gap between them is the debt.
- `sidra-db calendar` and `sidra-db seed-tracks`; `sidra-db status` now reports both halves.

### The REST API
- FastAPI on 8285: `/api/today`, `/api/tracks`, `/api/tracks/{id}`, `POST .../advance`,
  `/api/roadmap`, `/api/chavrusas`, `/api/tags` CRUD, `/api/alignment/{id}`, `/health`.
- Advances are absolute, so a retried request is a no-op rather than a double count.
- Every response carries Hebrew alongside the transliteration and a Sefaria deep link where one
  exists — Likutei Sichot and The Midrash Says carry none, which is a normal state.

### Portability
- `sidra-db export` / `sidra-db import` and `data/ledger.json`. The catalog is reproducible from
  `p1.jsonl`; the ledger is not, because every advance exists nowhere else and the database lives
  in a Docker named volume that does not travel with the project folder. Ids are carried verbatim,
  so an import is a restore rather than a copy with new identities. The calendar rides along, so a
  new machine needs no network to become usable.
- The launchers now run `sidra-db init`, seed the catalog if it is empty, and import the ledger if
  one is present — so copying the folder and running the launcher is the whole move.
- `sidra-db init` — the real `sidra` database had no schema at all; P1 only ever created tables in
  `sidra_test`, which no one noticed because the snapshot was never written.
- **`backend/data/snapshots/p1.jsonl` written**: 279 works, 27,252 units, 121,289 links, 19 MB.
  `sidra-db seed` now rebuilds the whole catalog offline in seconds and `verify` passes.

### Fixed
- A `PARSHA_ALIYAH` track indexed all 432 rows of Parashat HaShavua, so it landed on a parsha row
  every eighth day. It now indexes the 378 aliyot.
- A track naming a complex work found nothing: there is no `Tanya` in the catalog, only its five
  chalakim. Naming the parent now takes its parts in order.
- The Shulchan Aruch corpus was in Sefaria's alphabetical order, which opened a one-siman-a-day
  cycle at Choshen Mishpat 1 instead of Orach Chaim 1. Added `shulchan_aruch_order.yaml`.
- The coverage gate was measuring less than it reported: `coverage` loses its tracer across
  SQLAlchemy's greenlet switches. `concurrency = ["thread", "greenlet"]` restored it, and the gaps
  it had been hiding are now covered.


## v0.1.0 — unreleased

**P1 — Catalog & Alignment. Complete.**

### P1a — Foundation
- Project scaffold: uv, ruff, pytest, pydantic-settings; Docker Compose with PostgreSQL 16 on host
  5524; launchers with the full `[r]/[k]/[q]/[v]` loop.
- `Granularity`, `AddressScheme`, the canonical `corpus_id` vocabulary, `to_ref`.
- `amud_index_to_label` / `amud_label_to_index` / `real_amudim` — daf arithmetic including the
  Tamid (starts 25b) and Nazir (mid-masechta gap at 33b) traps.
- `to_gematria` — Hebrew numerals following Sefaria's convention, with the 15/16 exceptions.
- **`unit_at`** — resolves a unit from a work's shape array, replacing ~27,000 stored rows.
- Five SQLAlchemy models storing works and shapes rather than units.
- `SefariaClient` with HTTP-200-with-error-body detection, bounded retry on gateway failures, and
  shape parsing that handles `int | list[int] | list[dict] | list[list[int]]`.

### P1b — Ingestion
- One generic ingester covering eleven corpora, driven by a spec table.
- `parse_parasha_nodes` and `ingest_parshiyos` — 54 parshiyos and 378 aliyot as stored rows,
  carrying Sefaria's own range expansions.
- `ingest_named_work` — Orchot Tzadikim's 28 gate names from the index alt-struct.
- `build_parsha_work_drafts` — Likutei Sichot, The Midrash Says and Covenant and Conversation on
  the shared 54-parsha spine.
- Title aliases from `schema.titles` plus Amram's own spellings, with prefix resolution for works
  that exist only as their parts.
- `corpus_ordinal`, `persist_works`, `persist_units`.

### P1c — Alignment & Seed
- Ein Mishpat extractor: 17 shards streamed and filtered, 118,805 edges in about 50 seconds,
  nothing buffered.
- `rank_masechtos` and `bridge_via_tur`; direct and inferred edges kept distinct end to end.
- `crawl_catalog` — the orchestrator composing every ingester under one snapshot.
- Deterministic JSONL snapshot; `seed_from_snapshot`, idempotent.
- `sidra-db` CLI: `seed` / `refresh` / `verify` / `status`, with launcher auto-seed that never
  refreshes.
- `test_reference_values.py` — the P1 acceptance gate, asserting Amram's real positions against a
  live crawl and a real Postgres.
- GitLab CI: lint → sast → test → coverage → build → docker-build, with JUnit reporting.

### Measured catalog

| Corpus | Works | Units |
|---|---:|---:|
| Torah (5 chumashim + parsha cycle) | 6 | 619 |
| Neviim | 21 | 380 |
| Ketuvim | 13 | 362 |
| Mishnah | 63 | 525 |
| Talmud Bavli | 37 | 5,349 |
| Mishneh Torah | 84 | 15,143 |
| Shulchan Aruch | 6 | 1,707 |
| Mussar | 34 | 572 |
| Chassidus | 11 | 1,396 |
| Midrash | 1 | 1,037 |
| Parsha-weekly | 3 | 162 |
| **Total** | **279** | **27,252** |

Plus 432 stored units, 4,235 aliases, 118,805 direct Ein Mishpat edges and 2,484 inferred
Tur-bridge edges. A full crawl takes 94 seconds.
