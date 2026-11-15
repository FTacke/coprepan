# CPD-0037 — Workspace checks that scale with what is new; an intake controller that interleaves outlets

| Field | Value |
|---|---|
| Date | 2026-11-15 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Execution | implemented and tested offline (`tests/test_incremental_check.py`, `tests/test_intake_interleaved.py`, the existing intake and evidence suites). `canary-driver/8` and `intake-controller/3`. **Neither has run against a real outlet yet**: the weekend waves ran under `canary-driver/7`, and no intake has run since 2026-10-11 |
| Builds on / amends / supersedes | builds on CPD-0009 (recovery), CPD-0010 (chained evidence and heads), CPD-0029 (the bounded intake), CPD-0033 (resource isolation), CPD-0036 (qualification waves); amends nothing; supersedes nothing |
| Does not change | `recovery.diagnose` (the full audit, unchanged and still the authority on every finding); the storage contract; P2 (`RAW_PRESERVED` only after the bytes are re-read on the primary); the finalizer's and the canary evidence check's audits; every request limit, pacing rule, Crawl-delay, hold and access decision; `intake-controller/2` and its plans (the prepared canary `in2-20261114-canary` is a /2 plan and runs /2's code unchanged) |
| Decided by | the operator's brief of 2026-11-15 ("CO.PRE.PAN_v3 – Autonome Qualitäts- und Performance-Optimierung bis zur produktionsreifen Vorzugslösung", §8–§10: "wiederholte vollständige Workspace-Prüfungen eliminieren … Outlet-Interleaving statt unnötiger sequenzieller Wartezeit"); the form is the commissioned agent's |
| Run report | `docs/agent-runs/2026-11-15_coprepan-weekend-source-qualification.md` |

## Context

Measured on the weekend waves (`scripts/measure_weekend_capacity.py`): about three quarters of a wave's wall time lay between
fetch records -- the driver's checkpoints, each a whole-workspace `recovery.diagnose` (234 s once on 6,825 pack files: 58,000 file
opens, every sealed pack re-hashed, every layer re-read, every closed run's anchors against whole tables), 2 + 2 × outlets times a
wave; the intake controller runs one per hourly cycle. The transport itself took well under a second per request; the request
time of the canary measurements is the 10-second pacing wait plus the transport (`fetch_started_at` is taken before the pacing).
The October intake served the outlets one after another, so each origin's 10 seconds were waited out in sequence.

## Decision

1. **Incremental check** (`incremental_check.checkpoint`, `incremental-check/1`). Between stages a writer checks what was appended
   since the last verified point: append-only tables from an anchor (size, rows, hash and length of the last verified line; the
   anchor line re-read; the tail parsed and, where chained, authenticated); sealed packs verified once and then not re-hashed on the
   fast path; open packs scanned; ledger transitions, the ledger-to-pack relation, request intents, candidates and identity rows
   checked row by row against the derivation state of the earlier rows; closed runs' heads against the anchors and the tail.
2. **The full audit decides every finding.** Whatever the incremental check meets that it does not classify -- a broken anchor, a
   torn tail, a chain break, a pack that does not verify, an unfitting ledger transition, an unsupported candidate, any exception --
   runs `recovery.diagnose` and returns its classification. The incremental check alone only ever answers `CLEAN` or
   `INCOMPLETE_RESUMABLE`.
3. **Fixity of unchanged objects** is covered off the fast path: every incremental check re-verifies a bounded number of the
   longest-unaudited sealed packs (8, at most 64 MiB) and layer answers (32) -- a guaranteed share, so the rotation is never starved
   (the lesson of CO.RA.PAN's H-01) -- and a full audit runs when there is no valid check state, after any finding, and when the last
   full audit is older than seven days. **Stated boundary:** an in-place change of an old, verified object that keeps its size is
   found by the rotating audit when it comes round, or by the weekly audit -- not by the fast path (tested).
4. **The check state is a cache, never evidence.** `checks/verified-<n>.state`: chained JSON lines, one row per check, not a
   workspace table (`*.state`, so a damaged cache never makes the workspace look damaged). Missing, torn, broken or of another
   version: the next check is a full audit and a new file; the old one is kept. A file extended by another process is not extended
   again (that process's state is dropped). Loaded once per process.
5. **`canary-driver/8`** uses it at every checkpoint and reads the discovery tables once per run (the driver is the only writer
   while it runs).
6. **`intake-controller/3`**: a cycle polls the outlets one after another, then requests their items round the outlets, one item per
   outlet and turn (consecutive requests go to different origins; one request at a time; every interval and Crawl-delay as before);
   an allowance per outlet in the plan (items per cycle, per hour, in all; none above the budget's); items still due at a cycle's end
   stay due and are counted in the state; an optional drain period at the end of an intake polls nothing; the check after a cycle
   is incremental; the request log (`RequestLog`), the qualification table and the ledger (`Ledger.refresh`) are held across the
   calls of the process, each read in full once and then extended by its authenticated tail. New plans are /3; a /2 plan runs /2.

## Evidence (offline)

- Faults injected after a verified point -- torn tails, chain breaks, a changed anchor row, a cut table, a duplicate event with a
  valid chain, a lost pack, a new pack that does not verify, an unfitting ledger transition, an unsupported candidate, an
  interrupted request, a damaged/torn/foreign check state, a second writer of the state -- each ends in the full audit's
  classification (31 tests). A whole canary run on a growing workspace: one full check, then only incremental ones, agreeing with
  a full audit at the end.
- Synthetic inventories (`scripts/benchmark_workspace_checks.py synthetic`, local disk): the incremental check with nothing new
  took 0.06 s at 10,000 verified packs, 0.14 s at 50,000 and 0.29 s at 100,000, opening no file and verifying no pack (what remains
  linear is the listing of the pack directory's names, about 3 µs a name); loading the persisted state once per process took
  0.02 / 0.08 / 0.17 s (1.8 / 8.9 / 17.8 MB).
- Two loopback outlets at the production policy's 10 s interval, a clock that moves only while waiting: the pacing waits of the
  same twelve items fell from 140 s (/2) to 80 s (/3); each origin's releases stayed at least 10 s apart.
- Every existing intake test passes on a /3 plan.

## Alternatives considered

- **A cache rebuilt at every check** (e.g. a fresh index of every pack): the same linear cost in another place; rejected by the brief
  and by measurement.
- **Checking only the run's own packs and nothing else** (no anchors, no derivation state): misses a lost or damaged earlier object
  and a duplicate written with a valid chain; rejected.
- **Trusting size and mtime of old packs** (CO.RA.PAN's stat signature): stat calls on every pack are still linear, and for
  write-once packs whose identity is their manifest digest the signature adds little; replaced by not touching verified packs on the
  fast path plus the rotating audit.
- **Threads or several processes for interleaving**: the workspace's tables, ledger and packs are single-writer; rejected in favour of
  round-robin slices in one process, one request at a time.

## Not decided here

The canary budget split for outlets with two origins (`cr_crhoy`, run report §12); a `paced_until` instant in the fetch record (a
schema change); the authorisations of the first canary under `canary-driver/8`, the first intake under `intake-controller/3` and the
24-hour wave.

## Validation debt

The first real canary under `canary-driver/8` and the first intake under `intake-controller/3` (each needs its own authorisation);
the before/after on a copy of the real workspace is in the run report §7.
