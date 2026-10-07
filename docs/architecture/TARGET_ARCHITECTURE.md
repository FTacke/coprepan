# COPREPAN 3.0 — Target Architecture

**Status: NORMATIVE TARGET — MOSTLY NOT IMPLEMENTED.** Decided as the direction by
[CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md)
(2026-10-06). What exists is recorded in
[`docs/STATUS.md`](../STATUS.md); when the two differ, `STATUS.md` describes reality and this
document describes the goal.

*Added 2026-10-07:* the records of stages 1 and 3–6 — outlet, acquisition run, fetch record,
pack, document identity, extraction — and the layer separation are made specific by
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md); where this document is general and
the decision is specific, the decision governs. Those stages exist as code for *recorded*
exchanges only. Component entry points: [`INDEX.md`](INDEX.md) §0.

Evidence base: the architecture and migration audit of 2026-10-06 (kept in `corapan_playground`,
`docs/agent-runs/2026-10-06_coprepan3-architecture-and-migration-audit.md`; cited here as
"audit §n"). The audit is a historical record of one diagnostic run. This document, not the audit,
is what future work is built against.

Terms and identifiers: [`TERMINOLOGY_AND_NAMING.md`](TERMINOLOGY_AND_NAMING.md).

---

## 1. Shape

```text
OUTLET REGISTRY
    ↓
DISCOVERY                  ┐
    ↓                      │ acquisition
FETCH                      ┘
    ↓
RAW PRESERVATION             preservation
    ↓
DOCUMENT IDENTITY
    ↓
EXTRACTION                 ┐
    ↓                      │
ADMISSION LABELS           │ transformation (derived layers; labels, never deletion)
    ↓                      │
NORMALISATION              │
    ↓                      │
NLP                        │ annotation
    ↓                      │
VALIDATED ENRICHMENT       ┘ enrichment
    ↓
RELEASE                      selection, freeze, manifest
    ↓
CROSS-CORPUS ANALYSIS CONTRACT
```

There is **no monolithic crawl process**. Acquisition, preservation, transformation, annotation,
enrichment, admission and release are separate stages with separate state, each able to fail,
retry and be re-run alone. The legacy system fetched, extracted and stored in one in-memory step
and could therefore neither verify nor repair a single text (audit §1.2).

Three structural commitments distinguish this from the legacy pipeline:

1. **Preservation-first.** The primary raw object is the fetch with its exact response bytes, not
   the extracted article text. Every later layer is derived and regenerable.
   Detail: [`docs/storage/INDEX.md`](../storage/INDEX.md).
2. **Labels, not deletion.** Quality gates are *admission labels*. Nothing is discarded at crawl
   or extraction time because it is short, old, undated, a gallery or off-target; exclusion is a
   decision of a release or study selection view.
3. **Selection at release time.** Balancing and study scope are versioned views over preserved,
   labelled material. "Preserve first, balance later."

## 2. Rules common to every stage

| Rule | Meaning |
|---|---|
| Addressed input | a stage reads its inputs by id and hash, never by "the latest file in a directory" |
| Write-once layers | an output is written once; a different answer is a new artefact, never an overwrite |
| Fingerprint ≠ artifact id ≠ execution provenance | the *fingerprint* says what was asked (input hashes + component versions + parameters); the *artifact id* says which answer was produced; *execution provenance* (when, where, by which run) lives in the manifest and is not identity |
| One answer per fingerprint | the pipeline is deterministic; a second, different answer for the same fingerprint is an error, not a new version |
| Idempotent rerun | a rerun with the same fingerprint is a no-op |
| Ledger before state | every state transition is appended to a ledger before the state changes; an illegal transition raises |
| Closed state vocabularies | states are named tokens of a declared state machine, not free-text strings |
| A digest covers what it claims | a hash or id field is named for what it actually covers; an index is proven to fit the stream it addresses |
| Forward-only versions | a new component version applies to new work; old artefacts stay valid for their version; reprocessing is a recorded decision ([`AGENTS.md`](../../AGENTS.md)) |
| Derived-text traceability | any stage that produces or rewrites text records the upstream identity and hash, the component and version, the operations applied and the rendered result; the upstream artefact is never overwritten |
| No path in domain logic | storage locations are logical roles resolved fail-closed from the environment |

## 3. Stage contracts

| # | Stage | Responsibility | Input → output | Ids | State and retry | Storage |
|---|---|---|---|---|---|---|
| 1 | **Outlet registry** | which outlets exist; their attributes, channels, per-outlet rules, aliases | curated config → versioned registry | `outlet_id`, `channel_id` | reviewed change, versioned in git, append-style history | repository (`config/`) |
| 2 | **Discovery** | list item URLs per channel; keep the channel document and its fields (`lastmod`, `pubDate`, title, guid); expand sitemap indexes; archive census | channel → discovery events in an append-only frontier | discovery event id; channel-document hash | per channel `ACTIVE` / `EMPTY` / `FAILING` / `BLOCKED`; conditional requests; backoff | channel documents preserved; frontier ledger |
| 3 | **Fetch** | retrieve one URL politely under the outlet's policy | frontier entry → fetch record | `fetch_id` | `FETCH_PLANNED → FETCHED` / `FETCH_FAILED(reason, retry_at)` / `REFUSED_BY_POLICY(reason)`; bounded retries by error class; bounded re-fetch schedule for updates | open pack in the runtime workspace |
| 4 | **Raw preservation** | seal, hash, promote packs; fixity; reconciliation | open pack → sealed pack + manifest | pack hash, body `sha256` | `RAW_VERIFIED → PRESERVATION_PENDING → RAW_PRESERVED`; idempotent promotion; outage spool | PRESERVATION root; write-once |
| 5 | **Document identity** | canonical URL key; document and version assignment; duplicate and syndication relations | fetch records (+ extraction hash for versions) → identity tables | `document_id`, `document_version_id`, cluster id | deterministic; rule set versioned | append-only identity tables |
| 6 | **Extraction** | bytes → typed blocks + metadata with basis; deterministic, versioned | preserved body → extraction layer | fingerprint over body hash + extractor version + outlet-rule version | one answer per fingerprint | derived layer |
| 7 | **Admission labels** | label each document version: article / not article, access class, language, length, type, date basis — with reasons | extraction layer → label record | label-rule version | labels only; `QUARANTINED(reason)` for unreadable input | derived layer |
| 8 | **Normalisation** | Unicode and whitespace normalisation, one record per operation; **no lexical repair** | extraction → normalised text + operation report | text hash | deterministic | derived layer |
| 9 | **NLP** | the shared annotator contract ([`docs/nlp/INDEX.md`](../nlp/INDEX.md)) | normalised text → sentence and token tables | chain-version digest; ids on the document version | deterministic; fingerprint includes the pins; pin drift is refused | derived layer, columnar |
| 10 | **Validated enrichment** | only validated layers: verbal complex, section mapping, article type, syndication clusters | upstream layers → enrichment tables keyed on stable ids | rule or model version per layer | each layer switchable; rollback = deactivate | derived layers |
| 11 | **Release** | freeze a selection under a stated policy; manifest, hashes, coverage table | layers + selection policy → immutable release bundle | `release_id` | build → verify → publish; never overwritten | PRESERVATION `releases/`; DISTRIBUTION copy |
| 12 | **Cross-corpus contract** | export the release to the shared analysis tables | release → contract tables | contract version | reader shim per version | part of the release |

Ordering note: document *versions* are distinguished by the hash of the extracted text, so the
identity stage assigns `document_id` from the fetch record and completes `document_version_id`
once extraction has produced a text hash. Extraction may only read objects that are
`RAW_PRESERVED`.

Known failure modes each stage must name and test (audit §18): feed gone, truncated index, image
URLs in sitemaps, opt-out signals (discovery); timeouts, 4xx/5xx, soft paywalls, bot walls,
off-origin redirects (fetch); target unreachable, hash mismatch, identity conflict (preservation);
key collision, off-origin canonical, variant-folding errors (identity); template change, empty
body, wrong main block (extraction); landing page or truncated paywall text passing as an article
(admission); pin drift (NLP); an unvalidated layer leaking into a release (enrichment/release).

## 4. Acquisition

**Outlet registry.** Outlets are registered, attributed and aliased before anything is fetched.
Attributes and the supply model: [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md).
A channel is *qualified* by an output probe — a sample of its URLs must yield real article text —
which is the legacy system's one clearly good discovery idea and is kept as a gate.

**Discovery** preserves the channel document itself: it is the evidence of how a URL was found and
carries `lastmod` / `pubDate`. Sitemap indexes are expanded (the legacy system forced them
inactive, closing the main route to archives). Image and video sitemap entries never enter the
frontier.

**Fetch** is polite, per-outlet-policy, and separately ledgered. A failed or short response is a
recorded fetch with a reason and a `retry_at`, never a permanent blacklist of the URL.

**Policy.** Which robots and opt-out signals bind the crawler, under which crawler identity and
contact, and how long raw copies are retained, is an **open institutional decision** (master plan
§13, O-1, O-2). Two things are already fixed and do not wait for it:

- An access control (authentication, paywall, bot challenge, rate limit) is never bypassed.
  A refusal is recorded as `REFUSED_BY_POLICY` with its evidence.
- The policy that was applied is *recorded per fetch* (robots decision, robots.txt version
  consulted, access class observed, crawler and policy version). The legacy system configured one
  robots behaviour and implemented another, and nobody could tell from the data (audit T-7). In 3.0
  a configured policy that is not enforced by tested code is a defect.

No production crawl starts before the policy is decided, implemented and tested.

## 5. Preservation

Specified in [`docs/storage/INDEX.md`](../storage/INDEX.md): the fetch record, the WARC pack
container, the preservation state machine, storage roles and classes, promotion semantics,
retention, fixity, capacity.

## 6. Document identity

**Canonical URL key**, computed per outlet from, in order: `rel=canonical` when it stays on a
registered web origin of the outlet; else the final URL after redirects; else the requested URL.
Then: scheme and host normalised against the outlet's registered origins, fragment dropped, query
reduced to the parameters the outlet's rule set declares significant, AMP / mobile / print
variants folded by outlet rule. **The path keeps its case.** Inputs and rule-set version are
recorded, so a key can be recomputed; a rule change is a visible, versioned event and the old key
stays as an alias.

| Case | Treatment |
|---|---|
| Update | a later fetch of the same document with different text is a new *document version*; a release selects by a recorded policy. A bounded re-fetch schedule replaces the legacy rule "a URL is fetched once". |
| Exact duplicate | same normalised-text hash under different documents → a `duplicate_of` relation. Never a deletion. |
| Near duplicate / syndication | shingle-based similarity across outlets and days → `syndication_cluster_id`; the release view decides whether one representative or all are kept. |
| Liveblog | an article-type label; excluded from the *default* release view because its text is an accretion of versions. |

## 7. Extraction, admission labels, normalisation

**Extraction** turns preserved bytes into a list of **typed blocks** (`title`, `paragraph`,
`heading`, `list_item`, `quote_block`, `caption`, `embed`, …) with roles and DOM anchors, plus
metadata fields that each carry their basis (`json_ld`, `open_graph`, `html_meta`, `url_pattern`,
`unknown`). Design rules, each the negation of a measured legacy defect (audit §4, §10):

- Deterministic and versioned; replayable from preserved bytes without re-crawling.
- **Structural rules only.** No substring test on article prose, no minimum paragraph length as a
  deletion rule, no lexical "repair" of words. (The legacy extractor deleted every paragraph
  containing `epa`, and with it `separar` and `preparar`, and split 10-letter words before
  `o`/`al`.)
- Non-body blocks (captions, credits, embeds, bylines) are *kept and typed*, and excluded from the
  body view — not deleted.
- **Unknown stays unknown.** A missing publication date is `unknown`; the fetch instant is never
  written as a publication date (the legacy corpus did this for 16 % of its records).
- A generic structural extractor plus per-outlet rule sets where the channel probe shows the
  generic path failing. Extractor candidates are compared on a gold sample before one is adopted
  ([`docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md`](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md)).

**Admission labels** classify, with reasons and a rule version. Thresholds (minimum length, age,
language share) are parameters of a release view, not of the labeller. Provenance is never an
admission filter.

**Normalisation** is limited to recorded character-level operations (Unicode NFC, whitespace).
Each operation is recorded with its offset, so the extracted text can be reconstructed. The
published wording is never changed: no spelling correction, no standardisation of variants, no
"fixing" of the outlet's punctuation.

## 8. NLP and enrichment

[`docs/nlp/INDEX.md`](../nlp/INDEX.md). In short: one annotator contract for both corpora;
project-specific labels are separate enrichment layers keyed on token ids, never fields inside
`morph`; an enrichment enters a release only when validated.

## 9. Release and the cross-corpus contract

A **release** is an immutable bundle: the selected document versions, their layers, a manifest with
per-file hashes, the annotator-contract version, a coverage table and the selection policy that
produced it. A study pins `release_id` and manifest hash. Releases are built → verified →
published and never overwritten.

Release and freeze semantics are designed **once, jointly with CO.RA.PAN 3.0**, where they are
also open. The cross-corpus contract and what it must deliver:
[`docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md`](../plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) §9.

## 10. Orchestration and execution

- A scheduler-driven worker with persistent ledgers, on a workstation or a small server. State
  never lives in a thread or in a web handler.
- An operator dashboard may *read* ledgers; it never owns a job and never mutates state without a
  ledgered command.
- HPC is not part of the core: acquisition is I/O-bound and the NLP stage runs on CPU. It becomes
  relevant only if a self-hosted LLM enrichment is ever adopted.
- No external model API in a production path.

## 11. Relationship to `corapan_playground` code

Domain-independent mechanisms that CO.RA.PAN 3.0 already runs in production (storage targets and
promotion, forward-only change decisions, API accounting) are the reference implementation. The
audit's target is to consume them as a pinned dependency once they are generalised beyond
`recording_id` / `station_id`; that generalisation would be made in `corapan_playground` under its
own release gate. **Until then COPREPAN 3.0 implements against the same on-disk contracts in its
own code**, so a later consolidation moves no data. Whether and when to consolidate is a Phase-1
question (master plan §13, O-8). This repository never edits `corapan_playground`.

## 12. Testing

Unit tests on recorded fixtures — preserved responses replayed, never live sites. A contract test
per layer schema. A determinism test (same fingerprint, same bytes). A replay test (re-extract a
preserved sample and compare). Property tests for the URL key. A release-gate suite that every
production change must pass. **No test touches the network, a storage root or a production
ledger**; tests write only under `tmp_path`.
