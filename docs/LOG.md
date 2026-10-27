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
