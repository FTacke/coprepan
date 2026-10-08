# Extraction review codebook — version 1

**Status: DRAFT FOR REVIEW, written before any real page has been seen (2026-10-08).** It completes
what [`GOLD_SAMPLE_DESIGN.md`](GOLD_SAMPLE_DESIGN.md) §5 left as "to be completed into a codebook with
examples". It is versioned (`codebook_version: 1`); a change makes version 2, and scores under different
versions are not compared. Nothing here asks a reviewer for genre, register, section, opinion or
language (design §1).

## 1. What a reviewer decides, per case

| Field | Values | Rule |
|---|---|---|
| `state` | `JUDGED` · `NOT_AN_ARTICLE` · `DAMAGED_SOURCE` · `UNJUDGEABLE` | see §2 |
| `title` | text | the article's headline as the page shows it; empty if there is none |
| `body` | text | from the first to the last body paragraph, in page order (§3) |
| `metadata` | author · publication date · modification date · section · language | as the page states them, in the page's own words; empty if it states none; never inferred, never normalised |
| per candidate | title correct · body start correct · body end correct · text missing · boilerplate included | yes / no / cannot tell, against the reviewer's own `title` and `body` |
| `uncertain` | yes / no | only for real damage or real ambiguity (§4) |
| `notes` | free text | why, briefly |

## 2. The four states

- `JUDGED` — the page is one article and the reviewer can say what its title and body are.
- `NOT_AN_ARTICLE` — a section front, tag or author page, home page, gallery, video page, search page,
  or an error page served with status 200. A result, not a failure.
- `DAMAGED_SOURCE` — the preserved body is truncated, garbled or mis-decoded so that the article cannot be read
  from it (not: an extractor got it wrong).
- `UNJUDGEABLE` — a careful reader cannot say what the body is (for instance a live blog whose entries and updates
  have no clear article text). Used rarely; never as a way of skipping a hard case.

Cases that are not `JUDGED` are reported with their counts and are not scored for text overlap.

## 3. What belongs to the body

The body is the text the publisher wrote as the article, from its first to its last paragraph, in page order.

| Element | In the body? |
|---|---|
| paragraphs, including very short ones | yes — a short paragraph is never dropped for its length |
| subheadings inside the article | yes |
| block quotes and pull quotes that are in the article's flow | yes; a pull quote that repeats a sentence already in the text: **no** (it is a layout echo) |
| lists inside the article | yes |
| the lede or standfirst printed between headline and text | yes |
| image captions and credits | **no** |
| a byline or date line repeated inside the text container | **no** (metadata, not body) |
| "Lea también", "Te puede interesar", related-article teasers, inserted read-more blocks | **no** |
| advertising, newsletter and subscription prompts, consent or paywall notices | **no** |
| comment sections, share buttons, tags, navigation, footers | **no** |
| embedded social posts | **no**, unless the article's own text quotes them in its flow |
| a correction or update note written by the outlet and part of the article | yes, where it is in the article's flow; one that is a banner outside the flow: **no** |
| the second and later parts of a multi-page article | not in the preserved page; the page's own text only |

## 4. When `uncertain` is allowed

Only when the page is damaged or the answer is genuinely ambiguous in a way the codebook does not settle —
and then the reviewer writes the rule that is missing in `notes`, so that version 2 can decide it. "Hard" is not
"uncertain". An `uncertain` case is kept, reported separately, and excluded from the headline rates.

## 5. Per-candidate judgements

Candidates are shown as `A`, `B`, … in an order that changes per case. For each, against the reviewer's own title and body:

- **title correct** — the extracted title is the headline (minor whitespace excepted).
- **body start correct / body end correct** — the first and last extracted body sentences are the article's first and last (the lede counts; a byline, caption or teaser at the start or a related-links block at the end make it wrong).
- **text missing** — a body paragraph that the page has and the candidate lacks (yes/no; if yes, which, in `notes`).
- **boilerplate included** — text that §3 excludes is present in the candidate's body (yes/no; which, in `notes`).

A reviewer does not see a candidate's name, score, rank or default, or another reviewer's decision.

## 6. Agreement and freezing

At least two reviewers judge an overlapping subset independently; agreement is reported per field before
adjudication, and the pre-adjudication decisions are kept (design §6). A decision, once submitted, is never edited:
a correction is a new decision that names the one it replaces (design §7).
