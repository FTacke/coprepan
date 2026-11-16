# 2026-11-16 — CO.PRE.PAN final BODY/CORE pass and a local HTML reviewer

**Status:** `PASS` (error classes examined on every stored page, bounded improvement with population and control checks, the end of
development judged, reviewer built and tested on stored material, validation package prepared, tests) · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-16 (Monday), Europe/Berlin |
| Kind | development + offline measurement on stored raw evidence + tooling (AGENTS §8). **Not** a scientific validation and **not** an activation |
| Status | `PASS` for the brief's completion criteria (§1–§11 below). It does **not** claim that any extractor, gate or status is validated or adopted: every component is a `CANDIDATE`; the candidate's counts on the frozen control are **not blind**; the validation package is prepared, **not reviewed**; no gold judgment was made |
| External calls | none. No publisher request, no web page, no provider, LLM, GPU or HPC call. The reviewer was exercised over a literal loopback address only |
| Start | `main` = `origin/main` = `d3b35cf`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\body-final-reviewer`, branch `phase3/body-final-reviewer` |
| Operator brief | "CO.PRE.PAN_v3 – Finaler BODY-/CORE-Qualitätsabschluss und HTML-Reviewer" (2026-11-16) |
| Decision | [CPD-0043](../decisions/CPD-0043_final-body-candidate-and-local-reviewer.md) (partially supersedes CPD-0042) |
| Evidence | [0.4.1 → 0.4.2 on every stored page and on the frozen control](../intake/quality/body_final_candidate_2026-11-16.json), [the final study](../intake/quality/body_final_study_2026-11-16.json), [the validation package's manifest and instructions](../intake/quality/body_final_review_2026-11-16/README.md) |

## 1. Start state, commit and the decisions in force

- **Repository:** `main` = `origin/main` = `d3b35cf` (the published report of the BODY control review), clean; no newer
  commit, decision or change since CPD-0042. Four older worktrees of other runs (`legacy-archive-contract`, `legacy-freeze`,
  `newfs-phase-b`, `newfs-phase-d`) left untouched.
- **In force:** CPD-0038–CPD-0042 (read); preferred candidates at the start `article_html/0.4.1` + `body-templates/1`,
  `content-features/2` / `content-quality/4`, `body-quality/2`; four questions open (CPD-0042 *Not decided here*).
- **Evidence:** all 4,759 stored 2xx item pages, read once from the local packs (`C:\dev\panhispanic_media_corpora\coprepan_workspace`)
  into a page cache under `%LOCALAPPDATA%\Temp\coprepan-final` (publisher bytes, outside the repository, deleted at the end, §11).
  CO.RA.PAN, the reference repositories and the joint contracts were not touched; every heavy step ran at below-normal priority,
  one process at a time.
- **CO.RA.PAN review tools (read only):** its loopback review servers (`portable/review_html_v1`), per-review apps with an
  append-only `events.jsonl`, the reading audit with validated import and a self-test, and sealed-key text sheets. Taken over as
  concepts: loopback binding with a Host check, `textContent`-only rendering, append-only events with an atomic latest file and a
  torn-last-line rule, a manifest with every file's digest verified before any answer, a sealed key, single-key answers.
  Not taken over: audio playback, speaker semantics, the sync-share hub.

## 2. Error classes examined and the evidence that decided

The stated articleBody was read against the BODY on the 2,092 pages that state at least 1,000 text characters (5-word shingles of
letter words; beginning = first 30, end = last 30), every gap traced to the record's blocks and read on the page.

| Class | What the stored pages show | Outcome |
|---|---|---|
| BODY misses stated text | under 0.4.1: coverage < 0.5 on 22 pages, 0.5–0.8 on 90. Most gaps are the publisher's own promotions in the articleBody (`pe_diariocorreo`, `pe_el_buho`), AI notes (`co_elpais`), "Lee también" boxes (`cl_biobiochile`), captions, embedded posts, YouTube addresses -- kept out by design | not a loss |
| genuine paragraphs left out | (a) a body stated as **HTML** never matched a block (`pa_la_prensa`, `es_abc`: "25 mujeres , ha"); (b) a publisher's JSON-LD escaping quotes twice (`uy_el_observador`, 20 pages); (c) an **interview** in bare `<div>`s (`es_el_mundo`, 161 of 1,078 words); (d) paragraphs whose **phrase links a source** dropped by the link-share guard (`pa_la_prensa`, `ec_primicias`, `uy_ladiaria`, …); (e) the **lead behind the opening caption** (`es_el_correo`, 158 words) | repaired (§3) |
| linked-share guard | 1,420 linked paragraphs in containers on 726 pages: teasers ("Lea más:", "Le puede interesar:", headline lists) and genuine prose; the publisher's articleBody states teasers too, so it cannot separate them; the shape does (unlinked words before the first link, no label colon, sentence end, between BODY blocks) | shape rule (§3) |
| openings still missing | under 0.4.2: 18 pages with a beginning gap, 10 of them a standfirst on the title surface (`co_el_espectador`), the rest absent from the markup (`pr_el_nuevo_dia`) or a title-surface paragraph | not repairable safely |
| text only in the stated body | 19 pages; at `ar_pagina12` six result pages of different provinces state **one identical** article and a currency page an event report -- the stated body is not the page's text; at `uy_el_pais` four paywalled columns | no fallback (§10) |
| residue in accepted BODYs | credit lines 0.006 %, teaser lines 0.001 %, channel promotions 0.026 % of 2.41 M BODY words; recurring short lines are a digest's dates and a league table | no rule (lexical) |
| live pages | no live ticker among accepted pages; hits are articles about broadcasts, a "última hora" section, static "dónde ver" previews, agendas | no change |
| structured texts / word definition | measured as variants (§10) | the operator's |
| interactions | no metadata layer, no text-reuse relation changed; `body-quality/2` 19 transitions (selection recorded) | none harmful |

## 3. Improvements and versions

**`article_html/0.4.2`** (`extraction/3`, `CANDIDATE`, `PREFERRED`; BODY parser revision 2; 0.4.0 = revision 0 and 0.4.1 = revision 1
unchanged):

1. the stated articleBody read **as text** for the inclusion (`content_quality.stated_body_text`, the measure `content-features/2`
   already used), compared without white space before closing / after opening punctuation and without a backslash before a quote
   -- comparison values only, no text changed;
2. `unstructured_text` includable when the page states it (`stated_article_body`);
3. **`linked_paragraph`**: a paragraph dropped for its link share comes back when ≥ 3 unlinked words precede its first link, that
   head does not end in a colon, it ends with a sentence mark, and it stands between two BODY blocks in the container (or is the
   lead and passes the lead rule's tests);
4. the lead sought past a caption.

New selection reason `linked_paragraph` (`extraction.SELECTION_INCLUDING`); `content_quality.stated_body_text` factored out
(`stated_body_text_characters` measures identically, tested). `content-quality/4`, `content-features/2`, `body-quality/2`,
`body-templates/1` unchanged.

## 4. Measured effect and regressions (4,759 stored pages)

| | 0.4.1 | 0.4.2 |
|---|---|---|
| BODY changed | — | 53 pages (`uy_el_observador` 13, `ec_primicias` 9, `ni_nicaragua_investiga` 6, `co_semana` 3, …) |
| blocks added / removed | — | 107 (4,121 words) / 0 |
| by reason | — | `stated_article_body` 72 (32 paragraphs, 40 loose text), `linked_paragraph` 28, `lead_paragraph` 7 |
| read | — | all 107: 105 article text, 2 series notes (`hn_contracorriente`, 48 words) |
| CORE accepted (`content-quality/4`) | 4,074 | **4,075** (the interview `es_el_mundo`, 161 → 1,078 words) |
| metadata layers changed | — | 0 pages |
| text reuse | 293 | 293 (all kept) |
| `body-quality/2` | — | `clean`→`cleaned` 17, `incomplete`→`cleaned` 2 |
| frozen control (not blind) | CORE gold 16/16, 24/25; false deletions 0; residue random 14 blocks | identical |

Coverage of the stated text (2,092 pages): < 0.5 on 22 → 20 pages, 0.5–0.8 on 90 → 77. Tests: 11 new for 0.4.2, every rule with
its counter-example (a "Lea más:" teaser, a linked headline, a linked edge paragraph, unstated text stay out).

## 5. Optimisations rejected

- **Any stated paragraph whatever its links** -- the publisher states teasers ("Le puede interesar:", "Lea más:"); shape decides.
- **Linked paragraphs at the BODY's edge** -- related-article teasers stand there; only the lead under the lead rule.
- **A stated-body fallback** for script-rendered pages -- wrong article at `ar_pagina12`, paywalled text at `uy_el_pais`.
- **Prose-only counting** and **white-space words** -- measured (§10), not adopted: scientific choices with small effect.
- **Lexical residue rules** ("Foto:", "Síguenos", "¡Copiado!") -- 0.03 % of the words at most, against the no-lexical-deletion
  rule; reported instead.
- **An LLM stage** -- no class left that would need one.

## 6. Development judged complete

Further changes have no sufficiently evidenced net benefit. Still improvable in principle, and why not now: a few words of
credits and labels inside blocks (lexical or outlet-specific rules; endanger real text); one-line items under 12 words (a lower
inclusion threshold admits labels); leads absent from the markup (no source text); a standfirst written as the first body
paragraph (a title-surface rule of 0.3.0; changing it moves CORE word counts on many pages for little gain); the two series
notes 0.4.2 admits (a rule for them would be lexical). The remaining questions are scientific (§10), not technical. **No further
development is recommended before the validation.**

## 7. The HTML reviewer — scope and technical validation

`src/coprepan/body_review.py`, the client `src/coprepan/body_review_app/` (HTML, CSS, JS; no framework, no external resource),
`scripts/body_review.py` (`prepare`, `serve`, `export`, `validate`, `score`).

- **Blind case:** outlet, country, address (as text), dates, title surface, the candidate blocks in page order (BODY, every block
  the selection decided, the text between, three text blocks either side) **without** roles; the full page text; the inert page.
- **Per case:** block labels article / foreign / unsure (click or `1`/`2`/`3`, `J`/`K`, `A` for all open); missing text marked on
  the page or the page text (`M`, with the part); completeness (complete / beginning / middle / end missing / not assessable);
  CORE yes / no / unsure with reason (required for no and unsure); page types (15, several, optional, plus free text); comment;
  `F` closes when nothing is open. Progress bar, case list with state, previous / next / next open, help.
- **Integrity:** the machine labels (roles, reasons, CORE decision, BODY status, why the case was drawn) come from the sealed key
  and are served only after the case is closed (HTTP 403 before) or in `--diagnostic` mode; a case changed after its labels were
  shown is `revised_after_reveal` and not blind; diagnostic answers are never scored as gold. Every event carries package, case,
  fetch, body digest, extractor, and for a block its index and text digest; the server checks them against the case.
- **Persistence:** `judgments/events.jsonl` appended and synced per answer; `latest.json` written atomically; state replayed from
  the log on start (resume); an interrupted last line is left out and reported. Export `coprepan-body-review-judgments/v1`,
  validated against the package (identities, block digests, vocabularies); `score` (`coprepan-body-review-result/v1`) reads the
  frozen key and separates false deletion, residue, missing text (completeness and marks in / outside the machine BODY), CORE
  false accept / false reject, and doubt; random and targeted apart; case-level Wilson intervals for the random part only.
- **Safety:** the stored page is made inert (every script, frame, object, embed, form control, media element dropped; every
  attribute but class / id / style without `url()` / lang / dir / spans dropped -- no link target, image source, handler or
  address survives), served with `default-src 'none'` and shown in a frame sandboxed without scripts; the app runs under a strict
  CSP (`script-src 'self'`); the server binds 127.0.0.1 or ::1 only, checks Host and Origin, limits request size; a package
  directory inside the repository is refused; every package file is verified against the manifest before anything is served.
- **Tests:** `tests/test_body_review.py`, 10 tests: a hostile page (meta refresh, base, scripts, handlers, iframes incl. self-closed,
  svg, forms, object/embed, noscript, `url()` styles) comes out inert with its text; a package written once, outside the
  repository, a changed file refused; no machine field in a case; a stratified, seeded, shuffled draw; event checks; replay after
  a restart and a torn last line; not-blind marking; export validation and the five scoring classes; the server's gate, export
  and closed-case refusal; Host / Origin / loopback refusals.
- **On stored material:** a technical test package of 14 real pages (6 random, 8 targeted) built, served and driven over HTTP:
  blind case without machine fields, source with 0 script tags and the source CSP, machine labels 403 before and 200 after
  closing, export written; rendered in headless Chrome (blind view, and after closing with the machine roles and the
  differences marked); resumed after a server restart. Placeholder answers only; that package was deleted (§11).
- **Not exercised automatically:** the client's key handling and text selection in a real browser session (the server side of
  both is tested); the operator's first session is the check.
- **Full suite:** `python -m pytest tests` -- **2,185 passed, 15 skipped** (the known skips of applied waves and rebuilt
  inventories), 796 s; no tracked file modified by the run. The focused files (extraction, quality, metadata, repository
  contract) 324 passed before.

## 8. How to start and run the review

See the [package README](../intake/quality/body_final_review_2026-11-16/README.md). In short:
`python scripts/body_review.py serve --package "%LOCALAPPDATA%\Temp\coprepan-body-final-review\package"` opens
`http://127.0.0.1:8765/`; judge case by case; `F` closes a case; stop and resume any time; afterwards `export` and `score`.

## 9. The proposed final validation and its effort

- **Package `a24462c3c84a7691b2ab12d7`** (seed 20261116), prepared and frozen, **not reviewed**: 80 random cases (stratified by
  20 countries, proportional allocation, exact inclusion probabilities; rates with intervals) + 40 targeted (5 from each of
  8 error-class strata: changed by 0.4.2, CORE changed since CPD-0041, live or preview, 120–180 words, list or table structure,
  stated-body shortfall, `residual_suspect`, rejected for another reason than length; counts only).
- **Effort:** 2,866 blocks (random 1,908, targeted 958; mean 23.9 per case, median 19 random) -- *measured*. Time per case *not
  measured*; *scenario assumption* 2–5 minutes → 4–10 hours in several sittings. The 80 random cases alone give the population
  estimates.
- Expected precision (*arithmetic, not a result*): with 80 random cases a case-level share of 0 has a Wilson 95 % upper bound of
  about 4.6 %; 2 of 80 an interval of about 0.7–8.7 %.

## 10. Open scientific decisions, evidence gaps, blockers

1. **Acceptance** of `article_html/0.4.2` (with `body-templates/1`), `content-quality/4`, `body-quality/2` -- after the validation.
2. **Structured texts and the 150 words:** prose-only counting would flip 27 CORE decisions (26 out -- recipes, agendas, outage
   lists, but also genuine short reports just over 150 words; 1 in -- a report with a long candidate list). Recommendation: keep;
   let the validation's page types show whether a rule is needed.
3. **Word definition:** letter words vs white-space tokens flip 10 pages at the threshold. Recommendation: keep letter words.
4. **Stated-body fallback:** not recommended (§2); the paywalled case is an access question for the institution.
5. Unchanged: a layer for embedded social posts; whether `body-quality` is shown in a release; who reviews.
- **Evidence gaps:** no blind measurement of 0.4.2 yet (the control counts are not blind); the time per case is unknown.
- **Blockers:** none for the validation.

## 11. Git, commits, push, worktree

- **Committed** on `phase3/body-final-reviewer`: the extractor (0.4.2, `compare`, tests), the reviewer (library, client, script,
  tests), CPD-0043 with its evidence and the documentation, this report -- explicit pathspecs.
- **Merged** into `main` (fast-forward; `main` had not moved since `d3b35cf`) and **pushed**: `main` and the branch.
- **Report published** on `main` with `scripts/publish_run_report.py`.
- **Worktree** removed last with `scripts/worktree_closure.py remove`; the branch is kept.
- **Tree classification:** every change committed; nothing left in the repository. Outside it: the page cache and scratch files
  under `%LOCALAPPDATA%\Temp\coprepan-final` and the technical test package -- **deleted**; the **validation package** under
  `%LOCALAPPDATA%\Temp\coprepan-body-final-review\package` -- **kept on purpose** (publisher text, local only; its manifest is in
  the repository). The earlier reading sheet `%LOCALAPPDATA%\Temp\coprepan-body-control-sheet\` is untouched.
- Untouched: CO.RA.PAN, the reference repositories, the joint contracts, the frozen controls, the four other worktrees.
