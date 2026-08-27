# CLAUDE.md — Torah Learning Sidra

> **MANDATORY WORKFLOW: READ THIS ENTIRE FILE BEFORE EVERY CHANGE.** Every time. No skimming, no assuming prior-session context carries over — it does not.
>
> **Why:** This project spans multiple sessions and months of development. Skipping the re-read produces decisions that contradict the architecture, duplicate existing patterns, break data contracts, or introduce tech debt that compounds.
>
> **The workflow, every time:**
> 1. Read this entire file in full.
> 2. Read the master plan — `docs/superpowers/specs/2026-08-24-torah-sidra-design.md`.
> 3. Read `docs/status.md` — current state, what was just built.
> 4. Read `docs/versions.md` — recent version history.
> 5. Read the source files you plan to modify — understand existing patterns first.
> 6. Then implement, following the rules and contracts defined here.

---

<critical_context>

## 0. Critical context

**This app is a debt ledger, not a checklist.** Every daily track has a fixed rate of one unit per day. The *schedule* advances on the calendar whether or not learning happened; the *actual* position advances only when it did. The gap between them is a debt measured in units, paid down by doubling up.

```
scheduled = anchor_ordinal + rate × periods_elapsed(anchor_date → today)
debt      = scheduled − actual        negative debt = credit, and it banks
```

**Units are derived, not stored.** A `Work` carries Sefaria's own shape array and an `AddressScheme`; `unit_at(ref_title, scheme, shape, seq)` computes the address, labels and ref on demand. This replaces ~25,000 database rows with one function. Only ~460 units are stored — aliyot, parshiyos and named gates, which carry data that cannot be derived.

**Phase: complete.** P1 (catalog and alignment), P2 (ledger and API), P3 (the UI) and P4 (the Pace
Explorer, Stats, and the JSON export) all shipped, and so did the two things added after: correcting
a position or a schedule backwards, and the Maintenance screen that put six of the nine `sidra-db`
verbs behind buttons. There is no Obsidian integration: it was built on 2026-08-25 and removed the
same day. The frontend lives in `frontend/` — React 18, TypeScript strict, Vite, Redux Toolkit,
Vitest, on port 5285.

**What "complete" rests on**, measured 2026-08-27: 950 offline backend tests and 416 frontend tests,
both at 100% coverage, and **all 78 live tests green against the real Sefaria and Hebcal APIs**. The
live suite is the acceptance gate; a change that cannot keep it green is not finished.

</critical_context>

---

<domain_facts>

## 1. Measured facts — never substitute recalled values

Every number here was measured against the live Sefaria API on 2026-08-24. They are test fixtures. If one appears wrong, **re-measure against the API** — do not adjust the constant to make a test pass.

| Fact | Value |
|---|---|
| Avodah Zarah | 152 shape slots, indices 0–1 empty → **150 real amudim**, 2a…76b |
| `amud_label_to_index` | `"28b"` → **55**, `"38b"` → **75** (these are **shape indices**) |
| `unit_at` seq | 28b is **seq 54**, 38b is **seq 74** — difference **20**, the real Gemara debt |
| **Tamid** | length 66, first non-empty index **49** = `25b`, last 65 = `33b`, **17** real amudim |
| **Nazir** | length 132, empty indices **[0, 1, 65]**; index 65 = `33b` is a **mid-masechta gap**; 129 real |
| Bavli | 37 masechtos, 5,471 slots, **5,349 real amudim** |
| The Nazir trap | 5,471 − 121 leading zeros = 5,350 ≠ 5,349. **Count non-empty slots.** |
| Jeremiah | 52 perakim; 44 → 47 = **3**, the other real debt |
| Mishneh Torah, Human Dispositions | `[7,7,3,23,13,10,8]` — 7 perakim, 71 halachos; `5:8` is seq **48** |
| Neviim / Ketuvim / Mishnah | 380 / 362 / 525 perakim |
| Seder Zeraim | **75** perakim, so Mishnah Shabbat 1:1 is corpus ordinal **76** |
| Mishneh Torah | 90 shape nodes; **84 hilchos books, 1,006 perakim, 15,143 halachos**. The other 6 are front matter, Kuntres Zikah and Steinsaltz. |
| Shulchan Aruch | **1,705** simanim (OC 697 · YD 403 · EH 178 · CM 427), 13,409 seifim. Seder HaGet and Seder Halitzah are appendices, not simanim, and are excluded. **Re-measured 2026-08-27: Sefaria no longer serves them as child works at all**, so the crawl yields the four chalakim and the exclusion is now upstream as well as ours. Two live tests encoded the old six-work, 1,707-siman shape and were corrected to the measured values |
| Ein Mishpat | **118,805** edges across **17** CSV shards |
| A calendar week | one parsha, two, or **none**. `Lech-Lecha` is one; `Nitzavim-Vayeilech` is two; `Rosh Hashana I`, `Sukkot I`, `Shmini Atzeret`, `Pesach Shabbat Chol haMoed`, `Shavuot II` are none — they displace the sidra rather than supplying one |
| One whole cycle | **378 aliyot across all 54 parshiyos**, measured over a real crawled year (2026-10-04 → 2027-10-23). The wrap depends on this; it is a live test, not arithmetic |
| V'Zot HaBerachah | **Sefaria never names it.** It is read on Simchat Torah, 23 Tishrei, never a Shabbos in the diaspora, so it is never an *upcoming* sidra. `close_the_cycle` adds it to the week that already carries Bereshit — which is what that morning is. Without it a cycle bills 53 |
| Resolving a week | against the catalog's own 54 parshiyos (`ParshaIndex`), **never** by splitting on the hyphen. Splitting billed Lech-Lecha twice and every festival week once |
| Catalog totals | **277** works, **27,250** derivable units, **432** stored units, **4,167** aliases. Re-measured against the seeded database on 2026-08-27; the earlier 279 / 27,252 counted Even HaEzer's two appendix works, which Sefaria has since dropped. `expected_counts.json` gates on these numbers and `POST /api/maintenance/verify` reports them matching |
| Full crawl | **94 seconds** |

**`seq` is not the shape index.** `seq` counts real units from 1; the index counts array slots from 0 including empty ones. For Avodah Zarah they differ by one; for Tamid by 49; **for Nazir the offset changes mid-masechta.** Always go through `real_amudim`, never arithmetic on the index.

</domain_facts>

---

<tech_stack>

## 2. Tech stack — non-negotiable

Python 3.13+ · FastAPI (P2) · Pydantic v2 · SQLAlchemy 2.0 async + asyncpg · PostgreSQL 16 · uv · ruff · pytest + pytest-asyncio + pytest-cov · httpx · Docker Compose. Frontend (P3): React 18 + TypeScript strict + Vite + pnpm + Redux Toolkit + Vitest.

**No Redis.** Nothing in this design caches or uses pub/sub.

**Ports** (from `C:/Users/Amram/IMPORTANT/Projects/PORT_ASSIGNMENTS.md`): frontend **5285**, backend **8285**, Postgres host **5524** → container 5432. **Never bind host 5432** — that is the machine's single shared PostgreSQL listener.

</tech_stack>

---

<coding_standards>

## 3. Coding standards

- `from __future__ import annotations` at the top of every module.
- Full type annotations. **No `Any` in signatures.** No bare `except`.
- **One concept per file.** No `utils.py` grab-bags.
- ruff `line-length = 120`, `select = ["E","F","I","N","UP","ANN","S"]`; tests ignore `S101`.
- **Coverage is gated at 100% by a dedicated command, never by `addopts`.** Putting `--cov-fail-under` in `addopts` makes every focused single-file run fail on the untouched rest of the package.
- **No mocking of the database.** Integration tests use the real compose Postgres via the `db_session` fixture.
- **No test touches the network** except tests marked `live`, which are excluded from CI.
- Search before writing. Grep for an existing function before adding one.

</coding_standards>

---

<data_contracts>

## 4. Data contracts

**`addr` and `addr_types` are strings**, never ints and never `Granularity` members. Sefaria is polymorphic here — `["38b"]` for Talmud, `[1, 1]` for Mishnah — and strings round-trip both.

**`addr_types` uses Sefaria's own vocabulary** — `"Perek"`, `"Talmud"`, `"Halakhah"`, `"Integer"`, `"Aliyah"`, `"Mishnah"`. `Granularity` says what a unit *is*; `addr_types` says how Sefaria *addresses* it. **Conflating them is the single most common drift in this codebase's history.**

**A hilchos section's masechta is decided by dominance, never by rank alone.** `dominant()` requires a quarter of the citations *and* a 1.5x lead over the runner-up. Teshuvah leads with Yoma at 1.19x and Deos with Berakhot at 1.19x — neither is a masechta *about* that subject, and Amram's rule is that such a section leaves the Gemara where it is. Measured across all 84 books; the constants live in `sequence/dominance.py`.

**Never parse a ref backwards.** A ref's sefer is not recoverable by stripping its address off the front — an aliyah's ref is `Deuteronomy 27:11-28:6` while its label is `Chamishi`. `Position` carries `work_ref_title` and `work_title_he`; `RailUnit` surfaces both as `work_title_en` / `work_title_he`. Use them.

**An address alone does not identify a unit.** A track spanning books repeats its addresses in each of them: the Mishneh Torah chavrusa track offers `1:1` in three different hilchos. Anything the UI *offers* is sent as `to_ordinal`; only what Amram *types* is sent as `to_ref`, and that resolves against the work he is standing in first.

**A cycle track's ordinals are cumulative.** The Chumash and the three parsha-weekly works repeat annually (`data/cycles.yaml`). `scheduled` and `actual` count upward forever and only the *address* folds — `fold(n, L)` — which is what carries the debt across Simchat Torah instead of freezing it. Such a track is never `is_finished`. `reachable_ceiling` is the single bound for the advance endpoint, the rail and the picker.

**A typed reference is never lifted into the next cycle.** It names a place in the turn he is standing in (`align_to`), so a correction backwards resolves behind him. Lifting it would turn "no, I stopped there" into a year of learning that never happened. Wrapping forward is the picker's job. Both endpoints resolve through `align_to` and then read the direction themselves: `POST /advance` replays a backwards ref, `PUT /position` corrects to it.

**Three CLI verbs stay in the CLI, and that is a decision rather than an omission.** `init` the
launcher runs on boot; `seed-tracks` (`seed_tracks.py:73`) and `import` (`transfer.py:126`) both
call `clear_ledger`, and neither belongs behind a button in the app where he taps *Advance* every
morning. The one narrow exception is `POST /api/maintenance/restore`, which takes no path: it reads
`SAFETY_COPY_PATH` and nothing else, because it exists to undo a backwards correction and for no
other reason. Everything else — `status`, `verify`, `export`, `seed`, `calendar`, `refresh` — is a
button on the Maintenance screen.

**The job system is one mutable slot on `app.state`, and it is that small because every job is
atomic.** `seed` runs in one transaction, `calendar` fetches then stores in one, and `refresh`
writes its snapshot only after the crawl returns — so a job that dies with the container leaves
nothing half-finished. There is nothing to resume and nothing to clean up, which leaves progress as
the only thing the apparatus must provide. Hence no table, no ids, no history: one job at a time,
a second start is a 409, and a restart loses the job and says so.

**A correction writes the ledger to disk before it deletes anything.** `PUT /position` is the only
gesture in the app that destroys recorded learning, so `write_safety_copy` exports the whole ledger
to `backend/data/ledger.before-correction.json` first, and a copy that cannot be written **refuses
the correction** rather than being skipped past. Recover with
`uv run sidra-db import --source data/ledger.before-correction.json`. It is deliberately **not**
`data/ledger.json` — the launcher imports that into an empty ledger, so the pre-correction state
living there would restore exactly what he had just corrected away. One deep: a second correction
overwrites the first.

**Going backwards truncates; it never posts a negative advance.** `actual_ordinal` stays `MAX(Advance.to_ordinal)` (`ledger/seed_tracks.py`), so Stats, the streak, the pace projection, the rail and both ceilings never learn about backwards motion. `PUT /api/tracks/{id}/position` deletes every row past the chosen point and trims the row that straddles it, writing a synthetic opening row in the seeder's own idiom when the target falls below the earliest row. `confirm` is required — it deletes recorded learning, and there is still no undo of an undo.

**The schedule has two operands and they disagree about the past.** `scheduled` is `anchor_ordinal + f(calendar)`. Moving `anchor_date` leaves every earlier day reading a flat `anchor_ordinal` (`stats/scheduled_series.py`), so the opening debt the ledger was seeded with survives; shifting `anchor_ordinal` restates it. `PUT /api/tracks/{id}/schedule` therefore takes `started_on` **or** a target, never guessing which was wrong — choosing silently would rewrite a measured fact. Pinned by `tests/api/test_schedule_history.py`.

**Never synthesize a range ref.** Sefaria's range-tail compression (`Deuteronomy 26:16-26:19` → `26:16-19`) is undocumented and not reversibly derivable. Store the pointer form and cache Sefaria's own expansion in `resolved_ref`.

**Never send an unqualified title to Sefaria.** `Avoda Zara 38b` resolves to Bavli but `Avoda Zara 5.2` resolves to *Mishnah*. Always use the catalog's canonical `ref_title`.

**Sefaria returns HTTP 200 with an `{"error": …}` body.** Status codes lie. Every response is checked for the `error` key.

**Alt-struct titles come from `/api/index/` key `alts`.** `/api/v2/raw/index/` key `alt_structs` returns `title=None`. There is no fallback path.

**Canonical `corpus_id` vocabulary:** `torah` `neviim` `ketuvim` `mishnah` `bavli` `mishneh_torah` `shulchan_aruch` `mussar` `chassidus` `midrash` `parsha_weekly`.

</data_contracts>

---

<hebrew>

## 5. Hebrew handling — non-negotiable

**Hebrew is never hand-encoded.** `title_he` comes verbatim from Sefaria's `heTitle`/`heRef` as UTF-8; computed labels come from `to_gematria`. **No numeric character references anywhere in the pipeline.**

Every Hebrew label must contain only U+0590–U+05FF plus a known separator set, asserted by a test over the whole catalog.

**Why this rule exists:** hand-written entities once put a Cyrillic Che (U+04B4) where gershayim belonged and an Arabic alef (U+0673) where geresh belonged, corrupting four of five Hebrew strings while looking correct in a diff.

**Gematria exceptions:** 15 is `ט״ו` and 16 is `ט״ז`, not the arithmetic `י״ה`/`י״ו`, to avoid spelling a Divine name.

</hebrew>

---

<containerization>

## 6. Containerization

`docker-compose.yml` at the project root — compose v2, **no top-level `version:` key**. `postgres:16-alpine` with a `pg_isready` healthcheck, `restart: unless-stopped`, `${VAR:-default}` for every port and credential, named volume `sidra_postgres_data`.

**`./backend/data` is bind-mounted into the backend.** The image bakes the directory in (`COPY data ./data`), which is enough for everything the app *reads* — but a correction *writes* the safety copy there at runtime, and without the mount it would land in the container's own filesystem and die on the next `[r]` restart, which is the one moment it is needed.

`backend/docker/init-test-db.sh` creates `sidra_test` alongside `sidra` at first boot. **It must have LF line endings** — a CRLF shell script fails inside the Linux container.

`backend/Dockerfile` uses `python:3.13-slim`, **not alpine** — musl breaks many scientific Python wheels. It has **no `readme` key in pyproject** because the build context is `./backend` and `../README.md` would be unreachable.

Launchers `run_torah_sidra.{sh,bat}` implement `[r]` restart (unlimited), `[k]` stop, `[q]` stop + remove images, `[v]` full cleanup. **Unrecognised input reprints the menu and never exits.**

</containerization>

---

<git_policy>

## 7. Git

**Amram manages git himself.** Never run `git add`, `git commit`, `git checkout`, `git merge`, `git rebase`, `git push`, `git pull`, `git stash`, `git reset`, `git restore`, `git tag`, or any other state-changing git command. Read-only git (`status`, `diff`, `log`, `show`, `blame`) is fine.

When a task is done, report the files changed and a **suggested** commit message. That is all.

</git_policy>

---

<security>

## 8. Security

| Boundary | Injection classes | Defence |
|---|---|---|
| Sefaria / Hebcal responses | deserialization, SSRF | Pydantic validation on every decoded payload; host allowlist; no input-derived URLs |
| Advance notes, tag names (P2) | XSS | React escaping; no `dangerouslySetInnerHTML` |
| Ref strings from the catalog | SQL | SQLAlchemy bound parameters only; no string-built SQL |
| Snapshot import (P1c) | deserialization | strict model, size cap, no pickle |
| Ledger import — `data/ledger.json` (P2) | deserialization | strict Pydantic `extra="forbid"`, 32 MB size cap checked before the read, references validated before any write, no pickle |
| `PUT /tracks/{id}/position` body | deserialization, SQL | Pydantic `extra="forbid"`, `to_ref` bounded at 256 chars, `to_ordinal` `ge=0`, exactly-one-of validator; SQLAlchemy bound parameters on the delete and the update, no string-built SQL in `truncate_to` |
| `POST /maintenance/restore` body | deserialization | Pydantic `extra="forbid"`, and **no path field** — it reads `SAFETY_COPY_PATH` alone, so it cannot be talked into replacing the ledger from anywhere else; a typed `RESTORE` is required by a field validator |
| `POST /maintenance/calendar` body | resource exhaustion | `days` bounded 1..800, `CRAWL_PAUSE_SECONDS` throttles the per-day calls Sefaria rate-limits |
| `PUT /tracks/{id}/schedule` body | deserialization | Pydantic `extra="forbid"`, `to_ref` bounded at 256 chars, `to_ordinal` `ge=1`, exactly-one-of-three validator; the anchor is arithmetic on ints, never on input strings |

SAST: Semgrep (`semgrep scan`, **not** `semgrep ci`), `pip-audit`, gitleaks in a `sast` stage; Trivy in `docker-build`. Fails on HIGH.

</security>

---

<completion>

## 9. Task completion self-audit

1. **Summary** — what changed and why, in two sentences.
2. **Reuse check** — name the files you grepped before writing anything new.
3. **Tech-debt check** — no `Any`, no dead code, no commented-out blocks, no `TODO` without a linked task.
4. **File-organization check** — one concept per file.
5. **Data-contract check** — no contract changed without approval.
6. **Docs check** — `docs/status.md` and `docs/versions.md` updated; `PORT_ASSIGNMENTS.md` if a port changed.
7. **Test check** — tests added; coverage still 100%.
8. **Measured-facts check** — if any fact in §1 was contradicted, say so and re-measure. Never adjust a constant to make a test pass.
9. **Git state** — files changed and a *suggested* commit message. You do not commit.
10. **Security check** — SAST clean; injection classes named for any new boundary.

</completion>

---

<closing>

## 10. Closing reminder

Re-read this file before the next change. **Maximal clarity. Minimal tech debt. Optimal alignment.**

</closing>
