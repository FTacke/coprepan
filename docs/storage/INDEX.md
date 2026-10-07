# Storage, Preservation and Provenance — component index

**Status: NORMATIVE TARGET — PRIMITIVES ONLY.** Root resolution, promotion, the outage spool, the
state machine with its ledger and the layer store exist as code tested on temporary directories
(§13). **No pack format, no fetch record, no fixity schedule and no backup exist; no storage root
is configured; nothing has been preserved.** Governing decision:
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
| `BACKUP` | a second physical copy with its own verification states | to be configured |

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
| WARC library, codec, index format, pack rollover | technical, Phase 2 | this document §3 |
| Reuse of the `corapan_playground` storage modules as a dependency | technical, Phase 1 — own code against the same on-disk conventions for now (§13); the consolidation question stays open | master plan §13, O-8 |
| Phase-1 gate on a **real** preservation target | needs O-3 | master plan §11 |
| Cross-process locking of ledger and layer store | technical; single writer assumed today | §13 |
| A content index for the duplicate check (today a linear scan of manifests) | technical, Phase 2 | §13 |

## 12. Milestones

- 2026-10-06 — principles and target design recorded (repository bootstrap). Nothing implemented.
- 2026-10-07 — Foundation Core I: the primitives of §13, tested on temporary directories only.
  Run report: [`docs/agent-runs/2026-10-07_foundation-core-i.md`](../agent-runs/2026-10-07_foundation-core-i.md).

## 13. What exists (Foundation Core I)

Tested on temporary directories. None of it has run against a real storage root.

| Mechanism | Code | On-disk contract |
|---|---|---|
| Root resolution (§5) | `src/coprepan/storage_roots.py` | reads `config/storage_targets.yml`; refusals `StorageRootNotConfigured`, `StorageRootUnusable` (relative, filesystem root, inside the checkout), `StorageRootUnreachable`, `StorageRootReadOnly`; never creates a root; `.env` is read only on request |
| Promotion (§6) | `src/coprepan/preservation.py` | master `preservation/<area>/<relative path>`; manifest `preservation/manifests/<area>/<object id>.json`, schema `coprepan-preservation-manifest/v1`; staging `<name>.part-<hex>`; landed bytes re-hashed before the atomic rename; outcomes `promoted`, `already_preserved`, `repaired`, `duplicate_recorded`; refusals `HashMismatch`, `IdentityConflict` |
| Outage spool (§6) | `src/coprepan/outage_spool.py` | bytes `preservation/pending/<area>/<relative path>`; record `state/pending/<object id>.json`, schema `coprepan-preservation-spool/v1`; both bounds of `SpoolPolicy` are mandatory, no built-in size |
| State machine and ledger (§4) | `src/coprepan/ledger.py` | one JSON object per line, schema `coprepan-ledger-record/v1`, appended and flushed before the state changes; state is the replay of the ledger; a torn last line is quarantined to `<name>.torn-<n>`, never dropped |
| Layer store | `src/coprepan/layer_store.py` | `<root>/<stage>/<fp[:2]>/<fingerprint>/<artifact id>/{payload, manifest.json, PROMOTED}`; fingerprint schema `coprepan-layer-fingerprint/v1`; artifact id `ar1-` + 32 hex |

Notes that bind later work:

- The promotion unit is "a sealed file with an identity". **What a pack is, its id and its relative
  path are Phase-2 decisions**; the area name and path are parameters today.
- The state machine is the one of §4. One edge is implemented that the diagram does not draw:
  `FETCH_FAILED → FETCH_PLANNED`, the retry that `retry_at` implies. The fetch stage (Phase 2)
  confirms or corrects it.
- A duplicate (same bytes under another identity) gets a manifest with `duplicate_of` pointing at
  the holder's master; nothing is copied.
- The preservation module contains no deletion call at all (asserted structurally). The spool
  releases its own copy only after the promoted master has been re-read and verified.
- Staging name, hash-then-rename order and manifest rendering follow the CO.RA.PAN 3.0 storage
  code as read on 2026-10-07; the manifest *fields* are COPREPAN's own (a pack is not a recording).
