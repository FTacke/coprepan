# COPREPAN 3.0 — Evidence-table integrity closure before the real canary

```text
run_started_at:      2026-10-08T07:55:31+02:00   (first clock reading)
run_ended_at:        2026-10-08T08:27:20+02:00   (last clock reading, after the final full test run; the commits and the push followed)
timezone:            Europe/Berlin
wall_clock_seconds:  1909   (between the two readings above)
status:              PASS   — for the scope of §0
kind of run:         implementation + decision (CPD-0010), with robustness and reproducibility checks.
                     No new acquisition feature. No scientific validation. No production activation.
EXTERNAL_API_USAGE = NONE   (no model API, no external service, no request to any website)
NETWORK USE:         `git push` to `origin` only. Child processes of the tests spoke to a server on a
                     literal loopback address they started themselves. Nothing was installed.
```

## 0. What `PASS` covers, and what it does not

`PRE_CANARY_EVIDENCE_INTEGRITY = PASS` means: **the last local evidence-integrity point found
before the real canary is technically closed.** Primary append-only evidence (request log,
discovery inputs and events, candidate qualifications, admission labels) is chained and anchored;
derived state (discovery candidates, identity tables) is checked against the evidence and — for
identity — rebuilt from preserved packs and compared; recovery classifies the three cases; every
test, including the crash-recovery and concurrency suites of the previous run, passes.

**Does not cover:** one workstation, local disk, temporary directories, a loopback server; no power
failure; no real preservation target or share; no real outlet. It closes no acquisition or
production gate. It is not a proof that no integrity defect remains: §11 lists what is accepted.

## 1. State at the start (measured)

| | |
|---|---|
| repository | `main` = `origin/main` = `001e57863d18e7b0645f6d6d07b3a4da6bdf2465`, working tree clean |
| tests | **825 passed, 1 skipped** (as handed over) |
| reference repositories | not needed and not touched |

Read first: `docs/STATUS.md`, CPD-0009 and the audit report; then every writer and reader of a
JSON-lines table (`jsonl`, `ledger`, `discovery`, `http_acquisition`, `document_identity`,
`admission`, `candidate_filter`), `core_pipeline` and `recovery`.

## 2. Evidence / derived-state classification

Decided by what a row records, and checked against the code that writes and reads it.

| Store | Class | Reason found in the code |
|---|---|---|
| request log | `PRIMARY_EVIDENCE` | `PLANNED` is the only record of an intent; a `DENIED` or `DEFERRED` request has no fetch record at all |
| discovery inputs | `PRIMARY_EVIDENCE` | an input the gate refused has no fetch and no preserved bytes (`unavailable:<run>:<hash>`) |
| discovery events | `PRIMARY_EVIDENCE` | an observation under a parser version; the channel document is preserved, but the observation is not recomputable once the parser has changed |
| candidate qualifications, admission labels | `PRIMARY_EVIDENCE` | a decision under a rule set; later rule sets add rows *beside* these, so old rows cannot be recomputed once the rules have moved |
| discovery candidates | `DERIVED_REBUILDABLE` | event-created: the whole row is a function of the first event that listed it; redirect-created: of the request-log row carrying `moved_permanently_to` |
| identity: documents, observations, versions, relations | `DERIVED_REBUILDABLE` | functions of preserved fetch records and bodies, the ledger, the outlet URL rules and the extraction |
| channel health, candidate lifecycle, fetch plan | `CACHE/VIEW` | computed when read, nothing stored |

**Stores with mixed content:** one — the candidate table has two creation paths. It holds nothing
that is not derivable, so it was classed as derived and the cause clarified before any format
changed: both paths are reproduced by `derived_candidates`. The brief asked not to decide by file
name; two files that look alike differ: `candidates.jsonl` is derived, `events.jsonl` is not.

Measured before any change (old tree `001e578` unpacked from git into a scratch directory; 40
random single-bit changes per file; a workspace diagnosis afterwards; "not noticed" = it said
`CLEAN` or raised):

| File | Not noticed (of 40) |
|---|---|
| request log · discovery inputs · events · candidates · admission labels | 40 · 40 · 40 · 40 · 40 |
| candidate qualifications | 39 |
| identity documents · observations · versions (two workspaces) · relations | 15 · 22 · 4 and 6 · 22 |

## 3. Request-log decision

Chained like the ledger (CPD-0010 §2): `previous_row_sha256` is the SHA-256 of the line before.
The shared helper is `jsonl.append_chained` / `read_chained`; it takes the predecessor under the
append lock, so two appenders cannot build on one line, and verifies what it wrote.

- changed, removed, inserted, duplicated or reordered earlier row → `ChainBroken` at the row after it;
- an incomplete last line → `TornTail` (a crash), never a break; the rows before it still
  authenticate each other; `repair` moves it aside; appending resumes from the last whole row;
- a chained table is never repaired: `recovery.repair` leaves it byte for byte as found;
- a run refuses to start on a request log or discovery table that does not authenticate, before
  its first request (new check; the request log used to be read for the first time after the
  channel requests had been sent).

## 4. Discovery decision

| Table | Decision |
|---|---|
| inputs, events | chained (`v2`) |
| candidates | **not** chained: derived. `candidate_from_event` is the one function that derives a row; used when a candidate is created *and* when the table is checked. `candidate_consistency` reports missing / unsupported / different rows; `complete_candidates` appends missing rows and nothing else |

One change of behaviour came with it: a new candidate is now created from the **first** event that
listed it, not the event in hand. The two differ only after an interruption between an event and
its candidate row — a state the old code would have written differently from a clean run.

## 5. Identity rebuild semantics

Inputs: verified packs on the root (pack **and** index manifest present, masters hashing
correctly), the ledger (`RAW_PRESERVED` fetches), the outlet URL rules, the extraction (a stored
layer that verifies, else derived in memory and stored nowhere). No network (the tests forbid
sockets in the rebuilding process), no write to anything preserved or to any layer (trees hashed
before and after). Canonical order: packs by id, fetches in index order.

Comparison is by canonical rows, not by bytes alone: on the canary and on a full HTTP pass the
rebuild is **byte-identical** to the pipeline's own tables. Where bytes cannot be required: row
order and `first_fetch_id`, which depends on the order of identification — compared as "one of
the fetches that observed the document". Relations are compared exactly (see §10, M-3).

Statuses, `diagnose` classes and adoption rules: CPD-0010 §5. Adoption moves the old directory
aside (`identity.replaced-<n>`), never deletes it, and refuses on damaged evidence and, unless
asked, on a conflicting store.

Two cases that looked like damage and are not: a pack on the root whose index manifest has not
yet been written (an interrupted promotion), and fetches the ledger has not yet marked
`RAW_PRESERVED`. Both are "not preserved yet", outside the rebuild. The opposite is damage: a
fetch the ledger *does* record as preserved in a pack the root does not hold completely
(`SOURCE_EVIDENCE_DAMAGED`).

## 6. Schema changes

`v1` → `v2`, all before any corpus row existed: request log, discovery input, discovery event,
candidate qualification, admission label, acquisition run result (which now carries
`evidence_heads`). Unchanged: discovery candidate `v1`. Tests: a `v1` row is refused by a `v2`
reader and the reverse; a `v2` row without the chain field is not `v2`; a `v1` run result is
refused; the schema list of the baseline manifest names the `v2` ids and none of the superseded
ones. No migration code was written.

## 7. Heads (added during the run)

The first measurement after the chains were in showed the one thing a chain cannot cover: the
newest row. Of 40 changes per table, 1–7 went unnoticed, every one of them in the last row. Closing
a run now records the row count and the hash of the last line of the ledger and every chained
table in its result; `diagnose` checks them. Result: **0 of 40 unnoticed in every table**, except
admission labels: 7 of 40, all in the last row, because the labels of that workspace were written
after its run had closed (CPD-0010 §3; accepted, §11).

## 8. Adversarial tests

`tests/test_evidence_integrity.py`: 71 cases. Measured before/after of single changed bits:

| File | Not noticed of 40: before → after |
|---|---|
| request log | 40 → 0 |
| discovery inputs · events · candidates | 40 → 0 · 40 → 0 · 40 → 0 |
| candidate qualifications · admission labels | 39 → 0 · 40 → 7 (all last row, after close) |
| identity documents · observations · versions · relations | 15 → 0 · 22 → 0 · 4–6 → 0 · 22 → 0 |

| Area | What the cases do |
|---|---|
| chained tables (5, each with a real writer's data) | change, remove, insert, reorder a middle row → refused, `DAMAGED`, not repaired, bytes untouched; torn tail → `NEEDS_REPAIR`, repair restores the exact old bytes, appending goes on; every row names the hash of the line before |
| the mechanism | 15 random tables: an append never touches the old prefix; a change at any position but the last is reported at exactly the next line; the last row is the documented limit; schema versions are not read as each other; **3 real processes** append 360 rows into one valid chain; a request log cut by a **real kill** is a torn tail with an intact chain; a run refuses to start on a broken request log and sends nothing |
| heads | each of ledger + 4 tables: change to the newest row of a closed run → `DAMAGED`; complete rows cut from the end → `DAMAGED`; rows after the close do not disturb the anchor |
| candidates | consistent with the evidence; a lost row (listed, redirected) is found and restored with the same bytes and nothing else touched; a forged or altered row is `DAMAGED` and not completed away |
| identity | rebuild equals the tables byte for byte; deterministic across two rebuilds; no socket; preserved root, layers and packs unchanged; deleted tables; a missing row in each of the four tables; a changed value, a contradicting row, a wrong relation → `CONFLICTING`, refusal without a decision, adoption with one, old store kept; torn tail → both ways back end in the same bytes; damaged pack master, index master, either manifest gone → `SOURCE_EVIDENCE_DAMAGED`, nothing adopted, not even a staging directory; tables deleted *and* evidence damaged → refused |
| **real kills during a rebuild** | killed in the middle of the derivation (staging directory left, never read as data) and killed after the old store was moved aside: the next adoption completes; final state equals the uninterrupted run's; a second adoption is a no-op |

## 9. Recovery behaviour

| State | `diagnose` | `repair` |
|---|---|---|
| chained table, incomplete last line | `NEEDS_REPAIR` | moves the tail aside |
| chained table, chain broken / rows cut / newest row changed | `DAMAGED` | nothing |
| candidates missing | `INCOMPLETE_RESUMABLE` | (`complete_candidates` appends) |
| candidates unsupported / different | `DAMAGED` | nothing |
| identity absent or a subset | `INCOMPLETE_RESUMABLE` | (`identity_rebuild.adopt`) |
| identity unreadable | `NEEDS_REPAIR` | tail moved aside, or adopt |
| identity conflicting | `DAMAGED` | nothing; adoption needs a decision |
| source evidence damaged | `DAMAGED`; nothing rebuilt | nothing |

`diagnose` without the registry and the root checks identity for self-consistency only. The
28-crashpoint matrix of the previous run was **not** repeated; its suites pass unchanged except
for the request-log hook, which now targets the chained writer.

## 10. Defects found

| # | Defect in code that was committed | Severity | How found |
|---|---|---|---|
| E-1 | the request log, discovery inputs and events, qualifications and labels accept any change to an earlier row; **39–40 of 40** single-bit changes went unnoticed | high — evidence can be altered without any trace | measurement (old tree) |
| E-2 | a candidate lost to an interruption between a request's end row and its candidate row (permanent redirect) is never recreated; a candidate created after an interrupted pass was made from the later event; nothing checked the table against its evidence | medium | reading |
| E-3 | `diagnose` raised `KeyError` on a candidate row with a missing key and on request-log rows of another shape — the promise that it never raises on damaged content was false | low | measurement (after the first repair) |
| E-4 | the request log was first read after the channel requests of a run had been sent | low | reading |

Mistakes of my own, caught by the measurements: the first identity comparison ignored
`first_fetch_id` altogether (a changed bit in it went unnoticed, 8 of 40) — now compared as a
statement; my first tamper helper changed the digit of a schema version and tested nothing about
the chain; my first conflict test altered a byte inside the schema string and got the
(correct) status `REBUILDABLE`; the first rebuild called a half-promoted pack "damaged evidence";
one crashpoint was armed in the verification build instead of the adoption build. And I again
ran a shell command with a heredoc against the repository rule — twice in this run, both empty and
without effect (the fifth and sixth such slip of this session).

## 11. Remaining integrity limits

1. **Rows written after the last closed run** are chained but not anchored until the next close
   or append (labels written after a run ended: 7 of 40 unnoticed in the last row).
2. **Descriptive fields** of pack manifests, preservation manifests and run results are not
   covered by any digest (a single bit: about a third unnoticed in the previous run's
   measurement). None of them is evidence that cannot be recomputed or has no other copy.
3. **A rebuild of identity under another order of identification** can differ in relations; it is
   reported (`CONFLICTING`) and not accepted without a decision. In the pipeline's own order it is
   byte-identical.
4. **The rebuild reads the packs it verifies**: `diagnose` with the registry costs as much as
   reading the preserved packs.
5. **The ledger, the request log and the discovery tables cannot be rebuilt** — they are the
   evidence; the answer to their loss is the preserved packs, not a rebuild.
6. **Power failure, other file systems, a share**: unchanged from CPD-0009.
7. A chained table that is *replaced wholesale* by a different, internally valid chain is detected
   only through the heads of closed runs; before the first close, not at all.

## 12. Tests

`python -m pytest -p no:cacheprovider -q` (Python 3.12.10, pytest 9.1.1):

| | Result |
|---|---|
| at the start | 825 passed, 1 skipped |
| at the end | **897 passed, 1 skipped** (+72), 167 s (130 s before) |
| new | `test_evidence_integrity.py` (71 cases) and the header check of CPD-0010; `test_integrity_invariants`, `test_readiness`, `test_admission_eval` and the child process of the crash tests adjusted for the `v2` schemas, the moved crashpoint and the classification of a damaged identity table |
| the skip | unchanged |
| crash-recovery, concurrency, invariants | run in full, unchanged in number |

Cost of the checks (measured, diagnostic): chained append 1–7 ms (lock, sync, read-back); reading
and authenticating 5,000 rows / 3.1 MB 0.02 s; heads of all tables 0.08 s. Nothing here invites
switching a check off.

## 13. Validation classification

| Kind | Supported |
|---|---|
| robustness | the manipulation, torn-tail, damaged-evidence and interrupted-rebuild cases of §8 |
| reproducibility | the rebuild is byte-identical to the pipeline's tables and to a second rebuild; after a real kill a second process reconstructs the same state |
| replicability, generalisability | nothing |

## 14. Consequences for the real canary

- Evidence written during the canary is protected from the first row. Nothing needs migrating.
- After any abnormal end: `recovery.diagnose(workspace, root, registry=registry)` — with the
  registry and the root it also says whether the identity tables are right.
- **Close every run** (`close_run`): the close is what anchors the newest rows. A run that never
  closes leaves its last rows covered by the chain alone.
- Derived tables are not worth protecting by hand: if `diagnose` says `REBUILDABLE`, rebuild.
  If it says `SOURCE_EVIDENCE_DAMAGED`, stop: the preserved packs are what failed.

## 15. Next step, and the question the brief asked

**Is there a locally answerable integrity question, not needing real outlets or a preservation
target, that should sensibly be settled before the first real canary?** No. Limits 1 and 2 above
are known, measured and accepted: neither is evidence that cannot be recomputed or recovered from
another copy, and limit 1 closes at the next run close. The remaining open items are all bound to
the real target — locks and exclusive publication on its file system, power-loss behaviour —
and belong to the Phase-1 gate (O-3), where the two process suites should be run on the target.

**No further technical pre-canary run is needed.** What stands between the repository and the
first real fetch is the operator's list: O-11, O-1 (with the schedule policy), O-2, O-3.
