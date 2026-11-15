# CPD-0038 — A candidate article extractor and a candidate content-quality gate (not adopted)

| Field | Value |
|---|---|
| Date | 2026-11-15 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| What is active | the two candidates exist, implemented and measured, as `CANDIDATE`s; **they are not binding**: the scientific activation of a content-admission standard and of an extractor is the operator's (*Not decided here*) |
| Execution | `extraction_article.py` (`article_html/0.1.0`, lifecycle `CANDIDATE`), `content_quality.py` (`content-features/1`, `content-quality/2`, lifecycle `CANDIDATE`), `scripts/study_content_quality.py`; `tests/test_content_quality.py` |
| Builds on / amends / supersedes | builds on CPD-0005 (the extraction contract), CPD-0007 (technical admission labels, extractor lifecycle), CPD-0018 (the extraction comparison); amends nothing; supersedes nothing |
| Does not change | `baseline_html/0.1.0` and every stored extraction; `admission-technical/1` and its labels; any release view or release gate; the raw evidence (nothing is deleted or relabelled; a rejection says only that this extraction is not taken into the analysis corpus under this rule set) |
| Decided by | the operator's brief of 2026-11-15 (§2 "Qualität vor Recall", §4–§7); the rules are the commissioned agent's, the activation is the operator's |
| Run report | `docs/agent-runs/2026-11-15_coprepan-weekend-source-qualification.md` §4–§6 |

## Context

The baseline extractor fails on measured page structures (CPD-0018 diagnosis of the weekend), and nothing separated coherent
editorial texts from frames, section pages, walls and machine text: `admission-technical/1` only says that a text exists. The brief
of 2026-11-15 asks for a simple, deterministic, precision-first selection. Three states are kept apart: raw archiving (`RAW_PRESERVED`, the ledger), technical usability (`admission-technical/1`: an extracted text exists), content quality
(this record: the extracted body is a coherent editorial text). None implies another.

## Decision

### The extractor

`article_html/0.1.0` keeps the baseline's contract and changes one structural rule: the body container is the element that carries
the most running text (block text without link text counts for its element and half for the parent), its parent when that carries a
real share of its own, and sibling elements with at least a fifth of its score; paragraphs and list items are closed as HTML closes
them; inside the container `nav`/`aside`/`footer`/`form`/`figure`/`header` and link-heavy blocks are not body. It repairs the
measured defects of the baseline (teaser `<article>` cards before the article; an article container inside a page `<header>`;
unclosed paragraphs; an article split into sibling elements). On the 2,413 stored pages that state a JSON-LD `articleBody` it lands
within 85–125 % of it on 1,987 (baseline: 899).

### The gate (`content-quality/2`)

A page is **rejected** -- with every reason that applies, machine-readable -- when: the answer is not 2xx; nothing was extracted;
the body is empty; it has fewer than 150 words; its function-word share is below 0.30 (lists, names, menus, another language); it
speaks to the reader about the page (ad-blocker, JavaScript, consent, browser); it is paywall text; it carries a machine-generated
summary or declares itself made with AI (`machine_text`); it is sponsored (a block that begins with a sponsor mark, or a sponsor mark
or advertising section in the address); it is a live page (time-stamped updates, a live slug or title); it is a page about the
publication (institutional, FAQ, terms, subscription); it is less than half of the article body the page itself states; it repeats
itself; its body stands under three or more URLs of one outlet (a template); or an earlier page of the same outlet has the same body
(a duplicate; the earliest is judged on its merits). Agency copy across outlets is kept (whether it counts once is a corpus decision).
Every other page is accepted. Deterministic; the thresholds are named in `THRESHOLDS`; a changed rule is a new rule set.

## How it was chosen and measured

The stored item pages (4,759: the October pilot and 24-hour intake, the weekend waves) were split by `sha256(fetch_id)` into two
halves. The rules were chosen on the agent's own reading of 108 stratified pages and 40 hard negatives of the first half (not a gold
standard). `content-quality/1` was frozen (commit `b7d5f86`) and read **blind** on 140 pages of the second half (100 accepted, 40
rejected, shuffled, without decision or features): 94 of 100 accepted pages good. The five general classes of its false accepts were
closed in `/2` (commit `f1a0103`), which was read blind on a second, unseen draw of the second half: **97 of 100 accepted pages good
(95 % Wilson interval 91.5–99.0 %)**, 98 counting only the certain cases. Its false accepts: a lottery results page and two unmarked
promotional texts (native advertising) -- the residual class simple rules do not separate. Of the rejected pages about half were
good texts, nearly all complete briefs under 150 words: the recall the rule set gives up by design.

## Alternatives considered

- **A length threshold alone** (150 words): 7 bad pages accepted on the development reading — frames in full sentences, terms of
  use, live previews pass it.
- **A lower or higher minimum** (100/120 or 200/250 words): one more false accept at 100–120; 11–29 more good pages lost at 200–250
  for no measured precision gain.
- **Lexical diversity (type-token ratio)**: falls with length and separated nothing the function-word share and the 5-gram ratio do
  not; not used.
- **JSON-LD `articleBody` as the text**: a publisher-stated field that is often a summary (`ar_rio_negro`: 77 of 79 pages) or absent;
  used only as a comparison value (the shortfall rule).
- **A classifier or an LLM**: not needed for the precision reached, against the brief's preference for simple rules; not used.
- **Rescue rules per outlet** (CSS or XPath for `hn_la_prensa`, `pa_laestrelladepanama`, client-rendered `ar_pagina12`): not built —
  the gate rejects those pages, and enough other material exists.

## Not decided here (the operator's decision)

1. Whether `content-quality/2` (or a later rule set) becomes binding for corpus admission or for a release view, after the human
   review sample (`docs/intake/quality/content_quality_review_2026-11-15.md`).
2. Whether texts that declare themselves AI-assisted (seen at `co_elpais`, `ar_la_nacion`, `ar_clarin`, `cl_biobiochile`,
   `ni_nicaragua_investiga`, `co_el_espectador`) belong in the corpus at all -- until then they are not admitted.
3. Whether complete briefs under 150 words are wanted (on the calibration and hard-negative reading, a minimum of 120 words let one
   bad page through that 150 rejects, and admitted 11 more good ones).
4. Whether `article_html/0.1.0` becomes the corpus extractor (`VALIDATED` needs a gold sample, CPD-0007 §7).
