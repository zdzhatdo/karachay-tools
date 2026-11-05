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
