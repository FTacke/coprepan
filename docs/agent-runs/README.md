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
