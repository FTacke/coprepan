# CPD-0010 — Evidence classes: chained primary evidence, anchored heads, and identity as rebuildable derived state

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the evidence-table integrity closure (2026-10-08), which authorised the direction recommended by the adversarial audit: chain the evidence tables, treat the identity tables as deterministically rebuildable, no blanket integrity layer. Recorded by that run; subject to the operator's review. |
| Kind | architecture |
| Scope | which stores are primary evidence, which are derived, which are views; how primary evidence is protected against unnoticed change; how derived state is checked and restored |
| Builds on / amends / supersedes | builds on CPD-0009 and settles its "Not decided here" point on integrity protection of the other tables. Extends CPD-0009 §5 (the chained ledger) to the other primary-evidence tables. Supersedes, forward-only and before any corpus row existed, the row schemas of the request log, discovery inputs and events, candidate qualifications, admission labels (`v1` → `v2`) and of the run result (`v1` → `v2`). |
| Does not change | any id, the fetch record, the pack, the preservation manifest, the layer store, the ledger format of CPD-0009, any gate |
| Run report | [`docs/agent-runs/2026-10-08_evidence-table-integrity-closure.md`](../agent-runs/2026-10-08_evidence-table-integrity-closure.md) |
| Evidence | measurements of single changed bits per table before and after (run report §2, §8); `tests/test_evidence_integrity.py`; the reading of every writer of a JSON-lines table (run report §2) |

Validation debt: as in CPD-0009 — one workstation, local disk, temporary directories, a loopback
server, no power failure, no real preservation target.

## Context

CPD-0009 chained the ledger and listed the rest as open: single changed bits in a request-log,
discovery or identity file were mostly not noticed. Measured on the code as it stood after that
decision (40 random single-bit changes per file, a workspace diagnosis afterwards; run report §2):

| File | Not noticed |
|---|---|
| request log, discovery inputs, discovery events, candidates, admission labels | 40 of 40 |
| candidate qualifications | 39 of 40 |
| identity: documents / observations / versions / relations | 15 / 22 / 4–6 / 22 of 40 |

Not every one of these files has the same standing. Some record what happened and cannot be
recomputed; some are a function of other records and can be.

## Decision

### 1. Evidence classes

| Class | Meaning | Protection |
|---|---|---|
| **`PRIMARY_EVIDENCE`** | a record of an observation or a decision that no other record lets one re-derive, or that re-derivation could not reproduce once rules, code or the world have moved on | **cryptographically chained** (§2), anchored at run close (§3) |
| **`DERIVED_REBUILDABLE`** | a deterministic function of primary evidence (and, where stated, of configuration) | **checked against** the evidence; **rebuildable** from it; never an authority of its own |
| **`CACHE/VIEW`** | a convenience reading | no evidentiary authority; may be thrown away |

Classification of the stores — by what each row records, not by its file name:

| Store | Class | Why |
|---|---|---|
| fetch record, WARC pack, preservation master and manifest | `PRIMARY_EVIDENCE` | the bytes and what was asked; protected by SHA-256 over the content (CPD-0005, CPD-0009) |
| preservation ledger | `PRIMARY_EVIDENCE` | states cannot be re-derived from bytes; chained (CPD-0009 §5) |
| **request log** | `PRIMARY_EVIDENCE` | holds the *intent* of a request, which exists nowhere else, and the policy decision of requests that were refused and have no fetch record |
| **discovery inputs** | `PRIMARY_EVIDENCE` | an input that the gate refused has no fetch and no preserved bytes: the row is the only record |
| **discovery events** | `PRIMARY_EVIDENCE` | an observation of what a channel document listed, under a parser version; a parser change does not reproduce the old observation |
| **candidate qualifications** | `PRIMARY_EVIDENCE` | a decision under a rule set; a new rule set is a new decision *beside* the old, whose rules may no longer be in the code |
| **admission labels** | `PRIMARY_EVIDENCE` | the same: a label under a rule set, kept when a later rule set labels again |
| **discovery candidates** | `DERIVED_REBUILDABLE` | each row is a function of the first event that listed it, or of the request-log row of a permanent redirect (§4) |
| **identity: documents, observations, versions, relations** | `DERIVED_REBUILDABLE` | a function of preserved fetch records and bodies, the ledger, the outlet's URL rules and the extraction (§5) |
| extraction layers | `DERIVED_REBUILDABLE` | a function of a preserved body and an extractor version; write-once and verified on read (CPD-0005) |
| pack indexes, preservation-area listings, channel health, the candidate lifecycle, the fetch plan | `CACHE/VIEW` | computed when read from the stores above |

No store was left unclassified. The only store holding both kinds of statement is the candidate
table, and it holds nothing that is not derivable: its two creation paths are both reproduced by
the derivation of §4.

### 2. Chained tables (`previous_row_sha256`)

Each row of a `PRIMARY_EVIDENCE` table carries `previous_row_sha256`: the SHA-256 of the line
before it (`null` for the first). The table writer (`jsonl.append_chained`) takes the line it
chains to under the append lock, so two appenders cannot build on one predecessor.

- A changed, removed, inserted, duplicated or reordered row breaks the chain at the row after it.
  A reader refuses the table (`ChainBroken`); it never "repairs" a chained table.
- An **incomplete last line** is not a break. It is a torn tail (`TornTail`), the complete rows
  before it still authenticate each other, `recovery.repair` moves it aside, and appending
  continues from the last complete row. A crash and a manipulation are therefore told apart by
  construction: the former leaves an incomplete line, the latter a complete line that does not fit.
- Row schemas: `coprepan-request-log/v2`, `coprepan-discovery-input/v2`,
  `coprepan-discovery-event/v2`, `coprepan-candidate-qualification/v2`,
  `coprepan-admission-label/v2`. A `v1` row is refused by a `v2` reader and the reverse; a `v2`
  row without the chain field is not `v2`. No `v1` row of corpus material exists.
- A run refuses to start when the request log or a discovery table does not authenticate, before
  the first request is made.

### 3. Anchoring the newest row

A chain leaves the newest row unvouched until the next append. When a run closes, its result
(`coprepan-acquisition-run-result/v2`) records, for the ledger and every chained table, the number
of rows and the hash of the last line (`evidence_heads`). `recovery.diagnose` checks every closed
run's heads against the tables: a table that is shorter than it was, or whose row at the recorded
position is another row, is `DAMAGED`. From a clean close on, every row is covered. Not covered:
rows appended after the last close (for instance labels written after a run has ended), until the
next close.

### 4. Candidates: derived, checked, completed — never judged

`discovery.candidate_from_event` is the whole derivation of an event-created candidate, used both
when a candidate is created and when the table is checked; a redirect-created candidate is derived
from the request-log row that carries `moved_permanently_to`. `candidate_consistency` reports
rows that are **missing**, **unsupported** or **different**. `complete_candidates` appends the
missing ones, under the writer lock, and nothing else. Unsupported or different rows are
`DAMAGED` and left for a person.

### 5. Identity: preserved evidence → tables, rebuilt and compared

Inputs, and only these: the verified packs on the preservation root (pack and index manifests both
present, masters hashing correctly); the ledger (`RAW_PRESERVED` fetches only); the outlet URL rules
of the registry; the extraction of each body (a stored layer that verifies, otherwise derived again
in memory and stored nowhere). No network; no write to anything preserved or to any layer.

- **Canonical order**: packs by id, fetches in index order. The tables are *defined* as the
  derivation in that order; it is also the order in which they are produced when packs are
  identified day by day.
- `identity_rebuild.verify` rebuilds into a temporary directory and compares. Rows are compared
  regardless of file order; `first_fetch_id` is compared as a statement ("one of the fetches that
  observed the document") because it depends on the order of identification; relations are
  compared exactly. Result:

  | Status | Meaning | `diagnose` class |
  |---|---|---|
  | `CORRECT` (`exact` when the bytes are equal) | the existing tables are what the evidence gives | `CLEAN` |
  | `REBUILDABLE` | absent, a strict subset, or unreadable; nothing contradicts the evidence | `INCOMPLETE_RESUMABLE`; `NEEDS_REPAIR` when unreadable |
  | `CONFLICTING` | a row the evidence does not support, or another row where it gives one | `DAMAGED` |
  | `SOURCE_EVIDENCE_DAMAGED` | the evidence for the rebuild does not verify, or the ledger records preserved fetches that the root does not hold completely | `DAMAGED`; nothing is rebuilt |

- `identity_rebuild.adopt` makes the tables the rebuild: it builds into `identity.rebuild-<id>`,
  moves the existing directory aside to `identity.replaced-<n>` (never deleting it) and renames
  the rebuild into place, under the writer lock. It refuses on `SOURCE_EVIDENCE_DAMAGED`; it
  refuses on `CONFLICTING` unless asked (`replace_conflicting`), because a conflicting row is
  either a defect to look at or a manipulation. A store built in another order than the canonical
  one may differ in relations; it is reported, not accepted.
- A fetch the ledger does not (yet) record as `RAW_PRESERVED` is outside the rebuild: it is not
  damage, it is not preserved yet.

### 6. Diagnosis

`recovery.diagnose` now also: authenticates every chained table (a break is `DAMAGED`, a torn tail
`NEEDS_REPAIR`); checks the heads of closed runs; checks candidates against the evidence; and, when
given the registry and the preservation root, holds the identity tables against a rebuild. It does
not raise on damaged content of any of these.

## Alternatives considered

| Alternative | Why not |
|---|---|
| chain every JSON-lines file | the identity tables and candidates are derivable; chaining them makes a second ledger whose loss cannot be repaired by derivation |
| leave qualifications and labels unchained as "derived" | their old-ruleset rows cannot be reproduced once rules or code change; they are the only record of what was decided |
| treat the identity tables as primary and chain them | a damaged chained table is refused for good; a derived table can be rebuilt from the preserved evidence |
| rebuild identity by re-running the pipeline into the same directory | the existing store is exactly what is being checked; a rebuild must not read it |
| put the rebuild's result into the layer store | adds artefacts to historical layers; the rebuild is read-only on layers |
| compare `first_fetch_id` as a value | it depends on the order of identification; a different but valid order would be reported as damage |
| ignore `first_fetch_id` in the comparison | measured: a changed bit in it was then not noticed (8 of 40) |
| compare relations only as unordered pairs | existence and direction of `moved_to` / `duplicate_of` depend on order, but a wrong relation cannot be told from an order effect; exact comparison fails closed |
| replace conflicting identity tables automatically | a conflicting row is a signal; replacing it silently hides a defect or a manipulation |
| anchor heads in a separate file | a second file to protect; the run result is written once, whole or absent, and read by the run machinery anyway |
| anchor heads after every append | doubles the write cost and moves the problem to the anchor |
| keep `v1` row schemas and add the field | an old row would be read as new; versions must not be mistaken for each other |

## Consequences

- A change to evidence is noticed, wherever in the table it is — except in rows appended after the
  last closed run.
- A damaged derived table is not a loss: it is rebuilt from the preserved evidence, or the
  evidence is named as damaged.
- Row schemas of six stores changed before any corpus row existed. From the first real fetch a
  further change is a migration.
- A run start reads the request log and discovery tables once, and every closing run reads each
  chained table once; both are linear in size and cost, measured, a few hundredths of a second per
  few megabytes.
- `recovery.diagnose` with the registry and the root rebuilds the identity tables: its cost is that
  of reading the preserved packs.

## Not decided here

- Anchoring rows written after the last run close (labels written later, for instance) before the
  next close.
- A whole-workspace manifest: hashes of tables that are neither chained nor derivable (run records,
  pack manifests, preservation manifests, the descriptive fields in them) — their single-bit
  coverage is in the run report.
- A rebuild of the layer store, of the candidates by full re-discovery from preserved channel
  documents, or of the ledger — the latter is primary evidence.
- Multi-pack identity rebuilds in an order other than the canonical one.
- Behaviour after a power failure; other file systems; the runtime workspace on a share.
