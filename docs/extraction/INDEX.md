# Extraction — component index

**Status: CONTRACT IMPLEMENTED; BASELINE EXTRACTOR ONLY (`EXPERIMENTAL`) — NOT VALIDATED, NOT
ADOPTED. EVALUATION INSTRUMENT BUILT; NO GOLD, NO RESULT.** No extraction of corpus material has
taken place. Governing decisions:
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §5–§6,
[CPD-0007](../decisions/CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md) §9–§10. Current state:
[`docs/STATUS.md`](../STATUS.md). Method for adopting an extractor:
[methodology](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md).

Entry point for: the extraction record, typed blocks, metadata with basis, the baseline extractor,
storage of extractions and replay. Design background:
[`TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md) §7.

---

## 1. What exists

| Thing | Code | Test |
|---|---|---|
| Extraction record, digests, `Extractor` wrapper | `src/coprepan/extraction.py` | `tests/test_extraction.py` |
| Baseline extractor `baseline_html/0.1.0` (standard library HTML parser) | `src/coprepan/extraction.py` | same |
| Storage under a fingerprint; replay from the preservation root | `src/coprepan/core_pipeline.py`, `src/coprepan/layer_store.py` | `tests/test_core_pipeline.py` |
| Extractor lifecycle | `src/coprepan/extraction.py` | `tests/test_admission_eval.py` |
| Evaluation harness, metrics, review package | `src/coprepan/extraction_eval.py` | `tests/test_admission_eval.py` |
| Gold-sample design (no sample) | [`GOLD_SAMPLE_DESIGN.md`](GOLD_SAMPLE_DESIGN.md) | — |
| Extractor candidates for Phase 3 (a list from general knowledge, unverified) | [`EXTRACTOR_CANDIDATES.md`](EXTRACTOR_CANDIDATES.md) | — |

## 2. Record (`coprepan-extraction/v1`)

| Field | Content |
|---|---|
| `extractor` | `name`, `version` |
| `input` | `body_sha256`, size, declared content type, charset and content coding |
| `outcome`, `reason` | `EXTRACTED` · `NOT_EXTRACTABLE` with `unsupported_content_type`, `content_type_unknown_and_not_html`, `empty_body`, `unsupported_content_encoding` or `undecodable_content_encoding` |
| `decoding` | `charset`, `basis` (`byte_order_mark`, `http_header`, `html_meta`, `default_utf8`, …), `replaced_characters` |
| `metadata` | per field `value`, `basis`, `candidates[]` — fields `title`, `author`, `publication_date`, `modification_date`, `section`, `language` |
| `blocks[]` | `index`, `kind`, `role`, `text` |
| `extracted_text_sha256` | over the canonical JSON of `[kind, role, text]` of all blocks — the digest a document version is identified by |
| `body_text_sha256` | over the BODY view — the digest the `duplicate_of` relation uses |

The record holds no timestamp, path or run id: the same input gives the same bytes. When and by
which run an extraction was stored is execution provenance in the layer-store manifest.

## 3. Structural parts

| Part | Where |
|---|---|
| TITLE | the block with role `title` (the first `h1`); candidates with basis in `metadata.title` |
| BODY | the blocks with role `body`; `body_text` joins them with a blank line. **The primary linguistic text surface.** |
| AUTHOR, PUBLICATION_DATE, SECTION | `metadata`, value as published plus basis |
| everything else | blocks with role `non_body` (navigation, header, footer, aside, figure, form, captions): kept, typed, outside the body view |

A role describes markup. It is not a register, a genre or a section, and no later stage may read
it as one.

## 4. The baseline extractor

What it does: decodes by BOM, HTTP charset, declared charset, UTF-8; takes the first of
`article`, `main`, `body` as the body container; types `p`, `li`, `blockquote`, `figcaption`,
`h1`–`h6` and text standing in no block element; reads JSON-LD, OpenGraph, `meta`, `title`,
`html lang`. Whitespace inside a block is collapsed to single spaces — the one change it makes to
a text.

What it deliberately does not do (each a measured legacy defect, [archaeology](../legacy/ARCHAEOLOGY.md)
§6): no paragraph dropped for its length or for a substring; no word split or joined; no date
parsed, converted or substituted; no default language; no "cleaned" title.

**What is not known about it:** how well it finds the article body on any real page. It has seen
four synthetic pages. Its container rule is the simplest possible and will be wrong on real
templates. It exists to exercise the contract.

## 5. Rules

- Extraction reads only fetches of kind `item` that are `RAW_PRESERVED`, from the preservation root.
- The stored body keeps its HTTP content coding (CPD-0006 §1.2). Undoing `gzip` / `deflate` is the
  first recorded step of extraction; the coding is part of the fingerprint. The stored bytes are
  never changed, and a decoded body above 64 MiB is refused rather than expanded.
- One answer per fingerprint. A rerun is a no-op; a different answer is an error.
- A new extractor version is a new fingerprint and a new artefact; old artefacts stay valid for
  their version (forward-only). Re-extracting existing material under a new version for the
  corpus is a change decision, not a consequence of the new version existing.
- An extractor is adopted only after a comparison on a gold sample against the realistic baseline.

## 6. Open

| Item | Kind | Where |
|---|---|---|
| Gold sample stratified by outlet; preregistered comparison of extractor candidates; adoption | scientific, Phase 3 — **instrument and design delivered 2026-10-07** (§8); the sample, the codebook, the reviewers and the criterion are open | master plan §11; [`GOLD_SAMPLE_DESIGN.md`](GOLD_SAMPLE_DESIGN.md) §9 |
| Per-outlet rule sets and their versioning | technical, Phase 3 | target architecture §7 |
| Admission labels: content level (article / not article, access class, language from content, length, type) | scientific, Phase 3 — the **technical** label exists ([admission](../admission/INDEX.md)) | target architecture §3 |
| DOM anchors per block | technical, Phase 3 | target architecture §7 |
| Date parsing, time zone, date-basis ranking | scientific, Phase 3 | corpus supply §3 |
| Section mapping, register, genre, opinion | enrichment layers, not extraction | CPD-0005 §6 |

## 7. Milestones

- 2026-10-07 — extraction contract decided (CPD-0005), implemented with a baseline extractor,
  stored and replayed in the vertical canary on synthetic fixtures. Nothing validated.
- 2026-10-07 — extractor lifecycle, evaluation harness and review package decided (CPD-0007) and
  built; gold-sample design and candidate list written. Exercised on synthetic pages only. No
  gold, no comparison, nothing adopted.

## 8. Lifecycle and evaluation (CPD-0007 §9–§10)

**Lifecycle**: `EXPERIMENTAL` → `CANDIDATE` → `VALIDATED` → `ACTIVE` → `RETIRED`.
`baseline_html/0.1.0` is `EXPERIMENTAL`; `Extractor.require_active()` refuses anything that is not
`ACTIVE`. A step is a decision with evidence.

**Harness** (`extraction-eval/1`):

| Step | Function | Output |
|---|---|---|
| draw | `draw_sample(frame, strata, per_stratum, seed)` | cases, by hash order within strata |
| freeze | `sample_manifest(...)`, `verify_sample` | `coprepan-extraction-sample/v1` with `sample_sha256` |
| run | `evaluate(manifest, arms, body_of, references=None, catastrophic_retention_below=None)` | `coprepan-extraction-evaluation/v1`: per case and arm the state (`OK` · `EXTRACTOR_ERROR` · `NO_OUTPUT`), digests, pairwise disagreement, scores where a reference is `JUDGED`, a summary |
| review | `review_package(manifest, result, body_of, out_dir, blind_seed)` | one `coprepan-extraction-review-case/v1` per case, blinded; `blinding_key.json` apart |
| reference | `reference_from_decisions(review_dir)` | `coprepan-extraction-reference/v1` per decided case |

Arms are extractors or `PrecomputedArm`s. Each arm runs twice per case; two answers stop the run
(`NonDeterministicArm`). The body a case names must have the hash the manifest froze. A scored
evaluation needs `catastrophic_retention_below` stated: it has no default.

**Metrics** against a `JUDGED` reference: `text_retention` (share of reference tokens reproduced),
`boilerplate_inclusion` (share of the arm's tokens not in the reference), `body_boundary` (first
and last tokens agree), `title_correct`, per-field `metadata`, `catastrophic` (`no_output`,
`not_extracted`, `empty_body`, `body_mostly_lost`). **Diagnostics, not verdicts**: they are token
comparisons and cannot see whether a boundary is editorially right.

**What this is not**: a gold sample, a comparison, a result. The harness has seen synthetic pages
only, and its own numbers on them say nothing about any extractor on any real page.
- 2026-10-07 — the extraction record's place in the layer chain and what later layers rely on
  are fixed in [`PHASE3_SCIENTIFIC_ARCHITECTURE.md`](../architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md)
  (CPD-0008): blocks become the units of the analysis contract, the role decides the surface,
  BODY is the primary linguistic surface, the title a separate one. No change to the record.
