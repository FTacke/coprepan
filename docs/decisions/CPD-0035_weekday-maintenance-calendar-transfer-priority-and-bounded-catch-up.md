# CPD-0035 — Weekday maintenance calendar; CO.RA.PAN's priority over new preservation transfers; bounded catch-up; no surprise FULL run

| Field | Value |
|---|---|
| Date | 2026-11-14 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Execution | implemented and tested offline (`tests/test_resource_isolation.py`, the existing suites); resource policy `2026-11-14.2`; the scheduled task `COPREPAN_PreservationBackup` re-timed to Monday–Friday 08:00 (before: daily 04:45). **Nothing of it has run against the institutional share yet**: the first run under it is the scheduled one of Monday 2026-11-16 08:00, and acquisition stays `disabled` |
| Builds on / amends / supersedes | builds on CPD-0033 (resource policy, share gate, sibling advisory, incremental backup, `intake-controller/2`), CPD-0015 (P2/P4/P5), CPD-0029; amends CPD-0033 in five points (decisions 1–5 below); supersedes nothing |
| Does not change | the joint storage contract (bundle `49a3ca88…afb036`); P2 (every `RAW_PRESERVED` still needs the bytes re-read on the primary past the client cache); any root, identity marker, object, pack, index or manifest; the acquisition policy (`external_acquisition: disabled`) and every access, robots and TDM decision; any gate of `docs/STATUS.md` §5; the pending bounds (5,000 packs, 5 GiB, 72 h) and the free-space floors (60 GiB) of CPD-0033 |
| Decided by | the operator's brief of 2026-11-14 ("CO.PRE.PAN_v3 – Backup-Kalender, CO.RA.PAN-Priorität und Acquisition-Readiness-Closure"), which sets the weekday rule (§2.1) and the priority table (§3.1); the times, budgets and thresholds are the commissioned agent's, from the evidence named in `config/resource_policy.json` `basis`, stated as scenario assumptions |
| Sister decision | none. CO.RA.PAN is unchanged (read-only in this run) |
| Run report | [`2026-11-14_coprepan-backup-calendar-acquisition-readiness-closure.md`](../agent-runs/2026-11-14_coprepan-backup-calendar-acquisition-readiness-closure.md) |

## Context

CPD-0033 bounded CO.PRE.PAN's shared I/O and made the regular backup incremental. Five gaps remained, found on 2026-11-14:

- **The weekend.** CO.RA.PAN often processes large holdings at the weekend (operator, 2026-11-14). The backup task fired every day at
  04:45; on Sunday the policy deferred it (CO.RA.PAN's historic backup), on Saturday nothing did. A task that fires late
  (`StartWhenAvailable`) could start on any day.
- **04:45 is inside CO.RA.PAN's night window on every night, not only on Wednesday.** CO.RA.PAN's backup reconcile
  (`src/corapan_playground/storage/backup_reconcile.py`, read-only) is scheduled for Wednesday 02:00, but a run in progress or an
  overdue one continues in **any** night window 01:30–07:30; its log shows an `OVERDUE` run on 2026-11-07 01:18Z–06:28Z continued on
  2026-11-08 until 03:48Z (6.56 GB copied). CPD-0033's Wednesday-only window missed that.
- **Transfers.** CO.RA.PAN's `SHARE_SLOW` and `RECOVERING` deferred CO.PRE.PAN's maintenance, but not a new preservation transfer.
- **Catch-up.** At every decision point an intake preserved *every* pending pack at once, and found them by reading every pack of the
  workspace end to end (2,204 packs, 388 MB). After an outage the return of the share meant a burst; the end of an intake (the
  finalizer) preserved only open packs, so a remaining backlog either went at once or left the receipt `PARTIAL`.
- **Surprises.** A scheduled backup run without a verified receipt turned itself into a FULL run (CPD-0033 run, 2026-11-14), i.e. the
  78-minute whole-primary read over the share; a damaged journal or a mass change of timestamps would have done the same. And the
  first promotion with an empty manifest cache would have read all 4,408 manifests of the share (about 19 minutes at 260 ms each).
  No cache existed in the workspace on 2026-11-14.

## Decision

1. **A maintenance calendar in the resource policy, enforced in code.** `maintenance_calendar`: zone `Europe/Berlin` (computed by the
   EU summer-time rule in `resource_policy.local_time`, independent of the workstation's zone setting and of a time-zone database;
   a test compares it with the database over four years), days Monday–Friday, scheduled start 08:00. Outside the days every
   automatic maintenance on shared storage (backup, fixity, restore, the audit, the cache seeding) ends `SCHEDULED_PAUSE` before any
   contact. The quiet windows are on the same wall clock; the reconcile window is now every night 01:15–07:45. 08:00 is after
   CO.RA.PAN's night window on every weekday. `--ignore-windows` (the operator's explicit order) overrides the calendar and the
   windows only — never the pause file, CO.RA.PAN's observation, the share gate or a floor. The task's trigger is weekly Monday–Friday
   with a start boundary **without a zone offset** (08:00 local all year; the old `+01:00` boundary pinned a UTC instant, 05:45 in summer).
2. **Outcomes and health that separate a planned pause from a failure.** `_backup/last_run.json` records `SCHEDULED_PAUSE`,
   `DEFERRED_RESOURCE_PRIORITY` (a window, CO.RA.PAN slow or recovering, the pause, a floor, another run), `DEFERRED_SHARE_UNAVAILABLE`
   (refused, degraded, the gate backing off), `STOPPED` (time budget), `NEEDS_FULL_AUTHORIZATION`, `FAILED`, `BACKUP_VERIFIED`, and the
   last 20 attempts. The health keeps four facts apart — the last verified backup and its real age, the last attempt and the attempts
   since, the fixity rotation, the restore evidence — and counts **missed weekday slots** (a scheduled start plus 120 min grace that
   passed without a newer verified receipt): `WARNING` from 2, `FAILURE` from 5 (a working week) or above 336 h whatever the
   calendar, on a failed run, or when the basis needs the FULL order. A weekend has no slot: Friday's backup is not late on Monday
   morning (72 h); two weekdays without one are, whatever the reason. The 72 h warning of CPD-0033 is replaced by this count, not
   lengthened.
3. **No surprise FULL run.** A scheduled run never turns itself into a FULL run. It ends `NEEDS_FULL_AUTHORIZATION` (exit 1, health
   `FAILURE` with the operator action), before reading any object of the primary, when there is no verified receipt of this primary,
   when the backup journal holds evidence for fewer objects than the receipt verified (a damaged basis), or when more objects than
   one run's fixity slice show another size or timestamp than their evidence (a systemic change of a write-once primary). New
   objects stay the incremental run's work, bounded by its rate and time budget and resumable.
4. **CO.RA.PAN's priority over new transfers; four kinds of I/O.** The share gate has a `transfer` purpose (`ShareGate.closed_because(
   transfer=True)`, `guard(..., transfer=True)`, used by `scripts/intake_operator.py`): a new preservation transfer waits — without a
   contact — while CO.RA.PAN's fresh observation is degraded, **slow or recovering**, and while `PAUSE_IO` exists. Local fetching and
   local spooling go on within the pending bounds and the RUNTIME floor (unchanged); maintenance waits for everything of decision 1
   too. A missing, unreadable, unrecognised or stale signal permits nothing beyond the policy's own limits, and a normal one permits
   nothing either. The finalizer waits with the gate (one line in the log when the reason changes, no traceback per tick); the intake
   is disarmed at its deadline regardless.
5. **Bounded catch-up and a bounded cache warm-up.** The controller finds pending packs in the ledger (the transition to
   `PRESERVATION_PENDING` names its pack), not by reading every pack. While the gate is open it preserves the backlog oldest first, at
   most `catch_up_packs_per_hour` (200) packs per hour, counted in the intake's state file (a restart does not refill it); the first
   pack that stays pending ends the batch. The same step runs after the deadline (`intake.drain`, from the tick) until the backlog is
   empty, then the finalizer. A promotion reads at most 200 new manifests from the share to bring the manifest cache up and otherwise
   defers (`CacheIncomplete`: the pack stays honestly pending); the controller warms the cache at most `cache_warm_reads_per_hour`
   (1,200) reads per hour; `scripts/preservation_backup.py seed-cache` fills it from the verified BACKUP root without the share,
   taking a manifest only when its bytes hash to the journal's digest. The controller log is kept to 4 MiB and one generation, and an
   unchanged hold is logged once.

## Why it satisfies the contract

P2 is unchanged: every `RAW_PRESERVED` is still a re-read of both masters on the primary. P4/P5: a deferred transfer is an honest
`PRESERVATION_PENDING`, local copies verified and kept, inside the bounds of CPD-0033. I2: a held gate is a refusal, never an empty
root. A cache entry is used to *find* a duplicate; a promotion binds to it only after verifying the holder's master on the root, as
before; an incomplete cache never answers. B1–B6 are unchanged: an incremental receipt is still produced from the primary and verified
against it, and a basis that cannot carry that is refused rather than rebuilt silently.

## Alternatives considered

- **Keep 04:45 and add a daily night window.** Every start would have been a deferral: no backup at all.
- **A Wednesday-only window (CPD-0033).** Refuted by CO.RA.PAN's own log (an overdue reconcile on Friday and Saturday night).
- **Reading CO.RA.PAN's reconcile state to know when its night is free.** Not a declared interface; one more file read in one direction
  would not change that. Proposed to CO.RA.PAN instead (run report §11).
- **Lengthening the 72 h warning to cover the weekend.** It would also hide two missed weekdays; the slot count does not.
- **`zoneinfo` for Europe/Berlin.** Needs time-zone data that Windows does not ship and this project does not declare; the EU rule is
  five lines and is checked against the database where it exists.
- **An automatic FULL run "once".** A 78-minute read of the shared link, started by a scheduled task on a day nobody chose.

## Not decided here

The production schedule of acquisition (O-1); a recurring crawl; any authorization of an intake; the values as optima (they are
scenario assumptions until the first real runs measure them); how CO.RA.PAN could declare its observation and night window as an
interface; the growth of the fixity rotation with the corpus (300 objects × 5 runs a week cover the 8,816 objects of 2026-11-14 in about
six weeks, inside the 90-day cycle; a corpus growing by a 24-hour intake's 1,300 packs a day would not be covered — the status flags
an overdue cycle, and the policy then needs a new version).

## Validation debt

- The first scheduled incremental run on the real roots (Monday 2026-11-16 08:00): its `_backup/last_run.json` and receipt are the
  first real evidence of CPD-0033 and of this calendar.
- A real intake under `intake-controller/2` with a production write on the share, during a real `SHARE_SLOW` or `RECOVERING` of
  CO.RA.PAN, and its catch-up afterwards.
- Non-impairment of CO.RA.PAN under concurrent production load is **not measured**; it is constructed and tested offline.
- `seed-cache` against the real BACKUP root (a weekday, local reads of about 4,400 manifests on `D:`).

## Amendment of 2026-11-14 (the source-health run; resource policy `2026-11-14.3`)

1. **The calendar's start.** `maintenance_calendar.effective_from` (2026-11-14): the calendar counts no slot before the day it came into
   force. Found on the real roots: the last verified receipt (Friday 2026-11-13 05:04Z, 06:04 local, under the old daily 04:45 task)
   precedes Friday's 08:00 slot of a calendar that did not exist then, and the status showed it as one missed weekday slot. The real
   age of the backup is unchanged in the status; every real slot from 2026-11-16 on counts as before (tested: Monday 10:01 without a
   verified backup is one missed slot, Tuesday two and `WARNING`).
2. **The end-to-end request timeout.** `FetchLimits.total_seconds` bounds one request in all (120 s in `CANARY_LIMITS`, the limits of
   every canary and intake) besides the 30 s per socket operation; pinned in the intake's baseline block with the other fetch limits.
   A slow-drip server could before hold one request open for as long as the 8 MiB body limit allowed.
