# Joint release contract `crosscorpus-release/v1`

**Status: DRAFT. Not in force in either repository. Nothing validated scientifically, nothing
activated.** No release of either corpus exists. What exists is this text, the schemas beside it,
synthetic fixtures for both corpora, conformance vectors, and one implementation (CO.RA.PAN's). The
contract stays a draft until it has been checked against both current implementations and both
projects have recorded its adoption (§14.3).

This directory is the **contract bundle**: `CONTRACT.md`, `schemas/`, `fixtures/`, `conformance/`.
It is identified by one digest (§14) and is read byte-identically by both repositories.

The key words *must*, *must not*, *may* are used in their plain normative sense.

---

## 1. Purpose and scope

A corpus grows continuously; a study needs a corpus state that does not. This contract defines, for
CO.RA.PAN (spoken radio) and CO.PRE.PAN (written press) alike:

- what a **release** is, how it is identified, and how it is frozen, corrected and superseded;
- how a release names its content: immutable, content-addressed **exports**, bound by digests;
- how digests are formed, so that the same content gives the same digest on every machine;
- the shared **document index** and **coverage** of a release, with date semantics and counting;
- the **study-population manifest** that pins what an analysis actually read;
- **distribution** and **archive packages** without source media, and their citation metadata.

It does **not** define the analysis tables (tokens, sentences, units, layers): that is
`crosscorpus-analysis/v1`, which this contract extends and does not restate (§2). It defines no
pipeline, no storage location, no access policy and no scientific population.

## 2. Relation to what exists

| Existing thing | Where | Relation |
|---|---|---|
| `crosscorpus-analysis/v1` — the analysis layer (tables, value states, `production_mode`, `crosscorpus-token-denominator/v1`) | CO.PRE.PAN, `docs/crosscorpus/ANALYSIS_CONTRACT.md`, CPD-0008; a technical proposal | **Extended, not replaced.** This contract takes from it, by reference: the namespace `crosscorpus-`, the five value states (§7 there), the `<field>` / `<field>_state` convention, `corpus_id`, `outlet_id`, `country_id`, `date` / `date_basis` / `cohort` (§5.3 there), the unit kinds (§5.4 there), the token denominator (§6.3 there), `release_kind` (§8 there) and the pin shape `{state, id, sha256}`. It fills two items that contract lists as open (§16 there): the coverage schema and the place of the selection policy; and it settles what §8 there left open: release identity, freeze and correction |
| canonical JSON | CO.PRE.PAN CPD-0003 (`canonical.canonical_json`); CO.RA.PAN layer-store fingerprints (`reservoir.asr_ready.canonical_json`) | **The same bytes** (§4.1), restricted to values that have exactly one serialisation |
| the release / archiving plan | CO.RA.PAN, `docs/plans/2026-10-07_corpus-storage-release-distribution-and-archiving-plan.md` (operator plan) | Its §2.4, §6, §7, §8, §9.5, §12 and gates G4, G5, G7, G8 are what this contract makes checkable. Where this contract differs from the plan's sketches, §15 says so and why |
| native exports | CO.RA.PAN `corapan-export-ready/v1` bundles; CO.PRE.PAN: none yet | **Opaque members** (§6). Their inner format is each corpus's own |

One analysis bundle of `crosscorpus-analysis/v1` is, in the terms of this contract, a **projection**
of a release (§5.3): it is derived from the release's exports and is bound to the release by digest.

## 3. Terms that must not be confused

| Term | Meaning here | Is **not** |
|---|---|---|
| **release** | an immutable, named, frozen state of a corpus: a manifest, its pinned record sets and the exports they name | a software release; the live state of the corpus on a date |
| **export** | one immutable, content-addressed object of a corpus's own kind (e.g. an EXPORT_READY bundle) | a release; a file a study should open directly |
| **freeze** (of a release) | the recorded act that names a manifest by its digest (§9) | an *acquisition baseline freeze* (CO.PRE.PAN `freeze.py`); a *freeze manifest* of a legacy tree; frozen evidence (gold sets, seals); a *processing-cohort* freeze; the `freeze_status` strings inside CO.RA.PAN export manifests |
| **release gate** | — not a term of this contract — | the test suites named `release_gate` (CO.PRE.PAN) and `production_readiness` (CO.RA.PAN) gate *software changes*; they say nothing about a corpus release |
| **projection** | a deterministic derivative of a release (analysis tables, Parquet views) | a second source of truth |
| **package** | a distribution or archive copy of one release (§11) | the release itself: a package may be rebuilt, a release may not be |
| **study population** | the frozen ids one analysis read, with their selection provenance (§10) | a physical copy of data |

## 4. Identity: canonical form and digests

### 4.1 Canonical values and canonical JSON

Every document and record of this contract consists of **canonical values** only:

- `null`, `true`, `false`;
- integers in the range ±(2^53 − 1);
- strings in Unicode Normalization Form C;
- arrays of canonical values;
- objects with string keys in NFC, no key repeated.

**A number with a fraction is not a canonical value.** A quantity that is not whole is given as an
integer of a smaller unit (`audio_ms`, never hours) or as a string. `NaN` and infinities do not
exist.

The **canonical JSON** of a value is its JSON text with object keys sorted by Unicode code point,
no whitespace between tokens (separators `,` and `:`), strings escaped minimally (non-ASCII
characters written literally, not as `\u` escapes), encoded as UTF-8, without a byte-order mark and
without a trailing newline. In Python:
`json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`.

### 4.2 The two digests

All digests are SHA-256, written as 64 lower-case hexadecimal characters.

| Digest | Of | Definition |
|---|---|---|
| **document digest** | one document (a manifest) | SHA-256 over the canonical JSON of the parsed document |
| **record-set digest** | a set of records (a table) | canonicalise each record; sort the resulting byte strings ascending (bytewise); append one line feed (`0x0A`) to each; concatenate; SHA-256 |

Consequences, all intended:

- the stored whitespace and key order of a document, and the stored order of records, **carry
  nothing**; rewriting a file prettily or sorting its lines differently changes no digest;
- a record set has no duplicates that matter: every record set of this contract has a key (§6, §7,
  §10) and a repeated key is an objection;
- nothing depends on the file bytes of a contract document, so line-ending conversion of a
  manifest cannot change its identity. (Export payload files are different: §4.5.)

Recommended stored forms, not hashed as bytes: a document as indented, key-sorted UTF-8 JSON with
LF and one trailing newline; a record set as its canonical lines in digest order (`*.jsonl`).

### 4.3 No document contains its own digest

A digest of a document is always recorded **by what refers to it**: the freeze record names the
manifest (§9), a later release names its predecessor, a study names its releases (§10), a package
names its release (§11), a pointer names what it stood for. No field of a document is excluded
from its own digest, and there is no "hash of everything except the hash field".

Digests therefore have one direction. The chain is acyclic:

```text
export files ──► member records ──► release manifest ──► freeze record
                                          │
                 document / coverage ─────┤                ┌─► later release (previous_release)
                 records                  ├────────────────┼─► study population
                                          │                ├─► package manifest ──► deposit record (DOI)
            projection (analysis bundle) ◄┘ (by digest)    └─► pointer
```

`release_id` and the manifest digest do different jobs: the **id** is the stable human name by
which a release is cited and found; the **digest** proves which content the name stands for. A
reference always carries both.

### 4.4 Addresses never enter a digest

No digest covers where something lies: no drive, mount point, root directory, host name or URL.
The only paths that are hashed are **contract paths**, relative to the root of the tree they
belong to:

- relative; segments separated by `/`; no leading `/`; no backslash; no colon;
- no empty segment, no `.` and no `..`;
- NFC; no control character; no segment that begins or ends with a space or ends with a dot;
- within one tree no two paths that differ only by letter case.

A file or directory whose name cannot be written as a contract path makes the tree non-conformant
(`PATH_INVALID`); it is not skipped. A symbolic link is not a file of a tree.

### 4.5 The tree digest

The identity of a directory tree (an export, a package, this bundle) is the **record-set digest of
its file listing**: one record `{"path": <contract path>, "sha256": <SHA-256 of the file's bytes>,
"size": <length in bytes>}` per regular file below the root, at any depth. The root's own name,
empty directories, timestamps, permissions and the order in which a file system lists entries do
not enter. Payload files are hashed as bytes, exactly as stored: they are never normalised.

## 5. The release manifest

Schema: [`schemas/release-manifest.schema.json`](schemas/release-manifest.schema.json)
(`crosscorpus-release-manifest/v1`), stored as `RELEASE_MANIFEST.json`.

### 5.1 Fields

| Field | Content |
|---|---|
| `schema`, `contract` | `crosscorpus-release-manifest/v1`, `crosscorpus-release/v1` |
| `corpus_id` | `corapan` or `coprepan` |
| `release_id` | §5.4 |
| `release_kind`, `fixture` | `release` · `provisional_export` · `fixture` (the vocabulary of the analysis contract §8) |
| `modality` | `spoken` or `written` |
| `created_at` | UTC instant, `YYYY-MM-DDThh:mm:ss[.ffffff]Z` |
| `previous_release` | `{state, release_id, release_manifest_sha256}`: the predecessor by id **and** digest, or `not_applicable` for a first release |
| `members`, `documents`, `coverage` | pinned record sets `{schema, records, sha256}`: §6, §7 |
| `changes` | `{added, replaced[{old, new, reason}], removed[{export_id, reason}]}` relative to `previous_release` (§9.3) |
| `selection_policy` | `{state, id, sha256}`: the versioned rule that decided what is in the release, pinned by id and by the document digest of the policy document — or a state saying why not |
| `date_semantics` | `crosscorpus-date-semantics/v1` (§7.2) |
| `token_denominator`, `token_denominator_state` | `crosscorpus-token-denominator/v1`, or `null` with a state when the corpus cannot count under it yet |
| `totals` | `exports`, `documents`, `tokens_counted`°, `audio_ms`° — sums over §6 and §7, re-derived by every check |
| `anchors` | what the ids and positions of this corpus refer to: §8 |
| `vocabularies` | the closed corpus-specific value sets of this release: `date_basis`, `export_schema` |
| `analysis_layer` | `{state, contract, manifest_sha256}`: the `crosscorpus-analysis/v1` bundle projected from this release, by the digest of its release record — or a state |
| `provenance` | §5.3 |

° = stateful: accompanied by `<field>_state`; the value is `null` exactly when the state is not
`known`.

### 5.2 Rules

1. A `release` (not a `provisional_export`, not a `fixture`) pins its selection policy.
2. A token count names its denominator: `tokens_counted` may be `known` — in `totals`, in a document
   or in a coverage cell — only if `token_denominator_state` is `known`.
3. `totals` equal the sums over the member and document records; a sum of a stateful count follows
   §7.3.
4. `anchors` name only kinds of the release's modality (§8); exactly a spoken release has a time
   reference.
5. `analysis_layer` is `known` exactly when it names `crosscorpus-analysis/v1` and a digest.

### 5.3 Provenance

| Field | Content |
|---|---|
| `builder` | the code that *built the release*: `repository`, full `commit` (40 hex), `tool`, `tool_version`. A release is built from a clean, committed tree |
| `pipeline` | `id` and the set of pipeline `versions` under which the member exports were produced |
| `stack` | `{state, id, sha256}`: a pin of the production-stack registry in force, where one exists |
| `models` | `role`, `id`, `revision`° of each model whose output is in the release |
| `configuration` | `id` and `sha256` of each configuration document that determines content |
| `member_code_commits` | the set of code commits under which the member exports were produced |

The release manifest carries the **summary**; the full provenance of an export is in the export
itself and is covered by its tree digest (§6.2). Projections are derivatives: a projection states
the release it was derived from by id and manifest digest, and the release — or, if the projection
is built later, the study (§10) — states the projection by digest. A projection never contains the
digest of something that contains its own.

### 5.4 `release_id`

- begins with `<corpus_id>-`; lower-case ASCII letters, digits, `.` and `-` only
  (`^(corapan|coprepan)-[a-z0-9]+([.-][a-z0-9]+)*$`);
- is assigned once, is never reused and never changes its meaning;
- **the form after the prefix is each corpus's own** and is not unified: CO.RA.PAN plans
  `corapan-YYYY-MM`, CO.PRE.PAN has frozen `coprepan-YYYY.n` and `coprepan-legacy-YYYY-MM`. An id
  is an opaque name; nothing parses a date out of it;
- a suffix beginning with `0000` marks a fixture, and only a fixture.

## 6. Membership: exports

### 6.1 Member records

Schema: [`schemas/release-member.schema.json`](schemas/release-member.schema.json), stored as
`MEMBERS.jsonl`, key `export_id`.

| Field | Content |
|---|---|
| `export_id` | the corpus's own, native identifier of the export object; opaque here |
| `export_schema` | the schema id of the native export format; declared in `vocabularies.export_schema` |
| `tree_sha256` | the tree digest (§4.5) of **all** files of the export |
| `files`, `bytes` | number of files; sum of their sizes |
| `documents` | number of documents of the release this export delivers |

### 6.2 What an export is

An export is an immutable directory tree, written once, addressed by its `export_id` and stored at
`<exports root>/<export_id>/`. Its inner format belongs to its corpus. A release refers to exact
export versions: a member record names the export **and** the digest of every byte in it.

The contract's tree digest is taken over all files and is **in addition to** any native content id.
This is deliberate: a native id may cover less than the whole object. (Observed in CO.RA.PAN: the
`export_id` of a `corapan-export-ready/v1` bundle derives from a digest of the tables only; the
manifest that carries code commit, configuration and model provenance is outside it. Under this
contract the provenance is bound as well.)

### 6.3 A manifest reconstructs nothing by itself

A release is reconstructable only while every export it names is **retained and verifiable**.
Therefore:

- an export named by any frozen release must not be deleted, overwritten or rewritten, for as long
  as that release exists; retention rules of either repository must treat "referenced by a frozen
  release" as a hold;
- a check of a release with exports present recomputes every tree digest; a missing export
  (`EXPORT_MISSING`) and a differing one (`EXPORT_TREE_MISMATCH`) are objections, never warnings;
- a check without access to the exports is allowed (`require_exports = false`) and proves only
  that the manifest side is consistent. It must be reported as such.

## 7. Documents, dates, counting, coverage

### 7.1 Document records

Schema: [`schemas/release-document.schema.json`](schemas/release-document.schema.json), stored as
`DOCUMENTS.jsonl`, key `document_id`.

The **document** is the sampled unit of the corpus, as in the analysis contract §5.3: a recording;
for press one document version (an article in one textual state). A document is delivered by
exactly one member export of a release.

| Field | Content |
|---|---|
| `document_id` | the corpus's own id; opaque; the same string as in the analysis tables |
| `export_id` | the member that delivers it |
| `outlet_id`, `country_id` | as in the analysis contract §5.2; the outlet is registered under the country |
| `date`°, `date_basis`°, `cohort`° | §7.2 |
| `tokens_counted`° | counted tokens under the release's denominator; `not_available` while a corpus cannot count under it |
| `audio_ms`° | duration of the recording in milliseconds; `not_applicable` for a written document, and only for one |
| `source_sha256`° | SHA-256 of the preserved source the document derives from (`anchors.source_kind`): the raw audio master; the extracted text of the document version. It binds the release to preserved material that the release does not contain |

### 7.2 `crosscorpus-date-semantics/v1`

- `date` is a **calendar date in the outlet's local time**, `YYYY-MM-DD`, of the event that
  `date_basis` names (a broadcast; a publication).
- `date_basis` is a value of the release's own closed vocabulary (`vocabularies.date_basis`),
  written as the corpus writes it. The contract does not rank or translate bases.
- **A date and its basis are known together or not at all.**
- `cohort` is the calendar quarter of `date`, `YYYY-Qn`. It is `known` only if `date` is, and then
  contains it. A cohort is a property of the material (a *corpus cohort*), never of processing.
- A retrieval date, crawl date, ingest date, export date or file date **is never a `date`**. A
  document without a defensible date has `date_state` `unknown` (CO.RA.PAN: `UNDATED`) and belongs
  to no cohort; it is not assigned one by default.
- Time of day, time zone and weekday are not part of this contract; they stay in each corpus.

### 7.3 Counting and coverage

Token counts are counts under `crosscorpus-token-denominator/v1` (analysis contract §6.3) and
nothing else: a release that cannot count under that rule says `not_available`; it does not
deliver another count under the same field name. Rates are not stored; a study forms them from
counts and names the denominator.

The **sum of a stateful count** over a set of documents is: `known` with the sum, if every
document's value is known; otherwise `null` with the documents' common state if they share one,
and with `not_available` if they do not. A partial sum is never reported as a total.

Coverage — schema [`schemas/release-coverage.schema.json`](schemas/release-coverage.schema.json),
stored as `COVERAGE.jsonl` — has one record per cell
`country_id × outlet_id × cohort(+state) × date_basis(+state)` that contains at least one document,
with `documents`, `tokens_counted`° and `audio_ms`° summed as above. It is **fully determined by
the document records**: every check re-derives it and objects to any difference
(`COVERAGE_MISMATCH`). A study reads coverage; it never reconstructs it from file names.

Coverage along `production_mode`, speaker or section needs the unit level and therefore the
analysis bundle; it is not part of this table (§16).

## 8. Anchors: what ids and positions refer to

The two corpora keep their own internal models. The contract records, per release, what its ids
are — it does not translate one corpus's units into the other's.

| `anchors` field | spoken (CO.RA.PAN) | written (CO.PRE.PAN) |
|---|---|---|
| `document_kind` | `recording` | `document_version` |
| `unit_kinds` (subset of) | `turn`, `contribution_unit` | `title`, `heading`, `paragraph`, `list_item`, `quote_block`, `caption`, `unstructured_text` |
| `producer_kinds` (subset of) | `speaker_occurrence`, `station_speaker` | — none defined in v1 (§16) |
| `source_kind` | `audio_master` | `extracted_text` |
| `source_included` | `false` | `false` |
| `offset_reference`° | what a character offset is an offset into | the same, for the unit text |
| `time_reference`° | the timeline that `start_ms` / `end_ms` refer to | `not_applicable` |

Rules:

- A turn, a contribution unit, a paragraph, a technical segment boundary and a linguistic unit are
  **different things**. No kind of one modality is valid in a release of the other; none is named
  "utterance" or "segment"; a boundary an instrument made is not promoted to a linguistic one by
  being listed here (analysis contract §5.4).
- The three levels `document`, `unit`, `producer` are the levels of the analysis tables. They say
  where an id sits in a corpus's own hierarchy, not that the things at one level are comparable
  across corpora.
- Ids below the document are stable **within a release** only (analysis contract §6.1).
- Source audio and fetched pages are never part of a release (`source_included` is `false` in v1).
  A document is tied to its preserved source by `source_sha256`.

## 9. Freeze, correction, versions

### 9.1 States of a release

```text
(building)  ──►  FROZEN  ──►  [SUPERSEDED by a later release]   (a statement of the later release)
```

- While a manifest is being built, it is not a release, has no reserved id and must not be cited.
- A release **exists** when its freeze record exists: `RELEASE_FREEZE.json`
  ([schema](schemas/release-freeze.schema.json)), naming `corpus_id`, `release_id`,
  `release_manifest_sha256`, `frozen_at`, `frozen_by`. It is written after the manifest, by an
  explicit act of a person, after a check with every export present has passed.
- A `provisional_export` has no freeze record and is not a release. It exists so that a corpus
  without release machinery can hand over a pinned state honestly.

### 9.2 Immutability

After the freeze, nothing the freeze transitively names changes: not the manifest, not a pinned
record set, not a member export. A check that finds the manifest digest different from the freeze
record objects (`FREEZE_MISMATCH`). Human-readable release notes are not named by the manifest; an
erratum is a new, dated note beside the release, never an edit of the release.

### 9.3 Correction

- A corrected export is a **new export object** with a new `export_id`. The old object stays where
  it is, because an earlier release names it.
- A correction reaches users through a **later release** with a new `release_id`, whose
  `previous_release` names the predecessor by id and digest and whose `changes` account for every
  difference of membership: `added`, `replaced` (old → new, with a reason), `removed` (with a
  reason). A check given both releases objects to an unaccounted difference
  (`MEMBERSHIP_INCONSISTENT`) and to a predecessor that is not the named one
  (`PREVIOUS_RELEASE_MISMATCH`).
- A release is never withdrawn by deletion. If a release must not be used any more, that is said
  in a dated notice beside it and in the next release's notes; its manifest and exports stay.
- A new pipeline version does not by itself change a release or make one obsolete (forward-only;
  backfill is a separate decision in both repositories).

### 9.4 Versions of the contract

- Every document names its `contract` and its `schema`. An implementation of
  `crosscorpus-release/v1` **refuses by name** (`CONTRACT_VERSION_UNSUPPORTED`) any document of
  another contract or schema version. It never reads one "as far as it goes".
- While the contract is a draft, a revision of `v1` is identified by its bundle digest (§14). After
  adoption, any change that alters the meaning of a field, a digest or a verdict is `v2`; a
  release frozen under `v1` stays a `v1` release and stays checkable by a `v1` implementation.

## 10. Study populations

Schema: [`schemas/study-population.schema.json`](schemas/study-population.schema.json), stored as
`STUDY_POPULATION.json`, with `SELECTED.jsonl` and `EXCLUDED.jsonl`
([record schema](schemas/study-selection-record.schema.json)).

### 10.1 What a study pins

| Field | Content |
|---|---|
| `study_id`, `population_id` | lower snake case; a study may have several populations |
| `inputs` | one entry per corpus: `corpus_id`, `release_id`, `release_manifest_sha256`, and `analysis_layer` `{state, contract, manifest_sha256}` — the analysis bundle actually read, if any |
| `selection` | provenance of the choice: `kind`, `tool` (`id`, `version`), and for a declarative selection its `filters` |
| `selected`, `excluded` | pinned record sets of the frozen ids |
| `exclusion_reasons` | the closed vocabulary of this population's exclusion reasons |
| `totals` | per corpus: `selected_records`, `documents`, `tokens_counted`°, `audio_ms`° |
| `analysis_code` | `repository`°, `commit`° of the analysis code |

A study population is cited by `study_id`, `population_id` and the document digest of its manifest.
Together with the release pins it identifies the analytical input completely:
*release id + manifest digest + population digest (+ analysis code)*.

### 10.2 Selection records

`corpus_id`, `release_id`, `level` (`document` · `unit` · `producer`), `id_kind`, `id`,
`document_id`, `reason`.

- `id_kind` is an anchor kind **the pinned release declares** (§8). A `turn` in a written release,
  a `paragraph` in a spoken one, is an objection (`ANCHOR_KIND_INVALID`).
- `document_id` is the document the id belongs to; it must be in the pinned release
  (`POPULATION_NOT_RESTORABLE`). At level `document`, `id` is the `document_id`.
- Exactly an excluded record states a `reason`, from `exclusion_reasons`. An id is selected or
  excluded, never both, never twice.

**The frozen ids are the identity of the population; the selection is its provenance.** A
population is restored by resolving its ids against the pinned release — not by re-running a tool
and hoping for the same answer.

### 10.3 Selection kinds

| `kind` | Meaning | What a check can establish |
|---|---|---|
| `declarative_filter` | documents chosen by `crosscorpus-document-filter/v1` | the filter is re-run on the pinned document records: *selected ∪ excluded* must equal its result exactly (`POPULATION_SELECTION_MISMATCH`) |
| `external_tool` | chosen by a query or program outside this contract, recorded by `tool` id and version | that every id resolves; not that the tool would give the same ids again |
| `enumerated` | listed by hand | that every id resolves |

`crosscorpus-document-filter/v1`: per corpus a conjunction (`all`) of clauses over fields of the
document record. `country_id`, `outlet_id`, `export_id`, `cohort`, `date_basis`: `in` (a list);
`date`: `from` and/or `to` (inclusive); `tokens_counted`, `audio_ms`: `min` and/or `max`
(inclusive). **A clause on a stateful field is not satisfied by a record whose value is not
known**: an undated document is in no date range, by no default. A declarative filter selects
documents only.

`totals` are re-derived: the records and distinct documents always; `tokens_counted` and
`audio_ms` when the corpus's selection is at document level — below the document they are
`not_available`, because the document records cannot give them.

## 11. Distribution and archive packages

Schemas: [`package-manifest`](schemas/package-manifest.schema.json),
[`package-file`](schemas/package-file.schema.json),
[`release-pointer`](schemas/release-pointer.schema.json).

### 11.1 Principle

A package is a **copy for a purpose** of exactly one frozen release. It can be rebuilt from the
release at any time and is never a second source of truth. `package_kind`:

| Kind | Purpose | `exports` |
|---|---|---|
| `distribution` | read-only team access | `included` or `by_reference` (the exports stay in preservation) |
| `archive` | long-term deposit in a repository (LinguRep / NFDI) | `included` — an archive package is self-contained |

### 11.2 Layout and file list

```text
<package>/
├─ PACKAGE_MANIFEST.json      names the release by id and manifest digest; metadata
├─ PACKAGE_FILES.jsonl        {path, sha256, size, role} of every other file
├─ release/                   RELEASE_MANIFEST.json, RELEASE_FREEZE.json, MEMBERS.jsonl, DOCUMENTS.jsonl, COVERAGE.jsonl
├─ exports/<export_id>/…      the member exports (when included)
└─ …                          projections, documentation, schemas, licence
```

`PACKAGE_FILES.jsonl` lists every file of the package except the two that describe it, and is
pinned by the package manifest. A package is exactly its listed files: a missing, extra or
different file is an objection (`PACKAGE_INCOMPLETE`). Roles: `release_manifest`, `release_freeze`,
`release_members`, `release_documents`, `release_coverage` (under `release/`), `export_payload`
(under `exports/`), `projection`, `documentation`, `schema`, `licence`. The release inside a
package is checked as a release (§13.1) — with every export when they are included.

### 11.3 No source media

`contains_source_media` is `false` in v1, and a check objects (`PACKAGE_FORBIDDEN_CONTENT`) to any
listed file with an audio or video suffix (`.wav`, `.flac`, `.mp3`, `.m4a`, `.mp4`, `.ogg`, `.opus`,
`.aac`, `.wma`, `.aif`, `.aiff`, `.webm`). Publishing source audio needs a separate legal and
repository decision and a new contract version. `metadata.source_media_statement` says, in prose,
what the release derives from and that the source is not part of the package.

A package must contain no absolute path, no credential and no transient operational state. Only
the first of these can be checked mechanically here (contract paths, §4.4); the rest is a gate of
the publishing step.

### 11.4 Citation metadata

The bibliographic metadata live in the **package manifest**, not in the release manifest: a
repository's metadata rules may change and a deposit may be re-described without a corpus state
changing. `metadata` (oriented at the DataCite kernel; the receiving repository's own template
takes precedence): `title`, `description`, `resource_type` (`Dataset`), `version` (the
`release_id`), `languages`, `creators` (`name`, `orcid`°, `affiliation`°), `publisher`°,
`publication_year`°, `identifier` (`scheme`, `value`°), `rights.licence`°, `access.level`°
(`open` · `registered` · `restricted` · `embargoed`), `related_identifiers`, `funding`,
`source_media_statement`.

A persistent identifier (DOI) is assigned **after** deposit and is therefore never in a release
manifest. It is recorded in the deposit copy of the package manifest and in the repository's
records; a later release may cite it through `related_identifiers`. Licence, access level,
publisher and identifier are institutional decisions: until taken they are `undecided` or
`not_available`, never guessed.

A pointer (`RELEASE_POINTER.json`, e.g. in a `latest/` view) names the release it stood for by id
and manifest digest and when it was generated. It is replaced, not edited, and is never an
identity.

## 12. Schemas

The files under `schemas/` are JSON Schema (draft 2020-12) restricted to this subset, so that both
repositories can evaluate them without adding a dependency and so that a general validator and a
minimal one cannot disagree:

`$schema`, `$id`, `$defs`, `$ref` (local, `#/$defs/<name>`), `title`, `description`, `type`,
`const`, `enum`, `pattern`, `required`, `properties`, `additionalProperties` (`false`), `items`,
`minItems`, `minimum`, `minLength`.

An implementation refuses a schema that uses any other keyword. Every object is closed
(`additionalProperties: false`): an unknown field is an objection, not an extension point. Rules a
schema of this subset cannot state — a value is null exactly when its state is not `known`; sums;
references between records — are stated in this text and enforced by the checks (§13).

## 13. Conformance

### 13.1 Checks and their order

A check reads and never repairs. It runs in ordered phases; **a phase that objects ends the
check**, because later phases assume what earlier ones established. The verdict of a check is the
set of codes it reports.

**Release** (`release directory`, optionally `exports root`, optionally the previous release):

1. the manifest parses strictly (`NON_CANONICAL_VALUE`), is of this contract and schema
   (`CONTRACT_VERSION_UNSUPPORTED`), satisfies its schema and the rules of §5.2
   (`SCHEMA_VIOLATION`) and §5.4 (`RELEASE_ID_INVALID`);
2. the three pinned record sets exist (`REFERENCE_MISSING`), satisfy their schemas and are exactly
   the pinned sets (`PIN_MISMATCH`);
3. membership (§6.1, §9.3: `MEMBERSHIP_INCONSISTENT`, `PREVIOUS_RELEASE_MISMATCH`) and documents
   (§7.1, §7.2: `DOCUMENT_INCONSISTENT`); if both hold, coverage (`COVERAGE_MISMATCH`) and totals
   (`TOTALS_MISMATCH`);
4. if exports are required or supplied: every member export is present (`EXPORT_MISSING`), is a
   tree of contract paths (`PATH_INVALID`) and has the named tree digest, file count and size
   (`EXPORT_TREE_MISMATCH`);
5. the freeze record — required unless the release is a `provisional_export` — exists
   (`REFERENCE_MISSING`) and names this manifest (`FREEZE_MISMATCH`).

**Study population**: (1) the manifest as above; (2) every pinned release is available
(`REFERENCE_MISSING`), passes the release check without exports and is the pinned one
(`RELEASE_PIN_MISMATCH`); the two record sets are the pinned ones; (3) every record (§10.2:
`POPULATION_NOT_RESTORABLE`, `ANCHOR_KIND_INVALID`, `POPULATION_SELECTION_MISMATCH`); (4) the
declarative selection re-derived (`POPULATION_SELECTION_MISMATCH`) and the totals
(`TOTALS_MISMATCH`).

**Package**: (1) the manifest; (2) the file list is the pinned one; (3) paths, forbidden content
and roles (`PATH_INVALID`, `PACKAGE_FORBIDDEN_CONTENT`, `PACKAGE_INCOMPLETE`); (4) the files on
disk are exactly the listed ones (`PACKAGE_INCOMPLETE`); (5) the release inside it, as above, and
it is the named one (`RELEASE_PIN_MISMATCH`).

The codes above are the closed vocabulary of this contract version.

### 13.2 Reference fixtures and vectors

`fixtures/` holds, for each corpus, a synthetic archive package (a frozen release with two exports
and three documents, one of them undated) and a study population with one filter and one stated
exclusion; `fixtures/joint/` holds one population over both corpora below the document level.
**Everything in them is invented**; the stub files inside the exports are not instances of any
native export format.

[`conformance/VECTORS.json`](conformance/VECTORS.json) holds what every implementation must
reproduce: the canonical JSON and digests of fixed values; the digests of the fixtures; and a list
of **cases** — a target, a check, a list of declared manipulations of a copy of `fixtures/`, and
the exact set of codes the check must then report. The operations are described in the file.

An implementation conforms to this bundle when, in its own repository's test suite, it reproduces
every digest and every case verdict. Passing proves **reproducible identity and technical
robustness** of the mechanics on synthetic data. It proves nothing about any real export and is no
scientific validation of either corpus.

## 14. One contract, two repositories

### 14.1 The bundle and its digest

The contract a repository works against is this directory, byte for byte. Its identity is the
**bundle digest**: the tree digest (§4.5) of this directory. All bundle files are LF and are stored
verbatim (no line-ending conversion: the bundle is marked `-text` for git).

### 14.2 How both repositories obtain and pin it

- **One canonical home.** The bundle is edited in exactly one place: CO.RA.PAN,
  `contracts/crosscorpus-release-v1/`. (The canonical home of `crosscorpus-analysis/v1` stays
  CO.PRE.PAN.)
- **The other repository holds a verbatim copy** at the same relative path, taken from a named
  commit of the canonical home, and never edits it. No new shared package and no third repository
  exist for this.
- **Each repository records the digest it works against** in its own tracked pin file (CO.RA.PAN:
  `config/crosscorpus/contract_pins.json`), and its test suite recomputes the digest of its copy
  and fails on any difference. A copy can therefore not drift silently: an edit in the wrong place
  fails that repository's own tests.
- **Same version** means: the two pin files hold the same bundle digest. A study or a release
  record that needs to say which contract revision it was checked against quotes that digest.
- Each repository **implements the checks itself**, in its own code base and conventions; the
  implementations share no code and are held together by `conformance/VECTORS.json`.

### 14.3 From draft to adopted

1. The canonical home changes the bundle; its pin changes with it, in the same commit.
2. The other repository takes the new copy and moves its pin, in one commit that also runs the
   vectors against its implementation.
3. **Freeze of the contract**: when both implementations pass the same bundle digest and both
   projects have recorded the adoption (a decision record in each: `D…` in CO.RA.PAN, `CPD-…` in
   CO.PRE.PAN, each quoting the digest), the status in both pin files becomes `ADOPTED`. From then
   on the bundle of `v1` does not change (§9.4).

## 15. Technical decisions taken in this draft

Each is a decision of this draft, open to review until adoption; none is a scientific decision.

| # | Decision | Reason |
|---|---|---|
| T1 | The release contract is a separate contract id in the existing `crosscorpus-` namespace and **extends** `crosscorpus-analysis/v1` by reference | one specification per subject; the analysis contract already owns tables, states, denominator |
| T2 | No self-hash: the manifest has no `manifest_sha256` field (the plan's §6.4 sketch and the analysis contract's release record have one) | a field excluded from its own digest needs a special rule in every implementation; recording the digest in the referrer needs none and cannot be circular |
| T3 | Digests are taken over canonical content, not over the file bytes of contract documents | line endings and pretty-printing have broken byte pins before in CO.RA.PAN (autocrlf); a content digest cannot break that way |
| T4 | No fractions in hashed documents; durations in integer milliseconds | a float has no single serialisation across languages; the plan's `audio_hours` becomes `audio_ms` |
| T5 | Members, documents and coverage are pinned record sets beside a small manifest, not inline lists | the manifest stays small and of constant size as the corpus grows |
| T6 | A member is bound by a tree digest over **all** files of the export, in addition to its native id | the native CO.RA.PAN id does not cover the provenance manifest (§6.2) |
| T7 | The form of `release_id` after the corpus prefix is not unified | the two projects' forms differ (`YYYY-MM` vs `YYYY.n`) and nothing needs them equal; unifying would rename a frozen id form on one side |
| T8 | Citation metadata and the DOI live in the package / deposit record, not in the release manifest | a DOI exists only after deposit; bibliographic wording may change without a corpus state changing |
| T9 | The frozen ids are the identity of a study population; the selection is provenance | a query re-run later may not return the same ids; ids always can be resolved |
| T10 | Coverage is derived from the document records and checked, not delivered independently | a coverage table that can disagree with the data is worse than none |
| T11 | Schemas in a small JSON Schema subset, evaluated by each repository's own code | neither repository depends on a schema library (CO.PRE.PAN has no runtime dependency at all) |
| T12 | The implementations share vectors, not code; the bundle has one canonical home and is pinned by digest | the operator's constraint: no shared package, no third repository; copies must not drift |

## 16. Open — not decided here

Nothing below is guessed in this draft. Each item names who decides.

| # | Item | Kind |
|---|---|---|
| Q1 | Whether a `release` (not a provisional export) may be frozen while `tokens_counted` is `not_available`. The draft allows it and makes the state explicit. CO.RA.PAN cannot count under the shared denominator today | joint, scientific |
| Q2 | The analysis contract's sentence "a study records `release_id` and `manifest_sha256` — nothing else identifies its input" (§8 there) and its embedded `manifest_sha256` field. Under this contract a study pins the **release manifest digest** and, where it reads analysis tables, the digest of that bundle's release record. The wording there needs an amendment in CO.PRE.PAN (CPD-0008), which this run could not make | joint, editorial |
| Q3 | Producer anchors for press (author, byline): no id and no vocabulary exists in CO.PRE.PAN; `producer_kinds` is empty for `written` | CO.PRE.PAN |
| Q4 | CO.PRE.PAN's native export object (granularity, `export_id`, schema id): its release layer is not built. The fixture uses an invented `coprepan-fixture-export/v1` | CO.PRE.PAN |
| Q5 | Coverage below the document (`production_mode`, speaker, section): needs the analysis bundle; a second coverage table on that level is not specified | joint |
| Q6 | The selection policy *document*: only its pin is specified. What a policy must contain, and the scientific population of the first release of either corpus (boundary, eligibility), are not specified | scientific, per corpus and joint |
| Q7 | Licence, access level, publisher, identifier model (version DOIs, concept DOI, parent record) and the metadata template of LinguRep | institutional |
| Q8 | Columnar storage (Parquet) of record sets and projections. The digests are defined on content and do not depend on it; a Parquet file's *byte* digest is not stable across writers and must not be used as identity | technical |
| Q9 | A machine-readable notice for a release that must no longer be used (§9.3 specifies only that it is a dated note) | joint, technical |
| Q10 | Whether the corpus ids of this contract ever grow beyond `corapan`, `coprepan` | joint |
