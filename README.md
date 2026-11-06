# karachay-tools

Open-source language infrastructure for **Karachay-Balkar** (къарачай-малкъар тил, ISO 639-3 `krc`):
a morphological analyzer service, a provenance-tracked corpus pipeline, and an interactive reader.

> **Status: day 1.** Nothing runs yet. This README describes the plan; the [Status](#status) and
> [Metrics](#metrics) sections only ever contain things that actually work and numbers that were actually measured.

## Why

Karachay-Balkar is a Kipchak Turkic language of the North Caucasus (Karachay-Cherkessia and
Kabardino-Balkaria, Russia), with a diaspora in Turkey and elsewhere. UNESCO lists it as vulnerable, and there
are almost no digital tools for it — no reliable way to look up an inflected word, search a corpus, or read a
text with help.

As a heritage learner, coming across reliable resources or ways to analyze them has been the biggest roadblock to improving my vocabulary. Building a tool to help read important texts with confidence is a step toward that.

Rather than build a broad "learning platform", this project builds a few pieces of real infrastructure that
work on real text, and measures them:

- **Analyzer service** — wraps [apertium-krc](https://github.com/apertium/apertium-krc) (finite-state
  morphology with HFST) in an HTTP API. Same transducer runs both ways: analysis (word → lemma + tags) and
  generation (lemma + tags → word).
- **Corpus pipeline** — fetch → extract → normalize → language ID → segment → dedupe → tokenize → analyze →
  load. Every stage is idempotent and versioned; every sentence is traceable to its source and license.
- **Lexicon CI** — every lexicon change is built and tested in CI, with coverage measured on a frozen held-out
  set. Coverage alone can be gamed, so the gate also checks negative tests, gold accuracy, and ambiguity rate.
- **Reader** — paste Karachay-Balkar text, tap any word to see its dictionary form, gloss, and suffix
  breakdown. Unknown words feed a review queue.
- **Multi-script** — Cyrillic, 1920s–30s Latin, and modern romanization.

## Architecture

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
API (FastAPI: search, analyze) ◄─────────────────────────┘
        │
        ▼
Reader app (TypeScript web, offline-capable)
```

| Layer | Tech |
|---|---|
| Analyzer | apertium-krc, HFST, FastAPI, Docker |
| API | Python 3.12, FastAPI |
| Database | PostgreSQL 16 (`pg_trgm` for fuzzy and cross-script search) |
| Pipeline | Python CLI (Typer), JSONL → Postgres |
| Frontend | React, TypeScript, Vite, Tailwind (PWA) |
| CI / infra | GitHub Actions, Docker Compose |

Full design rationale (data model, pipeline contract, CI gate, roadmap): [`docs/DESIGN.md`](docs/DESIGN.md).

## Status

- [x] Project plan
- [x] Database schema ([`db/schema.sql`](db/schema.sql)) — tested on PostgreSQL 16
- [x] apertium-krc builds in Docker ([`analyzer/Dockerfile`](analyzer/Dockerfile))
- [x] Baseline coverage script ([`eval/coverage_report.py`](eval/coverage_report.py))
- [ ] Coverage tests in CI
- [ ] Ingestion pipeline (Wikipedia first)
- [ ] Analyzer API
- [ ] Reader (one screen: paste text, tap words)

## Metrics

Numbers appear here only after they are measured, with the method recorded in [`docs/LOG.md`](docs/LOG.md).

| Metric | Value |
|---|---|
| Token coverage on held-out set | — |
| Corpus size (tokens, by source) | — |
| Analyzer p95 latency / throughput | — |

## Repository layout

```
analyzer/   apertium-krc + HFST wrapped in FastAPI (Docker)
lexicon/    fork of apertium-krc + regression tests
pipeline/   ingestion stages
translit/   transliteration library
api/        public API
web/        reader app
db/         Postgres schema
eval/       frozen held-out set + coverage scripts
```

Directories are created as each piece is built.

## Data and ethics

- Only republish text whose license allows it; otherwise show short snippets with citations.
- Respect robots.txt and site terms; ask community sites before collecting text.
- Audio (later) requires explicit consent tiers and supports withdrawal.

## Acknowledgements

Built on [Apertium](https://www.apertium.org/) and the
[apertium-krc](https://github.com/apertium/apertium-krc) contributors.

## License

Code is licensed under [GPL-3.0](LICENSE), the same license as apertium-krc and HFST, which this project
builds on. Corpus text keeps the license of its original source; each document records its source and license.
