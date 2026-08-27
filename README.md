# Torah Learning Sidra

A tracker for twenty concurrent lines of Torah learning — one that knows what comes next, how far behind you are, and the calendar date each sefer finishes.

It replaces a hand-edited Obsidian note that had three problems: it needed updating by hand after every session, it did not know what came next, and it had no future — it could not say when Avoda Zara finishes, how far behind you are, or how Shulchan Aruch is even ordered.

Single-user, desktop, locally hosted. No auth, no cloud.

**Status: complete.** All four phases shipped, plus backwards correction and the Maintenance
screen. 950 offline backend tests and 416 frontend tests, both at 100% coverage, and 78 live tests
green against the real Sefaria and Hebcal APIs.

---

## The idea

**The tracks are debt ledgers, not checklists.**

Every daily track has a fixed rate of one unit a day. The *schedule* advances on the calendar whether or not learning happened; the *actual* position advances only when it did. The gap between them is a debt in units, paid down by doubling up.

```
scheduled = anchor_ordinal + rate × days_elapsed
debt      = scheduled − actual        negative debt = credit, and it banks
```

As of 24 August 2026 the model reproduces the real reckoning exactly:

| Track | Actual | Scheduled | Debt |
|---|---|---|---|
| Gemara | Avoda Zara 28b | 38b | **20 amudim** |
| Neviim | Yirmiyahu 44 | 47 | **3 perakim** |

Because the rate is fixed and the catalog complete, every future date is *derivable* rather than estimated — the app names the calendar date Avoda Zara ends, and shows it sliding by one day for each day fallen behind.

---

## What it tracks

**Daily** — one unit a day each: Chumash (an aliyah), Neviim (a perek), Ketuvim (a perek), Mishna (a perek), Gemara (an amud), Shulchan Aruch (a siman).

**Shabbat** — one unit a week each: Chovot HaLevavot, Orchot Tzadikim, Mesilat Yesharim, Shmirat HaLashon, Likutey Moharan, Likutei Sichot, Tanya, The Midrash Says, Covenant & Conversation.

**Chavrusa** — no fixed rate, sorted by staleness: Mishneh Torah with two chavrusas, Gemara Brachot, Bereishit Rabbah, Shaarei Teshuva.

Categories say *where* a track lives; **tags** cut across them, so Chumash in Daily and the three parsha seforim in Shabbat can share a `parsha` tag.

---

## Two ideas worth knowing

**Units are derived, not stored.** A `Work` holds Sefaria's own shape array; `unit_at(work, seq)` computes the address, the labels and the ref on demand. Avodah Zarah is one database row and 152 integers, not 150 rows. Only ~460 units are stored — aliyot, parshiyos and named gates, which carry data that cannot be derived.

**Alignment comes from Ein Mishpat.** Sefaria has digitised *Ein Mishpat Ner Mitzvah* — the classical marginal apparatus mapping every halachic sugya to Rambam, Semag, Tur and Shulchan Aruch — as a link type. 118,805 edges extract from the bulk export in about 50 seconds, and they drive the Gemara queue: learning Hilchos Avoda Zara with a chavrusa, the map ranks Avodah Zarah first at 42.5% and Sanhedrin second at 27.2%.

---

## Phases

| Phase | Delivers |
|---|---|
| **P1a** | Foundation — address primitives, `unit_at`, schema, Sefaria client |
| **P1b** | Ingestion — every corpus in the sidra |
| **P1c** | Alignment & seed — Ein Mishpat, snapshot, `sidra_db` CLI, acceptance gate |
| **P2** | Ledger & engine — tracks, advances, debt, projections, REST API |
| **P3** | UI — Today, the two-marker rail, Roadmap, Chavrusas, Tags |
| **P4** | Extras — Pace Explorer, Stats, Sequence, JSON export/import |
| **After** | Correcting a position or a schedule backwards; the Maintenance screen |

Every phase is done. The two rows after P4 were added because using the app surfaced them: there
was no way to undo a mistyped advance, and no way to run a `sidra-db` verb without a terminal.

---

## Running it

```bash
./run_torah_sidra.sh          # or run_torah_sidra.bat on Windows
```

The launcher brings up the stack and offers `[r]` restart, `[k]` stop, `[q]` stop and remove images, `[v]` full cleanup. Unrecognised input reprints the menu.

PostgreSQL listens on **localhost:5524** with databases `sidra` and `sidra_test`. The frontend is on **5285** and the backend on **8285**.

### The screens

| Screen | Answers |
|---|---|
| **Today** | what to learn now, debt-ordered within Daily / Shabbat / Chavrusa |
| **Track** | the full spine, lit to where you are, ghosted where the schedule is |
| **Roadmap** | when each track finishes at its current pace |
| **Pace** | what a full cycle costs at any rate — deliberately *not* your plan |
| **Stats** | whether the gap is opening or closing, per track and per day |
| **Sequence** | which Gemara the Rambam asks for next, and how much runway is left |
| **Chavrusas** | who you have not seen, longest first |
| **Alignment** | which masechta a hilchos book actually points at, via Ein Mishpat |
| **Tags** | create, rename, delete — a delete removes the label, never the track |
| **Maintenance** | the `sidra-db` verbs that are safe to press: export, verify, rebuild, calendar, re-crawl, and one narrow restore |

### Development

```bash
cd backend
uv sync --all-groups
uv run pytest -m "not live"                                       # the normal suite
uv run pytest -m "not live" --cov=sidra --cov-fail-under=100      # the coverage gate
uv run pytest -m live                                             # deliberate; hits the real API
uv run ruff check . && uv run ruff format --check .
```

```bash
cd frontend
pnpm install
pnpm test                     # the normal suite
pnpm coverage                 # the coverage gate, 100% including branches
pnpm lint && pnpm build       # eslint, then tsc -b + vite build
```

`live`-marked tests hit the real Sefaria API and are excluded from CI. They exist because a fixture can encode the same wrong belief as the code that reads it — only the real API contradicts it.

### CI

`.github/workflows/ci.yml` runs six stages in order, each gating the next: **lint** (ruff check, ruff format, eslint), **sast** (CodeQL for Python and TypeScript, semgrep to the Security tab, pip-audit, pnpm audit, gitleaks), **test** (pytest and vitest, each publishing a JUnit report), **coverage** (100% on both, and the build waits on it), **build**, and **docker-build** with a Trivy scan of each image.

Two rules of the house it follows. Only ERROR-severity semgrep findings fail the run — everything below is uploaded to the Security tab and triaged, and the three rules excluded outright carry their reason both in the workflow and beside the code they are about. And every command it runs is runnable here: `gitleaks.toml` allowlists the generated directories so a workstation scan and CI's fresh clone agree.

`.gitlab-ci.yml` is the same pipeline for GitLab and is kept in step. There is no Dependabot: on a repo this size it opens a burst of pull requests and each one runs all fourteen jobs. Actions are tracked at major tags and updated by hand when something needs it; `pip-audit` and `pnpm audit` are what actually gate a vulnerable dependency, and they run every push.

---

## Documents

| File | Contents |
|---|---|
| `docs/superpowers/specs/2026-08-24-torah-sidra-design.md` | the master design |
| `docs/superpowers/plans/2026-08-24-sidra-p1a-foundation.md` | P1a plan |
| `docs/superpowers/plans/2026-08-24-sidra-p1b-ingestion.md` | P1b plan |
| `docs/superpowers/plans/2026-08-24-sidra-p1c-alignment-and-seed.md` | P1c plan |
| `docs/superpowers/plans/2026-08-25-sidra-p2-ledger.md` | P2 plan |
| `docs/superpowers/plans/2026-08-25-sidra-p3-ui.md` | P3 plan |
| `docs/superpowers/specs/2026-08-27-backwards-correction-design.md` | correcting a position or a schedule |
| `docs/superpowers/plans/2026-08-27-backwards-correction.md` | its implementation plan |
| `docs/superpowers/specs/2026-08-27-maintenance-screen-design.md` | the Maintenance screen and the job model |
| `docs/status.md` | current state |
| `docs/versions.md` | changelog |
| `CLAUDE.md` | AI working agreement |

---

## Attribution

Structural data comes from [Sefaria](https://www.sefaria.org). This project stores refs, counts and titles — never text — and deep-links to Sefaria for the text itself. Sefaria licenses each text version separately.
