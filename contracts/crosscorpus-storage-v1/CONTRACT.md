# Joint storage-management contract `crosscorpus-storage/v1`

**Status: in force in both repositories when both pin this bundle digest and both conformance suites
pass (§12).** It governs how CO.RA.PAN (spoken radio) and CO.PRE.PAN (written press) name, resolve,
separate, write, protect and move their storage. It decides no location, quota, licence or
scientific question, and it activates nothing.

This directory is the **contract bundle**: `CONTRACT.md` and `conformance/CASES.json`. It is
identified by one digest — the tree digest of `crosscorpus-release/v1` §4.5 (the record-set digest
of `{path, sha256, size}` of every file) — and is read byte-identically by both repositories. All
bundle files are LF and are stored verbatim.

The key words *must*, *must not*, *may* are used in their plain normative sense.

No machine path appears in this bundle. Where a root lies on one machine is that machine's
configuration (§4); the actual and the planned topology of each project is recorded in each
repository's storage documentation and run reports, against the vocabulary of §3.

---

## 1. Scope

- the **roles** a storage root can have, and the two **holdings** of each corpus (§2);
- **authority**, temporary roles and planned changes of role (§3);
- **configuration**: how a root is resolved, what an unconfigured or unreachable target means (§4);
- **separation**: roots, nesting, volumes, the administrative umbrella, the institutional namespace
  (§5);
- **target identity** and availability (§6);
- **fixity, promotion, pending objects, resumption** (§7);
- **retention and cleanup** (§8);
- **backup** (§9);
- **identity independent of the root** (§10);
- **safe migration** to another root (§11).

Each repository keeps its own implementation, names, data formats and layouts. Nothing here
requires a shared package, a shared repository or a common on-disk format. The two release
contracts (`crosscorpus-release/v1`, `crosscorpus-analysis/v1`) are not changed by this one: a
release names exports by content digests, and this contract says where such bytes may live and
when they count as preserved.

## 2. Roles and holdings

### 2.1 Roles

A **role** is a function, not a machine and not a directory name.

| Role | Function | Authoritative | Never |
|---|---|---|---|
| `REPO` | the git checkout: code, tracked configuration, documentation, small fixtures, compact hash-bound evidence | for code and tracked evidence only | a storage root for corpus data of another role |
| `RUNTIME` | workspace: open work, ledgers in flight, caches, staging, scratch, working stores | no | a backup; a preservation authority |
| `SPOOL` | bounded local write-ahead buffer in front of `PRESERVATION` for outages | no | an archive; a mirror; a backup |
| `PRESERVATION` | the durable primary: source material and what is not regenerable | **yes — the only authority for preserved objects** | — |
| `BACKUP` | a second, independent, verified copy of the `PRESERVATION` primary | no | the primary; a directory on the primary's volume |
| `DISTRIBUTION` | read-only copies for use; rebuilt from releases | no | a source of truth |
| `EXCHANGE` / `REVIEW` | transit and hand-over (incoming material, review packages) | no | an archive |

A repository may keep its own role names. It records the mapping to these names and states for
each role one of the configuration states of §4. A role a repository does not use is stated as
such; it is not silently mapped onto another.

### 2.2 Holdings

Each corpus has two **holdings**. A holding is an inventory and storage division inside one corpus:

| Holding | Content |
|---|---|
| `PRODUCTION` | the continuously acquired material and everything derived from it |
| `HISTORIC` | retrospectively acquired or inherited material (CO.RA.PAN: the historical pre-AI stream; CO.PRE.PAN: the legacy press corpus and retrospective acquisitions) |

A holding is **not a corpus**. It creates no new `corpus_id`, no new family of release ids and no
separate identity scheme; objects keep the identifiers of their corpus. Each holding has its own
`PRESERVATION` primary and, when one exists, its own `BACKUP`; the roles, states and rules of this
contract apply to each holding separately. Two holdings of one corpus may share one primary root
only when that is declared (§3.2, `SHARED_WITH_HOLDING`).

## 3. Authority, temporary roles, planned changes

### 3.1 Authority

For every holding there is, at any time, **exactly one** root that is the authority for preserved
objects: its `PRESERVATION` primary. Every other copy — workspace, spool, backup, distribution — is
derived from it or is on its way to it. A copy that is not on the primary is never the reason to
call an object preserved.

### 3.2 The topology record

Each repository keeps, in its storage documentation, a **topology record**: one row per
*(holding, role)* it has or plans, with these fields. The values are a closed vocabulary.

| Field | Values |
|---|---|
| `existence` | `PRESENT` (the root exists and is configured) · `PLANNED` (decided, not present) · `NOT_PLANNED` |
| `configuration` | a state of §4.2 |
| `role_today` | the role the root has now, or `NONE` |
| `authority` | `PRIMARY` · `INTERIM_PRIMARY` (the authority today, declared temporary) · `SECONDARY` · `NONE` |
| `copies` | `SOLE_COPY` · `VERIFIED_SECONDARY_EXISTS` · `UNVERIFIED_SECONDARY` · `NOT_APPLICABLE` · `UNKNOWN` |
| `target_role` | the role the root is planned to have, or `UNCHANGED` |
| `transition_requires` | what must be true before the change (free text naming gates of §11) |
| `shares_root_with` | `NONE` · `SHARED_WITH_HOLDING:<holding>` (a declared sharing of one primary root by two holdings) |

Rules:

- **A planned target is never written as if it were present.** `PLANNED` rows carry no configured
  value in tracked configuration and no variable set in an example file.
- **An interim primary is a primary.** Everything in this contract that protects a primary protects
  an interim one. "Interim" says that a move is planned; it weakens nothing.
- **A sole copy is said to be one.** `SOLE_COPY` is a legitimate, recorded state (it may be a
  deliberate decision); it is never reported as backed up.
- A change of role is a migration (§11). A root never changes role by being renamed or by a
  variable being pointed elsewhere.

## 4. Configuration

### 4.1 Where values live

- Tracked configuration holds **logical roles and references to environment variables**, never a
  drive, mount point, host name, share or home directory.
- The value of a root is **machine configuration**: a gitignored local file or the process
  environment. Precedence, highest first: an explicit argument of the caller · the process
  environment · the machine's local file. Nothing else contributes: no built-in literal, no
  directory guessed from another root, no neighbouring checkout.

### 4.2 Configuration states

Resolving a role yields exactly one state:

| State | Meaning | A caller that needs the role |
|---|---|---|
| `NOT_DECLARED` | tracked configuration declares no such target | is refused |
| `NOT_CONFIGURED` | declared; the variable is unset or empty | is refused |
| `DEFAULTED` | declared with a **default written in tracked configuration**; the variable is unset; the default is used and reported as such | proceeds |
| `UNUSABLE` | a value is set and is not acceptable as a root (relative; a filesystem root; violates §5) | is refused |
| `UNREACHABLE` | a value is set; the directory is not reachable now | is refused |
| `READ_ONLY` | reachable; a write is needed and not possible | is refused for writing |
| `AVAILABLE` | usable for what is asked | proceeds |

### 4.3 Invariants

- **I1 — no silent substitute.** An unconfigured target stays unconfigured. No code path replaces
  it by the local disk, the checkout, another role's root or a remembered former location. A
  default exists only as `DEFAULTED`: written in tracked configuration, reported in status output,
  and **never taken when a value is set** — a set value that cannot be used is a refusal, not a
  reason to default.
- **I2 — unreachable is not empty.** The content of a root that cannot be reached is unknown.
  Nothing concludes from unreachability that an object is absent, that a directory is empty or
  that work is finished.
- **I3 — resolution creates no root.** A missing root directory means "not available" (a share
  that is not mounted looks exactly like that). Creating a root is an explicit operator act.

## 5. Separation

### 5.1 Role roots

Path comparison in this contract is **lexical and case-insensitive**: a path is its sequence of
segments (split at `/` and `\`, empty segments and a trailing separator ignored), each segment
compared after Unicode full case folding. No resolution of links and no I/O is needed, so the rule
can be applied to an unreachable root. Treating two names that differ only by case as the same is
deliberately conservative: it refuses a configuration that would be unsafe on a case-insensitive
file system.

For the configured role roots of **one holding of one corpus**:

- **S1** no two roles have the same root (`ROLE_SHARED`);
- **S2** no role's root lies inside another role's root (`ROLE_NESTED`);
- **S3** `BACKUP` and `PRESERVATION` are on different volumes (`BACKUP_NOT_INDEPENDENT`); if the
  volume of either cannot be determined, that is a refusal (`VOLUME_UNKNOWN`), never a guess;
- **S4** no role root of one corpus equals, contains or lies inside a role root of the **other**
  corpus (`FOREIGN_CORPUS_OVERLAP`). One corpus's storage is never placed under the other's root.

A repository may declare **co-located roles** — one root deliberately serving two named roles (for
example a data workspace inside its checkout). The declaration is in tracked configuration, names
both roles, and is reported in status output. A declared co-location is exempt from S1/S2 **for
exactly that pair**; `PRESERVATION`, `BACKUP` and `SPOOL` are never part of one.

### 5.2 The umbrella and the namespace

An **administrative umbrella** is a directory that only groups role roots. It is not a role, holds
no data of its own and takes no part in S1–S4: sibling roots under one umbrella are the intended
layout.

- **Local sibling layout.** Under one local umbrella, per corpus: `<corpus>` (`REPO`),
  `<corpus>_workspace` (`RUNTIME`), `<corpus>_storage` (`SPOOL`).
- **Institutional namespace.** On an administratively provided root, per corpus:
  `projects/panhispanic_media_corpora/<corpus>`; for the historic holding
  `projects/panhispanic_media_corpora/historic/<corpus>`. The namespace is **joined without
  duplication**: leading segments of the namespace that the provided root already ends with are
  not repeated. A provided root that already ends in `projects` gets no second `projects`.
  (`conformance/CASES.json`, `namespace`.)
- A sub-root of a corpus under the namespace (for example a primary and, on another volume, a
  backup) is named by the repository; the two are different roots of different roles and are
  subject to S1–S3.

### 5.3 Planned paths are not targets

A path that is planned (§3.2 `PLANNED`) exists in documentation and decisions only. It is not
entered into tracked or local configuration before its root exists, it is not created by code, and
no status output reports it as anything but planned.

## 6. Target identity and availability

- **T1 — a primary has an identity that is stored on it.** The `PRESERVATION` primary of a holding
  carries an identity record (a marker written once when the target is taken into service, or an
  equivalent recorded identity of the share). "The preservation root" is a named thing, not
  whatever a variable points at.
- **T2 — the wrong target is a refusal.** Where an expected identity is recorded, a root that
  carries another identity, or none, is `UNUSABLE` for writing preserved objects
  (`TARGET_IDENTITY_MISMATCH`).
- **T3 — an alias is not an identity.** A drive letter or mount name that maps to a root is a
  convenience of one machine. Configuration, receipts and reports name the root itself; two
  spellings of one root are one root for §5.
- **T4 — availability is measured at the time of the write**, not remembered. A root that was
  reachable when a run started may be gone when an object is promoted.

## 7. Fixity, promotion, pending, resumption

### 7.1 Object states

Every object that is to be preserved is, with respect to the primary, in exactly one state:

| State | Meaning |
|---|---|
| `PRESERVED` | the object is on the `PRESERVATION` primary, its bytes there have been **re-read and verified** against the recorded digest, and the persistent record that says so exists |
| `PENDING` | the object is complete and verified locally (workspace and / or spool) and is **not** `PRESERVED` |
| `REFUSED` | the object was rejected for its content (digest mismatch, identity conflict); it is not rerouted anywhere |

Each repository keeps its own state names; it records the mapping. `PENDING` must be an explicit,
persisted, queryable state — not the absence of a record.

### 7.2 Invariants

- **P1 — no success without the primary.** An unreachable or unusable primary produces no
  `PRESERVED` state, no preservation receipt and no "done" for the step, whatever exists locally.
- **P2 — success needs full verification and its record.** `PRESERVED` requires, in this order:
  the bytes written to the primary; the bytes **on the primary** re-read and found equal to the
  recorded digest (for a tree: every file, by path, size and digest); the persistent record
  written. A copy that was verified only before the last write to its destination is not verified.
- **P3 — workspace and spool are not preservation.** No copy in `RUNTIME` or `SPOOL` makes an
  object `PRESERVED`, and neither role is ever reported as a backup.
- **P4 — pending is honest and durable.** An object that could not be promoted stays `PENDING`,
  survives a restart, and is listed by the repository's status output with its age.
- **P5 — an outage leaves a complete local copy.** When the primary is unavailable, the pipeline
  ends the step with a complete, verified, resumable local copy and state `PENDING`. If a spool is
  configured and usable, the copy is in the spool under the spool's bounds; if the spool is not
  configured, not reachable or full, the object stays where it is in the workspace, still `PENDING`.
  **A configured but unreachable spool deletes nothing and marks nothing as done.**
- **P6 — the spool answers unavailability only.** A content refusal is never spooled.
- **P7 — drain verifies before it retires.** Replaying a pending object promotes it by the same
  promotion function, verifies the object on the primary (P2), and only then may release the
  spool's copy. A drain that cannot verify releases nothing.
- **P8 — every step is idempotent.** Repeating a promotion, a spooling or a drain after any
  interruption completes it or leaves it as it was. It never produces a second, different object,
  never a false `PRESERVED`, and never loses the only copy. The interruption points between
  workspace, spool and primary are tested.
- **P9 — receipts and evidence lie beside the payload, never in it.** A record the preservation
  layer writes about an object is not added to, and does not replace, any file of the object.

The decision table of P1–P7 is `conformance/CASES.json`, `preservation_outcome`.

## 8. Retention and cleanup

- **R1 — a class is not a licence.** That bytes are classified as runtime, cache, workspace or
  regenerable does not by itself permit their deletion.
- **R2 — sole copies and pending objects are protected, wherever they lie.** Before anything is
  removed, the remover establishes that the bytes are not the only copy of something that is not
  regenerable and not a `PENDING` object. In the workspace as everywhere else. What cannot be
  established is treated as protected.
- **R3 — preserved material is deleted only by a separately decided, recorded path** (a gate, a
  tombstone, a decision record). Nothing is deleted by age, and no preservation or spool code has
  a general deletion function; the one removal a spool performs is its own copy after P7.
- **R4 — an object named by a frozen release is on hold** for as long as the release exists
  (`crosscorpus-release/v1` §6.3).
- **R5 — protection that is configured is not protection that exists.** A retention class or a
  backup-required flag is a statement of intent; §9 says when a backup exists.

The decision table is `conformance/CASES.json`, `cleanup`.

## 9. Backup

- **B1 — a backup is a copy that exists and was verified.** A holding is `BACKUP_VERIFIED` only
  when a secondary copy is physically present on the `BACKUP` root, was produced **from the
  primary**, and was verified against the primary's inventory (every object: path, size, digest).
  A configured backup root, a backup-required class, a scheduled job or a manifest of what should
  be copied is none of that.
- **B2 — not on the primary's volume.** S3 applies. Two directories of one volume are one copy for
  every failure of that volume.
- **B3 — the limits of independence are stated.** Different volumes are the only independence this
  contract can check mechanically. Whether two volumes share a device, an enclosure, a host, a
  building, a power supply, an administrator or a ransomware blast radius cannot be determined
  from a path and **is not claimed**. A status output that reports a verified backup reports
  "different volume; further independence not determined" unless a recorded statement says more.
- **B4 — a sync is not a restore.** A synchronisation client's report that it uploaded a file is
  evidence that a server accepted it, not that the copy can be read back. Only a read-back and
  re-hash from the secondary demonstrates restorability.
- **B5 — a backup order is closed by a copy receipt**, never by a classification. Each repository
  keeps such orders (CO.RA.PAN: D39) separate from protection classes.
- **B6 — a role is not conferred by renaming.** A former primary does not become a backup by being
  renamed or re-declared. A backup is produced from the authoritative primary and verified against
  it (§11.2, step 9).

The decision table is `conformance/CASES.json`, `backup_status`.

## 10. Identity independent of the root

- **D1** Persistent identifiers of objects, documents, exports and releases, and every digest of a
  payload, are functions of content and of stable keys. **No root, drive, mount, host or absolute
  path enters an identifier or a payload digest.**
- **D2** A persisted reference to a location is a role (or named root) plus a **relative** path in
  POSIX form. A physical path exists only after resolution on one machine.
- **D3** Moving a holding to another physical root changes **no** object id, **no** release id and
  **no** payload digest. After a verified move the same references resolve to the same bytes; this
  is tested by reading preserved objects from a second root after a verified copy, with the first
  root gone.
- **D4** A record that was written with an absolute path before this rule is history: it is read,
  never rewritten.

## 11. Safe migration to another root

A change of the physical root of a holding's primary — in particular the move of both projects to
the institutional file system — follows one procedure, parameterised per project and per holding.
It has a **read-only planning part** and a **mutating part**; tools keep them apart, and the
mutating part runs only on an operator's explicit order naming the plan.

### 11.1 Preconditions

- The new root **exists** and is configured on the machine. Until then it is `PLANNED`: not in any
  configuration, not created, not probed.
- The target's file system is qualified **itself**. A qualification of a local disk says nothing
  about a network file system, and the reverse.

### 11.2 The procedure

| # | Step | Kind | Gate |
|---|---|---|---|
| 1 | **Inventory and fixity of the source**: every object with relative path, size and digest; every object re-hashed against its recorded digest | read-only | the source verifies completely; what does not is listed and decided before anything is copied |
| 2 | **Quiescence** (§11.3) | operational | no writer can change the source |
| 3 | **Verified copy** to the new root, into a location that is not yet the primary | mutating (target only) | — |
| 4 | **Target identity and readiness**: the new root gets its identity; usable, writable, space | mutating (target only) | readiness passes |
| 5 | **Crash and concurrency qualification** of the promotion mechanism **on the new file system** | mutating (probe area only) | passes on that file system |
| 6 | **Target verification**: the inventory of the copy, re-read from the target, equals the source inventory of step 1 — same paths, sizes, digests, nothing extra | read-only | equal |
| 7 | **Closing reconciliation** (§11.3): a second source inventory equals the first | read-only | equal; otherwise the difference is copied and steps 6–7 repeat |
| 8 | **Controlled cutover**: the machine configuration is pointed at the new root; pending objects are replayed; a sample is read back through the normal read path | mutating (configuration) | replay and read-back succeed; the old root is **not** changed |
| 9 | **The new root is the primary.** A `BACKUP` is then produced **from the new primary** onto the secondary root and verified against it | mutating (backup root only) | B1 |
| 10 | The former primary is retained until an operator decision releases it. Its release is a deletion under R3 | — | separate decision |

### 11.3 Writers during the copy

An inventory is a statement about one moment. It does not protect against a writer.

- **Preferred: a lock.** The procedure holds the repository's writer lock (or stops the writers it
  names) from step 2 to step 8. While the lock is held nothing is promoted; what arrives is
  `PENDING` (P5) and is replayed in step 8.
- **Where a lock cannot be held for the duration** (a long copy), the copy may run while writers
  work, **and then** a quiescent phase is entered for the closing reconciliation of step 7: with
  the writers stopped, the source is inventoried again; every object that is new or different is
  copied and verified; the reconciliation is repeated until two successive inventories are equal.
- A cutover without a lock **and** without an equal closing reconciliation is not a cutover under
  this contract.

### 11.4 What a migration never does

It never deletes or rewrites the source; never renames a root into another role (B6); never
changes an identifier or a payload digest (§10); never reports the new root as primary before
step 8, or a backup before step 9.

## 12. One contract, two repositories

- **One canonical home.** The bundle is edited only in CO.RA.PAN,
  `contracts/crosscorpus-storage-v1/`. CO.PRE.PAN holds a verbatim copy at the same relative path
  and never edits it.
- **Each repository pins the bundle digest** in its tracked pin file and its test suite
  recomputes the digest of its copy and fails on any difference. This check needs no neighbouring
  checkout.
- **Each repository implements the decision functions itself** (`role_separation`, `namespace`,
  `configuration_state`, `preservation_outcome`, `cleanup`, `backup_status`) and reproduces every
  case of `conformance/CASES.json`; and each has tests that exercise **its real code paths**
  against the invariants (an outage through the real pipeline entry, drain and read-back, the
  interruption points, sole-copy protection, a root change). The decision functions are used by
  the real resolvers and status outputs, not kept beside them.
- **A joint check** runs when both checkouts are present: both pins equal, both bundle copies
  byte-identical, and S4 over the two machines' configured roots.
- **In force** means: both pin files hold the same digest with status `IN_FORCE`, both conformance
  suites pass, and each project has a decision record quoting the digest. A change to the bundle
  is made in the canonical home, changes the digest, and is taken by the other repository in one
  commit that runs its suite.
- A later version that changes the meaning of a state, a code or an invariant is `v2`.

## 13. Closed vocabularies

Roles: `REPO` `RUNTIME` `SPOOL` `PRESERVATION` `BACKUP` `DISTRIBUTION` `EXCHANGE`.
Holdings: `PRODUCTION` `HISTORIC`.
Configuration states: `NOT_DECLARED` `NOT_CONFIGURED` `DEFAULTED` `UNUSABLE` `UNREACHABLE` `READ_ONLY` `AVAILABLE`.
Separation codes: `ROLE_SHARED` `ROLE_NESTED` `BACKUP_NOT_INDEPENDENT` `VOLUME_UNKNOWN` `FOREIGN_CORPUS_OVERLAP`.
Object states: `PRESERVED` `PENDING` `REFUSED`.
Pending locations: `SPOOL` `WORKSPACE`.
Cleanup verdicts: `PROTECTED` `REMOVABLE`.
Backup states: `NOT_CONFIGURED` `CONFIGURED_NO_COPY` `COPY_UNVERIFIED` `NOT_INDEPENDENT` `INDEPENDENCE_UNKNOWN` `BACKUP_VERIFIED`.

## 14. Not decided here

The location, quota and backup semantics of the institutional file system; distribution and
exchange roots; licences and access; retention periods; the cold-archive question; any scientific
population or release. Each is named in the repositories' own open-decision lists.
