# CPD-0015 — The joint storage-management contract `crosscorpus-storage/v1` is in force for CO.PRE.PAN; the outage spool is in the acquisition path

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the joint storage-contract run of 2026-10-08 (run from the CO.RA.PAN repository with write scope over both sister repositories), which ordered one contract, its implementation in both projects, drift checks, and the wiring of the existing spool into the acquisition path |
| Kind | policy · architecture |
| Scope | storage roles, holdings and their states; role separation; what a preservation step may claim; pending objects and the outage spool; protection from cleanup; backup status; the procedure of a root migration |
| Builds on / amends / supersedes | builds on CPD-0005 (pack), CPD-0009 (writer lock, operation semantics), CPD-0014 (roles, interim primary). **Amends CPD-0014 §8** (the spool is now wired in) and the spool's record naming. Supersedes nothing |
| Does not change | any identifier, any stored artefact, the layout under a preservation root, the acquisition policy, the crawler identity, the pinned release contract (`crosscorpus-release/v1`, revision 1) |
| Run report | [`docs/agent-runs/2026-10-08_joint-storage-contract-and-spool-wiring.md`](../agent-runs/2026-10-08_joint-storage-contract-and-spool-wiring.md); the joint report of the run is in CO.RA.PAN: `docs/agent-runs/2026-10-08_crosscorpus-storage-contract-implementation-and-migration-preparation.md` |
| Evidence | `tests/test_storage_contract.py` (99 tests); the full suite of the run report; `scripts/storage_contract.py check` / `status` / `compare-sister` on this workstation |

Validation debt: the outage path has run on temporary directories (system temporary directory and
a temporary directory on the interim primary's file system) with synthetic packs. It has never
carried corpus material, and no real outage has occurred. Nothing here qualifies the institutional
file system.

## Context

CPD-0014 gave CO.PRE.PAN the storage roles of CO.RA.PAN 3.0 and an interim primary, and recorded
that the outage spool, although built and tested, was not in the acquisition path. CO.RA.PAN had
the same rules under other names and a gap of its own (no role for a secondary copy of its
primary). Both corpora will move their preservation primary to one institutional file system that
does not exist yet. Two implementations of one intent drift unless the intent is written once and
checked on both sides.

## Decision

### 1. The contract

`crosscorpus-storage/v1` is in force for CO.PRE.PAN, bundle digest

```text
8d17fc214076b21e47774d228e016dfe36484b29ce0ecad693456c07f9018fb3
```

(two files: `CONTRACT.md`, `conformance/CASES.json`). The canonical home is CO.RA.PAN
(`contracts/crosscorpus-storage-v1/`); this repository holds a verbatim copy at the same path,
pinned in `config/crosscorpus/contract_pins.json` with status `IN_FORCE`. CO.RA.PAN's record is its
D95. There is no shared package: `src/coprepan/storage_contract.py` is this repository's own
implementation, and the two share only the hand-written reference cases.

Role names: the contract's `REPO` is `REPOSITORY` here; every other role has the same name
(CPD-0014 §2). The contract's holdings are `PRODUCTION` and `HISTORIC`; a holding is a division of
storage, not a corpus and not an id family. CO.PRE.PAN has a `PRODUCTION` holding only; no root is
configured or present for `HISTORIC` (the legacy press corpus is the read-only legacy tree, bound
by the freeze manifest, and is not a preservation holding of this repository).

### 2. Separation is decided by the contract's function

`storage_roots.validate_role_separation` now derives its refusal from
`storage_contract.role_separation` (`separation_codes`): `ROLE_SHARED`, `ROLE_NESTED`,
`BACKUP_NOT_INDEPENDENT`, `VOLUME_UNKNOWN`, and — when the roots of the sister corpus are given —
`FOREIGN_CORPUS_OVERLAP`. Behaviour for every configuration that was valid before is unchanged.

### 3. The outage spool is in the acquisition path

`core_pipeline.preserve_pack` is the preservation step of the acquisition path:

```text
seal → fetches PRESERVATION_PENDING → resolve the preservation root now
  target available      promote pack and index, re-read both masters → RAW_PRESERVED        route "direct"
  target unavailable    (a refusal of the root, or an I/O failure during promotion)
      usable spool      verified copies of pack and index in the spool, within its bounds  route "spooled"
      no usable spool   the sealed pack stays in the workspace                             route "workspace"
      in both cases     the fetches stay PRESERVATION_PENDING; nothing is RAW_PRESERVED
  content refusal       (hash mismatch, identity conflict) is raised; never spooled
```

`core_pipeline.drain_spooled_packs` replays the spool with the existing promotion: each object is
promoted, **re-read and verified on the target**, and only then is its spool copy released; a pack
is `RAW_PRESERVED` in the ledger only when its pack and its index both verify there.

- Nothing is deleted on any of these paths: the workspace copy of a pack is never removed by the
  preservation step, and a spool copy is released only by a verified drain.
- A configured spool that cannot be reached, or that is full, changes nothing but the route: the
  pack stays in the workspace, pending.
- Every step is repeatable. Interruption between the two spooled objects, after a spool copy and
  before its pending record, between promotion and release, and after a drain before the ledger
  is completed, each leave a state that the next call completes (tested at each point).
- `seal_and_preserve` stays as the direct path with an already resolved root.
- **No driver calls these functions yet**: the canary driver is not built. Whoever builds it calls
  `preserve_pack`, not `seal_and_preserve`; the module documentation of `http_acquisition` says so.

### 4. Spool record names

A pending record is `state/pending/<area>--<object_id>.json` (was `<object_id>.json`): a pack and
its index share one object id in two areas and must not share one record. A record with the old
name is still found for its own area. No spool on any machine held a record when this changed.

### 5. Drift checks

`tests/test_storage_contract.py` (suite `foundation_contract`): the pinned copy is the bundle (no
neighbouring checkout is read); every shared case; the closed vocabularies; the resolver's codes;
the acquisition path through outage, drain and read-back, with its interruption points; a root
change that changes no id and no payload hash; the read-only migration tools; the joint check on a
synthetic sister. The joint check against the real sister checkout is an operator command
(`python scripts/storage_contract.py compare-sister`), because this repository's tests read no
other repository.

### 6. Migration

The procedure of a root move is the contract's §11; CPD-0014 §6 named its steps and stays valid.
The read-only half is `scripts/storage_contract.py migration-inventory` and `migration-verify`;
the mutating half is an operator-ordered act in no tool. `preservation_interim` is never renamed
and declared a backup.

## Alternatives considered

- **A shared Python package for both corpora.** Rejected: one implementation checks nothing, and a
  third repository is a third thing to keep in step.
- **Spooling inside `seal_and_preserve`.** Rejected: that function takes a resolved root, and the
  outage case is exactly the one in which no root resolves. The new entry takes the resolution as a
  callable.
- **Reading the real sister checkout in the test suite.** Rejected: tests here touch no other
  repository; a synthetic sister exercises the comparison, the command does the real one.

## Consequences

- A change to roles, resolution, the spool, the promotion or the protection rules must keep the
  shared cases passing; a change of the rules is a change of the bundle in CO.RA.PAN, of both pins
  and of both implementations.
- The states of this workstation are unchanged: `BACKUP`, `DISTRIBUTION`, `EXCHANGE` are
  `NOT_CONFIGURED`; the interim primary is a sole copy and holds its target marker only.

## Not decided here

- A backup: there is none, and none is configured while `D:` is the primary.
- A `HISTORIC` holding for CO.PRE.PAN. The contract's namespace would place it at
  `…\projects\panhispanic_media_corpora\historic\coprepan`; nothing exists there and nothing is planned by this decision.
- The institutional file system: its mount, quota and qualification.
- The canary, its driver and its arming.
