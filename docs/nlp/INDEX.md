# NLP and Enrichment — component index

**Status: NORMATIVE TARGET — NOT IMPLEMENTED.** No annotator is installed or run by this
repository; no model has been loaded. Governing decision:
[CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) §6, §7.
Current state: [`docs/STATUS.md`](../STATUS.md).

---

## 1. Principle: one NLP instrument for both corpora

> COPREPAN 3.0 uses, as far as scientifically sensible, **the same NLP instrument contract as
> CO.RA.PAN 3.0**. What differs between the modalities is declared, not standardised away.

Cross-corpus studies compare token-level rates between radio and press. If the two corpora are
annotated by different parsers, tagsets or rule versions, an instrument difference is
indistinguishable from a register difference. Both corpora already use the same parser family,
which makes alignment cheap.

## 2. The instrument contract (reference values)

Read from `corapan_playground` on 2026-10-06 (`pyproject.toml`, `docs/nlp/INDEX.md`,
`src/corapan_playground/nlp/`). **The authoritative source of these values is the CO.RA.PAN 3.0
repository**; this table is a dated copy for orientation, mirrored as `PLANNED` in
`[tool.coprepan.nlp]` of [`pyproject.toml`](../../pyproject.toml). The Phase-4 implementation run
re-reads them from the source before pinning.

| Item | CO.RA.PAN 3.0 value |
|---|---|
| Parser model | `es_dep_news_trf` |
| Parser model version | `3.8.0` |
| spaCy | `3.8.15` |
| Transformer runtime pins | `spacy-curated-transformers==0.3.1`, `curated-transformers==0.1.1`, `curated-tokenizers==0.0.9`, `torch==2.13.0` |
| Execution | CPU |
| NER | separate sub-layer only: `es_core_news_lg` `3.8.0` supplies `ent_type` / `ent_iob` and nothing else; no NER gold exists |
| Annotator id | `corapan-spacy-annotator/v2` |
| Verbal-complex layer | `corapan3-verbal-complex/v2`, derived on demand, never inside `morph` |
| Chain version | a digest over the ordered layer versions: `corapan-linguistic-chain/<digest>` |
| Known gap there | transitive dependencies are not locked |

**Token schema.** CO.RA.PAN 3.0 stores, per token: `index`, `text`, `char_start`, `char_end`,
`lemma`, `pos`, `tag`, `morph`, `dep`, `head_index`, `sentence_index`, `is_punct`,
`source_token_index`, `production_event_types`, `ent_type`, `ent_iob`.

- Shared with press unchanged: `index`, `text`, `char_start`, `char_end`, `lemma`, `pos`, `tag`,
  `morph`, `dep`, `head_index`, `sentence_index`, `is_punct`, `ent_type`, `ent_iob`.
- Spoken-corpus fields with no press counterpart: `source_token_index` (mapping to the ASR token
  stream) and `production_event_types` (filled pauses, non-speech events). They are not invented
  for press; the shared contract carries them with a `not_applicable` value state or omits them by
  declared schema — decided with the cross-corpus contract.

## 3. What must be identical

1. Parser model and version, library version, tokenisation rules.
2. The tagsets and the morphological feature inventory: **plain UD; no project feature inside
   `morph`**.
3. The verbal-complex rule version and label inventory — the layer every existing study depends
   on.
4. The **token denominator**: which tokens count (punctuation, symbols, numerals). The existing
   studies compute rates on different tokenisations (radio 1.0 tokens keep attached punctuation,
   press tokens do not).
5. The provenance vocabulary: same keys, same meaning, on every document.

A pin change is a **joint, forward-only change decision for both corpora**. COPREPAN does not move
a pin unilaterally, and does not follow a CO.RA.PAN pin change silently: either is a recorded
decision with a bridge sample.

## 4. What is compatible but deliberately not identical

Each difference is **declared in the contract** — never harmonised away.

| Aspect | Press | Radio |
|---|---|---|
| Sentence segmentation | authorial punctuation inside DOM blocks; the parser segments within a block and never across a block boundary | ASR/repair punctuation with layer-2 terminals forced (`layer2-terminals-forced/v1`) |
| Unit above the sentence | block (`paragraph`, `title`, `quote_block`, …) | turn, contribution unit |
| What is masked before parsing | non-body blocks (captions, credits, embeds) are excluded from the parsed body view | orality projection, production-event masks |
| Text surface | the published text after recorded character normalisation | repaired ASR surface |

Consequence: **sentence-length and clause-per-sentence measures are modality-confounded by
construction.** The contract flags per measure family whether it is comparable across modalities:
lexical and morphosyntactic token-level rates yes, under the shared denominator; sentence-level
measures only with the declared segmentation difference.

Not adopted from CO.RA.PAN 3.0 because they are artefacts of speech: orality projection,
production-event detection, the numeric join, punctuation-source policy, forced terminals.

The press sentence-boundary policy needs its own id and its own explicit decision (Phase 4); it is
not inherited.

## 5. Provenance

Annotation is a deterministic derived layer bound to a document-version hash. Each annotated
document records: annotator id and version, model name **and model version**, library version,
runtime pins, the chain-version digest, the input text hash, the device class. (The legacy
annotation recorded the model name and library version but not the model version — audit T-12.)

The fingerprint of an annotation includes the pins; a run under drifted pins is refused, not
silently accepted.

## 6. Enrichment layers

An enrichment is a separate table keyed on token, sentence, unit or document-version ids, with its
own rule or model version and its own validation status. It enters a release only when validated;
each layer is switchable, and rollback is deactivation.

| Layer | Status | Note |
|---|---|---|
| Verbal complex | PLANNED — reuse of the CO.RA.PAN layer | replaces the legacy `tense-v3`, which wrote `PastType`, `TenseRole`, `FutureType`, … *into* `morph` |
| Section mapping v2 | PLANNED | starts from the legacy `section_map_v1.yml` vocabulary |
| Syndication clusters | PLANNED | [target architecture](../architecture/TARGET_ARCHITECTURE.md) §6 |
| Language identification | PLANNED | a classical language identifier per block; an admission label, not an LLM task |
| Article type / genre | EVALUATION CANDIDATE | the one LLM evaluation candidate — see §7 |
| Quotation spans | LATER (research enhancement) | deterministic baseline first |
| Topic labels | LATER, only if a study needs them | |
| LCP instruments on press text | LATER | reusable code; eligibility needs a press definition |

## 7. LLM policy

> **Deterministic or classical methods are the default. An LLM layer is activated only when it
> shows a clear, reproducible net benefit against a realistic baseline on human gold.**

No LLM is part of the foundation path, and no stage may presuppose one. The decision pattern is
CO.RA.PAN 3.0's: a preregistered comparison against the realistic deterministic baseline on a
human-reviewed sample; **the baseline wins ties**; the stage must be reversible and fully traced;
it is qualified on the serving stack that will run it. If ever adopted, an LLM stage is
self-hosted; **no external model API in a production path**.

| Task | Verdict | Reason |
|---|---|---|
| Extraction / boilerplate removal | **No** — deterministic first | preserved bytes make deterministic iteration possible; an LLM pass over every page is the costliest option and rewrites text |
| Metadata (date, author, section) | **No** | no hallucinated reconstruction: a guessed date is worse than `unknown` |
| Language identification | **No** | a classical language identifier |
| Linguistic variety | **Never machine-labelled** | it is what the studies measure |
| Article type / genre, news vs opinion | **Evaluate** (Phase 4) | 21.8 % of legacy articles are `other_unclear` and the studies lose a quarter of the corpus; compare rules, a supervised classifier and an LLM on stratified human gold; adopt only if it beats the classifier; the label is an enrichment, never an admission gate |
| Author / role, agency material, structure, hard extraction failures | **No** | markup, patterns, similarity clusters, per-outlet rules |
| "Is this an article?" | **No** in the pipeline | structural gates; an LLM at most as a development-only audit aid |
| Quoted vs authorial text | **Later** | rule baseline first |
| Study-specific functional labels | **Not a corpus stage** | study or research layer; the corpus supplies stable ids and sentence-neighbour access |

Further semantic enrichments stay study or research layers until validated as a corpus instrument.
A development-only LLM aid (an error finder) is never on a production path and never writes a
corpus layer.

## 8. Legacy annotation

The legacy annotation (`coprepan-article-ann-v1.4`, `clean-v6`, `segment-v2`, `tense-v3`, spaCy
3.8.14, `es_dep_news_trf`, one run on 2026-06-13) stays as it is inside the frozen legacy release.
It is not re-annotated in place. A mapping note relates `tense-v3` labels to the verbal-complex
labels with `mapping_status: hypothesis` until audited on a bridge sample.
See [`docs/legacy/INDEX.md`](../legacy/INDEX.md).

## 9. Gates (Phase 4)

- **Annotation equivalence** with CO.RA.PAN 3.0 on a shared text sample: same input, same output.
- **Bridge sample** relating `tense-v3` to the verbal-complex layer.
- The article-type evaluation, if run, follows the evaluation-plan checklist
  ([methodology](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md) §6).

## 10. Open

| Item | Kind |
|---|---|
| Press sentence-boundary policy id and decision | technical/scientific, Phase 4 |
| Token denominator definition | joint with CO.RA.PAN, cross-corpus contract |
| Carrying of spoken-only token fields in the shared schema | joint, cross-corpus contract |
| Token/sentence export table — open in CO.RA.PAN 3.0 too ("the token-attribute export") | joint; design once |
| Whether COPREPAN locks transitive dependencies (CO.RA.PAN does not) | technical, Phase 4; must not break pin identity |
| NER use in studies | deferred: no gold in either corpus |

## 11. Milestones

- 2026-10-06 — instrument contract and LLM policy recorded (repository bootstrap). Nothing
  implemented.
