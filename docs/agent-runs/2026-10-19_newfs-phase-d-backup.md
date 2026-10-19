# NEW_FS Phase D -- the BACKUP of the PRESERVATION primary (CO.PRE.PAN side)

```text
Status:            COMPLETE for CO.PRE.PAN (first BACKUP verified; recurring task installed)
run_started_at:    2026-10-18T23:33:05+02:00 (joint run, from the CO.RA.PAN repository)
timezone:          Europe/Berlin
Branch / commits:  newfs/phase-d-backup (worktree worktrees/coprepan/newfs-phase-d) from main 48c0e1c; main fast-forwarded to it
Decision:          CPD-0030 (Phase D section); sister decision CO.RA.PAN D111
```

Brief: "NEW_FS Phase D + C:-Speicherentlastung -- Backup, Fixity, Retention und kontrollierte Freigabe" (operator, 2026-10-18). The
joint report (all three holdings, C: relief, retention, decisions) is CO.RA.PAN's
`docs/agent-runs/2026-10-18_newfs-phase-d-backups-and-c-relief.md`.

## What was missing

CO.PRE.PAN had **no BACKUP**: the PRESERVATION primary on the institutional share (`coprepan-preservation-newfs`, since the cutover
2026-10-18 15:29:20) was a sole copy; the former interim primary on `D:` stays a protected fallback and is **not** a backup.

## What is new

- `src/coprepan/primary_backup.py`: `init_root` (new or empty directory, another volume than the primary, marker
  `BACKUP_ROOT.json` with role BACKUP and corpus), `require_root` (marker, volume, never a preservation root), `copy` (the migration
  engine: write-once, temporary file, uncached re-read, publish; journalled and resumable), `verify` (unbuffered re-read of every
  object; objects only in the backup are reported, never deleted), `restore_test` (samples read from the backup root only into a
  scratch directory; `_discard_restored` removes only inside it), `write_receipt` (superseded receipts kept), `receipt_status`
  (bound to the primary's target id).
- `scripts/preservation_backup.py` `init-root | run | status`; the primary's root and identity come from `.env` via
  `storage_roots.resolve_root("PRESERVATION")` (T2), the backup root from `COPREPAN_BACKUP_ROOT`.
- `scripts/storage_contract.py status` reports the receipt (`backup_receipt`).
- Tests: `tests/test_primary_backup.py` (10), deletion-guard registry entry; full suite 1,607 passed, 14 skipped.
- Workstation `.env` (untracked): `COPREPAN_BACKUP_ROOT=D:\projects\panhispanic_media_corpora\coprepan\backup`.
- Recurring: Windows task `COPREPAN_PreservationBackup`, daily 05:45, from the main checkout, evidence under
  `coprepan_workspace\work\preservation_backup_runs` (installer: CO.RA.PAN `scripts/install_holding_backup_tasks.ps1`).

## First run (evidence: `docs/storage/migration/2026-10-19_newfs-phase-d/`)

| Step | Result |
|---|---|
| baseline of the primary | 8,816 objects / 395,018,230 B, tree `f4bb0c9c…284da0e` = the Phase C closing plan's tree (chain intact); identity `coprepan-preservation-newfs`; 2026-10-19T01:06:08Z (hashing over the share took ~55 min) |
| copy | run `bk20261019T010608Z-27b085`: 8,816 COPIED, 0 problems |
| verification | unbuffered re-read of every object: 0 problems, 0 only-in-backup, 0 temporary files (01:14:56Z) |
| restore test | 25/25 from the backup root only (1.60 MB) |
| receipt | `D:\…\coprepan\backup\_backup\backup_receipt.json`, 01:14:57Z; `status`: copy exists, produced from and verified against the primary |

Independence: another volume (local `D:`); further independence (offsite, 3-2-1) is not determined and not claimed (contract B3).
Acquisition is still `disabled`, so no production write on the new primary has happened yet; each daily run covers what the
primary holds at its baseline.
