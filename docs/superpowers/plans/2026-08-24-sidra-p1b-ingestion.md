# Torah Learning Sidra — P1b (Ingestion) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill the catalog — every sefer Amram learns, stored as a `Work` with its shape array, so `unit_at` can resolve any position in it.

**Architecture:** Because units are derived (spec §7.10), ingestion is mostly **one generic function** driven by a table of corpus specs: fetch a shape, filter and order the nodes, build a `WorkDraft` each, persist. Three things resist that and get their own task: parshiyos and aliyot (which carry Sefaria's own range expansions and must be stored), works whose unit names are not derivable from a count, and the title-alias layer.

**Tech Stack:** As P1a. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-24-torah-sidra-design.md` — §7.10 (derived catalog) and §7.4 (verified traps).

**Prerequisite:** **P1a complete and green.** This plan consumes `unit_at`, `unit_count`, `real_amudim`, `parse_shape`, `SefariaClient`, `Work`, `LearnableUnit`, `AddressScheme`, `Granularity` and `CORPUS_IDS` exactly as P1a defines them. Do not redefine any of them.

**Scope:** Three tasks. Ends with every work in Amram's sidra persisted and resolvable. P1c adds alignment, the snapshot, the CLI and the acceptance gate.

---

## Global Constraints

Identical to P1a. Repeated because they bite here:

- **No mocking of the database.** Real compose Postgres via P1a's `db_session` fixture.
- **No test touches the network** except tests marked `live`. Ingestion tests use `httpx.MockTransport` with inline shape payloads.
- **Hebrew is never hand-encoded.** `title_he` is Sefaria's `heTitle` verbatim, stripped of whitespace.
- **`addr_types` uses Sefaria's vocabulary** (`"Perek"`, `"Talmud"`, `"Halakhah"`, `"Integer"`, `"Aliyah"`, `"Mishnah"`), **never `Granularity` members.**
- **Never synthesize a range ref.** Aliyot store Sefaria's own expansion in `resolved_ref`.
- **Git is Amram's.** Commit points only.

---

## Measured Facts — the acceptance targets

Every number was measured against the live API on 2026-08-24. **These are what the tests assert.**

| Corpus | Works | Units | Shape path |
|---|---:|---:|---|
| Torah | 5 | 187 perakim | `Tanakh/Torah` |
| Neviim | 21 | **380** perakim | `Tanakh/Prophets` |
| Ketuvim | 13 | **362** perakim | `Tanakh/Writings` |
| Mishnah | 63 | **525** perakim | `Mishnah` |
| Talmud Bavli | 37 | **5,349** amudim | `Talmud/Bavli` |
| Mishneh Torah | **84** | 1,006 perakim / **15,143** halachos | `Halakhah/Mishneh Torah` |
| Shulchan Aruch | **6** | **1,705** simanim across the 4 chelakim (+2 EH appendices) | `Halakhah/Shulchan Arukh` |

| Trap | Behaviour |
|---|---|
| **Tamid** | first non-empty shape index **49** = `25b`; 17 amudim |
| **Nazir** | empty indices `[0, 1, 65]`; index 65 = `33b` is a **mid-masechta gap**; 129 amudim |
| **Orchot Tzadikim** | shape reports **29** gates, the 29th is empty → **28**; gate 11's `heTitle` has a **trailing newline** |
| **Mesillat Yesharim** | shape reports **27**, the 27th is empty → **26** |
| **Shulchan Arukh, Even HaEzer** | node has `"title": null` and `isComplex: true` |
| **Tanya** | titles contain a **literal semicolon** — `Tanya, Part I; Likkutei Amarim` |
| **Ketuvim** | Sefaria orders Koheles **last**; Amram wants the traditional printed order → local override |
| **Mishnah** | filter out `Rishonim on Mishnah`, `Acharonim on Mishnah`, `Modern Commentary on Mishnah` |
| **Chumash** | `alts.Parasha` gives **54 parshiyos × exactly 7 aliyot**; maftir is **deferred past P1** |
| **Aliyah names** | Sefaria has no term for Rishon…Shvi'i — `/api/terms/Shlishi` is 404 → local override |

Other works and their unit counts: Duties of the Heart 93 · Shemirat HaLashon 86 · Likutei Moharan 286 + 125 · Tanya 53/12/12/32/9 · Sha'arei Teshuvah `[52,34,231,22]` = 339 · Bereshit Rabbah 100.

---

# Task 1: The generic ingester

**Delivers:** one function that ingests Torah, Neviim, Ketuvim, Mishnah, Bavli, Mishneh Torah and Shulchan Aruch — everything whose units are derivable from a shape array.

**Files:**
- `backend/src/sidra/catalog/work_draft.py`
- `backend/src/sidra/catalog/corpus_ordinal.py`
- `backend/src/sidra/catalog/corpus_spec.py`
- `backend/src/sidra/catalog/ingest.py`
- `backend/src/sidra/db/persist.py`
- `backend/src/sidra/catalog/overrides/ketuvim_order.yaml`
- Tests mirroring each

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class WorkDraft:
    corpus_id: str
    corpus_seq: int
    index_title: str | None
    ref_title: str
    title_he: str
    granularity: Granularity
    address_scheme: AddressScheme
    shape: tuple[int, ...]
    labels: tuple[str, ...] | None
    unit_count: int
    source: Literal["sefaria", "local"]


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    corpus_id: str
    shape_path: str
    granularity: Granularity
    address_scheme: AddressScheme
    exclude_sections: frozenset[str] = frozenset()
    order_override: tuple[str, ...] | None = None


async def ingest_corpus(client: SefariaClient, spec: CorpusSpec) -> list[WorkDraft]: ...


async def persist_works(session: AsyncSession, drafts: Sequence[WorkDraft], snapshot_id: UUID) -> list[Work]: ...


def corpus_ordinal(works: Sequence[Work], ref_title: str, seq: int) -> int:
    """1-based position within a whole corpus, not within one work.

    Sum of every preceding work's ``unit_count`` plus ``seq``. This is what makes the Mishna track
    a single 525-perek stream rather than 63 separate ones, and what places Mishnah Shabbat 1:1 at
    ordinal 76 -- Seder Zeraim being exactly 75 perakim.
    """
```

**Two rules the generic path must implement, both from measured traps:**

1. **Trim trailing empty entries before counting.** Orchot Tzadikim's shape reports 29 gates with the 29th empty; Mesillat Yesharim reports 27 with the 27th empty. A `FLAT` work's `unit_count` is `len(shape)` *after* trailing zeros are dropped. This single rule fixes both, and the two are separate tests.
2. **Never trim interior empties.** `DAF_AMUD` counts non-empty slots via `real_amudim`, which already handles Nazir's index-65 gap. A `FLAT` work must not "compact" its shape — the position of an entry is its identity.

- [ ] **Step 1: TDD `WorkDraft` and `CorpusSpec`**

Tests: both are frozen (mutation raises `FrozenInstanceError`); `CorpusSpec` rejects a `corpus_id` not in `CORPUS_IDS` (raise `ValueError` naming the valid set); `shape` and `labels` are tuples, not lists, so drafts are hashable.

- [ ] **Step 2: TDD `ingest_corpus` against inline shape fixtures**

Fixtures are trimmed but structurally faithful — a handful of nodes each, with the real field names Sefaria uses. **Do not fetch in these tests.**

The tests:

- **Neviim** — a 3-node fixture produces 3 drafts with `corpus_id="neviim"`, `address_scheme=FLAT`, `granularity=PEREK`, `corpus_seq` running 1,2,3 in shape order, and `unit_count == len(shape)`.
- **`title_he` is verbatim** — a node whose `heTitle` is `"ירמיהו"` yields exactly that; a node whose `heTitle` carries a trailing newline yields it stripped.
- **Bavli** — `address_scheme=DAF_AMUD`; a node with an Avodah-Zarah-shaped 152-slot array yields `unit_count == 150`; a Tamid-shaped array yields 17; a Nazir-shaped array yields 129. Assert all three in one parametrized test.
- **Mishnah excludes commentary** — a fixture containing a node with `section="Rishonim on Mishnah"` produces no draft for it. Assert the excluded titles are absent, not merely that the count is lower.
- **Trailing-empty trim** — a 29-entry shape whose last entry is 0 yields `unit_count == 28`; a 27-entry shape whose last is 0 yields 26. Two separate tests, named for Orchot Tzadikim and Mesillat Yesharim.
- **Interior empties are preserved** — a `FLAT` shape `[5, 0, 7]` yields `unit_count == 3` and `shape == (5, 0, 7)`. Position is identity; do not compact.
- **Mishneh Torah** — `address_scheme=NESTED`; a node with `chapters=[7,7,3,23,13,10,8]` yields `unit_count == 71` (`sum`), not 7.
- **Shulchan Aruch** — `address_scheme=FLAT` at `SIMAN` granularity; a node with 697 entries yields `unit_count == 697`, and the seif counts stay in `shape` so `unit_at` can surface them as `child_count`. Include the **Even HaEzer** node with `"title": null` and `isComplex: true` and assert it produces a draft rather than raising, taking its `ref_title` from a spec-supplied fallback.
- **Ketuvim order override** — with `order_override` supplied, drafts come back in override order and `corpus_seq` follows it. Assert **Koheles is not last** and that a book missing from the override raises `ValueError` naming it, so a Sefaria rename cannot silently drop a book.

- [ ] **Step 3: Write `ketuvim_order.yaml`**

The traditional printed order, one entry per line, each giving Sefaria's exact title:

```yaml
# Traditional printed order. Sefaria's own order places Koheles last, after Divrei HaYamim.
order:
  - Psalms          # Tehilim
  - Proverbs        # Mishlei
  - Job             # Iyov
  - Song of Songs   # Shir HaShirim
  - Ruth            # Rus
  - Lamentations    # Eicha
  - Ecclesiastes    # Koheles
  - Esther
  - Daniel
  - Ezra
  - Nehemiah        # Nechemia
  - I Chronicles    # Divrei HaYamim I
  - II Chronicles   # Divrei HaYamim II
```

Test that it holds exactly 13 entries and that `Ecclesiastes` precedes `Esther`.

- [ ] **Step 4: TDD `corpus_ordinal`**

Tests: for a Mishnah work list in seder order, `corpus_ordinal(works, "Mishnah Shabbat", 1) == 76`
— **Seder Zeraim's eleven masechtos total exactly 75 perakim**, which independently corroborates
Amram's stated position. Also: the first work's seq 1 is ordinal 1; the last unit of the last work
equals `sum(unit_count)`; an unknown `ref_title` raises `ValueError` naming it; a `seq` beyond a
work's `unit_count` raises rather than silently spilling into the next work.

- [ ] **Step 5: TDD `persist_works`**

Integration tests against the real Postgres: drafts are written as `Work` rows; `corpus_seq` survives; `shape` and `labels` round-trip through JSONB as lists; the unique constraint on `(corpus_id, corpus_seq)` rejects a duplicate; an empty draft list raises `ValueError` rather than silently succeeding.

- [ ] **Step 6: The `live` corpus verification**

A `@pytest.mark.live` test that ingests each of the seven corpora from the real API and asserts the measured totals in the table above — Neviim 21/380, Ketuvim 13/362, Mishnah 63/525, Bavli 37/5,349, Mishneh Torah 84 books / 15,143 halachos, Shulchan Aruch 1,705 simanim with OC 697 / YD 403 / EH 178 / CM 427.

**This is the test that catches a wrong fixture.** P1a's Tamid failure — an index carried from a report that contradicted the formula — is exactly what a live check finds and a fixture never will. Run with `-m live`, not in CI.

**Accept:** `uv run pytest tests/catalog/test_ingest.py tests/db/test_persist.py -q` green; `uv run pytest -m live -q` green against the network.

- [ ] **Commit point** — the five source files, the YAML, and their tests.
  Suggested message: `feat(catalog): generic corpus ingester with Ketuvim order override`

---

# Task 2: The stored-unit works

**Delivers:** the three cases the generic path cannot express — parshiyos and aliyot, works with non-derivable unit names, and the parsha-weekly works Amram owns on paper.

**Files:**
- `backend/src/sidra/catalog/parasha_node.py`
- `backend/src/sidra/catalog/ingest_parsha.py`
- `backend/src/sidra/catalog/ingest_named.py`
- `backend/src/sidra/catalog/ingest_parsha_works.py`
- `backend/src/sidra/catalog/overrides/aliyah_names.yaml`
- `backend/src/sidra/catalog/overrides/parsha_works.yaml`
- `backend/src/sidra/db/persist_units.py`
- Tests mirroring each

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class ParashaNode:
    title_en: str
    title_he: str
    whole_ref: str
    aliyah_refs: tuple[str, ...]      # exactly 7


def parse_parasha_nodes(index_payload: dict[str, Any]) -> list[ParashaNode]: ...
```

`parse_parasha_nodes` is **the only parsha parser in the codebase.** An earlier draft grew two, in different modules, parsing the same structure differently.

**It reads `payload["alts"]["Parasha"]["nodes"]`** — the `/api/index/` form. `/api/v2/raw/index/`'s `alt_structs` returns `title=None` and `heTitle=None`, so it is unusable here and there is **no fallback path** (spec §7.8).

- [ ] **Step 1: TDD `parse_parasha_nodes`**

Fixture: a trimmed `/api/index/Deuteronomy` payload with two Parasha nodes, each carrying `title`, `heTitle`, `wholeRef` and a 7-element `refs` array.

Tests: both nodes parse; `title_he` comes through as real Hebrew; `aliyah_refs` has exactly 7 entries; a node with a `refs` array of any other length raises `ValueError` naming the parsha (Sefaria is consistent at 7, and a change should fail loudly rather than silently produce a short parsha); a payload whose `alts` key is missing raises `ValueError` mentioning `alts`, **not** a `KeyError`.

- [ ] **Step 2: Write `aliyah_names.yaml` and TDD parsha ingestion**

```yaml
# Sefaria has no term for these — /api/terms/Shlishi returns 404 — so they are local.
aliyot:
  - {ordinal: 1, en: Rishon,  he: ראשון}
  - {ordinal: 2, en: Sheni,   he: שני}
  - {ordinal: 3, en: Shlishi, he: שלישי}
  - {ordinal: 4, en: Revii,   he: רביעי}
  - {ordinal: 5, en: Chamishi, he: חמישי}
  - {ordinal: 6, en: Shishi,  he: ששי}
  - {ordinal: 7, en: Shvii,   he: שביעי}
```

`ingest_parsha` produces a `WorkDraft` with `address_scheme=STORED`, `granularity=PARSHA`, plus `LearnableUnit` rows: 54 parshiyos (each `is_range=True`, `resolved_ref` = Sefaria's `wholeRef`) and 378 aliyot (each with `parent_seq` pointing at its parsha, `ordinal` 1–7, `label_en` from the YAML, `resolved_ref` = Sefaria's own aliyah ref).

Tests: five chumashim yield **54 parshiyos and 378 aliyot**; every parsha has exactly 7 children; `resolved_ref` is Sefaria's string **verbatim** — assert one equals `"Deuteronomy 26:16-26:19"` and that no code path builds it by concatenation; `addr_types` is `("Aliyah",)` for aliyot and `("Parasha",)` for parshiyos, never a `Granularity` member; Ki Tavo's third aliyah has `label_en == "Shlishi"` and `label_he == "שלישי"`.

**State in the task that maftir is deferred past P1**, and why: the index alt-struct carries 7 aliyot, and only `/api/calendars` exposes the 8th. `aliyah_names.yaml` therefore holds 7 entries, not 8.

- [ ] **Step 3: TDD `ingest_named` — works whose unit names are not derivable**

For Orchot Tzadikim the shape gives a count but not the shaar names; those live in `alts.Gate`. This ingester fetches the index, reads the gate titles, and attaches them to the `Work` as `labels` — so the work stays `FLAT` and derives its units, with `labels` overriding `label_en`.

Tests: 28 gates, not 29; gate 11's English label is its gate name and **its Hebrew label is stripped of the trailing newline** (assert `not label.endswith("\n")` explicitly — this is a measured trap); `labels` has exactly `unit_count` entries, so a mismatch raises rather than producing an off-by-one on every later lookup.

- [ ] **Step 4: TDD `ingest_parsha_works` — the three parsha-weekly works**

```yaml
works:
  - {ref_title: "Likutei Sichot",              title_he: "ליקוטי שיחות",   source: local,   deep_link: false}
  - {ref_title: "The Midrash Says",            title_he: "המדרש אומר",     source: local,   deep_link: false}
  - {ref_title: "Covenant and Conversation",   title_he: "ברית ושיחה",     source: sefaria, deep_link: true,
     sefaria_title: "Covenant and Conversation Family Edition"}
```

Each becomes a `Work` with `corpus_id="parsha_weekly"`, `granularity=PARSHA`, `address_scheme=FLAT`, `shape=(1,) * 54`, and `labels` = the 54 parsha names harvested in Step 2.

Tests: three works; each has `unit_count == 54`; `unit_at(..., seq=1).label_en == "Bereshit"`; the two local works have `source == "local"` and `index_title is None`; Covenant and Conversation has `source == "sefaria"` and a resolvable Sefaria title.

Note in the task that **Likutei Sichot and The Midrash Says are not on Sefaria at all** — confirmed by walking the full 6,604-book table of contents — so they carry no ref and the UI shows position without a deep link. That is a normal state, not a degradation.

- [ ] **Step 5: TDD `persist_units`**

Integration: writes `LearnableUnit` rows for a `STORED` work; resolves `parent_seq` to `parent_id` **after** the parent rows are flushed and have ids; the unique constraint on `(work_id, seq)` rejects a duplicate; a `parent_seq` with no matching row raises `ValueError` naming the orphan rather than writing a null parent.

**Accept:** `uv run pytest tests/catalog -q` and `uv run pytest tests/db -q` green. A `live` test ingests the five chumashim from the real API and asserts 54 parshiyos / 378 aliyot.

- [ ] **Commit point** — the seven source files, two YAMLs, and their tests.
  Suggested message: `feat(catalog): parsha, aliyah, named-label and parsha-weekly ingestion`

---

# Task 3: Title aliases and the Hebrew guard

**Delivers:** the layer that lets Amram's own spellings resolve, and the assertion that keeps Hebrew honest.

**Files:**
- `backend/src/sidra/catalog/ingest_aliases.py`
- `backend/src/sidra/catalog/overrides/local_aliases.yaml`
- `backend/tests/catalog/test_ingest_aliases.py`
- `backend/tests/test_hebrew_integrity.py`

**Produces:** `async def ingest_aliases(client, session, works, snapshot_id) -> int` returning the alias count.

Aliases come from two sources: Sefaria's own `schema.titles` (available **only** on `/api/v2/raw/index/`, which is why P1a's client has `raw_index`), and a local file for Amram's spellings.

- [ ] **Step 1: Write `local_aliases.yaml`**

```yaml
# Amram's spellings -> the canonical ref_title. Sefaria's English titles are translations,
# not transliterations: "Hilchos Daos" is "Mishneh Torah, Human Dispositions".
aliases:
  "Mesechet Avoda Zara":  Avodah Zarah
  "Avoda Zara":           Avodah Zarah
  "Brachot":              Berakhot
  "Tehilim":              Psalms
  "Yirmiyahu":            Jeremiah
  "Mishna Torah":         Mishneh Torah
  "Hilchos Avoda Zara":   "Mishneh Torah, Foreign Worship and Customs of the Nations"
  "Hilchos Daos":         "Mishneh Torah, Human Dispositions"
  "Chovot Halevavot":     Duties of the Heart
  "Shaarei Teshuva":      "Sha'arei Teshuvah"
  "Orchos Tzaddikim":     Orchot Tzadikim
  "Mesilat Yesharim":     Mesillat Yesharim
  "Shmirat Halashon":     Shemirat HaLashon
  "Likutey Moharan":      Likutei Moharan
```

- [ ] **Step 2: TDD `ingest_aliases`**

Tests: Sefaria aliases are harvested from `schema.titles` and written with `source="sefaria"`; local aliases are written with `source="local"`; both English and Hebrew variants are stored with the right `lang`; a local alias whose target `ref_title` matches no persisted `Work` raises `ValueError` naming it — **a typo in the YAML must fail the ingest, not vanish**; looking up `"Mesechet Avoda Zara"` returns the `Avodah Zarah` work; the same alias is not written twice when ingest runs twice.

- [ ] **Step 3: The Hebrew integrity guard**

An integration test over the **whole persisted catalog**:

```python
ALLOWED_SEPARATORS = set(" ,:.-–—()[]/0123456789")


def _is_clean(text: str) -> bool:
    return all(c in ALLOWED_SEPARATORS or HEBREW_BLOCK_START <= c <= HEBREW_BLOCK_END for c in text)
```

Assert that **every** `Work.title_he` and every stored `LearnableUnit.label_he` passes, and that the catalog is not vacuously clean — at least one `title_he` must contain a character in the Hebrew block, so an all-empty catalog cannot silently pass.

Write the failure message to name the offending work, the offending character, its codepoint and its Unicode name. That is what turns a mystery into a one-line fix.

**Why this exists:** hand-written numeric character references once put a Cyrillic Che (U+04B4) where gershayim belonged and an Arabic alef (U+0673) where geresh belonged, corrupting four of five Hebrew strings while looking correct in a diff. The rule is that Hebrew is copied from Sefaria as UTF-8 or computed by `to_gematria`, never typed as escapes.

- [ ] **Step 4: Ingest the whole catalog once, live**

A `@pytest.mark.live` test that runs every ingester from Tasks 1–3 against the real API into the real database, then asserts:

- Work count per corpus matches the table at the top of this plan
- Total derivable units across all works — `sum(unit_count)` — is **25,370**
- Stored `LearnableUnit` rows number **~460** (54 parshiyos + 378 aliyot + 28 gates)
- The Hebrew guard passes over the whole catalog
- `unit_at` resolves all 19 of Amram's seed refs (the full list is in P1c Task 5)

**Accept:** `uv run pytest -m "not live" -q --cov=sidra --cov-fail-under=100` green, then `uv run pytest -m live -q` green.

- [ ] **Commit point** — the alias ingester, the YAML, both test files.
  Suggested message: `feat(catalog): title aliases and the Hebrew codepoint guard`

---

## Definition of Done for P1b

- [ ] Every corpus in the measured table ingests to its exact work and unit counts.
- [ ] Tamid's first amud is `25b`; Nazir omits `33b`; every other masechta starts `2a`.
- [ ] Orchot Tzadikim has 28 gates with names attached; Mesillat Yesharim has 26 perakim.
- [ ] Shulchan Arukh, Even HaEzer ingests despite `"title": null`.
- [ ] Ketuvim follows the traditional printed order — Koheles is not last.
- [ ] 54 parshiyos and 378 aliyot are stored with Sefaria's own `resolved_ref` strings, none synthesized.
- [ ] Three parsha-weekly works exist; two carry no Sefaria ref and that renders as a normal state.
- [ ] `"Mesechet Avoda Zara"` resolves to the `Avodah Zarah` work.
- [ ] The Hebrew guard passes over the whole catalog and is non-vacuous.
- [ ] `sum(unit_count)` across all works is **25,370**; stored `LearnableUnit` rows are ~460.
- [ ] 100% coverage; ruff clean; `-m live` green.
