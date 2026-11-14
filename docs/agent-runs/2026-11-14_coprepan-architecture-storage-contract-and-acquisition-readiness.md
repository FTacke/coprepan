# 2026-11-14 — CO.PRE.PAN architecture, storage, contract and acquisition-readiness run

**Status:** `PARTIAL` · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-14 (session from about 07:58 local, +01:00) |
| Kind | diagnosis + implementation + offline validation (AGENTS §8). **No activation**, no gate closed, no request to any publisher |
| Status | `PARTIAL` — see §15 for what it does and does not claim |
| External API | `EXTERNAL_API_USAGE = NONE` |
| Start | branch `main`, HEAD `417cd1025f3404a246a875bfbb26cabc8613f186`, clean; `main` 14 commits ahead of `origin/main` (`a496b23`, the reports and merges of 2026-10-20/22, never pushed) |
| Work | worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\2026-11-14-readiness`, branch `readiness/2026-11-14-acquisition-readiness`; a second worktree `…\2026-11-14-release-rev2`, branch `readiness/2026-11-14-release-rev2`, for the release-contract take-over (a delegated sub-task, §5.8) |
| Operator brief | "CO.PRE.PAN_v3 – Umfassender Architektur-, Storage-, Contract- und Acquisition-Readiness-Run" (2026-11-14) |
| Decisions | CPD-0033 (bounded shared I/O, incremental backup); CPD-0034 (release contract revision 2, local adoption) — see §5.8 for its state |

## 1. Preflight

- **Git.** `main` clean at `417cd10`; four worktrees of earlier runs (`legacy-archive-contract`, `legacy-freeze`, `newfs-phase-b`,
  `newfs-phase-d`) — other runs' worktrees, left untouched (AGENTS §4).
- **Parallel work.** Two other Claude Code sessions were running, both on CO.RA.PAN (one waiting on a reservoir drive event). No other
  CO.PRE.PAN session.
- **CO.PRE.PAN processes.** None running. Scheduled task `COPREPAN_PreservationBackup`: daily 04:45 local, last run 2026-11-13 04:45
  (result 0), next 2026-11-15 04:45 (the 2026-11-14 run did not happen: the workstation was off at 04:45).
- **CO.RA.PAN production — active during the whole run** (read with `Get-ScheduledTask` and the process list only): an order of
  `reservoir_drive_v1.py` with materializer, post-export, preservation, housekeeping, index and flac-prefetch workers;
  `wave4_live_scheduler_v1.py supervise`, `wave4_preservation_sidecar_v1.py run`, `corpus_observatory_v1.py auto`; tasks
  `CORAPAN_BackupWindow` (every 30 min), `CORAPAN_LocalStorageMaintenance` (daily 03:30), `CORAPAN_HistoricBackup` (Sunday 04:15,
  last result 3), `CORAPAN_Wave4*`, `CORAPAN_ObservatoryRefresh`, `CORAPAN_ReleaseAnalysisReady`, `CORAPAN_ReviewReleaseCycle`.
  Nothing of it was started, stopped, changed or tested.
- **Storage roots** (`.env`, root variables only): RUNTIME `C:\dev\panhispanic_media_corpora\coprepan_workspace`, SPOOL
  `C:\dev\panhispanic_media_corpora\coprepan_storage`, PRESERVATION `\\dfs.hrz.uni-marburg.de\PROJEKTE\FB10\TACKE_FORSCHUNGSDATEN\projects\panhispanic_media_corpora\coprepan`
  (identity `coprepan-preservation-newfs`), BACKUP `D:\projects\panhispanic_media_corpora\coprepan\backup`.
- **The PRESERVATION primary was unreachable for the whole run.** One `isdir` of the root returned `False` at about 07:15Z; `net use`
  listed no connection; the AnyConnect adapter was up. CO.RA.PAN's own observation (`corapan_workspace\controller\preservation_mode_state.json`,
  read-only): `mode DEGRADED_LOCAL`, `last_error_class AUTH_REFUSED` (WinError 1326) since 2026-11-14T06:57:12Z, next probe on a 30-minute
  back-off. The share refuses this account's logons; CO.PRE.PAN made **no** further contact (each would be a logon attempt on the refused
  account), changed no connection and reset nothing.
- **Free space** (measured 2026-11-14): `C:` 306.3 GiB free, `D:` 2,360.4 GiB free (one external USB SSD, label `RESEARCH_BACKUP`).

## 2. Sources read

CO.PRE.PAN: `AGENTS.md`, `CLAUDE.md`, `docs/STATUS.md`, `docs/architecture/INDEX.md`, `docs/storage/INDEX.md` (§5–§8, §15–§20.8),
`contracts/crosscorpus-storage-v1/CONTRACT.md` (§2–§14), the decision registry and CPD-0031; code: `primary_backup.py`,
`preservation_migration.py`, `preservation.py`, `core_pipeline.py`, `intake.py`, `recovery.py`, `canary_driver.py` (preserve, derive,
evidence readers), `identity_rebuild.py`, `admission.py`, `storage_roots.py`, `freeze.py`, `scripts/preservation_backup.py`,
`scripts/intake_operator.py`, `scripts/storage_contract.py`; runtime evidence (local only): the 22 backup run documents
`coprepan_workspace\work\preservation_backup_runs\` (2026-10-19 to 2026-11-13), the backup journal and receipts on `D:` (one read each).

CO.RA.PAN (read-only, commit `8bb9914d0` of 2026-11-14; two read-only sub-analyses, their findings folded in here): `docs/architecture/`
(`STORAGE_AND_RETENTION_POLICY.md` §13i/§13j/§13w/§13y, `STORAGE_TARGETS_AND_PRESERVATION.md` §19.6–§19.7,
`RESERVOIR_CONTROLLER_PERFORMANCE.md` §3, `STORAGE_REDUNDANCY_INVENTORY.md`), `docs/crosscorpus/INDEX.md`, `HANDOFF_COPREPAN.md` §8,
decisions D93, D111, D116, D127–D131, D142, D148–D160 (headers and relevant parts), run reports of 2026-10-30, 2026-11-09 and 2026-11-13,
`storage/backup_window.py`, `backup_reconcile.py`, `preservation_mode.py`, `outage_spool.py`, `uncached_io.py`, `reservoir/state_index.py`,
the controller state files. No CO.RA.PAN code was executed, no SQLite opened, nothing on `D:` or the share of CO.RA.PAN read.

## 3. Working matrix

| Area | CO.RA.PAN now | CO.PRE.PAN at the start | Action (this run) |
|---|---|---|---|
| Storage and resolver | fail-closed `${ENV}` roots, T1/T2 markers per root, roots never `resolve()`d (SMB timeout); PRODUCTION / HISTORIC / LEGACY on NEW_FS, BACKUPs on `D:` | the same contract revision; PRODUCTION on the share, BACKUP on `D:`, LEGACY PRESENT; every resolution probes the share (exists, free space, three markers, a write probe) | gate in front of every share resolution (§5.2) |
| Reading and caching | state index with stat signature, TTL, rotating audit; read replica from BACKUP under five conditions | every new promotion read every manifest of its area; every derived read re-hashed both masters on the share | local manifest index; verified local read right after preservation (§5.3, §5.4) |
| Preservation | `.part` → landed hash → `os.replace`; uncached read-back; persisted preservation mode with back-off | the same promotion discipline, uncached read-back (P2, 2026-10-22); no back-off | back-off and bounded pending (§5.2, §5.5) |
| Backup and restore | continuous tee; weekly incremental reconcile, never lists the whole primary; up to 50 GiB fixity per run; monthly salted restore | daily FULL: every object of the primary re-hashed over the share (78 min), every backup object re-read | INCREMENTAL regular run with stated evidence reuse, rotating fixity, rotating restore (§5.6) |
| Cross-corpus contracts | storage rev 2 in force; release draft rev 2 pinned and used internally | storage rev 2 (synchronous); release rev 1 (one revision behind) | §4; release rev 2 taken over in its own worktree (§5.8) |
| Acquisition and scheduling | n/a (radio) | intake controller `/1`: every pending pack stops every request; preservation inline per outlet | `/2`: bounded pending, pause, floors (§5.5) |
| Recovery and resume | crash counters, stall detection, checkpointed reconcile | process-kill recovery qualified (CPD-0009); finalizer re-read the whole root | finalizer scoped to its own packs; whole-root audit separated (§5.5) |
| Resource isolation | capacity levels 50/35/20 GiB on `C:` and its `D:` volume; role budgets; stop files | none: no window, no floor, no pause, no knowledge of the sibling | resource policy, windows, floors, `PAUSE_IO`, sibling advisory (§5.1, §6) |
| Monitoring and accounting | `storage_health` problem codes, receipt age, observatory | status showed a backup receipt without its age; a missed or failed backup day was invisible | health block in the status, `last_run.json` (§5.7) |
| Release interfaces | internal release line on draft rev 2 (D160 active since 2026-11-10) | no release can be built (no extractor adopted) | none beyond §5.8 |

Outdated documentation and drift found: `docs/storage/INDEX.md` §20.8 named the backup task at 05:45 (it is registered at 04:45 local; the
recorded start boundary carries `+01:00`, the earlier text a summer-time reading); `scripts/storage_contract.py status` called the HISTORIC
holding "planned" while the topology record says not planned (corrected); `docs/STATUS.md` §5 still carries the release-pin split as the
current state (§5.8 says what changed); the AGENTS.md opening ("nothing discovers, fetches, preserves …") describes the bootstrap of
2026-10-06 and is dated by its own words — left as it is. The scheduled task `COPREPAN_PreservationBackup` was installed by CO.RA.PAN's
`scripts/install_holding_backup_tasks.ps1` (read in CO.RA.PAN) — not documented on this side until now.

## 4. Cross-corpus contract matrix (recomputed 2026-11-14)

Digests recomputed three ways (an independent reimplementation of the §4.5 tree digest over the files, over the git blobs, and
`coprepan.release_contract.bundle_digest`), on both checkouts; no CO.RA.PAN code executed.

| Contract | Home | Revision | Status | Pin CO.PRE.PAN (start) | Pin CO.RA.PAN | Byte-identical | Independent implementation and tests | Drift / action |
|---|---|---|---|---|---|---|---|---|
| `crosscorpus-storage/v1` | CO.RA.PAN | 2 (CO.RA.PAN `003ec84d5`, 2026-10-19; 110 cases) | `IN_FORCE` both | `49a3ca88c084eee26e40caa1dd987155bf8062c99c81d8cb734a7990a8afb036` | the same | yes (2/2 files) | both | none: no revision 3 on any CO.RA.PAN branch; CO.RA.PAN's decisions after 2026-10-10 (D111, D128, D131, D142, D148, D149, D153) state "contract unchanged" or apply it as it stands |
| `crosscorpus-release/v1` | CO.RA.PAN | CO.PRE.PAN rev 1 (`0a5f41dec`); CO.RA.PAN draft rev 2 (`374d2e44e`, 2026-10-08) | `DRAFT` both, not jointly adopted | `4fb72acf…6dbbe0` | `429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255` | no: 8 of 49 files differ | both (CO.PRE.PAN's passes rev 1's 52 cases) | one revision behind; a compatible take-over of the current draft (CONTRACT §14.3 step 2), not a joint normative decision; it needs a renewed **local** adoption (§17: CPD-0012 does not carry over) — §5.8 |
| `crosscorpus-analysis/v1` | CO.PRE.PAN | proposal (files unchanged since `5efabc6`) | CO.PRE.PAN CPD-0008 `ACTIVE_WITH_VALIDATION_DEBT`; CO.RA.PAN `TECHNICAL_PROPOSAL__NOT_ADOPTED_BY_CORAPAN` | no bundle pin | blob digests of 10 files observed at `5efabc6`, all equal to HEAD | n/a | CO.PRE.PAN only | **semantic drift**: CO.RA.PAN D116 (2026-10-16) retired speech mode, from which `production_mode` takes its spoken values; a new version needs the joint decision O-6 — **open, not touched** |
| NLP instrument contract (informal) | CO.RA.PAN (values) | — | CO.PRE.PAN mirror `PLANNED` | `[tool.coprepan.nlp]` | `pyproject.toml` | values equal (spaCy 3.8.15, es_dep_news_trf 3.8.0, …) | CO.RA.PAN only | CO.RA.PAN changed verbal-complex code on 2026-11-08 (`69b865084`) without a rule-version change — a CO.RA.PAN matter, recorded |

Holdings and roots (contract §2.2, §5.2): unchanged since revision 2. CO.RA.PAN D142 (2026-10-26) reads §2.2 locally (a holding follows the
acquisition method, not the date); it changes nothing for CO.PRE.PAN. Open joint decisions, recorded on either side and not touched: O-6
(analysis contract, D116 versioning), the joint freeze of `crosscorpus-release/v1` (§14.3 step 3) and its questions Q1, Q2, Q5, Q6, Q9–Q11,
the joint adoption of `crosscorpus-token-denominator/v1`.

## 5. Findings and what was built

Each finding was read in the code and, where it could be, measured from local evidence; each repair is decided in
[CPD-0033](../decisions/CPD-0033_bounded-shared-io-corapan-priority-and-incremental-backup.md) and described for operation in
[storage index §21](../storage/INDEX.md).

| # | Finding (start of the run) | Evidence | Severity | Repair |
|---|---|---|---|---|
| S1 | the daily backup re-hashed every object of the primary over the share and re-read every backup object | run documents 2026-10-19 to 2026-11-13: baseline 78 min (task start 03:45Z, baseline 05:03:09Z on 2026-11-13) for 8,816 objects / 395,018,230 B; copy + verify + restore about 1 min | P0 (CO.RA.PAN's link, daily, growing) | `INCREMENTAL` backup (§5.6) |
| S2 | every new promotion read every manifest of its area on the share | `preservation.find_by_content`; 2,204 packs → 4,408 manifest reads per new pack (two areas); measured on a fixture: 63 reads per promotion for 62 manifests | P0 (would have made any intake on the share unusable; never seen because nothing has been written there since 2026-10-18) | manifest index (§5.3) |
| S3 | the derivation after a promotion re-hashed both masters on the share twice more and read the pack from there | `canary_driver._derive` → `identify_and_extract`, `label_pack` → `open_preserved_pack`; counted on a fixture: 2 + 4 `verify_master` per pack before, 2 after | P1 | verified local read in the same step (§5.4) |
| S4 | an intake's finalizer re-hashed every master of the workspace and rebuilt the identity tables from every preserved pack read from the share | `intake.finalize` → `recovery.diagnose(…, preservation_root, registry)` | P1 | finalizer scoped to its own packs; whole-root audit separated (§5.5, §5.7) |
| S5 | an unreachable share was contacted again per pending pack and cycle; every 5-minute tick of a running intake resolved the share, and failed when it was away | `intake.run` (retry every ≤ 300 s), `intake_operator.load_environment` → `resolve_configured_roles` | P0 (logon attempts on the account the share refuses) | share gate; a tick without a share contact (§5.2, §5.5) |
| S6 | one pending pack stopped every request of an intake | `intake.run` (`if waiting: … continue`) | P1 (unattended operation through an outage) | bounded pending (§5.5) |
| S7 | no CO.PRE.PAN process knew CO.RA.PAN's windows or floors, nor a pause | — | P0 | resource policy, windows, floors, `PAUSE_IO` (§5.1) |
| S8 | the status showed a receipt without its age; a missed, failed or deferred backup day was invisible | `storage_contract.py status`; runs missing on 2026-10-26, 11-05, 11-08, 11-09 (no run document; the task's last result 0) | P1 | health block, `last_run.json` (§5.7) |
| S9 | the release contract pin is one revision behind | §4 | P2 | §5.8 |

### 5.1 The resource policy

`config/resource_policy.json` (`coprepan-resource-policy/v1`, `2026-11-14.1`) and `src/coprepan/resource_policy.py`. Values and their basis:
CPD-0033 decision 1. The file is pinned by the acquisition baseline from now on (`freeze.py`, list `configuration`).

### 5.2 The share gate and the sibling advisory

`ShareGate` (persisted in `<RUNTIME>/state/share_gate.json`): 5, 10, 20, 40, 60, 60 … minutes without contact after a failure, across
restarts; the refusal (`ShareBackingOff`) is a `StorageRootUnreachable`, so `preserve_pack` keeps the pack pending (P5) as for any outage;
an I/O failure during a promotion closes the gate too (`resource_policy.report_failure`). Measured on a fixture: an intake retrying every
minute for five hours makes at most 8 contacts instead of 300. The sibling advisory reads CO.RA.PAN's `preservation_mode_state.json`
(named by `COPREPAN_SIBLING_PRESERVATION_STATE`, `.env`): fresh and degraded → no contact until CO.RA.PAN's own next probe; fresh and slow
→ no maintenance; nothing in it ever permits anything.

### 5.3 The content index of a promotion

`src/coprepan/preserved_index.py`, `preservation.promote(content_index=…)`: a copy of each manifest in `<RUNTIME>/cache/preservation_manifests/<target id>/`,
keyed by the root's identity marker. Measured on a fixture of 62 manifests (`test_a_promotion_no_longer_reads_every_manifest_of_its_area`):
linear scan 63 manifest reads per promotion; with the index 61 once (cold), then 1 (its own manifest) plus one listing. On the real stock
that is 4,408 → 2 reads and 2 listings per pack (projection from the counts; the share's per-file latency was measured at about 260 ms on
2026-10-14). The first promotion on the share fills the index once (about 4,408 small reads, one time).

### 5.4 The verified local read right after preservation

`core_pipeline.open_preserved_pack(…, workspace=, trust_local_copy=)`. Only `canary_driver._derive`, which is always called with what
`_preserve` returned in the same step, passes `trust_local_copy=True`; it reads the workspace copy only when both files hash to the
manifests' digests. Every other reader is unchanged: `test_a_preserved_pack_that_no_longer_verifies_is_not_read` (a pre-existing test)
still holds, and a workspace copy that does not hash falls back to the root (`test_derivation_right_after_preservation_…`).

### 5.5 The intake controller `intake-controller/2`

Bounded pending (`pending_refusal`: ≤ 5,000 packs, ≤ 5 GiB, oldest ≤ 72 h, RUNTIME above 60 GiB), `PAUSE_IO`, the RUNTIME floor
(`io_refusal`), `held_because` in the state and the status line; the finalizer's `recovery.diagnose(…, master_scope=<its own packs>)`
without the registry (identity tables: self-consistency); `load_environment(…, need_preservation=False)` for a tick. Without a resource
policy the old behaviour is kept (the pre-existing test `test_while_the_preservation_target_is_away_nothing_more_is_asked` passes
unchanged). A plan of `/1` is refused by `/2` (`validate_plan`); the plans and receipts of 2026-10-10 are history.

### 5.6 The incremental backup

`primary_backup.run_incremental`, `scripts/preservation_backup.py run` (incremental by default; `--full`; `FULL` automatically without a
verified receipt of this primary). The reuse rule and the cases that require a full re-read: storage index §21.3, CPD-0033 decision 6. The
first incremental run after the merge builds on the receipt of 2026-11-13 (FULL, verified) and on the journal: 8,816 rows `COPIED`, each
with digest, size, `mtime_ns` and `reread: uncached` (read on `D:`, 2026-11-14) — full evidence for every object.

Isolated benchmark (`D:` scratch, local NTFS, synthetic tree of 8,816 objects of 1 KiB, measured 2026-11-14):

| Run | Files of the primary read | Bytes of the primary read | Local seconds |
|---|---|---|---|
| `FULL`, first (copies everything) | 17,633 | 17,967,531 | 170.4 |
| `FULL`, repeated (the daily run until now) | 8,817 | 8,983,847 | 14.2 |
| `INCREMENTAL`, nothing new | 300 (the fixity slice) | 304,940 | 1.2 |
| `INCREMENTAL`, 10 new objects | 320 | 323,086 | 1.3 |

The local seconds say nothing about the share. **Projection, not a measurement:** with the measured 0.53 s per object of the real full
baseline over the share (78 min / 8,816), the regular run's share reads fall from about 78 min to about 3 min per day, and stay there as
the corpus grows (the slice is fixed; the cycle lengthens and the status warns beyond 90 days).

### 5.7 Health and audit

`scripts/storage_contract.py status` → `health`: backup level (`OK` / `WARNING` above 72 h / `FAILURE` above 336 h or a last run with
problems), the last attempt, the fixity rotation, the share gate, the pause, the sibling advisory, the floors, the workspace's pending
fetches with their age (P4); PRESERVATION is not contacted while the gate is closed. `scripts/preservation_backup.py status` adds the
same health. `scripts/preservation_audit.py`: the whole-root check (every master on the root, the identity rebuild) on the operator's
order, yielding like every maintenance.

### 5.8 The release contract revision 2

Delegated to a sub-run in its own worktree (branch `readiness/2026-11-14-release-rev2`, commit `67258dc`), merged into this run's branch.
The 49 bundle files were taken from CO.RA.PAN's git objects at `374d2e44e` (read only; blob ids and SHA-256 equal; LF); 8 files differ from
revision 1; this repository's `bundle_digest` gives `429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255`, the committed tree
object equals CO.RA.PAN's. Run unchanged against the new vectors, the old checker passed 84 of 93 cases and 29 of 30 patterns; it was changed
to the revision's text, not to the vectors: T13 (the pattern subset: `^`/`$` absolute, `\s` = the 25 White_Space code points, a pattern
outside the subset refused), T16 (a freeze record beside a `provisional_export` is `FREEZE_MISMATCH`), T17 (the cohort is known exactly when
the date is), T19 (the sum over no documents is known zero, except tokens without a denominator and `audio_ms` of a written release),
T20 (WARC, ARC and CDX containers refused by the check), T18 (exactly one filter per input), T14 (a named release is identified first, then
checked). Result: all 93 cases and all 30 pattern vectors; then the pin moved (`revision: 2`, revision 1 kept under `previous_revisions`;
status `DRAFT`). Decision: [CPD-0034](../decisions/CPD-0034_local-adoption-of-crosscorpus-release-v1-revision-2.md) renews the local
adoption (CONTRACT §17: CPD-0012's does not carry over); CPD-0012 is superseded in its adoption record only. **Not done and not
CO.PRE.PAN's:** CO.RA.PAN's pin file (read at its commit `58307cb2a`) still records `other_side.pinned_revision: 1` — its own update; the
joint adoption (§14.3 step 3) needs CO.RA.PAN's adoption record, which does not exist. The contract stays `DRAFT` on both sides. Tests of
that branch: 1,834 passed, 14 skipped (before: 1,706).

### 5.9 Changed and new files

New: `config/resource_policy.json`, `src/coprepan/resource_policy.py`, `src/coprepan/preserved_index.py`, `scripts/preservation_audit.py`,
`tests/test_resource_isolation.py`, `docs/decisions/CPD-0033_bounded-shared-io-corapan-priority-and-incremental-backup.md`, this report.
Changed: `src/coprepan/{preservation,core_pipeline,admission,canary_driver,intake,recovery,primary_backup,freeze}.py`,
`scripts/{preservation_backup,intake_operator,storage_contract}.py`, `tests/test_primary_backup.py` (the clock of one CLI test fixed outside
the quiet windows; its assertions unchanged), `tests/test_repository_contract.py` (the closed list of `.env.example` names extended by the new
caution-only variable; the "no real path" check unchanged), `tests/suites/foundation_contract.txt`, `.env.example` (an empty, commented
entry), `docs/STATUS.md`, `docs/storage/INDEX.md` (§20.9, §21), `docs/architecture/INDEX.md`, `docs/architecture/TERMINOLOGY_AND_NAMING.md`
(§24), `docs/decisions/README.md`. Nothing was moved, deleted or overwritten outside this repository; no frozen evidence was edited.

## 6. Protection of CO.RA.PAN — what is shown and what is only constructed

| Mechanism | Shown (offline, by a test or a measurement) | Only constructed (not measured under real load) |
|---|---|---|
| no full-tree read in a regular cycle | backup: 300 primary reads instead of 8,817 (benchmark); promotion: 1 manifest read instead of 63 (fixture); finalizer and derivation scoped (code and tests) | the real duration on the share |
| no logon hammering | ≤ 8 contacts in 5 h of retries (fixture); a tick loads without the share (test) | the real share's refusal pattern |
| yield to CO.RA.PAN's windows and signals | windows, pause, sibling states, floors exercised (tests) | that the windows match CO.RA.PAN's real load profile |
| bounded bandwidth and duration | throttle and time budget exercised (tests) | the effect on CO.RA.PAN's throughput |
| one backup run per root | a second process is deferred (test) | — |
| capacity floors before CO.RA.PAN's | refusal at 10 GiB free (test); today 306 GiB on `C:`, 2,360 GiB on `D:` | — |

**Non-impairment of CO.RA.PAN under simultaneous production load is not claimed**: it was not measured, and it could not be (the share was
unreachable; no CO.PRE.PAN shared I/O ran at all). What is claimed: CO.PRE.PAN's regular share I/O is now bounded by construction and by
test, and it yields whenever CO.RA.PAN's own observation says the share is in trouble.

## 7. Tests and benchmarks

| Run | Result |
|---|---|
| full suite at the start (`417cd10`, worktree; it ran while the first edits were made — its collection had finished before them) | 1,706 passed, 14 skipped (511.7 s) |
| full suite after the storage and I/O work | 1,732 passed, 14 skipped (485.0 s) |
| full suite on the integrated branch (both strands merged, `fcfc0da` + this report; temporary directories on `C:`) | 1,862 passed, **1 failed**, 14 skipped (479.3 s): `test_storage_architecture.py::test_the_tracked_files_hold_no_machine_location` — a second closed list of `.env.example` names that did not know `COPREPAN_SIBLING_PRESERVATION_STATE`; extended like the first (its "no location" check unchanged); the two contract files then 98 passed |
| final full suite after that repair (the gate before integration; temporary directories on `C:`) | 1,863 passed, 14 skipped (490.2 s) |
| isolated backup benchmark | §5.6 |
| the sibling advisory against CO.RA.PAN's real state file (local read, 2026-11-14 ~08:02Z) | `SHARE_DEGRADED` (`DEGRADED_LOCAL`, `AUTH_REFUSED`, observed 301 s earlier); maintenance decision: not permitted |
| share latency probe (one listing and 20 manifest reads) | **not run**: the share was unreachable; no repetition (a logon attempt on the refused account) |

The tests write only under `tmp_path`. The first three runs used the session's temporary directory on `D:` (the shared USB device). The
integrated run started there at about 08:52 local made almost no progress for ten minutes (7 s of CPU: waiting on I/O) while CO.RA.PAN's
production worked on `D:`; it was stopped (this run's own process) and repeated with `--basetemp` on `C:`. Lesson, recorded: a CO.PRE.PAN
test run belongs on `C:`, not on the device that carries both projects' backups and CO.RA.PAN's working storage. No test touched a
storage root, the network beyond a literal loopback address, or a reference repository.

## 8. Preservation, backup and recovery status (2026-11-14)

- PRESERVATION primary: the share, identity `coprepan-preservation-newfs`, **unreachable** during the run (logons refused); content
  unknown, not empty (I2). Last verified state: 8,816 objects / 395,018,230 B, tree `f4bb0c9c…a284da0e` (receipt 2026-11-13T05:04:18Z).
- BACKUP: `D:\projects\panhispanic_media_corpora\coprepan\backup`, `BACKUP_VERIFIED` by the receipt of 2026-11-13 (FULL); its health on
  2026-11-14: `OK` (receipt age about 26 h). Independence beyond another volume not determined (B3).
- Pending: spool 0 records; workspace: no `PRESERVATION_PENDING` fetch (ledger read 2026-11-14).
- LEGACY: unchanged (CPD-0032); its backup has its own root and runs only on order.
- The next scheduled backup (2026-11-15 04:45) runs the merged code: with the share still refused it ends `DEFERRED` (primary unreachable)
  and closes the share gate; with the share back, an incremental run on the evidence of 2026-11-13.

## 9. Acquisition readiness

| Gate | Status | Evidence / open condition |
|---|---|---|
| Contract compatibility | `PARTIAL` | storage rev 2 synchronous; release: §5.8; analysis: O-6 open (a joint decision, no blocker for raw acquisition) |
| Storage safety | `PASS` (offline) | fail-closed roots, T2, gate, floors; tested; nothing contacted the share |
| Acquisition safety | `PASS` (offline) | policy gate, budgets, holds, deadline (CPD-0029, unchanged and passing); `intake-controller/2` bounded pending and pause tested; the switch `disabled` |
| Preservation | `PARTIAL` | P2 unchanged; the content index and gate tested offline; **no production write on the share has ever happened** (since 2026-10-18), and the share is unreachable now |
| Backup / Recovery | `PARTIAL` | incremental backup, fixity rotation, restore tested offline; the existing full backup verified on 2026-11-13; the first incremental run on the real roots is owed |
| Resource isolation | `PARTIAL` | constructed and tested on simulated signals (§6); not measured under real CO.RA.PAN load |
| Operational stability | `OPEN` | no outlet is `OPERATIONALLY_STABLE`; one 24-hour intake (2026-10-10/11) is the only long run; the Phase-1 core gate on the share is still owed (STATUS §5) |
| Bounded canary | `BLOCKED` | not permitted in this run: the PRESERVATION target is unreachable (a canary must preserve on it), the gates O-1 (scheduled crawling), O-12 (a new frozen baseline) and the arming are the operator's, and the brief's condition "storage targets safe" does not hold today |
| Continuous acquisition ready | `NOT_READY` | technical prerequisites on CO.PRE.PAN's side are built; open: the share's availability, a real intake under `/2` with a production write on the share, the first incremental backup on the real roots, O-1 for scheduled crawling, the operator's activation decision |

Technical readiness, scientific validation and operational activation are three statements: none of this run's results validates a
stage (D1–D3 of §6 of STATUS are untouched), and none activates anything. Raw acquisition does not wait for an adopted extractor: the
architecture separates raw preservation from extraction (Phase-3 layer architecture), and the baseline extractor runs only as a derived,
`EXPERIMENTAL` layer; no LLM or GPU dependency is in the foundation path.

## 10. Open decisions and proposals

1. **Operator — the share.** The share refuses this workstation's account (`AUTH_REFUSED`, WinError 1326, since 06:57Z): a credential
   or account matter of the institution, shared with CO.RA.PAN (its E-0 escalation draft of 2026-11-13 describes intermittent
   degradation). Nothing in CO.PRE.PAN can or should repair it.
2. **Operator — set `COPREPAN_SIBLING_PRESERVATION_STATE`** in the workstation's `.env` to CO.RA.PAN's controller file (path in §1); until
   it is set, the advisory is `NO_SIGNAL` and CO.PRE.PAN relies on its own gate and windows. *Done by this run in the workstation's `.env` (gitignored; §12); deleting the line switches the advisory off.*
3. **Proposal to CO.RA.PAN (a decision there, not here).** (a) Declare `preservation_mode_state.json` (schema `corapan-preservation-mode/v1`)
   a stable read-only interface for the sibling corpus, with its freshness semantics; (b) optionally publish its maintenance windows
   (backup reconcile, historic backup, local maintenance) as a small machine-readable file, so that CO.PRE.PAN's policy need not copy
   task times; (c) optionally a joint "share busy" lease. Effect: CO.PRE.PAN's caution would follow CO.RA.PAN's real state instead of a
   copy of 2026-11-14. Needed: a CO.RA.PAN decision record.
4. **Operator — release contract revision 2**: taken over locally (CPD-0034, §5.8) — the operator may review the agent's decision. Open and not CO.PRE.PAN's: CO.RA.PAN's pin file still names this repository's revision 1, and the joint adoption.
5. **Joint, scientific, not touched:** O-6 (the analysis contract after D116), the joint freeze of `crosscorpus-release/v1` and its open
   questions, the token denominator.
6. **Operator — the next acquisition.** A bounded intake under `intake-controller/2` (a new plan, authorisation, arming and frozen
   baseline, CPD-0029's procedure) once the share answers: it is the first production write on the share and the first real evidence for
   the gate, the index and the bounded pending. Not prepared further here (no plan file written: the share's availability decides when).

## 11. Risks

- The first incremental backup assumes that the `mtime_ns` the directory enumeration reports on the share equals the one `os.stat` gave
  the full baseline (both read the same file time; not verified on the share). If not, every object is re-hashed once (`RESTAMPED`) — the
  cost of one full run, no loss — and later runs reuse the new rows.
- The first promotion on the share fills the manifest index once (about 4,408 small reads).
- The quiet windows copy CO.RA.PAN's task times of 2026-11-14 (§10.3).
- `D:` holds both projects' backups on one device: the backups' independence from each other is not the question of B3, but one device
  failure affects both projects' secondary copies (CO.RA.PAN's inventory records this too).

## 12. Commits, integration, push

- **Commits** on `readiness/2026-11-14-acquisition-readiness`: `39c6636` (storage and I/O, CPD-0033), the merge `fcfc0da` of
  `readiness/2026-11-14-release-rev2` (`67258dc`, CPD-0034), and the commit of this report.
- **Report on `main`:** published with `scripts/publish_run_report.py publish … --status PARTIAL` (a documentation-only commit).
- **Merged into `main`:** yes, after the integrated suite passed (no conflict with `main`, which had not moved since `417cd10`).
- **Pushed:** `main` and both run branches to `origin`, fast-forward (`origin/main` was an ancestor). Pushing `main` also publishes the
  14 local commits of 2026-10-19 to 2026-10-22 (CPD-0031/0032 runs, the audit and its closure), all of them documentation and code
  already integrated, most already on `origin` as ancestors of the audit branch; the operator's brief authorises the push.
- **Workstation state outside git:** `COPREPAN_SIBLING_PRESERVATION_STATE` added to the main checkout's `.env` (gitignored).
- **Tree classification at the end:** every change committed; nothing untracked left in either worktree.

## 13. Processes and jobs

No CO.PRE.PAN process was started that is still running; no scheduled task was created, changed, started or removed; acquisition was not
armed. `COPREPAN_PreservationBackup` (next 2026-11-15 04:45) will run the merged code. CO.RA.PAN's processes and tasks (§1) were neither
touched nor measured beyond the process list and the task list. This run's two worktrees are closed by `scripts/worktree_closure.py remove` as its last act (their branches kept); the four worktrees of earlier runs are left as they were (another session's, no brief to close them).

## 14. Next operator decision

**Restore the share's access for this workstation's account** (an institutional credential matter, shared with CO.RA.PAN).
Nothing else needs a person before that: the scheduled backup defers by itself while the share is refused and runs incrementally
when it answers. After that, the one decision that moves acquisition forward is the operator's authorisation of **one bounded
intake under `intake-controller/2`** (a new plan, a `DIA` record, the arming and a frozen baseline, CPD-0029's procedure) as the first
production write on the share — and, on its evidence, the question of a recurring intake (O-1 for scheduled crawling).

## 15. Status

`PARTIAL`. Done: the comparison with CO.RA.PAN, the contract matrix, the P0/P1 storage and I/O repairs (S1–S8) with tests and a
benchmark, the documentation. Not done, with reasons: any real-share evidence (unreachable), any measurement under CO.RA.PAN load (not
possible without shared I/O), a bounded canary (not permitted: target unreachable, gates open). It does **not** claim that CO.RA.PAN is
unimpaired under simultaneous load, that any outlet is stable, or that anything is activated or validated.
