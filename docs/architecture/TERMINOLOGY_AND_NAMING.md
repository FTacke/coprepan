# Terminology and Naming

**Status: NORMATIVE** — decided by [CPD-0002](../decisions/CPD-0002_terminology-and-naming-model.md)
(2026-10-06). This is the only authoritative statement of COPREPAN 3.0 terms, names and identifier
rules. Other documents link here and do not restate the rules.

Naming is part of the foundation, not a later cleanup: the legacy system and the cross-corpus
studies show what unmanaged names cost (three country conventions, eight column names for a
country, one outlet under two slugs, ids that repeat across files). Evidence: audit §15.

The model **extends the conventions CO.RA.PAN 3.0 has already decided** to the press corpus and
introduces no parallel convention. Taken over, as read in `corapan_playground` on 2026-10-06: the
S0/D9 vocabulary rules V1–V4 (canonical machine vocabulary is English lower-case `snake_case`;
legacy values are immutable; a legacy mapping is a hypothesis until human-audited; no legacy or
German/Spanish token in a canonical enum) and registry rules R1–R4 (broadest stable namespace
first; alpha-2 lower-case country token; the registry is the source of truth, an id is never
derived from a display name); the `radio_id` pattern; and its practice of upper-case tokens for
states of a state machine.

---

## 1. Human-facing names

| Name | Use |
|---|---|
| **CO.RA.PAN** | the radio corpus, as a scholarly object (prose, citations, titles) |
| **CO.PRE.PAN** | the press corpus, as a scholarly object (prose, citations, titles, release names) |
| **CO.RA.PAN 3.0** | the current pipeline generation of the radio corpus, written as its repository writes it |
| **COPREPAN 3.0** | the pipeline generation and engineering project built in this repository |
| **Legacy COPREPAN** / "the legacy system", "the legacy corpus" | the system and data under the legacy repository; never "COPREPAN 1.0" or "2.0" |

Style rules:

1. **CO.PRE.PAN names the corpus; COPREPAN 3.0 names the generation.** The dotted form is the
   brand of the corpus and is used wherever the corpus is cited ("CO.PRE.PAN release 2027.1").
   The undotted form with the generation number is the established working name of this pipeline
   and repository. Both are human-facing; neither is a machine value.
2. The press pipeline carries "3.0" to mark the generation it shares with CO.RA.PAN 3.0. No "1.0" or
   "2.0" is retro-assigned to the legacy press system.
3. Existing spellings in historical files (`CORAPAN`, `CO.PRE.PAN`, `COPREPAN`) are never
   rewritten. The style applies to new text only.
4. Upper-case undotted forms (`COPREPAN`, `CORAPAN`) are **not** used as new machine values.
   The one fixed exception is the environment-variable prefix (§5.7), which is upper case by
   convention of the medium.

How the generation is branded in publications ("COPREPAN 3.0" or "CO.PRE.PAN 3.0") is an operator
style choice that changes no identifier; see master plan §13, O-7.

## 2. Levels that must never be conflated

| Level | Meaning | Machine form | Example |
|---|---|---|---|
| **corpus** | one of the two corpora | `corpus_id` | `coprepan`, `corapan` |
| **pipeline generation** | how material was produced | `generation` — an attribute | `legacy`, `v3` |
| **release** | a frozen, citable selection of a corpus | `release_id` | `coprepan-2027.1`, `coprepan-legacy-2026-06` |
| **schema / contract** | a file, table or interface format | `<namespace>-<thing>/v<n>` | `coprepan-fetch-record/v1` |
| **package version** | the version of this repository's code | PEP 440 | `0.1.0` |
| **study** | an analysis that reads releases | `study_id`, lower snake case | — |

Rules:

- **A generation number is not a release number and not a schema version.** "3.0" / `v3` never
  appears in a `corpus_id`, a `release_id` or a schema id. `corpus_id` is `coprepan`, never
  `coprepan3`.
- A schema id carries its own `v<n>`, which is the version of that schema and nothing else.
  No new id may use `v3` to *mean* the generation. (The legacy schema ids `corapan-ann/v3`,
  `corapan-transcript-ann-v3.2` are file-schema versions of the CO.RA.PAN 1.0 corpus; they stay as
  they are and are the cautionary example.)
- Releases are date-based (`<corpus_id>-<YYYY>.<n>`), forward-only and immutable. The frozen legacy
  state has the fixed id `coprepan-legacy-2026-06`.
- Schema namespaces: `coprepan-` for press-specific formats minted here; `corapan-` belongs to the
  sibling repository and is never minted here; shared cross-corpus contracts get one neutral
  namespace whose name is **not yet fixed** (working name `crosscorpus-`; a joint decision, master
  plan §13, O-6).

## 3. Core terms

One term per level. A term is not reused for a second level, in prose or in a field name.

### 3.1 Objects

| Term | Definition | Press (this corpus) | Radio (CO.RA.PAN 3.0) |
|---|---|---|---|
| **corpus** | the body of material under one `corpus_id` | CO.PRE.PAN | CO.RA.PAN |
| **outlet** | the publishing institution as an editorial unit | publication (newspaper, digital-native outlet, …) | station |
| **channel** | a place where an outlet lists its items | RSS/Atom feed, sitemap, sitemap index, section page, archive | programme feed, stream |
| **channel document** | the bytes of a channel as retrieved at one instant | feed or sitemap response | — |
| **discovery event** | the observation that a URL was listed in a channel document | one URL in one channel document | — |
| **fetch** | one retrieval event: one request, one response | HTTP request/response for one URL | one capture or download |
| **source object** | the acquired bytes, addressed by their hash | the exact response body | source asset |
| **document** | the editorial unit that is sampled | article | recording |
| **document version** | one textual state of a document | one distinct extracted text of an article | one pipeline answer |
| **unit** | the level between document version and sentence, with a declared `unit_kind` | block: `title`, `paragraph`, `heading`, `list_item`, `quote_block`, `caption`, `embed`, … | turn, contribution unit |
| **sentence** | a sentence as segmented by the NLP instrument | follows authorial punctuation inside a block | follows ASR/repair punctuation with forced terminals |
| **token** | a token as produced by the NLP instrument | same schema | same schema |
| **pack** | a sealed container of fetch records | WARC pack | — |
| **release** | a frozen selection of document versions with its layers, manifest and policy | same concept | open in CO.RA.PAN |
| **corpus record** | a document version admitted to a release: (`release_id`, `document_version_id`) | | |
| **study** | an analysis that reads one or more pinned releases | | |

At analysis level the sampled unit of the press corpus is the **document version** (an article in
one textual state). "Article" is the press specialisation of *document* and is used in prose; field
names use `document`.

### 3.2 Time strata and work batches

| Term | Definition |
|---|---|
| **corpus cohort** | a time stratum of the *material*: the calendar quarter of the publication date in the outlet's local time. A scientific property. |
| **processing cohort** | a batch of *work*: what one run or wave processed. An operational property; never used as a date and never as a stratum. |
| **date basis** | the evidence a date value rests on. Every date carries its basis; an unknown publication date is `unknown`. The fetch instant is never a publication date. |

### 3.3 Processes

| Term | Definition | Must not be used for |
|---|---|---|
| **acquisition** | discovery + fetch: obtaining channel documents and source objects | |
| **preservation** | sealing, hashing, promoting and verifying source objects on the preservation root | storing a derived layer |
| **extraction** | deterministic transformation of a source object into typed blocks and metadata with basis | cleaning or repairing text |
| **normalisation** | recorded, reversible-by-record character-level operations on extracted text (Unicode NFC, whitespace) | lexical repair; any change of wording |
| **annotation** | output of the shared NLP instrument: sentences, tokens, lemma, tags, morphology, dependencies | project-specific labels |
| **enrichment** | an additional layer keyed on stable ids (verbal complex, section mapping, article type, syndication clusters), each with its own version and validation status | a field written into an annotation layer |
| **admission** | assigning *labels* to a document version (article / not article, access class, language, length, type, date basis) with reasons | deleting or filtering material |
| **selection** | choosing which admitted document versions enter a release or a study, under a versioned, recorded policy | anything done at crawl time |

**Transformation** is the generic term for extraction, normalisation, annotation and enrichment:
every one of them produces a *derived layer*.

### 3.4 Reserved and retired words

| Word | Rule |
|---|---|
| **raw** | reserved for source objects (fetched bytes). Extracted text is never "raw" (the legacy `json_raw`, `text.body.raw` mean extracted text and are not carried over). |
| **source** | one meaning only: the origin of bytes or of a value (`source object`, `date_basis`). It is retired as a name for the outlet (legacy `source_slug`, `sources` table). |
| **segment** | not used: it means an utterance in radio 1.0 and a paragraph in legacy press. Use `unit` with a `unit_kind`. |
| **batch** | never a daily export file. A work batch is a processing cohort. |
| **register** | a study-side variable derived from `modality` and `production_mode`; never a name for a press section. |
| **collection**, **dataset**, **sample** | not levels of the model. A dataset is a release or an export of one; a sample is a study-side selection with its own id. |
| **source_file**, **file_id** | container names are not identifiers. A container file is never a key. |

## 4. Shared register variables

Cross-corpus analysis places both corpora on two declared axes; neither is machine-inferred for
press.

| Field | Values | Press |
|---|---|---|
| `modality` | `spoken`, `written` | `written` |
| `production_mode` | for radio the values of CO.RA.PAN 3.0's `speech_mode` (`unscripted`, `scripted`, `prerecorded`, `unknown`; its D37); for press one value | `written_edited` |

`production_mode` is the working name of the *shared* field. CO.RA.PAN 3.0 itself calls its
dimension `speech_mode` and keeps a separate `speech_mode_applicability`; how the shared field is
named and how applicability is carried is fixed with the cross-corpus contract (master plan §13,
O-6), not here. The press value `written_edited` is decided.

The three research conditions of the joint infrastructure are `spoken + unscripted`,
`spoken + scripted` and `written + edited`. The legacy study labels (`corapan_libre`,
`corapan_lectura`, `coprepan_written`) are a compatibility view derived from these two fields
(§7), never canonical values.

**Linguistic variety is never a machine label.** It is what the studies measure; the outlet's
country is the metadata.

## 5. Identifier rules

Principle: **slugs and display names may evolve; persistent ids may not.** An id is permanent once
minted. Display names, domains and human-readable slugs are attributes with history.

### 5.1 `country_id`

ISO 3166-1 alpha-2, lower case (`ar`, `es`, `pr`) — the CO.RA.PAN 3.0 decision, adopted unchanged —
in every canonical id and table. Alpha-3 upper case (`ARG`, `PRI`) is a display and compatibility
label only. Sub-national variety is never part of a country token: `region` and `city` are fields.

Which countries the corpus covers, and whether both corpora share one list, is open (master plan
§13, O-5). The *form* of the id is decided.

### 5.2 `outlet_id`

`{country_id}_{outlet}` with the pattern `^[a-z]{2}_[a-z0-9]+(?:_[a-z0-9]+)*$` — the `radio_id`
pattern of CO.RA.PAN 3.0, by value. ASCII, lower case, underscore-separated.

- Assigned in the outlet registry, **never derived from a display name at run time**. A slug helper
  may propose a value at registration; the registered value is what counts.
- Unique across countries by construction (`es_el_pais`, `uy_el_pais`).
- The pattern checks form, not registration: the legacy slug `el_pais` is lexically a well-formed
  id. Only the registry establishes that a value is an assigned `outlet_id` under a real
  `country_id`; code that accepts an outlet id resolves it through the registry.
- A renamed institution keeps its `outlet_id`; the registry records display names with validity
  dates. A merger or split creates new outlets with a recorded succession relation.
- A publication with several domains or editions is one outlet with `web_origins[]` and an
  `edition` attribute on the document. An edition becomes its own outlet only when it is
  editorially independent, recorded with the basis of that judgement (`same_outlet_basis`).
- Publisher group is an attribute (`outlet_group`), the handle for ownership and syndication
  analyses.

### 5.3 `channel_id`

Registry-assigned, scoped to its outlet: `{outlet_id}:ch:{slug}`. The slug is a short registry
label (`rss_portada`, `sitemap_news`). A channel whose URL changes keeps its id and records the URL
history; a channel that is replaced gets a new id.

### 5.4 Event and content ids

| Id | Identifies | Form (target; serialisation frozen in Phase 1) | Stability |
|---|---|---|---|
| `fetch_id` | one retrieval event | `ft1:` + hash over (requested URL, fetch-start instant, body `sha256`) | permanent, unique per event |
| source object | the bytes | `sha256` of the response body | content address: the same bytes fetched twice are one object, two fetches |
| `document_id` | the article as an editorial unit | `{outlet_id}:doc:{hash16(canonical URL key)}` | stable across re-fetches and updates |
| `document_version_id` | one textual state | `{document_id}:v:{hash12(extracted text)}` under a named extractor version | new id whenever the text differs |
| `unit_id` | a block of a document version | `{document_version_id}:UNIT:{i}` | bound to the version |
| `sentence_id` | a sentence | `{document_version_id}:SENT:{i}` | bound to the version |
| `token_id` | a token | `{document_version_id}:TOKEN:{i:08d}` (the form CO.RA.PAN 3.0 uses under its turn id) | bound to the version |
| `release_id` | a frozen release | `coprepan-<YYYY>.<n>`; `coprepan-legacy-2026-06` | permanent, never reused |
| corpus record | a version in a release | (`release_id`, `document_version_id`) | fixed per release |

Rules:

- Content-addressed ids are used where the content is the identity (source objects, document
  versions); registry-assigned ids where an institution is (countries, outlets, channels).
- Sentence, unit and token ids hang on the document version. They are unique across the corpus by
  construction and **never positional in a container file** (the legacy ids were, and shifted).
- The **canonical URL key** keeps the path's case, records its inputs and its rule-set version, and
  keeps a superseded key as an alias (target architecture §6).
- "A digest must cover what it claims to identify": an id or hash field is named for what it
  actually covers (the legacy `article_id` was documented as a content hash and was a URL hash).
- The column "Form" is the decided *target*. The exact byte-level serialisation (hash function
  inputs, encodings, separators, truncation lengths) is frozen with tests by the Phase-1 identity
  run and recorded in a decision; until then no id of these kinds is minted for production
  material.
- *Added 2026-10-07:* the serialisation is frozen by
  [CPD-0003](../decisions/CPD-0003_id-serialisation-and-canonical-url-key.md) and stated in
  [`docs/identity/INDEX.md`](../identity/INDEX.md): SHA-256 over canonical JSON, `fetch_id` with
  the full digest, zero-based unit, sentence and token indexes. No id has been minted yet: no
  stage exists that would record one.

### 5.5 Vocabulary values

- Canonical machine values are English, lower-case snake case (`national_reference`,
  `hard_paywall`, `native_v3`).
- Status tokens of state machines are upper case (`RAW_PRESERVED`, `FETCH_FAILED`).
- Closed vocabularies carry explicit value states (`unknown`, `unavailable`, `not_applicable`)
  instead of nulls or empty strings.
- An axis that cannot be measured yet reports `NOT_YET_MEASURABLE`, never a zero and never a guess.
- *Added 2026-10-07 (registry schema `coprepan-outlet-registry/v1`):* `registration_status` of a
  registry entry is `proposed` or `registered`. A proposed `outlet_id` is not yet an assigned id
  and does not resolve; it becomes permanent when a reviewer registers it. The frozen value sets of
  the registry vocabularies are listed in [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md) §4.

### 5.6 `provenance_class`

| Value | Meaning |
|---|---|
| `native_v3` | acquired by the 3.0 pipeline: preserved source object, full chain |
| `legacy_refetched` | a legacy URL re-fetched by the 3.0 pipeline; full chain from the re-fetch on, linked to its legacy record, the fetch delay recorded |
| `legacy_text_reannotated` | legacy extracted text carried through 3.0 normalisation and NLP: no source object, known extraction defects, flagged |
| `legacy_frozen` | the legacy corpus exactly as annotated on 2026-06-13, served from the frozen release |

Pooling rules: docs/legacy/INDEX.md §4.

### 5.7 Configuration and environment

One prefix: `COPREPAN_` (`COPREPAN_PRESERVATION_ROOT`, `COPREPAN_WORKSPACE_ROOT`, …). No absolute
workstation or network path in a tracked file of domain logic or configuration; tracked config
holds logical roles and `${ENV}` references only.

### 5.8 Repository, package, decisions, files

- Repository names: lower case, underscore. Python package: `coprepan` (the corpus, not the
  generation).
- Decisions: own namespace `CPD-<nnnn>` so they cannot collide with the CO.RA.PAN `D<nn>` sequence
  (docs/decisions/README.md).
- Run reports: `docs/agent-runs/YYYY-MM-DD_short-descriptive-title.md`.

## 6. Legacy names: forward-only

**Nothing historical is renamed.** Legacy names and historical ids are never silently rewritten;
every legacy name resolves through a versioned mapping whose entries carry a `mapping_status`
(`hypothesis` / `human_audited`).

| Legacy term | Canonical term | Mechanism |
|---|---|---|
| alpha-3 country codes (`ARG`, `PRI`, `ESP-SEV`) | `country_id` (+ `region`) | legacy country-code table |
| `newspaper_code`, `source_slug`, `source_slug_ascii`, directory names — every observed variant, including accented and duplicate forms | `outlet_id` | outlet registry `legacy_aliases[{country_code, slug}]`, one row per observed variant |
| `article_id` (`sha256:` of the lower-cased URL) | `document_id` | alias column `legacy_article_id` on documents re-acquired or re-annotated from legacy; never a key in 3.0 |
| legacy `token_id`, `sentence_id`, `segment_id`, `file_id`, `source_file` | none | valid only inside `coprepan-legacy-2026-06`; **not mapped** — no stable correspondence exists |
| `PastType`, `TenseRole`, `FutureType`, … inside `morph` | verbal-complex layer labels | mapping note, `mapping_status: hypothesis` until a bridge sample is audited |
| `standard_section` values | section mapping v2 | values kept where unchanged; a changed value is a new mapping version |
| `json_raw`, `json-raw`, `text.body.raw` | extracted-text layer | not carried into 3.0 names |

The complete legacy-slug → `outlet_id` table does not exist yet; building it from the observed
variants is a Phase-0/1 deliverable (master plan §11).

Any future rename of a name that 3.0 itself writes follows one rule: reading the old name stays
allowed, writing it is forbidden, and a record carrying both old and new with different values
fails closed.

## 7. Compatibility views

Existing analysis code keeps working through an **alias layer**, never through new canonical
values: `register_group` (`corapan_libre`, `corapan_lectura`, `coprepan_written`) derived from
`modality` and `production_mode`; alpha-3 country labels; legacy slugs. Figure labels remain
governed by the studies' label vocabulary, keyed on the canonical ids.

## 8. Machine check

`src/coprepan/naming.py` implements the frozen lexical rules of §2, §5.1, §5.2 and §5.6;
`tests/test_naming.py` pins them. A change to a rule here is a decision (CPD), then a code change,
in the same run.

## 9. Additions of 2026-10-07 (CPD-0005)

New terms, id kinds and vocabulary values introduced with the core pipeline contracts. Nothing
above is changed by them.

| Kind | Form or values | Defined in |
|---|---|---|
| **acquisition run** (term) | one execution that acquires for a declared set of outlets; a *processing cohort* in the sense of §3.2, never a stratum of the material | CPD-0005 §2 |
| `run_id` | `acq1-<YYYYMMDDTHHMMSSffffffZ>-<hash12>` | [acquisition](../acquisition/INDEX.md) §2 |
| run kind | `recorded_replay` | same |
| run status | `COMPLETED`, `FAILED` | same |
| `pack_id` | `pk1-<outlet_id>-<YYYYMMDD>-<nnn>` | CPD-0005 §3 |
| fetch outcome | `FETCHED`, `FETCH_FAILED` (states of the preservation machine) | [acquisition](../acquisition/INDEX.md) §3 |
| fetch failure reason | `timeout`, `connection_error`, `incomplete_response`, `unknown` | same |
| **block** (term) | the press `unit` of §3.1 as produced by extraction | CPD-0005 §5 |
| block `kind` | `title`, `heading`, `paragraph`, `list_item`, `quote_block`, `caption`, `unstructured_text` | [extraction](../extraction/INDEX.md) §2 |
| block `role` | `title`, `body`, `non_body` — structural, never a linguistic category | same |
| metadata basis | `json_ld`, `open_graph`, `html_meta`, `html_title`, `html_h1`, `html_lang`, `unknown` | same |
| extraction outcome | `EXTRACTED`, `NOT_EXTRACTABLE` | same |
| document relation | `duplicate_of`, `moved_to` | [identity](../identity/INDEX.md) §7 |
| corpus layer | `RAW`, `EXTRACTED`, `ANNOTATED`, `RELEASE` | CPD-0005 §6 |
| promotion outcome | `promoted`, `already_preserved`, `repaired`, `duplicate_recorded` | [storage](../storage/INDEX.md) §13 |
| layer artifact id | `ar1-<32 hex>` | storage §13 |
| schema ids minted | `coprepan-acquisition-run/v1`, `-acquisition-run-result/v1`, `-fetch-record/v1`, `-pack/v1`, `-pack-index/v1`, `-document-identity/v1`, `-document-observation/v1`, `-document-version/v1`, `-document-relation/v1`, `-extraction/v1` | the indexes above |

"Extracted text" (§3.1, document version) is defined by CPD-0005 §4: the canonical JSON of the
ordered `[kind, role, text]` of all blocks. **BODY** is the view over the blocks with role `body`.

## 10. Additions of 2026-10-07 (CPD-0006)

| Kind | Form or values | Defined in |
|---|---|---|
| **candidate** (term) | a canonical URL key of an outlet that a channel has listed: something to plan a fetch for. Not a document, not an article | CPD-0006 §2 |
| **discovery event** (term, §3.1) | now with an id: `de1:<32 hex>` | [acquisition](../acquisition/INDEX.md) §5 |
| `candidate_id` | `{outlet_id}:cand:<16 hex>` over the canonical URL key | same |
| `request_id` | `rq1:<32 hex>` | CPD-0006 §3 |
| fetch kind | `item`, `channel_document`, `robots_txt` | CPD-0006 §1 |
| run kind (added) | `http_fetch` | [acquisition](../acquisition/INDEX.md) §3 |
| fetch failure reason (added) | `malformed_response`, `body_limit_exceeded`, `redirect_limit_exceeded` | same §4 |
| channel-document format | `rss`, `atom`, `sitemap_urlset`, `sitemap_index`, `html_listing` | same §5 |
| discovery input outcome | `PARSED`, `UNPARSEABLE`, `UNAVAILABLE` | same |
| discovery relation | `item`, `child_document`, `next_page` | same |
| policy decision | `ALLOW`, `DENY`, `DEFER` | CPD-0006 §5 |
| policy status | `DECIDED`, `NOT_DECIDED`; value state `not_decided` | same |
| robots evidence state | `fetched`, `absent`, `unreachable`, `not_consulted` | same |
| identity scope | `external`, `loopback_test`; value state `not_configured` | CPD-0006 §4 |
| retry decision | `none`, `retry`, `gave_up` | CPD-0006 §3 |
| target readiness | `READY`, `NOT_READY`; check status `PASS`, `FAIL`, `INFO` | [storage](../storage/INDEX.md) §15 |
| quantity label | `measured`, `estimated`, `assumed` | storage §16 |
| baseline state | `PRE_FREEZE`, `READY_TO_FREEZE`, `FROZEN` | CPD-0006 §9 |
| extraction reason (added) | `unsupported_content_encoding`, `undecodable_content_encoding` | [extraction](../extraction/INDEX.md) §2 |
| schema ids minted | `coprepan-discovery-input/v1`, `-discovery-event/v1`, `-discovery-candidate/v1`, `-request-log/v1`, `-acquisition-policy/v1`, `-crawler-identity/v1`, `-preservation-target/v1`, `-preservation-readiness/v1`, `-capacity-model/v1`, `-acquisition-baseline/v1`, `-registry-review/v1` | the indexes above |

## 11. Additions of 2026-10-07 (CPD-0007)

| Kind | Form or values | Defined in |
|---|---|---|
| **qualification** (term) | the recorded decision whether a candidate is requested. Not a judgement of the page | CPD-0007 §2 |
| **candidate lifecycle** (term) | the state of a candidate derived from its request history; never stored | CPD-0007 §3 |
| **revalidation** (term) | a 304 answer to a conditional request, confirming a body that is held; a fetch of its own, without a body | CPD-0007 §4 |
| **admission label** (term, §3.1) | now with a first, technical rule set; says whether a fetch yielded readable body text, nothing about content | [admission](../admission/INDEX.md) |
| **freeze manifest** (term) | the hashed listing of a tree at an instant. Not a copy, not a release | [legacy](../legacy/INDEX.md) §5 |
| qualification decision | `QUALIFIED`, `REJECTED`, `DEFERRED` | [acquisition](../acquisition/INDEX.md) §11 |
| candidate state | `NEVER_FETCHED`, `FETCHED`, `SETTLED`, `FAILING`, `SUSPENDED`, `ABSENT`, `RETIRED`, `REFUSED`, `DENIED`, `DEFERRED`, `MOVED` | same |
| channel health state | `HEALTHY`, `DEGRADED`, `STALE`, `FAILING`, `DISABLED`, `UNKNOWN` | same |
| reserved channel slug | `robots_sitemaps` (a discovery source, never a registered channel) | same |
| technical status | `TECHNICALLY_USABLE`, `TECHNICALLY_UNUSABLE`; reason effect `blocks`, `informs` | [admission](../admission/INDEX.md) §2 |
| extractor lifecycle | `EXPERIMENTAL`, `CANDIDATE`, `VALIDATED`, `ACTIVE`, `RETIRED` | [extraction](../extraction/INDEX.md) §8 |
| evaluation arm state | `OK`, `EXTRACTOR_ERROR`, `NO_OUTPUT` | same |
| reference state | `JUDGED`, `NOT_AN_ARTICLE`, `DAMAGED_SOURCE`, `UNJUDGEABLE` | [gold-sample design](../extraction/GOLD_SAMPLE_DESIGN.md) §5 |
| legacy freeze state | `MANIFEST_ONLY`; verification `VERIFIED`, `DIFFERS` | [legacy](../legacy/INDEX.md) §5 |
| canary preflight | `READY`, `NOT_READY` | [acquisition](../acquisition/INDEX.md) §12 |
| component versions (added) | `fetch-planner/1`, `candidate-filter-generic/1`, `admission-technical/1`, `channel-health/1`, `extraction-eval/1`, `legacy-freeze/1` | the indexes above |
| schema ids minted | `coprepan-legacy-freeze-manifest/v1`, `-legacy-freeze-listing/v1`, `-candidate-qualification/v1`, `-candidate-rules/v1`, `-schedule-policy/v1`, `-admission-label/v1`, `-extraction-sample/v1`, `-extraction-evaluation/v1`, `-extraction-reference/v1`, `-extraction-review-case/v1`, `-canary-plan/v1`, `-canary-preflight/v1` | the indexes above |

Two words used with two meanings, kept apart by their object: `FAILING` (a candidate; a channel)
and `DEFERRED` (a qualification; a candidate whose request the policy deferred).

## 12. Additions of 2026-10-07 (CPD-0008)

The open points of §2 (shared namespace) and §4 (shared field) are settled **for this
repository** by CPD-0008; for CO.RA.PAN they are a proposal (master plan O-6).

| Kind | Form or values | Defined in |
|---|---|---|
| shared namespace | `crosscorpus-` — the working name, kept | CPD-0008 §2 |
| contract ids | `crosscorpus-analysis/v1`, `crosscorpus-token-denominator/v1`, `crosscorpus-legacy-studies-view/v1` | [contract](../crosscorpus/ANALYSIS_CONTRACT.md) |
| `production_mode` | `unscripted`, `scripted`, `prerecorded` (spoken; CO.RA.PAN's `speech_mode` values unchanged), `written_edited` (written). Carried at unit level | contract §4.2 |
| **value state** (term) | the declared reason a field has or lacks a value: `known`, `unknown`, `not_applicable`, `undecided`, `not_available`. Refines §5.5 for the analysis tables; `unavailable` of §5.5 is `not_available` there | contract §7 |
| **surface** (term) | which text of a document a unit belongs to: `primary` (BODY; speech), `title`, `auxiliary` | contract §5.4; Phase-3 architecture §5 |
| **segmentation nature** | `editorial` (the publisher's markup made the boundary) or `technical` (an instrument did). No unit kind is an utterance | contract §5.4 |
| unit kind (contract) | the block kinds of extraction; `turn`, `contribution_unit` | same |
| **counted token** (term) | a token that enters the shared denominator: a word on the primary surface of an in-scope unit | contract §6.3 |
| token kind | `word`, `punctuation` | contract §6.1 |
| scope status | `in_scope`, `out_of_scope`, `undecided` | contract §5.4 |
| document relation (contract) | `duplicate_of`, `syndicated_copy_of`, `earlier_version_of` | contract §5.6 |
| release kind | `release`, `provisional_export`, `fixture` | contract §8 |
| compatibility aliases | `register_group`, `country_code_alpha3`, `legacy_outlet_slug`, `legacy_article_id`, `legacy_file_id`, `legacy_standard_section`, `legacy_speaker_code` — never a field of a canonical table | contract §9 |

In the contract, `document_id` names the **sampled unit** — for press a document version (§3.1) —
and `editorial_id` the document it is a state of. Inside COPREPAN's own tables `document_id` and
`document_version_id` keep the meaning of §5.4.

## 13. Additions of 2026-10-08 (CPD-0009)

| Kind | Form or values | Defined in |
|---|---|---|
| **writer lock** (term) | the operating-system lock a process holds while it writes a workspace; it ends with the process. Not a file whose existence means something | CPD-0009 §2 |
| **torn tail** (term) | the incomplete last record of an append-only file, left by an interrupted write; moved to `<name>.torn-<n>`, never read, never deleted | [storage](../storage/INDEX.md) §17 |
| **reconciliation** (term) | writing the ledger transition a verified pack proves; the only state the pipeline completes from evidence | CPD-0009 §4 |
| workspace classification | `CLEAN`, `INCOMPLETE_RESUMABLE`, `NEEDS_REPAIR`, `DAMAGED` | storage §17 |
| identity result (added) | `revalidation_target_not_preserved` | CPD-0009 §7 |
| schema ids | `coprepan-ledger-record/v2` (replaces `v1`), `coprepan-workspace-diagnosis/v1` | the indexes above |

`src/coprepan/identity.py` implements the serialisation of the ids of §5.3 and §5.4 and the
canonical URL key (CPD-0003); `tests/test_identity.py` pins them. `src/coprepan/registry.py`
implements the registry schema and its vocabularies; `tests/test_registry.py` pins them.

## 14. Additions of 2026-10-08 (CPD-0010)

| Kind | Form or values | Defined in |
|---|---|---|
| evidence class | `PRIMARY_EVIDENCE`, `DERIVED_REBUILDABLE`, `CACHE/VIEW` | CPD-0010 §1 |
| **chained table** (term) | an append-only line file whose rows each name the SHA-256 of the line before them in `previous_row_sha256` | CPD-0010 §2 |
| **head** (term) | the row count of a chained table and the hash of its last line, recorded when a run closes | CPD-0010 §3 |
| **rebuild** (term) | deriving derived state again from preserved evidence into a new store, for comparison or adoption; not a repair of the existing store | CPD-0010 §5 |
| identity verification status | `CORRECT`, `REBUILDABLE`, `CONFLICTING`, `SOURCE_EVIDENCE_DAMAGED` | CPD-0010 §5 |
| leftover directories | `identity.rebuild-<id>`, `identity.replaced-<n>` — never read as data | [storage](../storage/INDEX.md) §18 |
| schema ids (supersede the `v1` ids of the lists in §10, §11 and §12) | `coprepan-request-log/v2`, `-discovery-input/v2`, `-discovery-event/v2`, `-candidate-qualification/v2`, `-admission-label/v2`, `-acquisition-run-result/v2`; `-identity-verification/v1` new; `-discovery-candidate/v1` unchanged | the indexes above |

## 15. Additions of 2026-10-08 (CPD-0011, CPD-0012)

The terms of the joint release contract `crosscorpus-release/v1`
([bundle](../../contracts/crosscorpus-release-v1/CONTRACT.md) §3) as this repository uses them.
They refine "release" of §3.1; nothing of §5.4 changes.

| Kind | Form or values | Defined in |
|---|---|---|
| **export** (term) | one immutable, content-addressed tree of one outlet's document versions with their extraction records and provenance; the thing a release names as a member. Not a release, not a pack, not "an export of a dataset" in the loose sense of §3.4 | CPD-0011 §1; [release](../release/INDEX.md) §3 |
| `export_id` | `cpx1-` + 32 hex digits of SHA-256 over the canonical JSON of the export manifest; permanent, never reused | CPD-0011 §3 |
| export kind | `corpus`, `fixture` | CPD-0011 §7 |
| export layer | `extraction` | CPD-0011 §5 |
| **release freeze** (term) | the record `RELEASE_FREEZE.json` that names a release manifest by its digest; the act that makes a manifest a release. **Not** the acquisition baseline freeze (§10, O-12) and **not** a freeze manifest of a tree (§11) | contract §9; CPD-0012 §4 |
| **release manifest digest** (term) | the document digest of a release manifest (`release_manifest_sha256`), recorded only by what refers to the manifest. Not the `manifest_sha256` of an analysis bundle, which is that bundle's own seal | contract §4.3; CPD-0012 §2 |
| **document digest**, **record-set digest**, **tree digest** (terms) | SHA-256 over the canonical JSON of a document; over the sorted canonical lines of a set of records; the record-set digest of a tree's `{path, sha256, size}` listing | contract §4.2, §4.5 |
| **contract path** (term) | a relative path with `/` separators that may enter a digest; never an address | contract §4.4 |
| **bundle digest** (term) | the tree digest of a contract bundle; what a repository pins | contract §14.1 |
| **projection** (term) | a deterministic derivative of a release, e.g. the analysis bundle; never a second source of truth | contract §3 |
| **package** (term) | a distribution or archive copy of one frozen release; may be rebuilt | contract §11 |
| package kind | `distribution`, `archive` | contract §11.1 |
| **study population** (term) | the frozen ids one analysis read, with their selection provenance; a "sample" in the sense of §3.4 with its own id | contract §10 |
| selection kind | `declarative_filter`, `external_tool`, `enumerated` | contract §10.3 |
| member, document, coverage (release record sets) | `MEMBERS.jsonl`, `DOCUMENTS.jsonl`, `COVERAGE.jsonl`. In a release document record `document_id` is the document version id, as in the analysis tables (§12) | contract §6, §7 |
| contract and schema ids (shared namespace) | `crosscorpus-release/v1`; `crosscorpus-release-manifest/v1`, `-release-member/v1`, `-release-document/v1`, `-release-coverage/v1`, `-release-freeze/v1`, `-release-pointer/v1`, `-study-population/v1`, `-study-selection-record/v1`, `-package-manifest/v1`, `-package-file/v1`; `crosscorpus-date-semantics/v1`, `crosscorpus-document-filter/v1` | the bundle |
| schema ids minted here | `coprepan-export/v1`, `coprepan-export-document/v1`, `coprepan-crosscorpus-contract-pins/v1` | [release](../release/INDEX.md) |
| component version (added) | `release-export/1` | same |
| release id (shared form) | begins with `<corpus_id>-`; the form after the prefix is each corpus's own. CO.PRE.PAN's own form (§5.4) is unchanged; CO.RA.PAN plans `corapan-YYYY-MM` | contract §5.4 |

## 16. Additions of 2026-10-08 (CPD-0013)

| Kind | Form or values | Defined in |
|---|---|---|
| **registration record** (term) | the dated record beside the registry by which an outlet becomes `registered`: authority, selection rule, every attribute set with its source, what was left unknown | CPD-0013 §1; [corpus supply](../corpus_supply/INDEX.md) §18 |
| **routine case** (term) | a registry-review case with the action `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES`, no warning that needs a judgement and an unchanged id | CPD-0013 §1 |
| **canary subset** (term) | the outlets registered for the first real canary; a technical subset, never a sample | CPD-0013 §2 |
| crawl-delay mode | `binding_minimum`, `record_only` | CPD-0013 §5 |
| policy refusal (added) | `robots_crawl_delay_exceeds_limit` | [acquisition](../acquisition/INDEX.md) §6 |
| policy versions | `canary/2026-10-08.1` (acquisition policy and schedule policy of the first canary) | CPD-0013 §3–§4 |
| schema ids | `coprepan-acquisition-policy/v2` (replaces `v1`; no `v1` policy was ever decided), `coprepan-registry-registration/v1` | the indexes above |

## 17. Additions of 2026-10-08 (CPD-0014)

| Kind | Form or values | Defined in |
|---|---|---|
| crawler name / robots token | `PanhispanicMediaResearchBot` / `panhispanicmediaresearchbot` | CPD-0014 §1 |
| **interim primary preservation** (term) | a preservation root that is the primary for a bounded scope until a named target replaces it. **Not a backup** and not the long-term target | CPD-0014 §5 |
| **backup** (term, role `BACKUP`) | a second, independent physical copy of `PRESERVATION`, on another volume, verified separately. A copy on the primary's volume is not one | CPD-0014 §4; [storage](../storage/INDEX.md) §5 |
| **role separation** (term) | the rule that no two storage roles share a root or nest, the checkout included | CPD-0014 §4 |
| root identity | the target marker `coprepan_preservation_target.json` (`target_id`), not a drive letter or mount; the id of the interim root is `coprepan-preservation-interim-d` | CPD-0014 §5, §7 |
| role mapping to CO.RA.PAN | `REPO` = `REPOSITORY`; `DATA_WORKSPACE` and `RUNTIME` = `RUNTIME`; `BACKUP_SECONDARY` = `BACKUP`; `REVIEW` = a logical role bound to `EXCHANGE` | CPD-0014 §2 |
| names of physical roots | `coprepan`, `coprepan_workspace`, `coprepan_storage` beside `corapan`, `corapan_workspace`, `corapan_storage`; on institutional storage `projects/panhispanic_media_corpora/{corapan,coprepan}` | CPD-0014 §3 |
| environment variable (added) | `COPREPAN_BACKUP_ROOT` | `.env.example` |

## 18. Additions of 2026-10-08 (CPD-0015)

| Kind | Form or values | Defined in |
|---|---|---|
| contract id | `crosscorpus-storage/v1` (bundle directory `contracts/crosscorpus-storage-v1/`) | CPD-0015 §1 |
| **holding** (term) | a division of a corpus's storage with its own primary and backup status: `PRODUCTION`, `HISTORIC`. Not a corpus, not an id family | contract §2 |
| configuration states | `NOT_DECLARED`, `NOT_CONFIGURED`, `DEFAULTED`, `UNUSABLE`, `UNREACHABLE`, `READ_ONLY`, `AVAILABLE` | contract §4 |
| separation codes | `ROLE_SHARED`, `ROLE_NESTED`, `BACKUP_NOT_INDEPENDENT`, `VOLUME_UNKNOWN`, `FOREIGN_CORPUS_OVERLAP` | contract §5 |
| object states (contract) | `PRESERVED`, `PENDING`, `REFUSED`; here `RAW_PRESERVED`, `PRESERVATION_PENDING`, a `ContentRefusal` | contract §7 |
| backup states | `NOT_CONFIGURED`, `CONFIGURED_NO_COPY`, `COPY_UNVERIFIED`, `NOT_INDEPENDENT`, `INDEPENDENCE_UNKNOWN`, `BACKUP_VERIFIED` | contract §9 |
| preservation routes | `direct`, `spooled`, `workspace` (`core_pipeline.PackPreservation.route`) | CPD-0015 §3 |
| spool pending record | `state/pending/<area>--<object_id>.json` | CPD-0015 §4 |
| **sister** (term) | the other corpus's checkout, `corapan`, beside this one; read by the joint-check command only, never by a test | CPD-0015 §5 |

## 19. Additions of 2026-10-08 (CPD-0018)

| Kind | Form or values | Defined in |
|---|---|---|
| extractor arms (wrappers, `EXPERIMENTAL`, not adopted) | `trafilatura/2.3.1.w1`, `readability_lxml/0.9.w1`, `justext/3.0.2.w1`: tool version, then the wrapper revision | CPD-0018 §1 |
| record field (added, candidates only) | `candidate`: tool, tool version, wrapper revision, parameters, what the mapping loses | CPD-0018 §4 |
| schema id minted | `coprepan-extraction-review-package/v1` (the manifest of a review package: files with digests, the key by digest only) | [extraction](../extraction/INDEX.md) §9 |
| **pilot package** (term) | a review package built on material that does not meet the gold-sample design; it tests the instrument and the codebook and yields no gold | [extraction](../extraction/INDEX.md) §9 |
