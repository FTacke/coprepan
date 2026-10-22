# Audit closure: canonical run reporting, safe merge and worktree lifecycle — 2026-10-22

```text
run_started_at:      2026-10-22T09:44:05+02:00   (first clock reading of the run)
run_ended_at:        2026-10-22T10:13:47+02:00   (last clock reading before this report's final commit)
timezone:            Europe/Berlin
wall_clock_seconds:  1782                        (between the two readings; the closing sequence below follows it)
```

- **Kind of run:** implementation — closure of the consistency audit of 2026-10-22. No scientific validation, no activation,
  no stage or gate state changed.
- **Status: `PASS`** for the closure scope of the brief: the report procedure is in place and used; the audit's repairs and
  this run's are merged into the local `main`; CPD-0032 is complete and the suite is green; the qualification tool cannot
  write into the shared umbrella any more; the worktree rule exists and is applied to this run's worktree as its last act.
  **It does not claim** that `main` is pushed (it is not, §E), that any finding of the audit other than F-02 and F-22 is
  closed, or anything scientific.
- `EXTERNAL_API_USAGE = NONE`. Network: `git fetch`/`git push` of this run's own branch to `origin` only.

## Brief

Operator brief "CO.PRE.PAN — Audit Closure, Canonical Run Reporting, Safe Merge & Worktree Lifecycle" (2026-10-22):
take over CO.RA.PAN's procedure for publishing run reports on `main`; publish the audit report; add the missing section to
CPD-0032 on the operator's authorisation; repair the qualification tool (F-22); merge the audit branch if safe; establish a
safe worktree closure and apply it to the audit's worktree; CO.RA.PAN read-only. Out of scope: everything scientific, the
release-contract revision 2, D116, acquisition, migration.

## A. Starting position

| | |
|---|---|
| `main` (local) | `e9e291d`, clean; **5 commits ahead of `origin/main` (`a496b23`)**: `7fcd6d7`, `17fac47`, `a8122f9`, `dad33b5`, `e9e291d` (the CPD-0031/0032 runs of 2026-10-19/20, never pushed to `main`). They reached `origin` on 2026-10-22 as ancestors of the audit branch when the audit pushed it — a consequence the audit did not state; recorded here |
| Audit branch | `audit/2026-10-22-full-consistency` at `1557ca6`, on `origin` (equal), parent `e9e291d` |
| Audit worktree | `C:/dev/panhispanic_media_corpora/worktrees/coprepan/full-audit-2026-10-22`, clean |
| Other CO.PRE.PAN worktrees | four, each clean and integrated in `main` (§E) |
| Reporting rules | AGENTS §16 (one dated report per run), `docs/agent-runs/README.md`; no publication procedure, no index |
| CO.RA.PAN (read-only) | `main` at `8824ef019`; 41 linked worktrees |

## B. CO.RA.PAN as reference (read-only)

**Reporting — found:**
- `scripts/publish_run_report_v1.py` (since 2026-10-15) publishes a report as a documentation-only commit on `main`: git plumbing on a
  temporary index (`read-tree` of main, `update-index` of the report's committed blob and of a generated `docs/agent-runs/INDEX.md`
  row, `write-tree`, `commit-tree -p main`), then `update-ref refs/heads/main <new> <old>` as compare-and-swap, then the two files written
  and staged in the main checkout.
  - It refuses non-report paths, uncommitted reports, and a main checkout holding a different change at the target paths.
  - It is used: 134 publication commits with the trailer `Published-By: publish_run_report_v1` on its `main`.
  - Rule: CO.RA.PAN AGENTS.md:349–367, CLAUDE.md:9.
- Its limits, from reading the code:
  - `INDEX.md` is read from disk before `main`'s HEAD, so a concurrent publication can lose its row.
  - `--status` is not compared with the report's own `Status:` line, and no header field is validated.
  - A re-publication overwrites without being asked.
  - Its `push` is in practice always blocked, because local `main` is far ahead of `origin/main`.

**Worktrees — found:**
- `scripts/local_storage_audit_v1.py` creates worktrees (`worktree-add`, sparse) and classifies them (`worktrees`: ACTIVE/PROTECTED,
  UNMERGED, SAFE_CLEANUP, UNKNOWN), but **removes none**. It prints `git worktree remove "<path>"` for a SAFE_CLEANUP one.
- SAFE_CLEANUP requires all of:
  - HEAD in `main` and in `origin/main`;
  - clean, with caches only as ignored content;
  - no operation in progress and not locked;
  - 24 h idle.
- Rule (CO.RA.PAN AGENTS.md:52): remove your worktree in the same run once integrated **and** pushed.
- **No automatic cleanup exists**; removal is manual, one by one; 41 worktrees persist, 34 of them merged. The "pushed" condition
  rarely becomes true because its `main` is not pushed.

**Taken over:**
- the plumbing commit with compare-and-swap;
- the path allow-list;
- the generated index with markers;
- the trailer;
- the guard on the main checkout;
- "published even when the code stays on its branch";
- the worktree classification (clean, caches only, no operation, not locked, integrated, idle);
- the location `worktrees/<repo>/<name>`.

**Not taken over, or changed:**
- `INDEX.md` is read from the checked commit, not from disk (closes the lost-row race).
- `--status` must equal the report's `Status:` line.
- The `EXTERNAL_API_USAGE` statement is required (AGENTS §7).
- An existing report with other bytes is replaced only with `--update`.
- Publication has no push command (pushing `main` is a separate act, AGENTS §16).
- The remote condition for a worktree is "HEAD in some remote-tracking ref", the run's branch pushed, not `origin/main`. Here, as
  there, `main` is not pushed regularly, and the pushed branch is the copy beyond this disk.
- Our tool **performs** the removal itself, but only when every check passes; it never uses `--force` and never deletes a branch.
- The idle time is 30 minutes by default; the finished owning session may pass 0.
- No sparse checkout (this repository's tree is small).

**CO.RA.PAN gaps, reported only:** the index race and the unchecked status above; completed worktrees accumulate (41, of which 34
merged).

## C. What was done in CO.PRE.PAN

| Item | Result | Where |
|---|---|---|
| Report procedure | `scripts/publish_run_report.py` (`publish`, `check`), generated `docs/agent-runs/INDEX.md` | AGENTS §16, `docs/agent-runs/README.md` §Delivery, CLAUDE.md |
| Audit report on `main` | published docs-only as `36a4df1` (report + `INDEX.md`, nothing else; repeated call `NO_CHANGE`); before publication it got a dated closing note and an **appendix with the sub-audits' file:line evidence for F-01 … F-37** (they existed only in session scratch space) | `docs/agent-runs/2026-10-22_full-repository-pipeline-documentation-scientific-crosscorpus-audit.md` |
| CPD-0032 | `## Alternatives considered` added as a dated formal addition on the operator's authorisation (registry rule 1: dated additions only), marked as such; it says none was recorded, that point 4 discusses HISTORIC, and that the decision replaces CPD-0031 decision 3 — all stated in the record itself. The diff is 8 added lines, none changed. The edit was accepted this time (the audit's attempt without that authorisation had been refused; nothing was worked around) | `docs/decisions/CPD-0032_…md` |
| Qualification tool (F-22) | `spool-failover` computes its probe area by `qualification_area`: only `<corpus directory "coprepan">/_qualification/…` beside the root, never under a reserved segment, never in, around or equal to a configured root, refused **before anything is written** (`REFUSED`, exit 2). On the current primary (`…/panhispanic_media_corpora/coprepan`, parent = the shared umbrella) it refuses. The tool was not run against any real root | `scripts/qualify_storage_roots.py`, `tests/test_qualify_storage_roots.py` |
| Worktree closure | `scripts/worktree_closure.py` (`status`, `remove`); the rule in AGENTS §4 | as named |
| Merge | `5d6dafb` = merge of the audit branch (`1557ca6`, `836ca6e`) into `main`, `--no-ff`; the merged tree differs from the tested branch tip only by `INDEX.md` | §E |
| Documentation | AGENTS §4, §16; CLAUDE.md; `docs/agent-runs/README.md`; STATUS §8 | — |

## D. Validation

| Run | Result (measured 2026-10-22) |
|---|---|
| Decision records and registry after the CPD-0032 addition | `tests/test_repository_contract.py`: 80 passed |
| Qualification tool, synthetic trees (shared umbrella refused with the tree unchanged; corpus sub-root PASS and nothing left; reserved segment; overlap with a configured root) | 4 passed |
| Publisher and worktree closure against a real temporary repository with a bare remote (docs-only commit, checkout in step, repeat = no change, `--update`, wrong path and wrong status refused, uncommitted and no API statement refused, a foreign change in the main checkout untouched, compare-and-swap against a moved `main`, `check`; worktree: integrated and pushed removed, repeat = gone, branch kept, main checkout never; kept when unmerged, uncommitted, ignored non-cache file, report not on main, not pushed, locked, `index.lock`, recently changed) | 20 passed |
| Full suite on the branch tip `836ca6e` | **1706 passed, 14 skipped, 0 failed**, 533.79 s |
| Full suite on the merged `main` `5d6dafb` (main checkout) | **1706 passed, 14 skipped, 0 failed**, 556.67 s; no tracked file modified afterwards |

Against the audit's end state (1,681 / 14 / 1): the formerly failing `test_decision_record_header[CPD-0032]` passes; 24 cases
were added. **Not checked:** the publisher against a `main` changed by another session in the same second (only the
compare-and-swap itself is tested); whether another session holds files open in a worktree (no check can see that; the idle
time and the lock are the proxies); the qualification tool on a real file system (forbidden by the brief).

## E. Git and worktree state

- **Commits of this run:** `836ca6e` on the audit branch (closure); `36a4df1` on `main` (audit report, docs-only); `5d6dafb` on
  `main` (merge); this report's final commit on the audit branch, its publication on `main` and a second merge (closing
  sequence below).
- **Pushed:** the audit branch (`1557ca6..836ca6e`, fast-forward; again after the final commit). **`main` is not pushed:** it is
  ahead of `origin/main` by the five commits of 2026-10-19/20 plus this run's. Whether `main` goes to `origin` is the
  operator's decision (AGENTS §16).
- **Uncommitted changes:** none in the main checkout or the audit worktree at the final commit.
- **Worktrees:**

| Worktree | Branch | In `main` | On a remote | Clean | Class | Action |
|---|---|---|---|---|---|---|
| `full-audit-2026-10-22` | `audit/2026-10-22-full-consistency` | yes (after the closing merge) | yes | yes | this run's | removed as the last act (below) |
| `legacy-archive-contract` | `storage/legacy-archive-contract` (`17fac47`) | yes | via the audit branch only | yes | integrated, potentially removable | kept — another session's, no brief |
| `legacy-freeze` | `storage/legacy-freeze` (`e9e291d`) | yes | via the audit branch only | yes | integrated, potentially removable | kept — same |
| `newfs-phase-b` | `newfs/phase-b-migration` (`881ae58`) | yes | yes (`origin/main`) | yes | integrated, potentially removable | kept — same |
| `newfs-phase-d` | `newfs/phase-d-backup` (`a496b23`) | yes | yes (`origin/main`) | yes | integrated, potentially removable | kept — same |

Recommendation (not done): the four can be closed one at a time by `scripts/worktree_closure.py remove <path> --report <their
report>` under an operator brief; their branches stay.

**Closing sequence after this report's final commit** (each step is the stated tool; its outcome is the session's final
message and can be checked with `git log`, `git worktree list`):

1. `python scripts/publish_run_report.py publish docs/agent-runs/2026-10-22_audit-closure-run-reporting-merge-and-worktree-lifecycle.md --status PASS`;
2. `git merge --no-ff audit/2026-10-22-full-consistency` in the main checkout (the branch's last commit is this report, identical on `main`);
3. `git push origin audit/2026-10-22-full-consistency`;
4. from the main checkout: `python scripts/worktree_closure.py remove C:/dev/panhispanic_media_corpora/worktrees/coprepan/full-audit-2026-10-22 --report docs/agent-runs/2026-10-22_audit-closure-run-reporting-merge-and-worktree-lifecycle.md --min-idle-minutes 0`
   — the finished owning session; every other check applies. If any check fails, the worktree stays and the reason is reported.

The scratch space of the session holds helper probes and test outputs only; every statement here rests on the repository or on
the measured runs above.

## F. What remains

1. **Of this closure:** pushing `main` (operator); closing the four integrated worktrees of earlier sessions (operator brief).
2. **Scientific decisions:** the audit's F-07, F-15 to F-19, F-27, F-30 to F-32 (article definition, selection policy, version
   identity, validation design …).
3. **Cross-corpus contract decisions:** F-05 (release revision 2), F-07 (analysis contract after D116), F-08, F-09.
4. **Technical work of its own:** F-20, F-21, F-23 to F-26, F-28, F-34 (status output, A6 in code, intake robustness, classifier
   length, registry URLs, analysis-export gate).

## Files

Created: `scripts/publish_run_report.py`, `scripts/worktree_closure.py`, `tests/test_qualify_storage_roots.py`,
`tests/test_run_closure_tools.py`, this report; on `main` by the publisher: `docs/agent-runs/INDEX.md`. Changed: `AGENTS.md`,
`CLAUDE.md`, `docs/STATUS.md`, `docs/agent-runs/README.md`, the audit report (closing note, appendix), CPD-0032 (formal addition),
`scripts/qualify_storage_roots.py`, `tests/suites/foundation_contract.txt`, `tests/test_repository_contract.py`. Nothing moved or
deleted except the worktree removal above; no contract bundle, evidence file, storage root or CO.RA.PAN file touched.

## Operator report

1. **Result:** the audit is closed organisationally. Its report is on `main` (docs-only), its repairs and this run's are merged into
   the local `main`, CPD-0032 is complete, and the suite on the branch is fully green. The qualification tool refuses to write into
   the shared umbrella. Reports now have a tested publication path and worktrees a tested closure.
2. **Status `PASS`** for this closure; not a push of `main`, not a closure of the audit's other findings.
3. **Consequence:** from now on a run is delivered when its report is on `main`. A run's worktree is closed only when nothing can be
   lost.
4. **Next steps:** the operator's decisions in §F; no follow-up run is needed for this closure.
5. **Files:** above.
6. **Untouched:** CO.RA.PAN and its worktrees, the legacy repositories, the storage roots, the four other worktrees, `origin/main`.
