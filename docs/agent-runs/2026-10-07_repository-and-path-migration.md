# CO.PRE.PAN / panhispanic_media_corpora — Repository and Path Migration

```text
run_started_at:      2026-10-07T20:20:00+02:00   (first clock reading; the session began a few minutes earlier)
run_ended_at:        2026-10-07T20:26:11+02:00   (last clock reading before this report was written)
timezone:            Europe/Berlin
wall_clock_seconds:  371   (between the two readings above)
status:              PARTIAL
kind of run:         implementation (infrastructure) with reproducibility / infrastructure-integrity validation
EXTERNAL_API_USAGE = NONE   (no network access, no model call)
```

**Status `PARTIAL`.** Two of the three moves are done and verified; the third — renaming this
repository — could not be performed by the agent and is handed to the operator as one script (§10).
The status claims only that repository, path and archive structure were migrated and checked as
far as described here. It is **not** a scientific validation and **not** a production activation
of anything in CO.PRE.PAN; no stage state in `docs/STATUS.md` changed.

## 1. Objective and operator brief

Bring the local repositories of CO.RA.PAN / CO.PRE.PAN under one roof,
`C:\dev\panhispanic_media_corpora\`, with `corapan\` (authoritative CO.RA.PAN), `coprepan\`
(authoritative CO.PRE.PAN, from today's `coprepan_playground`) and `legacy\` (frozen archives of
the old `coprepan` and of `corapan_coprepan_studies`). Audit first, migrate only without a
blocker, change CO.RA.PAN only where a path correction is unavoidable, never hide an old path
behind a junction. This brief explicitly authorised moving the reference repositories that
`AGENTS.md` §2 otherwise declares read-only.

## 2. State at the start (measured 2026-10-07, 20:17–20:21 +02:00)

The roof already existed: an earlier run of the same day had moved CO.RA.PAN 3.0 there.

| Location | Role | Git | Working tree |
|---|---|---|---|
| `C:\dev\panhispanic_media_corpora\corapan` | CO.RA.PAN 3.0, authoritative (was `C:\dev\corapan_playground`, moved 19:15) | `main` `43185639d`, origin `FTacke/corapan_playground`; linked worktree `worktrees\corapan\gemma-commercial-requal` | **a parallel agent session was working in it** ("Path Architecture Final Cleanup", started 20:14): six modified storage/test files, two untracked documents |
| `C:\dev\coprepan_playground` | COPREPAN 3.0 foundation | **no git metadata** (by design: `docs/STATUS.md` §3, the operator initialises it) | 34 files, 220,585 bytes |
| `C:\dev\coprepan` | legacy COPREPAN and legacy corpus | `main` `3e6bdd3`, origin `FTacke/coprepan-app`, clean | 32,598 files, 18,813,086,219 bytes (mostly git-ignored corpus data) |
| `C:\dev\corapan_coprepan_studies` | cross-corpus studies | `main` `679e14c`, origin `FTacke/corapan_coprepan_studies` | 3,385 files, 1,014,533,482 bytes; foreign changes: `M config/label_vocabulary.yml`, untracked two run reports and `studies/past_tense_study_sidg/` |
| `C:\dev\corapan` | CO.RA.PAN 1.0 (legacy web app and radio data) | `main` `713629b`, remotes `origin` and `legacy-webapp` | 35 dirty entries |
| `C:\dev\panhispanic_media_corpora\legacy` | archive target | — | existed, empty |

No submodules, no junctions or symlinks in any of the three trees to be moved, no stash, no
linked worktree outside CO.RA.PAN 3.0. Also present and not part of this run:
`corapan_workspace`, `corapan_storage`, `worktrees`, `_relocation` under the roof;
`C:\dev\corapan_regress`, `C:\dev\corapan_hygiene_backup_20260926`.

Active components: two scheduled tasks / processes (`CORAPAN_Wave4LiveSupervisor` pid 37288,
`CORAPAN_Wave4Preservation` pid 41004), both already running from the new CO.RA.PAN checkout. No
process, scheduled task, user/machine environment variable or `PATH` entry referenced
`coprepan`, `coprepan_playground` or the studies repository. No `.code-workspace` file exists
under `C:\dev`. `LongPathsEnabled` = 1.

## 3. Path dependencies found

| Where | Reference | Class | Action |
|---|---|---|---|
| CO.RA.PAN `.env` (not versioned) | `CORAPAN_STUDIES_ROOT=C:\dev\corapan_coprepan_studies` | **active runtime configuration** | updated |
| CO.RA.PAN `.env` | `COPREPAN_JSON_ANNOTATED=C:\dev\coprepan\json_annotated` | **active runtime configuration** | updated |
| CO.RA.PAN `.env` | `CORAPAN_LEGACY_ROOT=C:\dev\corapan` | active runtime configuration | unchanged: that tree was not moved |
| CO.RA.PAN `AGENTS.md` lines 7, 20 | old locations of the studies and legacy COPREPAN repositories | operator / agent path | updated, committed |
| CO.RA.PAN `scripts/mine_e2d_dnr_candidates_coprepan.py` docstring | "default `C:/dev/coprepan/json_annotated`" (no such default exists in code) | operator path in active code comment | reworded, committed |
| CO.RA.PAN `config/corpus_paths.yml`, `config/storage_targets.yml`, `storage/roots.py` | `${CORAPAN_STUDIES_ROOT}`, `${COPREPAN_JSON_ANNOTATED}`, `${CORAPAN_LEGACY_ROOT}` | logical, environment-resolved | none needed |
| this repository `AGENTS.md` §2, `CLAUDE.md` | table of reference repositories | operator / agent path | updated |
| this repository `src/`, `config/`, `tests/` | none | — | — |
| studies `config/corpus_paths.yml`, `README.md` | `C:/dev/coprepan/json_annotated`, `C:/dev/corapan/media/transcripts` | frozen legacy reference | **left as is** (see §9, §11) |
| studies result files, legacy COPREPAN `tools/*.py` (`C:/dev/coprepan-app/...`) | self-references of generated outputs, old debug tools | frozen legacy reference | left as is |
| CO.RA.PAN `data/inventories/…coprepan_v1.json`, `data/human_review/e2d_open_anchor_review_blind_v1.json`, `artifacts/audit/…` | recorded input root of past runs | frozen evidence | left as is |
| CO.RA.PAN `docs/lcp/*`, `docs/legacy-corapan-data.md`, `docs/nlp/LEGACY_ANNOTATION_ARCHAEOLOGY_V1.md`, `docs/radio_ingest/…`, 26 files under `docs/agent-runs/` | old paths in dated specifications, audits and run reports | historical documentation | left as is |
| this repository, bootstrap run report of 2026-10-06 | old names | historical documentation | left as is |

No dependency of CO.RA.PAN 3.0 on `coprepan_playground` exists in code or configuration, and
none of this repository on any other repository.

## 4. Migration decision

- Move by atomic same-volume rename (`System.IO.Directory.Move`), refusing on any collision. No
  copy, no junction. A rename copies no bytes, so "unchanged" is proven by a stat-only census
  (relative path, size, mtime of every file) before and after plus identical git state; no file
  of the legacy tree was opened, and its tests were not run.
- `C:\dev\coprepan` → `legacy\coprepan`; `C:\dev\corapan_coprepan_studies` →
  `legacy\corapan_coprepan_studies`; `C:\dev\coprepan_playground` → `coprepan`.
- **`C:\dev\corapan` is not moved.** The brief's target picture shows a `legacy\corapan` slot but
  orders no such move; the running CO.RA.PAN daemons resolve `CORAPAN_LEGACY_ROOT` to it, the
  frozen studies configuration hard-codes it, and the relocation run of the same day deliberately
  left it. Moving it is an operator decision (§11).
- CO.RA.PAN: only the two `.env` values and the two tracked wording corrections; nothing in the
  files of the parallel session.
- No `git init` here: initialising git is reserved to the operator (`AGENTS.md` §4).

## 5. What was done

| Time (+02:00) | Step | Result |
|---|---|---|
| 20:21 | census and `git status --porcelain --ignored` of the three trees; baseline `python -m pytest` here | 72 passed |
| 20:22:21 | `C:\dev\coprepan` → `C:\dev\panhispanic_media_corpora\legacy\coprepan` | moved |
| 20:22:21 | `C:\dev\corapan_coprepan_studies` → `C:\dev\panhispanic_media_corpora\legacy\corapan_coprepan_studies` | moved |
| 20:23 | CO.RA.PAN `.env`: the two values replaced byte-exactly by script (file not read into the session; other lines and line endings untouched, 2,085 → 2,151 bytes) | done |
| 20:24 | CO.RA.PAN `AGENTS.md` (2 lines), mining-script docstring (1 line) | committed `57c8cc750` |
| 20:24 | this repository: `AGENTS.md` title and §2 table, `CLAUDE.md`, history line in `docs/STATUS.md` | changed, not committed (no git) |
| 20:25:42 | `C:\dev\coprepan_playground` → `C:\dev\panhispanic_media_corpora\coprepan` | **FAILED**: "Der Prozess kann nicht auf die Datei zugreifen, da sie bereits von einem anderen Prozess verwendet wird." — the folder is the working directory of this agent session and of VS Code. Nothing was changed by the attempt. |

One mistake made and repaired: the first edit of the mining script rewrote the whole file's line
endings (309 lines in the diff). The file was restored from `HEAD` (it had been clean) and the one
line replaced byte-exactly; the committed diff is 1 line.

Moved: two directories. Deleted: nothing. Overwritten: nothing. Copied: nothing.

## 6. Directory picture at the end of the run

```text
C:\dev\panhispanic_media_corpora\
├── corapan\                         CO.RA.PAN 3.0, authoritative
├── corapan_workspace\               its runtime workspace   (earlier run)
├── corapan_storage\                 its outage spool        (earlier run)
├── worktrees\corapan\…              its linked worktree     (earlier run)
├── _relocation\                     scripts and records of the moves
└── legacy\
    ├── coprepan\                    archived unchanged
    └── corapan_coprepan_studies\    archived unchanged

C:\dev\coprepan_playground\          still here: becomes ...\panhispanic_media_corpora\coprepan (§10)
C:\dev\corapan\                      CO.RA.PAN 1.0, not moved (§4)
```

`C:\dev\coprepan`, `C:\dev\corapan_coprepan_studies` and `C:\dev\corapan_playground` do not
exist, neither as directories nor as links.

## 7. Git

| Repository | Before | After |
|---|---|---|
| `legacy\coprepan` | `main` `3e6bdd3350913d55c07efe500036bf752de65cc2`, clean | identical; remote unchanged |
| `legacy\corapan_coprepan_studies` | `main` `679e14c10a05632d2da631a8d0a9f193dc174ee4`, 4 foreign entries | identical, the same 4 entries; remote unchanged |
| `corapan` | `43185639d` at the audit; the parallel session committed up to `f83ebbfaa` meanwhile | `57c8cc750a54848d2a0b66dded90e9b1127ea941` — this run's only commit, pathspec-limited to `AGENTS.md` and `scripts/mine_e2d_dnr_candidates_coprepan.py` (3 insertions, 3 deletions). **Not pushed.** `main` is 4 ahead of `origin/main`, three of those commits are the parallel session's. |
| this repository | no git | no git; nothing could be committed |

## 8. Checks and results

| Check | Result |
|---|---|
| Census `legacy\coprepan` before / after | 32,598 / 32,598 files, 18,813,086,219 / 18,813,086,219 bytes, listing digest identical (`6c20d3d1…896fae`) |
| Census `legacy\corapan_coprepan_studies` before / after | 3,385 / 3,385 files, 1,014,533,482 / 1,014,533,482 bytes, listing digest identical (`54f3d139…379145`) |
| `git status --porcelain --ignored`, both archives, before / after | byte-identical |
| `git fsck --connectivity-only`, both archives | no error (dangling trees only) |
| CO.RA.PAN root registry (`roots.current()`), read-only | `repo`, `runtime`, `spool`, `legacy_corapan`, `studies_reference`, `coprepan_annotated` all resolve and exist; `corpus_paths.yml` keys resolve to the new locations |
| CO.RA.PAN `python scripts/check_hardcoded_paths_v1.py` (after the edits) | 49 baselined files, 62 hits, 0 problems — unchanged from the relocation run's figure |
| CO.RA.PAN focused path gates: `test_path_roots_v1`, `test_cluster_layout_v1`, `test_hardcoded_path_gate_v1`, `test_path_portability_v1`, `test_runtime_workspace_v1`, `test_storage_outage_spool_v1` | 164 passed |
| CO.RA.PAN daemons (pids 37288, 41004) | still running after the moves |
| this repository `python -m pytest` before and after the edits | 72 passed / 72 passed |
| this repository `python -m pytest` **from the new location** | **not run** — the move has not happened; the script of §10 runs it |

**Not run, deliberately:** the full CO.RA.PAN suites (`production_readiness`, `repository_hygiene`,
`component_qualification`, …). A parallel session was editing and committing storage code in that
checkout during this run, and the full suite rewrites tracked artefact files; a result would not
have been attributable to this run. The focused gates above were run against a tree containing
that session's in-flight work, which is the tree as it was, not a clean `HEAD`. Not run, by rule:
the legacy COPREPAN test suite.

Paths of 260 characters or more (measured): `legacy\coprepan` 0 → 3, studies 31 → 38. With
`LongPathsEnabled` = 1 the census read all of them.

## 9. Old paths that remain

**Active:** `C:\dev\coprepan_playground` — until the script of §10 has run. Nothing else: no
active code or configuration uses `C:\dev\coprepan` or `C:\dev\corapan_coprepan_studies` as a
current location any more.

**Kept on purpose (frozen or historical):**

- everything inside the two archives, including the studies `config/corpus_paths.yml`, whose
  `coprepan_annotated: "C:/dev/coprepan/json_annotated"` **no longer resolves**. The studies code
  therefore cannot read the COPREPAN corpus from its archived state without a local edit. This
  follows from "archive unchanged" and is a consequence the operator should know, not a defect
  that was repaired;
- the legacy COPREPAN `.venv` was moved with the tree and was not rebuilt; console-script
  launchers inside it embed the old absolute path (not verified individually, not executed);
- recorded input roots in CO.RA.PAN evidence and inventories, and old paths in dated CO.RA.PAN
  specifications, audits and run reports (§3);
- the bootstrap run report of this repository;
- agent state under `~\.claude\projects\` (`c--dev-coprepan`, `c--dev-corapan-coprepan-studies`,
  `c--dev-coprepan-playground`, `c--dev-corapan-playground`) and VS Code's recent-folder entries:
  untouched.

## 10. Hand-over: the last move

`C:\dev\panhispanic_media_corpora\_relocation\relocate_coprepan_checkout.ps1` (new file; nothing
there was overwritten). Close every VS Code window and agent session that has
`C:\dev\coprepan_playground` open, then from a plain PowerShell window:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File C:\dev\panhispanic_media_corpora\_relocation\relocate_coprepan_checkout.ps1
```

It refuses on a collision, renames atomically, compares file count and bytes, copies the agent
state to `~\.claude\projects\c--dev-panhispanic-media-corpora-coprepan` (old directory kept) and
runs `python -m pytest` from the new place (expected: 72 passed). The agent-facing files of this
repository already name the new location, so until the script has run they are one step ahead of
the disk.

## 11. Open risks and decisions

1. **The CO.PRE.PAN move is not done** (§10). Until then the target picture is incomplete.
2. **Git for this repository is the operator's decision** and is still open. The brief asked for
   the migration to be committed; here that was impossible. This run's changes to this repository
   sit uncommitted beside the bootstrap files.
3. **`C:\dev\corapan` → `legacy\corapan`** was not ordered and not done. It would need
   `CORAPAN_LEGACY_ROOT` changed with the CO.RA.PAN daemons stopped, and it would break the second
   hard-coded path of the frozen studies configuration.
4. **CO.RA.PAN commit `57c8cc750` is local only**, and the full CO.RA.PAN regression was not run
   by this run (§8).
5. The studies archive contains uncommitted foreign work (`studies/past_tense_study_sidg/`, two
   run reports, one modified file). It was preserved exactly, and it exists only in that working
   tree — it is in no commit and on no remote.
6. The CO.RA.PAN documentation of the local layout
   (`docs/architecture/PATH_REFERENCES_AND_NAMED_ROOTS.md` §12) does not yet mention `legacy\` or
   `coprepan\`. That file was being edited by the parallel session and was left alone.

## 12. Gates

None touched. All acquisition and production gates of `docs/STATUS.md` §5 remain open.

## 13. Working-tree classification (this repository; no git exists)

| Entry | Class |
|---|---|
| `AGENTS.md`, `CLAUDE.md`, `docs/STATUS.md` (changed), `docs/agent-runs/2026-10-07_repository-and-path-migration.md` (new) | left in place: there is no git to commit to; to be included when the operator initialises it |
| caches | none written (`-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`) |

Outside this repository: `_relocation\relocate_coprepan_checkout.ps1` (new, kept for the
operator); census files and helper scripts in the session scratchpad (not kept).

## 14. Recommended next run

None by an agent before the operator has run the script of §10. After that: one short run from
`C:\dev\panhispanic_media_corpora\coprepan` that confirms the suite from the new place, and — if
the operator decides so — initialises git and makes the first commit.

## 15. Operator report

1. **Result:** legacy COPREPAN and the studies repository are archived unchanged under
   `panhispanic_media_corpora\legacy\`; CO.RA.PAN resolves both new locations; the rename of
   `coprepan_playground` is blocked by the session living in it and is prepared as one script.
2. **Status:** `PARTIAL`. Claims infrastructure integrity of what was moved; claims no scientific
   validation, no production activation, and no full CO.RA.PAN regression.
3. **Consequence:** CO.RA.PAN keeps working against the archived reference data; the archived
   studies code can no longer find the COPREPAN corpus at its hard-coded path.
4. **Next:** the operator runs `relocate_coprepan_checkout.ps1`.
5. **Files:** see §5 and §13. Moved: two directories. Deleted or overwritten: nothing.
6. **Untouched:** `C:\dev\corapan`; the content of both archives; the parallel session's files in
   CO.RA.PAN; no push, no `git init`, no history rewrite; no network, `EXTERNAL_API_USAGE = NONE`.
