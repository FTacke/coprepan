# Storage, Preservation and Provenance — component index

**Status: NORMATIVE TARGET — IMPLEMENTED ON TEMPORARY DIRECTORIES ONLY.** Root resolution,
promotion, the outage spool, the state machine with its ledger, the layer store (§13) and — since
CPD-0005 — the fetch record and the sealed WARC pack with its promotion
([acquisition index](../acquisition/INDEX.md)) exist as tested code. **No fixity schedule, no
reconciliation and no backup exist; no storage root is configured; nothing has been preserved
for the corpus; nothing has run against a real target.** Governing decisions:
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §3 and
[CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) §3.
Current state: [`docs/STATUS.md`](../STATUS.md).

This is the single entry point for: what a preservable source object is, how it is contained and
promoted, the preservation state machine, storage roles and classes, retention, fixity, backup,
capacity, and the provenance chain.

---

## 1. Principle: preservation-first

> The primary raw object of COPREPAN 3.0 is a **reconstructable fetch**, not the extracted article
> text. Extraction, normalisation and NLP are derived layers. **No derived layer may be the only
> copy of a source.**

The legacy system kept no HTML, no HTTP status, no headers and no final URL for any of its 64,932
article rows; no text can be re-extracted, verified or repaired, and its two systematic extraction
defects are permanent (audit T-1 to T-4). That is the failure this component exists to prevent.

`ACQUIRE ≠ PROCESS ≠ ADMIT`: acquiring bytes, processing them and admitting a text to a release
are three separate acts with separate state.

## 2. The fetch record

The minimal preservable unit is the **fetch record**, not the article.

| Component | Content | Tier |
|---|---|---|
| request | requested URL, method, the request headers that matter (user agent, conditional headers), reference to the discovery event | required |
| response envelope | status, final URL, redirect chain, response headers, fetch start and end as UTC instants | required |
| body | the **exact response bytes**, identified by `sha256` | required |
| policy context | robots decision and the robots.txt version consulted; access class observed (`open` / `metered` / `paywalled`); crawler version; policy version | required |
| discovery provenance | the channel document (feed or sitemap bytes) the URL was found in, itself preserved | required |
| rendered DOM, screenshot | only for outlets qualified as needing rendering | optional tier, later decision |
| linked media (images, video) | not preserved | out of scope |
| PDFs (e-paper) | not acquired in the foundation | later decision |

The body is stored as received: no transcoding, no charset repair, no decompression-recompression
that changes the identified bytes. Decoding is a recorded step of extraction.

## 3. Container: sealed WARC packs

Target container (decided as the direction; no technical contradiction was found against the
CO.RA.PAN 3.0 storage contract, which is container-agnostic — its promotion unit is "a file with a
stable identity and a manifest"):

- Bodies and their request/response records are written into **WARC packs** (one gzip member per
  record), **one pack per outlet and UTC day**, with a line-oriented index (fetch id, URL, body
  hash, pack, offset).
- A pack is appended to in the runtime workspace, then **sealed**: pack hash computed, manifest
  written. A sealed pack is never modified.
- The sealed pack is the **promotion unit** (§5). Only after verified promotion are its fetch
  records `RAW_PRESERVED`.
- Channel documents are preserved in the same way.

Why WARC: it is the standard web-archive container and keeps request, headers and body together;
packing avoids millions of small files on a network share; a sealed pack is a natural unit for
promotion, fixity and retention.

Open design points for the Phase-2 implementation (to be settled by measurement and recorded in a
decision, not assumed here): the WARC library and its pin, the compression codec, the index format,
maximum pack size and rollover, how a manifest references records. **No WARC pipeline is
implemented.**

## 4. Preservation state machine

```text
DISCOVERED → FETCH_PLANNED → FETCHED → RAW_VERIFIED → PRESERVATION_PENDING → RAW_PRESERVED
                    │
                    ├─ FETCH_FAILED(reason, retry_at)
                    ├─ REFUSED_BY_POLICY(reason)
                    └─ QUARANTINED(reason)
```

- Every transition is appended to a ledger **before** the state changes. An illegal transition
  raises.
- `PRESERVATION_PENDING` is **not** preserved. A hash disagreement means the object does not become
  `RAW_PRESERVED`.
- Extraction may only read `RAW_PRESERVED` objects.
- States are named tokens. The legacy system had seven free-text statuses in its data and five in
  its model comment.

## 5. Storage roles and root resolution

Roles (adapted from CO.RA.PAN 3.0; one role per function, never mixed):

| Role | Holds | Root |
|---|---|---|
| `REPOSITORY` | code, configuration, documentation, small fixtures, compact hash-bound evidence records. **No corpus data, no runtime state.** | the checkout |
| `RUNTIME` | open packs, ledgers in flight, frontier, caches, scratch, working layer store | `COPREPAN_WORKSPACE_ROOT` |
| `PRESERVATION` | sealed packs, manifests, tombstones, release bundles. Durable and authoritative; not a working area. | `COPREPAN_PRESERVATION_ROOT` |
| `SPOOL` | bounded local write-ahead buffer for preservation outages. Not a second archive. | `COPREPAN_SPOOL_ROOT` |
| `DISTRIBUTION` | read-only publication copy of releases. Not a source of truth. | `COPREPAN_DISTRIBUTION_ROOT` |
| `EXCHANGE` | temporary hand-over zone. Not an archive. | `COPREPAN_EXCHANGE_ROOT` |
| `BACKUP` | a second physical copy with its own verification states; never on the primary's volume | `COPREPAN_BACKUP_ROOT` — NOT_CONFIGURED |

Deliberate difference from CO.RA.PAN 3.0: there the runtime workspace was separated from the
checkout late (its D85/D87), and an unset workspace variable still means "historical in-checkout
locations". COPREPAN 3.0 starts with the separation: **an unset root is a refusal**, there is no
in-checkout fallback, and there is nothing to migrate later.

Resolution rules:

- Roots are resolved from the environment; tracked configuration
  ([`config/storage_targets.yml`](../../config/storage_targets.yml)) holds logical roles and
  `${ENV}` references only. Concrete paths live in a gitignored `.env` or
  `config/storage_targets.local.yml`.
- **Fail closed.** Not configured → refusal. Configured but unreachable → refusal *before any byte
  moves*. Read-only → refusal. No default, no guess, **no fallback to local disk or to the
  checkout**.
- **An unreachable target is never reported as empty.** Its usage is unknown, not zero.
- No drive letter, UNC path or home directory in tracked domain logic or configuration. A test
  enforces it (`tests/test_repository_contract.py`).
- **Roles are kept apart by code, not by habit** (CPD-0014): `validate_role_separation` refuses two roles on one root or one inside another (the checkout included), and a `BACKUP` on the volume of `PRESERVATION`. A role that is not configured is `None`, not a default (`resolve_configured_roles`).
- The machine values live in the gitignored `.env`, read for `COPREPAN_*` names only; the process environment wins (`workstation_environment`).
- **Same function = same logical name on every target.** Logical area names are English, lower
  case, ASCII; no historical synonym for a data class that already has a name.

## 6. Promotion semantics

Taken over from CO.RA.PAN 3.0 unchanged in meaning (there keyed on a recording, here on a pack):

```text
sealed pack → validate → stable identity → sha256 → manifest → verified immutable master
```

- **Atomic:** copy to a `.part-<hex>` name in the destination directory, hash *the landed bytes*,
  then atomic rename. A `.part-*` file is never a master.
- **Idempotent:** a completed promotion re-verifies and writes nothing.
- **Repairing:** a manifest whose master is missing or mismatched is re-promoted and reported as
  repaired.
- **Identity conflict** (same identity, different content) is a hard refusal, never resolved
  automatically and never by deleting.
- **Duplicate** (same bytes under another identity) is recorded, not copied twice.
- **Outage spool:** if the preservation target is unreachable, a verified local copy is spooled
  and the object is `PRESERVATION_PENDING`; on return the same promotion function runs. The spool
  is bounded (free space that must remain; ceiling on spool size). A *content* refusal is never
  rerouted into the spool: spooling answers unavailability only. A crawler must not stall on a
  share outage, and must not pretend to have preserved.
- **No delete function.** The preservation code has no deletion path, enabled or disabled; a
  structural test asserts the absence.

## 7. Storage classes, retention, deletion

Classes (adapted from the CO.RA.PAN 3.0 retention policy; audio-specific classes dropped):

| Class | Content | Default |
|---|---|---|
| `acquisition_source` | sealed packs, channel documents | `retain_until_freeze`; deletion gated |
| `corpus_text_annotation` | extraction, normalisation, NLP, enrichment and release layers | regenerable by version; released layers permanent with the release |
| `provenance_manifest` | manifests, ledgers, identity tables, tombstones | permanent |
| `frozen_evidence` | gold sets, freeze inventories, completed review files, frozen predictions, evaluation results | permanent, immutable |
| `processing_workspace` | open packs, scratch, working stores | transient |
| `model_cache` | installed models | transient, reinstallable |
| `operational_log` | logs | transient |
| `unclassified` | anything not yet classified | **never cleanup-eligible** |

A file is `frozen_evidence` when a completed human decision, a freeze manifest or a published
evaluation result is bound to *those exact bytes* and could not be re-derived without them.

Retention rules:

- **Nothing is deleted by age.** Age is not a gate. An unknown never satisfies a gate.
  The present reachability of a source URL is never a reason to delete a preserved copy — link rot
  is why the copy exists.
- The default source retention must never be the destructive one.
- After a corpus release, packs holding only non-admitted fetches (galleries, home pages, binaries)
  *may* become delete-eligible through an explicit gate mechanism, with a **tombstone written while
  the bytes are still present** (identity, hash, size, reason from a closed vocabulary, decided by,
  decided at, policy version). This is the only controlled way to drop redundant raw material.
- **Named by a frozen release is a hold** (added 2026-10-08, CPD-0011; joint release contract
  §6.3). An export that any frozen release names is never deleted, overwritten or rewritten for as
  long as that release exists; neither is a pack holding a fetch such an export names as a source.
  The delete-eligibility of the rule above therefore applies only to packs that no export of a
  frozen release refers to. No retention code exists; this rule binds whatever is built.
- Derived layers are regenerable and may be pruned by version under a recorded decision.
- How long raw third-party copies may be retained at all is part of the open acquisition policy
  (master plan §13, O-1).

## 8. Fixity and backup

- Pack hashes are re-verified on a schedule and before every release. Reconciliation can rebuild
  the ledger from the target manifests.
- Backup carries digest-bound verification states: local copy verified, remote sync confirmed,
  remote restore verified. **A copy that cannot be verified is not a backup**; a refreshed backup
  does not inherit an old confirmation.
- A **restore test** is part of the Phase-2 gate.

## 9. Provenance chain

```text
outlet → channel → discovery event → fetch → preserved source object → extraction →
normalisation → NLP → enrichment → release record
```

For any released text, the following must be answerable **from stored records alone**: which
outlet under which registry version; which URL, found when, in which channel document; fetched
when, with which status, final URL and headers; which bytes (hash) in which pack; which extractor
and version with which block decisions; which normalisation operations; which annotator, model and
model version; which enrichments under which version; which release and selection policy admitted
it.

Identity model (five identities, canonical URL key, duplicates):
[`docs/architecture/TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md) §6 and
[`docs/architecture/TERMINOLOGY_AND_NAMING.md`](../architecture/TERMINOLOGY_AND_NAMING.md) §5.

## 10. Capacity

**Raw HTML volume is not measured** — the legacy system kept none. The only figures are scenario
assumptions from the audit (§8.5), reproduced here with that label and not to be quoted as
estimates:

| Quantity | Label | Value |
|---|---|---|
| fetches per day (100 outlets × 150) | scenario assumption | 15,000 |
| compressed body size per fetch | scenario assumption | 50 KB (range considered: 20–100 KB) |
| raw volume per year | derived from the assumptions | about 270 GB (110–550 GB) |
| free space on the CO.RA.PAN preservation share, 2026-10-05 | measured there, reported by the audit | 177.62 GiB, quota mode `SHARED`, 100 GiB reserve floor |

Consequence: under any scenario row, COPREPAN raw preservation does not fit beside CO.RA.PAN on
that share for a year. **The preservation target and its capacity are a precondition for
production crawling** (master plan §13, O-3, O-4). The Phase-2 canary must measure bytes per fetch
before any capacity figure is trusted. Capacity models distinguish `measured` rates from
`configured_assumption` rates.

## 11. Open

| Item | Kind | Where |
|---|---|---|
| Preservation target (own allocation or shared with CO.RA.PAN) | institutional | master plan §13, O-3 |
| Storage capacity | institutional, then measured | master plan §13, O-4 |
| Retention period for raw third-party copies; who may access them | institutional / legal | master plan §13, O-1 |
| Durable location (role) of the non-released layer store | technical, Phase 1 — **still open**: the store takes any directory | master plan §11 |
| WARC library, codec, index format, pack rollover | **partly settled 2026-10-07 by CPD-0005 §3**: own standard-library writer (`pack-writer/1`), gzip per record, index derived at seal time and bound by the manifest. Read by warcio 1.7.5 for the written subset (§14). Still open: other tools, another codec, rollover by size, `revisit` records | this document §3, §14 |
| Wire bytes or transfer-decoded bytes as the stored body | **settled 2026-10-07 by CPD-0006 §1.2**: the payload with its content coding, without transfer coding | CPD-0006 |
| Scheduled fixity re-verification; reconciliation of the ledger from the target manifests | technical, Phase 2 — today: `pack.verify_sealed` and `preservation.verify_master` on demand | §8 |
| Reuse of the `corapan_playground` storage modules as a dependency | technical, Phase 1 — own code against the same on-disk conventions for now (§13); the consolidation question stays open | master plan §13, O-8 |
| Phase-1 gate on a **real** preservation target | needs O-3 | master plan §11 |
| Cross-process locking of ledger and layer store | technical; single writer assumed today | §13 |
| A content index for the duplicate check (today a linear scan of manifests) | technical, Phase 2 | §13 |

## 12. Milestones

- 2026-10-06 — principles and target design recorded (repository bootstrap). Nothing implemented.
- 2026-10-07 — Foundation Core I: the primitives of §13, tested on temporary directories only.
  Run report: [`docs/agent-runs/2026-10-07_foundation-core-i.md`](../agent-runs/2026-10-07_foundation-core-i.md).
- 2026-10-07 — CPD-0005: fetch record and sealed WARC pack decided and implemented; a pack and its
  index are promoted (areas `raw`, `raw_index`) and read back from the preservation root in the
  vertical canary — on temporary directories, with synthetic fixtures.
  Run report: [`docs/agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md`](../agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md).
- 2026-10-07 — CPD-0006: the stored body defined (payload with content coding, without transfer
  coding); pack interoperability checked with an independent reader (§14); preservation-target
  readiness check (§15) and capacity model (§16) built. No target chosen, no capacity measured.
  Run report: [`docs/agent-runs/2026-10-07_discovery-acquisition-readiness-offline-e2e.md`](../agent-runs/2026-10-07_discovery-acquisition-readiness-offline-e2e.md).

## 13. What exists (Foundation Core I)

Tested on temporary directories. None of it has run against a real storage root.

| Mechanism | Code | On-disk contract |
|---|---|---|
| Root resolution (§5) | `src/coprepan/storage_roots.py` | reads `config/storage_targets.yml`; refusals `StorageRootNotConfigured`, `StorageRootUnusable` (relative, filesystem root, inside the checkout), `StorageRootUnreachable`, `StorageRootReadOnly`; never creates a root; `.env` is read only on request |
| Promotion (§6) | `src/coprepan/preservation.py` | master `preservation/<area>/<relative path>`; manifest `preservation/manifests/<area>/<object id>.json`, schema `coprepan-preservation-manifest/v1`; staging `<name>.part-<hex>`; landed bytes re-hashed before the atomic rename; outcomes `promoted`, `already_preserved`, `repaired`, `duplicate_recorded`; refusals `HashMismatch`, `IdentityConflict` |
| Outage spool (§6) | `src/coprepan/outage_spool.py` | bytes `preservation/pending/<area>/<relative path>`; record `state/pending/<object id>.json`, schema `coprepan-preservation-spool/v1`; both bounds of `SpoolPolicy` are mandatory, no built-in size |
| State machine and ledger (§4) | `src/coprepan/ledger.py` | one JSON object per line, schema `coprepan-ledger-record/v2` *(v1 until 2026-10-08; CPD-0009 §5)*: each record names the SHA-256 of the record before it; appended under an append lock, flushed and read back before the state changes; state is the replay of the ledger; a torn last line is quarantined to `<name>.torn-<n>`, never dropped |
| Layer store | `src/coprepan/layer_store.py` | `<root>/<stage>/<fp[:2]>/<fingerprint>/<artifact id>/{payload, manifest.json, PROMOTED}`; fingerprint schema `coprepan-layer-fingerprint/v1`; artifact id `ar1-` + 32 hex |

Notes that bind later work:

- The promotion unit is "a sealed file with an identity". Since CPD-0005 §3 that is the sealed
  pack `pk1-<outlet_id>-<YYYYMMDD>-<nnn>` under `preservation/raw/<country_id>/<outlet_id>/`, with
  its index under `preservation/raw_index/…`; the promotion functions themselves stay generic.
- The state machine is the one of §4. One edge is implemented that the diagram does not draw:
  `FETCH_FAILED → FETCH_PLANNED`, the retry that `retry_at` implies. The fetch stage (Phase 2)
  confirms or corrects it.
- A duplicate (same bytes under another identity) gets a manifest with `duplicate_of` pointing at
  the holder's master; nothing is copied.
- The preservation module contains no deletion call at all (asserted structurally). The spool
  releases its own copy only after the promoted master has been re-read and verified.
- Staging name, hash-then-rename order and manifest rendering follow the CO.RA.PAN 3.0 storage
  code as read on 2026-10-07; the manifest *fields* are COPREPAN's own (a pack is not a recording).

## 14. Pack interoperability

**Claim, exactly:** packs written by `pack-writer/1` — the record subset it writes (`warcinfo`,
`response`, `metadata`; one gzip member per record) — are read by **warcio 1.7.5**
(`ArchiveIterator`, digest checking on): every record is found, typed and addressed as written;
every payload comes back byte for byte, including empty, binary and content-coded bodies;
SHA-256 block and payload digests are verified by the reader (a record with a wrong digest is
flagged). Tested on a synthetic pack and on the pack of the offline canary after promotion
(`tests/test_warc_interoperability.py`, `tests/test_offline_e2e.py`).

**Not claimed:** WARC conformance in general; behaviour with other tools (indexers, replay
systems); anything about record types the writer does not write.

Two findings, kept as tests:

- A `Transfer-Encoding` header rendered as received would make a reader de-chunk bytes that are
  not chunked. It is written as `X-Coprepan-Orig-Transfer-Encoding` in the pack; the fetch record
  keeps it as received (CPD-0006 §1.2).
- warcio reads a **truncated** pack without complaint and returns less. Interoperability is not
  fixity: a pack is trusted because its bytes hash to its manifest, and this repository's own
  scan refuses a torn tail.

## 15. Preservation-target readiness (O-3)

**Status 2026-10-08: an interim primary is configured and qualified (§19); the long-term target is not chosen.** Original text: no target was chosen and none configured; O-3 is an institutional decision. What exists is
the contract a target must meet and the check for it (`src/coprepan/preservation_target.py`,
CPD-0006 §7).

| Check | Passes when |
|---|---|
| `usable_root` | absolute, not a filesystem root, not inside the checkout |
| `reachable` | an existing directory; otherwise its content is *unknown*, not empty |
| `target_identity` | the marker `coprepan_preservation_target.json` exists and is readable — written once by `initialise_target` when the operator takes the target into service |
| `free_space` | free bytes known and at least the required amount (an input, no default) |
| `writable`, `atomic_promotion`, `no_silent_overwrite` | a probe file can be staged, flushed, hashed, renamed atomically and re-read; an exclusive create refuses an existing name |
| `long_names` | a 190-character file name can be created |
| `case_sensitivity` | information only |
| `fixity` | up to 50 held objects per area verify against their manifests |

The probe writes a few hundred bytes into `_readiness_probe/` and removes exactly those; it never
touches `preservation/`. A report is `READY` or `NOT_READY` with every check listed.

**For the operator, to close O-3:** choose the target; set `COPREPAN_PRESERVATION_ROOT` in the
workstation `.env`; run `initialise_target` once with a target id; run `check_readiness` with the
free space the capacity model calls for; then the second half of the Phase-1 gate (promotion,
idempotence, conflict and crash recovery on that target).

## 16. Capacity model (O-4)

`src/coprepan/capacity.py` (CPD-0006 §8): a calculator whose inputs are labelled `measured`,
`estimated` or `assumed` and whose outputs carry the weakest label beneath them.
`python -m coprepan.capacity --help` lists the nine inputs; none has a built-in value.

Evidence available on 2026-10-07:

| Quantity | Value | Label |
|---|---|---|
| legacy fetch rows, total | 64,932 over 23 distinct crawl days (2025-12-18 to 2026-06-15), 53 outlets with rows | measured, on a copy of the legacy database, 2026-10-07 |
| legacy fetch rows per active crawl day | median 3,112; mean 2,823; maximum 5,986 | measured, same |
| legacy fetch rows per outlet and crawl day | median 115; maximum 367 | measured, same |
| legacy extracted text per `ok` article | mean 2,854 characters, 467 words | measured, same — **extracted text, not page size** |
| legacy stores | `json_raw` 127.0 MB (949 files); `json_raw_extended` 40.1 MB; `json_annotated` 17.0 GB (926 files) | measured, file sizes, 2026-10-07 |
| pack overhead per fetch (WARC headers + fetch record, compressed) | about 1.3 KB | measured, on synthetic exchanges with four response headers; real responses carry more headers |
| extraction record against the page it was made from | 5.2 KB for a 2.3 KB page | measured, on one synthetic page; **not a rate for real pages** |
| index row, ledger and request-log rows per fetch | of the order of 0.4 KB and 3 KB | estimated, from the record formats |
| **stored (compressed) body bytes per fetched page** | **unknown** — the legacy system kept no page | the audit's scenario assumption of 50 KB (20–100 KB) is the only figure |
| fetches per day under a registered outlet set | unknown — no outlet is registered | — |

**O-4 cannot be closed from this evidence.** The one number that dominates every scenario, the
size of a real stored page, has never been measured, and the legacy rate describes 53 outlets
under a crawl loop that fetched each URL once. What is missing, exactly: *stored body bytes per
fetch and fetches per outlet-day, measured on real outlets* — the Phase-2 canary's job. Until then
any total is a scenario, and the calculator labels it so.
- 2026-10-07 — CPD-0007: a 304 answer is preserved as its own fetch (empty body, `revalidates`),
  written to the pack as an ordinary response record — a WARC `revisit` record stays open (§11).
  Legacy freeze manifest built (legacy index §5): a manifest, **not** a preserved copy; the copy
  and its restore check need O-3. Admission labels and candidate qualifications are further
  append-only tables of the runtime workspace, whose durable home is open like that of the
  identity tables.
  Run report: [`docs/agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md`](../agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md).
- 2026-10-08 — adversarial audit with real process kills and real concurrent processes
  (CPD-0009; §17). Repaired: lost appends between processes, conflicting promotions under one
  identity, conflicting layer answers, four unrecoverable interruption states, an unchained
  ledger. One writer per workspace is now enforced.
  Run report: [`docs/agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md`](../agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md).

## 17. Interruption, concurrency and integrity (CPD-0009)

**One writer per workspace.** Every operation that writes a workspace holds its writer lock
(`src/coprepan/exclusive.py`): an operating-system lock on `<workspace>/.writer.lock`, released by
the system when the process ends. A second process gets `WorkspaceBusy` at once. The file is
empty and permanent; whether the lock is held is not readable from the file.

**After an interruption** (`src/coprepan/recovery.py`):

| `diagnose` class | Meaning | Way on |
|---|---|---|
| `CLEAN` | nothing open | — |
| `INCOMPLETE_RESUMABLE` | a step did not finish: an unsealed pack, a sealed pack without manifest, a promotion without its last transition, a run without a result, a request planned and never ended | run the step again |
| `NEEDS_REPAIR` | an append-only file ends in an incomplete record: ledger, a table, an open pack | `repair`, then run the step again |
| `DAMAGED` | lost evidence, a master or layer that does not verify, contradicting rows, a record that is not the one its id names | a person; nothing is changed automatically |

`repair` moves a torn tail into `<name>.torn-<n>` beside the file. It rewrites, invents and
deletes nothing.

**What is left behind and never read as data:** `*.part-<hex>` (an interrupted staged write),
`layers/.staging/<hex>` (an abandoned or withdrawn layer write), `*.torn-<n>` (a torn tail).
Nothing collects them; `diagnose` counts them.

**What is hashed and what is not** (single changed bits, measured 2026-10-08 on the canary
workspace, 40 per file; "noticed" = `diagnose` does not say `CLEAN`):

| File | Noticed |
|---|---|
| preserved masters; workspace pack; pack index; layer payload; layer manifest; ledger; run record | 40 of 40 in every file |
| layer marker | 199 of 200 |
| run result | 30 of 40 |
| pack manifest (`.pack.json`) | 27 of 40 |
| preservation manifests | 51 of 80 |
| identity tables | 88 of 160 |

The unnoticed changes are in fields no digest covers: descriptive fields of manifests, and whole
rows of tables that are derived (identity) or evidence without a chain (request log, discovery).
*Closed for the evidence and the derived tables by CPD-0010; see "Evidence classes" below.* What
remains is the descriptive fields of the manifests and of the run result.

**Cost of the checks** (measured 2026-10-08, one workstation, local disk; diagnostic only):
ledger append 4.1 ms, rebuild of 5,000 records 0.02 s; a pack of 1,500 fetches / 56.8 MB:
scan 0.5 s, seal 1.0 s, fixity check 0.5 s; layer store 5 ms per write, 12 ms per verified read;
`diagnose` of the canary workspace 0.02 s; the legacy freeze manifest over 18.8 GB: 143 s
(previous run). None of these is a reason to switch a check off.

**Not covered:** power failure (data the system had not written out), directory durability, a
runtime workspace on a network share, any file system but the one tested.
- 2026-10-08 — evidence classes, chained primary evidence, rebuildable identity (CPD-0010;
  §18). Run report: [`docs/agent-runs/2026-10-08_evidence-table-integrity-closure.md`](../agent-runs/2026-10-08_evidence-table-integrity-closure.md).

## 18. Evidence classes (CPD-0010)

| Class | Stores | Protection |
|---|---|---|
| `PRIMARY_EVIDENCE` | fetch records and packs, preservation masters and manifests | SHA-256 of the content |
| | preservation ledger, request log, discovery inputs and events, candidate qualifications, admission labels | **chained**: each row names the SHA-256 of the line before it (`previous_row_sha256`) |
| `DERIVED_REBUILDABLE` | discovery candidates | checked against events and request log; missing rows completed |
| | identity: documents, observations, versions, relations | rebuilt from preserved packs, ledger, URL rules, extraction; compared |
| | extraction layers | write-once, verified on read |
| `CACHE/VIEW` | pack indexes, channel health, candidate lifecycle, fetch plan | none; computed when read |

**Chain.** A change, removal, insertion, duplication or reordering of an earlier row breaks the
chain at the row after it: `ChainBroken`, and `recovery.diagnose` says `DAMAGED`; nothing repairs
it. An incomplete last line is a torn tail (`NEEDS_REPAIR`), not a break.

**Heads.** Closing a run records, for the ledger and each chained table, the row count and the
hash of the last line (`evidence_heads` in the run result, `coprepan-acquisition-run-result/v2`).
`diagnose` checks them: this covers the newest row, and rows cut from the end. Rows written after
the last close are covered at the next one.

**Identity rebuild** (`identity_rebuild.verify`, `adopt`; `diagnose(…, registry=…)`):

| Status | `diagnose` class |
|---|---|
| `CORRECT` | `CLEAN` |
| `REBUILDABLE` (absent, subset, unreadable) | `INCOMPLETE_RESUMABLE` / `NEEDS_REPAIR` |
| `CONFLICTING` | `DAMAGED`; adoption needs an explicit decision |
| `SOURCE_EVIDENCE_DAMAGED` | `DAMAGED`; nothing is rebuilt |

`adopt` moves the existing `identity/` aside to `identity.replaced-<n>` and renames the rebuild
(`identity.rebuild-<id>`) into place. Both leftovers are named by `diagnose` and never read as data.

**Single changed bits** (measured 2026-10-08, 40 per file, `diagnose` afterwards; "not noticed"):

| File | Before CPD-0010 | After |
|---|---|---|
| request log, discovery inputs, events, candidates | 40 / 40 / 40 / 40 | 0 / 0 / 0 / 0 |
| qualifications; admission labels | 39; 40 | 0; 7 (all in the last row, written after the run closed) |
| identity documents / observations / versions / relations | 15 / 22 / 4–6 / 22 | 0 / 0 / 0 / 0 |

**Cost** (measured, diagnostic): chained append 1–7 ms (lock, sync, read-back); reading and
authenticating 5,000 rows / 3.1 MB 0.02 s; heads of all tables 0.08 s.

## 19. This workstation's roots, the interim primary and the planned move (CPD-0014)

State of 2026-10-08. Physical locations are machine configuration (`.env`) and are written here as a
record of the state, not as configuration.

| Role | Root | State |
|---|---|---|
| `REPOSITORY` | `C:\dev\panhispanic_media_corpora\coprepan` | the checkout |
| `RUNTIME` | `C:\dev\panhispanic_media_corpora\coprepan_workspace` | configured; no marker (the architecture has one for the preservation role only) |
| `SPOOL` | `C:\dev\panhispanic_media_corpora\coprepan_storage` | configured; the module is tested on it; **not wired into acquisition** (a target that is down leaves the sealed pack `PRESERVATION_PENDING` in the workspace) |
| `PRESERVATION` | `D:\projects\panhispanic_media_corpora\coprepan\preservation_interim` | **`INTERIM_PRIMARY_PRESERVATION`**, target id `coprepan-preservation-interim-d`, readiness `READY` (no capacity statement) |
| `BACKUP`, `DISTRIBUTION`, `EXCHANGE` | — | `NOT_CONFIGURED` |

`D:` is a local volume of 3.8 TB that also holds CO.RA.PAN's `projects\panhispanic_media_corpora\corapan`
(untouched). **While it is the primary, `BACKUP` is not configured: `D:` is not its own backup.**

**The move to the new university file system** (not yet available; nothing here qualifies it):

```text
current primary  D:\projects\panhispanic_media_corpora\coprepan\preservation_interim
target           <NEW_FS>\projects\panhispanic_media_corpora\coprepan     (no doubled "projects" if the mount is already that root)

inventory current primary
  -> verified copy                          every path, size and SHA-256 equal (the contract's tree digest)
  -> destination verification
  -> readiness of the new root              (preservation_target.check_readiness)
  -> crash and concurrency qualification    on that file system (scripts/qualify_storage_roots.py; pytest --basetemp there)
  -> switch COPREPAN_PRESERVATION_ROOT      one variable
  -> replay and read-back                   no network
  -> the new file system is the PRIMARY
then
  -> D:\projects\panhispanic_media_corpora\coprepan\backup   made from the new primary, verified independently
```

Why this is a copy and a switch and nothing else: no id depends on the root (fetch, document and
version ids come from content and URL keys; no stored record names a root; the target marker moves
with the data), so no WARC and no evidence is rewritten — `tests/test_storage_architecture.py`
exercises it on a synthetic pack. `preservation_interim` is never renamed and declared a backup.

**Qualification procedure for a real file system** (what was run on `D:`): the readiness check on
the real root; the whole persistence, crash, concurrency, integrity and pipeline test set with
`pytest --basetemp=<a new directory on that file system>` (real process kills and real concurrent
processes there, not in a system temporary directory); and `scripts/qualify_storage_roots.py
spool-failover` for the outage spool. The probe artefacts are removed by the harness itself.
