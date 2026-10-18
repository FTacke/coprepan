# CPD-0030 — NEW_FS: the identity of the PRESERVATION root is checked (T1/T2), the pre-copy tool, and the verified pre-copy to the institutional share

| Field | Value |
|---|---|
| Date | 2026-10-14 |
| Status | `ACTIVE` |
| Execution | the identity check and the tool are in force; the pre-copy is executed and verified; **the cutover is executed (Phase C, 2026-10-18 15:29:20 +02:00): the institutional share is the PRESERVATION primary** -- see "Phase C (2026-10-18)" below |
| Decided by | the operator, in the brief "NEW_FS Phase B — Implementation, Qualification & Verified Pre-Copy" of 2026-10-14 (run from the CO.RA.PAN repository with write scope over both sister repositories): target layout, the interim primary on `D:` as the source, no change of any configured root |
| Kind | policy · architecture · operation |
| Scope | the identity check of the PRESERVATION root; the copy of the primary to its future root; the NEW_FS root of CO.PRE.PAN |
| Builds on / amends / supersedes | builds on CPD-0014 (roles, interim primary, the planned move), CPD-0015 (the joint contract and its §11 procedure). **Amends CPD-0014 §6/§8 and the storage index §20.4** ("the copy is an operator-ordered act in no tool here": the copy now has a tool; the act stays operator-ordered). Supersedes nothing |
| Does not change | any identifier, pack, index, manifest or relative path; the interim primary (read only, never renamed into a backup); the acquisition policy (`external_acquisition` stays `disabled`); the workspace and its evidence tables; the pinned contracts (`crosscorpus-storage/v1`, `crosscorpus-release/v1` revision 1) |
| Run report | [`docs/agent-runs/2026-10-14_newfs-phase-b-implementation-qualification-precopy.md`](../agent-runs/2026-10-14_newfs-phase-b-implementation-qualification-precopy.md); the joint report is in CO.RA.PAN under the same name; the sister decision is CO.RA.PAN's D111 |
| Evidence | `tests/test_preservation_migration.py` (suite `foundation_contract`); the storage-related tests run with `--basetemp` on the institutional share; the pre-copy's journal, plan and receipt on the new root under `_migration/newfs-2026-10-14/` |

## Context

The institutional project share exists since 2026-10-14 (HRZ, 3 TB, tape backup and snapshots). The joint contract's T1 was half in
place here (the marker `coprepan_preservation_target.json`, written once; baselines pin it), T2 was not: nothing compared the marker of
the configured root with an expected identity, so a wrong value of `COPREPAN_PRESERVATION_ROOT` would have been followed. The copy step of
the migration had no tool (storage index §20.4).

## Decision

1. **The NEW_FS root of CO.PRE.PAN** is `\\dfs.hrz.uni-marburg.de\PROJEKTE\FB10\TACKE_FORSCHUNGSDATEN\projects\panhispanic_media_corpora\coprepan`
   (contract §5.2), identity `coprepan-preservation-newfs`. The location lives here, in run reports and in the workstation's `.env`, never in
   tracked configuration. It is a sibling of CO.RA.PAN's roots (S4 holds); no HISTORIC holding of CO.PRE.PAN exists or is created.
2. **T2 is checked at every resolution of PRESERVATION** (`storage_roots.resolve_root`, `preservation_identity`): with
   `COPREPAN_PRESERVATION_TARGET_ID` set (an identity, not a path; `.env`), a root without marker or with another target id is
   `TARGET_IDENTITY_MISMATCH` (`StorageTargetIdentityMismatch`, a `StorageRootUnusable`) for reading and writing; a CO.RA.PAN marker or a
   `BACKUP_ROOT.json` at the root, or an unreadable marker, is a mismatch in every case. Unset, a root without marker stays usable
   (`IDENTITY_UNRECORDED`) — the state every test root is in.
3. **The pre-copy tool** (`src/coprepan/preservation_migration.py`, `scripts/preservation_migration.py`): the baseline is the source's
   contract inventory without its marker and without probe or migration directories; every object is copied through a temporary file, its
   timestamp kept, re-read **unbuffered** from the server and published by `os.rename`, which never replaces a name; an existing object with
   the same digest is `ALREADY_PRESENT`, with another digest `CONFLICT` (every object of this corpus is write-once); a source that lost its
   baseline digest is `SOURCE_CHANGED`; journal under `_migration/<id>/` on the destination, resume, byte-rate limit, stop file. The only
   removal is the tool's own unpublished temporary file (`_discard_own_temporary`, registered in the deletion guard of
   `tests/test_preservation.py`). It refuses a destination without its own marker and the root in use today.
4. **The pre-copy is executed** from the interim primary to the new root and verified there; its receipt says `PRE_COPY_NOT_PRIMARY`.
   The interim primary stays the primary; with acquisition disabled no writer changes it, so the closing reconciliation at the cutover is
   expected to be empty — it is still a gate.

## Alternatives considered

- **`robocopy` or a plain copy, then `migration-verify`.** Rejected: no per-object digest at the moment of the copy, no journal of what
  was published, overwrite semantics that depend on flags, and a buffered re-read that the SMB client cache answers.
- **Server-side SMB copy from the old location** (CO.RA.PAN's add-on test, 2026-10-14). Not applicable: the institutional share is
  served by another server than the faculty share and than `D:`; the payload crosses the workstation either way.
- **Renaming the interim primary into the future BACKUP.** Excluded by CPD-0014 §6: a former primary is never renamed into a backup.
- **Requiring a marker at every PRESERVATION root without an expected identity.** Rejected for now: every test root would need one and
  the interim primary has one anyway; the strict check applies where the identity is recorded (the cutover sets it).

## Not decided here

The cutover and its window; the BACKUP on `D:` (Phase D); the durable home of the workspace's evidence tables; RUNTIME on the share (not
qualified: the layer store's directory renames); DISTRIBUTION, EXCHANGE and access groups.

## Cutover gates (Phase C) and after

The workspace writer lock held (no acquisition can promote); the closing reconciliation (a new baseline of the interim primary against the
journal: nothing new, nothing changed); `.env`: `COPREPAN_PRESERVATION_ROOT` and `COPREPAN_PRESERVATION_TARGET_ID`; `check_readiness` on the
new root; the drain and a read-back of every preserved pack. Afterwards (Phase D): `COPREPAN_BACKUP_ROOT` on `D:` with a copy produced from
the new primary and verified against it; the interim primary retained, never renamed into a backup. The durable home of the workspace's
evidence tables stays a separate decision.

## Phase C (2026-10-18)

Executed under the operator brief "NEW_FS Phase C: Final Reconciliation, Production Cutover und Rollback-Qualifikation" of 2026-10-18
(run from the CO.RA.PAN repository). Every gate above, with its evidence in
[`docs/storage/migration/2026-10-18_newfs-phase-c/`](../storage/migration/2026-10-18_newfs-phase-c/) and storage index §20.6: the closing
baseline (a fresh plan of the interim primary, every object re-hashed) has the pre-copy's tree; the copy pass skipped all 8,816 objects;
an unbuffered re-read of every object on the new root found 0 problems and 0 extra objects; the spool was empty; the writer lock was free
and the interim tree unchanged under it; `.env` names the new root and `COPREPAN_PRESERVATION_TARGET_ID=coprepan-preservation-newfs`
(2026-10-18 15:29:20 +02:00); `check_readiness` `READY` on the new root. The code of this decision was integrated by a fast-forward of
`main` to `881ae58`. **The institutional share is the PRESERVATION primary.** The interim primary is retained unchanged (a protected
fallback, not a backup). Not shown yet: a production write (acquisition stays `disabled`), the Phase-1 core gate with only PRESERVATION on
the share, the BACKUP (Phase D). Joint report: CO.RA.PAN `docs/agent-runs/2026-10-18_newfs-phase-c-final-reconciliation-cutover.md`;
this repository's run report: [`../agent-runs/2026-10-18_newfs-phase-c-cutover.md`](../agent-runs/2026-10-18_newfs-phase-c-cutover.md).
