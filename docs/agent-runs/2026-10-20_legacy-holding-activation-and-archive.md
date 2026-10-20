# 2026-10-20 — LEGACY holding activated; the legacy repository archived (CPD-0032)

```text
Status:   COMPLETE
Brief:    "Legacy-CO.PRE.PAN und CORAPAN/COPREPAN Studies – wissenschaftlicher Freeze und institutionelle Archivierung"
          (operator, 2026-10-20)
Branch:   storage/legacy-freeze (worktree worktrees\coprepan\legacy-freeze, from main 17fac47)
run_started_at:  2026-10-20T14:30:00+02:00
run_ended_at:    2026-10-20T18:30:00+02:00 (approximately)
timezone:        Europe/Berlin
Decision: CPD-0032; sister CO.RA.PAN D131
Evidence: legacy repository docs/agent-runs/2026-10-20_legacy-freeze-and-archive.md and its 2026-10-20_freeze_evidence/
```

## 1. What was done here

- **CPD-0032** recorded before anything was written to NEW_FS: the LEGACY holding of CO.PRE.PAN is activated; the legacy press
  corpus is classified as a frozen legacy research holding (`legacy_frozen`; not `native_v3`, not production, never a pipeline
  input); compatibility with contract §2.2 and CPD-0031 checked (no normative contradiction; only CPD-0031's "no activation" is
  superseded). The contract bundle is unchanged (`49a3ca88…afb036`; `tests/test_storage_contract.py` green).
- **Backup tool** (`dad33b5`): `primary_backup.init_root/require_root/copy` take the holding (PRODUCTION default, LEGACY); the marker
  records it and a root is refused for another holding; `scripts/preservation_backup.py --holding LEGACY` reads
  `COPREPAN_LEGACY_ARCHIVE_ROOT` / `COPREPAN_LEGACY_ARCHIVE_TARGET_ID` (required, T2) / `COPREPAN_LEGACY_BACKUP_ROOT`. The scheduled
  PRODUCTION backup is unaffected (default path unchanged). Tests: 3 new; `test_primary_backup.py` 13 passed,
  `test_preservation.py` + `test_storage_contract.py` 174 passed. No other test suite was run.
- **Configuration**: `.env.example` lists the three variables without values; `.env` is not changed (the run set them per process).
  `config/storage_targets.yml` is unchanged (LEGACY is a holding, not a role).
- **Docs**: storage index §20.3 (LEGACY row superseded) and new §20.7 (topology, PRESENT); legacy index §5 (steps 2 and 3 done,
  step 4 open) and §9 milestone; `STATUS.md`; decisions index; `AGENTS.md` (reference-repository rows: frozen, archived; the stale
  `C:\dev\corapan` row annotated, not resolved).

## 2. Result on the storage

| | |
|---|---|
| LEGACY primary | `\\dfs.hrz.uni-marburg.de\PROJEKTE\FB10\TACKE_FORSCHUNGSDATEN\projects\panhispanic_media_corpora\legacy\coprepan`, marker `coprepan-archive-newfs-legacy` (written once 13:13:39Z) |
| Tree `coprepan` | 3,583 files, 17,635,313,888 B, `tree_sha256 b97105bda5d3c8fd68dd33385edb0a6f28c6b07ed7c5e2a53e0554d3e76547c6`, manifest SHA-256 `c536fdd5…`; PRESERVED 15:15:40Z (unbuffered re-read, `archive_tree` no code in both repositories' implementations) |
| Freeze listing | all 3,256 release-scope files identical; 3,572 of the tree's files identical to the 2026-10-07 listing; 0 missing |
| LEGACY backup | `D:\projects\panhispanic_media_corpora\legacy\coprepan\preservation_backup` (marker holding `LEGACY`); run `bk20261020T154744Z-7f7224`: 3,584 copied, unbuffered verification 3,584/3,584, restore 40/40, receipt written; own read-back 45/45 |
| Protected holdings | the 2026-10-15 secondary `legacy_coprepan`, the PRODUCTION backup and interim primary: listing digests before = after |

## 3. Not done (by the brief)

No push, no deployment, no acquisition, no reader switched (`COPREPAN_JSON_ANNOTATED` in CO.RA.PAN keeps naming the local tree), no
A7 release, nothing deleted. `EXTERNAL_API_USAGE = NONE`.

## 4. Working tree

Every change of this branch is committed; the integration into `main` is recorded in the commit log (fast-forward or merge, no
push).
