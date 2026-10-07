# Extraction gold sample — design

**Status: DESIGN ONLY. No gold sample exists, no case has been drawn, no page has been judged.**
This document fixes *how* a gold sample is built so that the questions are settled before the
first real page is looked at. Every number is a parameter still to be set; none is proposed here.
Decision that makes it binding: Phase 3 (master plan §11). Instrument:
`src/coprepan/extraction_eval.py` ([CPD-0007](../decisions/CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md) §10).

Why a design before the data: a gold sample assembled after looking at extractor outputs measures
what its makers already believed. Order of work: design → frozen sample → blinded review → frozen
reference → comparison.

## 1. What the sample is for

One question: **for a preserved page, which text is the article's title and body, and which
metadata does the page state?** The reference answers that per case. It is used to compare
extractor candidates and, later, to detect regressions.

It is not for: deciding whether a page belongs in the corpus, its genre, register, section or
opinion status, or anything about language. A reviewer is never asked for these.

## 2. Sampling unit and frame

- **Unit**: one preserved fetch of kind `item` — a body hash in a sealed pack. Not a URL, not a
  document: two fetches of one URL are two possible units.
- **Frame**: the item fetches preserved by the Phase-2 canary and whatever follows it, restricted
  to `RAW_PRESERVED`. The frame is described in the sample manifest (`frame_description`) with the
  run ids and pack ids it was built from.
- **No legacy text in the frame.** The legacy system kept no raw HTML; a legacy extraction has no
  page to be judged against. Legacy outputs can enter only as a precomputed arm on pages that
  were fetched again.
- Fetches with an HTTP error status, non-HTML content or an empty body are **in** the frame as
  their own stratum (§3), not removed: how an extractor behaves on them is part of the question.

## 3. Stratification

Strata are attributes known *before* extraction, from the registry and the fetch record only:

| Stratum | Source | Why |
|---|---|---|
| outlet | registry | templates differ by outlet more than by anything else |
| country | registry | balance across the project's population |
| outlet type | registry | different publishing systems |
| discovery channel kind | discovery event | feeds and sitemaps list different page populations |
| response class | fetch record: 2xx HTML · error status · non-HTML | failure behaviour |
| time slice | fetch record | template changes over time |

No stratum may be derived from an extractor's output (length of extracted text, detected section,
"looks like an article"): that would condition the sample on the thing under test.

Drawing: within each stratum, cases ordered by the hash of seed and case id; the first *n* taken
(`draw_sample`). Seed and *n* are recorded in the manifest. A stratum with fewer than *n* cases
contributes all it has, and the shortfall is reported.

**Parameters to set, not set here**: *n* per stratum; which strata are crossed; the minimum
number of outlets; total size. They follow from the precision the comparison needs and the review
time available — an estimate of both belongs in the Phase-3 decision.

## 4. Page types to make sure of

Stratified drawing will under-represent rare, hard page types. A second, **purposive** part of the
sample is allowed, kept apart (`strata.part = purposive`) and never pooled with the stratified
part in a rate:

- very short items (briefs, agency flashes); very long ones
- live blogs and continuously updated pages
- pages dominated by a gallery, a video or an embed
- interviews and question–answer layouts; lists
- opinion pages with an author box inside the body container
- paywalled or truncated pages; consent and login walls
- pages with related-article blocks, inserted read-more teasers or advertising inside the body
- multi-page articles; AMP or mobile variants
- pages with a correction or update note
- section fronts, tag pages and home pages that a channel listed as if they were items
- error pages served with status 200

Purposive cases are found by reviewers browsing the frame, **before** any extractor output is
shown to them.

## 5. What a reviewer sees and records

Per case (`coprepan-extraction-review-case/v1`, written by `review_package`):

- the preserved page: its visible text in a neutral rendering, and access to the preserved bytes;
- each candidate's title, body, other blocks and metadata under a **blinded label** (`A`, `B`, …)
  whose order changes per case; the key sits in a separate file not given to reviewers;
- an **empty** decision form. Nothing is pre-filled, no candidate is marked as default.

The reviewer records:

| Field | Content |
|---|---|
| `state` | `JUDGED` · `NOT_AN_ARTICLE` · `DAMAGED_SOURCE` · `UNJUDGEABLE` |
| `title` | the article's title as the page shows it |
| `body` | the article's body text, from first to last body paragraph, in page order |
| `metadata` | author, publication date, modification date, section, language — **as the page states them**, or left empty; never inferred |
| per candidate | title correct · body start correct · body end correct · text missing · boilerplate included |
| `reviewer`, `reviewed_at`, `notes` | |

Rules for the body, to be completed into a codebook with examples before the review starts:
captions, pull quotes, subheadings, embedded social posts, correction notes, bylines repeated in
the text, "read also" lines — each needs one written rule. The codebook is versioned and its
version recorded with every decision.

States other than `JUDGED` are results, not failures: a section front is `NOT_AN_ARTICLE`; a
truncated or garbled body is `DAMAGED_SOURCE`; a page on which reviewers cannot agree what the
body is, is `UNJUDGEABLE`. Such cases are reported with their counts and are not scored for text
overlap.

## 6. Reviewers and agreement

- At least two reviewers judge an overlapping subset independently; its size is a parameter.
- Agreement is reported per field before any adjudication, and disagreements are adjudicated by a
  written procedure, with the pre-adjudication decisions kept.
- A reviewer does not see another reviewer's decision or the blinding key before finishing.
- Who reviews, and with what training, is recorded. It is not decided here.

## 7. Freezing and provenance

| Thing | Frozen as |
|---|---|
| sample | the sample manifest and its `sample_sha256` (cases bound to body hashes) |
| review package | its `index.json` with sample and evaluation hash |
| decisions | one file per case and reviewer; **never edited after submission** — a correction is a new decision file that names the one it replaces |
| reference | the set of adjudicated decisions, with codebook version, as one hashed release |

A reference is valid for the sample it was made on and for no other. Adding cases makes a new
sample id. A change of codebook makes a new reference version; scores under different versions
are not compared.

## 8. What the automatic metrics may and may not carry

`text_retention`, `boilerplate_inclusion`, `body_boundary`, `title_correct`, per-field metadata
agreement and the `catastrophic` flag are computed against a `JUDGED` reference by token
comparison. They are **diagnostics**:

- they locate cases worth reading; they do not replace the per-candidate judgements of §5;
- a threshold (for instance for "catastrophic") is stated in the evaluation plan before the
  reference is opened;
- pairwise disagreement between arms needs no reference and is used to choose which cases
  reviewers see first — never as evidence that either arm is right.

## 9. Open

| Item | Kind |
|---|---|
| sizes, crossed strata, overlap share | scientific, Phase 3 |
| the codebook | scientific, Phase 3 |
| reviewers, training, adjudication procedure | scientific, operator |
| the adoption criterion for an extractor | scientific, Phase 3, preregistered |
| where review packages and decisions are stored | technical; needs O-3 |
