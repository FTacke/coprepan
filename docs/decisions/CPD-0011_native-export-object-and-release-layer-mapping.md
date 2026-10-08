# CPD-0011 — CO.PRE.PAN's native export object `coprepan-export/v1` and its mapping into a release

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the second-implementation run of `crosscorpus-release/v1` (2026-10-08), which named the native export object (contract §16 Q4) as the CO.PRE.PAN architecture decision of that run and ordered it to be recorded as a CPD on sufficient evidence. Recorded by that run; subject to the operator's review |
| Kind | architecture |
| Scope | what a CO.PRE.PAN export is: granularity, identity, content, schema id, provenance; how an export becomes a release member and release document records; the builder's gates |
| Builds on / amends / supersedes | builds on CPD-0003 (ids, canonical JSON), CPD-0005 (extraction record, layers), CPD-0007 (technical admission, extractor lifecycle), CPD-0010 (evidence classes). Amends nothing |
| Does not change | any stored artefact, any pipeline stage before the release stage, the joint contract bundle, anything in CO.RA.PAN |
| Run report | [`docs/agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md`](../agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md) |
| Evidence | `src/coprepan/release_export.py`; `tests/test_release_export.py` (the synthetic canary through the real pipeline code into an export, a fixture release, a package and a study population); the inventory in the run report §11 |

Validation debt: the object has carried synthetic pages only. No corpus material, no adopted
extractor, no annotation layer, no real preservation target. Listed in `docs/STATUS.md` §6.

## Context

The joint release contract treats a corpus's exports as opaque members: an immutable tree, a
native id, a schema id (contract §6). CO.RA.PAN has such an object (`corapan-export-ready/v1`).
CO.PRE.PAN had none; the contract's own CO.PRE.PAN fixture uses an invented
`coprepan-fixture-export/v1` and says so (contract §16 Q4).

What CO.PRE.PAN has, as built: preserved fetches in sealed packs (primary evidence); documents and
document versions in identity tables (derived, rebuildable); extraction records in a write-once
layer store, addressed by fingerprint and artifact id; technical admission labels (chained
evidence); and an analysis bundle that is a projection. None of these is a thing a release can
name: the layer store and the identity tables are workspace state, a pack holds fetched pages, and
the analysis bundle is derived.

## Decision

### 1. The export

An export is an immutable directory tree at `<exports root>/<export_id>/`:

```text
EXPORT_MANIFEST.json                      coprepan-export/v1
DOCUMENTS.jsonl                           one coprepan-export-document/v1 record per document version
extraction/<fingerprint[:2]>/<artifact_id>.json   the stored extraction records, byte for byte
```

It is the smallest object that is at once complete (the text and its provenance), closed (nothing
in it refers to workspace state) and nameable by a release.

### 2. Granularity

- **One export holds document versions of one outlet.** A release can then stop naming an outlet's
  material — a withdrawal, an opt-out, a registry correction — by its `changes`, without touching
  any other export.
- **A document version is delivered by exactly one member export of a release.** The release
  builder refuses anything else.
- **Not decided:** how an outlet's versions are partitioned into exports over time. No measured
  volume exists (O-4); a size or a period would be an invented number. An export is not a pack and
  not an acquisition run: the same version is observed in many packs, and a release selects.

### 3. Identity

`export_id` = `cpx1-` + the first 32 hex digits of the SHA-256 over the canonical JSON of
`EXPORT_MANIFEST.json`. The manifest does not contain the id; it pins the document records (record
set digest) and the layer files (record set digest of their `{path, sha256, size}` listing). The
id therefore covers the whole object, provenance included, and **no document contains its own
digest** — the rule of the joint contract (§4.3) applied to the native object. The contract's tree
digest over all files is recorded in the member record in addition.

The manifest holds **no clock time, no host name, no location**. The same versions exported by the
same code give the same id on every machine. When, where and by which run an export was built is
execution provenance and is not part of the object (AGENTS.md §10).

### 4. Content

Per document version: `document_version_id`, `document_id`, `outlet_id`; the digests of the
extracted text and of the body text; the extraction record by path, digest, fingerprint, artifact
id and extractor version; **the source**: `fetch_id`, the digest of the preserved body, the
`pack_id`; the technical admission label by rule set, status and informing reasons; a date with
its basis and state.

- The export contains extracted text. **It contains no fetched page, no pack and no response
  header.** A document is tied to preserved material by ids and hashes (`source_included` is
  `false` in the release).
- A date is known only when a parsed date is handed in with its basis and the component that
  parsed it; a page value nobody parsed is `not_available`; a page without one is `unknown`. A
  retrieval date is never a date.
- The manifest names the code commit, the export builder version, the extraction schema, the
  extractors with their lifecycle state, the admission rule sets and the URL-key rule set.

### 5. Layers and versions

`layers` is `["extraction"]`. **An annotation layer is not part of `v1`**, because none exists.
Token counts are therefore `not_available` in every release document record built from a `v1`
export, and the release states `token_denominator_state: not_available`. Carrying annotation is a
new version of this schema, decided with the NLP stage. A reader refuses another schema version by
name.

The analysis bundle (`crosscorpus-analysis/v1`) stays a **projection**: it is not in the export,
and it names nothing of the release by digest.

### 6. Correction

A corrected text is a new document version; it enters a **new export** with a new id. The old
export stays, because an earlier release names it. Nothing is rewritten, and an export under an
existing id is never overwritten (`ALREADY_STORED` for the same tree, a conflict otherwise).

### 7. Gates the builder does not go around

- `export_kind` is `corpus` or `fixture`. **A `corpus` export is refused unless every extractor
  that produced its text is `ACTIVE`** (CPD-0007 §7). Nothing is `ACTIVE`, so no corpus export can
  be built today. A fixture export enters a fixture release (`coprepan-0000.n`) and nothing else.
- A version whose fetch is `TECHNICALLY_UNUSABLE` is not exported; it stays labelled.
- A label, an extraction record, a preserved body and a version id that do not belong together
  are refused.
- The builder reads the layer store, the identity results and the labels; it writes only below the
  exports root it is given.

### 8. Mapping into `crosscorpus-release/v1`

| Release record | From |
|---|---|
| member: `export_id`, `export_schema`, `tree_sha256`, `files`, `bytes`, `documents` | the export's name, `coprepan-export/v1`, the tree digest over all of its files |
| document: `document_id` | `document_version_id` |
| `source_sha256` | `extracted_text_sha256` (`anchors.source_kind`: `extracted_text`) |
| `date`, `date_basis`, `cohort` | the export record; the cohort is the quarter of the date |
| `tokens_counted` | `not_available` |
| `audio_ms` | `not_applicable` |
| `anchors.unit_kinds` | the block kinds of extraction; `producer_kinds` empty |
| `vocabularies.date_basis` | the bases a publication date can rest on (`json_ld`, `open_graph`, `html_meta`) |

A release is written by `build_release` and **exists only after `freeze_release`**, which requires
the check with every export present to pass and the manifest's digest to be stated. This release
freeze is not the acquisition baseline freeze (O-12) and not the legacy freeze manifest.

## Alternatives considered

| Alternative | Why not |
|---|---|
| one export per document version | the member list would be as long as the document index; the contract keeps the manifest small by naming exports, not documents |
| one export per pack or per acquisition run | a version is observed in many packs; "exactly one member per document" could not hold; a pack holds fetched pages |
| one export per outlet and calendar quarter of publication | dates are not parsed yet; an undated version would have no export; the period is a parameter better left open |
| the layer store itself as the export | workspace state, fan-out by fingerprint of every extractor version, not closed |
| the analysis bundle as the export | it is a projection; it would make a derivative the source of a release |
| a native id over the text only, provenance beside it | the defect the contract records for CO.RA.PAN (§6.2): provenance outside the identity |
| an `export_id` field inside the manifest | a self-reference; needs a "hash of everything but" rule in every reader |
| a build timestamp in the manifest | the same content would get a new id on every build |
| raw pages in the export | a release never contains its source (contract §8); retention of raw copies is O-1 |

## Consequences

- Stage 11 (release) is `PARTIAL`: an export object, a builder and the release mechanics exist and
  are tested offline on synthetic pages.
- A real export needs an adopted extractor (Phase 3); a real release additionally needs a
  selection policy (contract §16 Q6) and a durable exports root (O-3).
- **Retention:** an export named by a frozen release is on hold for as long as the release exists,
  and so is every pack that holds a fetch such an export names ([storage](../storage/INDEX.md) §7).

## Not decided here

- How an outlet's versions are partitioned into exports over time; sizes and cadence.
- The annotation layer of an export (`v2`) and with it token counts.
- The date parser, and the outlet time zone a local calendar date needs.
- Whether a release selects one version per document; the selection policy and its document.
- A producer anchor for press (author, byline): contract §16 Q3.
- Where exports and releases are stored; distribution; any deposit.
- Columnar storage of the record sets.
