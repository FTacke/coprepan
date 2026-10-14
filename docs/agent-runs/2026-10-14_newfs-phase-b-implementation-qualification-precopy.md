# NEW_FS Phase B — implementation, qualification and verified pre-copy (CO.PRE.PAN side)

```text
run_started_at:      2026-10-14T15:31:27+02:00
run_ended_at:        (open)
timezone:            Europe/Berlin
```

Status: IN PROGRESS. Decision: [CPD-0030](../decisions/CPD-0030_newfs-target-identity-and-verified-pre-copy.md). The run was carried out
from the CO.RA.PAN repository with write scope over both repositories; the joint report (qualification of the share, HISTORIC, the
CO.RA.PAN pre-copy) is `corapan/docs/agent-runs/2026-10-14_newfs-phase-b-implementation-qualification-precopy.md`. Branch
`newfs/phase-b-migration` in `C:\dev\panhispanic_media_corpora\worktrees\coprepan\newfs-phase-b`, cut from `main` = `origin/main` = `100f2b0`.

Not done, by the brief: no cutover, no change of `.env` (the interim primary stays configured), no acquisition (`external_acquisition`
stays `disabled`), nothing of the interim primary, the workspace or the legacy tree moved, renamed or deleted; the workspace's evidence
tables stay where they are (a separate scope).

## 1. Starting state

`main` `100f2b0` (2026-10-11), clean; no CO.PRE.PAN process running; the last intake `in1-20261010-24h` COMPLETED (2026-10-11), disarmed.
Interim primary `D:\projects\panhispanic_media_corpora\coprepan\preservation_interim` (marker `coprepan-preservation-interim-d`, taken
into service 2026-10-08): 8,816 objects / 395,018,230 B besides the marker (2,204 WARC packs, 2,204 indexes, 4,408 manifests); every object
`RAW_PRESERVED`; spool empty; **no BACKUP** (sole copy).

## 2. Code

| File | Change |
|---|---|
| `src/coprepan/storage_roots.py` | T2: `preservation_identity`, `StorageTargetIdentityMismatch`, `COPREPAN_PRESERVATION_TARGET_ID`, foreign markers; checked in `resolve_root("PRESERVATION")` for reading and writing |
| `src/coprepan/preservation_migration.py` (new), `scripts/preservation_migration.py` (new) | the pre-copy: baseline (contract inventory), copy with unbuffered re-read and no-overwrite publish, verify, receipt, sweep of its own temporaries |
| `.env.example` | `COPREPAN_PRESERVATION_TARGET_ID=` (an identity, not a path) |
| tests | `tests/test_preservation_migration.py` (new, suite `foundation_contract`); the deletion guard of `tests/test_preservation.py` names `_discard_own_temporary`; `.env.example` assertions in `test_repository_contract.py` and `test_storage_architecture.py` |

## 3. Pre-copy

Plan (`plan --source <interim primary>`): **8,816 objects, 395,018,230 B, tree SHA-256 `f4bb0c9ca71a9615383dec29da57b940ffe43aabf8f4f9a748932333a284da0e`**
(the source's marker excluded). New root `\\dfs.hrz.uni-marburg.de\PROJEKTE\FB10\TACKE_FORSCHUNGSDATEN\projects\panhispanic_media_corpora\coprepan`,
marker `coprepan-preservation-newfs` (2026-10-14T14:23:13Z). The live interim primary was refused as a target by the tool. Copy running
since 16:24 (`--workers 3 --max-mib-s 0.5`, beside CO.RA.PAN's HISTORIC copy).

Run 1 died at 17:03:41 (a reset SMB session invalidated the open journal handle; the joint report §5) after 4,000 objects; the copier was
hardened (journal reopen with a byte-exact tail check, transport retries, a clean `NETWORK_UNAVAILABLE` stop; tests for a row lost with its
acknowledgement, a foreign torn tail, a lost publish acknowledgement, a racing writer, two concurrent copies) and resumed: run 4
(17:41-18:26) 5,762 `SKIPPED_JOURNALLED` + 3,054 `COPIED`, no problem, journal never reopened.

| Result | |
|---|---|
| verification (16:37Z) | 8,816 / 8,816 re-read unbuffered from the server, digests equal, 0 extra, 0 temporary files |
| journal audit | 8,816 rows, 0 torn, 0 duplicate, no object copied twice |
| closing baseline of the interim primary | 8,816 / 395,018,230 B, tree SHA-256 `f4bb0c9c…a1a2c` -- **equal**: the pending delta is empty |
| `check_readiness` on the new root | `READY` (identity, 2.99 TB free, atomic promotion, no silent overwrite, long names, fixity of 100 objects) |
| receipt | `<new root>/_migration/newfs-2026-10-14/migration_receipt.json`, `PRE_COPY_NOT_PRIMARY`; copies in [`docs/storage/migration/2026-10-14_newfs-phase-b/`](../storage/migration/2026-10-14_newfs-phase-b/) |

## 4. Qualification on the share

The joint report has the file-system qualification. This repository's suites with `--basetemp` on the share:

- crash, concurrency and preservation suites with every root on the share (16:54-17:59): 234 passed, 9 failed, 29 errors -- child timeouts
  tuned for a local disk, `WinError 59` during the 17:03 reset, and `LayerStoreError: could not publish` (a directory rename of the RUNTIME
  layer store; the share refuses a directory rename for about a second after its files were written -- probe in the joint report §4.1);
- the preservation-path suites in isolation (18:0x-19:0x): **241 passed, 1 failed** -- the failure is the same layer-store directory rename
  (that test's workspace was on the share as well).

The PRESERVATION paths of this repository rename files only. **RUNTIME on the share is not qualified and not planned.** The Phase-1 core
gate "on the long-term target" stays open for the configuration that will exist (only PRESERVATION on the share).
