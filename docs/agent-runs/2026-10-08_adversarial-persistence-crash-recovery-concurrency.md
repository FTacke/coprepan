# COPREPAN 3.0 — Adversarial persistence, crash-recovery and concurrency audit

```text
run_started_at:      2026-10-08T00:20:39+02:00   (first clock reading)
run_ended_at:        2026-10-08T01:06:00+02:00   (last clock reading, after the final full test run; the commits and the push followed)
timezone:            Europe/Berlin
wall_clock_seconds:  2721   (between the two readings above)
status:              PASS   — for the scope of §0
kind of run:         diagnosis (adversarial audit, measured) + repair of the defects found +
                     decision on durable semantics (CPD-0009). No new feature.
                     No scientific validation. No production activation.
EXTERNAL_API_USAGE = NONE   (no model API, no external service, no request to any website)
NETWORK USE:         `git push` to `origin` only. Child processes of the tests spoke to a server on a
                     literal loopback address they started themselves. Nothing was installed.
```

## 0. What `PASS` covers, and what it does not

**Covers:** the question of the brief was answered by measurement. On the code as found, the
answer was **no** — after a concurrent access or an interruption COPREPAN could lose evidence
silently, report a success that was none, and be left in a state it could not get out of. The
defects were repaired, each with a regression test, and on the repaired code every invariant
defined in this run holds under real process kills and real concurrent processes:
`PRE_CANARY_ROBUSTNESS = PASS`.

**Does not cover, and must not be read into it:** one workstation (Windows 11, NTFS, local
disk), temporary directories, a loopback server. **No power failure** was simulated — a process
was killed, the operating system lived on. No real preservation target, no network share. The
`PASS` is about the failure, recovery and concurrency tests listed here; it is not a proof of
absence of further defects, and it closes no gate.

## 1. State at the start (measured)

| | |
|---|---|
| repository | `main` = `origin/main` = `1e5f807e64e8850b926401356d932d7ea26e930f`, working tree clean |
| tests | 734 passed, 1 skipped (as handed over) |
| reference repositories | not needed and not touched: nothing outside this repository was read in this run |

Read first: `docs/STATUS.md`, the four most recent run reports, CPD-0005 to CPD-0008, then the
code of every module that writes: `ledger`, `jsonl`, `pack`, `preservation`, `layer_store`,
`document_identity`, `core_pipeline`, `http_acquisition`, `acquisition`, `outage_spool`,
`discovery` (tables), `admission`, `candidate_filter`, `schedule`.

## 2. Guarantee inventory

"in-process" = a failure injected inside the process under test; "kill" = a child process killed
from outside at that point and inspected by another process; "race" = separate processes started
at the same instant. The column "before" is the state at `1e5f807`.

| Guarantee | Documented | Implemented before | Tested before | Now |
|---|---|---|---|---|
| ids: deterministic, content-derived | yes | yes | in-process, property tests | unchanged; one more generated test (URL keys are fixed points) |
| acquisition run: one record, resumable | yes | record written in place, not atomic | in-process | atomic record; kill |
| discovery events, candidates: append-only | yes | yes; duplicate keys: last row wins on load | in-process | contradicting rows refused on load |
| fetch record in a pack: whole or absent | yes | yes | in-process (torn tail) | kill (half a fetch on disk) |
| ledger before state | yes | yes | in-process | kill; chain |
| ledger: one writer | **documented as an assumption** | **not enforced** | untested | enforced; race |
| state machine: illegal transition raises | yes | yes | exhaustive in-process | + generated walks |
| open pack: one writer | implied | not enforced | untested | refused; race |
| seal: idempotent, crash between steps completed | yes | yes | in-process | kill at both intermediate points; a pack that changes while sealing is refused |
| promotion: verified landing, idempotent, no overwrite of other content | yes | idempotent yes; **overwrite possible between two processes** | in-process | exclusive; race; kill at three points |
| `RAW_PRESERVED` ⇒ verified master | yes | pack master verified, index master not | in-process | both verified; damage tests |
| layer store: one answer per fingerprint, write-once | yes | **not between processes** | in-process | race; kill at three points |
| document identity: idempotent per fetch | yes | rows yes; **relations lost after an interruption** | in-process | kill; relations re-derived |
| identity tables refuse collisions on load | **yes (docstring)** | **no** | untested | implemented; tested |
| extraction: replay gives the same bytes | yes | yes | in-process | + replay in a process with sockets forbidden |
| admission labels: append-only | yes | yes | in-process | contradicting rows refused on load |
| schedule: pure, never rewrites history | yes | yes | in-process | race of two planners; generated histories |
| conditional request: 304 invents no body | yes | yes; **believed without checking that the body is preserved** | in-process | 304 believed only for a preserved, verifying body |
| legacy freeze manifest | yes | yes | in-process | not re-examined |
| recovery from any interruption | implied by "resumable" | **four interruption states had no way on** | untested with kills | 28 crashpoints, kill |

Nothing in the last column is a guarantee about a real preservation target or a real server.

## 3. Failure model

| Failure | How it was produced | In scope |
|---|---|---|
| process killed between two writes | child process killed from outside (`TerminateProcess`) while blocked at a named point | yes — 28 points |
| partial file; truncated append | the child writes half of the bytes, syncs, then is killed | yes — pack, ledger, table, run record, layer payload, layer manifest, master copy |
| rename refused; permission denied; read-only target; disk full | the call raises `PermissionError` / `OSError(EACCES, EROFS, ENOSPC)` in-process | yes |
| short write (the system takes half) | `os.write` returns after half the bytes, in-process | yes |
| source disappears; source changes between validation and copy; target appears between check and rename | in-process, at the exact step | yes |
| duplicate controller; parallel writers | two or three real processes released at the same instant | yes |
| stale lock | the lock holder is killed; a second process then starts | yes |
| corrupt manifest, index, ledger tail, stored payload | bytes flipped, truncated, rows removed, added, reordered — with the manifest kept consistent where an attacker would | yes |
| out-of-order resume; repeated command | every resumed step is run twice; steps resumed after another kill | yes |
| missing directory | covered by existing root-resolution tests | not re-examined |
| **machine death, power failure** | — | **no**: un-synced data and directory entries are not simulated |
| network file system semantics | — | **no** |

## 4. Crash matrix (real kills)

Scenario A: the recorded-replay canary (nine exchanges → pack → preservation → identity →
extraction). For every row: the process was killed at the point; a second process ran
`diagnose`, `repair`, the pipeline, the pipeline again. "= reference": ledger states, identity
tables, layer artifacts and preserved masters equal those of an uninterrupted run.

| Crashpoint | State after the kill | `diagnose` | Repair | Resume | = reference | Idempotent | Left behind |
|---|---|---|---|---|---|---|---|
| half a run record | staging file only; no run record | `INCOMPLETE_RESUMABLE` | — | start again | yes | yes | 1 staging file |
| half the first record of a new pack | open pack with a torn first record | `NEEDS_REPAIR` | tail moved aside | yes | yes | yes | 1 sidecar |
| half a fetch in the pack | open pack, torn tail; ledger `FETCH_PLANNED` | `NEEDS_REPAIR` | tail moved aside | yes | yes | yes | 1 sidecar |
| after the pack append, before the ledger | fetch whole in the pack; ledger `FETCH_PLANNED` | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| half a ledger record | torn last line | `NEEDS_REPAIR` | tail moved aside | yes | yes | yes | 1 sidecar |
| before `FETCHED` | as two rows above | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| seal: renamed, no index | sealed name, no index, no manifest | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| seal: index, no manifest | index without manifest | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| before `RAW_VERIFIED` (third) | sealed; some fetches verified | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| before `PRESERVATION_PENDING` (third) | sealed; some pending | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| before promotion | sealed; nothing on the root | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| during the master copy | part of the master under a staging name | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | 1 staging file |
| master in place, no manifest | bytes without a manifest: claims nothing | `INCOMPLETE_RESUMABLE` | — | yes (`repaired`) | yes | yes | — |
| pack promoted, index not | one of two masters | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| both promoted, before `RAW_PRESERVED` | all `PRESERVATION_PENDING`; masters verify | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| before `RAW_PRESERVED` (fourth) | some preserved, some pending | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| after identity, before extraction | document and observation rows, no layer | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| half a layer payload | staging directory | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | 1 abandoned write |
| payload, half a layer manifest | staging directory | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | 1 abandoned write |
| layer complete, not published | staging directory | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | 1 abandoned write |
| layer stored, version not registered | layer without a version row | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |
| half a version row | torn table | `NEEDS_REPAIR` | tail moved aside | yes | yes | yes | 1 sidecar |
| rows written, relation not (two points) | version without its relation | `INCOMPLETE_RESUMABLE` | — | yes | yes | yes | — |

No row is `DAMAGED`; no row reports `ledger_claims_bytes_no_pack_has`; no row needs manual repair.
The same matrix on the code as found: **4 rows could not be resumed at all** (run record, first
pack record, torn pack, torn ledger — the last two had a repair function nobody called) and **2
rows resumed to a state that differed from the reference** (the lost relations).

Scenario B: one HTTP acquisition pass against a loopback server.

| Crashpoint | After the kill | Resume | Result |
|---|---|---|---|
| intent logged, request not sent | `PLANNED` without `FINISHED` | the candidate is planned again and requested | all candidates end as in the reference; the old intent stays on record, counted as "interrupted, repeated later" |
| server answered, nothing recorded | as above — **the response is lost with the process** | as above | the server saw two requests; one answer is preserved |
| end of a request half-written to the log | torn log; the answer is in the pack and the ledger | `repair`, then as above | no loss; the request may be repeated |
| answer in the pack, ledger and log silent | fetch in pack, ledger `FETCH_PLANNED` | reconciled when the pack is sealed | 14 fetches `RAW_PRESERVED`, none blocked |

Also by kill: a process holding the writer lock is killed; the next process is admitted at once
(no stale lock). Replay of all extractions in a process in which creating a socket raises: seven
re-derived byte for byte, one first extraction added beside them, no preserved byte changed.

## 5. Concurrency matrix (real processes, started together)

| Component | Before | Semantics now | Evidence |
|---|---|---|---|
| ledger, one object per process | **unsafe race**: 389 of 600 records on disk, ledger unreadable | **explicit conflict**: one writer proceeds, a stale one is refused; reported = on disk | `test_ledger_writers_cannot_lose_or_duplicate_a_record` |
| append-only table | **unsafe race, invisible**: 597 of 900 rows on disk, file reads fine | **safe serialisation**: 450 of 450 | `test_table_appends_of_several_processes_are_all_on_disk` |
| open pack | creation: explicit (`FileExistsError`); appends to an existing pack: all 180 survived in one round — not a guarantee | **explicit conflict**: a second object on the pack is refused | `test_two_objects_on_one_open_pack_cannot_both_append`; workspace lock |
| layer, same answer | explicit error for 80 of 120 identical writes | **idempotent duplicate** | `test_the_same_layer_answer_…` |
| layer, different answers | **unsafe race**: 120 of 120 `STORED`, all 40 slots unreadable | **explicit conflict**: at most one answer stays, every other writer is told | `test_different_layer_answers_…` |
| promotion, same object and content | idempotent, with occasional explicit I/O errors | unchanged: **idempotent duplicate** or explicit I/O error | `test_promoting_one_object_…` |
| promotion, same identity, different content | **unsafe race**: two or three "promoted" in 8 of 8 rounds; master ≠ manifest in 1 | **explicit conflict**: exactly one binds (12 of 12 rounds) | `test_one_identity_offered_with_different_content_…` |
| acquisition run started twice | explicit by accident when simultaneous (`FileExistsError`); **unsafe** when staggered | **safe serialisation or explicit refusal** (`WorkspaceBusy`) | `test_one_workspace_started_twice_…` |
| candidate planned by two planners | — | **pure**: identical plans; the writer lock decides who requests | `test_two_planners_…` |

Scheduling questions of the brief, answered by construction and by the tests above: a candidate
cannot become due "while another run processes it" in a second process — the second process is
refused; a permanent redirect and the scheduling of the old URL happen in one process, in order;
a retry schedule after a crash is the lifecycle derived from the log (Scenario B); channel health
is computed when read and has no stored view to go stale.

## 6. Operation semantics

Decided in [CPD-0009](../decisions/CPD-0009_single-writer-recovery-and-operation-semantics.md) §3.
In one line each: an **HTTP request is at-least-once**; a **response is recorded under one fetch
id or not at all**; a **pack append is atomic per fetch**; a **ledger transition happens exactly
once per subject and state**; **seal and promotion are idempotent**, promotion **exclusive per
identity**; **document, version, label and qualification are assigned once per key**; **a layer
has one answer per fingerprint**; **replay only reads what is preserved**. Nothing is promised
"exactly once" towards the outside world.

## 7. Defects found

Real defects of the committed code, each reproduced before it was repaired.

| # | Defect | Severity | How found |
|---|---|---|---|
| B-1 | two processes appending to the ledger lose records silently; the ledger is unreadable afterwards | **critical** — lost state evidence, no error | race |
| B-2 | two processes appending to any table lose rows silently; the table still reads | **critical** — invisible loss (request log, discovery, identity) | race |
| B-3 | one identity promoted with different content by two processes: both "promoted"; the master can end up not fitting its manifest | **critical** — false success, silent overwrite on the preservation root | race |
| B-4 | different layer answers for one fingerprint: all reported stored, the slot unusable afterwards | high — false success; detected only at the next read | race |
| B-5 | a fetch written to the pack but not yet to the ledger (kill in between, HTTP run) stays `FETCH_PLANNED`; identity and extraction then refuse the **whole pack** | high — one kill blocks a day of an outlet, no way on | reading + kill |
| B-6 | killed while writing a run record: the run can never be resumed | high | kill |
| B-7 | killed while creating a pack: the pack id of that outlet and day is unusable | high | kill |
| B-8 | killed during any table append: the table is refused for good; no recovery function existed (for ledger and pack one existed and nothing called it) | high | kill |
| B-9 | killed between a version row and its relation: `duplicate_of` / `moved_to` missing for good, no error | medium — silent, wrong identity relations | kill |
| B-10 | the identity tables' documented refusal of collisions on load was not implemented: of two rows under one key the last one won | medium | reading |
| B-11 | a 304 was assigned to a version without checking that the body it names is preserved; a conditional request was sent for a body that was only in the request log | medium — a "held" body that is not held | reading |
| B-12 | `RAW_PRESERVED` was set after verifying the pack master only, not the index master | low | reading |
| B-13 | the pack manifest could name bytes other than the ones scanned (change between scan and hash) | low — needs a writer during sealing | reading |
| B-14 | a ledger record changed in place (one bit) was accepted whenever it stayed a legal record | medium — unnoticed alteration of evidence | bit-flip measurement |
| B-15 | a stored extraction of another record schema would have been read as the current one (the fingerprint names the extractor version, not the record schema) | low — latent until a schema change | reading |
| B-16 | a missing layer payload raised a bare `FileNotFoundError` instead of the store's refusal | low | corruption test |

Count: 16 — 3 critical, 5 high, 4 medium, 4 low. All sixteen are repaired and each has a regression test.
B-1 to B-9 and B-14 were reproduced on the old code by measurement before the repair (§4, §5, §9); the
others were found by reading and are covered by tests written against the repaired behaviour.

## 8. Repairs

| Repair | Defects | Where |
|---|---|---|
| writer lock per workspace, held by every writing operation, released by the system when its process ends | B-1, B-2, B-4 (within a workspace), double start | `exclusive.py`; `core_pipeline`, `http_acquisition`, `admission`, `recovery` |
| appends serialised by an operating-system lock and read back; a ledger or open pack that grew behind an object refuses its next write | B-1, B-2 | `canonical.append_lock`, `jsonl.append_line`, `ledger`, `pack` |
| exclusive publication of a new master and a new manifest | B-3 | `canonical.publish_exclusive`, `preservation` |
| layer store: an identical concurrent answer is `ALREADY_STORED`; a different one is withdrawn (moved, not deleted) and reported | B-4, B-16 | `layer_store` |
| reconciliation of the ledger from a verified pack at sealing | B-5 | `core_pipeline.reconcile_ledger_with_pack` |
| run record and run result written under a staging name and renamed | B-6 | `acquisition` |
| an empty open pack is a pack that has not started | B-7 | `pack.OpenPack` |
| `recovery.diagnose` and `recovery.repair` | B-8, classification of every state | `recovery.py` |
| relations derived from the stored rows, written again when missing | B-9 | `document_identity` |
| keyed tables refuse contradicting rows on load | B-10 | `jsonl.keyed`; identity, discovery, qualification, label tables |
| a 304 is believed, and a conditional request sent, only for a preserved and verifying body | B-11 | `core_pipeline`, `http_acquisition` |
| both masters verified before `RAW_PRESERVED`; the pack re-scanned and re-hashed before its manifest is written | B-12, B-13 | `core_pipeline`, `pack.seal` |
| ledger record `v2`: each record names the hash of the one before it | B-14 | `ledger` |
| a stored extraction is used only if it names the current schema, this extractor and this body | B-15 | `core_pipeline` |

Alternatives that were weighed are in CPD-0009. Two choices deserve a line here. The lock is an
operating-system lock and not a lock file, because a lock file needs a rule for the case that its
writer was killed, and this run is about processes being killed. And the ledger format was
changed now, with a schema bump, because no ledger of corpus material exists yet; after the first
real fetch the same change would be a migration.

One existing behaviour changed and its test with it: a 304 naming a fetch nobody preserved is now
`revalidation_target_not_preserved` (it was `revalidation_target_unknown`).

## 9. Limits that remain

1. **Power failure is not covered.** A killed process leaves what it handed to the operating
   system. A dead machine can lose synced-but-unacknowledged data and directory entries; renames
   are not followed by a directory sync. What recovery finds then is not tested.
2. **Unhashed fields.** Single changed bits, 40 per file, on the canary workspace — not noticed
   by `diagnose`: 72 of 160 in the identity tables, 29 of 80 in preservation manifests, 13 of 40 in
   the pack manifest, 10 of 40 in the run result, 1 of 200 in layer markers; 0 in preserved
   masters, packs, indexes, layer payloads and manifests, the ledger, the run record. The request
   log and the discovery tables were not in this measurement and have no protection either.
   The ledger chain is the pattern; applying it to every table is a decision (CPD-0009).
3. **The last ledger record** has no successor to vouch for it.
4. **A response that arrived and was not yet recorded dies with the process.** The window is the
   time between the last byte from the server and the pack append. The request is repeated.
5. **Leftovers accumulate** (staging files, abandoned layer writes, sidecars). Nothing deletes
   them, by design; nothing reports their size yet beyond a count.
6. **A damaged layer answer or a damaged preserved master is reported, not repaired.** A layer is
   re-derivable and a master may still be in the workspace, but no procedure moves the damaged one
   aside. That is a person's decision today.
7. **Identity tables cannot be rebuilt** from packs and layers by a tool, although in principle
   they are derived.
8. **The outage spool** was not exercised under competing writers and still replaces on rename.
9. **One corrupt manifest in an area** makes every new promotion into that area fail (the
   duplicate search reads all manifests). Fail closed, but one bad file stops the area.
10. **Locks on other file systems.** The writer lock and the append lock rest on `msvcrt.locking`
    here and `flock` elsewhere; exclusive publication rests on a rename that refuses an existing
    target here and on a hard link elsewhere. Only the first of each was run.
11. Two workspaces for one outlet and day build the same pack id; the second promotion is now
    refused. Whether that setup may exist is an operational rule nobody has written.
12. `diagnose` reads everything it checks; on a large workspace it will take as long as hashing
    it. Measured only on the canary (0.02 s).

## 10. Tests

`python -m pytest -p no:cacheprovider -q` (Python 3.12.10, pytest 9.1.1):

| | Result |
|---|---|
| at the start | 734 passed, 1 skipped |
| at the end | **825 passed, 1 skipped**, about 135 s (55 s before) |
| new | `test_crash_recovery.py` 32 cases (real kills), `test_concurrency.py` 8 (real processes), `test_integrity_invariants.py` 49, `test_ledger.py` +1, and the header check of CPD-0009 |
| changed | `test_ledger.py` (record format `v2`), `test_preservation.py` (the manifest writer that is interrupted), `test_refetch_e2e.py` (the 304 outcome) |
| the skip | unchanged: symbolic links cannot be created on this account |

Test support: `tests/adversarial_child.py` (the child process; crashpoints are installed by
wrapping functions in that process only — production code contains no crash hook) and
`tests/support_processes.py`.

Cost of the safety checks (measured, diagnostic): ledger append 4.1 ms, rebuild of 5,000 records
0.02 s; pack of 1,500 fetches / 56.8 MB: scan 0.5 s, seal 1.0 s, fixity 0.5 s; layer store 5 ms
per write, 12 ms per verified read. Nothing here invites switching a check off.

Mistakes of mine during the run, kept on record: the first version of the repaired ledger
checked the file size outside the append lock and three processes wrote three "first" records —
caught by re-running the race, fixed by moving the check inside; the first conflict rule for the
layer store could leave two answers — caught by reasoning through the interleavings before
running it; a writer-lock holder file with a process id and a time made two identical runs differ
and was removed; several expectations in new tests were wrong and the code right. One shell call
again contained an (empty, ineffective) heredoc, against the repository rule — the fourth such
slip in this session.

## 11. Validation classification

| Kind | What this run supports |
|---|---|
| robustness | the crash, race, corruption and fault tests of §3–§5 |
| reproducibility | a second process, sharing nothing with the first but the disk, reconstructs the state and completes the run to the byte-identical result of an uninterrupted one — stronger than an in-process rerun, still one implementation on one machine |
| replicability | nothing |
| generalisability | nothing: one platform, one file system, synthetic data |

## 12. Consequences for the first real canary

- **Start exactly one process per workspace.** A second one is refused; that refusal is the
  system working. Do not put a runtime workspace on a network share until locks were tried there.
- **After any abnormal end: `recovery.diagnose` first.** `NEEDS_REPAIR` → `recovery.repair`;
  `INCOMPLETE_RESUMABLE` → run the same command again; `DAMAGED` → stop and look.
- **A request can be sent twice.** The politeness budget of O-1 should be decided knowing that
  an interrupted run repeats at most the request it was in.
- The Phase-1 gate on the real target (O-3) should run `tests/test_crash_recovery.py` and
  `tests/test_concurrency.py` against that target's file system: exclusive publication and locks
  are exactly the parts that depend on it.
- The preflight needs no change: it starts nothing and writes no workspace.

## 13. Next step, and the question the brief asked

**Is there still a technically relevant integrity question that should sensibly be settled
before the first real canary?** One, and it is a decision more than work: **whether the other
append-only tables get the integrity protection the ledger now has** (limit 2). Before the canary
it is a schema change on empty tables; after it, a migration of real evidence. Everything else in
§9 is either bound to the real target (limits 1, 10 — the Phase-1 gate) or acceptable for a
five-outlet canary if known (limits 4–9, 11, 12).

Sensible next steps: (1) the operator's decision on limit 2 — I recommend chaining the request
log and the discovery tables, and treating the identity tables as rebuildable instead; (2) O-3,
then this audit's two process suites on the real target; (3) unchanged: O-11, O-1, O-2.
