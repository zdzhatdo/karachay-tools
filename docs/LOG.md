# Session log

## 2026-10-09 — Week 1, day 1: README and license

**Did**
- Wrote the README: what/why, architecture, status checklist, metrics table (empty until measured).
- Chose GPL-3.0 for the whole repo. apertium-krc and HFST are both GPL-3.0; the analyzer imports HFST, so it
  must be GPL anyway, and one license keeps things simple. Revisit for `translit/` before publishing it to
  PyPI/npm (permissive may matter there).
- Added `.gitattributes` so shell scripts and Dockerfiles keep LF line endings on Windows.

**Next (days 2–3)**
- Explore in a throwaway container (`docker run -it debian:bookworm bash`): install Apertium toolchain
  (apertium-krc README lists lttoolbox ≥ 3.3, apertium ≥ 3.3, vislcg3, hfst ≥ 3.8.2), clone apertium-krc
  inside Linux, `./autogen.sh && make`, analyze one sentence.
- Turn the working commands into `analyzer/Dockerfile`.

## 2026-11-02 — Week 1, day 2: apertium-krc builds and analyzes words

**Did**
- Explored in a throwaway container (`docker run -it --name krc-explore debian:bookworm bash`) to find a
  working command sequence before writing a Dockerfile.
- Toolchain: Apertium nightly apt repo (`install-nightly.sh`) + `apertium-all-dev`. Versions installed:
  hfst 3.17.3, VISL CG-3 1.7.0.13898. `apt-cache depends apertium-all-dev` confirmed it pulls in everything
  apertium-krc needs (hfst, lttoolbox, cg3, apertium, autotools).
- Source: apertium-krc at commit `e84bc3a`. Upstream's last commit is 2022-03-05, so the project is dormant;
  our fork will effectively be where development happens, and upstream PRs may be slow to review.
- `./autogen.sh` succeeded; `make` succeeded after one fix (below).
- First analyses (`echo <word> | hfst-lookup krc.automorf.hfst`):
  - `киштик` → `киштик<n><nom>` and `киштик<n><attr>` — two candidates, equal weight (ambiguity).
  - `киштигим` → `киштик<n><px1sg><nom>` — suffix and stem alternation handled.
  - `Киштигим` (capitalized) → `+?` unknown. Lowercase works, so the analyzer is case-sensitive: evidence for
    the lowercase fallback in DESIGN.md §8.
  - `Тибр` → `Тибр<np><top><nom>` / `<attr>` — confirms the fix.

**Broke / learned**
- **Build failure from version drift.** The Makefile runs `hfst-lexc --Werror`. Two lexicon entries
  (`эмансипа́ция`, `Ти́бр`) contained a combining acute accent (U+0301, a stress mark). Current hfst warns that
  letter + U+0301 is now one symbol (older versions treated it as two); `--Werror` turned the warning into an
  error. Only 2 lines in the whole lexicon had it — copy-paste from a dictionary/Wikipedia.
  - Options: drop `--Werror` (hides future warnings), declare the symbols as multichar (builds, but entries
    still never match real text), or remove the accents.
  - Chose removal after native-speaker confirmation: stress marks are not used in ordinary writing, only in
    dictionaries/encyclopedias to show pronunciation. So it's a data-entry bug fix, and upstreamable.
  - Saved as a patch (`git diff > fix-stress-marks.patch`, copied out with `docker cp`).
- **Pipeline rule found:** Wikipedia uses stress marks, so the normalize stage must strip U+0301, or known words
  will show up as unknown.
- Remaining warning: `{Ъ}` multichar symbol in the Seegmiller → Cyrillic transliteration transducer. Not fatal;
  deferred to the transliteration work.
- **Locale:** `debian:bookworm` has no UTF-8 locale by default, so pasted Cyrillic showed as byte codes.
  `export LANG=C.UTF-8 LC_ALL=C.UTF-8` fixes it; the Dockerfile needs `ENV LANG=C.UTF-8`.
- **Exit codes through pipes:** `make | tee log` reports `tee`'s exit code. `${PIPESTATUS[0]}` gives `make`'s.
  Matters in CI, where a hidden failure makes a red build look green.
- **Mojibake:** Windows PowerShell 5.1 `type` reads BOM-less UTF-8 as Windows-1252, so `п` displayed as `Ð¿`.
  The bytes were fine; use `Get-Content -Encoding UTF8`. Same class of bug the normalize stage should detect
  in scraped text.
- Containers started without `--rm` survive a closed terminal: `docker start -ai krc-explore`.

**Next (day 3)**
- Decide how our fix gets into the build: fork apertium-krc vs. pinned upstream commit + patch file.
- Write stage 1 of `analyzer/Dockerfile` from today's commands: pinned base image, Apertium repo, `ENV LANG`,
  pinned apertium-krc commit, apply fix, `autogen.sh && make`. Done when `hfst-lookup` in the built image
  analyzes `киштигим` and `Тибр`.

## 2026-11-04 — Week 1, day 3: analyzer image builds from the repo

**Did**
- Vendored apertium-krc into `lexicon/` (upstream `e84bc3a`, dormant since 2022) instead of a separate fork,
  so lexicon fixes, their tests, and CI path filters (`lexicon/**`) live in one repo and one PR.
  `lexicon/UPSTREAM` records the source commit and the one omitted file.
- Commit structure: unmodified upstream copy first, then each local change as its own commit, so
  `git diff <vendor commit> HEAD -- lexicon/` shows exactly what we changed (needed for upstream PRs).
- Wrote `analyzer/Dockerfile` (build stage only): Debian bookworm, Apertium nightly toolchain, copy
  `lexicon/`, `autogen.sh && make`. Built on the first try. Inside the image, `киштигим` →
  `киштик<n><px1sg><nom>` and `Тибр` → `Тибр<np><top>` — same as the manual day 2 build.
- Layer order: toolchain install before `COPY lexicon/`, so lexicon edits reuse the cached toolchain
  (`make` alone takes ~17 s).
- Image records its toolchain in `/toolchain-versions.txt` (`dpkg-query`): apertium 3.10.0, cg3 1.7.0,
  hfst 3.17.3, lttoolbox 3.8.4, each with its upstream source hash.

**Broke / learned**
- Windows broke the vendored copy in four separate ways:
  - `PRN.prefix.dix`: `PRN` is a reserved device name on Windows; git refuses the path. Omitted (only used
    by an optional upstream test helper) and documented in `UPSTREAM`.
  - Windows `tar` decoded UTF-8 filenames as CP437 (`kün.yaml` → `k├╝n.yaml`) — mojibake in file names.
  - Executable bits were lost (`autogen.sh` 755 → 644), which would fail `./autogen.sh` in Linux.
  - Upstream's `.gitignore` ignores files upstream tracks (`krc.prob`), so `git add` silently skipped them.
  - Fix for names and modes: load upstream's tree straight from git objects with `git update-index
    --index-info` (skipping PRN), bypassing the filesystem. Verified every entry's mode and hash against
    upstream with `git ls-tree`.
- Upstream's SVN-era `lexicon/.gitattributes` (`* text=auto !eol`) overrode our root LF rule, because a
  nested `.gitattributes` wins. Removed it; `git check-attr eol` now reports `lf`, and
  `git ls-files --eol` shows the binary `krc.prob` is detected as `-text` (never converted).
- `SHELL ["/bin/bash", "-o", "pipefail", "-c"]` in the Dockerfile so `curl … | bash` fails the build if
  `curl` fails — same lesson as `${PIPESTATUS[0]}` on day 2.
- Reproducibility: the lexicon is pinned; `debian:bookworm` and the Apertium nightly packages are not
  (nightly can't really be pinned). Goal is a reproducible *artifact* (published, tagged image) plus a
  version record, rather than bit-identical rebuilds. Pin the base image by digest later, with automated
  update PRs.

**Next (day 4)**
- Run a Wikipedia article and some native-speaker text through the analyzer; look at what's right
  and wrong (DESIGN.md §15).

## 2026-11-05 — Week 1, day 4: first look at real text

**Did**
- Ran a small native-speaker sample and one Wikipedia article (`Алан`, revision 129091) through
  `apertium -d /src/lexicon krc-morph`. Samples stay in gitignored `data/`.
- Wikipedia article: 1,328 words, 230 unknown (180 distinct), 716 with more than one analysis. Exploratory
  numbers from one name-heavy history article, not a coverage score; those come only from the eval set.
- Sorted unknowns by cause instead of treating them as one list:
  - Missing stems: names, ethnonyms (`гуннла`, `печенегле`), loanwords, some verbs. Plural `-ла/-ле` itself
    works (`киштикле`).
  - Attached `бла`: only the separate word is in the lexicon (`киштик бла` works, `киштикбла` doesn't).
  - Missing verb form: `джаша` is in the lexicon, but `джашагъадыла` is unknown.
  - Misclassified stem: `полк` is entered as an adjective, so noun endings fail.
  - Possible overgeneration: `айт<v><tv><aor><p3><pl>` generates `айтадыла`, `айтедиле`, `айтйдыла`.

**Broke / learned**
- Correction to day 2: capitalization failure is specific to `hfst-lookup`. The `krc-morph` pipeline
  (`lt-proc -w`) analyzes `Киштигим` and `КИШТИК` and splits punctuation. Compare it with the planned
  lowercase fallback before building the service (DESIGN.md §8).
- The pipeline appends a `^./.<sent>$` token when the input has no final period, so counting tokens naively
  would be wrong. The coverage script must handle it.
- An unknown word isn't necessarily a misspelling. Two "maybe misspelled" verbs fit the lexicon's patterns;
  `къайт-` also appears in an unrelated article (`къайтханны`), which suggests a missing stem.
- First hypothesis (missing verbs are the main gap) didn't hold on the Wikipedia sample, which was a mix.
- One rule can fix many words; one stem fixes only that word. Frequency across more text should decide order.
- Windows Python printed through cp1252 and crashed on Cyrillic; `-X utf8` fixes it.

**To verify with native speakers**
- Spelling of `къууан-` and `къайт-` forms; spelling of `казак` in Karachay-Balkar.
- Whether `бла` is normally attached, separate, or both.
- Whether `айтедиле` and `айтйдыла` are valid. If not, they become negative tests.
- Whether `полк` should be a noun.

**Next (day 5)**
- Coverage script: read text → analyze → print % recognized and top 20 unknowns (first baseline, DESIGN.md §15).

## 2026-11-06 — Week 1, day 5: first coverage baseline

**Did**
- Added `eval/coverage_report.py`, which reads Apertium stream output and reports word count, unknown count,
  token and type coverage, and the top 20 unknowns. It needs no HFST or Docker: Docker produces the analysis,
  Python only reads it, so tests run in milliseconds.
- Added `eval/test_coverage_report.py` (4 pytest tests): unknown markers, multiple analyses, escapes, and the
  word rule. Tests use placeholder strings, not Karachay-Balkar forms.
- **First dev baseline: 82.1% token coverage, 76.6% type coverage** (1,279 words, 229 unknown).

**How it was measured**
- Text: Wikipedia article `Алан`, revision 129091, plain text from the MediaWiki API (`prop=extracts`).
- Analyzer: lexicon at `5d4d0ea`; image built 2026-11-04 with apertium 3.10.0, cg3 1.7.0, hfst 3.17.3,
  lttoolbox 3.8.4.
- Commands: `apertium -d /src/lexicon krc-morph` in the image, then
  `python -X utf8 eval/coverage_report.py <output>`.
- A word is a token whose surface form contains a letter. Numbers and punctuation are excluded; tokens like
  `1828дж` count as words. Types are compared in lowercase.
- This is one name-heavy article, not the eval set, so it stays out of the README metrics table.

**Broke / learned**
- Correction to day 4: the 1,328 words / 230 unknown in that entry came from a quick script that counted numbers
  and some punctuation as words. The letter rule gives 1,279 / 229.
- The letter rule replaced a list of punctuation tags, and also removes the extra `.` the pipeline appends.
- Apertium escapes special characters with backslashes, so the parser uses negative lookbehind
  (`(?<!\\)`) to avoid ending a token at an escaped `$`.
- Renamed the script from `coverage.py`: that name can shadow the `coverage` package that `pytest-cov` needs.
- Known limits: an empty input file crashes; a word that is known in one place and unknown in another
  counts as unknown for type coverage.

**Next**
- Roadmap step 1: run the tests and coverage report in CI.
- Add the U+0301 stripping rule to the normalize stage in DESIGN.md §6.

## 2026-11-09 — Week 2, day 1: CI

**Did**
- Added GitHub Actions CI (`.github/workflows/ci.yml`), on every push to main and every pull request. Two
  parallel jobs: `python-tests` (pytest on `eval/`) and `analyzer` (build the image, run the smoke test).
  Least-privilege `permissions: contents: read`.
- Added `analyzer/smoke-test.sh`: native-speaker-verified forms must still get their analyses
  (`киштигим` → `киштик<n><px1sg><nom>`, `Тибр` → `Тибр<np><top><nom>`). Checks that the expected analysis
  is among the candidates, so extra candidates don't break it. Confirmed it fails on a wrong expectation.
- First run on `a6671bf`: both jobs passed. `python-tests` 9 s; `analyzer` 65 s, of which the image build
  is 61 s. Under the 5-minute target without caching.

**Broke / learned**
- Upstream's `apertium-regtest` suite fails on our build: 9 of 12 corpora differ from the 2022 snapshot.
  Left out of CI for now so CI stays green and meaningful; triage is a separate task.
  - It compares against "expected" (last accepted output) and "gold" (human-checked answer). In `yots`,
    `къоюб` went from unknown in the snapshot to 4 candidates including the gold analysis — an improvement
    that still counts as a failure. So at least part of the red is a stale snapshot.
  - Its gold check needs an exact match, but `krc-morph` returns every candidate. Stricter than our planned
    gold accuracy ("correct analysis among candidates", DESIGN.md §9).
  - Not accepting all changes with `-a`: that would hide any real regressions.

**Regtest triage (same day)**
- Sorted all 32 mismatches: 9 improved (unknown → known, gold among candidates), 9 snapshot formatting only
  (old snapshot escaped tags as `\<...\>`), 5 extra candidates with gold still present, 9 open questions for
  native speakers. No known → unknown regressions.
- Updated the "expected" snapshot to current output only after that review (exactly 32 lines in 9 files);
  gold files untouched (411/858 gold matches before and after). Then added `apertium-regtest test` to CI.
- `apertium-regtest cli` accepts one corpus per session, so accepting needed repeated sessions.

**Broke / learned**
- Working-tree line endings were wrong: 60 files under `lexicon/` were CRLF on disk, because they were checked
  out while upstream's `.gitattributes` was still active, and git doesn't rewrite unchanged files. The day 3
  check missed it: Git Bash `grep` hides `\r`. `git ls-files --eol` is the reliable check.
  - Main analyzer files were LF (no effect on analyses); the Seegmiller transliteration files and regtest files
    were CRLF locally but LF in CI. Fixed by re-checking out `lexicon/`; triage rerun gave identical results.

**To verify with native speakers (regtest)**
- `кюнюн`: should it also have a genitive reading? `кёзюуюню`: accusative or genitive?
- `кюн` + "your" + dative: `кюнюнге`, `кюнюнга`, or `кюннге`?
- Ordinal + copula: `39-чусуду` or `39-чуду`; `55-чисиди` or `55-чиди`?
- `айныныкъ`, `айнылыкъ`: valid, or overgeneration?
- `алгъанча` or `алгъынча`? `къойаргъа` or `къояргъа`?

**Next**
- Pin action versions and `pytest` together with the base-image digest.
- Add the U+0301 stripping rule to the normalize stage in DESIGN.md §6.

## 2026-11-12 — Week 2, day 2: pipeline stage 1 (fetch)

**Did**
- Added `pyproject.toml` (Python ≥ 3.12, `typer`, dev extra `pytest`, `krc-pipeline` command, pytest test
  paths). CI now installs from it, so CI and local use the same dependency list.
- Added `pipeline/fetch.py` and `krc-pipeline fetch --date 20261101`: downloads the dated Karachay-Balkar
  Wikipedia articles dump (5,521,144 bytes), verifies size and SHA-1 against Wikimedia's `dumpstatus.json`,
  stores it as `data/raw/<sha256>.xml.bz2`, and appends a record to `data/raw/manifest.jsonl` (URL, dump
  date, fetch time, license, size, SHA-1, SHA-256, stage version).
- 3 tests with a fake network: stored under its hash and recorded; second run downloads nothing;
  corrupted download rejected and nothing written. All 7 tests pass locally and in CI.

**Design points**
- Dated dump URL, not `latest`, so the same command always means the same input.
- Idempotent: a second run finds the same SHA-1 in the manifest and skips the download (verified: same record,
  same timestamp).
- Reproducible: two independent downloads produced the same SHA-256 (`19db27f1…`).
- Write to `.part`, then rename: a crash never leaves a half-written file under the final name.
- The network function is passed in as a parameter (dependency injection), so tests need no internet.
- No `http_status` field (DESIGN.md §6 lists one): any non-success response raises, so every stored record
  is a successful download.
- Reads the whole file into memory; fine at 5.5 MB, needs streaming for large sources.

**Next**
- Stage 2 (extract): wikitext from the dump → plain text with titles and paragraphs, keeping page IDs and
  revision IDs for provenance.

## 2026-11-12 — Week 2, day 3: pipeline stage 2 (extract)

**Did**
- Profiled the dump before designing (3 s): 3,140 articles, 2,075 redirects, ~12,000 non-article pages;
  49% of articles under 1,000 characters of wikitext; 5,482 `<ref>` citations; 1.28 million Latin letters in
  article wikitext (mostly citation templates and URLs); 982 U+0301 stress marks.
- Added `pipeline/extract.py` and `krc-pipeline extract <dump>`, using `mwparserfromhell` (parses wiki markup
  into a tree; regexes break on nested templates). Keeps titles, section headings, and paragraphs; drops
  templates, citations, tables, images, and categories. One JSON line per article with page ID, revision ID,
  template names, source SHA-256, and stage version.
- Result: 2,617 articles extracted. Skips are counted by reason and reconcile with the profile:
  2,617 + 523 empty = 3,140 articles.
- Checked one article against Wikipedia's own plain text (`Алан`): 1,282 vs 1,335 words (difference is mostly
  headings), and the same 24 Latin letters, so citations were removed cleanly.
- 4 new tests (11 total); all pass locally and in CI.

**Design points**
- Streams the dump (`iterparse` + `clear()`), so memory stays flat regardless of dump size.
- Output file is named `<input sha256>.<stage version>.jsonl`: new input or new code version means a new file;
  old outputs are never overwritten. Idempotent: an existing output is not rebuilt.
- Deterministic: two runs in different environments produced byte-identical output.
- File and category namespace names are read from the dump, not hard-coded.
- Template names are kept so later stages can flag stubs without parsing wikitext again.
- Stress-mark stripping and whitespace cleanup belong to stage 3 (normalize), not extract.

**Broke / learned**
- The 523 empty articles were checked, not assumed: 504 are year pages with only empty headings, 18 are
  infobox-only, 1 is a list made entirely of a table. Dropping tables also drops table-only articles (accepted
  for now).
- Breaking the code on purpose showed a weak test: with citations no longer removed, all tests still passed,
  because the test citation contained only a template. Added a citation with plain text; now it fails as it
  should. Same check confirmed the idempotency test catches a missing skip.

**To verify with native speakers**
- Does the template `тамамланмагъан статья` (760 pages) mean "unfinished/incomplete article" (a stub marker)?

**Next**
- Stage 3 (normalize): Unicode NFC, strip U+0301, fix Latin/Cyrillic lookalikes, tidy whitespace; log every
  change and report volumes.
