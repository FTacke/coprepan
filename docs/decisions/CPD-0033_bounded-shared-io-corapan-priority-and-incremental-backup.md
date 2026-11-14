# CPD-0033 — Bounded shared I/O: CO.RA.PAN has priority; no full-tree read in a regular cycle; incremental backup with stated evidence reuse

| Field | Value |
|---|---|
| Date | 2026-11-14 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Execution | implemented and tested offline (`tests/test_resource_isolation.py` and the existing suites); in force for the next scheduled backup run and for every intake planned under `intake-controller/2`. **Nothing of it has run against the institutional share yet**: the share refused logons for this workstation's account during the whole run (CO.RA.PAN's own observation `AUTH_REFUSED` since 2026-11-14T06:57Z), and acquisition stays `disabled` |
| Builds on / amends / supersedes | builds on CPD-0015 (joint storage contract, P2/P4/P5/B1), CPD-0029 (the bounded intake), CPD-0030 (the share as primary, Phase D backup), CPD-0009 (writer lock), CPD-0010 (identity rebuild); amends CPD-0029 in three points (decision 5) and the Phase-D backup procedure of CPD-0030 (decision 6); supersedes nothing |
| Does not change | the joint storage contract (bundle `49a3ca88…afb036`) or any of its invariants; P2 (every `RAW_PRESERVED` still needs the bytes re-read on the primary past the client cache); any root, identity marker, object, pack, index or manifest; the acquisition policy (`external_acquisition: disabled`); any gate of `docs/STATUS.md` §5; the scheduled task `COPREPAN_PreservationBackup` (its command line is unchanged; the code it runs changes) |
| Decided by | the operator's brief of 2026-11-14 ("CO.PRE.PAN_v3 – Umfassender Architektur-, Storage-, Contract- und Acquisition-Readiness-Run"), which authorises the technical repairs and requires that CO.PRE.PAN does not impair CO.RA.PAN, which has priority on shared storage, network and I/O; the values are the commissioned agent's, stated as scenario assumptions |
| Sister decision | none. CO.RA.PAN is unchanged (read-only in this run); a proposal to it is in the run report §10 |
| Run report | [`2026-11-14_coprepan-architecture-storage-contract-and-acquisition-readiness.md`](../agent-runs/2026-11-14_coprepan-architecture-storage-contract-and-acquisition-readiness.md) |

## Context

Both corpora run on one workstation and share three things: the institutional share (one DFS server and namespace, in practice one
Windows account), the external USB device `D:` that holds both projects' BACKUP copies and much of CO.RA.PAN's working storage, and the
`C:` umbrella of workspaces and spools. CO.RA.PAN's production is far more data-intensive and has priority. Read on 2026-11-14:

- **The daily backup re-hashed the whole primary over the share.** `scripts/preservation_backup.py run` took a fresh baseline of every
  object (78 min for 8,816 objects / 395,018,230 B on 2026-11-13, measured from the run's own evidence) and re-read every object of the
  backup, every day at 04:45 -- inside CO.RA.PAN's Sunday historic-backup window and next to its 30-minute backup ticks. CO.RA.PAN's
  run reports record the contention ("adds to the share load", 2026-10-30; "beside the CO.PRE.PAN backup window at 4.1 MB/s",
  2026-11-09). The cost grows with the corpus.
- **Every new promotion read every manifest of its area** (`preservation.find_by_content`): with 2,204 packs, 4,408 small reads per new
  pack on a link measured at about 260 ms per small file (2026-10-14) -- O(n) per pack, O(n²) over the corpus. Never seen in practice:
  no production write has happened on the share since it became the primary (2026-10-18).
- **The derivation re-read every pack it had just verified**, twice (identity and extraction, then labels), each time re-hashing both
  masters on the share past the client cache; **an intake's finalizer re-hashed every master of the workspace and rebuilt the identity
  tables from every preserved pack read from the share.**
- **An unreachable share was retried per pack and per cycle**, every 5 minutes, with no memory across processes. CO.RA.PAN had to build a
  persisted back-off for the same reason (about 60 logon attempts an hour from one of its processes); on 2026-11-14 the share refuses
  this account's logons.
- **No CO.PRE.PAN process knew of CO.RA.PAN's windows, of its capacity floors** (it stops its own production below 20 GiB free on `C:`
  and on its `D:` volume), or of a way for the operator to pause CO.PRE.PAN's shared I/O without killing it.
- **An outage stopped every request** of an intake as soon as one pack was pending, although the received bytes are complete and
  verified on local disk (P4/P5).

## Decision

1. **A tracked resource policy** (`config/resource_policy.json`, schema `coprepan-resource-policy/v1`, version `2026-11-14.1`, read by
   `src/coprepan/resource_policy.py`): limits for backup and fixity (one worker, 2 MiB/s, 90 minutes, a fixity slice of 300 objects /
   256 MiB per run, a 90-day cycle, 10 restore samples), free-space floors (60 GiB for RUNTIME, SPOOL and BACKUP -- above CO.RA.PAN's
   warning level), the bounds of pending preservation in an intake (5,000 packs, 5 GiB, 72 h), the share back-off (5 min doubling to
   60 min) and quiet windows taken from CO.RA.PAN's registered tasks (daily 03:15–04:30, Sunday 04:00–07:00, Wednesday 01:15–07:45,
   local time). Every number is a scenario assumption with its basis named in the file; a change is a new version of the file. Since
   this decision the file is pinned by the acquisition baseline (`freeze.py`, `configuration`).
2. **The share gate.** Every resolution of the PRESERVATION root by an intake, the backup, the audit and the status goes through
   `ShareGate`: after a failed contact (an unreachable root, or an I/O failure during a promotion) nothing in CO.PRE.PAN contacts the
   share before the back-off ends; the state is persisted in `<RUNTIME>/state/share_gate.json` and survives a restart. A refusal of the
   gate is an unreachable root to the pipeline (P1/P5: the pack stays honestly pending).
3. **The sibling advisory -- caution only.** CO.RA.PAN's own observation of the share (`corapan-preservation-mode/v1`, the file named by
   `COPREPAN_SIBLING_PRESERVATION_STATE` in the workstation's `.env`) is **not a declared interface** of CO.RA.PAN. It is therefore used
   in one direction only: a fresh (≤ 30 min) observation that the share is degraded closes the gate until CO.RA.PAN's own next probe; a
   fresh observation that it is slow defers maintenance. A missing, stale, unreadable, unrecognised or normal observation **permits
   nothing** the policy does not permit by itself; missing information is never read as idle.
4. **The content check of a promotion from a local index; the verified local read right after preservation.**
   `src/coprepan/preserved_index.py`: a copy of each preservation manifest under `<RUNTIME>/cache/preservation_manifests/<target id>/`,
   keyed by the target's identity marker (T1). The content check lists the area once and reads only the manifests it does not hold; the
   manifest of the object itself is always read from the root, every verification of bytes on the root is unchanged. A pack that
   `preserve_pack` has just made `RAW_PRESERVED` -- both masters re-read on the root past the cache seconds before -- is derived (identity,
   extraction, labels) from the workspace copy **only when its bytes hash to the manifests' digests** (`trust_local_copy`, passed only by
   `canary_driver._derive`). **Every other reader re-verifies on the root as before**; a master that no longer verifies is not read.
5. **The intake controller `intake-controller/2`** (amends CPD-0029): (a) with a resource policy, an intake goes on while what is pending
   stays within the policy's bounds and the RUNTIME volume above its floor, and pauses beyond them (`held_because` in the state); without
   one, the behaviour of `/1` (nothing asked while anything is pending) is kept; (b) `<RUNTIME>/state/PAUSE_IO` pauses the requests at
   the next decision point, and its removal resumes them; (c) the finalizer re-hashes the masters of **its own packs** on the root and
   checks the identity tables for self-consistency; the whole-root read (every master, the identity rebuild from every preserved pack)
   is the operator-ordered `scripts/preservation_audit.py`; (d) a tick of a running intake (`scripts/intake_operator.py tick`, every 5
   minutes) no longer resolves the share when it loads its environment -- it reaches it only through the gate, so an outage neither
   costs a logon attempt per tick nor fails the tick. A start still needs the target. A plan of `/1` is history and is not run by `/2`.
6. **The backup: `INCREMENTAL` is the regular run, `FULL` the operator's** (amends the Phase-D procedure of CPD-0030). One enumeration of
   each root instead of a hash of every object. **Stored hash evidence is reused only when all hold:** the journal row was written by a
   copy that re-read the landed bytes unbuffered against the digest read from the primary (or by a re-hash after a timestamp change,
   `RESTAMPED`); the primary carries the identity the previous verified receipt names; the object's size **and** `mtime_ns` are the row's;
   the backup root holds a file of that size. **A full re-read stays required** for another primary identity, a torn or absent row, a
   changed timestamp (re-hashed: `RESTAMPED`, or `SOURCE_CHANGED_SINCE_BACKUP` and never overwritten), a missing backup copy (copied
   again), the operator's `--full`, and -- spread over time -- for every object: each run re-hashes a budgeted slice on **both** roots past
   the client cache, oldest verification first; the status flags a cycle longer than 90 days. An object the journal holds and the primary
   does not is `MISSING_ON_PRIMARY`, a finding; nothing is removed. A run without a verified receipt of this primary is `FULL`
   automatically. A run yields (`DEFERRED`, exit 0) in a quiet window, while paused, while the gate is closed, under the BACKUP floor or
   while another run holds the root's lock; it stops at its time budget or a refusal (`STOPPED`, resumable, no receipt). The receipt of an
   incremental run names its mode, its evidence basis, the slice re-read and the last full run; its `tree_sha256` is that of the full
   inventory, and an unchanged primary must give the previous receipt's digest. `_backup/last_run.json` records every attempt.
7. **Health from local files.** `scripts/storage_contract.py status` reports, without contacting the share while the gate is closed: the
   backup's receipt age (warning above 72 h, failure above 336 h), the last attempt, the fixity rotation, the share gate, the pause, the
   sibling advisory, the free-space floors and the pending fetches of the workspace with their age (P4).

## Why it satisfies the contract

B1 asks that the copy was produced from the primary and verified against the primary's inventory, every object by path, size and
digest. Every object of today's listing is on the backup with the digest established by an unbuffered verification of the copy against
bytes read from this primary, reused only under the write-once invariant (P8) with unchanged size and timestamp; new objects are verified
in the run. What an incremental receipt does **not** claim -- that an object outside today's fixity slice was re-read today -- it says. P2
is untouched: no `RAW_PRESERVED` is given without the re-read on the primary. I2 is untouched: a closed gate is "unreachable", never
"empty".

## Alternatives considered

- **Keep the daily full baseline.** Rejected: 78 minutes of share reads per day at today's size, growing linearly, at a time CO.RA.PAN
  uses the share; it is kept as `--full` for an explicit order.
- **Content-addressed marker files on the share** for the duplicate check. Rejected: a change of the on-disk layout of a joint-contract
  primary; a local, rebuildable index needs no joint decision.
- **Derive always from the local copy.** Rejected: it would drop the tested guarantee that a pack whose master no longer verifies is not
  read; the local read is limited to the one moment a fresh verification exists.
- **A joint lease or orchestration service with CO.RA.PAN.** Rejected for now: it needs changes in CO.RA.PAN and is not needed for
  CO.PRE.PAN's side; proposed as an option in the run report.
- **Read CO.RA.PAN's state file as a permission ("idle, go").** Rejected: undeclared semantics; absence of information is not idleness.
- **Stop all requests while anything is pending (intake-controller/1).** Kept as the behaviour without a resource policy; with one, the
  bounded pending keeps an unattended intake useful through a share outage without holding more than the local disk guarantees.

## Not decided here

- Whether and when acquisition is activated, or another intake is armed: the operator's (`docs/STATUS.md` §5; nothing here closes a gate).
- A joint coordination interface with CO.RA.PAN (a declared state file, shared windows, a lease): proposed in the run report §10, needs
  CO.RA.PAN's decision.
- The schedule of `COPREPAN_PreservationBackup` (unchanged at 04:45 local; the windows make a run inside them defer).
- The cadence of an operator-ordered `FULL` run or whole-root audit beyond the fixity rotation's 90-day cycle.
- Any change of the joint storage contract; whether CO.PRE.PAN adopts CO.RA.PAN's read-replica role of the BACKUP (its §13j) — not
  taken over here.

## Validation debt

- The share: no promotion, content check, gate back-off, incremental backup or fixity slice has run against it (unreachable for this
  account during the run). The first scheduled backup after the merge is the first real evidence; its `last_run.json` and receipt say
  what happened.
- Coexistence under real CO.RA.PAN load is constructed (windows, gate, advisory, throttle, budgets, floors) and tested on simulated
  signals; **it is not measured** on the shared link.
- The policy's numbers are scenario assumptions; a measurement of the incremental run's real duration and of the share's per-file
  latency on a normal day is owed.
- The quiet windows copy CO.RA.PAN's task times as registered on 2026-11-14; a change there is not seen here until the policy is
  versioned again (or CO.RA.PAN declares an interface, run report §10).
