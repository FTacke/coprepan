# Authorised real canary → O-4 → Phase 3: not executed — the arming edit was refused by the permission layer (third attempt)

```text
run_started_at:      before 2026-10-08T18:19:35Z (the storage status below is the first clock reading)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin (reading in UTC)
```

**Status: BLOCKED.** The first action of the arming protocol — the edit of `"external_acquisition"` in
`config/acquisition_policy.json` from `disabled` to `enabled` — was denied by the session's permission layer
(reason given: `[Security Weaken]`). The operator brief of this run authorised exactly that edit; the layer
still refused it. As the brief instructs, the refusal was not worked around: the file was not changed by
any other tool, and no other route to the same effect was tried.

**What the status does not claim.** **No request was made to any publisher.** No arming commit, no baseline
(O-12 stays `OPEN`), no preflight, no start-state record, no receipt, no robots or TDM statistics of a real
site, no O-4 measurement, no Phase-3 sample, candidate run or review package. Nothing here is a number from a
real run, because there is none. This report supersedes nothing: it is the third record of the same boundary
([first](2026-10-08_canary-driver-and-arming-prepared.md),
[second](2026-10-08_real-acquisition-canary-o4.md)).

**Kind of run:** an attempted activation that did not take place.

`EXTERNAL_API_USAGE = NONE`. No outlet was contacted. No network was used.

## 1. State measured at the start

| Item | Value |
|---|---|
| `HEAD` = `origin/main` | `5e33e59ca803a0524319c3da1b82c5cf5dc247ca` (after `fetch`; a valid continuation of `73a6311`: reports only) |
| tree | clean |
| policy | `canary/2026-10-08.2`, `external_acquisition = disabled` (read from the file) |
| full suite, switch off | **1304 passed, 1 skipped** (the skip: a symbolic link cannot be created on this account) |
| storage (`scripts/storage_contract.py status`, 2026-10-08T18:19:35Z) | `crosscorpus-storage/v1` `IN_FORCE`, digest `8d17fc21…18fb3`; `PRESERVATION`, `RUNTIME`, `SPOOL`, `REPOSITORY` `AVAILABLE`; separation `SEPARATED`; spool 0 pending; `BACKUP` `NOT_CONFIGURED` |

## 2. What happened, exactly

1. The authoritative documents (AGENTS.md, STATUS, runbook, CPD-0016, the three previous reports, the Phase-3
   design and candidate documents) were read. Nothing in the repository had advanced beyond the report commit.
2. The full suite was run on the unarmed tree (above) as the reference for the armed run.
3. The arming edit — one line in `config/acquisition_policy.json` — was **denied** by the permission layer.
4. A later read-only PowerShell call (clock reading, `git status`, `git diff --stat`, a text search) was also
   denied in one compound; `git status` alone then ran and showed the tree clean.
5. No other route to the edit was sought. The file is unchanged.

Difference from the previous attempt: then the edit was accepted and the following test run on the armed tree
was refused; this time the refusal came at the edit itself. The permission layer, not the repository, is the
boundary in both cases, and the operator's textual authorisation in the brief does not reach it.

## 3. Consequences, all following from that one refusal

| Step of the brief | State |
|---|---|
| arming commit, tests on the armed checkout | not done |
| O-12 baseline built and frozen | not done (its precondition is the armed switch); `O-12 = OPEN` |
| preflight `READY`, `CANARY_START_STATE` | not done |
| five-outlet canary, verification, replay, recovery | not done |
| O-4 measurement | not done; `O-4 = OPEN`, `NOT_YET_MEASURABLE` |
| disarming commit | not applicable — never armed |
| Phase 3 | `PHASE3_GOLD_PACKAGE = NOT_BUILT`. Not `INSUFFICIENT_FROM_CANARY`: that value would describe a canary that ran and yielded too little |

Phase 3 also has a precondition the brief calls "already selected" that the repository does not support:
[`EXTRACTOR_CANDIDATES.md`](../extraction/EXTRACTOR_CANDIDATES.md) is a survey from general knowledge, not a
selection; none of the candidate packages is installed or pinned, and no wrapper exists
(its §5: versions, licences and maintenance confirmed from the source, pins, wrappers with determinism tests,
preregistration). That is a separate piece of work, to be decided when real material exists; it is named here
so that it is not found only then.

## 4. The one manual step

Either, by a person:

- **(a)** Run the canary yourself from [`docs/canary/RUNBOOK.md`](../canary/RUNBOOK.md) §1 (set the switch,
  commit it alone, then the commands in order). The driver refuses to start unless every precondition holds
  and writes the start-state record before its first request.
- **(b)** Add a permission rule for the session that allows the agent to edit `config/acquisition_policy.json`
  and to run commands on the armed checkout (including outbound HTTP(S) from `python -m coprepan.canary_driver`),
  then ask for the run again. Nothing else is missing.

## 5. Files and git

Created: this report. Changed: `docs/STATUS.md` (one history entry). `config/acquisition_policy.json` was
**not** changed; nothing was moved, deleted or overwritten. Reference repositories untouched.

## 6. Gates

| Gate | State |
|---|---|
| O-12 (canary scope) | `OPEN` — not frozen |
| Phase-2 canary | `OPEN` — not run |
| O-4 | `OPEN` — nothing measured |
| `external_acquisition` | `disabled` (unchanged) |
