# Design — Karachay-Balkar Language Tools

> Architecture, data model, and roadmap. Last updated: 2026-10-27. Update this file whenever a decision changes.

---

## 1. Why this project exists

Karachay-Balkar (къарачай-малкъар тил, ISO 639-3 `krc`) is a Kipchak Turkic language of the North Caucasus
(Karachay-Cherkessia and Kabardino-Balkaria, Russia) with a diaspora in Turkey (e.g. Afyonkarahisar) and
elsewhere. UNESCO lists it as vulnerable. There are almost no learning or digital resources. Learning it is
extremely hard, especially for heritage speakers.

**Goal:** build real language infrastructure for Karachay-Balkar — a morphological analyzer as a service, a
provenance-tracked corpus, multi-script tools, and an interactive reader — that is genuinely useful to the
community, built with production-quality engineering: tested, measured, versioned, and deployed.

---

## 2. Core decisions (the "why" behind the architecture)

These came from critiquing an earlier plan (a 10-feature "language learning platform" with
React + Node/Express + Python/FastAPI, a "knowledge graph", hand-rolled rule-based analyzer, user accounts in
Phase 1). What we changed and why:

1. **Narrow and deep, not broad and shallow.** The original was ten projects pretending to be one. Solo, that
   ends as a login page + half-empty dictionary + toy analyzer. We build a few things that work on real text,
   with numbers to prove it.
2. **Build on Apertium, don't hand-roll the analyzer.** Turkic morphology (vowel harmony, consonant
   assimilation, stem changes, ambiguity, heavy verb morphology) needs finite-state transducers, not Python
   if-statements. `github.com/apertium/apertium-krc` already exists (incubator status = immature): lexc
   morphotactics, twol morphophonology, Constraint Grammar (`.rlx`) disambiguation, a tagger model, and
   Seegmiller-romanization transducers. Extending it measurably is more impressive than a toy, and it's a
   visible open-source contribution.
3. **The analyzer is infrastructure / a dependency, not the product.** The product is a system: ingest messy
   text → pipeline → database → API → fast frontend, with tests, CI, and monitoring.
4. **Corpus coverage is the headline measurable goal**, tracked in CI on every lexicon change.
5. **Reverse generator is not a separate engine.** An FST runs both directions; the generator is just a UI.
6. **"Knowledge graph" = a well-designed relational schema in Postgres.** No graph database.
7. **One Python backend, not Node + Python.** All hard parts (FST, OCR, corpus) are in Python. Two backends =
   two sets of models and an API boundary to maintain alone. Keep React/TS/Vite/Tailwind for the frontend.
8. **Multi-script support is core**, not an afterthought (Cyrillic, 1920s–30s Latin, modern romanization;
   Perso-Arabic historically).
9. **Real linguistic data before learning features.** No lessons/flashcards/gamification in v1.
10. **No user accounts in Phase 1.** Readers don't need accounts; contributors do, later.

**Target balance of effort:** ~50% software engineering, ~30% data/NLP engineering, ~20% linguistics.
The linguistics sits *inside* a well-engineered system.

---

## 3. Architecture

```
Sources (web text, scans, audio)
        │
        ▼
Ingestion pipeline (clean, OCR, dedupe, tag) ◄──► Analyzer service (HFST transducer, cached)
        │                                                ▲          ▲
        ▼                                                │          │
Postgres (corpus, lexicon, provenance)          Lexicon CI (tests + coverage gate)
        │                                                │
        ▼                                                │
API (FastAPI: search, analyze, auth) ◄───────────────────┘
        │
        ▼
Reader app (TypeScript web, offline-capable)
```

- Data layer: pipeline + Postgres. Language engine: analyzer + lexicon CI. Edges: sources, API, reader.
- The analyzer service is internal only; the public API calls it.

### Stack
| Layer | Choice | Notes |
|---|---|---|
| Analyzer | Apertium-krc + HFST, `hfst` Python bindings, FastAPI | Dockerized, two-stage build |
| Backend API | Python, FastAPI | Generate OpenAPI → typed TS client |
| Database | PostgreSQL 15+ (tested on 16) | `pg_trgm` for fuzzy/translit search, `unaccent` |
| Pipeline | Python CLI (Typer) first → Dagster or Prefect later | JSONL on disk first, then Postgres |
| Frontend | React + TypeScript + Vite + Tailwind | PWA, mobile-first, i18n (ru/tr/en) |
| Infra | Docker Compose locally; GitHub Actions; Terraform; cheap AWS/Azure/Cloud Run/Fly deploy | |
| Observability | Prometheus metrics, structured JSON logs, request IDs | |
| Load testing | k6 or Locust | |
| Dedup | `datasketch` (MinHash) | |
| Lang ID | GlotLID or fastText LID | |
| HTML extraction | trafilatura | |
| Property tests | Hypothesis (for transliteration round-trips) | |

(Django + its admin was considered as an alternative backend for free moderation UI; current choice is FastAPI.)

---

## 4. Repository layout

```
karachay/
├── README.md              # what/why, architecture diagram, live demo link, metrics, 2-min video
├── docs/
│   ├── DESIGN.md          # this file
│   └── LOG.md             # session log
├── analyzer/              # Docker image: apertium-krc + HFST, wrapped in FastAPI
├── lexicon/               # fork of apertium-krc (lexc, twol, rlx) + regression tests
├── pipeline/              # ingestion stages, each rerunnable, with provenance
├── translit/              # standalone transliteration library → PyPI/npm (+ browser build)
├── api/                   # main backend: search, words, texts, review queue
├── web/                   # TypeScript reader app
├── db/
│   └── schema.sql         # Postgres schema (see §7)
├── eval/                  # frozen held-out corpus + coverage scripts
├── infra/                 # Terraform, docker-compose
└── .github/workflows/     # tests, coverage gate, deploy
```

---

## 5. Corpus sources (in order)

**Tier 1 — start here (week 1)**
- **Karachay-Balkar Wikipedia** (CC BY-SA, dump download). Caveat: small Wikipedias contain many bot-generated
  stubs ("X is a village in Y") that skew frequencies — measure the template share and filter/down-weight.
  The Wikilangs project on Hugging Face (`wikilangs/krc`) has tokenizers/n-grams/vocab stats from it — useful
  as a sanity check.
- **apertium-krc `texts/` and `tests/` folders** → first baseline coverage before any pipeline code.
- **Text from native-speaker family/community members** (with permission) — a few pages of naturally written text (messages, stories, a recipe). Tiny but
  colloquial and dialect-specific; great for the eval set.

**Tier 2 — bulk modern text (weeks 2–4)**
- Republic newspapers/media (Nalchik, Cherkessk). Check terms + robots.txt. Store for analysis, don't
  republish in full.
- **Elbrusoid** (elbrusoid.org) community site — hosts literature; researchers have used it for concordance
  work. Ask before scraping; possible partner.
- Diaspora writing from Turkey — different register/spelling habits, good robustness test.

**Tier 3 — parallel text (weeks 4–6)**
- Karachay-Balkar ↔ Russian/Turkish: Bible translation (check license), Universal Declaration of Human Rights,
  bilingual government/school materials. Even a few thousand aligned sentences help glosses/translations.

**Tier 4 — historical + OCR (later)**
- Karachay press 1918–1943, 1920s–30s Latin-script books (drives translit + OCR work).
- Dictionaries (e.g. Karachay-Balkar–Russian) as *reference* to validate/extend the lexicon, not to republish.

**Not yet checked:** whether Karachay-Balkar exists on Mozilla Common Voice. If not, request it and seed the
sentence corpus (good community contribution; enables future ASR).

### The evaluation set (most important "source")
- 3–5k tokens, hand-checked by native speakers. Mix: news, literature, colloquial/family, Karachay AND Balkar.
- **Never train or tune on it.** Frozen and versioned (`eval/heldout-v1.txt`). To fix it, create `heldout-v2`
  and record which version each metric used. Never edit in place.
- Every reported coverage number comes from this set.

---

## 6. Ingestion pipeline

### Stage contract (every stage)
- Input → output only; never reach back two stages or edit earlier data.
- **Idempotent** (rerun = same result).
- **Versioned** (`stage_version` on outputs).
- **Content-addressed** (artifacts stored by hash; unchanged inputs skipped).
- **Golden-file tests** (tricky samples + expected output, checked in CI).

### Stages
1. **Fetch** — download raw (HTML/PDF/image/dump), store untouched. Record URL, fetch time, license, HTTP
   status, hash. Respect robots.txt + rate limits. Raw files are immutable ground truth.
2. **Extract** — plain text with structure. trafilatura for HTML boilerplate; wikitext from dump; PDF text;
   OCR for scans (store per-page OCR confidence). Keep paragraphs + titles.
3. **Normalize** — where subtle bugs live:
   - Unicode NFC.
   - **Fix Latin/Cyrillic lookalikes** (`c o a e p x` mixed into Cyrillic words) — mixed-script words silently
     fail analysis.
   - Standardize quotes, dashes, apostrophes, whitespace.
   - Remove soft hyphens; rejoin line-broken words in OCR output.
   - Log every change; report normalization volume per source.
4. **Language ID** — tag paragraph/sentence as krc / rus / tur / other. Russian quotes are everywhere in news
   and will tank coverage if not filtered. (Kumyk/Nogai confusion is harder but rare in our sources.) Keep
   non-krc sentences — useful later for parallel text.
5. **Segment** — sentence splitting; rule-based with a Karachay abbreviation list (initials, numbers, abbrevs).
6. **Deduplicate** — exact hash at sentence level (reposted news); MinHash near-dup at document level (same
   article, different header). Flag Wikipedia template stubs. **Mark, don't delete.**
7. **Tokenize** — edge cases: hyphenated compounds, numbers with attached suffixes (year + case ending),
   punctuation, names. **Keep character offsets** for highlighting. Shared tokenizer package used by pipeline
   AND analyzer service so offsets always match.
8. **Analyze** — batch calls to analyzer service. Store **all** analyses for ambiguous words + analyzer version.
   Words with no analysis → unknowns (frequency + example sentences) = the lexicon to-do list.
9. **Load** — Postgres upserts; everything linked to source + stage versions.
10. **Report** — per run: token/sentence counts per source; coverage overall + per source (token vs type,
    separately); top unknown words with examples; normalization + duplicate stats.

### Build order
- Weeks 1–2: Typer CLI, one command per stage, JSONL on disk. Stages 1, 2, 4, 7, 8 only, on Wikipedia.
- Weeks 3–4: add normalize, dedup, report; load into Postgres.
- Later: migrate to Dagster/Prefect (scheduling, retries, dashboard) once there are several sources.

---

## 7. Database schema (`db/schema.sql`)

Already written and **tested on PostgreSQL 16**: 18 tables + 2 materialized views; a smoke test confirmed the
unknown-words view returns only unanalyzed words.

Layers:
- **Provenance:** `sources` (kind, license, `can_republish` → full text vs snippets only), `documents`
  (script, dialect, `raw_sha256`, `ocr_confidence`, metadata jsonb).
- **Corpus:** `sentences` (`text_original` + `text_norm`, `text_sha256`, `lang` + confidence, `duplicate_of`,
  `in_eval_set`, `stage_versions` jsonb), `sentence_translations` (origin: parallel_source / contributor /
  machine_draft; review status).
- **Analysis:** `tokens` (form, `form_lower`, `char_start/char_end`, `is_word`), `analyzer_versions` (tag,
  git_sha), `analyses` (one row per candidate; `lemma_text`, `lemma_id`, `tags text[]`, `rank`, `is_gold`).
- **Lexicon:** `lemmas` (headword, pos, dialect, etymology, status, `in_analyzer`), `senses` (glosses in
  rus/tur/eng), `lemma_relations` (derived_from, synonym, dialect_variant, turkish_cognate), `cognates`
  (lang, word, `false_friend`).
- **Audio:** `speakers` (birth_decade, region, dialect, consent tier, consent_doc, `withdrawn_at`),
  `recordings` (storage_key never a public URL, per-recording consent).
- **Community:** `users` (roles: reader/contributor/reviewer/admin), `suggestions` (review queue, payload
  jsonb), `audit_log` (append-only before/after jsonb).
- **Ops:** `pipeline_runs` (stats jsonb), `eval_runs` (token_coverage, type_coverage, gold_accuracy,
  per_source, regressions).
- **Views:** `word_frequency` (krc, canonical, excludes eval set), `unknown_words` (frequent words the latest
  analyzer can't parse, ordered by frequency).

Enums: `source_kind`, `script_kind` (cyrl, latn_1920s, latn_modern, arab), `dialect_kind` (standard, karachay,
baksan_chegem, malkar_cherek, unknown), `lang_label` (krc, rus, tur, eng, other), `review_status`,
`consent_tier` (public, research, family_only), `user_role`.

Design points to be able to explain:
- Relational, not graph DB; relationships in `lemma_relations`.
- Analyses keep every candidate + rank + `is_gold` → measure accuracy, not just coverage.
- Eval set protected in the DB via `in_eval_set`.
- `pg_trgm` GIN indexes on headwords, glosses, sentences → fuzzy + English→Karachay search without Elasticsearch.
- Scale note: `tokens` is the biggest table (~1 row per corpus word). Millions fine; past tens of millions,
  partition `tokens`/`analyses` by source.

---

## 8. Analyzer service

**Build:** two-stage Dockerfile.
- Stage 1: Debian + Apertium/HFST toolchain (package name may differ — check Apertium install docs / nightly
  packages), copy our apertium-krc fork, `./autogen.sh && make` → `krc.automorf.hfst` (analyzer),
  `krc.autogen.hfst` (generator).
- Stage 2: `python:3.12-slim` + `hfst fastapi uvicorn prometheus-client`; copy only the two binaries + app.
- Bake `ANALYZER_VERSION` (git tag + sha) into the image; every response reports it.

**Core:** load transducers once per worker. `analyzer.lookup(form)`, fall back to `form.lower()` for
sentence-initial caps (return which variant matched; proper nouns are the exception). Parse output strings
like `китап<n><pl><px1pl><abl>` into `{lemma, tags[]}`; split on `+` for joined analyses (e.g. noun + copula).

**Request path for `/analyze`:** validate (size cap ~20k chars) → tokenize (shared tokenizer) → dedupe unique
forms → cache check → lookup misses → assemble tokens with offsets, analyses, `unknown` flag, version.
`/generate`: build tag string from lemma + tags, **validate tags against an allow-list**, run generator.

**Caching:** key = `(analyzer_version, form)`. In-process LRU (~100k entries/worker); shared Redis later.
Version in key → new deploy auto-invalidates. Report hit rate (expect high for Turkic text).

**Concurrency:** lookups are CPU-bound → multiple worker processes (uvicorn `--workers` ≈ cores), each with
its own transducer + cache; synchronous handlers (no I/O to await).

**Endpoints (internal):** `POST /analyze`, `POST /analyze/batch`, `POST /generate`, `GET /health`,
`GET /ready` (transducers loaded), `GET /version`, `GET /metrics`.

**Observability:** latency histograms per endpoint (p50/p95/p99), cache hit rate, unknown-word rate on live
traffic, request size, errors. Structured JSON logs with request ID from the main API.

**Testing:** parser unit tests (compound `+`, multiple analyses, empty), contract tests vs API schema, golden
full-response tests, k6/Locust load test on a stated machine size (report throughput + p95 latency).

**Deploy:** any container host; readiness checks; gradual rollout; rollback = redeploy previous tag.

**Later:** Constraint Grammar disambiguation via `vislcg3` + the `.rlx` file; frequency-weighted ranking;
spellchecker (transducer + edit distance).

**v1 needs only:** build, core lookup, request path, `/health`.

---

## 9. Lexicon CI and coverage gate

On every PR touching `lexicon/**`, `eval/**`, `tests/**`:

1. **Build** the transducer in Docker (cache keyed on lexicon file hash).
2. **Regression tests** (YAML, grouped by nouns/verbs/pronouns/numerals):
   - Positive: form → expected analysis.
   - Generation: analysis → exact form (catches misspelled generator output).
   - **Negative:** forms that must NOT be accepted (broken vowel harmony, impossible suffix order).
   - Round-trip: generate full paradigms for sample lemmas, analyze back; non-round-trips are bugs.
   - Any failure fails the build.
3. **Coverage** on frozen held-out set: token coverage, type coverage, per-source coverage, gold accuracy
   (correct analysis among candidates on hand-checked subset), ambiguity rate (analyses/word).
4. **Compare to main** (metrics JSON artifact from last main merge). Gate:
   | Check | Rule |
   |---|---|
   | Regression tests | must all pass |
   | Token coverage | may not drop > 0.1 points |
   | Gold accuracy | may not drop at all |
   | Ambiguity rate | warn if it rises > ~5% |
   | Negative tests | must all pass |
   **Why:** coverage can be gamed — a sloppy rule accepting any suffix sequence raises coverage while making
   the analyzer worse. Negative tests + gold accuracy + ambiguity rate catch that.
5. **PR comment** (one, updated): metrics table main vs PR vs Δ; newly analyzed (top 10 by freq);
   **lost analyses** (words analyzed before but not now — most useful line for reviewers); top remaining unknowns.
6. **After merge:** tag new analyzer version + publish image → POST metrics to `/internal/eval-runs` →
   deploy analyzer (cache self-invalidates) → reanalyze corpus + refresh `unknown_words`.

Keep PR check < ~5 min (small eval set); full-corpus coverage runs nightly.
Practices: **write the test first, watch it fail, then fix the lexicon (TDD).** Periodically upstream
improvements to apertium-krc as PRs (CI results make them easy to trust).

Workflow sketch:
```yaml
name: lexicon
on:
  pull_request:
    paths: ["lexicon/**", "eval/**", "tests/**"]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t krc-analyzer ./analyzer
      - run: docker run krc-analyzer python -m lexicon_ci.tests tests/
      - run: docker run krc-analyzer python -m lexicon_ci.coverage eval/heldout-v1.txt > metrics.json
      - run: gh run download --name metrics-main --dir baseline
      - run: python -m lexicon_ci.gate baseline/metrics.json metrics.json --report report.md
      - run: gh pr comment ${{ github.event.number }} --body-file report.md --edit-last
```

---

## 10. Public API (`/v1`, FastAPI)

**Public (no login)**
- `POST /v1/analyze` — sentence/paragraph → tokens + offsets + candidate analyses (powers the reader).
- `POST /v1/analyze/batch` — capped size.
- `POST /v1/generate` — lemma + tags → surface form (word builder).
- `GET /v1/paradigm/{lemma_id}` — full inflection table.
- `POST /v1/transliterate` — `cyrl` ↔ `latn_1920s` ↔ `latn_modern` (library also runs in browser).
- `GET /v1/lemmas/{id}` — word page (senses, relations, cognates, audio, frequency).
- `GET /v1/lemmas/{id}/examples` — corpus sentences with any form of the word (paginated).
- `GET /v1/search?q=&lang=` — one box: any inflected form, any script, glosses in en/ru/tr, fuzzy.
- `GET /v1/documents/{id}` — text for the reader with precomputed analyses; respects `can_republish`.
- `GET /v1/concordance?lemma=` or `?tags=` — every occurrence of a word/grammatical pattern in context.
- `GET /v1/frequency?pos=&limit=`
- `GET /v1/stats` — corpus size, coverage, sources (public dashboard).

**Contributors (login)**
- `POST /v1/suggestions`; `GET /v1/suggestions?status=pending` (reviewers);
  `POST /v1/suggestions/{id}/approve|reject` (writes audit log); `GET /v1/history/{table}/{id}`.
- `POST /v1/recordings` → returns signed upload URL; `GET /v1/recordings/{id}/stream` → short-lived signed URL
  only if viewer's access matches consent tier and speaker hasn't withdrawn.

**Internal (service token)**
- `POST /internal/pipeline-runs`, `POST /internal/eval-runs`, `GET /internal/unknown-words?limit=`,
  `POST /internal/analyzer-versions`.

Sample response:
```json
{
  "analyzer_version": "krc-2026.10.2",
  "tokens": [
    { "form": "Мен", "start": 0, "end": 3,
      "analyses": [{ "lemma": "мен", "lemma_id": 812, "tags": ["prn","pers","p1","sg","nom"] }] },
    { "form": "китапны", "start": 4, "end": 11,
      "analyses": [{ "lemma": "китап", "lemma_id": 1043, "tags": ["n","acc"] }] },
    { "form": "окъуйма", "start": 12, "end": 19, "analyses": [], "unknown": true }
  ],
  "coverage": 0.667
}
```
(Illustrative only — tags/forms not yet verified against the real analyzer.)

Design points: cache by `(analyzer_version, token)`; analyzer never public (one place for rate limits, size
caps, auth); cursor pagination for concordance/examples; audio never gets a permanent public URL; generated
OpenAPI → typed TS client (API and frontend can't drift); rate limits on public analyze/search, higher when
logged in.

**Start with only three:** `/analyze`, `/lemmas/{id}`, `/search`.

---

## 11. Reader app (frontend)

**Core screen:** pasted/selected text on top (serif), tapped-word panel below (sans).
- Every word tappable (dotted underline); selected word highlighted.
- Panel: surface form + other-script form; POS; dictionary form + gloss; **color-coded segment chips**
  (root neutral, plural one color, possessive another, case another — consistent everywhere so learners learn
  to recognize suffixes on sight); "Together: <meaning>"; buttons: N examples, All forms, Suggest a fix; Listen.
- **Global script toggle** (Cyrillic / Latin), stored per user — diaspora in Turkey may prefer Latin.
- Unknown words: **dashed** underline; tap → "We don't know this word yet" + quick suggestion form → review queue.

**Other screens:** Home (big paste box + library filterable by difficulty/dialect; difficulty = share of
words outside top-1000 frequency); Word page (glosses ru/tr/en, inflection table, Turkish cognates, audio,
real examples with sources); Word builder (generator as a toy — best demo of the transducer); Stats page
(public corpus size, coverage over time, sources).

**Design decisions:** mobile-first (many users in the republics on slow connections); small bundle; offline PWA
caching of texts + translit library; keyboard accessible (Tab through words, Enter opens, screen-reader labels);
i18n ru/tr/en from day one; fetch all analyses per document once so taps are instant.

**First frontend milestone:** just the paste box + this one screen.

---

## 12. Additional features (later, in this order)

1. Spellchecker (Hunspell/browser extension generated from the transducer) + **keyboard layout** for къ, гъ, нг
   — tools people use daily in WhatsApp/Word/social media.
2. Transliteration library published to PyPI/npm, compiled to TS/WASM for the browser; property-based
   round-trip tests (Hypothesis). Build from apertium-krc's Seegmiller transducers.
3. OCR-with-validation pipeline for old books (incl. Latin script): Tesseract has no krc model → use Russian
   Cyrillic OCR + post-correction; the analyzer flags unparseable words; fix systematic digraph errors. This
   OCR → FST validation → correction loop is the genuinely novel technical piece.
4. Elder recording / oral history archive: mobile-friendly elicitation flow (picture, Russian/Turkish word, "how
   would you say…?"), record, tag dialect + speaker, **explicit consent tiers** (public / research /
   family_only), takedown support. Treat recordings with patient-data-level care.
5. Learning features built on top (frequency lists, spaced repetition on *inflected forms*, listening-first
   content, Cyrillic-reading drills using words heritage speakers already know aurally, self-assessment that
   routes users instead of fixed "profiles A–D").
6. **Turkish bridge:** Turkish equivalents, false-friend flags, systematic sound correspondences; UI in ru/tr/en.
7. **Dialects first-class:** Karachay vs Balkar varieties (e.g. ч/ц and дж/з type differences, vocabulary).
   Tag every entry/clip with dialect; "how is this said in Balkar?"
8. Open datasets on Hugging Face/GitHub (properly licensed). Common Voice contribution.
9. Careful LLM layer (if any): **LLM proposes → transducer checks → human approves.** Never publish
   unverified LLM output.

---

## 13. Linguistic cautions (known errors to avoid)

- An earlier draft plan used **"Мен китапны окъуйма" = "I am not reading the book", glossed
  read-PROG-NEG. That is wrong.** It's affirmative ("I read / am reading the book"); the negative puts the
  negation marker before the person ending (something like окъумайма — `TODO(verify)` with a native speaker).
- Example breakdown used throughout: **китапларыбыздан** = китап (book) + лар (plural) + ыбыз (our) + дан
  (from/ablative) = "from our books". Plausible but `TODO(verify)` against the real analyzer and family.
- The reader mockup's sample sentence/segmentations (e.g. бирин, окъуйма chips) were guesses — verify before use.
- Turkic suffixes surface in several forms (vowel harmony, assimilation) — never hardcode one surface form
  for a suffix.
- Standard written language is based on the Karachay–Baksan–Chegem dialect; family speech may differ.
- Alphabet history: Arabic-based → 1920s Latin → Cyrillic (with a 1964 restoration of normal Cyrillic noted
  in sources). Digraphs: къ, гъ, нг, etc.

---

## 14. Ethics, licensing, privacy

- Respect robots.txt, site terms, rate limits. Ask community sites before scraping.
- Store full text for analysis; **only republish where `can_republish` is true**; otherwise show snippets
  with citations. Many scanned dictionaries/textbooks can't be republished — store extracted vocabulary with
  citations, not the books.
- Audio: explicit consent, consent tiers, withdrawal hides everything, takedown flow, signed short-lived URLs,
  never public permanent URLs.
- Every edit attributable and reversible (audit log).

---

## 15. Roadmap

### Week one
- **Day 1:** GitHub repo + README (what and why). Push.
- **Days 2–3:** install Apertium/HFST (or Docker), clone apertium-krc, build, run one sentence on the command
  line. Hardest step — expect toolchain debugging.
- **Day 4:** run a Wikipedia article + family sentences through it; look at what's right/wrong.
- **Day 5:** Python script: read text file → split words → analyze each → print % recognized + top 20 unknowns.
  **= first baseline coverage number.**

### Then, one layer at a time (don't start N+1 until N works)
1. Coverage script → tests in CI.
2. Script → pipeline (Wikipedia download + cleaning).
3. Pipeline → Postgres.
4. Command line → FastAPI + Docker service.
5. Service → reader (one screen: paste text, tap words).

### 12-week shape
| Weeks | Software | NLP / data | Linguistics |
|---|---|---|---|
| 1–2 | Repo, CI, Docker, build apertium-krc in a container | First ~50–100k-word corpus | Spot-check analyzer output with native speakers |
| 3–5 | Analyzer API, caching, load tests | Pipeline stages, provenance, unknown-word report | Fix top-frequency failures |
| 6–8 | Reader frontend, deploy | Coverage-in-CI, held-out eval set | Continue data-driven fixes |
| 9–10 | Transliteration library + WASM | Test historical Latin text | Verify script mappings |
| 11–12 | Polish, observability, README, demo video | Publish dataset + metrics | Write up findings |

Realistic first milestone: Wikipedia + one news source + family text ≈ a few hundred thousand tokens.

---

## 16. What "done well" looks like

Measurable outcomes (report only measured numbers):
- Analyzer coverage on the frozen eval set, tracked over time (start → current).
- Analyzer service throughput and p95 latency on a stated machine size.
- Corpus size by source, with provenance and license for every document.

Public deliverables: live demo link, architecture diagram in the README, a short demo video ("paste any
Karachay sentence and watch it get analyzed"), coverage-over-time chart, open-source PRs to apertium-krc,
published dataset (properly licensed).

---

## 17. Conventions

- Python 3.12, type hints, `ruff` + `mypy`, `pytest`. TypeScript strict mode.
- Small PRs, descriptive commits. Tests next to the code they test.
- Every data artifact carries source, license, and stage/analyzer version.
- Secrets in env vars / `.env` (gitignored), never committed.
- On Windows: run the toolchain in WSL2 or Docker (Apertium/HFST is Linux-first).

## 18. Open questions
- Which news sources allow use, and on what terms?
- Contact Elbrusoid about data sharing?
- Is krc on Common Voice?
- Exact Apertium package names / image for the Docker build stage.
- Which dialect(s) do our native-speaker checkers speak? (affects eval set and dialect tags)
- Hosting choice and budget for the deploy.
