# Cross-corpus analysis contract `crosscorpus-analysis/v1`

**Status: TECHNICAL PROPOSAL WITH A CONFORMANCE PROTOTYPE — JOINT DECISION OPEN. NOT IN FORCE IN
CO.RA.PAN. NOTHING VALIDATED.** No release of either corpus exists; no corpus material has passed
through this contract. What exists is a design, a validator, an adapter on COPREPAN's side and two
synthetic fixtures that pass the same checks. Decision:
[CPD-0008](../decisions/CPD-0008_cross-corpus-analysis-contract-and-phase3-layer-architecture.md).
Entry point: [`INDEX.md`](INDEX.md). Current state: [`docs/STATUS.md`](../STATUS.md).

Evidence labels used below: **[corapan]** read in the CO.RA.PAN 3.0 repository on 2026-10-07 at
commit `3a6972ff` (read-only; two untracked plan files present); **[studies]** read in the frozen
studies repository at commit `679e14c1` (read-only; its working tree is not clean); **[copy]**
restated from this repository's own documents. Nothing was run in either repository.

---

## 1. Principle

```text
CO.RA.PAN internal data ──┐
                          ├──► one versioned analysis layer
CO.PRE.PAN internal data ─┘
```

The contract is an **analysis layer**: tables a study reads. It is not a shared raw model, not a
shared pipeline, and it does not make a recording look like an article. Each corpus keeps its own
data model and writes these tables through an adapter. What the two share is a vocabulary, an id
discipline, explicit value states and one counting rule.

It serves three conditions and must keep an instrument difference from passing as a difference
between them:

| Condition | Corpus | `modality` | `production_mode` |
|---|---|---|---|
| spoken, unscripted | CO.RA.PAN | `spoken` | `unscripted` |
| spoken, scripted | CO.RA.PAN | `spoken` | `scripted` |
| written, edited | CO.PRE.PAN | `written` | `written_edited` |

## 2. What CO.RA.PAN 3.0 has today [corapan]

| Area | Observed | Consequence for the contract |
|---|---|---|
| corpus, release | no `corpus_id` field; no release, no freeze (`CORPUS_FREEZE_SEMANTICS` open; a release plan exists as an untracked, inactive document). The nearest thing is an *export bundle*, `corapan-pipeline-export/v2`, with per-file SHA-256 and a fixed `freeze_status` "provisional" | the contract needs a `release_kind` that can say `provisional_export` honestly; release semantics are a proposal (§8) |
| document | the recording; `recording_id` is a semantic file stem (`AR_Radio10_…_8a0ea0f6`), country prefix in upper case, may be `undated` | ids are opaque strings to the contract; `country_id` is its own field; a date carries a state |
| outlet | `radio_id` `^[a-z]{2}_[a-z0-9]+(?:_[a-z0-9]+)*$`, `country_id` alpha-2 lower case; a legacy alpha-3 table with region suffixes "not countries" | identical to `outlet_id` here (adopted by value, CPD-0002): shared as is |
| units | technical: diarisation **turn** (`{recording}:{snapshot}:T:{hash16}`, content-addressed), **contribution unit** (`{turn_id}-CU-{nn}`), speech-mode **region**. Stated in three places: "a turn is a technical unit"; "a technical segment is not a linguistic utterance". No utterance layer exists | `unit_kind` with a declared `segmentation_nature`; no kind named utterance (§5.4) |
| `speech_mode` | `unscripted` · `scripted` · `prerecorded` · `unknown` (an abstention, "not a synonym for `not_applicable`"), plus `speech_mode_applicability` ∈ `applicable` · `not_applicable`. Assigned to **time regions**, projected on turns as the dominant mode with an overlap share. "Conceptually provisional"; not validated on fresh material | shared field `production_mode` (§4.2) with value states; a share; no document-level value for a recording |
| sentences | `{turn_id}:S{n}`, zero-based; terminal marks of the ASR punctuation forced on the parser (`layer2-terminals-forced/v1`); "sentence boundaries are an instrument output"; 41 % of terminal marks inserted by ASR text repair [sourced from its export index]; not exported | sentence measures are modality-confounded by construction (§13) |
| tokens | **no token table is exported and no string token id exists.** Tokens live per recording in `nlp.json` in three layers: lexical (time anchors, zero-based), analysis (`idx` one-based, `head_idx` with 0 = root; punctuation, whitespace and masked tokens excluded), parse view (zero-based, punctuation included, root heads itself). `pos` = UPOS, `tag`, `morph` a **dict**, `dep`. Time is on the lexical layer only, joined by `lexical_index` | one typed token schema with string ids and id-valued heads (§6); CO.RA.PAN needs an export it does not have (§15) |
| production events | `FILLED_PAUSE`, `HESITATION`, `REPETITION`, `SELF_REPAIR`, `FALSE_START`, `ABANDONED_FRAGMENT`, `NON_SPEECH_EVENT`; the first and last are **masked before parsing**, the others are parsed | masked material is not a token; parsed disfluencies are tokens with their event types (§6.3) |
| token denominator | **not defined anywhere** (`word_count` counts ASR words; a planned `population.tokens` has no definition) | defined here for both (§6.3) |
| NLP pins | `spacy==3.8.15`, `es_dep_news_trf` 3.8.0, `corapan-spacy-annotator/v2`, a chain digest over twelve layer versions; transitive dependencies unlocked; stock tokenizer | the same pins COPREPAN planned (§10) |
| verbal complex | `corapan3-verbal-complex/v2`: derived on demand, **never stored, never in `morph`**; id `{turn_id}:VC{n}`; 22 paradigms, 11 roles | a derived layer keyed on token ids (§5.7); storing it is a CO.RA.PAN change |
| value states | eleven upper-case states for `*_value_state` columns (`VALUE`, `UNKNOWN`, `INSUFFICIENT_EVIDENCE`, `DEGRADED`, `NOT_APPLICABLE`, `EXCLUDED_POPULATION`, `STAGE_FAILED`, `STAGE_GATED`, `STALE`, `NOT_RUN`, `REVIEW_PENDING`); scientific enums lower case; some nulls still meaningful | five analysis-level states with a declared mapping (§7) |
| language, genre | "language is not measured"; no genre or section variable | stateful fields; `not_available` / `not_applicable` |
| cross-corpus | no contract, no `production_mode` variable, no reference to a shared namespace | nothing to conflict with; nothing agreed either |

## 3. What the studies had to work around [studies]

The studies read the **CO.RA.PAN 1.0** transcripts and the **legacy** press annotation — not 3.0
data of either corpus. Each workaround is a requirement; none is a design to copy.

| # | Workaround observed | Requirement on the contract | Met by |
|---|---|---|---|
| 1 | press cluster id built as `source_file\|article_id` because `article_id` repeats across daily files; one study falls back to the bare id and merges duplicates | one unique `document_id`; duplicates as an explicit relation | §5.3, §5.6; validator: ids unique within and across corpora |
| 2 | a run-order counter as hit id (`future_hit_000006414`), one duplicate patched by hand | a stable `token_id` a hit can cite | §6.1 |
| 3 | region split off the country code at a hyphen (`ARG-CBA`), twice, differently | `country_id` and `region` as separate fields | §5.2, §5.3 |
| 4 | outlet slug recovered from the directory layout | `outlet_id` on every document | §5.3 |
| 5 | absolute corpus paths in config; `rglob("*.json")` as "the corpus" | a release identified by id and manifest hash | §8 |
| 6 | hits dated by `date_published` falling back to the daily file's date, the sampling frame by the file date only; "distinct dates" therefore count crawl days | `date` with `date_basis` and a state; the container is not a document attribute | §5.3 |
| 7 | `segment_id` = speaker turn in radio, paragraph in press; a role code (`lib-pm`) as fallback id | declared `unit_kind`; `segment` retired | §5.4 |
| 8 | context windows over a whole turn in radio and over one sentence in press | one rule for neighbours (§6.2) and units that say what they are | §6.2 |
| 9 | `morph` coerced to `{}` when it is not a dict; multi-valued values split on `\|` and `,` | `morph` is a dict of UD features with a declared inventory | §6.1 |
| 10 | project labels inside `morph` (`PastType`, `TenseRole`, `FutureType`, `VoiceType`, `VerbLemma`; radio-only `TranscriptSpecial`) | layers, never features | §5.7; validator refuses them |
| 11 | unreadable files skipped silently; `.get()` chains; booleans re-parsed from CSV | a validator that fails closed; typed fields | `analysis_contract.validate` |
| 12 | three rate conventions: per 10,000 of all tokens (punctuation included, press with titles), per 1,000 non-punctuation tokens, and an unnamed "token or word count" | one named denominator, delivered as counts | §6.3 |
| 13 | press counts include the title in hits and denominator | `surface`; the denominator is over `primary` | §6.3 |
| 14 | no corpus version stored with any result; only derived CSVs pinned | `release_id` + `manifest_sha256` | §8 |
| 15 | excluded sections, included sections, the register triple and country lists repeated in up to seven files, with one deviating copy | closed vocabularies and `scope_status` / `scope_reason` delivered with the data; selection as a pinned policy | §5.4, §8 |
| 16 | sparse cells hard-coded in library code | a coverage table referenced by the release | §8 |
| 17 | sentence context rebuilt by reloading the corpora; the "previous sentence" of the first body sentence is the title; a rerun with boundary placeholders | neighbours by id, within one surface | §6.2 |
| 18 | `corapan_libre` / `corapan_lectura` / `coprepan_written` built from speaker type, speaker mode, language and section by two classifiers that disagree | canonical axes; the legacy groups as an alias view | §9 |
| 19 | `speaker_code` is a role-sex-mode code reused across files; a "speaker proxy" pasted from file and code | `producer_id` with a state; never a role code | §5.4 |
| 20 | synthetic future re-derived from UD features; future perfect by a four-token look-ahead; present perfect counted on the participle, simple past on the finite verb | one verbal-complex layer per predicate, the same rule version in both corpora | §5.7, §12 |
| 21 | dominance and leave-one-out diagnostics computed ad hoc from file names | `outlet_id`, `outlet_group`, relations and counts per document | §5.2–§5.6 |

Two findings that correct this repository's own documents:

- The rules version the studies assert for radio 1.0 is **`tense-v4-coprepan-compatible`**; the
  string `tense-v3` does not occur in the studies. Only the radio side is version-checked; for
  press "no version field [is] required". This repository records the legacy press annotation as
  `tense-v3` ([NLP index](../nlp/INDEX.md) §8), and the legacy code confirms it
  (`TENSE_RULES_VERSION = "tense-v3"`, read 2026-10-07). So the studies compared labels of **two
  rule versions**. CO.RA.PAN's own archaeology calls them "the same logic with the older internal
  label map … coprepan-compatible by construction" [corapan]; that is a statement of intent by the
  rules' author, **not an audited equivalence** (§12).
- The studies' `corapan_libre` is unscripted speech **of professional speakers only**; the alias
  in §9 cannot reproduce that restriction from two axes alone.

## 4. O-6: what is decided, and what stays a joint decision

| Question | Technical proposal (CPD-0008) | Status |
|---|---|---|
| namespace | **`crosscorpus-`**, kept. It names what the contracts are, belongs to neither corpus, and nothing in CO.RA.PAN uses or contradicts it | `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN` |
| contract id | `crosscorpus-analysis/v1`; denominator `crosscorpus-token-denominator/v1` | same |
| shared production field | **`production_mode`** (§4.2) | same |
| token denominator | §6.3 | same |
| release and freeze semantics | §8 | same; CO.RA.PAN's own freeze semantics are open there |
| form of a CO.RA.PAN `release_id` | **not proposed.** Its inactive plan uses `corapan-YYYY-MM`; this repository's naming rule would give `corapan-YYYY.n`. The contract requires only that a `release_id` begins with its `corpus_id` | `JOINT_DECISION_OPEN` |

O-6 is **not closed**. Everything COPREPAN can decide alone it has decided; a contract between two
corpora is in force when both have adopted it.

### 4.2 `production_mode`

- **Name.** The shared field is `production_mode`. `speech_mode` cannot be the shared name: a
  press article has no speech. CO.RA.PAN keeps `speech_mode` as its own field; its documentation
  already glosses it as "production mode". Nothing is renamed there.
- **Vocabulary**: `unscripted` · `scripted` · `prerecorded` · `written_edited`.
- **Mapping**: CO.RA.PAN's three substantive values pass **unchanged**. Its abstention `unknown`
  becomes the value state `unknown`; `speech_mode_applicability = not_applicable` becomes the
  state `not_applicable`. Press material is `written_edited`, declared by corpus design.
- **Not normalised away**: `written_edited` is not `scripted`. Scripted speech was written and
  then performed; edited press was written to be read. The validator refuses a spoken value on a
  written row and the reverse.
- **Level**: the unit. A recording changes mode within itself, so its document-level value is
  `not_applicable`; a turn carries the dominant mode with `production_mode_share`. A press
  document carries the value at both levels.
- **Limits, declared**: CO.RA.PAN's assignment is model-made, region-based and not validated on
  fresh material; `prerecorded` is "intended as a subtype of scripted" with a known heterogeneity
  caveat. The press value describes the channel's production process, not every sentence.

## 5. The tables

Checked by `src/coprepan/analysis_contract.py`. A row has exactly the fields of its table.
*Stateful* fields (marked °) come with `<field>_state` (§7).

### 5.1 `release`

`contract`, `corpus_id`, `release_id`, `release_kind` (`release` · `provisional_export` ·
`fixture`), `fixture`, `modality`, `created_at`, `annotator_contract` (`annotator_id`, `pins`,
`chain_version`, `sentence_boundary_policy`, `morph_features`, `masked_event_types`),
`token_denominator`, `anchors` (what offsets and times refer to), `vocabularies` (the closed
corpus-specific value sets), `selection_policy`, `coverage_reference`, `id_stability`, `layers`,
`tables`, `compatibility`, `manifest_sha256`.

### 5.2 `outlets`

`outlet_id`, `corpus_id`, `country_id`, `display_name`, `outlet_kind`°, `city`°, `region`°,
`scope`°, `outlet_group`°. `outlet_kind` is closed per corpus and declared by the release (a
station and a newspaper have no common typology worth inventing).

### 5.3 `documents`

`document_id` — the **sampled unit**: a recording; for press one *document version* (an article
in one textual state) — `corpus_id`, `release_id`, `outlet_id`, `country_id`, `modality`,
`provenance_class`, `tokens_total`, `tokens_counted`, `editorial_id`° (press: the document shared
by its versions), `region`°, `production_mode`°, `date`°, `date_basis`°, `cohort`°,
`section_published`°, `section_mapped`°, `programme`°, `language`°, `language_basis`°.

A date and its basis are known together or not at all. A cohort must contain its date.

### 5.4 `units`

`unit_id`, `document_id`, `unit_kind`, `segmentation_nature`, `surface`, `order_index`,
`scope_status` (`in_scope` · `out_of_scope` · `undecided`), `tokens_counted`, `parent_unit_id`°,
`production_mode`°, `production_mode_share`°, `producer_id`°, `producer_role`°, `scope_reason`°.

| `unit_kind` | `segmentation_nature` | Corpus |
|---|---|---|
| `title`, `heading`, `paragraph`, `list_item`, `quote_block`, `caption`, `unstructured_text` | `editorial` — a boundary the publisher's markup made | press |
| `turn`, `contribution_unit` | `technical` — a boundary an instrument made | radio |

**No unit kind is an utterance**, and the word `segment` is not a field. A technical boundary is
never promoted to a linguistic one by renaming; if either corpus defines a linguistic
segmentation, it is a new unit kind with its own contract. `surface` is `primary` (body text;
speech), `title` or `auxiliary` (non-body blocks).

### 5.5 `sentences`

`sentence_id`, `unit_id`, `document_id`, `surface`, `order_index`, `previous_sentence_id`°,
`next_sentence_id`°, `char_start`°, `char_end`°, `start_ms`°, `end_ms`°.

### 5.6 `relations`

`relation` (`duplicate_of` · `syndicated_copy_of` · `earlier_version_of`), `document_id`,
`target_document_id`, `target_in_release`, `basis`. A relation may point outside the release and
says so.

### 5.7 Derived layers

One table per layer, declared by the release: layer id, `target_level`, `rule_version`, the
closed `values`, `validation_status`, optional attributes. Rows: `target_id`, `value`°, attributes.
**A layer never adds a field to a token.** A bundle of kind `release` may carry validated layers
only.

## 6. Tokens, sentences, anchors, counting

### 6.1 Token

`token_id`, `sentence_id`, `unit_id`, `document_id`, `order_index` (in its sentence, zero-based),
`form`, `lemma`, `upos`, `xpos`°, `morph`, `head_token_id`°, `deprel`, `token_kind` (`word` ·
`punctuation`), `production_event_types`, `counted`, `char_start`°, `char_end`°, `start_ms`°,
`end_ms`°.

| Decision | Reason |
|---|---|
| a token is a **parser token**; whitespace is never one; what an instrument masks before parsing (filled pauses, non-speech events) is never one | the only definition both instruments can meet: CO.RA.PAN's analysis layer already is this |
| ids are strings; a head is named by `head_token_id`, the root by the state `not_applicable` | CO.RA.PAN has three index conventions (one-based with 0 = root; zero-based with self = root; lexical); an id needs no base |
| `morph` is a dict of plain UD features from an inventory the release declares | both instruments produce a dict; the studies' string handling becomes unnecessary; project labels are refused |
| `upos` / `xpos` are the names; CO.RA.PAN's `pos` / `tag` map onto them | UD names; no change inside CO.RA.PAN |
| every `order_index` is zero-based and dense | the base CPD-0003 froze and CO.RA.PAN uses for turns, sentences and lexical tokens |
| ids below the document are promised stable **within a release** only | true for both: a turn id embeds ASR and diarisation snapshots; a press token id hangs on the text version and the annotator |

### 6.2 Sentence neighbours

`previous_sentence_id` / `next_sentence_id` follow the order of the sentences of **one document
and one surface**. The title is its own surface: it is never "the sentence before" the first body
sentence. Neighbours cross unit boundaries — a paragraph break, a change of turn — and the unit
ids say when; whether a study follows a neighbour across a turn is the study's stated choice.

### 6.3 `crosscorpus-token-denominator/v1`

> A token **counts** when it is a word — a parser token that is not punctuation — on the
> `primary` surface of a unit whose `scope_status` is `in_scope`.

`counted` is stored on the token and re-derived by the validator; `tokens_counted` on units and
documents must equal the sum.

What the rule deliberately does and does not equalise:

| Case | Rule | Caveat |
|---|---|---|
| punctuation | never counted | in radio it is instrument output; in press it is authorial. Excluding it removes the largest asymmetry of the old conventions |
| title, captions, navigation | not counted (`surface`) | the old press counts included titles |
| numerals, symbols, foreign words | counted | CO.RA.PAN joins split spoken numerals into one token; press writes digits. Number expressions are **not** equalised |
| repetitions, self-repairs, false starts | **counted**, with their `production_event_types` | they are words that were said. Speech therefore has tokens writing cannot have; a study that wants a "fluent" denominator can build one from the event types and must name it |
| filled pauses, non-speech events | not tokens | masked before parsing in CO.RA.PAN |
| contractions, clitics | as the shared tokenizer leaves them | same instrument on both sides; not examined on real text |

**It is one rule, not one population.** The denominator makes rates *formally* comparable. It
does not make a spoken token and a written token the same kind of event (§13, §14 H1).

### 6.4 Anchors

One token schema carries both kinds; the medium decides the state.

| | written | spoken word | spoken punctuation |
|---|---|---|---|
| `char_start`, `char_end` | `known` | `known` | `known` |
| `start_ms`, `end_ms` | `not_applicable` | `known`, or `unknown` / `not_available` when alignment failed | `not_applicable` |

Offsets are code points, half-open. *What* they are offsets into differs and is declared in
`release.anchors`: the normalised text of the unit (press); the projection text of the turn
(radio). They locate a token for display and alignment; they are not comparable quantities.

## 7. Value states

| State | Meaning | Examples |
|---|---|---|
| `known` | a value is given | |
| `unknown` | the field applies; the source was consulted or the determination attempted, and no defensible value exists | a page that states no date; a speech-mode abstention |
| `not_applicable` | the field has no value for this row by the nature of the row | the time anchor of a written token; the programme of an article; the mode of a whole recording |
| `undecided` | the field applies; the value needs a human or scientific decision that has not been made | a review that is pending |
| `not_available` | the field applies; the stage that would produce the value has not delivered one | no section mapping exists; language is not measured; a stage did not run or failed |

The value is null **exactly** when the state is not `known`. No empty string, no default, no bare
null. `NOT_OBSERVED` was considered and folded into `unknown`: at analysis level the two do not
lead to different handling.

Mapping from CO.RA.PAN's eleven states (lossy by declaration; the native state stays in
CO.RA.PAN): `VALUE` → `known`; `UNKNOWN`, `INSUFFICIENT_EVIDENCE` → `unknown`; `NOT_APPLICABLE` →
`not_applicable`; `REVIEW_PENDING` → `undecided`; `DEGRADED`, `STAGE_FAILED`, `STAGE_GATED`,
`STALE`, `NOT_RUN` → `not_available`; `EXCLUDED_POPULATION` never becomes a row. COPREPAN's
internal `unknown` strings map to the state `unknown`.

## 8. Release, manifest, pins

| Term | Shared meaning |
|---|---|
| **release** | an immutable, named selection of a corpus with its layers. `release_kind = release` is only that. A `provisional_export` is a bundle from a corpus that has no freeze yet — all CO.RA.PAN can truthfully produce today |
| **manifest** | the `release` record. It names every table and layer with row count and SHA-256 of its canonical bytes |
| **hash** | SHA-256; a table's bytes are one sorted-key JSON object per line; the manifest hash is over the canonical JSON of the release record (CPD-0003 serialisation, which CO.RA.PAN already uses for turn content) |
| **pinned inputs** | a study records `release_id` and `manifest_sha256` — nothing else identifies its input |
| **annotator-contract version** | annotator id, the pins, the chain version and the sentence-boundary policy, in the manifest |
| **selection policy** | the versioned rule that chose what is in the release, pinned by id and hash; a `release` must pin one |
| **coverage snapshot** | a table of what the release contains per cell, referenced by id and hash; never recomputed by a study from file names |

Not decided: where releases are stored and published, their cadence, and CO.RA.PAN's freeze
semantics — which are open in CO.RA.PAN and are not COPREPAN's to set.

**Amendment of 2026-10-08
([CPD-0012](../decisions/CPD-0012_local-adoption-of-crosscorpus-release-v1-and-study-pin-semantics.md) §2).**
Since the joint release contract `crosscorpus-release/v1`
([bundle](../../contracts/crosscorpus-release-v1/CONTRACT.md)) the bundle described here is a
**projection** of a release, and the row "pinned inputs" above is replaced: a study pins, per
corpus, the release — `release_id` and `release_manifest_sha256`, the document digest of the
release manifest — and, where it reads these tables, the `manifest_sha256` of this bundle
(`inputs[].analysis_layer` of a study-population manifest, §10.1 there). The two digests are
different things: `manifest_sha256` stays the bundle's own seal over its `release` record and is
unchanged; the release manifest carries no digest of itself. Release identity, freeze, correction,
coverage and the place of the selection policy are defined by the release contract.

## 9. Compatibility view `crosscorpus-legacy-studies-view/v1`

A separate table of aliases — `(target_level, target_id, alias, value)` — for reproducing old
studies and migrating new ones. **A compatibility value is never canonical**: the validator
refuses an alias name in a canonical table and an alpha-3 code in `country_id`.

| Alias | Derived from |
|---|---|
| `country_code_alpha3` | `country_id` through each corpus's legacy country table |
| `legacy_outlet_slug` | the outlet registry's `legacy_aliases` |
| `register_group` | `spoken` + `unscripted` → `corapan_libre`; `spoken` + `scripted` → `corapan_lectura`; `written` + `written_edited` → `coprepan_written`; nothing for `prerecorded` or an unknown mode |
| `legacy_article_id`, `legacy_file_id`, `legacy_standard_section`, `legacy_speaker_code` | reserved names; filled only for material that has a legacy counterpart |

Limit: the legacy `register_group` also depended on speaker type (professional only), language
and section. Those were selections. The alias gives the group the two axes imply; a study that
wants the old population applies the old selection on top, by name.

The finished studies stay reproducible on what they read — the legacy data — not on 3.0 data
through this view. The view exists so that new work can be compared with old labels.

## 10. NLP alignment

| Item | CO.RA.PAN 3.0 [corapan] | CO.PRE.PAN (planned) | Verdict |
|---|---|---|---|
| tokenizer | stock spaCy tokenizer on a rendered projection text; no customisation found | the same tokenizer on the normalised unit text | **same**; the input text differs in kind |
| sentence segmentation | ASR / repair punctuation; terminals forced on the parser | authorial punctuation; parser within one block | **different by necessity**; each policy has its own id in the manifest |
| lemma, POS, morphology, dependencies | `es_dep_news_trf` 3.8.0 under spaCy 3.8.15 | same pins | **same instrument**; a model trained on written news is applied to speech on one side — a known asymmetry of accuracy, not of schema |
| masking before parsing | filled pauses, non-speech events; orality projection | non-body blocks excluded from the parsed view | **different by necessity**, declared |
| numerals | split spoken numerals joined (`corapan-numeric-join/v1`) | none | **different**; not equalised |
| token ids | none as strings | `{document_version_id}:TOKEN:{i:08d}` | contract needs an id on CO.RA.PAN's side (§15) |
| sentence ids | `{turn_id}:S{n}` | `{document_version_id}:SENT:{i}` | compatible as opaque strings |
| pins | exact; transitive dependencies unlocked | not installed | **same pins or a recorded deviation**; a lock on one side must not change resolved versions |
| verbal complex | `corapan3-verbal-complex/v2`, derived on demand | reuse planned | **same rule version**, to be shown equal on shared text (§11) |
| counting | none defined | none defined | §6.3 |

The same parser is not required for its own sake. It is the cheapest way to keep an instrument
difference out of a register comparison, and both corpora already point at it. Every row marked
"different" is a place where a measured difference between speech and press may be the
instrument; §13 says which measure families that touches.

## 11. Shared-text equivalence — design, not a result

Question: given **the same written Spanish text**, do the two instrument paths give the same
annotation? This is the Phase-4 gate "annotation equivalence".

| Element | Design |
|---|---|
| sample | written Spanish text that both paths can ingest unchanged: body paragraphs of preserved press pages (after Phase 3), stratified by country and outlet; plus a small set of constructed sentences for known hard cases (clitics, contractions, numerals, quotation marks, abbreviations). Sizes are parameters |
| paths | (a) COPREPAN: normalised unit text → shared annotator; (b) CO.RA.PAN's annotator entry point fed the same text as a ready surface, with **no** ASR, repair, orality projection or forced terminals — otherwise the test compares pipelines, not instruments |
| compared | tokenisation (boundaries by offset); sentence boundaries; lemma; UPOS; each morphological feature; head and relation; the verbal-complex layer |
| expected | **identity.** Same model, same version, same text: any difference is a defect of pins, preprocessing or wrapper, and is investigated — not averaged |
| metrics | exact agreement per layer with the list of every disagreement; no threshold. If nondeterminism of the transformer runtime appears, it is measured by running one path twice first |
| tolerable vs substantive | tolerable: none assumed in advance. A difference class may be declared tolerable only by a written decision naming it (e.g. a sentence split caused by a policy difference that is itself declared) |
| gold | **not needed for equivalence** (it compares two outputs). Accuracy against human gold is a different question, asked separately on speech and on press, because the model is applied out of domain on one side |
| second part | the same on *spoken* material is not possible: press has no ASR path. What can be done is to pass a transcribed turn's text through path (a) and compare with CO.RA.PAN's stored annotation — this measures the effect of CO.RA.PAN's projection and forced terminals, and is reported as that |
| provenance, freeze | sample manifest with text hashes; both annotator contracts with pins; outputs written once; the comparison script and its result stored together |
| human review | only for disagreements, to classify their cause |

Nothing of this was run: COPREPAN has no annotator installed, and no preserved real page exists.

## 12. Verbal complex and legacy tense labels — bridge design

Three label systems, not two:

| System | Where | Shape |
|---|---|---|
| legacy press | recorded here as `tense-v3` [copy] | labels inside `morph` on single tokens |
| radio 1.0 as the studies read it | `tense-v4-coprepan-compatible` [studies] | the same field set inside `morph`; the only side that is version-checked |
| CO.RA.PAN 3.0 | `corapan3-verbal-complex/v2` [corapan] | one object per predicate: paradigm, role, finiteness, tense, mood, voice, reference; derived, never in `morph` |

**First question, before any mapping**: are `tense-v3` (press) and `tense-v4` (radio) the same
rules? CO.RA.PAN's archaeology says so "by construction" [corapan]; the studies assume it and
check one side; nobody has compared the two rule sets' outputs on the same text. The bridge
therefore has **two legs**: `tense-v3` ↔ `tense-v4` (a code comparison plus the same text through
both, cheap, no gold needed), and legacy labels ↔ verbal complex (below). The first leg decides
whether the finished studies compared like with like, independently of 3.0.

The closed label sets as CO.RA.PAN's archaeology lists them [corapan]: past —
`simplePast`, `imperfectPast`, `presentPerfect`, `pastPerfect`, `futurePerfect`,
`conditionalPerfect`, `otherCompoundPast`, `otherPast`, `perfectInfinitive`; future —
`periphrasticFuture`, `periphrasticFuturePast`; voice — `passive`, `resultative_or_state`. The
studies' own schema file lists seven past values without `conditionalPerfect` and `otherPast`
[studies]: a third thing to reconcile.

Reconstructed semantics [studies], and the hypothesised correspondence (`mapping_status:
hypothesis`; nothing audited):

| Legacy label | Verbal-complex counterpart (hypothesis) | Known difference |
|---|---|---|
| `PastType=simplePast` with `TenseRole=finite_verb` | paradigm `PRETERITE` | counted on the finite verb in both |
| `PastType=presentPerfect` | paradigm `PRESENT_PERFECT` | legacy: counted on the **participle**, where `TenseRole` is mostly absent; the layer has one object per predicate. Counts differ wherever one auxiliary governs coordinated participles — the studies report 35.58 % of present-perfect tokens in sentences with several [sourced from the studies' token-schema note] |
| `imperfectPast` | `IMPERFECT` | mood: the legacy label does not separate subjunctive; the layer has `IMPERFECT_SUBJUNCTIVE` |
| `pastPerfect` | `PLUPERFECT`, possibly `PRETERITE_ANTERIOR` | one legacy value, two paradigms |
| `perfectInfinitive` | `PERFECT_INFINITIVE` | |
| `futurePerfect` | `FUTURE_PERFECT` | |
| `conditionalPerfect` | `CONDITIONAL_PERFECT` | not in the studies' value list |
| `otherCompoundPast`, `otherPast` | several, e.g. the perfect subjunctives | residual classes; no one-to-one counterpart |
| `FutureType=periphrasticFuture` | role `AUX_FUTURE`, pattern `IR_A_INFINITIVE` | a role and pattern, not a paradigm |
| synthetic future (no legacy label; re-derived by a study from `Tense=Fut`, `VerbForm=Fin`) | paradigm `FUTURE` | the study's rule is on UD features; the layer's rule is its own |
| `VoiceType=passive`, `resultative_or_state` | voice `PASSIVE`; roles `AUX_PASSIVE`, `AUX_RESULTATIVE` | |

Bridge sample: documents that carry **both** annotations of the same text. For radio that exists
in principle (1.0 transcripts re-processed in 3.0 as `legacy_ingest`); for press it requires
legacy text re-annotated under the shared instrument (`legacy_text_reannotated`) or re-fetched
pages. Per verbal form: legacy label(s), layer object, agreement class (same / different by
design / different by error on either side), decided by a reviewer where the classes are unclear.
Stratified by legacy label so that rare labels are represented. Output: a confusion table with
every cell traceable, and a statement per measure of whether an old study's result is
reproducible on the new layer.

Not implemented: the old rules are not ported. Porting them would decide scientifically what the
bridge is supposed to find out.

## 13. Comparability of measure families

A judgement of design, on the evidence of §2, §3 and §10. **Nothing was measured.**

| Measure family | Verdict | Why |
|---|---|---|
| token frequency of a word form | comparable with declared caveat | same tokenizer and denominator; spoken counts include repeated and repaired words; ASR spelling of a form is an ASR decision |
| lemma frequency | comparable with declared caveat | same lemmatiser; its accuracy on speech is unmeasured; ASR errors reach it |
| POS distribution | comparable with declared caveat | same tagger, trained on written news: out of domain on one side |
| morphological features (tense, mood, person) | comparable with declared caveat | as POS; the features the old studies relied on most |
| verbal-complex measures (shares such as present perfect vs preterite) | comparable with declared caveat | one rule version on both sides, once equivalence on shared text is shown; **shares within the verbal system** are the most robust family because they need no token denominator |
| rates per token (per 1,000 counted tokens) | comparable with declared caveat | depend on §6.3; disfluency tokens and numeral handling shift the denominator |
| sentence-level syntax (sentence length, clauses per sentence, depth) | **not comparable** as a modality contrast | sentence boundaries are authorial on one side and an instrument output on the other |
| dependency relations within a clause | comparable with declared caveat | same parser; attachment across a wrongly placed boundary is affected |
| lexical diversity (type–token and relatives) | **undecided** | sensitive to text length, to repetitions and to ASR normalisation; needs a design of its own |
| unit-length measures (turn length, paragraph length) | modality-specific | the units are different things by construction |
| temporal anchors (speech rate, pauses) | modality-specific | exist for speech only |
| production and register variables | comparable as design axes, **not as measured outcomes** | `production_mode` is declared for press and model-assigned for radio |
| punctuation-based measures | not comparable | instrument output in radio |
| named entities | undecided | no gold in either corpus |
| publication section, programme | modality-specific | different institutions; no common vocabulary is claimed |

## 14. Hypotheses

| | Hypothesis | Verdict | Evidence, and its limit |
|---|---|---|---|
| H1 | a shared token contract is possible without essential instrument artefacts | **partially supported** | a single schema and one counting rule fit both data models (prototype). Whether residual artefacts are *essential* is unmeasured: out-of-domain tagging, numerals, disfluency tokens |
| H2 | `production_mode` can serve as the shared dimension without falsifying `speech_mode` | **supported** as a design | the three spoken values pass unchanged; abstention and applicability map to states; nothing spoken maps to written. Not supported: any claim about the *accuracy* of the radio values |
| H3 | one sentence and token layer can carry modality-specific anchors without parallel contracts | **supported** at prototype level | one schema, state by medium, enforced by the validator on both fixtures. Real exports untested |
| H4 | legacy studies can be served through a compatibility view without making legacy semantics canonical | **partially supported** | aliases are separable and refused in canonical tables. The legacy register groups also encode selections the alias cannot carry; finished studies are reproduced on legacy data, not through the view |
| H5 | COPREPAN can build on CO.RA.PAN's NLP pins, or instrument the deviations | **supported** as far as pins go; **undecided** in practice | the pins are identical in both plans; nothing is installed here; the unlocked transitive dependencies make "same pins" weaker than it sounds until both resolve to the same versions |

## 15. What CO.RA.PAN would have to add — a proposal, not a request made

Nothing was changed in CO.RA.PAN, and nothing below is in force there. Named so that a later,
separate run in that repository has a starting point:

| # | Need | Where (as observed) |
|---|---|---|
| 1 | a token and sentence export with string ids — e.g. `{turn_id}:TOKEN:{i:08d}` over the parse view, the form its LCP provenance already uses internally | `pipeline/export.py`, `nlp/canonical_stage.py`, `ling_elab/provenance.py` |
| 2 | time anchors on exported tokens (the join through `lexical_index` done at export) | `nlp/lexical.py`, `nlp/spacy_gold.py` |
| 3 | the verbal-complex layer written as a table at export | `nlp/verbal_complex.py` |
| 4 | a `corpus_id`, a release or at least a named provisional export with a canonical-JSON manifest hash | `pipeline/export_contract.py`; its release plan |
| 5 | a value state for speech mode on turns | `speech_mode/`, `pipeline/export.py` |
| 6 | the mapping of its eleven value states onto the five of §7, owned there | `pipeline/export_contract.py` |
| 7 | agreement on the namespace, on `production_mode` as the shared name, on the denominator and on the form of its `release_id` | its decision registry |

Recommended: a separate run in CO.RA.PAN, after its own closure work, that reviews this proposal
and builds an adapter against the validator here.

## 16. Open

| Item | Kind |
|---|---|
| adoption by CO.RA.PAN; everything in §4 marked joint | joint decision (O-6) |
| whether `tense-v3` and `tense-v4` give the same labels on the same text (first leg of §12) | factual; a comparison nobody has run |
| press sentence-boundary policy id | scientific, Phase 4 |
| lexical-diversity design; named-entity use | scientific |
| columnar storage of the tables (the prototype writes JSON lines) | technical |
| a `coverage` table schema; the selection-policy schema | joint, with the first release. *2026-10-08:* coverage at document level is specified by `crosscorpus-release/v1` §7.3; of the selection policy only the pin is specified, its content stays open |
| whether a "fluent" second denominator is defined by the contract or left to studies | scientific |
| equivalence run (§11) and bridge sample (§12) | Phase 4; need real material and an installed instrument |
