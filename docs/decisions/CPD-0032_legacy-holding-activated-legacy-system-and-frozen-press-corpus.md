# CPD-0032 — CO.PRE.PAN's LEGACY holding activated: the legacy system and its frozen press corpus archived as tree `coprepan`

| Field | Value |
|---|---|
| Date | 2026-10-20 |
| Status | `ACTIVE` |
| Execution | executed 2026-10-20 (run report [`docs/agent-runs/2026-10-20_legacy-holding-activation-and-archive.md`](../agent-runs/2026-10-20_legacy-holding-activation-and-archive.md)); the contract bundle is unchanged (`49a3ca88c084eee26e40caa1dd987155bf8062c99c81d8cb734a7990a8afb036`) |
| Builds on / amends / supersedes | builds on CPD-0031 (revision 2 taken over) and CPD-0030 (target identity); **supersedes CPD-0031 decision 3 ("no activation")**; refines `docs/legacy/INDEX.md` §5 (the frozen legacy release gets its preserved copy) |
| Does not change | the PRODUCTION primary, its BACKUP and their identities; the acquisition policy; the contract; the standing of the legacy corpus (legacy index §3); CPD-0004 |
| Decided by | the operator, in the brief "Legacy-CO.PRE.PAN und CORAPAN/COPREPAN Studies – wissenschaftlicher Freeze und institutionelle Archivierung" of 2026-10-20 (decisions O-2, O-3, O-5, O-7), on the read-only audit of the same day |
| Sister decision | CO.RA.PAN `D131` (the cross-corpus studies repository becomes tree `corapan_coprepan_studies` of CO.RA.PAN's LEGACY holding) |

## Context

The legacy repository (`legacy\coprepan`, last development commit `3e6bdd3`) holds the legacy press corpus (`json_annotated`, 926
files, ≈ 17 million tokens), its extracted text, the crawl database and the annotation state — gitignored, on C: only, with a D:
secondary of 2026-10-15 made from the local tree. The freeze manifest `coprepan-legacy-2026-06` (2026-10-07, `MANIFEST_ONLY`)
records every file's SHA-256 but restores nothing; its steps 2–3 waited for a preservation target (O-3). CPD-0031 took over the
LEGACY holding without activating it.

## Decision

1. **The LEGACY holding of CO.PRE.PAN is activated.**
   - PRESERVATION primary: `projects/panhispanic_media_corpora/legacy/coprepan` on the NEW_FS share
     (`\\dfs.hrz.uni-marburg.de\PROJEKTE\FB10\TACKE_FORSCHUNGSDATEN`), identity marker `coprepan_preservation_target.json`
     (`coprepan-preservation-target/v1` schema of CPD-0030) with `target_id` **`coprepan-archive-newfs-legacy`**. It shares no root
     with PRODUCTION (`legacy` is a reserved segment; the PRODUCTION primary is `…/coprepan`).
   - BACKUP: `D:\projects\panhispanic_media_corpora\legacy\coprepan\preservation_backup`, marker `BACKUP_ROOT.json` with role
     `BACKUP`, corpus `coprepan`, **holding `LEGACY`**; produced FROM the LEGACY primary and verified against it (B1, A7). The D:
     secondary of 2026-10-15 is not this backup and stays.
   - Configuration: `COPREPAN_LEGACY_ARCHIVE_ROOT`, `COPREPAN_LEGACY_ARCHIVE_TARGET_ID`, `COPREPAN_LEGACY_BACKUP_ROOT`
     (`.env.example`, names only); `scripts/preservation_backup.py --holding LEGACY` makes, verifies and receipts the backup. The
     role list of `config/storage_targets.yml` is unchanged: LEGACY is a holding, not a role.
2. **Tree `coprepan`** = the legacy repository's working tree as frozen (tag `frozen-2026-10`), every file including the gitignored
   data (`json_annotated`, `json_raw`, `json_raw_extended`, `data/db` with the SQLite WAL and SHM unchanged, `state/annotation`, logs,
   `backup/`, `outputs/`), except `.git/` (replaced by a verified bundle `_git_bundle/coprepan.bundle`), `.venv/` (described in
   `docs/legacy_environment.txt`), `.pytest_cache/` and `__pycache__/`; plus `_derived/`: consistent single-file snapshots of the two
   SQLite databases, made with the SQLite backup API on an isolated copy (the originals were never opened).
3. **Scientific classification (binding).** The legacy press corpus is a **frozen legacy research holding** (`legacy_frozen`): not
   `native_v3`, not registered in or admitted to CO.PRE.PAN 3.0 production, and the archive is **never a pipeline input** (A6). A
   later import into the HISTORIC holding would be a separate, separately authorised act that copies from the archive into HISTORIC
   under its own decision; nothing reads LEGACY as a source.
4. **Compatibility with contract §2.2 and CPD-0031.** §2.2 places in PRODUCTION or HISTORIC the source material that a holding
   *processes or releases* ("a recording or document that a holding processes or releases is never only in LEGACY"). No CO.PRE.PAN
   holding processes or releases the legacy corpus (legacy index §7: never migrated into 3.0 as corpus); it is an earlier corpus
   version and closed research evidence — the content §2.2 names for LEGACY. CPD-0031 decision 3 called HISTORIC "the place for the
   legacy press corpus *as source material*": that stays true for the day it becomes source material, by the import of point 3. There
   is no normative contradiction; only CPD-0031's "no activation" is superseded.
5. **Freeze manifest.** The archived tree is compared file by file with `docs/legacy/freeze/coprepan-legacy-2026-06/files.jsonl`;
   the freeze listing is not rewritten. With the PRESERVED tree, its B1 backup and the read-back, steps 2 and 3 of the frozen release
   (legacy index §5) are done; step 4 (a study loader reads the frozen copy) stays open.
6. **Local original.** The local legacy tree on C: stays complete; no A7 release. The CO.RA.PAN tools that read
   `COPREPAN_JSON_ANNOTATED` keep reading the local tree; nothing is switched to the archive.

## Not decided here

The release of the local original or of the 2026-10-15 secondary; a HISTORIC import or a `legacy_refetched` backfill; any change
of the legacy corpus's standing.
