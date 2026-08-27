# Torah Learning Sidra — Design Specification

**Date:** 2026-08-24
**Status:** Draft for review
**Author:** Design session with Amram
**Supersedes:** the manual Obsidian note

---

## 1. Purpose

Amram learns Torah across three categories — **Daily**, **Shabbat**, and **Chavrusa** — spanning roughly twenty concurrent tracks. Today the state of that learning lives in a hand-edited Obsidian note listing each track and its current position. That note has three failures:

1. **It must be manually updated after every session**, which means opening Obsidian mid-learning.
2. **It does not know what comes next.** After Yirmiyahu 52 comes Yechezkel 1, but the note cannot say so; the ordering lives in Amram's head.
3. **It has no future.** It cannot answer "when do I finish Avoda Zara", "how far behind am I", or "how is Shulchan Aruch even ordered".

This app replaces that note. It owns the canonical ordering of every sefer being learned, tracks the exact position in each, records when each was last advanced, computes how far behind or ahead the schedule Amram is, and projects dated completion for every track and everything queued behind it.

It is a **single-user, desktop, locally-hosted** application. No auth, no multi-tenancy, no mobile layout.

---

## 2. The core insight

The tracks are not checklists. **They are debt ledgers.**

Every daily track has a fixed rate of one unit per day. The *schedule* advances on the calendar whether or not learning happened. The *actual* position advances only when it did. The gap between them is a debt measured in units, and Amram's own rule is that debt is paid down by doubling up.

```
scheduled = anchor_ordinal + rate × periods_elapsed(anchor_date → today)
actual    = ordinal of the latest Advance
debt      = scheduled − actual          negative debt = credit, and it banks
```

As of 2026-08-24 this model reproduces Amram's own reckoning exactly:

| Track | Actual | Scheduled (Tue) | Debt | Amram's own note |
|---|---|---|---|---|
| Gemara | Avoda Zara 28b | 38b | **20 amudim** | "20 days behind" |
| Neviim | Yirmiyahu 44 | 47 | **3 perakim** | "3 days behind" |

Both fall out of the arithmetic with no fudging. The 28b→38b gap is exactly 20 amud slots in Sefaria's shape array for Avodah Zarah; Yirmiyahu 44→47 is exactly 3 perakim. **This correspondence is the primary validation of the whole model and must be encoded as a test.**

A second insight follows from the first. Because the rate is fixed and the catalog is complete, **every future date is derivable rather than estimated.** The app can state the calendar date Avoda Zara ends, the date Neviim finishes, the date Yechezkel begins — and show each of those dates sliding by exactly one day for each day fallen behind. That is the "future plan" the Obsidian note cannot provide.

---

## 3. Scope

### In scope

- Canonical structure catalog for every sefer being learned (~250 works, ~460 stored units, 118,805 edges)
- Position tracking, advance history with timestamps and notes
- Debt ledger with banking, per-track projections, dated roadmap
- Cross-work alignment (Bavli ↔ Mishneh Torah ↔ Shulchan Aruch) via Ein Mishpat
- Hebrew calendar integration: Hebrew date, weekly parsha, Yom Tov
- User-managed tags, cross-cutting over the three fixed categories
- Chavrusa records with session logs, sorted by staleness
- Pace Explorer — aspirational rate/horizon calculator, read-only
- Machine-readable JSON state export and import, for moving between machines
- Full portability: deterministic catalog seed, ledger export/import

### Explicitly out of scope

- **Caching Sefaria text.** The app stores refs and deep-links. Sefaria licenses per text *version* (CC-BY, CC-BY-SA, CC-BY-NC, or unverified); storing structure — counts, titles, ref strings — avoids the question entirely.
- Mobile layout. Desktop only, per decision.
- Authentication, multi-user, sharing.
- **Any Obsidian integration.** Dropped 2026-08-25 on Amram's decision: the app replaces the
  note rather than mirroring it, and he is moving off Obsidian for this. The consequence is
  recorded in section 12.
- Statistical or topic-model inference of alignment. Only Ein Mishpat and the Tur bridge, both of which are real scholarly apparatus.

---

## 4. Domain model

### 4.1 Catalog (reference data — seeded, read-only at runtime)

#### `Work`

One sefer or one book. `Avodah Zarah`, `Jeremiah`, `Mishneh Torah, Human Dispositions`, `Shulchan Arukh, Orach Chayim`.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | surrogate PK |
| `corpus_id` | UUID \| None | FK → Corpus, when the work belongs to an ordered corpus |
| `corpus_seq` | int \| None | position within that corpus |
| `index_title` | str \| None | the fetchable Sefaria Index; **differs from `ref_title`** for complex nodes. NULL when hand-authored |
| `ref_title` | str | exact title path used when building refs |
| `title_he` | str | Hebrew title |
| `granularity` | Granularity | unit type this work is enumerated at |
| `unit_count` | int | denormalised count, for progress maths |
| `source` | `sefaria` \| `local` | |
| `snapshot_id` | UUID | which ingest run produced it |

#### `LearnableUnit`

The atom. One row per learnable portion. **~460 rows** after the §7.10 revision — units are derived from each work's shape array, not stored. See §7.10.

```python
class LearnableUnit(BaseModel):
    id: UUID
    work_id: UUID
    seq: int                            # 1..N monotonic study order; this is the cursor
    parent_id: UUID | None              # aliyah → parsha; perek → shaar; NULL for flat works

    # --- ref round-trip: the only two fields to_ref() reads ---
    ref_title: str
    addr: list[str]                     # ALWAYS strings, never ints (see note below)
    addr_types: list[str]               # mirrors Sefaria addressTypes; validation only

    index_title: str | None
    source: Literal["sefaria", "local"]
    snapshot_id: UUID

    # --- range units (aliyah, parsha, Tehillim cycle day) ---
    is_range: bool
    resolved_ref: str | None            # Sefaria's OWN expansion, cached at seed time
    resolved_he_ref: str | None
    is_spanning: bool | None

    # --- display ---
    granularity: Granularity
    label_en: str                       # "38b" | "Shlishi" | "5:8" | "ON REMORSE"
    label_he: str                       # "ל״ח ב" | "שלישי" | "שער החרטה"
    ordinal: int | None
    child_count: int | None             # segments inside this unit, from shape chapters[i]
```

The ref formula, which round-trips **16 of 17** unit types in this sidra:

```python
def to_ref(unit: LearnableUnit) -> str:
    return unit.ref_title if not unit.addr else f"{unit.ref_title} {':'.join(unit.addr)}"
```

**`addr` is `list[str]`, not `list[int]`.** Sefaria is polymorphic here: `/api/texts/Avodah Zarah 38b` returns `"sections": ["38b"]` (string) while Mishnah returns `[1, 1]` (ints). Strings round-trip both without loss.

**Two rules that keep the catalog honest:**

1. **Never synthesize a range ref.** Sefaria's range-tail compression (`Deuteronomy 26:16-26:19` → `Deuteronomy 26:16-19`) is undocumented and not reversibly derivable. Store the *pointer* form (`Deuteronomy, Ki Tavo 3`) and cache Sefaria's own expansion into `resolved_ref` at seed time. Sefaria remains the sole authority on range syntax.
2. **`index_title` ≠ `ref_title` for complex and alt-struct units.** `index_title` is what you pass to `/api/shape/`; `ref_title` is what you concatenate into a ref. Separate columns are what let Tanya's literal semicolons and Chumash's virtual parsha titles coexist with flat works.

##### Round-trip proof — every unit type in this sidra, all verified live

| Unit type | `ref_title` | `addr` | → ref |
|---|---|---|---|
| Daf + amud | `Avodah Zarah` | `["38b"]` | `Avodah Zarah 38b` |
| Aliyah | `Deuteronomy, Ki Tavo` | `["3"]` | expands to `Deuteronomy 26:16-19` |
| Parsha (whole) | `Deuteronomy, Ki Tavo` | `[]` | `Deuteronomy, Ki Tavo` |
| Perek | `Jeremiah` | `["44"]` | `Jeremiah 44` |
| Mizmor | `Psalms` | `["16"]` | `Psalms 16` |
| Mishnah | `Mishnah Shabbat` | `["1","1"]` | `Mishnah Shabbat 1:1` |
| Halacha | `Mishneh Torah, Human Dispositions` | `["5","8"]` | `Mishneh Torah, Human Dispositions 5:8` |
| Seif | `Shulchan Arukh, Orach Chayim` | `["1","1"]` | `Shulchan Arukh, Orach Chayim 1:1` |
| Midrash siman | `Bereshit Rabbah` | `["3","5"]` | `Bereshit Rabbah 3:5` |
| Treatise chapter | `Duties of the Heart, Seventh Treatise on Repentance` | `["2"]` | `… Repentance 2` |
| Os | `Sha'arei Teshuvah` | `["1","29"]` | `Sha'arei Teshuvah 1:29` |
| Gate paragraph | `Orchot Tzadikim` | `["11","1"]` | `Orchot Tzadikim 11:1` |
| Shaar perek | `Shemirat HaLashon, Book I, The Gate of Remembering` | `["1","1"]` | `… Remembering 1:1` |
| Torah section | `Likutei Moharan` | `["1","1"]` | `Likutei Moharan 1:1` |
| Tanya perek | `Tanya, Part I; Likkutei Amarim` | `["1","1"]` | `Tanya, Part I; Likkutei Amarim 1:1` |
| Parsha-work unit | `Covenant and Conversation Family Edition, Bereshit` | `[]` | deep-linkable |
| Likutei Sichot / Midrash Says | — | — | `source="local"`, **no Sefaria ref** |

#### `TitleAlias`

Amram's spellings differ from Sefaria's, and Mishneh Torah titles are *English translations*, not transliterations — `Hilchos Daos` is `Mishneh Torah, Human Dispositions`. Sefaria ships the alias list free: `/api/v2/raw/index/<T>` exposes `schema.titles` (25 variants for Deos alone, Hebrew included).

| Field | Type |
|---|---|
| `work_id` | UUID |
| `alias` | str |
| `lang` | `en` \| `he` |
| `source` | `sefaria` \| `local` |

Local aliases are added for Amram's spellings: `Mesechet Avoda Zara`, `Brachot`, `Tehilim`, `Mishna Torah`, `Chovot Halevavot`, `Hilchos Avoda Zara`, `Shaarei Teshuva`.

#### `TopicLink`

Ein Mishpat Ner Mitzvah edges. See §8.

| Field | Type | Notes |
|---|---|---|
| `from_ref` | str | anchor segment ref |
| `to_ref` | str | target ref |
| `from_work_id` / `to_work_id` | UUID | |
| `kind` | `ein_mishpat` \| `tur_bridge` \| `manual` | provenance matters — `tur_bridge` edges are inferred |
| `anchor_group` | str | shared `anchorRef`; grouping key |
| `confidence` | `direct` \| `inferred` | |

### 4.2 Ledger (Amram's data)

#### `Track`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `name_en` / `name_he` | str | display |
| `category` | `DAILY` \| `SHABBAT` \| `CHAVRUSA` | exactly one; fixed set |
| `kind` | TrackKind | see §5.2 |
| `sequence_source` | JSON | corpus id, curated queue, or calendar rule |
| `rate` | int | units per period |
| `period` | `DAY` \| `WEEK` \| `NONE` | `NONE` = chavrusa, no debt |
| `anchor_date` | date | |
| `anchor_ordinal` | int | scheduled ordinal on `anchor_date` |
| `starts_on` | date \| None | future-dated tracks accrue no debt before this |
| `chavrusa_id` | UUID \| None | |
| `is_active` | bool | |

#### `Advance`

Every movement. This one table is simultaneously the history, the streak data, the pace input, and the chavrusa session log.

| Field | Type |
|---|---|
| `id` | UUID |
| `track_id` | UUID |
| `from_ordinal` / `to_ordinal` | int |
| `unit_count` | int |
| `occurred_at` | datetime (tz-aware) |
| `hebrew_date` | str |
| `note` | str \| None |

#### `Chavrusa`

| Field | Type |
|---|---|
| `id` | UUID |
| `name` | str — may name more than one person (`Yosef Mendelson & David Gofman`) |
| `notes` | str \| None |

Chavrusa tracks have `period = NONE`: no debt, only staleness and session history.

#### `Tag` and `track_tags`

User-managed, full CRUD. **Categories say where a track lives; tags are cross-cutting labels.** A track has exactly one category and any number of tags.

| Field | Type |
|---|---|
| `id` | UUID |
| `name` | str, unique |
| `name_he` | str \| None |
| `color` | str \| None |

Tags are pure labels — no cadence, no rules, no side effects. They filter Today, Roadmap, and search. Seeded with one tag, `parsha`, applied to Chumash (Daily) plus Likutei Sichot, The Midrash Says and Covenant & Conversation (Shabbat).

#### `TrackAlignment`

| Field | Type | Notes |
|---|---|---|
| `follower_track_id` | UUID | the Gemara track |
| `leader_track_id` | UUID | Rabbi Jacob's Mishneh Torah track |
| `mode` | `topic_map` \| `manual` | |

---

## 5. The schedule engine

Pure functions over catalog + ledger + date. **Nothing here is persisted.** Everything is recomputed per request, so derived state can never drift from the ledger.

### 5.1 Debt and banking

```
periods_elapsed = calendar days (or weeks) from anchor_date to today, inclusive rules per period
scheduled       = anchor_ordinal + rate × periods_elapsed
debt            = scheduled − actual
```

- `debt > 0` → behind. Displayed as `N amudim behind`.
- `debt < 0` → ahead. **Surplus banks.** Displayed as `N days ahead`, never as a negative number, so it does not read as licence to stop.
- Tracks with `starts_on` in the future accrue no debt and display `starts in N weeks`.

**The clock ticks every calendar day, including Shabbos and Yom Tov.** No exceptions, per decision. Debt is debt.

### 5.2 Track kinds

| Kind | Sequence comes from | Used by |
|---|---|---|
| `CORPUS` | concatenate whole works in canonical order | Neviim, Ketuvim, Mishna, Shulchan Aruch, both Mishneh Torah chavrusa tracks |
| `CURATED_QUEUE` | an explicit ordered list of works | Gemara (fed by the topic map), the seven Shabbat sefarim |
| `PARSHA_ALIYAH` | this week's parsha → its 7 aliyot, calendar-driven | Chumash |
| `PARSHA_WEEKLY` | one unit per parsha week | Likutei Sichot, The Midrash Says, Covenant & Conversation |
| `OPEN` | no rate; position + staleness only | all chavrusa tracks |

Only `CURATED_QUEUE` requires configuration. `CORPUS` order is inherited — which is why Yechezkel following Yirmiyahu is not a decision Amram ever makes.

### 5.3 Calendar rules

- **Parsha for any date** from Sefaria `/api/calendars?year=&month=&day=&diaspora=1`, verified to work for arbitrary dates. This makes a *dated* Chumash roadmap possible.
- **Combined-parsha weeks** (Vayakhel-Pekudei, Tazria-Metzora, and — imminently — Nitzavim-Vayeilech on 2026-09-01): **two aliyot per day**, 14 across the week, per decision. Keeps the annual cycle exact.
- **Hebrew date and Yom Tov** from the Hebcal HTTP API (CC-BY, no key, documented policy), snapshotted into Postgres for the relevant year range.
- **`@hebcal/core` is deliberately NOT bundled** — it is GPL-2.0, and copyleft in the frontend bundle should be a deliberate decision, not an accident. `@hebcal/leyning` (BSD-2) remains available if ever needed.
- A Hebrew year runs **353–385 days**, so a "one a day" cycle drifts 10–11 units per year against a fixed corpus. The Pace Explorer must state this.

### 5.4 Projections

With a fixed rate and a complete catalog, projections are arithmetic, not inference:

```
units_remaining     = work.unit_count − actual_ordinal_within_work
projected_finish    = today + units_remaining / rate     (adjusted for current debt)
```

Every projected date slides by exactly one day per day of debt accrued.

---

## 6. Track inventory — the seed

All 19 existing positions verified to resolve against Sefaria on 2026-08-24.

### 6.1 Daily — rate 1/day

| Track | Kind | Position | Sefaria ref | Corpus size | Finishes |
|---|---|---|---|---|---|
| Chumash | `PARSHA_ALIYAH` | Ki Tavo, Shlishi | `Deuteronomy, Ki Tavo 3` | 378 aliyot | annual cycle |
| Neviim | `CORPUS` | Yirmiyahu 44 (**owes 3**) | `Jeremiah 44` | 380 perakim | 2026-12-25 |
| Ketuvim | `CORPUS` | Tehilim 16 | `Psalms 16` | 362 perakim | 2027-08-05 |
| Mishna | `CORPUS` | Shabbat 1:1 — day 76 | `Mishnah Shabbat 1:1` | 525 perakim | 2027-11-16 |
| Gemara | `CURATED_QUEUE` | Avoda Zara 28b (**owes 20**) | `Avodah Zarah 28b` | 150 amudim in AZ | 2026-11-28 |
| Shulchan Aruch | `CORPUS` | *not started* → OC 1:1 | `Shulchan Arukh, Orach Chayim 1:1` | **1,705 simanim** | ~4.7 years |

**Ketuvim uses the traditional printed order via a local override**, not Sefaria's (which places Koheles last, after Divrei HaYamim):

> Tehilim · Mishlei · Iyov · Shir HaShirim · Rus · Eicha · Koheles · Esther · Daniel · Ezra · Nechemia · Divrei HaYamim

**Mishna runs all six sedarim in order.** Seder Zeraim is exactly 75 perakim, so Shabbat 1:1 is day 76 — which independently corroborates the "straight through" answer and dates the track's start to ~2026-06-10.

| Seder | Masechtos | Perakim |
|---|---|---|
| Zeraim | 11 | 75 |
| Moed | 12 | 88 |
| Nashim | 7 | 71 |
| Nezikin | 10 | 74 |
| Kodashim | 11 | 91 |
| Tahorot | 12 | 126 |
| **Total** | **63** | **525** |

**Shulchan Aruch at one siman a day**, not one seif. At seif granularity it would take 36.7 years; at siman granularity, 4.7. Ordering, which Amram explicitly wanted mapped:

| Chelek | Simanim | Seifim |
|---|---|---|
| Orach Chaim | 697 | 4,183 |
| Yoreh De'ah | 403 | 3,702 |
| Even HaEzer | 178 | 1,830 |
| Choshen Mishpat | 427 | 3,694 |
| **Total** | **1,705** | **13,409** |

### 6.2 Shabbat — rate 1/week

| Track | Position | Sefaria ref | Size |
|---|---|---|---|
| Chovot HaLevavot | Shaar HaTeshuva 2 | `Duties of the Heart, Seventh Treatise on Repentance 2` | 93 nodes |
| Orchot Tzadikim | Shaar HaCharata (gate 11) | `Orchot Tzadikim 11:1` | 28 gates |
| Mesilat Yesharim | *not started* | `Mesillat Yesharim 1:1` | 26 perakim |
| Shmirat HaLashon | *not started* | `Shemirat HaLashon, Book I, The Gate of Remembering 1:1` | 86 nodes |
| Likutey Moharan | 1:1 | `Likutei Moharan 1:1` | 286 + 125 torot |
| Tanya | *not started* | `Tanya, Part I; Likkutei Amarim 1:1` | 118 perakim |
| **Likutei Sichot** | starts **2026-10-10** | *local, no ref* | 54 parshiyos/yr |
| **The Midrash Says** | starts **2026-10-10** | *local, no ref* | 54 parshiyos/yr |
| **Covenant & Conversation** | starts **2026-10-10** | `Covenant and Conversation Family Edition, <Parsha>` | 54 parshiyos/yr |

The three parsha-weekly tracks begin at **Shabbos Bereishis, 10 October 2026** (Parshas Bereishis is read the week of 2026-10-06, confirmed via the calendars API). Until then they display "starts in N weeks" and accrue no debt.

Tanya's Sefaria titles contain a **literal semicolon** — `Tanya, Part I; Likkutei Amarim` — which is part of the title string, not a delimiter.

### 6.3 Chavrusa — no rate, staleness only

| Chavrusa | Work | Position | Sefaria ref |
|---|---|---|---|
| Rabbi Jacob | Mishneh Torah *in order* | Hilchos Avoda Zara 5:2 | `Mishneh Torah, Foreign Worship and Customs of the Nations 5:2` |
| David Cohen | Mishneh Torah *in order* | Hilchos Deos 5:8 | `Mishneh Torah, Human Dispositions 5:8` |
| David Hadar | Gemara Brachot | 13a | `Berakhot 13a` |
| Yosef Mendelson & David Gofman | Bereishit Rabbah | 3:5 | `Bereshit Rabbah 3:5` |
| Nesher | Shaarei Teshuva | Shaar 1, os 29 | `Sha'arei Teshuvah 1:29` |

Both Mishneh Torah chavrusa tracks are `CORPUS` kind running the Rambam's own order, and they are **independent** — Rabbi Jacob is at Avoda Zara (Sefer Madda #4) while David Cohen is at Deos (#2).

**Bereishit Rabbah needs no override.** Verified: Sefaria's numbered chapters *are* the traditional parshiyos — ch 1 opens `רַבִּי הוֹשַׁעְיָה רַבָּה פָּתַח`, ch 2 `וְהָאָרֶץ הָיְתָה תֹהוּ וָבֹהוּ`, ch 3 `וַיֹּאמֶר אֱלֹהִים יְהִי אוֹר`, ch 12 `אֵלֶּה תוֹלְדוֹת הַשָּׁמַיִם`. So `3:5` is parsha 3, siman 5, natively addressable.

**Sha'arei Teshuvah** has no flat 1–339 numbering; osiyos restart per shaar (52 / 34 / 231 / 22). Bare "29" is disambiguated to **Shaar 1, os 29**.

---

## 7. Catalog ingestion

An **offline, idempotent, re-runnable job** — not part of the running app. The app never depends on Sefaria being reachable.

### 7.1 Pipeline

| Step | Source | Yields |
|---|---|---|
| 1 | `/api/index/` (one call, ~4 MB, 6,600 books) | the full TOC tree |
| 2 | `/api/shape/<path>` per corpus | counts. Paths: `Tanakh/Prophets`, `Tanakh/Writings`, `Mishnah`, `Talmud/Bavli`, `Halakhah/Mishneh Torah`, `Halakhah/Shulchan Arukh` |
| 3 | `alts.Parasha` on the five chumashim | 54 parshiyos × 7 aliyot as verse ranges |
| 4 | `schema.titles` per work | the alias layer, free |
| 5 | `links/links{0..16}.csv` from the export bucket, streamed and filtered (see §7.7) | the entire topic map, no per-daf crawling |
| 6 | three local override files | see §7.3 |

`/api/shape/Halakhah/Mishneh Torah` returns the Rambam's **entire 90-node corpus in one call** — of which 84 are hilchos books: 1,006 perakim, 15,143 halachos.

### 7.2 Snapshot, not live crawl

Output is a **committed snapshot file in the repo**. `sidra_db seed` rebuilds the catalog from it: offline, deterministic, seconds. A new machine gets byte-identical data. `sidra_db refresh` re-crawls Sefaria and writes a *new* snapshot — run deliberately, never on boot.

### 7.3 Local override files — three

1. **Ketuvim ordering** — traditional printed order (Sefaria's differs).
2. **Aliyah ordinal names** — Rishon…Shvi'i. Sefaria has no term for these; `/api/terms/Shlishi` returns `Term does not exist`, and `/api/terms/Aliyah` is the *sociological* term.
3. **Maftir as an eighth aliyah** — the index alt-struct gives 7; only `/api/calendars` `extraDetails.aliyot[7]` carries the maftir.

Likutei Sichot and The Midrash Says need only a `Work` row each — their unit *is* the parsha, and the 54-parsha spine already exists from the Chumash seed. **No hand-authored structure file is required for any work.**

### 7.4 Verified traps — each becomes a test

| Trap | Detail |
|---|---|
| Tamid starts at **25b** | 36 of 37 tractates start at 2a. Never hardcode 2a. |
| Bavli amudim = **~5,349**, not 5,422 | Traditional 2,711-daf figure overcounts: 17 tractates end on an `a` amud, plus Tamid. Recompute from shape arrays at ingest. |
| Leading zeros in Bavli `chapters` | Indices 0/1 are daf 1a/1b and are empty. Amud index → `daf = idx//2 + 1`, `side = 'b' if idx%2 else 'a'`. |
| Even HaEzer has `"title": null` | `isComplex: true`, with two flat appendices (Seder HaGet 101, Seder Halitzah 57). |
| Orchot Tzadikim reports 29 gates | The 29th is empty. **28 real gates.** |
| Mesillat Yesharim reports 27 | The 27th is empty. **26 real perakim.** |
| Likutei Moharan is depth-3 | But `referenceableSections = [true, true, false]` — only two levels addressable. Section counts vary wildly per torah; read them, never assume. |
| Tanya titles contain `;` | Literal, part of the title. |
| `/api/name/` returns Topics | Filter `type == "ref"` before using a completion as a ref. `Hilchos Shabbos` returns a *Topic*, which will not resolve. |
| HTTP 200 with an `error` key | Status codes lie. Always check the body. |
| Bare titles are ambiguous | `Avoda Zara 38b` → Bavli; `Avoda Zara 5.2` → *Mishnah*. **Never send an unqualified title**; always use the catalog's canonical `ref_title`. |
| `chapters` is polymorphic | `int \| list[int] \| list[dict]`. |
| Whole-book link fetches fail | `/api/links/Berakhot?with_text=0` → HTTP 504, reproducibly. Always pass `with_text=0` and fetch per-segment, or use the bulk CSV. |
| No conditional requests | Refresh is full re-fetch only. |
| GCS export is a monthly snapshot | `last_export.txt` = 2026-08-01. Fine for links; seed structure from the live API. |

### 7.5 Licensing

No rate limit is documented or was observed. Sefaria's API software is AGPLv3; **texts are licensed per version** — Public Domain, CC0, CC-BY, CC-BY-SA, CC-BY-NC, or unverified. Storing only structure sidesteps this. Attribution to Sefaria appears in the UI regardless. Hebcal content is CC-BY with a documented policy and requires attribution.

---

### 7.7 The Ein Mishpat extract — verified end to end

**Measured 2026-08-24, not assumed.** Earlier drafts described a single 34.7 MB `links0.csv`. That is wrong.

| Fact | Value |
|---|---|
| Shards | **17** — `links0.csv` … `links16.csv`; `links17` is 404 |
| Total size | **~656 MB** |
| Total rows | **5,041,682** |
| Column header | **`Conection Type`** — Sefaria's own typo, one `n`. `Connection Type` matches nothing. |
| Columns | `Citation 1`, `Citation 2`, `Conection Type`, `Text 1`, `Text 2`, `Category 1`, `Category 2` |
| Ein Mishpat edges | **118,805** |
| Extraction time | **49 seconds** |

**Stream and filter; never store the 656 MB.** Wrap each shard's HTTP response in a `TextIOWrapper` and feed `csv.DictReader` directly, keeping only rows whose `Conection Type` is `ein mishpat / ner mitsvah`. Shard 8 contains zero Ein Mishpat rows — an empty shard is normal, not an error. Rows are ordered alphabetically by `Citation 1`, so one masechta's edges may straddle shards; never assume locality.

| Edge direction | Count |
|---|---:|
| Talmud → Halakhah | 59,400 |
| Halakhah → Halakhah | 42,584 |
| Halakhah → Talmud | 16,821 |

**Round-trip verification** — the offline extract matches the live API exactly:

```
Avodah Zarah 38b:4     -> Forbidden Foods 17:13 | Semag Neg. 148
                       | Tur YD 112 | Shulchan Arukh YD 112:9
Human Dispositions 5:8 -> Berakhot 43b:19-20 | Kiddushin 31a:3
                       | Tur OC 2 | Shulchan Arukh OC 2:6
Foreign Worship 5:2    -> Sanhedrin 50a:4, 53a:14, 67a:4, 67a:5, 67a:8
```

**Aggregate ranking works** — this is the input to the Gemara queue. Hilchos Avoda Zara draws 471 links across 29 masechtos:

| Masechta | Links | Share |
|---|---:|---:|
| Avodah Zarah | 200 | 42.5% |
| Sanhedrin | 128 | 27.2% |
| Makkot | 18 | 3.8% |
| Chullin | 14 | 3.0% |
| Kiddushin | 14 | 3.0% |

The alignment screen shows the **ranked list**, never a single recommendation. Sanhedrin at 27% is materially significant and the reader should see it.

---

### 7.8 Alt-struct titles — use `/api/index/`, key `alts`

**Resolved 2026-08-24 by direct test.** Two probe reports disagreed; the test settles it.

| Endpoint | Field | `title` / `heTitle` |
|---|---|---|
| `/api/index/<T>` | `alts` | **resolved for every node type** |
| `/api/v2/raw/index/<T>` | `alt_structs` | `None` / `None` — only `sharedTitle` or a raw `titles[]` array |

```
/api/index/Deuteronomy  alts.Parasha[-1]  -> title="V'Zot HaBerachah"  heTitle="וזאת הברכה"
/api/v2/raw/index/...   alt_structs...    -> title=None  heTitle=None
```

Holds for both node kinds — parsha nodes that delegate through `sharedTitle`, and gate nodes that carry inline `titles[]`. **Ingester rule: always `/api/index/<Title>` + `alts`.** There is no fallback case.

**Trap:** Orchot Tzadikim gate 11's `heTitle` ends with a trailing newline. Strip whitespace on every ingested title.

---

### 7.9 The ingestion contract — one row type, one persistence layer

**Added 2026-08-24 after a plan review exposed the gap.** The catalog has nine ingesters (Tanakh, parsha, Mishnah, Bavli, Mishneh Torah, Shulchan Aruch, mussar works, parsha works, aliases). Without a stated contract between them and the database, each grows its own row shape — a first draft of the implementation plan produced four incompatible ones, with `addr_types` encoded four different ways.

**One row type.** `CatalogRow` is a frozen dataclass whose fields are exactly `LearnableUnit`'s insertable columns. Every ingester returns `list[CatalogRow]` and touches no session.

```python
@dataclass(frozen=True, slots=True)
class CatalogRow:
    seq: int
    ref_title: str
    addr: tuple[str, ...]            # always strings
    addr_types: tuple[str, ...]      # Sefaria addressTypes vocabulary, e.g. ("Perek",) — never Granularity
    granularity: Granularity
    label_en: str
    label_he: str                    # verbatim from Sefaria heRef; "" is a test failure, not a default
    index_title: str | None
    source: Literal["sefaria", "local"]
    is_range: bool
    resolved_ref: str | None
    resolved_he_ref: str | None
    is_spanning: bool | None
    ordinal: int | None
    child_count: int | None
    parent_seq: int | None           # resolved to parent_id at persist time
```

**One persistence layer.** `persist_work(session, work_spec, rows, snapshot_id) -> Work` is the only code that writes `Work` or `LearnableUnit`. Ingesters are pure and unit-testable without a database; persistence is integration-tested once instead of nine times.

**`addr_types` uses Sefaria's own `addressTypes` vocabulary** — `"Perek"`, `"Talmud"`, `"Halakhah"`, `"Integer"`, `"Aliyah"`, `"Mishnah"` — never `Granularity` members. `Granularity` says what a unit *is*; `addr_types` says how Sefaria *addresses* it. Conflating them was the single most common drift in the review.

**Canonical `corpus_id` vocabulary**, declared once and referenced everywhere:
`torah` · `neviim` · `ketuvim` · `mishnah` · `bavli` · `mishneh_torah` · `shulchan_aruch` · `mussar` · `chassidus` · `midrash` · `parsha_weekly`

---

### 7.11 Measured catalog totals

Measured by a full crawl on 2026-08-25. These are what `expected_counts.json` asserts.

| Corpus | Works | Derivable units |
|---|---:|---:|
| Torah (5 chumashim + the parsha cycle) | 6 | 619 |
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

Plus **432** stored units (54 parshiyos + 378 aliyot), **4,235** title aliases and **118,805**
Ein Mishpat edges. A full crawl takes **94 seconds**.

The earlier estimate of ~25,370 units predated the mussar, chassidus and midrash works being
specced, and counted Mishneh Torah at 15,229 rather than the measured 15,143.

---

### 7.10 Derived catalog — units are computed, not stored

**Revised 2026-08-24.** The original design stored one row per learnable unit: ~25,370 rows. Reviewing it against the code showed that almost all of them are *derivable*, and that storing them is tech debt rather than data.

`real_amudim` already computes `["2a", "2b", … "76b"]` from a 152-integer shape array. Jeremiah's 52 perakim are `range(1, 53)`. Mishneh Torah's 15,143 halachos — the majority of the original catalog — are a nested count array. **A position is an integer; its label is a function of that integer and the work's shape.**

So `Work` carries the shape, and units are resolved on demand.

```python
class AddressScheme(StrEnum):
    FLAT      = "flat"       # seq -> ["7"]              Tanakh perek, Mishnah perek, SA siman
    NESTED    = "nested"     # seq -> ["5", "8"]         Mishneh Torah halacha, Sha'arei Teshuvah os
    DAF_AMUD  = "daf_amud"   # seq -> nth non-empty slot Bavli
    STORED    = "stored"     # rows in learnable_unit    only where nothing is derivable
```

`Work` gains `shape: list[int]` (JSONB — Sefaria's own per-unit counts) and `labels: list[str] | None` (only for works whose unit names are not derivable, such as Orchot Tzadikim's shaarim).

**`unit_at(work, seq) -> ResolvedUnit`** is the single resolver. It replaces 25,000 rows with one function.

### What still needs stored rows

| Stored | Why | Rows |
|---|---|---:|
| Aliyot | carry Sefaria's own range expansions, which §4.1 forbids synthesizing | 378 |
| Parshiyos | carry Sefaria's `wholeRef` and Hebrew names | 54 |
| Named gates | Orchot Tzadikim's shaar names are not derivable from a count | 28 |
| **Total** | | **~460** |

### Resulting sizes

| Table | Before | After |
|---|---:|---:|
| `work` | ~250 | ~250 |
| `learnable_unit` | **25,370** | **~460** |
| `topic_link` | 118,805 | 118,805 |

Ein Mishpat edges are unaffected — they were always ref-strings, never unit rows.

### What this costs

A **gematria function** for Hebrew labels — about 20 deterministic lines, since `כ״ח ע״ב` is computed from 28 rather than fetched. And per-unit annotation would need a migration; that is acceptable because notes attach to `Advance` records, not to units.

### What this saves

The nine bespoke ingesters collapse to **one generic ingester** (fetch shape → store `Work` + array) plus two special cases (parsha, named-label works). It also makes §7.9's `CatalogRow` contract nearly moot: most ingesters now return a `Work`, not a list of rows.

---

### 7.6 Granularity choice — what determines catalog size

A work is enumerated at **the granularity its track advances at**, with the next level down preserved as `child_count`. This keeps ordinal arithmetic trivial (advancing is always `seq + 1`) without discarding structure.

The consequential case is **Shulchan Aruch**: enumerated at **siman** (1,705 rows), each carrying its seif count in `child_count`, because the track advances one siman a day. Enumerating at seif instead would produce 13,409 rows and make `seq + 1` mean something the track never does. Should seif-level ever be wanted, it is a catalog rebuild — cheap, deterministic, and the seif counts are already stored.

| Work | Granularity | Rows | `child_count` holds |
|---|---|---:|---|
| Chumash | aliyah (+ parsha) | 378 + 54 | pesukim |
| Torah | perek | 187 | pesukim |
| Neviim | perek | 380 | pesukim |
| Ketuvim | perek | 362 | pesukim |
| Mishnah | perek | 525 | mishnayos |
| Talmud Bavli | amud | 5,349 | segments |
| Mishneh Torah | halacha | 15,143 | — |
| **Shulchan Aruch** | **siman** | **1,705** | **seifim** |
| Likutei Moharan | torah section | 411 | comments |
| Sha'arei Teshuvah | os | 339 | — |
| Bereshit Rabbah | siman | 100 | — |
| Tanya | perek | 118 | seifim |
| Chovot HaLevavot | perek | 93 | paragraphs |
| Shemirat HaLashon | perek | 86 | paragraphs |
| Orchot Tzadikim | gate | 28 | paragraphs |
| Mesillat Yesharim | perek | 26 | verses |
| **Total units represented** | | **25,370** | |

Note: after §7.10 these are the units the catalog *represents*, resolved on demand from each work's shape array. Only ~460 are stored as rows.

Mishneh Torah dominates at 60% of the catalog. Only a fraction is on an active track today, but the whole corpus is seeded so the Ein Mishpat map and the chavrusa queues resolve without gaps.

---

## 8. Alignment — Ein Mishpat

Amram learns Mishneh Torah with Rabbi Jacob **in the Rambam's own order**, and pulls across the Gemara that matches whatever hilchos they are on. Hilchos Talmud Torah finished → Hilchos Avoda Zara began → Mesechet Avoda Zara began. His Gemara track is therefore ordered by *Mishneh Torah*, not by Shas.

Sefaria has digitised **Ein Mishpat Ner Mitzvah** — the classical marginal apparatus mapping every halachic sugya to Rambam / Semag / Tur / Shulchan Aruch — as a first-class link `type` string. It is not a text and has no Index; the links API is the only access path.

```
GET /api/links/Avodah_Zarah.38b        → 318 links, 29 of them ein mishpat

Avodah Zarah 38b:4  → Mishneh Torah, Forbidden Foods 17:13
                    → Sefer Mitzvot Gadol, Negative Commandments 148
                    → Tur, Yoreh De'ah 112
                    → Shulchan Arukh, Yoreh De'ah 112:9
```

Group by `anchorRef` and the alignment rows fall out. The graph is **bidirectional and round-trips exactly**: Deos 5:8 → SA OC 2:6, and SA OC 2:6 → Deos 5:8.

### 8.1 Two resolutions

- **Fine** — this halacha → these dapim. Note that Hilchos Avoda Zara 5:2 links to *Sanhedrin* 50a/53a/67a, **not** to Mesechet Avoda Zara. The mapping is per-halacha and the sugyos are scattered across Shas.
- **Aggregate** — for a set of hilchos, rank masechtos by Ein Mishpat link count, to propose the next masechta. This is what feeds the Gemara `CURATED_QUEUE`, with Amram confirming each transition.

### 8.2 Honest limits

1. **Rambam coverage is near-complete; Shulchan Aruch coverage is genuinely partial.** Horayos: 297 Ein Mishpat links, of which 112 point at Mishneh Torah versus 17 across all of SA. Structural, not a data defect.
2. **Zero-coverage dapim are real.** Sukkah 28a has 474 total links and *zero* Ein Mishpat. Aggadic stretches have none. Not a masechta property — Niddah 31a = 0, Niddah 66a = 38.
3. **Fallback: the Tur bridge.** Where a Bavli→SA edge is missing but Bavli→Tur exists on the same anchor, emit a provisional SA edge at siman granularity. Sampling found **104 matched / 0 unmatched** — SA follows Tur's siman numbering. These edges are stored with `confidence = inferred` and labelled as such in the UI.
4. **"No Shulchan Aruch parallel recorded" is a normal state**, rendered as ordinary UI, never an error.
5. **No statistical or topic-model inference.** Only real scholarly apparatus.

### 8.3 Drift

Rabbi Jacob's Rambam and the Gemara move at very different speeds — Hilchos Avoda Zara is 12 perakim at chavrusa pace; Mesechet Avoda Zara is 150 amudim at one a day, about five months. Whichever finishes first strands the other. The app surfaces **proportional drift** ("38% through the masechta, 21% through the hilchos") plus each side's projected date, so the collision is visible in advance.

---

### 8.4 The projected Gemara queue — computed from the extract

Rabbi Jacob's Mishneh Torah runs in the Rambam's order, so the Gemara queue is derivable years ahead. Computed from the 118,805-edge extract:

| Rambam (in order) | Top masechtos backing it | Links |
|---|---|---:|
| *Avodas Kochavim* (current) | **Avodah Zarah 42%** · Sanhedrin 27% · Makkot 4% | 471 |
| Teshuva | Yoma 18% · Sanhedrin 15% · Shevuot 9% | 104 |
| Krias Shema | **Berakhot 71%** · Shabbat 6% · Megillah 4% | 149 |
| Tefilah u'Birkas Kohanim | Berakhot 40% · Megillah 25% · Sotah 10% | 504 |
| Tefillin, Mezuzah, Sefer Torah | **Menachot 41%** · Shabbat 12% · Berakhot 10% | 292 |
| Tzitzis | **Menachot 61%** · Shabbat 8% · Nazir 5% | 96 |
| Brachos | **Berakhot 69%** · Chullin 8% · Pesachim 4% | 396 |
| Milah | **Shabbat 41%** · Yevamot 15% · Nedarim 8% | 73 |

These match what any learner would expect — Menachos for tefillin and tzitzis, Berachos for krias shema and brachos, Shabbos for milah. The map validates against known practice.

**Two consequences for the UI:**

1. **Proposal confidence varies and must be shown.** Krias Shema is 71% Berakhot — unambiguous. Teshuva's top match is 18% across a long tail. The alignment screen renders the *distribution's concentration*, never a bare single recommendation. A diffuse case is presented as diffuse.
2. **Sefer Ahavah parks the Gemara track in Berakhot for a long stretch** — Krias Shema, Tefilah and Brachos all resolve there, and Berakhot is already the David Hadar chavrusa track. Surface that collision at the transition.

## 9. Screens

### 9.1 Today — home

The answer to "what do I owe." Debt-ordered, grouped Daily / Shabbat / Chavrusa, filterable by tag. Each row: Hebrew name, current position, a compressed two-marker rail, a mono debt badge. One click advances, optionally with a note.

Today it opens with `עבודה זרה · 20 amudim behind`, then `ירמיהו · 3 perakim behind`.

### 9.2 Track — the signature screen

The full rail. **Two markers on one spine**: solid lit segment ending at the actual position, ghost marker at the scheduled position. *The gap between them is the debt, rendered literally.* Avoda Zara shows 150 nodes lit to 28b with the ghost at 38b.

Requires windowing — 5,349 amudim will not render unvirtualized.

### 9.3 Roadmap — dated

| Track | Position | Remaining | Finishes |
|---|---|---|---|
| Gemara — Avoda Zara | 28b · 37% | 96 amudim | 2026-11-28 |
| Neviim | Yirmiyahu 44 · 67% | 123 perakim | 2026-12-25 |
| Ketuvim | Tehilim 16 · 4% | 346 perakim | 2027-08-05 |
| Mishna | Shabbat 1 · 14% | 449 perakim | 2027-11-16 |

### 9.4 Alignment

Rambam ↔ Gemara ↔ Shulchan Aruch, both resolutions, with `inferred` edges visibly distinguished from `direct` ones.

### 9.5 Chavrusas

Per person: tracks, staleness ("Nesher — 3 weeks"), full session log with notes.

### 9.6 Pace Explorer — read-only

Set a horizon (1 / 3 / 7 / 18 years) and see the required daily rate per corpus, or set a rate and see the horizon. Explicitly aspirational and disconnected from the live plan.

Notable: **Chumash (378), Neviim (380) and Ketuvim (362) are already annual cycles at one a day.** A yearly Mishneh Torah is 2.86 perakim/day — essentially the classic Rambam Yomi 3-perakim cycle.

| Corpus | Unit | Total | Per day for 1 year | Years at 1/day |
|---|---|---:|---:|---:|
| Chumash | aliyot | 378 | 1.04 | 1.0 |
| Neviim | perakim | 380 | 1.04 | 1.0 |
| Ketuvim | perakim | 362 | 0.99 | 1.0 |
| Tanach | perakim | 929 | 2.55 | 2.5 |
| Mishnah | perakim | 525 | 1.44 | 1.4 |
| Talmud Bavli | amudim | 5,349 | 14.65 | 14.7 |
| Talmud Bavli | daf | 2,711 | 7.43 | 7.4 |
| Mishneh Torah | perakim | 1,006 | 2.76 | 2.8 |
| Mishneh Torah | halachos | 15,143 | 41.49 | 41.5 |
| Shulchan Aruch | simanim | 1,705 | 4.67 | 4.7 |
| Shulchan Aruch | seifim | 13,409 | 36.74 | 36.7 |
| Likutei Moharan | torot | 411 | 1.13 | 1.1 |
| Sha'arei Teshuvah | osiyos | 339 | 0.93 | 0.9 |
| Tanya | perakim | 118 | 0.32 | 0.3 |
| Bereshit Rabbah | perakim | 100 | 0.27 | 0.3 |
| Chovot HaLevavot | perakim | 93 | 0.25 | 0.3 |
| Shemirat HaLashon | perakim | 86 | 0.24 | 0.2 |
| Orchot Tzadikim | shearim | 28 | 0.08 | 0.1 |
| Mesillat Yesharim | perakim | 26 | 0.07 | 0.1 |

### 9.7 Stats

Advance heatmap, per-track pace, streaks.

### 9.8 Tags

CRUD screen: create, rename, recolour, delete. Deleting a tag removes the association, never the track.

---

## 10. Design language

Adapted from the sibling TV app, whose vertical "route rail" is the idea worth carrying over — progress as the structure of the page rather than a bar in a corner, with the node on the rail *being* the control.

- **Dark, hairline construction.** Structure drawn in `rgba(255,255,255,.07)` borders and 1px rules. Real shadows only on overlays.
- **Type:** a display face for headings, a text face for body, **monospace with `tabular-nums` for every number** — ordinals, debts, percentages, dates.
- **Hebrew primary, transliteration secondary.** `מסכת עבודה זרה כ״ח ע״ב` as headline, `Avoda Zara 28b` beneath, with proper RTL handling (`direction: rtl; unicode-bidi: isolate`).

### 10.1 Typefaces — decided

| Role | Face | Notes |
|---|---|---|
| Hebrew | **David Libre** 400/500/700 | Ismar David, 1954. Calligraphic contrast. |
| Latin display + body | **Spectral** | shares David's contrast character |
| Numbers, refs, eyebrows | **IBM Plex Mono**, `tabular-nums` | every countable value |

Two consequences of choosing David Libre, both required rather than optional:

1. **It runs optically small.** Hebrew needs its own size step roughly 10% above the Latin at the same nominal size — a shared type scale renders the Hebrew visibly undersized.
2. **Its thin strokes drop out at small sizes.** Row headlines use weight **500**, not 400. Google Fonts ships 400/500/700 only.

### 10.2 Hebrew text handling — non-negotiable

**Never hand-encode Hebrew.** `label_he` is taken verbatim from Sefaria's `heRef` and stored as UTF-8. No numeric character references, no transliteration of codepoints anywhere in the pipeline.

**Codepoint assertion in the catalog tests:** every `label_he` must contain only U+0590–U+05FF plus a known separator set (space, comma, colon, period, hyphen, em dash, parentheses, digits). This originates from a real defect — a hand-written `&#1204;` (Cyrillic Che) and `&#1651;` (Arabic alef) were silently substituted for gershayim and geresh, corrupting four of five sample rows while looking correct in a diff.
- **Accent per category** — Daily / Shabbat / Chavrusa each get one, plus per-tag colours.
- **Optimistic updates with toasts**, as TV does.
- **`prefers-reduced-motion`** collapses all animation.

Deliberately *not* inherited from TV: `.xlsx` persistence, absent Docker, absent frontend tests, absent coverage config.

---

## 11. Infrastructure

Per the global standards.

| Layer | Choice |
|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0 async + asyncpg |
| DB | PostgreSQL 16 |
| Package mgmt | uv |
| Lint | ruff, line-length 120, `["E","F","I","N","UP","ANN","S"]` |
| Tests | pytest + pytest-asyncio + pytest-cov, `asyncio_mode = "auto"` |
| Frontend | React 18, TypeScript strict, Vite, pnpm, Redux Toolkit |
| Frontend tests | Vitest + React Testing Library |
| Containers | Docker + compose, healthchecks, `depends_on: condition: service_healthy` |
| Launcher | `run_torah_sidra.sh` + `.bat`, full `[k]/[q]/[v]/[r]` loop |
| CI | GitLab CI (private project): lint → sast → test → coverage gate → build → docker-build, JUnit XML on every test job |

### 11.1 Ports — allocated

Checked against `PORT_ASSIGNMENTS.md` and against live listeners on 2026-08-24. All three are free in both.

| Service | Host port | Range | Note |
|---|---|---|---|
| Frontend (Vite) | **5285** | `5174-5290` | adjacent to `Personal/TV` at 5284 |
| Backend (FastAPI/uvicorn) | **8285** | `8220-8314` | matching last digits, per registry convention |
| Postgres (containerized) | **5524** | `5433`, `5520-5591` | never `5432`, the sole shared listener |

**No Redis.** Nothing in this design caches or uses pub/sub, and a single-user local app does not earn a second stateful service. No Redis port is reserved.

Both app ports bind `127.0.0.1` only; Vite proxies `/api` to the backend, as TV does.

The registry entry under a `Personal/Torah_Learning_Sidra` heading is written **when the project is scaffolded in P1**, since the registry documents real file paths and launcher defaults.

---

## 12. Portability

```
sidra_db seed       rebuild the catalog from the committed snapshot (offline, deterministic)
sidra_db refresh    re-crawl Sefaria, write a NEW snapshot (deliberate, never on boot)
sidra_db export     write the ledger — positions, advances, notes, chavrusas, tags — to one JSON
sidra_db import     restore that JSON onto any machine
```

The launcher auto-runs `seed` when it finds the catalog empty. Moving machines is: clone → run launcher → `sidra_db import your-backup.json`.

**Superseded 2026-08-25.** An earlier draft had the app write `Torah Sidra.md` and a JSON state file into the Obsidian vault on every advance. That was built and then removed: the app replaces the note, so mirroring it back was circular. `sidra_db export` already writes the same ledger to `backend/data/ledger.json`.

**The open consequence:** the app is desktop-only and locally-hosted, so there is now no way to read the sidra away from that machine. If that matters, the answer is a read-only view reachable from a phone, not a markdown file.

---

## 13. Testing

Coverage target 100%, gated in CI. The derivation layer is where this earns its keep — every function has a knowable right answer.

**Reference tests, drawn from real data:**

- `Avodah Zarah 28b → 38b == 20 amudim` — reproduces Amram's own "20 days behind"
- `Jeremiah 44 → 47 == 3 perakim` — reproduces "3 days behind"
- Seder Zeraim totals **75** perakim, so Mishna Shabbat 1:1 is ordinal **76**
- Neviim totals **380**; Ketuvim **362**; Mishnah **525**
- Avodah Zarah shape length is **152** slots with indices 0–1 empty → **150** learnable amudim
- Tamid's first non-empty slot is index **51** → 25b
- Every one of the 19 seed refs resolves against a recorded Sefaria fixture
- Banking: +3 units on a 1/day track yields `2 days ahead`, and two missed days return it to zero
- A combined-parsha week yields 14 aliyot across 7 days
- A `starts_on` track accrues zero debt before its start date

**No mocking of the schedule maths.** Sefaria responses are recorded fixtures; the arithmetic runs for real.

---

## 14. Open items — all closed

1. ~~**Port allocation**~~ — **RESOLVED 2026-08-24.** Frontend `5285`, backend `8285`, Postgres `5524`, no Redis. See §11.1. Registry entry written at scaffold time.
2. ~~**Hebrew typeface pairing**~~ — **RESOLVED 2026-08-24.** David Libre + Spectral + IBM Plex Mono. See §10.1–10.2.
3. ~~**Bulk links CSV**~~ — **RESOLVED 2026-08-24.** 17 shards, ~656 MB, 118,805 Ein Mishpat edges extracted in 49s, round-trips verified against the live API. See §7.7. Per-segment crawling is no longer needed.
4. ~~**Alt-struct title resolution**~~ — **RESOLVED 2026-08-24.** Always `/api/index/` + `alts`; `alt_structs` never resolves titles. See §7.8.
5. ~~**Mesillat Yesharim recension**~~ — **CLOSED 2026-08-24.** No action needed: the UI asserts no edition. 26 perakim in the standard arrangement is all the app claims.
6. ~~**Gemara queue seeding**~~ — **RESOLVED 2026-08-24.** Queue seeds with Avodah Zarah only; each transition is proposed from the ranked aggregate and confirmed, never auto-applied. Projection in §8.4.

---

## 15. Phases

**Revised 2026-08-24:** alignment moved from P4 into P1. The Ein Mishpat map extracts in 49 seconds from the bulk export (§7.7), so it is effectively free once the catalog exists — and the catalog is what gives its refs meaning. Deferring it would have meant building the topic-link table twice. Four phases, not five.

| Phase | Deliverable | Gate |
|---|---|---|
| **P1 — Catalog & Alignment** | Ingestion pipeline, snapshot, `sidra_db seed`, ~250 works + ~460 stored units + 118,805 Ein Mishpat edges in Postgres, with `unit_at` resolving the other ~24,900 on demand, aggregate ranking | All 19 seed refs resolve; every §7.4 trap has a passing test; `Deos 5:8 ↔ SA OC 2:6` round-trips; Hilchos Avoda Zara ranks Avodah Zarah first |
| **P2 — Ledger & engine** | Tracks, advances, debt, banking, projections; REST API | The two reference debts (20 amudim / 3 perakim) computed correctly from seed |
| **P3 — UI** | Today, Track rail, Roadmap, Chavrusas, Tags, Alignment screen | Two-marker rail renders 5,349 nodes without jank; confidence shown as a distribution |
| **P4 — Extras** | Pace Explorer, Stats, JSON export | Export/import round-trips onto a clean machine |

Every gate additionally requires SAST green with zero HIGH findings, 100% coverage, and `docs/status.md` + `docs/versions.md` updated.

---

## 16. Security

Single-user and local, but the standards still apply.

| Boundary | Injection classes | Defence |
|---|---|---|
| Sefaria / Hebcal HTTP responses | deserialization, SSRF | Pydantic validation on every decoded payload; host allowlist; no input-derived URLs |
| Advance notes, tag names | XSS | React escaping; no `dangerouslySetInnerHTML` |
| Ref strings from the catalog | SQL | SQLAlchemy bound parameters only; no string-built SQL |
| Import JSON | deserialization | strict Pydantic model, size cap, no pickle |

SAST: Semgrep + `pip-audit` + `pnpm audit` + gitleaks in a `sast` stage, Trivy in `docker-build`.

---

## 17. Sources

All API findings were verified live on 2026-08-24 against `https://www.sefaria.org`. Structural counts come from `/api/shape/`; parsha data from `/api/calendars` and `alts.Parasha`; alignment from `/api/links/` filtered to `type == "ein mishpat / ner mitsvah"`. Hebrew calendar policy from `https://www.hebcal.com/home/developer-apis`.
