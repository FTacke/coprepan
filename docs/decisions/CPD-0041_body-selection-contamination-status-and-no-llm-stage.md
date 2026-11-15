# CPD-0041 — BODY selection block by block, a contamination status apart from CORE, and no LLM stage

| Field | Value |
|---|---|
| Date | 2026-11-15 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| What is active | the preferred candidates `article_html/0.4.0` (record schema `extraction/3`, the pinned table `body-templates/1`), `body-quality/1`, `agency-credit/3` in `editorial-metadata/3`. **None is validated or activated**; nothing binds a release, an admission or a stored record. Their activation is the operator's, after the BODY control (*Not decided here*) |
| Decided by | the operator's brief of 2026-11-15 ("CO.PRE.PAN_v3 – Autonome BODY-Qualitätsoptimierung": implementation and offline evaluation authorised; the phase-3 blind control is development material now); the rules are the commissioned agent's |
| Kind | extraction · scientific method |
| Execution | `extraction.py` (`extraction/3`, the closed selection vocabulary), `extraction_body.py` (`article_html/0.4.0`), `body_quality.py` (`body-quality/1`), `provenance.py` (`agency-credit/3`), `enrichment.py` (`editorial-metadata/3`); `config/extraction/body-templates_1.json`; `scripts/study_body_quality.py`; `tests/test_body_quality.py` |
| Builds on / amends / supersedes | builds on CPD-0039 and CPD-0040; **partially supersedes CPD-0040** as the preferred candidate for the extractor (`0.3.0` → `0.4.0`) and the metadata envelope (`editorial-metadata/2` → `/3`). Everything earlier stays in the code unchanged |
| Does not change | `extraction/1`–`/2` and `article_html/0.1.0`–`0.3.0` (their code and records); the title and subtitle surface of 0.3.0; `content-quality/3` and its 150-word minimum (applied unchanged to the new BODY); `section-map/1`, the IPTC extracts, the scope, genre and AI layers, `agency-credit/1`–`/2`, `text-reuse/2`; the joint contracts (`release_export` refuses an `extraction/3` record as it refuses `/2`) |
| Run report | [`2026-11-15 BODY quality`](../agent-runs/2026-11-15_coprepan-body-quality.md) |
| Evidence | [study record](../intake/quality/body_quality_study_2026-11-15.json) (the 4,759 stored item pages), [BODY control](../intake/quality/body_quality_control_2026-11-15/README.md) (frozen before review) |

## Context

The operator's reading of the phase-3 blind control found BODY texts with page furniture (breadcrumbs, share and audio controls,
"RELACIONADAS", promotions, AI and agency notes), a missing lead (C01), an author filter extracted as two "identical" articles
(C05, C54) and a column submission note as the "same text" of two opinion pieces (C49). The study of all stored pages showed
the general form: recurring outlet furniture in the BODY of 1,952 pages under 0.3.0, a body ending in a label heading on 342,
an author filter as the container on 30, lead paragraphs outside the chosen container.

## Decision

### 1. `article_html/0.4.0` on `extraction/3`

0.3.0's container rule and title surface; the BODY decided block by block, every decision recorded on the block
(`selection`: rule, decision, reason) with its text and position unchanged, so the BODY before the selection is read back from
the record. Text in form controls is never scored and never BODY. **Excluded**: form controls and blocks without letters; page
modules by markup on the block or an element below the container (advertising, share, related, newsletter, breadcrumb, tags,
caption and gallery, date, social embeds, audio and page controls, channel promotion) when the element holds under 30 % of the
container's text, bylines at the BODY's edges only; production notes in the forms of `ai-disclosure/1` (text forms only) and
agency material notes; verbatim repeats of at least 12 words; blocks of the pinned outlet-template table; label headings (≤ 4
words) that end the BODY; a short letter-only label printed at least three times. **Included**: a paragraph the page states as
its JSON-LD `articleBody`; the lead paragraph adjacent before the first BODY block in the container's `<article>` element.
No block is split or rewritten; no outlet rule.

The **template table** (`body-templates/1`, `config/extraction/body-templates_1.json`) holds digests only: blocks one outlet
prints in at least 5 unrelated articles of the reference population (articles sharing more than 0.2 of their other 8-word
shingles are one story); 3–4 unrelated articles: recurring, kept and reported. A new table is a new extractor version.

### 2. `body-quality/1`

`clean` · `cleaned` · `residual_suspect` · `incomplete` · `not_article`, with evidence (selection counts, words before and
after, signals: an address or file path in a BODY block, a block opening as a photo credit, several label-like blocks, a
recurring-but-kept block). A statement about the extraction; the CORE decision is the gate's, unchanged.

### 3. `agency-credit/3`, `editorial-metadata/3`

`/2` would read the bylines of teaser cards that 0.4.0 moves out of the BODY as the article's own (10 pages). `/3` is `/2` that
does not read blocks excluded as foreign page modules; on a record without a selection it equals `/2`.

### 4. No LLM stage

Measured on the stored pages and read by the agent (diagnosis, not gold), the remaining defects are of three kinds: text that
is absent at the source (JS-rendered pages, paywall stubs: `not_article` 159, `incomplete` 27 pages — no model recovers text
that is not there); foreign material *inside* a block (an image address glued to a caption, a tweet glued to a paragraph) —
a span-level question the record cannot represent without a new schema; and small unmarked, non-recurring labels.
`residual_suspect` flags 332 pages (7.0 %), 295 of them CORE-accepted; on a sample of 24 flagged pages about half carried real
residue, nearly always a few words. An LLM would neither change CORE decisions nor recover missing text; its benefit is a few
words of contamination on a few percent of pages, against an inference stage, its validation on gold and a span-level
representation. **No LLM stage is built or proposed for activation.** The escalation contract, should a later run need it, is
in the run report (§12).

## Measured (4,759 stored pages, offline; agent readings are not gold)

- BODY changed on 2,286 pages (2,473 identical); container changed on 23 (form controls); no title changed; 18 subtitle sets
  changed (`gt_prensa_libre`, where the article now replaces the author filter); no schema problem.
- Words: 2,553,275 → 2,527,879. Removed by reason (blocks / pages / words) and included (lead 146 / 146 / 9,467; stated body
  437 / 165 / 18,932) in the study record.
- **Against the publisher's own `articleBody`** (where stated): no excluded byline, caption, date, related, share, tag,
  advertising, newsletter, form-control, label or trailing-heading block is in it; 33 template blocks and 9 embed blocks are
  (the publisher's articleBody carries its promotions and quoted tweets); 54 of 84 checkable lead inclusions are in it.
- CORE (`content-quality/3`): 4,066 → 4,067 accepted; 26 newly rejected (21 below 150 words once the furniture is gone --
  the removed blocks of 9 of them read: embeds, promotions, labels, dates, author biographies, nothing of the article; 4 `incomplete_against_stated_body`
  at `cl_biobiochile`, whose stated body counts the quoted tweets; 1 live page whose time-stamped share rose), 27 newly
  accepted (11 `gt_prensa_libre` pages whose article replaces the author filter, leads and stated paragraphs recovered).
- Every other layer has the same value on every page (`agency-credit/2` → `/3` included).
- Text reuse: 547 → 293 relations; the 287 lost are within-outlet `exact` pairs of furniture (an author filter, a paywall
  footer, a submission note); 33 new cross-outlet pairs; cross-outlet `exact` 9 → 15, `near_identical` 102 → 146.
- Cost: 12.8 ms per page against 11.6 ms (one process, beside CO.RA.PAN's production); `body-quality/1` 2.1 ms.

## Alternatives considered

- **Every paragraph of the `<article>` element** — a third of what it added on pages with a stated articleBody was not in it
  (captions, author biographies); narrowed to the adjacent lead.
- **Hiding marked text from the container scoring** — moved the container away from the article on 253 pages (a "cuerpo ad"
  class around the article); dropped.
- **Templates from 3 unrelated articles** — removed recipe headings, a poll's technical sheet, column names; raised to 5.
- **"teaser" as a related-module mark** — removed a paywalled article's visible lead; dropped.
- **Removing image credits and URLs inside blocks** — would rewrite published text; reported instead.
- **An LLM pass** — §4.

## Not decided here (the operator's decision)

1. After the BODY control: adopt `article_html/0.4.0` (with `body-templates/1`) as the corpus extractor, and whether
   `body-quality/1` is shown in a release.
2. Whether completeness against a stated articleBody should count blocks the selection excluded (the 4 `cl_biobiochile`
   pages; a change of `content-quality/3` is a new version).
3. Whether embedded social posts and the outlet's own posts belong in a layer of their own.
4. Unchanged: the joint requests of CPD-0039/0040; the phase-3 blind control's verdicts (now development material).
