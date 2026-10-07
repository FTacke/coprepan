# CPD-0008 — Cross-corpus analysis contract `crosscorpus-analysis/v1` (technical proposal) and the Phase-3 layer architecture

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the Phase-3 and cross-corpus analysis contract run (`docs/plans/COPREPAN3_PHASE3_CROSS_CORPUS_ANALYSIS_CONTRACT_RUN.md`), which ordered O-6 to be decided as far as the evidence of both repositories reaches and authorised that run to take the technical decisions. Recorded by that run; subject to the operator's review. **It binds COPREPAN only**: for CO.RA.PAN it is a proposal (§9). |
| Kind | architecture |
| Scope | the shared analysis contract as COPREPAN proposes and implements it on its own side; the value-state system; the token denominator; release and manifest semantics of a contract bundle; the compatibility view; the order and boundaries of COPREPAN's text layers between extraction and release |
| Builds on / amends / supersedes | builds on CPD-0001 (principles), CPD-0002 (naming: fixes the namespace left open there), CPD-0003 (ids, canonical JSON), CPD-0005 (extraction record), CPD-0007 (technical admission, evaluation instruments). Amends nothing. |
| Does not change | anything in CO.RA.PAN; the legacy corpus; the finished studies; any extractor, annotator or enrichment — none is adopted or activated |
| Run report | [`docs/agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md`](../agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md) |
| Evidence | read-only archaeology of CO.RA.PAN 3.0 (commit `3a6972ff`) and of the studies repository (commit `679e14c1`), recorded in [`docs/crosscorpus/ANALYSIS_CONTRACT.md`](../crosscorpus/ANALYSIS_CONTRACT.md) §2–§3; `tests/test_analysis_contract.py` |

Validation debt: the contract has met two synthetic fixtures. No corpus material of either
corpus, no real export, no annotation by an instrument, no adoption by CO.RA.PAN. Listed in
`docs/STATUS.md` §6.

## Context

The master plan's question O-6 — the name and semantics of what the two corpora share — had been
left for a joint decision, with working names. Two things made it urgent to settle COPREPAN's
side now. The studies show what the absence of a contract costs: constructed ids, three rate
conventions, labels of two rule versions compared as one, context windows of different reach in
the two corpora. And Phase 3 is about to define COPREPAN's text layers; they should be defined
towards the tables a study will read, not away from them.

CO.RA.PAN 3.0, read on 2026-10-07, has no release, no token export, no token denominator and no
cross-corpus document. There is nothing to conflict with, and nothing agreed.

## Decision

### 1. An analysis layer, not a common data model

Each corpus keeps its own model and exports, through its own adapter, to one versioned set of
analysis tables: `release`, `outlets`, `documents`, `units`, `sentences`, `tokens`, `relations`,
derived layers, and a compatibility view. A press article is not modelled as a recording and a
turn is not modelled as a paragraph. Full definition:
[`ANALYSIS_CONTRACT.md`](../crosscorpus/ANALYSIS_CONTRACT.md) §5–§6.

### 2. Names

- Namespace **`crosscorpus-`**; contract **`crosscorpus-analysis/v1`**; denominator
  **`crosscorpus-token-denominator/v1`**; view `crosscorpus-legacy-studies-view/v1`. The working
  name of CPD-0002 is kept: it belongs to neither corpus and says what the thing is.
- The shared production field is **`production_mode`**, on the axis `modality` ∈ `spoken` ·
  `written`. CO.RA.PAN's `speech_mode` is not renamed and is not the shared name: writing has no
  speech.

### 3. `production_mode`

Vocabulary `unscripted` · `scripted` · `prerecorded` · `written_edited`. CO.RA.PAN's three
substantive values pass unchanged; its abstention becomes the value state `unknown`, its
`not_applicable` the state `not_applicable`. Press is `written_edited` by corpus design, never
inferred. A spoken value on written material, or the reverse, is a contract violation: scripted
speech is not equated with edited writing. The value is carried at unit level; a document whose
units differ has none.

### 4. Value states

Five lower-case states: `known`, `unknown`, `not_applicable`, `undecided`, `not_available`
(definitions: contract §7). A field that can lack a value carries its state beside it, and the
value is null exactly when the state is not `known`. No bare null, no empty string, no default.

### 5. Units, sentences, tokens

- A unit declares its `unit_kind` and its `segmentation_nature` (`editorial` or `technical`).
  **No unit kind is an utterance.** `segment` is not a field.
- A token is a parser token. Ids are strings; heads are ids; the root is a state; `morph` is a
  dict of plain UD features from a declared inventory. **Project labels are never features**:
  they are layers.
- Order indexes are zero-based and dense. Ids below the document are promised within a release.
- Sentence neighbours are given by id, within one document and one surface.
- Anchors are medium-typed inside one schema: character offsets in both modalities, time for
  spoken words, `not_applicable` otherwise. What an offset refers to is declared per release.

### 6. The token denominator

A token counts when it is a word — a parser token that is not punctuation — on the `primary`
surface of a unit that is in scope. Titles and non-body blocks do not count. Words of
repetitions and repairs count and carry their event types; what an instrument masks before
parsing is not a token. Numeral handling is not equalised. The rule makes rates formally
comparable and is **not** a claim that a spoken and a written token are the same kind of event.

### 7. Release, manifest, pins

A bundle's `release` record is its manifest: per-table and per-layer row counts and SHA-256 over
canonical bytes, the annotator contract with its pins, the denominator id, the selection policy
and coverage reference (pinned, or a state saying why not), and a hash over the record itself. A
study pins `release_id` and `manifest_sha256`. `release_kind` distinguishes a `release` from a
`provisional_export` and from a `fixture`; only validated layers enter a `release`.

### 8. COPREPAN's text layers (Phase 3)

Order: extraction → technical admission → normalisation → annotation → enrichment layers →
content admission → release → contract export
([`PHASE3_SCIENTIFIC_ARCHITECTURE.md`](../architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md)).

- **BODY is the primary linguistic surface.** Each body block is one parser input; no sentence
  spans a block boundary. The title is a separate surface, never prefixed to the body.
- **Normalisation** is a closed, versioned set of character-level operations, each application
  recorded with its offset. It never changes wording. Its contents are not decided.
- **Language** is three things in three places: the page's declaration (metadata with basis), an
  identification layer per unit (a measurement), and an admission label over that layer.
- **Section as published, mapped section, production mode, article type and opinion are five
  variables.** None is filled from another. Register is a study's grouping, not a corpus field.
- Technical admission, content admission and scientific taxonomies are three kinds of statement;
  no taxonomy value admits or excludes.

### 9. Standing towards CO.RA.PAN

For CO.RA.PAN this record is a **proposal**. COPREPAN implements its side against the validator
and does not wait; it does not write into CO.RA.PAN, and it does not treat the contract as agreed.
O-6 is `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN`.

## Alternatives considered

| Alternative | Why not |
|---|---|
| model press internally like radio (documents as recordings, paragraphs as turns) | destroys what is specific to each; the contract's job is the analysis tables only |
| `speech_mode` as the shared field, press as `scripted` | false for writing; would merge two of the three research conditions |
| `speech_mode` as the shared field, press as `not_applicable` | makes the press condition invisible on the very axis the research design crosses |
| a neutral `register` field | register is a study-side grouping (CPD-0002); it would hide two axes in one |
| sentinel strings (`"unknown"`) in value columns | breaks typed columns (dates, integers) and is how defaults creep in |
| CO.RA.PAN's eleven value states as the shared set | most describe pipeline execution; a study needs to know whether it has a value and why not, not which stage was gated |
| count all tokens (punctuation included) | punctuation is instrument output in radio; the old studies' largest asymmetry |
| drop repetition and repair tokens from the denominator | decides a scientific question in a counting rule; the event types let a study do it openly |
| a separate token table per modality | two contracts; every study re-implements the join |
| positions as head references | three index bases exist in CO.RA.PAN alone |
| port the legacy tense rules to press 3.0 | decides in advance what the bridge sample is meant to find out; the rules wrote project labels into `morph` |
| a namespace named after the project or an institution | none is decided; `crosscorpus` describes and commits to nothing else |
| wait for CO.RA.PAN's release design | Phase 3 would then define layers with no target; a proposal with a validator is something to react to |

## Consequences

- Stage 12 (cross-corpus contract) is `PARTIAL`: a validator, an adapter on COPREPAN's side and
  fixtures. No export of corpus material exists, because none can.
- The token denominator, the unit vocabulary and the value states are fixed for COPREPAN's own
  later stages: annotation and release are built towards them.
- The finding that the finished studies compared `tense-v3` press labels with `tense-v4` radio
  labels is on record, with the comparison that would settle it (contract §12).
- A change of the contract after adoption is a new contract version; `v1` before adoption may
  still change with CO.RA.PAN's review, and such a change is recorded as an amendment here.

## Not decided here

- Adoption by CO.RA.PAN; the form of its `release_id`; its freeze semantics.
- The schema of a coverage table and of a selection policy.
- Columnar storage of the tables.
- The normalisation operation set; the language identifier; the press sentence-boundary policy.
- Vocabularies of section mapping, article type and opinion; whether those layers are built.
- A second, "fluent" denominator.
- Lexical-diversity and named-entity measures.
- Anything about accuracy: of the annotator on either modality, of `speech_mode`, of any layer.
