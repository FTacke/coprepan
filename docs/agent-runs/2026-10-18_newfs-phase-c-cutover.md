# NEW_FS Phase C -- final reconciliation and cutover (CO.PRE.PAN side)

```text
Status:            COMPLETE for CO.PRE.PAN (cutover PASS technically; production proof pending: acquisition disabled)
run_started_at:    2026-10-18T14:11:50+02:00 (joint run, from the CO.RA.PAN repository)
cutover_at:        2026-10-18T15:29:20+02:00 (.env)
timezone:          Europe/Berlin
Branch / commits:  main fast-forwarded 100f2b0 -> 881ae58 (newfs/phase-b-migration, CPD-0030); this report and the docs: next commit
Decision:          CPD-0030 (Phase C section); sister decision CO.RA.PAN D111
```

Brief: "NEW_FS Phase C: Final Reconciliation, Production Cutover und Rollback-Qualifikation" + addendum on parallel sessions (operator,
2026-10-18). The `.env` change was explicitly released by the operator in the session ("Ich erlaube es!") after the permission check
had stopped the first attempt. The joint report (all three holdings, GO/NO-GO, writer freeze, SMB findings) is CO.RA.PAN's
`docs/agent-runs/2026-10-18_newfs-phase-c-final-reconciliation-cutover.md`.

| | Before | After |
|---|---|---|
| PRESERVATION primary | `D:\projects\panhispanic_media_corpora\coprepan\preservation_interim` (`coprepan-preservation-interim-d`) | `\\dfs.hrz.uni-marburg.de\PROJEKTE\FB10\TACKE_FORSCHUNGSDATEN\projects\panhispanic_media_corpora\coprepan` (`coprepan-preservation-newfs`) |
| T2 expected identity | unset | `COPREPAN_PRESERVATION_TARGET_ID=coprepan-preservation-newfs` |
| RUNTIME / SPOOL | `C:\…\coprepan_workspace` / `C:\…\coprepan_storage` | unchanged |

## Gates and evidence (`docs/storage/migration/2026-10-18_newfs-phase-c/`)

| Gate | Result |
|---|---|
| source and target identified | interim marker `coprepan-preservation-interim-d`; new root marker `coprepan-preservation-newfs` (T1) |
| closing reconciliation | fresh plan of the interim primary, every object re-hashed: 8,816 / 395,018,230 B, tree `f4bb0c9c…a1a2c` = the pre-copy's (`plan_final_summary.json`) |
| delta copy | same migration id `newfs-2026-10-14`: 8,816 `SKIPPED_JOURNALLED`, 0 bytes (run `mig20261018T130104Z-9672ee`) |
| full verification | unbuffered re-read of every object against the fresh plan: 0 problems, 0 extra, 0 temporary files (`verification_final.json`, 2026-10-18T13:17:33Z) |
| journal | 8,816 rows, clean (Phase B audit; no new row) |
| writers | none running; `external_acquisition: disabled`; writer lock free, interim tree unchanged under it (`writer_lock_check.json`, 13:33:53-13:33:57Z) |
| spool | 0 pending |
| code | `main` fast-forwarded to `881ae58`; test suite 1,597 passed, 14 skipped |
| after the switch | `qualify_storage_roots.py roles`: PRESERVATION `CONFIGURED`, separation checked; `readiness`: `READY`, fixity of 100 objects, no probe artefact (`readiness_after_cutover.json`); `storage_contract.py status`: PRESERVATION `AVAILABLE`, `SEPARATED`, spool 0 (`storage_contract_status_after_cutover.json`) |

## State and what is owed

- **Production proof pending:** no production write can happen on the new root while acquisition is disabled; the first armed canary or
  intake is it. Technical qualification (resolution, T2, readiness with fixity read-back) is done.
- **Protection:** the interim primary on `D:` is retained unchanged (protected fallback, never renamed into a backup). **No BACKUP of the
  new primary exists** (`NOT_CONFIGURED`): Phase D -- a copy on `D:` produced from the new primary and verified against it, with restore tests.
- **Rollback:** no write on the new root -> restore the two `.env` lines (the interim root, the target id unset). After a first write,
  carry the new objects back first (CO.RA.PAN `scripts/newfs_cutover_v1.py rollback-delta / rollback-copy`, D111).
- **Still open (CPD-0030 §20.5):** the Phase-1 core gate and the process-kill tests with only PRESERVATION on the share; RUNTIME stays on `C:`.
