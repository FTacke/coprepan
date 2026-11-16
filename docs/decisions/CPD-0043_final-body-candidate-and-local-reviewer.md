# CPD-0043 — The final BODY/CORE candidate (`article_html/0.4.2`), the end of development, and a local reviewer for the validation

| Field | Value |
|---|---|
| Date | 2026-11-16 |
| Status | `PARTIALLY_SUPERSEDED` |
| What is active | the preferred candidates `article_html/0.4.2` (`extraction/3`, the pinned `body-templates/1`) with the unchanged `content-quality/4` (`content-features/2`) and `body-quality/2`; the local reviewer `body_review` (package `coprepan-body-review-package/v1`, events `coprepan-body-review-event/v1`, export `coprepan-body-review-judgments/v1`, result `coprepan-body-review-result/v1`); a frozen validation package, prepared and **not reviewed**. **Nothing is validated or activated**; scientific acceptance is the operator's (*Not decided here*) |
| Decided by | the operator's brief of 2026-11-16 ("CO.PRE.PAN_v3 – Finaler BODY-/CORE-Qualitätsabschluss und HTML-Reviewer": develop until no change has a sufficiently evidenced net benefit, accept `NO_CHANGE` where right; no new blind human control during development; build a local reviewer; no activation); the rules and the tool are the commissioned agent's |
| Kind | extraction · scientific method · validation tooling |
| Execution | `extraction_body.py` (`article_html/0.4.2`, revision 2), `content_quality.py` (`stated_body_text`, measure unchanged), `extraction.py` (selection reason `linked_paragraph`); `body_review.py` with `body_review_app/`; `scripts/body_review.py`, `scripts/study_body_final.py`, `scripts/study_body_quality.py compare`; `tests/test_body_final_candidate.py`, `tests/test_body_review.py` |
| Builds on / amends / supersedes | builds on CPD-0042; **partially supersedes CPD-0042** as the preferred extractor (`0.4.1` → `0.4.2`). `content-quality/4`, `content-features/2` and `body-quality/2` stay preferred, unchanged. Every earlier version stays in the code unchanged |
| Does not change | `article_html/0.1.0`–`0.4.1`, `body-templates/1`, `content-quality/1`–`/4` and their thresholds, `content-features/1`–`/2` (measured identically), `body-quality/1`–`/2`, the 150-word minimum and the letter-word definition, every metadata layer, `text-reuse/2`; the frozen controls (manifests, forms, keys, verdicts); the joint contracts |
| Run report | [`2026-11-16 BODY final and reviewer`](../agent-runs/2026-11-16_coprepan-body-final-and-reviewer.md) |
| Evidence | [0.4.1 → 0.4.2 on every stored page and on the frozen control](../intake/quality/body_final_candidate_2026-11-16.json), [the final study](../intake/quality/body_final_study_2026-11-16.json), [the frozen validation package](../intake/quality/body_final_review_2026-11-16/README.md) |

*Status line 2026-11-16 (later the same day):* **partially superseded by [CPD-0044](CPD-0044_independent-body-core-validation-design-and-gold-reviewer.md)**
(was `ACTIVE_WITH_VALIDATION_DEBT`) in §5 only: the prepared 120-case package draws from the development population and is
`DEVELOPMENT_DIAGNOSTIC / NOT_INDEPENDENT_HOLDOUT`, not the validation; its reviewer annotates the candidate's blocks and is
replaced for gold by the model-independent `gold_review`; its scoring is design-weighted since then. The candidates
`article_html/0.4.2`, `content-quality/4`, `body-quality/2` stay the preferred ones, unchanged. Nothing here is rewritten.

## Context

CPD-0042 left a candidate whose control showed no deleted article text and 2.2 % residue, and four open questions. The brief
asked for a last evidence-led pass over every known error class on the stored pages -- missing and wrongly removed text,
contamination, misleading stated bodies, structured texts, live pages, the interaction of extractor, status and gate -- and for a
reviewer with which the operator can validate the result efficiently.

## Decision

### 1. Error classes examined on the 4,759 stored pages (0.4.1 as the baseline)

The stated articleBody was read against the BODY on the 2,092 pages that state one of at least 1,000 text characters; every
signal was traced to the blocks of the record and read on the page.

- **Gaps between the BODY and the stated text are mostly not losses.** The publisher's articleBody itself carries promotions
  (`pe_diariocorreo`, `pe_el_buho`), AI notes (`co_elpais`), "Lee también" boxes (`cl_biobiochile`), captions, embedded posts and
  YouTube addresses; the extractor keeps these out by design. A standfirst on the title surface (`co_el_espectador`) is not BODY.
- **Genuine article text left out** -- five structural causes, each bounded and repaired (§2).
- **Contamination inside accepted BODYs** (patterns used to measure, not as rules): credit lines 0.006 %, teaser lines 0.001 %,
  channel promotions 0.026 % of the BODY words; recurring short lines are a digest's date lines and a league table (real text).
  No safe structural rule remains; a lexical one is excluded (CPD-0041 §4). No change.
- **Live pages**: no live ticker among the accepted pages; title and address hits are articles *about* broadcasts, a section
  named "última hora", static "dónde ver" previews and agendas. No change.
- **Text only in the stated articleBody** (19 pages): at `ar_pagina12` the stated body is often *another* article -- six result
  pages of different provinces state one identical text, a currency page states an event report; at `uy_el_pais` the full text
  of four paywalled columns stands only in the JSON-LD. A fallback to the stated body is **not** adopted (§4).
- **Interactions**: the repairs change no metadata layer and no text-reuse relation (293 of 293 kept); `body-quality/2`
  `incomplete` → `cleaned` on 2 pages, `clean` → `cleaned` on 17 (selection recorded).

### 2. `article_html/0.4.2` (revision 2 of the BODY parser; 0.4.0 and 0.4.1 unchanged)

1. **The stated articleBody read as text** for the inclusion rule (`content_quality.stated_body_text`, the measure of
   `content-features/2`), compared without the white space a tag leaves before a punctuation mark ("25 mujeres , ha") and without
   the backslash a publisher's JSON-LD leaves before a quote when it escapes twice (`uy_el_observador`, 20 pages). Comparison
   values only; no block's text changes.
2. **Text outside `<p>`** the page states as its body may be included (`unstructured_text`): an interview in bare `<div>`
   elements kept 161 of 1,078 words (`es_el_mundo`).
3. **A linked paragraph built as prose** (`linked_paragraph`): the container rule drops a block more than half of whose text is
   link text; it comes back when at least three unlinked words precede its first link, that head does not end in a colon
   ("Lea más:", "Le puede interesar:"), it ends with a sentence mark and stands between two BODY blocks in the container (or is
   the lead and passes the lead rule). Teasers, linked headline lists and edge paragraphs stay out.
4. **The lead behind the opening photo**: a caption between the lead and the BODY is passed over when the lead is sought.

Measured, 0.4.1 → 0.4.2: BODY changed on **53 pages**, **107 blocks (4,121 words) added, none removed**; every added block read:
105 article text (openings, linked paragraphs, interview answers, live entries on pages that stay rejected), 2 series notes
("Este artículo forma parte del especial …", `hn_contracorriente`, 48 words). CORE under `content-quality/4`: **4,074 → 4,075**
(the interview). No layer changed; text reuse unchanged; on the frozen control (not blind) the same counts as 0.4.1: CORE gold 16/16
random, 24/25 targeted, 0 false deletions, residue 14 blocks in the random part.

### 3. End of development

No known change with a sufficiently evidenced net benefit remains. What is left is either not safely repairable (a few words of
credits and labels inside blocks; one-line items under 12 words; leads that are absent from the markup; a standfirst written as
the first paragraph) or a scientific choice (§4). Further rules would be outlet-specific or lexical, or would trade article
text for cosmetic gains.

### 4. The open questions of CPD-0042, measured (the operator decides)

- **Structured texts.** Counting only running prose for the 150 words and the function-word share would flip 27 CORE decisions
  of 4,759: 26 out (recipes, agendas, outage lists -- but also genuine short reports just above 150 words whose short lines are not
  "prose"), 1 in (a report with a long list of candidates). Recommendation: keep the gate as it is; let the validation's page
  types show whether structured texts need a rule.
- **Word definition.** Letter words against white-space tokens: 10 flips at the threshold (146–149 against 150–160). Recommendation:
  keep letter words.
- **Stated articleBody as the BODY of script-rendered pages.** Not adopted: at `ar_pagina12` the stated text is not reliably the
  page's article; at `uy_el_pais` it would surface paywalled text the page withholds -- an access question for the institution,
  not a technical one. Recommendation: no fallback.
- Unchanged from CPD-0041/0042: a layer for embedded social posts; whether `body-quality` is shown in a release.

### 5. The reviewer and the prepared validation

`scripts/body_review.py` builds a frozen package outside the repository and serves a browser reviewer on a loopback address
(`src/coprepan/body_review.py`): the inert stored page beside the candidate blocks **without** machine roles; per block article /
foreign / unsure; missing text marked on the page; completeness; CORE with reason; page types; comment. Every answer is an event
bound to package, case, fetch, body digest, extractor and block digest; the machine labels are shown after a case is closed (a
change afterwards marks it not blind) or in a separate diagnostic mode never scored as gold. Export, validation and scoring
(five classes, random and targeted apart; case-level Wilson intervals for the random part only).

The validation package (`a24462c3c84a7691b2ab12d7`, seed 20261116) is prepared and frozen: 120 cases -- 80 random (stratified by
country, proportional allocation, exact inclusion probabilities) and 40 targeted (5 from each of 8 error-class strata) --
2,866 blocks to judge (mean 23.9 per case). It is **not reviewed**.

## Alternatives considered

- **Any paragraph of the stated articleBody whatever its links** -- the publisher states teasers too ("Le puede interesar:",
  "Lea más:" in `co_el_espectador`, `py_abc_color`); the shape of the paragraph decides, not the statement.
- **Linked paragraphs at the BODY's edge** -- the related-article teasers stand there (`ni_nicaragua_investiga` printed the same
  linked text under other articles); only the lead position, under the lead rule's own tests, is admitted.
- **Counting running prose only** and **white-space words** -- measured, not adopted (§4).
- **The stated articleBody as a fallback BODY** -- rejected on evidence (§4).
- **An LLM stage** -- no class left that a deterministic rule could not reach or that would justify one.

## Not decided here (the operator's decision)

1. Scientific acceptance and activation of `article_html/0.4.2` (with `body-templates/1`), `content-quality/4`, `body-quality/2`
   -- after the validation the package prepares.
2. Structured text types and the 150 words; the word definition; a stated-body fallback for script-rendered pages (§4).
3. Whether the prepared package (120 cases) is the validation to run, or a smaller one; who reviews.
4. Unchanged: a layer for embedded social posts; whether `body-quality` is shown in a release.
