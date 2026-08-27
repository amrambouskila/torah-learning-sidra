# Torah Learning Sidra — P1c (Alignment & Seed) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Ein Mishpat topic map, make the whole catalog reproducible offline from a committed snapshot, and close P1 with an acceptance suite that asserts Amram's real positions.

**Architecture:** Ein Mishpat Ner Mitzvah — the classical marginal apparatus mapping every halachic sugya to Rambam, Semag, Tur and Shulchan Aruch — is digitised by Sefaria as a link type. It is extracted by **streaming and filtering 17 bulk CSV shards**, never by crawling 2,711 dapim. Everything then serialises to a committed snapshot so a fresh machine rebuilds the catalog offline and deterministically.

**Tech Stack:** As P1a and P1b. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-24-torah-sidra-design.md` — §7.7 (the extract), §8 (alignment and its limits).

**Prerequisite:** **P1a and P1b complete and green.** This plan consumes `Work`, `TopicLink`, `Snapshot`, `unit_at`, `SefariaClient`, `WorkDraft`, `persist_works` and `persist_units` exactly as they are defined there.

**Scope:** Five tasks. Ends with P1 done: a seeded catalog, 118,805 topic edges, a working `sidra_db` CLI, and a green acceptance gate.

---

## Global Constraints

Identical to P1a and P1b. The ones that bite here:

- **Never buffer the bulk export.** The 17 shards total ~656 MB; stream and filter, keeping only matches.
- **No mocking of the database.** Real compose Postgres.
- **Network only in `live`-marked tests.** Extraction tests use inline CSV fixtures.
- **Git is Amram's.** Commit points only, never a git command.

---

## Measured Facts — the acceptance targets

Measured on 2026-08-24 by downloading and filtering the real export.

| Fact | Value |
|---|---|
| Shards | **17** — `links0.csv` … `links16.csv`; `links17` is 404 |
| Total size / rows | ~656 MB · **5,041,682** rows |
| **Column header** | **`Conection Type`** — Sefaria's own typo, **one `n`**. `Connection Type` matches nothing. |
| Columns | `Citation 1`, `Citation 2`, `Conection Type`, `Text 1`, `Text 2`, `Category 1`, `Category 2` |
| Filter value | `ein mishpat / ner mitsvah` |
| **Ein Mishpat edges** | **118,805** |
| Extraction time | ~49 seconds |
| **Shard 8** | contains **zero** matching rows — normal, not an error |
| Row order | alphabetical by `Citation 1`, so one masechta's edges may **straddle shards** |
| Edge directions | Talmud→Halakhah 59,400 · Halakhah→Halakhah 42,584 · Halakhah→Talmud 16,821 |

**Hilchos Avoda Zara ranking** — `"Mishneh Torah, Foreign Worship and Customs of the Nations"`, 471 links across 29 masechtos:

| Masechta | Links | Share |
|---|---:|---:|
| Avodah Zarah | 200 | 42.5% |
| Sanhedrin | 128 | 27.2% |
| Makkot | 18 | 3.8% |
| Chullin | 14 | 3.0% |
| Kiddushin | 14 | 3.0% |

**Known-good round trips:**

```
Avodah Zarah 38b:4      -> Mishneh Torah, Forbidden Foods 17:13
                        -> Sefer Mitzvot Gadol, Negative Commandments 148
                        -> Tur, Yoreh De'ah 112
                        -> Shulchan Arukh, Yoreh De'ah 112:9
Mishneh Torah, Human Dispositions 5:8  <->  Shulchan Arukh, Orach Chayim 2:6
```

---

# Task 1: The Ein Mishpat extractor

**Delivers:** 118,805 edges out of 656 MB, without ever holding a shard in memory.

**Files:** `backend/src/sidra/alignment/{__init__,ein_mishpat}.py` · `backend/tests/alignment/test_ein_mishpat.py`

**Produces:**

```python
EIN_MISHPAT_TYPE = "ein mishpat / ner mitsvah"
LINKS_URL_TEMPLATE = "https://storage.googleapis.com/sefaria-export/links/links{shard}.csv"
SHARD_COUNT = 17
CONNECTION_TYPE_COLUMN = "Conection Type"   # Sefaria's typo. One 'n'. Load-bearing.


class EinMishpatEdge(NamedTuple):
    citation_1: str
    citation_2: str
    category_1: str
    category_2: str


def iter_ein_mishpat(shard: int, client: httpx.Client) -> Iterator[EinMishpatEdge]: ...
def iter_all_ein_mishpat(client: httpx.Client) -> Iterator[EinMishpatEdge]: ...
```

**Implementation shape:** open the shard with `client.stream("GET", url)`, wrap `response.iter_bytes()` in something file-like, hand that to `io.TextIOWrapper(..., encoding="utf-8")`, and feed it to `csv.DictReader`. Yield only rows whose `CONNECTION_TYPE_COLUMN` equals `EIN_MISHPAT_TYPE`. **Nothing accumulates.**

- [ ] **Step 1: TDD against an inline CSV fixture**

The fixture carries the **exact real header row** and a handful of real rows, including the Avodah Zarah 38b:4 quadruple:

```csv
Citation 1,Citation 2,Conection Type,Text 1,Text 2,Category 1,Category 2
"Avodah Zarah 38b:4","Mishneh Torah, Forbidden Foods 17:13",ein mishpat / ner mitsvah,"Avodah Zarah","Mishneh Torah, Forbidden Foods",Talmud,Halakhah
"Avodah Zarah 38b:4","Shulchan Arukh, Yoreh De'ah 112:9",ein mishpat / ner mitsvah,"Avodah Zarah","Shulchan Arukh, Yoreh De'ah",Talmud,Halakhah
"Avodah Zarah 38b:4","Tur, Yoreh De'ah 112",ein mishpat / ner mitsvah,"Avodah Zarah","Tur, Yoreh De'ah",Talmud,Halakhah
"A Dictionary of the Talmud, אֱגוֹד 1","Mishnah Peah 6:6",quotation,"A Dictionary of the Talmud","Mishnah Peah",Reference,Mishnah
"Berakhot 2a:1","Genesis 1:1",,"Berakhot","Genesis",Talmud,Tanakh
```

Tests:

- Only the three Ein Mishpat rows are yielded; the `quotation` row and the empty-type row are not.
- The Avodah Zarah quadruple comes back with `category_1 == "Talmud"` and `category_2 == "Halakhah"`.
- **The typo is load-bearing** — a fixture whose header says `Connection Type` (two `n`s) yields **zero** edges. Write this test explicitly; it is the single most likely way this module silently returns nothing.
- **An empty shard is normal** — a shard whose rows contain no Ein Mishpat yields an empty iterator and does **not** raise. Name the test for shard 8.
- **`shard` is range-checked** — `iter_ein_mishpat(17, client)` raises `ValueError` naming the valid range, since `links17.csv` is a 404.
- **A real HTTP error propagates** — an in-range shard that 404s raises `httpx.HTTPStatusError`. Use an in-range shard so the range guard does not fire first.
- **Nothing accumulates** — consume `iter_all_ein_mishpat` over a fixture spanning several shards and assert it is a generator (`inspect.isgenerator`), so a future refactor to a list fails the test rather than the memory budget.

- [ ] **Step 2: The `live` extraction**

`@pytest.mark.live` — stream all 17 shards from the real bucket and assert **118,805** edges, that shard 8 yields zero, and that the three edge-direction counts match (59,400 / 42,584 / 16,821).

This takes about 50 seconds and moves ~656 MB. Run deliberately; never in CI.

**Accept:** `uv run pytest tests/alignment/test_ein_mishpat.py -q` green; `-m live` green.

- [ ] **Commit point** — `ein_mishpat.py` and its tests.
  Suggested message: `feat(alignment): stream Ein Mishpat edges from the bulk export`

---

# Task 2: Ranking and the Tur bridge

**Delivers:** the aggregate that drives Amram's Gemara queue, and the fallback for Shulchan Aruch's thinner coverage.

**Files:** `backend/src/sidra/alignment/{aggregate,tur_bridge}.py` · `backend/src/sidra/db/persist_links.py` · tests mirroring each

**Produces:**

```python
class MasechtaRank(NamedTuple):
    masechta: str
    links: int
    share: float


def rank_masechtos(edges: Iterable[EinMishpatEdge], hilchos_ref_title: str) -> list[MasechtaRank]: ...
def bridge_via_tur(edges: Iterable[EinMishpatEdge]) -> list[EinMishpatEdge]: ...
async def persist_links(session, edges, snapshot_id, *, kind, confidence) -> int: ...
```

`rank_masechtos` walks edges in **both directions** — Ein Mishpat rows appear as Talmud→Halakhah and Halakhah→Talmud — strips the address off each Talmud citation to get the masechta, counts, and sorts by `(-links, masechta)`.

- [ ] **Step 1: TDD `rank_masechtos`**

Build the fixture from the **measured 29-masechta distribution** and assert its own total is 471 before using it — a fixture that does not sum to the measured total is the bug, and an earlier draft shipped one summing to 469.

Tests:

- The ranking reproduces the measured order: **Avodah Zarah, Sanhedrin, Makkot, Chullin, Kiddushin**. Note Makkot (18) outranks Chullin and Kiddushin (14 each), so a naive alphabetical tiebreak on equal counts must not reorder the top five.
- Shares are 42.5% and 27.2% within ±0.05.
- Totals: 471 links across 29 masechtos.
- Edges are counted in **both directions** — an edge recorded Halakhah→Talmud contributes identically to one recorded Talmud→Halakhah.
- A hilchos with no edges returns `[]` rather than raising.
- Equal counts break ties by masechta name, deterministically.

- [ ] **Step 2: TDD `bridge_via_tur`**

Where a Bavli→Shulchan Aruch edge is missing but a Bavli→Tur edge exists **on the same anchor**, emit a provisional SA edge at siman granularity. Sampling found **104 matched / 0 unmatched**: Shulchan Aruch follows Tur's siman numbering.

Tests: an anchor with a Tur edge and no SA edge yields one bridged edge at the same chelek and siman with no seif; an anchor that already has an SA edge yields **nothing** (never duplicate a direct edge); an anchor with neither yields nothing; bridged edges are distinguishable from direct ones by their `kind`.

- [ ] **Step 3: TDD `persist_links`**

Integration: 118,805-scale insertion uses a bulk path, not one `session.add` per row — time a 10,000-edge insert and assert it completes inside a generous bound so a per-row regression is caught. `kind="ein_mishpat"` rows get `confidence="direct"`; `kind="tur_bridge"` rows get `confidence="inferred"`. `anchor_group` is the shared `citation_1`. Re-running does not duplicate.

- [ ] **Step 4: Record the honest limits in code**

Write `tests/alignment/test_coverage_limits.py` asserting the two measured asymmetries, so nobody later "fixes" them:

- **Rambam coverage is far broader than Shulchan Aruch's.** For Horayos, 297 Ein Mishpat links resolve to 112 Mishneh Torah targets against 17 across all of SA. Structural, not a defect.
- **Zero-coverage dapim are real.** Sukkah 28a has 474 total links and **zero** Ein Mishpat — aggadic stretches have none. Not a masechta property: Niddah 31a is 0 while Niddah 66a is 38.

The consequence for P3: "no Shulchan Aruch parallel recorded" renders as an ordinary state, never an error.

**Accept:** `uv run pytest tests/alignment -q` and `tests/db/test_persist_links.py` green.

- [ ] **Commit point** — the three source files and their tests.
  Suggested message: `feat(alignment): masechta ranking, Tur bridge and bulk link persistence`

---

# Task 3: The crawl orchestrator and the snapshot

**Delivers:** the one function that runs every ingester under a single `Snapshot`, and the committed file that makes it reproducible offline.

**Files:** `backend/src/sidra/catalog/crawl.py` · `backend/src/sidra/catalog/snapshot.py` · tests mirroring each

**Produces:**

```python
async def crawl_catalog(session: AsyncSession, client: SefariaClient, http: httpx.Client) -> Snapshot: ...
@dataclass(frozen=True, slots=True)
class SnapshotPayload:
    format_version: int
    created_at: datetime          # parsed back to tz-aware; a str reaching timestamptz is rejected
    sefaria_version: str
    works: tuple[WorkDraft, ...]
    units: tuple[StoredUnitRow, ...]
    links: tuple[EinMishpatEdge, ...]


def write_snapshot(path: Path, payload: SnapshotPayload) -> None: ...
def read_snapshot(path: Path) -> SnapshotPayload: ...
```

`StoredUnitRow` is the row shape `persist_units` already consumes in P1b Task 2 — reuse it; do not
declare a second one.

**`crawl_catalog` is the piece an earlier draft omitted entirely** — nine ingesters existed and nothing called them, so the CLI had nothing to snapshot and the acceptance suite nothing to seed from. It runs, in order: the seven generic corpora (P1b Task 1), parsha and aliyot (P1b Task 2), named-label works, parsha-weekly works, aliases (P1b Task 3), then the Ein Mishpat extract and the Tur bridge (Tasks 1–2 here). It creates exactly one `Snapshot`, sets `unit_count` and `edge_count` on it, and returns it.

**Snapshot format is JSONL** — one record per line, streamable, diffable, and it does not require holding 118,805 edges in one JSON array to write or read.

- [ ] **Step 1: TDD `crawl_catalog` with fake ingesters**

Tests: exactly one `Snapshot` row is created; `unit_count` equals the sum of every work's `unit_count`, `edge_count` the number of links; ingesters run in dependency order (parsha-weekly works consume the parsha names, so parsha must precede them — assert the recorded call order); if an ingester raises, **no partial `Snapshot` is left behind** (the whole crawl is one transaction); the returned `Snapshot` id is what every `Work`, `LearnableUnit` and `TopicLink` written during the run points at.

- [ ] **Step 2: TDD `write_snapshot` / `read_snapshot`**

Tests: a round trip preserves every field including Hebrew strings, JSONB shapes and `None`s; **two writes of the same input are byte-identical** — sort keys, fix the separators, and write `created_at` as an explicit ISO string; `read_snapshot` parses `created_at` back to a timezone-aware `datetime` (a string reaching a `timestamptz` column is rejected by asyncpg, so this must be tested, not assumed); a truncated file raises a clear error naming the line number rather than yielding a half-catalog; the header record carries a format version so a future change fails loudly.

**Accept:** `uv run pytest tests/catalog/test_crawl.py tests/catalog/test_snapshot.py -q` green.

- [ ] **Commit point** — `crawl.py`, `snapshot.py`, tests.
  Suggested message: `feat(catalog): crawl orchestrator and deterministic JSONL snapshot`

---

# Task 4: The `sidra_db` CLI

**Delivers:** the four commands that make the project portable across machines.

**Files:** `backend/src/sidra/cli/{__init__,sidra_db}.py` · `backend/tests/cli/test_sidra_db.py` · `[project.scripts]` entry in `pyproject.toml`

**Commands:**

| Command | Behaviour |
|---|---|
| `seed` | Rebuild the catalog from the committed snapshot. **Offline, deterministic, seconds.** |
| `refresh` | Re-crawl Sefaria and write a **new** snapshot. Deliberate; **never on boot.** |
| `verify` | Assert the catalog matches `expected_counts.json`; exit non-zero on mismatch. |
| `export` | Write the current catalog to a snapshot path. |

- [ ] **Step 1: TDD the CLI**

**Write these tests synchronously.** Typer's `CliRunner.invoke` calls commands that call `asyncio.run`, and `asyncio.run` inside a running loop raises `RuntimeError`. Under `asyncio_mode = "auto"` an `async def` test *is* a running loop, so async CLI tests fail for a reason unrelated to the code. This is a real trap; note it in the test file.

Tests: `seed` on an empty database populates it and reports the counts; **`seed` is idempotent** — running twice yields identical row counts, not doubles; `verify` exits 0 on a good catalog and non-zero naming the first mismatch on a bad one; `refresh` is **not** wired into any startup path — assert by grepping the launcher scripts and compose file for `refresh` and finding nothing; `--help` lists exactly the four commands.

- [ ] **Step 2: Wire the launcher's auto-seed**

The launcher runs `sidra_db seed` when it finds the catalog empty, so a fresh machine needs no manual step. Add to `run_torah_sidra.{sh,bat}` after the healthcheck passes: count works, and if zero, seed.

Assert in the test file that the launcher invokes **`seed`** and never **`refresh`** — booting into a 656 MB crawl would be a bad surprise.

**Accept:** `uv run pytest tests/cli -q` green; on a clean database, `sidra_db seed` then `sidra_db verify` both succeed.

- [ ] **Commit point** — CLI, tests, launcher edits, pyproject script entry.
  Suggested message: `feat(cli): sidra_db seed/refresh/verify/export with launcher auto-seed`

---

# Task 5: The P1 acceptance gate

**Delivers:** the suite that decides whether P1 is done, written entirely from Amram's real data.

**Files:** `backend/tests/test_reference_values.py` · `backend/data/expected_counts.json` · `.gitlab-ci.yml`

- [ ] **Step 1: Write `expected_counts.json`**

```json
{
  "works": {"torah": 5, "neviim": 21, "ketuvim": 13, "mishnah": 63, "bavli": 37,
            "shulchan_aruch": 4, "parsha_weekly": 3},
  "units": {"torah": 187, "neviim": 380, "ketuvim": 362, "mishnah": 525, "bavli": 5349,
            "mishneh_torah": 15143, "shulchan_aruch": 1705},
  "shulchan_aruch_simanim": {"Orach Chayim": 697, "Yoreh De'ah": 403,
                             "Even HaEzer": 178, "Choshen Mishpat": 427},
  "total_derivable_units": 25370,
  "stored_units": {"parshiyos": 54, "aliyot": 378, "named_gates": 28},
  "ein_mishpat_edges": 118805,
  "ein_mishpat_shards": 17
}
```

- [ ] **Step 2: Write the acceptance suite**

**All 19 of Amram's seed refs must resolve to real catalog units.** Parametrize over them:

```
Avodah Zarah 28b                                              Gemara — actual
Avodah Zarah 38b                                              Gemara — scheduled
Jeremiah 44                                                   Neviim — actual
Jeremiah 47                                                   Neviim — scheduled
Psalms 16                                                     Ketuvim
Mishnah Shabbat 1:1                                           Mishna
Deuteronomy, Ki Tavo 3                                        Chumash — Shlishi
Shulchan Arukh, Orach Chayim 1:1                              Shulchan Aruch — start
Duties of the Heart, Seventh Treatise on Repentance 2         Chovot HaLevavot
Orchot Tzadikim 11:1                                          Shaar HaCharata
Mesillat Yesharim 1:1                                         not started
Shemirat HaLashon, Book I, The Gate of Remembering 1:1        not started
Likutei Moharan 1:1                                           Likutey Moharan
Tanya, Part I; Likkutei Amarim 1:1                            not started
Mishneh Torah, Foreign Worship and Customs of the Nations 5:2 Rabbi Jacob
Mishneh Torah, Human Dispositions 5:8                         David Cohen
Berakhot 13a                                                  David Hadar
Bereshit Rabbah 3:5                                           Yosef Mendelson & David Gofman
Sha'arei Teshuvah 1:29                                        Nesher
```

Then the assertions that make the model true:

| Assertion | Value |
|---|---|
| Avodah Zarah `28b → 38b` | **20 amudim** — Amram's real Gemara debt. Derive both seqs via `real_amudim`; assert the difference, not the absolute seqs. |
| Jeremiah `44 → 47` | **3 perakim** — his other real debt |
| Seder Zeraim | **75** perakim, so `corpus_ordinal(works, "Mishnah Shabbat", 1) == 76` |
| Corpus totals | Neviim 380 · Ketuvim 362 · Mishnah 525 · Bavli 5,349 · MT 15,143 · SA 1,705 |
| Tamid | first amud is `25b` |
| Nazir | `33b` is absent |
| Every other masechta | starts at `2a` |
| Orchot Tzadikim / Mesillat Yesharim | 28 gates / 26 perakim |
| Ein Mishpat | **118,805** edges across **17** shards — so a truncated ingest **fails the gate** |
| `Deos 5:8 ↔ SA OC 2:6` | round-trips in both directions |
| `rank_masechtos` on Hilchos Avoda Zara | returns **Avodah Zarah** first |
| Hebrew guard | passes over the whole catalog, non-vacuously |

Every one of these is a measured fact. **If any stops holding, the model is wrong, not the test.**

- [ ] **Step 3: Write `.gitlab-ci.yml`**

Stages `lint → sast → test → coverage → build → docker-build`.

- **lint** — `ruff check .` and `ruff format --check .`
- **sast** — `semgrep scan --config auto --error` (**`scan`, not `ci`** — the `ci` subcommand rejects `--severity` and `--error` and exits 2), plus `uv run pip-audit` and `gitleaks detect --no-git --redact`. Fails on HIGH.
- **test** — `pytest -m "not live"` with `--junitxml=junit-unit.xml`, published via `artifacts: reports: junit:` with **`when: always`** so a failing job still uploads its report.
- **coverage** — `--cov-fail-under=100` with a cobertura report.
- **docker-build** — builds the image and runs `trivy image --severity HIGH,CRITICAL --exit-code 1`.

**`live`-marked tests are excluded from CI** — they hit the network and move 656 MB.

- [ ] **Step 4: Update the documents**

`docs/status.md` records P1 complete with the acceptance numbers. `docs/versions.md` keeps everything under the single unreleased `## v0.1.0` heading as subsections — **never a second version heading.** Add the `Personal/Torah_Learning_Sidra` entry to `C:/Users/Amram/IMPORTANT/Projects/PORT_ASSIGNMENTS.md` recording host ports **5285 / 8285 / 5524** and that no Redis is used, with the file paths that carry those defaults.

**Accept:** `uv run pytest -m "not live" --cov=sidra --cov-fail-under=100` green; `uv run pytest -m live` green; pipeline green end to end.

- [ ] **Commit point** — acceptance suite, expected counts, CI config, docs.
  Suggested message: `feat(gate): P1 acceptance suite, expected counts and GitLab pipeline`

---

## Definition of Done for P1

- [ ] All 19 seed refs resolve to real catalog units.
- [ ] `28b → 38b == 20` and `Jeremiah 44 → 47 == 3`.
- [ ] Every corpus total matches `expected_counts.json`; `sum(unit_count) == 25,370`.
- [ ] 118,805 Ein Mishpat edges across 17 shards, persisted with `kind` and `confidence`.
- [ ] `Deos 5:8 ↔ SA OC 2:6` round-trips; Hilchos Avoda Zara ranks Avodah Zarah first at ~42.5%.
- [ ] The two coverage asymmetries are asserted, not silently tolerated.
- [ ] `sidra_db seed` rebuilds the catalog offline from the committed snapshot and is idempotent.
- [ ] The launcher auto-seeds an empty catalog and never calls `refresh`.
- [ ] Snapshot writes are byte-identical across runs.
- [ ] Hebrew guard passes over the whole catalog, non-vacuously.
- [ ] 100% coverage; SAST green with zero HIGH findings; JUnit visible in the CI UI.
- [ ] `docs/status.md`, `docs/versions.md` and the root `PORT_ASSIGNMENTS.md` all updated.
- [ ] No `Any` in any signature; no state-changing git command anywhere in P1a, P1b or P1c.

## What P2 will need from P1

The ledger phase consumes exactly three things from here: **`unit_at`** (to turn a stored integer position into a displayable ref), **`Work.unit_count`** (to compute remaining units and projected completion dates), and **`TopicLink` plus `rank_masechtos`** (to drive the Gemara queue from Rabbi Jacob's Mishneh Torah position). Nothing in P2 re-reads Sefaria.
