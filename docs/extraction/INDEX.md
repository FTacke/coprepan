# Extraction — component index

**Status: CONTRACT IMPLEMENTED; BASELINE EXTRACTOR ONLY — NOT VALIDATED, NOT ADOPTED.** No
extraction of corpus material has taken place. Governing decision:
[CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §5–§6. Current state:
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

## 2. Record (`coprepan-extraction/v1`)

| Field | Content |
|---|---|
| `extractor` | `name`, `version` |
| `input` | `body_sha256`, size, declared content type and charset |
| `outcome`, `reason` | `EXTRACTED` · `NOT_EXTRACTABLE` with `unsupported_content_type`, `content_type_unknown_and_not_html` or `empty_body` |
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

- Extraction reads only fetches that are `RAW_PRESERVED`, from the preservation root.
- One answer per fingerprint. A rerun is a no-op; a different answer is an error.
- A new extractor version is a new fingerprint and a new artefact; old artefacts stay valid for
  their version (forward-only). Re-extracting existing material under a new version for the
  corpus is a change decision, not a consequence of the new version existing.
- An extractor is adopted only after a comparison on a gold sample against the realistic baseline.

## 6. Open

| Item | Kind | Where |
|---|---|---|
| Gold sample stratified by outlet; preregistered comparison of extractor candidates; adoption | scientific, Phase 3 | master plan §11 |
| Per-outlet rule sets and their versioning | technical, Phase 3 | target architecture §7 |
| Admission labels (article / not article, access class, language from content, length, type) | technical and scientific, Phase 3 | target architecture §3 |
| DOM anchors per block | technical, Phase 3 | target architecture §7 |
| Date parsing, time zone, date-basis ranking | scientific, Phase 3 | corpus supply §3 |
| Section mapping, register, genre, opinion | enrichment layers, not extraction | CPD-0005 §6 |

## 7. Milestones

- 2026-10-07 — extraction contract decided (CPD-0005), implemented with a baseline extractor,
  stored and replayed in the vertical canary on synthetic fixtures. Nothing validated.
