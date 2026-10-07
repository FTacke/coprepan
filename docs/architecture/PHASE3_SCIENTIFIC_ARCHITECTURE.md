# Phase 3 — scientific architecture of the text layers

**Status: ARCHITECTURE — partly implemented (extraction contract, technical admission label,
evaluation instrument), otherwise NOT IMPLEMENTED. NOTHING VALIDATED.** This document fixes where
each layer between a preserved page and the cross-corpus analysis tables sits, what it may and may
not do, and where human gold attaches — so that validation on real material can be run without
redesign. It decides no threshold, adopts no tool and validates nothing.

Governing decisions: CPD-0001 (principles), CPD-0005 §5–§6 (extraction record),
[CPD-0007](../decisions/CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md)
§8–§10 (technical admission, lifecycle, harness),
[CPD-0008](../decisions/CPD-0008_cross-corpus-analysis-contract-and-phase3-layer-architecture.md)
(this architecture and the analysis contract). Current state: [`docs/STATUS.md`](../STATUS.md).

---

## 1. The chain

```text
preserved body (RAW)                       bytes, addressed by sha256
   │  extraction            extractor/version            → typed blocks + metadata with basis
   ▼
extraction record (EXTRACTED)              document version = hash of the extracted text
   │  technical admission   rule set                     → label per fetch          (exists)
   │  normalisation         operation set/version        → normalised unit text + operation report
   ▼
normalised units                           the NLP input surface (§5)
   │  annotation            annotator contract, pins     → sentences, tokens        (shared instrument)
   ▼
annotation (ANNOTATED)
   │  enrichment layers     each: own id, version, validation status, keyed on stable ids
   │     language · verbal complex · section mapping · syndication · article type · opinion
   │  content admission     rule set reading the layers above → labels, never deletion
   ▼
release                                    selection under a recorded policy; manifest
   │  export
   ▼
analysis contract tables (`crosscorpus-analysis/v1`)
```

Rules that hold at every arrow:

- **A layer is derived, addressed and write-once**: fingerprint (input hashes + component version
  + parameters) → one answer. A new version is a new artefact beside the old one.
- **No layer edits the layer above it.** Extraction does not repair bytes; normalisation does not
  repair extraction; an enrichment never writes into the token table.
- **Nothing is removed.** Every exclusion is a label read by a release or study selection.
- **Unknown stays unknown**, as an explicit value state, never as an empty string or a default.

## 2. Extraction (exists as a contract)

Fixed by CPD-0005 and the [extraction index](../extraction/INDEX.md); restated here only as the
interface later layers rely on:

| Guarantee | Consequence downstream |
|---|---|
| input named by `body_sha256`; extractor by name and version | a unit, sentence or token traces to preserved bytes |
| typed blocks in document order, each with `kind` and `role` (`title` · `body` · `non_body`) | units of the analysis contract are blocks; the role decides the surface (§5) |
| `TITLE`, `BODY` and everything else kept apart; non-body blocks kept, not deleted | a study can include captions or headings deliberately; none leaks in silently |
| metadata `value` as published + `basis` + all `candidates` | a date carries its basis into the contract; nothing is parsed or reinterpreted at extraction |
| `extracted_text_sha256` defines the document version | sentence and token ids hang on a text that cannot change under them |
| deterministic; replayable from the preservation root | a different answer for the same fingerprint is an error |

Open and unchanged: which extractor; DOM anchors per block; per-outlet rules. All Phase 3, on a
gold sample ([design](../extraction/GOLD_SAMPLE_DESIGN.md)).

## 3. Admission: three kinds of statement that must not be mixed

| Kind | Says | Decided by | State |
|---|---|---|---|
| **technical admission** | this fetch yielded readable body text — or why not | recorded facts (status, extraction outcome), rule set `admission-technical/1` | built ([admission index](../admission/INDEX.md)) |
| **content admission** | this document version is an article / is complete / is in a given language / has a given length | rules reading extraction and enrichment layers; each label with reasons and rule version | not built; needs the gold sample |
| **scientific taxonomy** | section, genre / article type, opinion, register | enrichment layers with their own validation (§7) | not built |

- A technical label is never upgraded into a content judgement, and a taxonomy value is never an
  admission gate. "Is in section X" or "is opinion" does not admit or exclude anything; a
  *selection policy* of a release or study may read it.
- Thresholds (minimum length, language share, age) are parameters of a selection, recorded with
  the release — not properties of a label.
- `access_class` (paywall, consent wall, truncated) is a content-admission label, observed from
  the page; it is not inferred from the outlet's `access_model` in the registry.

## 4. Normalisation (contract and position only)

Position: after extraction, before annotation. One normalised text per unit.

| | |
|---|---|
| Input | one block's `text` from an extraction record |
| Operations allowed | Unicode normalisation to NFC; a declared set of whitespace and invisible-character operations (for instance: no-break space to space, removal of zero-width characters, soft hyphen removal). The set is closed and versioned (`normalisation-ops/v<n>`) |
| Operations forbidden | anything that changes wording: spelling, accents, casing, punctuation, quotation marks, hyphenation of real compounds, variant standardisation, "joined word" repair |
| Output | the normalised text; its hash; **one record per applied operation** with offset and the characters before and after, so the extracted text is reconstructible exactly |
| Identity | fingerprint = extraction text hash + operation-set version; deterministic |
| Anchors | token offsets (§5) refer to the normalised unit text; the operation report maps them back to the extracted text |

The baseline extractor already collapses runs of whitespace inside a block (its one recorded
change, extraction index §4). Whether that belongs in extraction or moves here is decided with
the adopted extractor; either way it happens once and is recorded.

**Which operations are in the set is not decided.** Each candidate operation needs the same
question as any transformation: what does it remove, what can it damage (methodology §4). A
soft-hyphen removal can join a real line-break hyphen; that is a harm family to be measured, not
assumed away.

## 5. The NLP input surface

> **BODY is the primary linguistic surface.** The annotation of a document version is the
> annotation of its body blocks, each parsed on its own.

- **One block, one parser input.** The parser never sees two blocks as one text, so no sentence
  spans a block boundary. This is the press sentence-boundary policy's first clause; the policy
  needs its own id and decision in Phase 4 ([NLP index](../nlp/INDEX.md) §4).
- **The title is a second, separate surface.** It may be annotated — headlines are linguistically
  interesting and syntactically unlike prose — but as its own unit, never prefixed to the body.
  Its tokens are not body tokens and do not enter the body token count.
- **Non-body blocks** (captions, navigation remnants, embeds) are not annotated by default. If a
  later decision annotates them, they are units with their own `unit_kind` and surface.
- Every unit, sentence and token therefore carries a **`surface`**: `body` · `title` ·
  `non_body`. Counts and rates state which surface they are over; the cross-corpus denominator is
  defined on `body` (analysis contract §6).
- **Offsets** are code-point offsets into the normalised text of the token's unit, half-open
  `[char_start, char_end)`.
- **Quoted speech inside a body block stays in the body.** Distinguishing authorial from quoted
  text is a later enrichment (NLP index §6), not a surface.

## 6. Language

Three different things, kept in three places:

| Thing | Where | Nature |
|---|---|---|
| declared language | extraction metadata `language`, basis `html_lang` | what the page claims; often a site-wide constant, sometimes wrong |
| **identified language** | enrichment layer `language-id`, keyed on `unit_id`, with tool, version and model hash; values BCP-47 language subtags plus value states | a measurement by a classical identifier; per block, because a page can mix languages |
| language admission label | content admission (§3), a rule over the layer: e.g. share of body units identified as Spanish | a label with its rule version; the threshold belongs to the selection |

- The identifier is a classical tool, not an LLM (NLP index §7). Which one, and how it is
  validated on short blocks and on Spanish against its closest neighbours (Catalan, Galician,
  Portuguese), is open.
- **Variety is never identified by machine.** `es` is the finest value the layer may give; the
  country of the outlet is metadata, and regional variety is what studies measure.
- Until the layer exists the contract carries `language` from the declaration with its basis, or
  `unknown` — never a default `es` (legacy F-11).

## 7. Section, production mode, register, genre, opinion

Five variables. **None is a proxy for another, and no layer may fill one from another silently.**

| Variable | What it is | Source | Level | State |
|---|---|---|---|---|
| `publication_section` | where the outlet placed the item | page metadata, as published, with basis | document version | carried by extraction |
| `section_mapped` | the item's place in a cross-outlet vocabulary | enrichment layer: mapping rules, versioned (section mapping v2) | document version | planned; starts from the legacy vocabulary |
| `production_mode` | how the language was produced | **declared by corpus design**: every press document is `written_edited` | document, unit | decided (terminology §4; CPD-0008) |
| `register` | a study's grouping of conditions | derived by the study from `modality` and `production_mode` | — | **not a corpus field** |
| `article_type` (genre) | news report, interview, chronicle, obituary, … | enrichment layer; evaluation candidate; needs human gold | document version | not built, no vocabulary decided |
| `opinion` | opinion or editorial content vs reporting | its own enrichment layer; needs human gold | document version | not built |

Why they are apart — each line is a mistake the legacy data or the studies made, or would invite:

- A section is an editorial placement. "Opinión" as a section does not make a text opinion, and
  opinion pieces appear under "Deportes". The legacy `is_opinion` flag came out of the section
  mapping; in 3.0 an opinion value needs its own evidence.
- `production_mode` is not `register` and not `genre`: an interview printed verbatim is
  `written_edited` by this corpus's design, whatever one thinks of its orality. That limit is
  declared, not hidden: **`written_edited` describes the channel's production process, not a
  property of every sentence in it.**
- `article_type` is not derivable from `section_mapped`. A study that wants "news only" needs the
  genre layer or says that it used a section as a stand-in.

Every such layer has the same shape:

| Field | Content |
|---|---|
| `layer_id` | `<name>/v<n>`, with rule or model version and, for a model, its hash |
| `target_level`, `target_id` | what is labelled, by stable id |
| `value`, `value_state` | a value of the layer's closed vocabulary, or a state (`unknown`, `undecided`, `not_applicable`) |
| `basis` | which evidence the value rests on (rule id, model score reference, reviewer decision) |
| `validation_status` | `NOT_VALIDATED` · `VALIDATED` with the report that says so |

An unvalidated layer may exist and be studied; it does not enter a release as a default field
(target architecture §8).

## 8. Where human gold attaches

| Layer | Gold unit | Instrument | State |
|---|---|---|---|
| extraction | preserved item fetch | review package, blinded ([gold-sample design](../extraction/GOLD_SAMPLE_DESIGN.md)) | instrument built; no gold |
| content admission | document version | the same review cases (`NOT_AN_ARTICLE`, `DAMAGED_SOURCE`) plus access class | states exist in the review form; no rules |
| language | unit | sample of blocks with identified and declared language | not designed |
| annotation equivalence | token | shared-text sample ([analysis contract](../crosscorpus/ANALYSIS_CONTRACT.md) §11) | designed; not run |
| verbal complex | token / verbal group | bridge sample (same document, §12) | designed; not run |
| section mapping | document version | mapping review | not designed |
| article type, opinion | document version | codebook first; then stratified gold | not designed |

Common rules (methodology §5, §10): gold is frozen before any prediction is made on it;
development and validation data are disjoint by outlet and document; a decision is append-only
and keyed on a content-addressed id, so it is invalidated — visibly — when the text it judged
changes; reviewers see material and a closed label set, not the machine's answer.

## 9. What cannot be done before real material exists

Everything that measures: extractor comparison, the normalisation operation set, the language
identifier, the sentence-boundary policy, annotation equivalence, every enrichment. The order
once the canary has preserved real pages: gold sample → extractor adoption → normalisation set →
annotation under the shared pins → equivalence and bridge samples → enrichment layers one by one.

## 10. Open

| Item | Kind |
|---|---|
| extractor adoption; outlet rules | scientific, Phase 3 |
| the normalisation operation set and its version id | scientific / technical, Phase 3 |
| the language identifier, its validation, the label rule | scientific, Phase 3 |
| press sentence-boundary policy id | joint / scientific, Phase 4 |
| whether titles are annotated in the first release | scientific |
| vocabularies of `article_type` and `opinion`; whether they are built at all | scientific, Phase 4 |
| durable home of the layers | technical; needs O-3 |
