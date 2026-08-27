# Torah Learning Sidra — P1a (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the project and prove the three contracts everything else rests on — the resolver that turns an integer position into a Sefaria ref, a database that stores *works* rather than units, and a Sefaria client that survives Sefaria returning HTTP 200 with an error body.

**Architecture:** Units are **derived, not stored** (spec §7.10). A `Work` carries Sefaria's own shape array; `unit_at(work, seq)` computes the address, labels and ref on demand. That replaces ~25,000 rows with one function and collapses nine bespoke ingesters into one generic one. Pure functions first, database second, network third.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 async + asyncpg, PostgreSQL 16, Pydantic v2, httpx, uv, ruff, pytest.

**Spec:** `docs/superpowers/specs/2026-08-24-torah-sidra-design.md` — **read §7.10 before starting.**

**Scope:** Six tasks. Ends with a running Postgres, a green suite, and `unit_at` proven against Amram's real positions. P1b (ingestion) and P1c (Ein Mishpat, snapshot, CLI, acceptance gate) follow once these contracts exist as code.

**On granularity:** each task states its contract, its tests and its acceptance command. It does not spell out every keystroke — the executor runs TDD in the normal order: write the listed tests, watch them fail, implement, watch them pass. A first draft of this plan used 73 micro-steps to deliver 435 lines of production code. That ratio was the format, not the work.

---

## Global Constraints

- **Python 3.13+**, `from __future__ import annotations` in every module.
- **uv** for packages; **ruff** `line-length = 120`, `select = ["E","F","I","N","UP","ANN","S"]`, tests ignore `S101`.
- **Coverage gated at 100% by a dedicated command, never by `addopts`** — `--cov-fail-under` in `addopts` makes every focused run fail on the untouched rest of the package.
- **SQLAlchemy 2.0** async, `Mapped[]`/`mapped_column()` only. **No mocking of the database** — tests use the real compose Postgres.
- **httpx** for all HTTP. **No test touches the network** except the one explicitly marked `live`.
- **Full type annotations. No `Any` in signatures.** No bare `except`. One concept per file.
- **Ports:** frontend `5285`, backend `8285`, Postgres host `5524` → container `5432`. **No Redis.** Never bind host `5432`.
- **Hebrew is never hand-encoded.** Sefaria's `heTitle`/`heRef` is stored verbatim as UTF-8; computed Hebrew labels come from the gematria function in Task 2.
- **Git is Amram's.** No task runs a state-changing git command. Each ends with a commit point: files changed plus a suggested message for him to run.

---

## Measured Facts

Measured against the live Sefaria API on 2026-08-24. Tests use them as fixtures; **do not substitute recalled values.**

| Fact | Value |
|---|---|
| Avodah Zarah | 152 shape slots, indices 0–1 empty → **150 real amudim**, 2a…76b |
| `amud_label_to_index` | `"28b"` → **55**, `"38b"` → **75** — difference **20**, Amram's real Gemara debt |
| `amud_index_to_label` | 2→`2a`, 49→`25b`, 55→`28b`, 75→`38b`, 151→`76b` |
| **Tamid** | length 66, first non-empty index **49** = `25b`, last 65 = `33b`, **17** real amudim |
| **Nazir** | length 132, empty indices **[0, 1, 65]**; index 65 = `33b` is a **mid-masechta gap**; 129 real, 2a…66b |
| Bavli | 37 masechtos, 5,471 slots, **5,349 real amudim** |
| The Nazir trap | 5,471 − 121 leading zeros = 5,350 ≠ 5,349. **Count non-empty slots.** |
| Jeremiah | 52 perakim; 44 → 47 = **3**, Amram's other real debt |
| Mishneh Torah, Human Dispositions | `[7,7,3,23,13,10,8]` — 7 perakim, 71 halachos |

---

## File Structure

```
backend/src/sidra/
├── constants.py            SEFARIA_BASE_URL, AMUDIM_PER_DAF, Hebrew block bounds   T1
├── config.py               pydantic-settings, env_prefix SIDRA_                    T1
├── catalog/
│   ├── granularity.py      Granularity StrEnum                                     T2
│   ├── address_scheme.py   AddressScheme: FLAT NESTED DAF_AMUD STORED              T2
│   ├── corpus.py           the canonical corpus_id vocabulary                      T2
│   ├── ref.py              to_ref                                                  T2
│   ├── amud.py             index <-> label                                         T2
│   ├── bavli_amudim.py     real_amudim (counts non-empty slots)                    T2
│   ├── gematria.py         to_gematria (28 -> "כ״ח")                               T2
│   ├── resolve.py          ResolvedUnit, unit_at, unit_count  <-- the core         T3
│   ├── sefaria_error.py    SefariaError                                            T5
│   ├── sefaria_client.py   SefariaClient                                           T5
│   └── shape.py            ShapeNode, parse_shape                                  T5
└── db/
    ├── base.py · engine.py                                                          T4
    └── models/{work,learnable_unit,title_alias,topic_link,snapshot}.py               T4
```

---

# Task 1: Scaffold and infrastructure

**Delivers:** a synced uv environment, the project documents, and a healthy PostgreSQL 16 on host `5524`.

**Files:** `backend/pyproject.toml` · `backend/src/sidra/{__init__,constants,config}.py` · `backend/tests/{__init__,test_constants,test_config}.py` · `.gitignore` · `README.md` · `CLAUDE.md` · `docs/{status,versions}.md` · `docker-compose.yml` · `.env.example` · `backend/Dockerfile` · `backend/.dockerignore` · `backend/docker/init-test-db.sh` · `run_torah_sidra.{sh,bat}`

**Produces:**
- `sidra.constants.SEFARIA_BASE_URL = "https://www.sefaria.org/api"` (no trailing slash), `AMUDIM_PER_DAF = 2`, `HEBREW_BLOCK_START`, `HEBREW_BLOCK_END`
- `sidra.config.Settings(BaseSettings)` — `env_prefix="SIDRA_"`, fields `postgres_host/port/db/user/password`, `sefaria_base_url`, `http_timeout_seconds`; property `database_url`
- `sidra.config.get_settings()` — `lru_cache`d

- [ ] **Step 1: Write `backend/pyproject.toml`**

Two deliberate absences: **no `readme` key** (the Docker build context is `./backend`, so `../README.md` is unreachable and the image build would fail), and **no `--cov-fail-under` in `addopts`** (it would make every focused run in this plan fail on untouched modules).

```toml
[project]
name = "sidra"
version = "0.1.0"
description = "Torah Learning Sidra — Torah-learning progress tracker"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.6.0", "pydantic-settings>=2.6.0",
    "sqlalchemy[asyncio]>=2.0.36", "asyncpg>=0.30.0",
    "httpx>=0.28.0", "pyyaml>=6.0.2", "typer>=0.15.0",
]

[dependency-groups]
dev = ["pytest>=8.3.0", "pytest-asyncio>=0.24.0", "pytest-cov>=6.0.0", "ruff>=0.8.0", "pip-audit>=2.7.3"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sidra"]

[tool.ruff]
line-length = 120
target-version = "py313"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "ANN", "S"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]

[tool.ruff.lint.isort]
known-first-party = ["sidra"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src", "."]
addopts = ["--strict-markers"]
markers = [
    "integration: requires the compose Postgres",
    "live: hits the real Sefaria API",
]

[tool.coverage.run]
source = ["src/sidra"]
branch = true

[tool.coverage.report]
show_missing = true
fail_under = 100
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING:"]
```

Then `cd backend && uv sync --all-groups`.

- [ ] **Step 2: TDD `constants.py` and `config.py`** — 8 tests

`tests/test_constants.py`: `SEFARIA_BASE_URL` equals `"https://www.sefaria.org/api"` and has no trailing slash; `AMUDIM_PER_DAF == 2`; the Hebrew block bounds are `U+0590`/`U+05FF`; alef (`U+05D0`) and gershayim (`U+05F4`) both fall inside them.

`tests/test_config.py`: defaults give `postgres_port == 5524` and `postgres_db == "sidra"`; `SIDRA_POSTGRES_DB` overrides it; `database_url` renders `postgresql+asyncpg://u:p@db:5432/sidra`; `get_settings()` returns the same object twice. Use an `autouse` fixture deleting every `SIDRA_*` var and calling `get_settings.cache_clear()`.

```python
# backend/src/sidra/constants.py
from __future__ import annotations

SEFARIA_BASE_URL = "https://www.sefaria.org/api"
AMUDIM_PER_DAF = 2
HEBREW_BLOCK_START = "֐"
HEBREW_BLOCK_END = "׿"
"""Unicode Hebrew block bounds.

Every Hebrew label must fall inside these plus known separators. The guard exists because
hand-written numeric character references once substituted a Cyrillic Che (U+04B4) for gershayim
and an Arabic alef (U+0673) for geresh — corrupting labels in a way that looked correct in a diff.
"""
```

```python
# backend/src/sidra/config.py
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from sidra.constants import SEFARIA_BASE_URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIDRA_", env_file=".env", extra="ignore")

    postgres_host: str = "localhost"
    postgres_port: int = 5524
    postgres_db: str = "sidra"
    postgres_user: str = "sidra"
    postgres_password: str = "sidra_dev"
    sefaria_base_url: str = SEFARIA_BASE_URL
    http_timeout_seconds: float = 30.0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

**Accept:** `uv run pytest tests/test_constants.py tests/test_config.py -q` → `8 passed`.

- [ ] **Step 3: Write the compose stack**

`docker-compose.yml` — compose v2, **no `version:` key**. `postgres:16-alpine`, `restart: unless-stopped`, `pg_isready` healthcheck (`interval: 5s`, `timeout: 3s`, `retries: 10`), ports `"${SIDRA_POSTGRES_PORT:-5524}:5432"`, named volume `sidra_postgres_data`, and a read-only mount of `./backend/docker/init-test-db.sh` into `/docker-entrypoint-initdb.d/`.

`backend/docker/init-test-db.sh` creates the second database Task 4's fixtures need:

```bash
#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE sidra_test OWNER $POSTGRES_USER;
EOSQL
```

`backend/Dockerfile` — `python:3.13-slim` (**not** alpine; musl breaks scientific Python wheels), uv copied from `ghcr.io/astral-sh/uv:latest`, dependencies installed before source for layer caching. `.env.example` mirrors every `Settings` field with the `SIDRA_` prefix.

**Accept:** `docker compose up -d --build` → `postgres` shows `running (healthy)` within ~15s. `docker compose port postgres 5432` prints `0.0.0.0:5524` — **if it prints 5432, stop**; that is the machine's one shared PostgreSQL listener and must never be bound by a project container. `docker compose exec postgres psql -U sidra -d sidra -c "\l"` lists both `sidra` and `sidra_test`.

- [ ] **Step 4: Write both launchers**

`run_torah_sidra.sh` and `run_torah_sidra.bat`, each printing a banner with the Postgres URL then looping on a single-character prompt:

- `[r]` — `docker compose down` then `up --build -d`, reprint the banner, **return to the prompt**. Must work an unlimited number of times.
- `[k]` — `docker compose down`. Terminal.
- `[q]` — `down --remove-orphans` plus removal of images matching `torah_learning_sidra`. Terminal.
- `[v]` — `down --volumes --remove-orphans` plus image removal. Terminal.
- Anything else — reprint the menu and return to the prompt. **Never exit on unrecognised input.**

The `.bat` uses `goto` labels for the loop, checks `errorlevel`, and `pause`s before final exit.

**Accept:** run the `.sh`, press `r` three times and confirm the stack returns healthy each time, press `x` and confirm the menu reprints without exiting, then press `k`.

- [ ] **Step 5: Write the project documents**

`.gitignore` — OS junk, `.idea/`, `.vscode/`, `.claude/`, `.env*` except `.env.example`, `__pycache__/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `.coverage`, `coverage.xml`, `junit-*.xml`, `node_modules/`, `docker-compose.override.yml`, `postgres-data/`.

`docs/versions.md` opens at `## v0.1.0 — unreleased` listing P1a's deliverables. `docs/status.md` records the current phase, that nothing is built yet, and that P1b/P1c are deliberately unplanned pending these contracts.

`README.md` — what the project is, the four phases, how to run it. `CLAUDE.md` — opens with the mandatory-re-read directive, wraps sections in semantic XML tags (`<non_negotiable>`, `<tech_stack>`, `<coding_standards>`, `<containerization>`, `<security>`, `<domain_facts>`), names the spec as the master document, and reproduces the Measured Facts table verbatim under `<domain_facts>`.

- [ ] **Commit point** — the files above.
  Suggested message (for Amram to run himself — do not run git):
  `feat(scaffold): project skeleton, settings, compose stack and launchers`

---

# Task 2: The address primitives

**Delivers:** six pure, dependency-free modules that between them turn an integer into a Sefaria address. This is the arithmetic the whole app rests on.

**Files:** `backend/src/sidra/catalog/{__init__,granularity,address_scheme,corpus,ref,amud,bavli_amudim,gematria}.py` · `backend/tests/catalog/test_{granularity,address_scheme,ref,amud,bavli_amudim,gematria}.py`

**Produces:**
- `Granularity(StrEnum)` — `DAF_AMUD ALIYAH PARSHA PEREK MISHNAH HALAKHAH SIMAN SEIF OS GATE TORAH_SECTION PARAGRAPH`, each value the lowercased member name
- `AddressScheme(StrEnum)` — `FLAT NESTED DAF_AMUD STORED`
- `corpus.CORPUS_IDS: frozenset[str]` — the canonical vocabulary, declared once so no ingester can invent a variant: `torah` `neviim` `ketuvim` `mishnah` `bavli` `mishneh_torah` `shulchan_aruch` `mussar` `chassidus` `midrash` `parsha_weekly`
- `to_ref(ref_title: str, addr: Sequence[str]) -> str`
- `amud_index_to_label(index: int) -> str` / `amud_label_to_index(label: str) -> int`
- `real_amudim(chapters: Sequence[int]) -> list[str]`
- `to_gematria(number: int) -> str`

- [ ] **Step 1: TDD the three vocabularies**

Every member's value equals its lowercased name; the twelve `Granularity` members and four `AddressScheme` members are exactly as listed; members compare equal to their string value; `CORPUS_IDS` holds exactly the eleven ids above.

- [ ] **Step 2: TDD `ref.py`**

**Contract:** components join with `:`, separated from the title by one space. An **empty `addr` returns the bare `ref_title`** — that is the parsha case. Components **may contain `:`**, because aliyah pointers carry verse ranges like `26:16-26:19`; rejecting `:` would make every aliyah unbuildable. A non-`str` component raises `TypeError`.

Parametrize over all twelve unit types:

```python
("Avodah Zarah", ["38b"],                          "Avodah Zarah 38b"),
("Jeremiah", ["44"],                               "Jeremiah 44"),
("Psalms", ["16"],                                 "Psalms 16"),
("Mishnah Shabbat", ["1","1"],                     "Mishnah Shabbat 1:1"),
("Mishneh Torah, Human Dispositions", ["5","8"],   "Mishneh Torah, Human Dispositions 5:8"),
("Shulchan Arukh, Orach Chayim", ["1"],            "Shulchan Arukh, Orach Chayim 1"),
("Shulchan Arukh, Yoreh De'ah", ["87","1"],        "Shulchan Arukh, Yoreh De'ah 87:1"),
("Bereshit Rabbah", ["3","5"],                     "Bereshit Rabbah 3:5"),
("Sha'arei Teshuvah", ["1","29"],                  "Sha'arei Teshuvah 1:29"),
("Orchot Tzadikim", ["11","1"],                    "Orchot Tzadikim 11:1"),
("Likutei Moharan, Part II", ["1","1"],            "Likutei Moharan, Part II 1:1"),
("Tanya, Part I; Likkutei Amarim", ["1","1"],      "Tanya, Part I; Likkutei Amarim 1:1"),
```

Plus four standalone tests: empty addr returns the bare title; a component containing `:` survives; the literal semicolon in Tanya's title survives; `to_ref("Jeremiah", [44])` raises `TypeError`.

```python
def to_ref(ref_title: str, addr: Sequence[str]) -> str:
    for component in addr:
        if not isinstance(component, str):
            raise TypeError(f"addr components must be str, got {type(component).__name__}")
    return f"{ref_title} {':'.join(addr)}" if addr else ref_title
```

- [ ] **Step 3: TDD `amud.py`**

**This carries the project's most load-bearing arithmetic.** Parametrize both directions over the measured pairs `(2,"2a") (3,"2b") (49,"25b") (55,"28b") (75,"38b") (151,"76b")`; assert `amud_label_to_index("38b") - amud_label_to_index("28b") == 20` — Amram's real Gemara debt; assert round-trip identity for every index in `range(2, 152)`; assert a malformed label raises `ValueError`.

```python
def amud_index_to_label(index: int) -> str:
    if index < 0:
        raise ValueError(f"amud index must be non-negative, got {index}")
    return f"{index // AMUDIM_PER_DAF + 1}{'b' if index % AMUDIM_PER_DAF else 'a'}"


def amud_label_to_index(label: str) -> int:
    match = re.fullmatch(r"(?P<daf>\d+)(?P<side>[ab])", label)
    if match is None:
        raise ValueError(f"not a daf label: {label!r}")
    daf = int(match.group("daf"))
    if daf < 1:
        raise ValueError(f"daf must be at least 1, got {daf}")
    return (daf - 1) * AMUDIM_PER_DAF + (1 if match.group("side") == "b" else 0)
```

- [ ] **Step 4: TDD `bavli_amudim.py`**

Build fixtures with a helper `_shape(length, empty_indices)` returning `[0 if i in empty else 7 for i in range(length)]`, then:

- `AVODAH_ZARAH = _shape(152, {0, 1})` → 150 labels, first `"2a"`, last `"76b"`
- `TAMID = _shape(66, set(range(49)))` → 17 labels, first `"25b"`, last `"33b"`
- `NAZIR = _shape(132, {0, 1, 65})` → 129 labels, first `"2a"`, last `"66b"`, **`"33b"` absent** while `"33a"` and `"34a"` are present
- **A test proving the naive formula wrong:** `len(NAZIR) - leading_zeros == 130` while `len(real_amudim(NAZIR)) == 129`
- Empty and all-empty shapes both yield `[]`

```python
def real_amudim(chapters: Sequence[int]) -> list[str]:
    """Labels of every amud carrying text, in shape order.

    Counts non-empty slots. Deliberately not ``len(chapters) - leading_zeros``: Nazir has an empty
    slot at index 65 (33b) in the middle of a masechta running 2a..66b, so the subtraction
    overcounts and the Bavli total comes out 5,350 instead of the measured 5,349.
    """
    return [amud_index_to_label(i) for i, segments in enumerate(chapters) if segments]
```

- [ ] **Step 5: TDD `gematria.py`**

Needed because Hebrew labels are now computed rather than fetched per unit.

Cases: `1→"א"`, `15→"ט״ו"`, `16→"ט״ז"`, `28→"כ״ח"`, `38→"ל״ח"`, `44→"מ״ד"`, `100→"ק"`, `400→"ת"`, `500→"ת״ק"`, `999→"תתקצ״ט"`. A single letter takes no gershayim; multi-letter values take `״` before the final letter. `to_gematria(0)` and negatives raise `ValueError`.

**The 15 and 16 cases are the substantive ones** — they are written `ט״ו` and `ט״ז` rather than the arithmetic `י״ה`/`י״ו`, to avoid spelling a Divine name. Write those two tests first; they are the reason this module cannot be a one-liner.

**Accept:** `uv run pytest tests/catalog -q` — every listed test passes.

- [ ] **Commit point** — the six modules and their tests.
  Suggested message: `feat(catalog): address primitives — refs, amud arithmetic, gematria`

---

# Task 3: `unit_at` — the resolver that replaces 25,000 rows

**Delivers:** the single function turning `(work, seq)` into a full unit. This is the heart of the derived-catalog design.

**Files:** `backend/src/sidra/catalog/resolve.py` · `backend/tests/catalog/test_resolve.py`

**Produces:**

```python
@dataclass(frozen=True, slots=True)
class ResolvedUnit:
    seq: int
    addr: tuple[str, ...]
    ref: str
    label_en: str
    label_he: str
    child_count: int | None


def unit_count(scheme: AddressScheme, shape: Sequence[int]) -> int: ...


def unit_at(
    ref_title: str,
    scheme: AddressScheme,
    shape: Sequence[int],
    seq: int,
    labels: Sequence[str] | None = None,
) -> ResolvedUnit: ...
```

**Contract by scheme** (`seq` is 1-based throughout):

| Scheme | `seq` maps to | `addr` | `child_count` | `unit_count` |
|---|---|---|---|---|
| `FLAT` | the `seq`-th entry of `shape` | `(str(seq),)` | `shape[seq-1]` | `len(shape)` |
| `NESTED` | cumulative sum over `shape` | `(str(chapter), str(offset))` | `None` | `sum(shape)` |
| `DAF_AMUD` | the `seq`-th **non-empty** slot | `(label,)` | that slot's value | count of non-empty |

> **`seq` is not the shape index.** `seq` counts real units from 1; the shape index counts array
> slots from 0, including empty ones. For Avodah Zarah they differ by one (two leading empties);
> for Tamid by 49; for Nazir the offset **changes mid-masechta** at its index-65 gap. Always go
> through `real_amudim`, never arithmetic on the index.
| `STORED` | — | raises `ValueError` | — | raises `ValueError` |

`label_en` is `addr` joined with `:`. `label_he` is each component's gematria joined with `:`; for `DAF_AMUD` it is `{gematria(daf)} ע״{alef|beis}` — so seq 54 of Avodah Zarah gives `כ״ח ע״ב`. When `labels` is supplied it overrides `label_en` (that is how Orchot Tzadikim's shaar names attach).

- [ ] **Step 1: Write the failing tests against real measured shapes**

- **FLAT / Jeremiah** — `shape` is the real 52-entry pasuk-count array. `seq=44` → `addr=("44",)`, `ref="Jeremiah 44"`, `label_he="מ״ד"`, `child_count == shape[43]`.
- **DAF_AMUD / Avodah Zarah** — `seq=1` → `"2a"`; **`seq=54` → `addr=("28b",)`, `ref="Avodah Zarah 28b"`, `label_he="כ״ח ע״ב"`**; `seq=150` → `"76b"`.
  Derive both seqs in the test as `real_amudim(shape).index("28b") + 1` rather than hard-coding — `seq` is the 1-based position among **non-empty** slots, which is **not** the shape index. For Avodah Zarah the two differ by one, because indices 0 and 1 are empty.
- **DAF_AMUD / Tamid** — `seq=1` → `"25b"`. **DAF_AMUD / Nazir** — no `seq` resolves to `"33b"`; assert by resolving all 129 and checking membership.
- **NESTED / Mishneh Torah, Human Dispositions** — `shape=[7,7,3,23,13,10,8]`. Assert `seq=1` → `("1","1")`; `seq=71` → `("7","8")` (the last halacha); and **compute the seq for `("5","8")` in the test from the array** — `sum(shape[:4]) + 8` — rather than hard-coding it, then assert `unit_at(...).ref == "Mishneh Torah, Human Dispositions 5:8"`. Hard-coding a cumulative index by hand is exactly the error class that produced a wrong Tamid constant earlier.
- **Both measured debts, end to end:** on Avodah Zarah, `unit_at(seq=74).addr == ("38b",)` and `74 - 54 == 20`. On Jeremiah, `unit_at(seq=47).ref == "Jeremiah 47"` and `47 - 44 == 3`. Compute both Avodah Zarah seqs from `real_amudim`; assert only that their **difference** is 20, so the test cannot be satisfied by two wrong numbers.
- **Bounds:** `seq=0` and `seq=unit_count(...)+1` both raise `ValueError`.
- **`STORED`** raises `ValueError` naming the scheme.
- **`labels` override:** with `labels=["ON HUMILITY", ...]`, `label_en` is the supplied name while `addr` is unchanged.
- **`unit_count`** returns 52 for the Jeremiah shape, 150 for Avodah Zarah, 17 for Tamid, 129 for Nazir, 71 for Human Dispositions.

- [ ] **Step 2: Implement and go green**

**Accept:** `uv run pytest tests/catalog/test_resolve.py -q` passes, and these two hold:

```python
unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AZ_SHAPE, 54).ref  # "Avodah Zarah 28b"
unit_at("Avodah Zarah", AddressScheme.DAF_AMUD, AZ_SHAPE, 74).ref  # "Avodah Zarah 38b"
```

- [ ] **Commit point** — `resolve.py` and its tests.
  Suggested message: `feat(catalog): unit_at resolver — derive units from work shape arrays`

---

# Task 4: Database — works, not units

**Delivers:** the schema, the async engine, and a real-Postgres test fixture.

**Files:** `backend/src/sidra/db/{__init__,base,engine}.py` · `backend/src/sidra/db/models/{__init__,work,learnable_unit,title_alias,topic_link,snapshot}.py` · `backend/tests/conftest.py` · `backend/tests/db/test_{engine,models,resolver_integration}.py`

**Produces:** `Base(DeclarativeBase)`, `create_engine(url) -> AsyncEngine`, `create_session_factory(engine) -> async_sessionmaker[AsyncSession]`, five models, and fixtures `db_engine` (session-scoped, `create_all`/`drop_all`) and `db_session` (function-scoped, rolled back per test).

**`Work` is the important one** — it now carries the shape:

```python
class Work(Base):
    __tablename__ = "work"
    __table_args__ = (
        UniqueConstraint("corpus_id", "corpus_seq", name="uq_work_corpus_position"),
        Index("ix_work_ref_title", "ref_title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corpus_id: Mapped[str] = mapped_column(String(32), nullable=False)
    corpus_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    index_title: Mapped[str | None] = mapped_column(String(256))
    ref_title: Mapped[str] = mapped_column(String(256), nullable=False)
    title_he: Mapped[str] = mapped_column(String(256), nullable=False)
    granularity: Mapped[Granularity] = mapped_column(SAEnum(Granularity, name="granularity"), nullable=False)
    address_scheme: Mapped[AddressScheme] = mapped_column(
        SAEnum(AddressScheme, name="address_scheme"), nullable=False
    )
    shape: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    labels: Mapped[list[str] | None] = mapped_column(JSONB)
    unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshot.id"), nullable=False)
```

`LearnableUnit` survives but is now **sparse** — only `STORED`-scheme works populate it (aliyot, parshiyos, named gates: ~460 rows total). Columns: `id`, `work_id`, `seq`, `parent_id`, `ref_title`, `addr` (JSONB), `addr_types` (JSONB), `label_en`, `label_he`, `resolved_ref`, `resolved_he_ref`, `is_range`, `is_spanning`, `ordinal`, `child_count`, `source`, `snapshot_id`. Unique on `(work_id, seq)`, indexed on `ref_title`.

`TitleAlias(work_id, alias, lang, source)` indexed on `alias`.
`TopicLink(from_ref, to_ref, from_category, to_category, kind, anchor_group, confidence, snapshot_id)` indexed on `from_ref`, `to_ref`, `anchor_group`.
`Snapshot(created_at, sefaria_version, unit_count, edge_count)` — UUID primary key, so **no sequence handling anywhere**.

**`addr_types` uses Sefaria's own vocabulary** — `"Perek"`, `"Talmud"`, `"Halakhah"`, `"Integer"`, `"Aliyah"`, `"Mishnah"` — **never `Granularity` members.** `Granularity` says what a unit *is*; `addr_types` says how Sefaria *addresses* it. Conflating the two was the most common drift in an earlier draft.

- [ ] **Step 1: TDD base and engine** — `Base` exposes `metadata` and `registry`; `create_session_factory(...).class_ is AsyncSession`; an `@pytest.mark.integration` test runs `SELECT 1` through `db_session`.

- [ ] **Step 2: Write `backend/tests/conftest.py`**

`db_engine` is session-scoped, connects to database **`sidra_test`** (created by Task 1 Step 3's init script), runs `drop_all` then `create_all` on entry and `drop_all` on exit. `db_session` opens a connection, begins a transaction, yields a session bound to it, and **always rolls back**, so tests never see each other's rows.

If it errors with `database "sidra_test" does not exist`, the init script did not run — `docker compose down -v && docker compose up -d`.

- [ ] **Step 3: TDD the five models** — one round-trip integration test each: insert, flush, select back, assert a distinguishing field. For `Work`, assert `shape` and `labels` survive JSONB round-tripping intact. For `LearnableUnit`, assert `addr == ["26:16-26:19"]` and that `label_he` returns the exact Hebrew stored. For `TopicLink`, assert `kind` and `confidence`.

- [ ] **Step 4: Prove the resolver against a persisted work**

`tests/db/test_resolver_integration.py` — store Avodah Zarah as a `Work` with its real 152-entry shape and `address_scheme=DAF_AMUD`, read it back in a fresh query, and assert:

```python
unit_at(work.ref_title, work.address_scheme, work.shape, 54).ref == "Avodah Zarah 28b"
unit_at(work.ref_title, work.address_scheme, work.shape, 74).ref == "Avodah Zarah 38b"
work.unit_count == 150
```

**This is the test that proves the derived catalog end to end** — one database row standing in for 150.

**Accept:** `uv run pytest tests/db -q` passes with the compose stack up.

- [ ] **Commit point** — db package, models, conftest, tests.
  Suggested message: `feat(db): schema storing works and shape arrays rather than units`

---

# Task 5: Sefaria client and shape parsing

**Delivers:** the only code that talks to Sefaria, and the parser turning its shape responses into `Work` inputs.

**Files:** `backend/src/sidra/catalog/{sefaria_error,sefaria_client,shape}.py` · `backend/tests/catalog/test_{sefaria_client,shape}.py`

**Produces:**
- `SefariaError(message: str, *, url: str)`
- `SefariaClient(client: httpx.AsyncClient, base_url: str)` with `shape(path)`, `index(title)`, `raw_index(title)`, `text(ref)`
- `ShapeNode(title, title_he, section, length, chapters, is_complex)` and `parse_shape(payload) -> list[ShapeNode]`

**The critical behaviour:** Sefaria returns **HTTP 200 with an `{"error": …}` body.** Status codes lie. Every response is inspected regardless of status.

**`shape(path)` takes an unprefixed path** — callers pass `"Tanakh/Prophets"` and the client adds `shape/`. `raw_index` exists because `schema.titles`, the alias source used in P1b, lives only on `/api/v2/raw/index/`.

**No test touches the network** — all use `httpx.MockTransport` with inline payloads.

- [ ] **Step 1: TDD the client** — 7 tests

`shape` returns the parsed body; the request path is exactly `/api/shape/Tanakh/Prophets` with no double prefix; **a 200 carrying an `error` key raises `SefariaError`**; a clean 200 does not; a real 500 raises with `"HTTP 500"`; `raw_index` hits `/api/v2/raw/index/…`; the raised error carries the failing URL.

```python
async def _get(self, path: str) -> Any:
    url = f"{self._base_url}/{path}"
    response = await self._client.get(url)
    if response.status_code != httpx.codes.OK:
        raise SefariaError(f"HTTP {response.status_code} from Sefaria", url=url)
    payload = response.json()
    if isinstance(payload, dict) and "error" in payload:
        raise SefariaError(str(payload["error"]), url=url)
    return payload
```

- [ ] **Step 2: TDD `parse_shape`** — 6 tests

`chapters` is polymorphic: `int | list[int] | list[dict]`. A simple node parses to a `ShapeNode`; a bare-int `chapters` becomes `[24]`; **a node with `title: None` and `isComplex: True` parses without raising** — that is Shulchan Arukh, Even HaEzer; dict entries reduce to their `length`; a missing `chapters` yields `[]`; a non-list payload raises `TypeError`.

**Titles are stripped** — Orchot Tzadikim's gate 11 `heTitle` carries a trailing newline.

**Accept:** `uv run pytest tests/catalog -q` passes.

- [ ] **Commit point** — the three modules and their tests.
  Suggested message: `feat(catalog): Sefaria client with error-body detection and shape parsing`

---

# Task 6: Verify against the real API, then gate

**Delivers:** proof that the fixtures match reality, and a green 100%-coverage run.

**Files:** `backend/tests/test_live_sefaria.py` (marked `live`, excluded by default) · updates to `docs/{status,versions}.md`

- [ ] **Step 1: Write the `live`-marked verification test**

It fetches four real shapes and asserts the Measured Facts **against the live API, not against the fixtures**:

| Fetch | Assert |
|---|---|
| `shape("Talmud/Bavli")` | 37 masechtos; total non-empty slots across all = **5,349** |
| `shape("Tamid")` | first non-empty index **49**; `real_amudim(...)[0] == "25b"`; 17 entries |
| `shape("Nazir")` | empty indices are `[0, 1, 65]`; `"33b"` not in `real_amudim(...)` |
| `shape("Avodah Zarah")` | length 152; `unit_at(..., 54).ref == "Avodah Zarah 28b"` |

**This is the guard against the exact failure that broke an earlier draft of this plan:** a hand-carried constant — Tamid's first index, stated as 51 — that contradicted the formula and would have failed a dozen tests on first run. Run it deliberately with `-m live`; never in CI.

- [ ] **Step 2: Run the full gate**

```bash
docker compose up -d
cd backend
uv run pytest -m "not live" --cov=sidra --cov-report=term-missing --cov-fail-under=100 --junitxml=junit-unit.xml
uv run ruff check . && uv run ruff format --check .
uv run pytest -m live -q          # deliberate; requires network
```

If coverage falls short, **add the missing test — never lower the threshold.**

- [ ] **Step 3: Update the docs** — `docs/status.md` records P1a complete and names P1b as next; `docs/versions.md` keeps everything under the single unreleased `## v0.1.0` heading as subsections, never a second heading.

- [ ] **Commit point** — live test, docs.
  Suggested message: `test(catalog): live Sefaria verification of the measured facts`

---

## Definition of Done for P1a

- [ ] `docker compose up -d` brings PostgreSQL 16 up healthy on host **5524**, with both `sidra` and `sidra_test`; host `5432` untouched.
- [ ] Both launchers implement the full `[r]/[k]/[q]/[v]` loop; `[r]` repeats indefinitely; unrecognised input reprints the menu without exiting.
- [ ] `uv run pytest -m "not live" --cov=sidra --cov-fail-under=100` passes at 100%.
- [ ] `ruff check` and `ruff format --check` are clean.
- [ ] `amud_label_to_index("38b") - amud_label_to_index("28b") == 20`.
- [ ] `real_amudim` starts Tamid at `25b` and omits Nazir's `33b`.
- [ ] `unit_at` on a **persisted** Avodah Zarah `Work` returns `Avodah Zarah 28b` at seq **54** and `38b` at seq **74**, and their difference is 20.
- [ ] `unit_at` on Mishneh Torah, Human Dispositions returns `5:8` at the seq computed from its shape array.
- [ ] `to_gematria(15) == "ט״ו"` and `to_gematria(16) == "ט״ז"`.
- [ ] `pytest -m live` passes against the real API.
- [ ] No `Any` in any signature; no state-changing git command anywhere in this plan.

## What follows

**P1b — ingestion.** With units derived, this is mostly **one generic ingester**: fetch a shape, build a `Work`, store it. Special cases are parsha/aliyot (`STORED`, carrying Sefaria's own range expansions), named-label works (Orchot Tzadikim), and the three local parsha-weekly works. Plus title aliases from `schema.titles`. Roughly three tasks, not nine.

**P1c — alignment and seed.** The Ein Mishpat streaming extractor (17 shards, the `"Conection Type"` typo, 118,805 edges), aggregate ranking, the Tur bridge, snapshot write/read, the `sidra_db` CLI, and `test_reference_values.py` — the acceptance gate asserting all 19 seed refs, both measured debts, and every corpus total.
