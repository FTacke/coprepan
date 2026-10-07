# Repository Instructions

Read and follow [`AGENTS.md`](AGENTS.md) before doing any work in this repository. It is the only
set of agent rules; this file only points to it.

**This is a foundation, not a pipeline.** Read [`docs/STATUS.md`](docs/STATUS.md) before assuming
anything is built, and start navigation from
[`docs/architecture/INDEX.md`](docs/architecture/INDEX.md).

The rules most often broken, in one place:

- The reference repositories (under `C:\dev\panhispanic_media_corpora\`: `legacy\coprepan`,
  `corapan`, `legacy\corapan_coprepan_studies`; and `C:\dev\corapan`) are **read-only**. Never run
  the legacy test suite; never open a legacy SQLite database in place.
- **No live network**: no crawl, no feed or sitemap fetch, no external API — the acquisition gates
  are open.
- **Never use heredocs (`<<EOF`) or PowerShell here-strings (`@'…'@`)** on this Windows setup. Use
  the edit/write tools or a script file; commit messages via `git commit -F <file>`.
- Commit only when asked, with explicit pathspecs; never `git add -A`.
- Never invent a number; never guess an open operator or institutional decision.
- Give every run exactly one dated report under `docs/agent-runs/`.
