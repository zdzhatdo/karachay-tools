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
