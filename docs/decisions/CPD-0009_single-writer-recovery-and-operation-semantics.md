# CPD-0009 — Single writer, recovery after interruption, and what each operation guarantees

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the adversarial persistence, crash-recovery and concurrency audit (2026-10-08), which ordered the existing guarantees to be broken on purpose, real defects to be repaired where small and understood, the actual operation semantics to be decided and documented, and a CPD to be written for durable semantics. Recorded by that run; subject to the operator's review. |
| Kind | architecture |
| Scope | who may write a workspace; what an append guarantees; the ledger record format; exclusive binding of an identity on the preservation root; the layer store under competing writers; recovery after a process death; the semantics (at-least-once / exactly-once / idempotent) of every central operation; when a 304 is believed |
| Builds on / amends / supersedes | builds on CPD-0001 (ledger before state, write-once, no deletion), CPD-0003 (canonical JSON), CPD-0005 (pack, identity, layers), CPD-0006 (request log, transport), CPD-0007 (re-fetching, conditional requests). **Amends the ledger record format** of Foundation Core I: `coprepan-ledger-record/v1` → `v2` (§5), forward-only — no ledger of corpus material exists. Tightens CPD-0007 §4 (§7). |
| Does not change | any id, the pack format, the fetch record, the preservation manifest schema, the layer-store layout, any policy or gate |
| Run report | [`docs/agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md`](../agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md) |
| Evidence | measurements with real concurrent processes and real process kills, before and after the repairs (run report §4–§7); `tests/test_crash_recovery.py`, `tests/test_concurrency.py`, `tests/test_integrity_invariants.py` |

Validation debt: everything was measured on one workstation (Windows, NTFS, local disk), on
temporary directories, with a loopback server. No real preservation target, no network file
system, no power failure. Listed in `docs/STATUS.md` §6.

## Context

Until this decision the persistence layer said "one writer at a time" in its docstrings and
enforced it nowhere, and every failure test injected its failure inside the process under test.
An audit with real processes found what that leaves open:

| Measured on the code as committed at `1e5f807` (2026-10-08) | |
|---|---|
| three processes, 200 ledger transitions each | 600 reported as written, **389 on disk**, the ledger unreadable afterwards |
| three processes, 300 table rows each | 900 reported, **597 on disk**, the table readable — the loss invisible |
| three processes storing different answers under one layer fingerprint | 120 of 120 reported `STORED`; all 40 slots unreadable afterwards |
| three processes promoting different bytes under one identity | two or three reported `promoted` in **8 rounds of 8**; in one round the master did not fit its manifest |
| a process killed while writing a run record | the run could never be resumed |
| a process killed while writing the first record of a new pack | the pack of that outlet and day unusable |
| a process killed between the pack append and the ledger transition (HTTP run) | the fetch stays `FETCH_PLANNED`; identity and extraction then refuse **the whole pack** |
| a process killed between a version row and its relation | the relation (`duplicate_of`, `moved_to`) silently missing for good |
| a process killed mid-append of any table | the table refused from then on; no recovery path existed |

Appending to a file is not atomic between processes on this platform. None of these was a
misuse: each is what two schedulers started by mistake, or one kill at the wrong moment, would do.

## Decision

### 1. Principle

**Evidence is written at least once and identified exactly once; success is claimed only for
what can be read back.** No operation promises "exactly once" for an effect on the outside world.
Every operation promises that its durable record either stands whole under one identity or does
not stand, and that a repetition is recognised.

### 2. One writer per workspace — enforced

- Every operation that writes a workspace holds that workspace's **writer lock**
  (`coprepan.exclusive`): acquisition, sealing and preservation, identity and extraction, replay,
  admission labels, repair. A second process is refused at once with `WorkspaceBusy`. It does not
  wait and it writes nothing.
- The lock is an operating-system lock on an open file. It ends with the process that holds it,
  however that process ends. **There is no stale lock**, and so no rule for breaking one.
- The lock is taken per operation, not per run: two processes may alternate between steps. That
  is safe because every step recognises its own finished work — and for no other reason.
- Underneath, as a second line: every append to a ledger, table or open pack is serialised by an
  operating-system lock for the length of the append and re-reads what it wrote; a ledger or an
  open pack that grew behind an object's back refuses that object's next write.

### 3. What each operation guarantees

| Operation | Semantics | Durable identity | After an interruption |
|---|---|---|---|
| HTTP request | **at least once** — may be sent again if the process died before its end was logged; may have been sent with nothing recorded | — | the intent (`PLANNED` without `FINISHED`) stays on record for good; the candidate is asked again |
| fetch evidence (response → pack + ledger) | **at most once per response, never doubled**: a response is recorded under its `fetch_id` or lost with the process that held it in memory | `fetch_id` over URL, start instant, body hash | a second request is a second fetch with its own id; two answers are never merged |
| pack append | **atomic per fetch**: whole or absent; a torn tail is detectable and is moved aside, never read | position in the pack, bound by the seal | `repair` cuts the pack back to its last whole fetch |
| ledger transition | **exactly once per (subject, state)**: the machine refuses a repeated or illegal step; the record is chained to its predecessor | `seq`, chain hash | a torn last record is moved aside; a fetch whose bytes are in a verified pack is reconciled to its recorded outcome |
| seal | **idempotent**: repeated sealing re-verifies and returns the same manifest | pack SHA-256 | completed by sealing again, from any of its three intermediate states |
| promotion | **idempotent for the same content; exclusive for an identity**: one identity is bound to one content, by whoever binds first | manifest (object id → SHA-256) | completed by promoting again; a staging file is never a master |
| `RAW_PRESERVED` | claimed only after both masters were re-read and hashed on the preservation root | — | `PRESERVATION_PENDING` is never read as preserved |
| document and version assignment | **idempotent per fetch**; relations are re-derived from the stored rows | `document_id`, `document_version_id` | completed by running the step again |
| extraction layer | **one answer per fingerprint**: the same answer again is a no-op; another answer is a conflict, never a version | fingerprint → artifact id | an abandoned write is never an answer |
| admission label, qualification | **once per (subject, rule set)** | key in the table | completed by running the step again |
| replay | **read-only on everything preserved**; adds at most a layer that did not exist | fingerprint | — |

### 4. Recovery

- `recovery.diagnose` names the state of a workspace without changing it, and never raises on
  damaged content. Four classes: `CLEAN`; `INCOMPLETE_RESUMABLE` (running the step again
  completes it); `NEEDS_REPAIR` (a torn tail); `DAMAGED` (a person has to look: lost evidence, a
  master that does not verify, rows that contradict each other).
- `recovery.repair` does one thing: it moves the torn tail of an append-only file into a sidecar
  beside it. **It never rewrites a record, never invents a state, never deletes.**
- The one reconciliation the pipeline performs by itself: a fetch that a *verified* pack holds
  while the ledger says `FETCH_PLANNED` is moved to the outcome the pack records, marked
  `reconciled_from_pack`. The pack is the evidence; nothing the pack does not prove is written.
- Leftovers are never deleted and never read as data: staging files (`*.part-*`), abandoned or
  withdrawn layer writes (`.staging/`), torn sidecars (`*.torn-<n>`). They are counted by
  `diagnose`.
- A record that must be whole or absent (run record, run result, manifests, index) is written
  under a staging name and renamed.

### 5. Ledger record `coprepan-ledger-record/v2`

Every record carries `previous_record_sha256`: the SHA-256 of the line before it (`null` for the
first). A record that was changed, removed, duplicated or moved is detected by the record after
it. The last record has no successor to vouch for it. A `v1` file is refused, not read as `v2`.

### 6. Binding an identity on the preservation root

A master and the manifest of a new identity are published **exclusively**: only if their name is
free. A process that finds the name taken either sees its own bytes there — the same promotion —
or has an `IdentityConflict`. The only case in which a master is replaced is the declared repair:
a manifest names these bytes and the master does not hold them.

### 7. When a 304 is believed

A `304 Not Modified` is the server's statement about a body. It is believed only for a body the
corpus holds: the fetch it names must be `RAW_PRESERVED`, on a preservation root where it
verifies, with the body hash the record names. Otherwise nothing is assigned
(`revalidation_target_not_preserved`). A conditional request is sent only for a body that is
preserved; otherwise the page is simply asked for again.

### 8. Tables refuse contradictions

A keyed table (documents, observations, events, candidates, qualifications, labels) refuses two
different rows under one key when it is opened. The same row twice is one row. A table never
answers with "whichever came last".

## Alternatives considered

| Alternative | Why not |
|---|---|
| leave "one writer" a convention | measured: 35 % of ledger records lost without an error |
| a lock *file* (existence = held) | needs stale-lock detection after every kill; the wrong guess either blocks forever or admits a second writer |
| wait for the lock instead of refusing | hides a double start, which is an operator error worth seeing |
| one lock per run instead of per operation | a killed run would have to be "taken over"; per-operation locking needs no hand-over because steps are idempotent |
| a multi-writer ledger (re-read the tail under the lock on every transition) | every other table would need the same; one writer is what the design assumed all along |
| automatic repair of whatever is found | a repair that judges content can destroy evidence; only the mechanical case (a torn tail) is automatic |
| delete staging files and sidecars after recovery | no deletion path (CPD-0001); they cost little and are evidence of what happened |
| a per-record checksum instead of a chain | detects a changed record, not a removed or reordered one |
| chain every table like the ledger | changes every table schema at once; decided only for the ledger, whose every state claim depends on it (see "Not decided here") |
| trust a 304 whenever the request log shows an earlier 200 | the log proves a response came back, not that its bytes survived |
| resolve a conflicting promotion by "last writer wins" | the measured defect |
| keep both conflicting layer answers and refuse the slot | leaves the store unusable for that fingerprint; withdrawing the later answer keeps one and tells the other writer |

## Consequences

- A double start is a visible refusal instead of silent loss.
- An interrupted workspace has a named state and a deterministic way on; 28 crashpoints are
  killed for real in the test suite and end as if never interrupted.
- The ledger format changed before any corpus ledger existed. From the first real fetch on, a
  further change is a migration.
- The workspace must live on a file system whose locks work (a local disk). A network share for
  the *runtime workspace* is outside what was tested.
- Appends cost about 4 ms each on the test machine (lock, sync, read-back); a fetch makes five.

## Not decided here

- Integrity protection of the other append-only tables (request log, discovery, identity,
  qualification, labels) and of the descriptive fields of manifests and run results: a single
  changed bit there is often not noticed (measured: run report §9). The ledger chain shows the
  pattern; applying it changes every table schema and is a decision of its own.
- A rebuild of the identity tables from preserved packs and layers.
- Behaviour after a power failure; directory durability; any file system other than the one
  tested; the runtime workspace on a network share.
- Whether leftovers are ever collected, and by which recorded procedure.
- Concurrency of two *workspaces* acquiring for the same outlet and day (they would build the
  same pack id): the second promotion is now refused; whether such a setup is allowed at all is
  an operational rule.
- The outage spool under competing writers (not exercised; it still replaces on rename).
