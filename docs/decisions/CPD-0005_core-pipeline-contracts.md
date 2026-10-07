# CPD-0005 — Core pipeline contracts: run, fetch record, pack, document identity, extraction, layers

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Status note 2026-10-07 | Audited by the following run and **amended forward-only by [CPD-0006](CPD-0006_discovery-transport-policy-gate-and-readiness.md) §1** in three points: the fetch record gains `fetch_kind` and a complete policy block; "the body" is the HTTP payload with its content coding and without transfer coding (the item left open below); identity observations keep each fetch's own URL keys. Everything else stands. The debt "read by an independent WARC reader" is paid for the written record subset (warcio 1.7.5). |
| Decided by | the operator, in the brief of the foundation, architecture and core-pipeline run (2026-10-07), which ordered the core architecture to be decided from the master plan, the foundation, the legacy evidence and proven CO.RA.PAN 3.0 principles, and authorised that run to decide where the evidence suffices. Recorded by that run; subject to the operator's review. |
| Kind | architecture |
| Scope | the contracts of the stages from acquisition run to document version; the separation of corpus layers |
| Builds on / amends / supersedes | builds on CPD-0001 (principles), CPD-0002 (naming), CPD-0003 (id serialisation); makes [`TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md) §3–§7 specific for these stages; settles the open points of [`docs/storage/INDEX.md`](../storage/INDEX.md) §3 as far as stated in clause 3 |
| Does not change | the acquisition policy (undecided, O-1); the preservation target (O-3); which extractor is adopted; any scientific taxonomy |
| Run report | [`docs/agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md`](../agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md) |
| Evidence | [`docs/legacy/ARCHAEOLOGY.md`](../legacy/ARCHAEOLOGY.md) §6 (failure mechanisms); the CO.RA.PAN 3.0 survey of 2026-10-07 in the run report §6; `tests/test_acquisition_pack.py`, `tests/test_extraction.py`, `tests/test_core_pipeline.py` (canary and identity ablation) |

Validation debt (why not plain `ACTIVE`): the pack writer has not been read by an independent
WARC reader; nothing has run against a real preservation target or a real outlet; the baseline
extractor is not validated. Listed in `docs/STATUS.md` §6.

## Context

The target architecture named the stages; it did not fix their records. The legacy system shows
what unfixed records cost (failure mechanisms F-1, F-7, F-8, F-12, F-13, F-14).

## Decision

### 1. Outlet as the source entity

The entity that describes a source is the **outlet** of the registry (`coprepan-outlet-registry/v1`):
country, display names with validity, type, group, seat, access model, medium, time zone, web
origins with URL rules, channels (the "source endpoints") with URL history, legacy aliases.
*Publisher* is the attribute `outlet_group`, not an entity. *Domain* is `web_origins[]`, not an
identity. *Active period* is not a registry field: it is what the ledgers show. *Acquisition
policy* is not a registry field until O-1 is decided. Only a `registered` outlet is acquired for.

### 2. Acquisition run

A run has an identity that covers **what was asked** and a result that says **what happened**.

- `run_id` = `acq1-<UTC start, YYYYMMDDTHHMMSSffffffZ>-<hash12>`; the hash is the first 12 hex
  digits of SHA-256 over the canonical JSON of kind, start instant, outlet ids, discovery method,
  software version, component versions and the configuration's SHA-256.
- The run record (`coprepan-acquisition-run/v1`) is written once when the run starts; the result
  (`coprepan-acquisition-run-result/v1`: finish instant, `COMPLETED` / `FAILED`, counts, pack ids,
  errors) once when it ends. **A run with a record and no result is interrupted or running** —
  that is visible, and such a run can be resumed. A finished run is never reopened.
- The only run kind that exists is `recorded_replay`. A live kind is added with the fetcher, behind
  the acquisition gates.

### 3. Fetch record and raw container

- **Fetch record** (`coprepan-fetch-record/v1`), one per retrieval event: `fetch_id`, `run_id`,
  `outlet_id`, outcome, request (method, URL, headers), response (status, final URL, redirect
  chain, headers as an ordered list, declared content type), start and finish instants,
  `body_sha256`, size, discovery (`channel_id`), policy context. A value that does not exist is
  `not_applicable` or `unknown`, never absent. The record never contains the body.
- **`FETCHED` means a complete response came back**, whatever its status: a 404 page is a
  preserved fetch. `FETCH_FAILED` means nothing came back, with a reason from a closed list. What
  a status code means for the corpus is an admission label, not a fetch outcome.
- **Container:** WARC/1.1, one gzip member per record, written by the repository's own writer
  (`pack-writer/1`, standard library only). Per fetch a `response` record whose payload is the
  exact body, then a `metadata` record holding the fetch record; a fetch without a response has
  the `metadata` record alone. No `request` record: the request facts are in the fetch record, and
  a rendered request would claim wire bytes that were never recorded. The HTTP header block of a
  `response` record is rendered from the fetch record; the digest covers the body.
- **Pack:** `pk1-<outlet_id>-<YYYYMMDD>-<nnn>` — one pack per outlet and UTC day of the fetch
  start, with a rollover number. Open as `<pack_id>.warc.gz.open` in the runtime workspace; sealed
  by re-reading every record, renaming, deriving the index and writing the manifest
  (`coprepan-pack/v1`: pack SHA-256, size, index SHA-256, counts).
- **Index:** derived at seal time from the bytes actually written, bound to the pack by the
  manifest, and re-checked on every read (the record reached through an index entry must be that
  fetch and its body must hash to the indexed digest).
- **Interrupted append:** a fetch is whole or absent. The tail from the first incomplete fetch is
  moved to a sidecar and the open pack cut back; nothing is discarded. A sealed pack is never
  touched.
- **Promotion:** the sealed pack and its index are promoted with the semantics of storage §6
  (areas `raw` and `raw_index`, path `<country_id>/<outlet_id>/<pack_id>…`). A fetch is
  `RAW_PRESERVED` only after the promoted master has been re-read and verified.
- Still open, as storage §3 says: an independent WARC reader as a conformance check; the
  compression codec beyond gzip; pack rollover by size; `revisit` records for a body already held.

### 4. Document identity

Five identities, never conflated:

| Identity | Id | Covers |
|---|---|---|
| fetch | `fetch_id` | one retrieval event |
| source object | `body_sha256` | the bytes |
| document | `document_id` | the article as an editorial unit: outlet + canonical URL key |
| document version | `document_version_id` | one textual state: document + digest of the extracted text |
| relation | (`relation`, document, target) | `duplicate_of`, `moved_to` |

- **An article is not its URL.** The observed URL is recorded per fetch; the document is the
  canonical URL key (CPD-0003 §8) under the outlet's registered rules. `rel=canonical` is read
  from the head of the preserved body by a versioned scan (`head-scan/1`).
- **Same URL, changed content** → the same document, a new version. **Same content fetched
  again** → the same version, one more observation.
- **Different URLs, same body text** → different documents with a `duplicate_of` relation on the
  digest of the BODY text. Never a merge, never a deletion.
- **URL change:** when the requested URL, keyed on its own, is the key of *another* existing
  document, a `moved_to` relation is recorded from that document to the one the response belongs
  to. No id is rewritten.
- **Syndication** across outlets (near-duplicates) is a later enrichment layer, not identity.
- **"The extracted text"** of CPD-0003 §5 is now defined: the canonical JSON of the ordered list
  of `[kind, role, text]` of all blocks of the extraction record. Any change in what was
  extracted is a new textual state. The same text produced by another extractor version is the
  same version id; the extractor version is recorded per observation.
- Identity tables are append-only; a truncated id that would stand for two keys or two texts is
  refused (`DocumentIdCollision`).
- A fetch whose URLs all lie off the outlet's registered origins has no document under that
  outlet. It stays preserved.

### 5. Extraction

- A pure function of (body bytes, declared content type and charset, extractor name and version):
  no clock, no network, no state. Its record (`coprepan-extraction/v1`) names its input by hash
  and its extractor by version and contains nothing volatile.
- **Typed blocks in document order**, each with a `kind` (`title`, `heading`, `paragraph`,
  `list_item`, `quote_block`, `caption`, `unstructured_text`) and a structural `role` (`title`,
  `body`, `non_body`). **BODY** — the blocks with role `body`, joined by a blank line — **is the
  primary linguistic text surface.** The title and every non-body block are kept and typed, and
  excluded from the body view. A role is a statement about markup, not a linguistic category.
- **Metadata with basis:** `title`, `author`, `publication_date`, `modification_date`, `section`,
  `language`; each with the value exactly as published, the basis it rests on (`json_ld`,
  `open_graph`, `html_meta`, `html_title`, `html_h1`, `html_lang`) and every candidate found.
  Nothing is parsed, converted or defaulted: an absent value is `unknown`. Tags are not extracted
  (the legacy system discarded them and no study asked for them).
- **Structural rules only:** no substring test on prose, no length threshold, no lexical repair.
- **Not extractable is a label:** an unsupported or unrecognisable content type gives a record
  with `NOT_EXTRACTABLE` and a reason; the fetch stays preserved and keeps its document.
- **Decoding** is recorded: charset, its basis, and the number of replaced characters.
- An extraction is stored in the layer store under the fingerprint (stage, extractor version,
  body hash, declared content type and charset). **Replay** re-derives it from the preserved pack
  and must reproduce the stored bytes; a different result under the same fingerprint is an error.
  A new extractor version is a new fingerprint; the old answer stays.
- `baseline_html/0.1.0` implements this contract so that it can be exercised. **It is not
  adopted.** Which extractor produces corpus text is decided in Phase 3 on a gold sample.

### 6. Corpus layers

```text
RAW        sealed packs on the preservation root; fetch records; write-once
EXTRACTED  extraction records in the layer store, keyed by fingerprint; identity tables
ANNOTATED  the shared NLP instrument's output, keyed on document versions        (not built)
RELEASE    a frozen selection with manifest, hashes and policy                    (not built)
```

No layer overwrites an earlier one, and a later layer reads an earlier one **by id and hash**,
only when the ledger says it may (extraction reads `RAW_PRESERVED` fetches from the preservation
root, never the workspace copy). Scientific layers — section mapping, register, genre, opinion,
verbal complex — are **enrichment layers keyed on document versions, blocks or tokens**, each with
its own version and validation status; none is a field of the extraction record, and none is
decided or validated here. What extraction supplies them with is the published `section` value
with its basis, the structural roles, and stable ids.

## Alternatives considered

| Alternative | Why not |
|---|---|
| URL as the article identity | Ablation on a controlled set (`tests/test_core_pipeline.py`): one article under four observed URLs becomes four "articles" and its revision is unrelated to it. The legacy lower-cased variant still splits it four ways and in addition merges two different pages whose paths differ in case. |
| Content hash as the article identity | A corrected article would become a new article; the same agency text in two outlets would become one. Content identifies the *version*. |
| Version digest over the body text only | A changed headline would not be a new textual state. The body digest is kept separately for the duplicate relation. |
| One loose file per fetch | Millions of small files on a network share; no natural unit for sealing, promotion and fixity (storage §3). |
| A third-party WARC library now | None is installed, no network access is allowed to install one, and the record subset needed is small. Reading the packs with an independent reader stays owed. |
| A WARC `request` record rendered from the fetch record | It would present reconstructed bytes as an exchange. The request facts are stored as what they are. |
| Dropping fetches with error statuses or non-HTML bodies | That is the legacy "discarded" path (F-1, F-9). They are preserved and labelled. |
| Letting extraction pick one "best" title or date and discard the rest | The legacy title contamination came from exactly such a choice. Candidates with their basis cost little and keep the decision reviewable. |

## Consequences

- Stages 2–3 (discovery, fetch) remain `NOT_STARTED`: there is no network code.
- Stages 4–6 are `PARTIAL` in `docs/STATUS.md`: they work end to end on recorded exchanges and
  have never seen a real outlet or a real preservation target.
- New id kinds and vocabularies are recorded in [`TERMINOLOGY_AND_NAMING.md`](../architecture/TERMINOLOGY_AND_NAMING.md).

## Not decided here

- The acquisition policy and crawler identity (O-1, O-2); the live fetcher; whether stored bodies
  are wire bytes or transfer-decoded bytes (to be fixed with the fetcher and recorded per fetch).
- Channel documents and discovery events (Phase 2).
- The adopted extractor, per-outlet extraction rules, admission labels (Phase 3).
- Publication-date parsing, time-zone conversion and cohort assignment (corpus-supply §3).
- Any section, register, genre or opinion taxonomy; the annotation layer; the release format.
- Where the durable layer store and the identity tables live (today: the runtime workspace).
