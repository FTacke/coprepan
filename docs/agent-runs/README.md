# Agent run reports

One dated Markdown file per run: `YYYY-MM-DD_short-descriptive-title.md`. Created at the start of
the run and updated while working. Compact enough to share on its own.

**A run report is a historical record of one execution, never a specification.** A recommendation
in a run report is not a decision; an old result is not a current configuration. Reports are not
rewritten later: a correction is a dated note in a later report, at most with a forward pointer
added to the old one. Negative results and failed runs are kept.

## Header

```text
run_started_at:      2026-10-06T16:24:05+02:00
run_ended_at:        2026-10-06T17:40:00+02:00
timezone:            Europe/Berlin
wall_clock_seconds:  4555
```

- ISO-8601 with UTC offset, never a naive local time; the IANA zone alongside, because an offset
  does not name a zone. `wall_clock_seconds` is computed from the two instants.
- Record only times actually read from a clock. Do not invent a start or end time; say when a
  value is the first or last clock reading rather than the true boundary.
- A status line: `PASS` / `PARTIAL` / `FAIL` / `BLOCKED`, and **what the status does not claim**.
- The **kind of run**: diagnosis, implementation, scientific validation or production activation.
- `EXTERNAL_API_USAGE = NONE` when no external call was made. A run that says nothing about
  external usage and a run that provably made none are different.

## Content

Record what a later reader needs to reproduce and trust the run:

- objective and operator brief;
- repository states at start (HEAD and working tree of this repository and of every reference
  repository touched read-only; foreign changes already present);
- inputs inspected;
- files created or changed; **whether anything was moved, deleted or overwritten**;
- infrastructure reused or adapted, and infrastructure deliberately not adopted;
- commands and checks run, with their results — including failures;
- measurements, each labelled measured / sourced / estimated / scenario assumption / unknown;
- assumptions and unresolved decisions;
- gates touched and their state;
- working-tree classification at the end;
- exactly one recommended next run;
- the operator report.

## Delivery on `main` (since 2026-10-22)

The report is written and committed on the run's branch and **published on `main`** with
`python scripts/publish_run_report.py publish docs/agent-runs/<file>.md --status <PASS|PARTIAL|FAIL|BLOCKED|IN_PROGRESS>`
(AGENTS §16). The publication is a documentation-only commit (trailer `Published-By: publish_run_report`) that adds
the report as committed on the branch and its row in the generated `docs/agent-runs/INDEX.md`; `--status` must equal the
report's own `Status:` line, and the report must carry its `EXTERNAL_API_USAGE` statement. Publishing the same bytes
again changes nothing; a report already on `main` with other bytes is replaced only with `--update`; a change in the
main checkout at either path, or a `main` that moved meanwhile, refuses the publication. `check` lists reports of a
branch that `main` lacks or holds differently.

One run, one consolidated report: detail reports of sub-agents and scratch notes stay in the session's scratch space
and are folded into the canonical report with the evidence its statements rest on (file and line, digests, counts).
A scratch file is kept, or its content moved into the report, as long as it is the only basis of a statement.

The report states, as separate facts: published on `main`; committed (branch, commit); merged into `main`; pushed
(`main`, branch); worktree removed or kept (and why).
