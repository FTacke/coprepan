# CO.PRE.PAN — Repository Migration Closure and Git Initialisation

```text
run_started_at:      2026-10-07T20:32:24+02:00   (first clock reading; the session began shortly before)
run_ended_at:        2026-10-07T20:34:36+02:00   (last clock reading, after the first push; the completing commit followed)
timezone:            Europe/Berlin
wall_clock_seconds:  132   (between the two readings above)
status:              PASS
kind of run:         implementation (infrastructure) with reproducibility / infrastructure-integrity validation
EXTERNAL_API_USAGE = NONE   (no model call, no external API; the only network use is git transport
                             to the repository's own remote, authorised by the operator brief — §7)
```

The status claims only that this repository works completely from its new location, that no
active dependency on the old location is left, and that git holds the foundation as it stands.
It is **not** a scientific validation and **not** a production activation of anything in
CO.PRE.PAN. No stage state in `docs/STATUS.md` changed; every gate of `docs/STATUS.md` §5 is open.

**Predecessor.** [`2026-10-07_repository-and-path-migration.md`](2026-10-07_repository-and-path-migration.md)
ended `PARTIAL` because the rename of this repository was blocked by the session living in it. That
report stays as written, including its status. This report closes what it left open (its §10,
§11 items 1 and 2, §14).

## 1. Objective and operator brief

Close the repository and path migration after the operator's successful move
`C:\dev\coprepan_playground` → `C:\dev\panhispanic_media_corpora\coprepan`: verify the new
location, confirm the suite there, initialise git on `main` without any legacy history, commit the
existing foundation as the first commit, and — by the brief's addendum — configure
`https://github.com/FTacke/coprepan.git` as `origin` and push `main` once branch, commit, clean
tree, green tests and remote are all confirmed. The brief is the operator's request for the commit
and the push (`AGENTS.md` §4).

Not in scope, and not done: any change of domain architecture, any import from legacy, any studies
infrastructure, any move of `C:\dev\corapan`, any change to the archived repositories.

## 2. The operator's rename (sourced: operator brief, output of the hand-over script)

The operator ran `C:\dev\panhispanic_media_corpora\_relocation\relocate_coprepan_checkout.ps1`
(written by the predecessor run; read in this run, not modified).

```text
MOVED C:\dev\coprepan_playground -> C:\dev\panhispanic_media_corpora\coprepan
files 35 -> 35
bytes 239379 -> 239379
72 passed
pytest exit code: 0
```

A first attempt had been refused because of an open handle; by the script's design
(`System.IO.Directory.Move`, atomic, same volume) and its own message it changed nothing. The
second attempt succeeded. These five lines are the operator's report of the script output; this
run did not observe the move. What this run measured itself is in §3.

## 3. State found (measured 2026-10-07, 20:32 +02:00)

| Check | Result |
|---|---|
| `C:\dev\coprepan_playground` | does not exist (`Test-Path` false) |
| `C:\dev\panhispanic_media_corpora\coprepan` | plain directory; `LinkType` empty |
| Census of the new location before any edit of this run | 35 files, 239,379 bytes — equal to the script's figures |
| Links under the roof | `coprepan`, `corapan`, `corapan_storage`, `corapan_workspace`, `legacy`, `worktrees`, `_relocation`, and `legacy\coprepan`, `legacy\corapan_coprepan_studies`: all plain directories, no junction, no symlink |
| `.git` here | absent |
| Caches, environments, editor or agent state inside the tree (`__pycache__`, `.pytest_cache`, `.venv`, `.vscode`, `.claude`, `.idea`) | none |
| `.env`, `*.log`, `*.db`, `*.sqlite`, `*.tmp`, `*.bak`, `*.pyc` inside the tree | none |

Reference repositories, read-only (`git rev-parse HEAD`, `git status --porcelain`; nothing
written, no legacy database opened, legacy suite not run):

| Repository | State | Compared with the predecessor report §7 |
|---|---|---|
| `legacy\coprepan` | `main` `3e6bdd3350913d55c07efe500036bf752de65cc2`, clean | identical |
| `legacy\corapan_coprepan_studies` | `main` `679e14c10a05632d2da631a8d0a9f193dc174ee4`; `M config/label_vocabulary.yml`, untracked two run reports and `studies/past_tense_study_sidg/` | identical, the same 4 foreign entries |
| `C:\dev\corapan` | exists | not inspected further; not part of this run |
| `corapan` (CO.RA.PAN 3.0) | not inspected | not part of this run |

## 4. Search for the old location

Search for `coprepan_playground` over the whole tree: 13 hits in 3 files.

| File | Hits | Class |
|---|---|---|
| `AGENTS.md` line 1 | 1 | current, deliberate: "working name until 2026-10-07: `coprepan_playground`" — a statement about the former name, not a location in use |
| `docs/agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md` | 2 | historical run report, left as is |
| `docs/agent-runs/2026-10-07_repository-and-path-migration.md` | 10 | historical run report, left as is |

`src/`, `config/`, `tests/`, `pyproject.toml`, `.env.example`, `.editorconfig`, `.gitattributes`,
`.gitignore`, `README.md`: **no hit**. No absolute path at all in `src/`, `config/`, `tests/`
(`test_no_absolute_path_in_tracked_logic_or_config` passes). `AGENTS.md` §2 and `CLAUDE.md`
already named the new locations (changed by the predecessor run, one step ahead of the disk until
the move; now in agreement with it).

**Result: no active dependency on `C:\dev\coprepan_playground`.**

## 5. Files changed by this run

Three small factual corrections, all required because the facts they state changed in this run;
no path was rewritten and no domain or architecture content was touched.

| File | Change |
|---|---|
| `docs/STATUS.md` §3, row "Git" | "not initialised — the operator initialises it …" → initialised 2026-10-07, branch, `origin`, link to this report |
| `docs/STATUS.md` §8 | one history entry added for this run; the entry of the predecessor run is unchanged |
| `docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md` §12 item 2 | one line appended: git initialisation done 2026-10-07, pointer to `docs/STATUS.md` |
| `docs/agent-runs/2026-10-07_coprepan-repository-migration-closure.md` | this report (new) |

Deliberately unchanged: the machine-readable block of `docs/STATUS.md`
(`"git_initialised_by_bootstrap": false` is a statement about the bootstrap and remains true;
`as_of` is not raised because no asserted state changed); `AGENTS.md` §4 ("The bootstrap run
created no git metadata; the operator initialises git. From then on: …" — still accurate);
both earlier run reports.

Moved: nothing. Deleted: nothing. Overwritten: nothing. Copied: nothing.

## 6. Tests from the new location (measured)

```text
python -m pytest -p no:cacheprovider      (PYTHONDONTWRITEBYTECODE=1; Python 3.12.10, pytest 9.1.1)
rootdir: C:\dev\panhispanic_media_corpora\coprepan
collected 72 items
72 passed in 0.07s        exit code 0     — before any edit of this run
72 passed                 exit code 0     — after the edits of §5 and `git init`, before the commit
```

No additional test exists; 72 is the current full suite (`test_naming.py` 51,
`test_repository_contract.py` 18, `test_test_guards.py` 3). No cache or bytecode was written.

## 7. Git

**Initialisation.** `git init -b main` (git 2.53.0.windows.1) in the new root. No history from
`legacy\coprepan` or any other repository was fetched, merged or transplanted; no file was copied
in from anywhere. No remote existed after `git init`.

**Pre-commit inventory.** `git status --porcelain -uall` listed exactly the 35 files of the census
as untracked; `git status --ignored` listed nothing ignored. Checked before staging:

| Class | Finding |
|---|---|
| `.gitignore` | present, anchored and commented; covers environments, caches, `.env` / `.env.*` (except `.env.example`), keys, local config, editor and agent state, logs, databases, corpus material, models, archives |
| Secrets | none: no `.env`; `.env.example` holds five empty `COPREPAN_*_ROOT` names; a pattern search (key, secret, password, token, private-key header, common token prefixes) over everything outside `docs/` hit only a `.gitignore` comment, the `/secrets/` rule, a pinned package name and two docstring lines |
| Generated files, caches, temporary files | none present |
| Machine-specific artefacts | none. Absolute workstation paths occur only in `AGENTS.md` §2, `CLAUDE.md`, the new history entry of `docs/STATUS.md` §8 and the run reports — operator documentation, where `AGENTS.md` §2 places them — never under `src/`, `config/`, `tests/` |
| Line endings | `.gitattributes` (`* text=auto eol=lf`) is in force from the first commit; the system-level `core.autocrlf=true` of Git for Windows is overridden by it |

**The first commit and everything after it** — commit hash, `git remote -v`, the push result, the
confirmed `origin/main` and the final working-tree state — cannot be written into the commit that
contains this file. They are recorded in §7a by a second, report-only commit made after the push
of the first.

## 7a. Commit, remote and push record

Written after the push of the first commit (measured 2026-10-07, 20:34 +02:00).

| Item | Value |
|---|---|
| Staging | explicit pathspecs (the eight root files, `config/storage_targets.yml`, `docs`, `src/coprepan`, `tests`); 36 files staged = the 35 of the census + this report; nothing left untracked, nothing ignored; all 36 `i/lf w/lf` |
| Foundation commit (first commit, root, no parent) | `4bfb52a06de4ad36ec5c771e1463dad72d335a9f` — "Initial commit: COPREPAN 3.0 foundation", 2026-10-07T20:34:20+02:00, 36 files |
| Branch | `main` |
| `origin` before this run | none (`git remote -v` empty after `git init`); nothing was overwritten |
| `git remote add origin https://github.com/FTacke/coprepan.git` | exit 0 |
| `git remote -v` | `origin  https://github.com/FTacke/coprepan.git (fetch)` / `origin  https://github.com/FTacke/coprepan.git (push)` |
| `git ls-remote origin` before the push | no refs: the remote repository was empty |
| Push conditions of the brief | branch `main`; foundation commit present; working tree clean; 72 passed; `origin` unambiguous — all met before pushing |
| `git push -u origin main` | exit 0: `* [new branch] main -> main`; `branch 'main' set up to track 'origin/main'` |
| `git ls-remote origin` after the push | `refs/heads/main` and `HEAD` = `4bfb52a06de4ad36ec5c771e1463dad72d335a9f` |
| `git rev-parse origin/main` | `4bfb52a06de4ad36ec5c771e1463dad72d335a9f` — equal to the local commit |
| Working tree after the push | clean (`## main...origin/main`, no entry) |

No force, no history rewrite, no second remote, no tag.

**The completing commit.** This section, the header values and §12 are added by a second commit
that changes this file only and is pushed to the same branch. A commit cannot name itself: its
hash is the `HEAD` of `main` after this run and is given in the operator's closing message, not
here. The **foundation commit is `4bfb52a0…`**; `HEAD` is one report-only commit ahead of it.

## 8. Directory picture (measured, top level only)

```text
C:\dev\panhispanic_media_corpora\
├── corapan\                         CO.RA.PAN 3.0, authoritative
├── coprepan\                        CO.PRE.PAN 3.0, authoritative — this repository
├── legacy\
│   ├── coprepan\                    archived unchanged
│   └── corapan_coprepan_studies\    archived unchanged
├── corapan_workspace\               CO.RA.PAN runtime workspace   (not part of this run)
├── corapan_storage\                 CO.RA.PAN outage spool        (not part of this run)
├── worktrees\                       CO.RA.PAN linked worktree     (not part of this run)
└── _relocation\                     scripts and records of the moves

C:\dev\corapan\                      CO.RA.PAN 1.0 — deliberately still separate
```

The schema of the brief is reached for `corapan\`, `coprepan\`, `legacy\coprepan\` and
`legacy\corapan_coprepan_studies\`.

## 9. Old paths that remain

**Active: none.**

**Historical or frozen, kept on purpose:**

- the 12 mentions of `coprepan_playground` in the two earlier run reports of this repository, and
  the former-name note in the title of `AGENTS.md`;
- the "formerly `C:\dev\…`" notes in the reference table of `AGENTS.md` §2;
- everything inside the two archives, with the consequence recorded in the predecessor report §9
  (the studies' hard-coded corpus path no longer resolves) — unchanged by this run;
- the comment header and the `$src` value of `_relocation\relocate_coprepan_checkout.ps1`: an
  executed one-off script, kept as the record of the move;
- agent state under `~\.claude\projects\c--dev-coprepan-playground` (kept by the script's
  copy-never-move convention) and editor recent-folder entries: not inspected, not touched.

## 10. Boundaries

- **`C:\dev\corapan`** (CO.RA.PAN 1.0) is deliberately still separate. The `legacy\corapan` slot
  stays empty; moving it is a separate operator decision with its own preconditions (predecessor
  report §11 item 3). Nothing was done towards it.
- **Studies.** `legacy\corapan_coprepan_studies` is an archive. No studies infrastructure was
  built here; a later rebuild is its own run against the cross-corpus contract (master plan,
  Phase 7).
- **CO.RA.PAN 3.0** was not opened by this run. The open points the predecessor report lists for
  it (its §11 items 4 and 6) are not closed by this report.

## 11. Gates

None touched. All acquisition and production gates of `docs/STATUS.md` §5 remain open.

## 12. Working-tree classification

| Entry | Class |
|---|---|
| all 36 files of the repository, including the three changed documents of §5 and this report | committed |
| ignored or untracked entries | none exist |

Outside the repository: one commit-message file per commit in the session scratchpad (not kept).
The archives were re-read after the push: `legacy\coprepan` `3e6bdd33…`, clean;
`legacy\corapan_coprepan_studies` `679e14c1…`, the same 4 foreign entries. Unchanged.

## 13. Gate assessment of the brief

| Condition for `PASS` | Evidence |
|---|---|
| `coprepan` works completely from the new place | §3, §6 |
| tests green there | §6: 72 passed, twice |
| no active dependency on `C:\dev\coprepan_playground` | §4 |
| git cleanly initialised, foundation committed | §7, §7a |
| no legacy holdings changed | §3, §12 |

## 14. Recommended next run

No action is needed to close the migration. The next run in the repository's own sequence is
**Foundation Core I** (master plan §12 item 3), when the operator orders it.

## 15. Operator report

1. **Result:** CO.PRE.PAN 3.0 lives at `C:\dev\panhispanic_media_corpora\coprepan`, is under git
   on `main`, and its foundation is on `origin` (`https://github.com/FTacke/coprepan.git`).
2. **Status:** `PASS` — reproducibility / infrastructure integrity only. No scientific validation,
   no production activation; the rename itself is reported from the operator's script output, not
   observed by this run.
3. **Consequence:** none for method or production. From here on the working-tree rules of
   `AGENTS.md` §4 apply in full, and the remote is no longer an open point.
4. **Next:** no action needed for the migration; Foundation Core I when ordered.
5. **Files:** created this report; changed `docs/STATUS.md` (2 places) and the master plan
   (1 line). Moved, deleted, overwritten: nothing.
6. **Untouched:** `C:\dev\corapan`, CO.RA.PAN 3.0, the content of both archives, the predecessor
   report. No crawl, no feed or sitemap fetch, no external API, no model call; network use was
   `git ls-remote` and `git push` to `origin` only.
