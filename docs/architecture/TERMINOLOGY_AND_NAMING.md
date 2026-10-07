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

### 5.5 Vocabulary values

- Canonical machine values are English, lower-case snake case (`national_reference`,
  `hard_paywall`, `native_v3`).
- Status tokens of state machines are upper case (`RAW_PRESERVED`, `FETCH_FAILED`).
- Closed vocabularies carry explicit value states (`unknown`, `unavailable`, `not_applicable`)
  instead of nulls or empty strings.
- An axis that cannot be measured yet reports `NOT_YET_MEASURABLE`, never a zero and never a guess.

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
