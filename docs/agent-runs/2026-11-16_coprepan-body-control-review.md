# 2026-11-16 — CO.PRE.PAN BODY control review: the operator's verdicts, the evaluation, three bounded repairs

**Status:** `PASS` (verdicts transferred, evidence checks, controlled evaluation, bounded repairs with population checks, tests) · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-15 (Sunday) late evening to 2026-11-16 (Monday), Europe/Berlin |
| Kind | evaluation of a frozen human control + bounded repair + offline measurement on stored raw evidence (AGENTS §8). **Not** a scientific validation and **not** an activation |
| Status | `PASS` for the brief's completion criteria (§9 of the brief; §2–§13 below). It does **not** claim that any extractor, gate or status is validated or adopted: every component is a `CANDIDATE`; the candidate's scores on the control are **not blind** (§7) |
| External calls | none. No publisher request, no web page, no provider, LLM, GPU or HPC call |
| Start | `main` = `origin/main` = `52ddef8`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\body-control-review`, branch `phase3/body-control-review` |
| Operator brief | "CO.PRE.PAN_v3 – Operator-Review übernehmen, BODY-Blindkontrolle auswerten und Phase 3 entscheidungsreif abschließen" (2026-11-15) |
| Decision | [CPD-0042](../decisions/CPD-0042_body-control-evaluated-and-bounded-repairs.md) (partially supersedes CPD-0041 and CPD-0039) |
| Evidence | [filled form](../intake/quality/body_quality_control_2026-11-15/verdicts_filled_2026-11-15.csv), [control result](../intake/quality/body_quality_control_2026-11-15/result_2026-11-15.json), [repairs on every stored page](../intake/quality/body_control_repairs_2026-11-15.json) |

## 1. Start state and sources

- **Repository:** `main` = `origin/main` = `52ddef8` (the published report of the BODY quality run), clean. Four older worktrees
  of other runs (`legacy-archive-contract`, `legacy-freeze`, `newfs-phase-b`, `newfs-phase-d`) left untouched.
- **Sources read:** CPD-0039, CPD-0040, CPD-0041; the [BODY quality report](2026-11-15_coprepan-body-quality.md); the control
  directory (manifest, blank form, key — the key only after §4); `article_html/0.3.0`/`0.4.0`, `body-select/1`,
  `body-templates/1`, `body-quality/1`, `content-quality/3`; `scripts/study_body_quality.py`.
- **Integrity:** the SHA-256 of the blank form, the key and the local reading sheet equal the manifest's (checked before the
  merge and inside it; `merge` refuses a changed key, a changed blank form, a form with other questions and an unknown basis).
- **Evidence:** the 45 control pages and then all 4,759 stored 2xx item pages, read once from the local packs
  (`C:\dev\panhispanic_media_corpora\coprepan_workspace`) into a page cache under `%LOCALAPPDATA%\Temp\coprepan-body-review`
  (publisher bytes; outside the repository; deleted at the end, §11). CO.RA.PAN was not touched; CPU load about 39 % at the
  start (read only); every heavy step ran at below-normal priority, one process at a time.

## 2. The operator's verdicts, transferred

The brief's table (§3.1) went into the working copy `verdicts_filled_2026-11-15.csv` of the frozen form, one row per question
(135), with the columns `answer`, `basis`, `operator_answer` (the operator's verdict verbatim: block ranges as written, `yes`/`no`),
`operator_open` (the blocks the operator marked "prüfen") and `note` (the operator's remark, verbatim, and what the run found).

- **FOREIGN:** 42 cases as the operator gave them (`OPERATOR_CONFIRMED`); three with an open point (`B01` block 1, `B28` blocks
  4–6, `B38` block 6) — the confirmed part stays in `operator_answer`, the open blocks in `operator_open`.
- **CORE:** 41 as given; `B28` "eher nein" is entered as the operator's `no` with the hedge noted (the operator's rule for live
  coverage, §3.2, applies and the page is a live blog). Four CORE points the operator gave to the word count (`B19`, `B21`, `B29`,
  `B30`) are not gold (§3).
- **MISSING:** no operator verdict; every answer is the run's (§3).

## 3. The operator's gold apart from the run's answers

| Basis | FOREIGN | MISSING | CORE | All |
|---|---|---|---|---|
| `OPERATOR_CONFIRMED` | 42 | 0 | 41 | 83 |
| `TECHNICALLY_VERIFIED` | 1 | 43 | 2 | 46 |
| `AGENT_ASSESSED` | 2 | 2 | 2 | 6 |
| `UNRESOLVED` | 0 | 0 | 0 | 0 |

How the run answered (each case's note in the form says it):

- **MISSING (45):** every `<p>`, `<blockquote>`, heading and the JSON-LD `articleBody` of the stored page against the sheet's
  blocks (5-word shingles). A standfirst outside the blocks is title surface, not missing BODY; a machine summary panel, a
  related teaser, a caption, a footer is not article text. Found missing: the opening paragraph of `B03` (133 words, before the
  paywall container) and `B39` (37 words, bold and linked); three of six one-line items of `B02`; live-entry headings and the
  newest entries of `B28` and `B43`; the whole text of `B08` and `B27` (`ar_pagina12`: only in the JSON-LD, the form has no value
  for "all", `beginning_missing` is used and noted). `B22` (a section listing) and `B36` (an account page) are not articles.
  Agent-assessed: `B31` not an article (a photo gallery whose only text is its standfirst), `B33` complete (the live coverage
  is an embedded frame not in the stored page).
- **FOREIGN, the open points:** `B38` block 6 is an ordinary paragraph container of the body, no figure, no caption — not
  foreign (verified). `B01` block 1 is the post's first paragraph, wholly bold-italic without closing punctuation: a standfirst
  written into the body — article text, not foreign; its place on the title surface is a separate question (assessed). `B28`
  blocks 4–6 are a regular entry (16:59) of the same live blog on another match, inside the stated articleBody — text of the blog,
  not an embedded foreign item (assessed).
- **CORE by word count**, the gate's own definition (letter-only words, `content-quality/3`): `B19` 149 and `B30` 147 after the
  operator's FOREIGN (155 and 150 by white space) — `no`, borderline (verified). `B21` recipe: 125 words of method (179 with the
  ingredients) — `no` (assessed: what counts as running prose). `B29` match report: 172 words of running report beside the
  tables — `yes` (assessed).

**Every question is answered; none is open.** The form, the `merge` extension and its tests were committed and pushed
(`81749ba`) **before the key was read**.

## 4. Control results (frozen predictions of 0.3.0 and 0.4.0; random 16 and targeted 29 apart)

On the operator's gold (blocks the operator left open are left out); the all-answers counts are the same for FOREIGN and CORE
except where stated.

| | random: 0.4.0 | random: 0.3.0 | targeted: 0.4.0 | targeted: 0.3.0 |
|---|---|---|---|---|
| foreign blocks kept out (correct removals) | 45 (201 words) | 1 (91) | 539 (1,735) | 1 (2) |
| **article text kept out (false deletions)** | **0** | 1 block (38 words) | **0** | 38 blocks (1,176 words), 9 cases |
| foreign blocks kept in (residual) | 15 (219 words), 6 cases | 59 (329), 11 cases | 18 (153), 8 cases | 556 (1,886), 22 cases |
| CORE agreement, gold | 15 / 16 | 15 / 16 | 21 / 25 | 22 / 25 |
| CORE agreement, all answers | 15 / 16 | 15 / 16 | 23 / 29 | 22 / 29 |
| MISSING agreement (all answers; no gold) | 13 / 16 | — | 22 / 29 | — |

0.3.0's "false deletions" are the blocks 0.4.0 *included* (leads, stated-body paragraphs) that 0.3.0 lacked. Residual share of
the random BODY words: 0.4.0 2.2 % (219 of 9,897). No population precision or recall is derived from the targeted part.

## 5. Every deviation and its cause

- **CORE, `B20` and `B42` (`cl_biobiochile`, rejected `incomplete_against_stated_body`, gold `yes`):** the publisher states its
  articleBody as **HTML** — tags, attributes, the addresses of "Lee también" boxes, embedded posts — and `content-quality/3`
  compares its raw length (B42: 7,757 characters, 3,769 as text) with the extracted text (3,203). A measurement inconsistency,
  not missing text (§6).
- **CORE, `B28` and `B43` (live blogs accepted by 0.4.0, gold `no`):** both pages declare a schema.org `LiveBlogPosting`; the gate
  knows live pages only by address, by a title that begins with "en vivo", and by the share of BODY blocks led by a time stamp.
  0.3.0 rejected both — `B28` only as too short and incomplete, `B43` also as live (one of its three BODY blocks led by
  "Minuto 6"); 0.4.0 included their stated-body paragraphs, and `B43`'s time-stamp share fell from 1/3 to 1/11 (§6).
- **CORE, `B40` (`duplicate_of_earlier`, gold `yes`):** the same address fetched again on 2026-11-14 with the BODY of 2026-10-10;
  the earlier copy is assessed on its merits. The rule is right; the operator judged the page alone.
- **CORE, `B21`, `B29` (all answers only):** the gate counts every BODY word — the recipe's ingredient list carries it over 150;
  the match report's tables bring its function-word share to 0.289. A question of the CORE standard for structured text, not
  of the BODY (§12).
- **Residual under 0.4.0, random:** `B03` (a related-news card's title and author, two pull quotes with name and role), `B06`
  (a related title), `B10` (a rubric label), `B11` (two photo credits), `B13` (a name), `B37` (the paywall teaser included as
  the lead — **introduced by 0.4.0's lead rule**, §6 — and an author's note). Targeted: `B05`, `B16` (a summary box), `B18`
  (captions ending with a photo credit), `B22` (a date on a listing), `B32`, `B39` ("LECTURAS RELACIONADAS"), `B40` (credits),
  `B43` ("Enlace copiado"). Credit lines, labels and pull quotes the markup does not mark; a few words each.
- **MISSING:** `B03`'s opening paragraph — the lead rule gives up on an `<article>` that holds another `<article>`, and the
  "Noticia relacionada" card is one (§6); its stated-body check fails on a " ... " teaser span inside the paragraph. `B39`'s lead
  is more than half link text, and the lead rule keeps link-heavy paragraphs out (a guard against teasers; not changed). `B02`'s
  missing items are under the 12-word inclusion minimum. `B08`/`B27`: no rendered text at all. `B20`/`B42` were predicted
  `middle_missing` from the same raw-length measurement.

## 6. The repairs (new versions; the old ones unchanged)

| Version | Defect (control case) | Rule |
|---|---|---|
| `article_html/0.4.1` | a hidden paywall teaser cut off with "…" included as the lead: the BODY begins twice (`B37`, 18 `co_el_espectador` pages) | no paragraph is included whose text, a trailing ellipsis set aside, is the **beginning** of a block the BODY holds |
| `article_html/0.4.1` | a teaser card inside the article turns the lead rule off: the opening paragraph lost (`B03`, `es_abc`) | an `<article>` holding other articles is a list only when they hold at least 30 % of its text |
| `content-quality/4` (`content-features/2`) | completeness measured against an articleBody stated as HTML (`B20`, `B42`) | `stated_body_text_characters`: markup, scripts, embedded social posts out |
| `content-quality/4` | live blogs the gate does not see (`B28`, `B43`) | `live_coverage` also when the page declares a top-level `LiveBlogPosting`, unless it is static live markup (≥ 2 updates, one time) |
| `body-quality/2` | `incomplete` from the same raw-length measurement | the stated text, as `/4` |

Two first drafts were narrowed on the population before they were kept (negative examples):

- the copy rule first matched a text *anywhere inside* a BODY block — on `ec_primicias` it left out the article's own paragraph
  because an embedded police post the rules do not see quotes it word for word; only the beginning counts now;
- the live rule first took every declared `LiveBlogPosting` — two `cr_la_nacion` previews are static articles whose CMS wraps
  each paragraph as an update at one time (24 and 9 updates, one time stamp); those are excluded. The two declared live pages
  with a single update (`co_elpais`, `ec_primicias`) were read: live.

The 150-word minimum, every threshold and every reason of `/3` are unchanged; no social post returns to the BODY; no block is
split or rewritten.

## 7. False deletions and residual contamination

- **0.4.0 in the frozen control: no false deletion** — 0 of 584 removals were article text, on the gold, in both components.
- **0.4.1 on every stored page:** BODY changed on 45 pages — 21 copies out (1,160 words; each the beginning of a kept block:
  18 teasers, 3 echoes), 24 opening paragraphs in (2,297 words; `es_abc` 17, `co_el_nuevo_siglo` 5, `es_el_correo` 1,
  `pr_metro_puerto_rico` 1). Every added block was read: an opening paragraph, none from a list. Inside the ABC openings a
  " ... " teaser marker stays (in-block, reported, not rewritten).
- **The candidate on the control — not blind** (written after the key was opened; it checks the repairs, it does not validate
  them): false deletions 0; residual random 14 blocks, 128 words (1.3 % of the random BODY words), targeted 18 blocks, 153
  words; `B03`'s opening (133 words) in — a block the sheet could not show, judged against its `MISSING` label.
- **Missed openings** (the agent's heuristic, not gold; CPD-0042 §4): 33 → 14 of 2,081 pages that state an articleBody.
- **What stays visible:** the residue classes of §5 (credit and name lines, labels, pull quotes, a summary box, caption
  credits); link-heavy leads; one-line items under 12 words; live-entry headings; text rendered only by script. No LLM stage:
  the residue is a few words per page, and a rule for it would be lexical or outlet-specific.

## 8. CORE decisions

| | accepted (4,759 pages) |
|---|---|
| `content-quality/3` on 0.4.0 (the last run's 4,067, reproduced) | 4,067 |
| `/4` on 0.4.0 (the gate alone) | 4,073 |
| `/3` on 0.4.1 (the extractor alone) | 4,068 |
| **`/4` on 0.4.1 (the candidate)** | **4,074** |

From `/3` on 0.4.0 to the candidate: **19 in** — 17 `cl_biobiochile` (the BODY covers 76–96 % of the stated text; the rest is
"Lee también" boxes and captions), 2 `co_el_nuevo_siglo` (their opening paragraph back); **12 out** — 11 declared live blogs
(`es_abc` 4, `ar_la_nacion` 2, `ec_primicias` 2, `co_elpais`, `cr_la_nacion`, `uy_el_observador`; each read: live), 1
`bo_opinion` page that had 150 words only through its duplicated paragraph (151 → 123). The 14 pages still incomplete against an
articleBody with markup have a BODY that covers 0–11 % of the stated text. On the control (not blind): CORE gold 16 of 16 random,
24 of 25 targeted (the remaining one is `B40`, the duplicate).

## 9. Technical validation

- `merge` v2: three tests (counts, gold apart from the run's answers with open blocks left out, refusals).
- `tests/test_body_control_repairs.py` (16 tests, suite `foundation_contract`): the teaser copy and its counter-cases (a real
  lead, a text inside — not at the beginning of — a BODY block, a short line), the teaser card and the list of nested articles,
  the stated body as HTML with a related box and an embedded post, a plain stated body and a real stub, the declared live blog
  (top level, list, `@graph`, nested mention, static live markup, a series, a single update), `/4` refusing `content-features/1`,
  `/3` unchanged.
- Existing tests adjusted for the preferred versions only (`test_body_quality`, `test_phase3_metadata`).
- **Full suite** (in the worktree, below-normal priority): 2,158 passed, 15 skipped (the known skips), 4 failed — all four the
  decision-record format (a dated note written into the `Status` field of CPD-0039 and CPD-0041 instead of a status line under
  the table). Fixed; `tests/test_repository_contract.py` then 100 passed. The fix touched those two Markdown files only, which
  no other test reads; the full suite was not run a second time.
- Population: `scripts/study_body_quality.py repair` on all 4,759 pages (numbers, outlets and fetch prefixes in the evidence
  file; the texts in a local review file only); text reuse 293 relations before and after; no metadata layer changed; 11.4 ms
  per page for 0.4.1.

## 10. Versions

| Kind | Before (preferred) | Now (preferred) | Unchanged beside it |
|---|---|---|---|
| extractor | `article_html/0.4.0` | `article_html/0.4.1` | 0.1.0–0.4.0, `extraction/3`, `body-templates/1` |
| features | `content-features/1` | `content-features/2` (adds two) | `/1`'s fields |
| CORE gate | `content-quality/3` | `content-quality/4` | `/1`–`/3` |
| contamination status | `body-quality/1` | `body-quality/2` | `/1` |
| metadata, text reuse | `editorial-metadata/3`, `text-reuse/2` | same | — |
| control result | — | `coprepan-body-quality-result/v2`, `coprepan-body-control-repairs/v1` | the frozen manifest, form, key, sheet |

## 11. Git and closure

- Commits on `phase3/body-control-review`, explicit pathspecs: `81749ba` (the filled form and `merge`, before the key); the
  repairs and their tests; CPD-0042, the evidence and the documents; this report.
- Full suite in the worktree before the merge; `main` fast-forwarded and pushed with the branch; this report published on `main`
  with `scripts/publish_run_report.py publish … --status PASS`; the worktree removed last with `scripts/worktree_closure.py
  remove` (never `--force`). The outcomes of the last steps are stated in the operator report.
- Local scratch deleted: the page cache and the review lists under `%LOCALAPPDATA%\Temp\coprepan-body-review`. Kept: the
  operator's reading sheet under `%LOCALAPPDATA%\Temp\coprepan-body-control-sheet\` (publisher text). Nothing in the repository
  was moved, deleted or overwritten; the four older worktrees and every other branch are untouched.

## 12. Scientific decisions still needed (the operator's)

1. **Acceptance** of `article_html/0.4.1` (with `body-templates/1`), `content-quality/4` and `body-quality/2` (§13).
2. **Structured text and the 150 words:** the gate counts every BODY word; a recipe is accepted on its ingredient list (`B21`),
   a match report with tables is rejected on its function-word share (`B29`). Count running prose only — a new rule set — or
   keep the rule and accept both outcomes?
3. **The word at the threshold:** letter-only words (the gate) or white-space tokens (`B19` 149 / 155, `B30` 147 / 150)?
4. **Script-rendered pages:** may a stated `articleBody` serve as the BODY when the page renders no text (`ar_pagina12`)? It is
   the publisher's own text but not the page's markup.
5. Unchanged from CPD-0041: a layer for embedded social posts; whether `body-quality` is shown in a release. To confirm in
   passing: `B28` blocks 4–6 (an entry on another match) as text of the live blog.

## 13. Recommendation

**Release `article_html/0.4.1` with `body-templates/1` as the BODY extractor and `content-quality/4` as the CORE gate**, with
`body-quality/2` as the status. In the frozen control 0.4.0 deleted no article text and left 2.2 % foreign words in the random
part; 0.4.1 changes 45 pages, only by leaving out copies and taking back opening paragraphs; `/4` corrects two measurements, and
every one of its 31 changed decisions was read. Accepting it does not require the open questions 2–4 first: they concern a small
class of pages and can follow as a later rule set. A fresh blind sample is not required for the repairs (they are enumerated and
read), but it is the only way to put a number on the candidate itself.
