# 2026-11-14 — CO.PRE.PAN backup calendar, CO.RA.PAN priority and acquisition-readiness closure

**Status:** `PARTIAL` · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-14 (Saturday; session from about 12:50 local, +01:00) |
| Kind | follow-up of the [readiness run of the same day](2026-11-14_coprepan-architecture-storage-contract-and-acquisition-readiness.md): implementation + offline validation + operator preparation (AGENTS §8). **No activation**, no gate closed, no request to any publisher, no canary |
| Status | `PARTIAL` — everything that needs no authorization and no real share run is done; the real evidence (the first scheduled incremental backup, the first intake under `intake-controller/2`) is still owed (§10) |
| External API | `EXTERNAL_API_USAGE = NONE` |
| Start | branch `main`, HEAD `965e31afe3f20e92c0dc6cc18bb99526f75993eb` = `origin/main`, clean |
| Work | worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\backup-calendar`, branch `readiness/2026-11-14-backup-calendar` |
| Operator brief | "CO.PRE.PAN_v3 – Backup-Kalender, CO.RA.PAN-Priorität und Acquisition-Readiness-Closure" (2026-11-14) |
| Decision | [CPD-0035](../decisions/CPD-0035_weekday-maintenance-calendar-transfer-priority-and-bounded-catch-up.md) (amends CPD-0033) |

## 1. Start state and sources

- **Git:** `main` = `origin/main` at `965e31a`, clean; four worktrees of earlier runs (`legacy-archive-contract`, `legacy-freeze`,
  `newfs-phase-b`, `newfs-phase-d`), untouched. No other CO.PRE.PAN session.
- **CO.PRE.PAN processes:** none. `COPREPAN_PreservationBackup`: daily 04:45, last run 2026-11-13 04:45 (result 0), one missed run
  (2026-11-14 04:45). The workstation restarted at 01:30 and 01:31 that night (System log 6005/6006); the task runs only while the
  account is logged on (`Interactive`) — the likely cause, **not established** (the Task Scheduler operational log holds no event).
- **CO.RA.PAN (read only):** production active throughout (the reservoir drive and its workers, an S3 stage on `D:`, the wave-4 live
  scheduler and preservation sidecar, the reconcile tick). Its observation of the share at 12:50 local: `mode NORMAL`, `reachable`,
  last probe 0.73 s, the outage of the morning (`AUTH_REFUSED` 06:57Z–08:03Z) caught up at 09:05Z. Read: its task list,
  `controller/preservation_mode_state.json`, `controller/backup_reconcile_log.jsonl`, `controller/preservation_mirror_reconcile_state.json`,
  `src/corapan_playground/storage/backup_reconcile.py` (schedule rules). Nothing started, stopped, changed or tested.
- **Read in CO.PRE.PAN:** the readiness report of the same day, CPD-0033, CPD-0034, `docs/STATUS.md`, `docs/storage/INDEX.md` §20–§21,
  `config/resource_policy.json`, the code of the resource policy, the backup, the manifest cache, the intake controller and its
  operator script, the plans and authorizations of October, the readiness and inventory files. A delegated read-only survey (one
  sub-agent, no network, no file changed) established the acquisition stock (§7).
- **Real backup basis** (read only, `D:`): the journal holds 8,816 evidence rows (all `COPIED`, all with `mtime_ns`), the receipt of
  2026-11-13 05:04Z is verified and names `coprepan-preservation-newfs` — the first incremental run will build on it (it does not fall
  back to anything).
- **Free space:** `C:` 304 GiB, `D:` 2,345 GiB (measured 2026-11-14 afternoon).

## 2. Decisions taken over and changed

Taken over unchanged: CPD-0033's floors (60 GiB), pending bounds (5,000 packs / 5 GiB / 72 h), share back-off (5 min doubling to
60 min), the evidence-reuse rule of the incremental backup, the fixity slice (300 objects / 256 MiB) and the rotating restore (10).
The pending bounds were checked against the data model: the 24-hour intake left 1,301 packs with the day 20261010, 2,204 sealed packs
hold 388 MB (176 KiB on average), so 5,000 packs are about 3.5 days of a full intake and under 1 GB; the 72-hour age bound binds
first, the 5 GiB bound practically never. Not widened.

Changed (CPD-0035, resource policy `2026-11-14.1` → `2026-11-14.2`): the maintenance calendar (§3); the quiet window of CO.RA.PAN's
reconcile now every night 01:15–07:45 (it was Wednesday only — refuted by CO.RA.PAN's log, §3); `receipt_warning_hours` (72) replaced
by missed weekday slots (§3); two new pending budgets (`catch_up_packs_per_hour` 200, `cache_warm_reads_per_hour` 1,200, §5); the
automatic FULL run abolished (§3).

## 3. The backup schedule

**From now on:** Monday–Friday, 08:00 on the wall clock of Europe/Berlin. Not on Saturday and Sunday.

Why 08:00 and not 04:45: CO.RA.PAN's backup reconcile is scheduled for Wednesday 02:00, but `backup_reconcile.due()` continues a run
in progress, and starts an overdue one, in **any** night window 01:30–07:30. Its log shows it: `rec20261107T011830Z` ran as `OVERDUE`
on 2026-11-07 01:18Z–06:28Z (interrupted at the deadline), continued on 2026-11-08 until 03:48Z (`RECONCILE_COMPLETE`, 6,564,127,607 B
copied). 04:45 is therefore inside CO.RA.PAN's night on every night; 08:00 is after it on every weekday. Daily 03:30 (local storage
maintenance) and Sunday 02:30/04:15 (repository health, historic backup) are also clear of it.

**Why a weekend can no longer start a backup on the share:** the calendar is in `config/resource_policy.json` and is enforced in
`resource_policy.maintenance_hold`, which every maintenance entry asks before any contact (`preservation_backup.py run` and `seed-cache`,
`preservation_audit.py`, and the stop predicate of a running backup). On a Saturday or Sunday in Europe/Berlin it answers
`SCHEDULED_PAUSE`, whatever started the process — the task, a late start after a missed weekday (`StartWhenAvailable`), a manual call.
The local day is computed by the EU summer-time rule in code (not the workstation's zone setting, not a time-zone database; a test
compares it with the database over four years). Only `--ignore-windows`, the operator's explicit order, overrides the calendar and the
quiet windows — never the pause file, CO.RA.PAN's observation, the share gate or a floor.

**Outcomes and health:** `SCHEDULED_PAUSE` · `DEFERRED_RESOURCE_PRIORITY` · `DEFERRED_SHARE_UNAVAILABLE` · `STOPPED` (exit 0) ·
`NEEDS_FULL_AUTHORIZATION` · `FAILED` (exit 1) · `BACKUP_VERIFIED`. The health keeps apart the last verified backup (with its real age),
the last attempt and the attempts since, the fixity rotation and the restore evidence, and counts **missed weekday slots** (a start plus
120 min that passed without a newer verified receipt): `WARNING` from 2, `FAILURE` from 5 or above 336 h whatever the calendar. Friday →
Monday is about 72 h and no slot; two weekdays without a backup are a warning whatever the reason. One deferral for CO.RA.PAN shows as a
missed slot and an attempt, without an alarm.

**Safety of the incremental backup, checked:** evidence is reused only under CPD-0033's conditions (unchanged); a normal run lists
both roots and re-reads only the fixity slice and the restore sample; an interrupted run writes no receipt (`ok` requires no stop, no
problem, a complete inventory — unchanged, tested). New: a scheduled run **never becomes a FULL run**: with no verified receipt of this
primary, with a journal that covers fewer objects than the receipt verified, or with more changed timestamps than one fixity slice, it
ends `NEEDS_FULL_AUTHORIZATION` before reading any object of the primary (tested: zero reads). Long-term coverage: 300 objects × 5 runs
a week cover the 8,816 objects of 2026-11-14 in about six weeks, inside the 90-day cycle; a corpus that grows by a full intake a day
would outgrow it — the status flags an overdue cycle (§10).

## 4. The scheduled task

`COPREPAN_PreservationBackup` (installed by CO.RA.PAN's `scripts/install_holding_backup_tasks.ps1`; that script is untouched). Changed
by this run with `Set-ScheduledTask`, the trigger only, while the task was `Ready` (nothing running):

| | Before | After |
|---|---|---|
| Trigger | `CalendarTrigger`, `ScheduleByDay` interval 1, StartBoundary `2026-10-19T04:45:00+01:00` | `CalendarTrigger`, `ScheduleByWeek` Monday–Friday, interval 1, StartBoundary `2026-11-16T08:00:00` |
| Zone | the `+01:00` offset pins one UTC instant: 04:45 in winter, **05:45 in summer** | no offset: 08:00 local all year |
| Next run | 2026-11-15 04:45 (a Sunday) | 2026-11-16 08:00 (Monday) |
| Action, account, settings | `pythonw.exe scripts\preservation_backup.py run --evidence-dir …\work\preservation_backup_runs` (the main checkout), `Interactive`, `Limited`, `IgnoreNew`, `PT6H`, `StartWhenAvailable` | unchanged |

`python scripts/preservation_backup.py schedule` (new, read-only) reads the task definition and compares it with the calendar:
`consistent: true` after the change (before it: two problems, the days and the time). The XML of both states was exported before and
after the change (kept in the session's scratch directory, not in the repository).

## 5. CO.RA.PAN's priority and the preservation rules

Taken from CO.RA.PAN's own code and state file (`corapan-preservation-mode/v1`, its `reachable`, `mode`, `share_slow`, `verdict`); no
unversioned field added; the advisory remains caution-only.

| CO.RA.PAN state (fresh) | New share I/O of CO.PRE.PAN (transfers) | Local acquisition (fetch, pack, spool) | Maintenance |
|---|---|---|---|
| `DEGRADED` / unreachable | held, no contact, until CO.RA.PAN's next probe | within the pending bounds | `DEFERRED_SHARE_UNAVAILABLE` |
| `RECOVERING` | **held** (new: before only maintenance waited) | within the pending bounds | `DEFERRED_RESOURCE_PRIORITY` |
| `SHARE_SLOW` | **held** (new) | within the pending bounds | `DEFERRED_RESOURCE_PRIORITY` |
| `NORMAL` | within CO.PRE.PAN's limits (the catch-up budget, the gate) — it permits nothing by itself | yes | by the calendar and the windows |
| no signal / unreadable / unrecognised / stale | the policy's own limits only | within the pending bounds | by the calendar and the windows |

Mechanics: the share gate has a `transfer` purpose (`ShareGate.closed_because(transfer=True)`, `guard(..., transfer=True)`, used by
`scripts/intake_operator.py`); it also holds while `PAUSE_IO` exists. A held transfer is a refusal of the root without a contact; the
pack stays honestly `PRESERVATION_PENDING` in the workspace and the spool (P4/P5). A failed contact still closes the gate with the
persisted back-off, so `AUTH_REFUSED` is never retried by CO.PRE.PAN in a loop; no credential mechanism, no `net use`, no SMB session
is touched by any code of this run. The finalizer waits with the gate (one log line when the reason changes; the intake is disarmed at
its deadline regardless). **Bounded return:** pending packs come from the ledger (not a read of every pack); the backlog is preserved
oldest first, at most 200 packs an hour, counted in the intake's state file (a restart does not refill it), the first pack that stays
pending ends the batch; after the deadline the tick drains the backlog the same way before the finalizer. **Cache warm-up:** a
promotion reads at most 200 new manifests from the share and otherwise defers (`CacheIncomplete`); the controller warms the cache at
most 1,200 reads an hour; `preservation_backup.py seed-cache` fills it from the verified BACKUP root without the share, taking a manifest
only when its bytes hash to the journal's digest.

Proposal to CO.RA.PAN (unchanged in substance from the readiness run §10.3, extended): declare `preservation_mode_state.json` a
read-only interface with a schema version, the fields `reachable`, `mode` (`NORMAL`, `RECOVERING`, `DEGRADED_*`), `share_slow`,
`last_probe_utc`, `next_probe_after_utc`, and add one field for its night activity (`night_run_active` or the reconcile's
`current.run_id`), so CO.PRE.PAN could defer exactly instead of by a fixed window.

## 6. Acquisition improvements and the prepared configuration

Repairs in the agreed scope (no access, robots or TDM decision changed; no publisher released):

- **No full pack read per decision point.** `canary_driver.pending_pack_ids` reads the ledger (the `PRESERVATION_PENDING` transition
  names its pack); before, every decision point of an intake with anything pending read every pack of the workspace end to end
  (`packs_holding`). Measured on the real workspace (read only, local `C:`, warm cache): 1.97 s for the 2,204 packs before, 0.18 s for
  the ledger — small locally, but linear in the corpus and repeated every 5 minutes while an intake is held.
- **Bounded catch-up, drain and cache warm-up** (§5), restart-safe.
- **Log growth:** the controller log is kept to 4 MiB and one previous generation; an unchanged hold is logged once instead of every
  five minutes; the tick of a waiting finalizer writes one line when its reason changes instead of a traceback per tick.
- **An operations block** in `python scripts/storage_contract.py status` → `operations` (§6 of the brief): acquisition
  `DISABLED`/`READY`/`RUNNING`/`PAUSED`/`DEGRADED`/`BLOCKED`, the qualified stock, the intakes, the last recorded request, pending
  preservation and its age, free-space floors, share gate, new transfers, CO.RA.PAN's advisory, backup level, age, missed slots, last
  attempt, next scheduled start, and the actions that need a person (`none` otherwise). Local files only, no tree scan.

Robustness review of the fetchers (read-only survey, file and line in the session's evidence): timeouts (one socket timeout of 30 s
for connect and each read; no total per request — a gap, bounded in practice by the 8 MiB body cap and the pacing), 429 and 403 hold
the origin or URL without a retry, 5xx and timeouts are recorded and retried by the schedule (1 h, doubling, suspended for 7 days after
three), `Retry-After` is honoured as not-before, one request at a time with at least 10 s per origin (Crawl-delay up to 60 s), at most 3
redirects each re-checked by the policy, an 8 MiB body cap, short reads and malformed HTTP are failures, candidates are deduplicated by
canonical URL across runs, `utm_` stripped and http upgraded, documents and versions are stable identities, one outlet's error is that
outlet's (the intake stops only when more than a third fail in one cycle), quarantine through the policy's lists. **Open, not repaired
(they are decisions, not defects):** an evidence-derived hold never expires and has no recorded lifting path; a changed feed URL needs a
registry change; channel polls do not back off after failures; there is no per-outlet budget for non-item requests (only the total and
the discovery limits). None of them endangers a bounded canary.

**Prepared:** [`docs/intake/canary/in2-20261114-canary_PREPARATION.md`](../intake/canary/in2-20261114-canary_PREPARATION.md) and
`config/intake/plans/in2-20261114-canary.json` (`plan_sha256` `b39ae894…dc3f`, `intake-controller/2`, `canary/2026-10-10.1`): seven
outlets in seven countries covering RSS, RSS + news sitemap, RSS + sitemap index, sitemap only, a section page with its reviewed
candidate rule, and a Crawl-delay of 20 s; 3 h, cycles of 1 h, at most 300 requests, 15 item requests per outlet, 6 per outlet-hour, 20
per origin. Validated offline: `validate_plan` **PASS** against the registry, the acquisition policy and the 20 holds derived from every
stored answer of the workspace (none on the plan; 22.1 s, local). The authorization is a deliberately invalid
[draft](../intake/canary/in2-20261114-canary_AUTHORIZATION_DRAFT.json) for the operator; stop/resume/rollback, abort criteria and the
concept of the next wave with its release criteria are in the preparation document. The frozen baseline is written by `start` (it pins
the arming commit, the test run, the authorization, the plan, the resource policy file among the configuration, the target identity);
it cannot be made before the authorization without inventing it.

## 7. Sources and intake readiness (current, from files)

| Fact | Value | Source |
|---|---|---|
| Outlets registered / proposed | 114 / 12 (126), 20 countries | `config/outlet_registry.json` (sha `7470d583…b9bb8`, unchanged since 2026-10-11) |
| Qualified for intake | 87 outlets (85 tier A, 2 tier B), 121 channels: RSS 72, sitemap 36, sitemap index 11, section page 2 | `config/intake/intake_readiness_2026-10-10.1.json` |
| Countries in the readiness file | 20: ar 7, bo 2, cl 5, co 5, cr 1, cu 4, do 4, ec 6, es 5, gt 5, hn 6, mx 1, ni 3, pa 8, pe 6, pr 3, py 4, sv 2, uy 3, ve 7 | same |
| Held | 17 outlets (10 origins, 9 URLs) in the readiness file, plus `efectococuyo.com/rss` since the 24-hour intake; 20 holds derived from the stored evidence on 2026-11-14 | readiness file, `config/source_discovery/access_holds_2026-10-10.json`, the workspace |
| Last real acquisition | 2026-10-11 10:52 local (the end of `in1-20261010-24h`); nothing fetched since; nothing preserved on the share since 2026-10-18 | workspace file times; the backup receipt of 2026-11-13 (8,816 objects, the tree of the cutover) |
| The 24-hour intake | `COMPLETED`, verification `PASS`: 7,173 of 12,000 requests, 3,691 item pages, 3,681 answered 2xx, 85 of 87 outlets with pages, 1 hold arose, 0 restarts | `docs/intake/reports/in1-20261010-24h/` |
| Qualified since 2026-10-10 | nothing | git log of `config/intake`, `config/source_discovery` |
| `OPERATIONALLY_STABLE` | 0 outlets (it needs three verified runs on three days, CPD-0025); the readiness file predates the 24-hour intake and was not rebuilt | inventory, readiness builder |
| Valid authorization today | none (both October records expired 2026-10-11 and name `/1` plans) | `config/intake/authorizations/` |

Known problem sources (left out of the canary): `pe_elperuano` (robots unreachable at every poll), `hn_radio_progreso` (no new page in
24 polls), 17 outlets whose channels give no dates (stock pages only), the anomaly flags of October (71 empty, 223 very short extractions).

## 8. Tests, benchmarks, results

All temporary directories on `C:` (`--basetemp`); no test touched a storage root, `D:` or the share.

| Run | Result |
|---|---|
| new and changed tests (`tests/test_resource_isolation.py`): calendar incl. weekend, local midnight, the spring switch night and the four-year comparison with the time-zone database; quiet windows on the Berlin wall clock (winter and summer); health by missed slots; `NEEDS_FULL_AUTHORIZATION` without reads (missing receipt, torn journal, mass restamp) and in the CLI; transfers held for slow/recovering/degraded with no contact; no/unreadable/stale signals; cache seeding (tampered copy refused, resumable) and the bounded warm-up; an intake through `RECOVERING` (local acquisition on, zero share contacts) and its bounded catch-up and drain across processes to a `PASS` finalization; pending packs from the ledger without a pack scan; the task-definition check | 54 passed (19.4 s; on `main` before this run the file collected 27 tests) |
| `tests/test_primary_backup.py` (the first CLI run now needs `--full`) | 13 passed |
| full suite (the gate before integration; temporary directories on `C:`) | 1,892 passed, 14 skipped (606.6 s) — the readiness run's final gate was 1,863 passed, 14 skipped |

Benchmarks: the pack-scan measurement of §6; the isolated backup benchmark of the readiness run (300 / 320 reads instead of 8,817) stays
valid and was not repeated. No benchmark ran on the share or on `D:`.

## 9. Real backup and share evidence

- **Share:** reachable at the time of this run in CO.RA.PAN's observation (`NORMAL`, probe 0.73 s at 11:50Z); the morning's outage
  (06:57Z–08:03Z, `AUTH_REFUSED`) caught up at 09:05Z. CO.PRE.PAN did not contact the share in this run (the plan validation, the cache
  and the benchmark read local files; the status block resolves the root once, through the gate).
- **Incremental backup:** **none has run yet.** The task did not run on 2026-11-14 (§1); its next start is Monday 2026-11-16 08:00 on the
  new code. No backup was started by this run (a Saturday — the calendar's pause applies to its author too). The real basis is intact
  (§1), so that run will be incremental.
- **New acquisition or preservation events:** none since 2026-10-18 (preservation) and 2026-10-11 (acquisition).

## 10. Real production evidence still owed

1. The first scheduled incremental backup (2026-11-16 08:00): read `_backup/last_run.json`, the receipt and `preservation_backup.py
   status`; it is the first real measurement of CPD-0033's load reduction.
2. `seed-cache` on the real BACKUP root (a weekday).
3. The first intake under `intake-controller/2` with a production write on the share — including, if it happens, a real `SHARE_SLOW`
   or `RECOVERING` of CO.RA.PAN and the catch-up afterwards.
4. Non-impairment of CO.RA.PAN under concurrent load: **not measured**, constructed and tested offline only.
5. The fixity rotation's capacity once the corpus grows (a new policy version when the status flags an overdue cycle).

## 11. Open operator gates

1. **The authorization of the canary** `in2-20261114-canary` (fill and commit the draft, then `start`) — the next decision.
2. Then, separately: a 24-hour wave under `/2` (concept prepared), and only after its criteria the gate O-1 (a production schedule) and
   any recurring acquisition.
3. Optional: review the scheduled-task change (§4) and the calendar's 08:00.
4. To CO.RA.PAN (a proposal, its decision): §5's interface.

## 12. Commits, merge, push

[[GIT]]

## 13. Processes

Running at the end: none of CO.PRE.PAN's. Not started on purpose: no intake, no canary, no backup run, no `seed-cache`, no audit, no
benchmark on the share or `D:`. Scheduled: `COPREPAN_PreservationBackup`, Monday–Friday 08:00 (next 2026-11-16 08:00). CO.RA.PAN's
processes and tasks: untouched.

## 14. What this report does not claim

That CO.RA.PAN is unimpaired under real concurrent load (not measured); that the incremental backup has run on the real roots (it has
not); that any acquisition is authorized (none is); that the values of the policy are optima (they are scenario assumptions from the
evidence named in its `basis`).
