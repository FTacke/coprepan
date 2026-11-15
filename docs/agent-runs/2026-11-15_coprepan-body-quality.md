# 2026-11-15 — CO.PRE.PAN BODY quality: selection block by block, a contamination status, and no LLM stage

**Status:** `PASS` (technical implementation, offline evaluation on the stored pages, preparation of the independent control) · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-15 (Sunday), Europe/Berlin, from about 20:30 |
| Kind | implementation + offline measurement on stored raw evidence + preparation of a human control (AGENTS §8). **Not** a validation and **not** an activation |
| Status | `PASS` for the brief's technical completion criteria (§14 of the brief; §2–§13 below). It does **not** claim that the extractor, the contamination status or any layer is validated or adopted: every component is a `CANDIDATE` / `NOT_VALIDATED`; the BODY control is prepared and frozen, not answered |
| External calls | none. No publisher request, no web page, no provider, LLM, GPU or HPC call |
| Start | `main` = `origin/main` = `dd183e9`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\body-quality`, branch `phase3/body-quality` |
| Operator brief | "CO.PRE.PAN_v3 – Autonome BODY-Qualitätsoptimierung: Extraktion, Kontaminationskontrolle und selektive LLM-Eskalation" (2026-11-15) |
| Decision | [CPD-0041](../decisions/CPD-0041_body-selection-contamination-status-and-no-llm-stage.md) (partially supersedes CPD-0040) |
| Evidence | [study record](../intake/quality/body_quality_study_2026-11-15.json), [template table](../../config/extraction/body-templates_1.json) (digests only), [BODY control](../intake/quality/body_quality_control_2026-11-15/README.md) |

## 1. Start state and scope

- **Repository:** `main` = `origin/main` = `dd183e9` (the published report of the phase-3 repair), clean. Four older worktrees of
  other runs (`legacy-archive-contract`, `legacy-freeze`, `newfs-phase-b`, `newfs-phase-d`) left untouched.
- **CO.RA.PAN production was running** (scheduler, preservation sidecar, reservoir drive and six controller workers, about twenty
  KISSKI supervisor ticks; CPU about 17 % at the start). Read only through the process list; nothing stopped, changed or started.
  Every heavy step of this run ran at below-normal priority, one process at a time.
- **Monday's programme** (backup, preservation, `/2` canary) not touched; no pinned baseline read for writing.
- **Evidence:** the 4,759 stored 2xx item pages, read once from the local packs into a page cache under
  `%LOCALAPPDATA%\Temp\coprepan-body` (outside the repository and every shared root; deleted at the end, §15). The local reading
  sheet of the phase-3 blind control was present and was read for case C32. The phase-3 key, manifest and form were read, never
  written.
- **Scope done:** every point of the brief — diagnosis of the named cases and of the whole population, deterministic repair in
  iterations, a contamination status, the LLM question, the old/new comparison, a new frozen control, documentation, Git.

## 2. Systematic error classification (measured on 0.3.0, 4,759 pages; diagnosis is the agent's, not gold)

| Class | Measured under 0.3.0 | Cause | Fate under 0.4.0 |
|---|---|---|---|
| An author filter as the article (C05, C54) | 30 pages whose container lies in a form control (`gt_prensa_libre` 20, `pr_el_nuevo_dia` 9, `uy_ladiaria` 1) | hundreds of `<option>` names out-score the paywalled article in the density rule | form-control text never scored or BODY: container changed on 23 pages, the article found |
| Lead outside the body component (C01) | 1,197 pages with paragraphs of the container's `<article>` outside the BODY — mixed: leads, newsletter promotions, captions, author biographies | the density rule keeps one component; the first paragraph stands in the article element itself | adjacent lead only (146 pages); paragraphs the page states as its `articleBody` (437 blocks, 165 pages) |
| Recurring outlet furniture in the BODY (C24, C28, C31, C49, C51, C53) | 1,952 pages; 353 block texts that one outlet prints under at least 3 different bodies | labels, promotions, controls and notes inside the article container | marked modules by markup; the rest by the template table (2,815 blocks, 1,092 pages) |
| Marked page modules (C14, C18, C24, C28, C30) | — | ad labels, share bars, related lists, tags, bylines, captions, dates, tweets, players inside the container | `module_*` (table in §6) |
| A label heading ending the BODY (C32) | 342 pages ("VER MÁS", "Temas relacionados", "VIDEO RECOMENDADO") | module titles after the last paragraph | `trailing_heading` (≤ 4 words) |
| Repeated blocks | 126 pages with a block of ≥ 20 characters twice — mixed: captions, tweet credits, pull quotes, live-blog summaries | layout copies and embeds | captions and embeds by markup; `duplicate_block` for verbatim repeats of ≥ 12 words (29 blocks) |
| Production notes in the BODY (C62, C66, C69, C70) | — | AI and agency notes printed as paragraphs | `provenance_ai_note`, `provenance_agency_note` (they stay in the provenance layers) |
| Blocks without letters | 205 pages (ad-slot placeholders of zero-width characters) | empty slots in the container | `no_text` |
| Foreign material *inside* a block (C04) | — | an image address glued to a caption, a tweet glued to a paragraph, a credit at a paragraph's tail | **not removed** (no block is split or rewritten); reported by `body-quality/1` |
| Text absent at the source (C33, C39, C42, C48, C55) | — | JS-rendered pages, paywall stubs, listing pages | not repairable without the text; `not_article` / `incomplete` / gate rejection |
| C32 "paragraphs repeat" | **not an extraction error**: the BODY had no duplicate; the reading sheet showed the subtitle window (which lists the first paragraphs) and the BODY one under the other | — | — |

What the simple heuristics cannot do reliably (brief §4.8): split a block with foreign material inside it; tell an unmarked,
non-recurring label from a genuine short line; tell a repeated data list or an infographic's labels from furniture.

## 3. Deterministic approaches tried (each run over the whole population and inspected)

| Approach | Outcome |
|---|---|
| Form controls out of scoring and BODY | kept: the article replaces the author filter on the `gt_prensa_libre` pages |
| Every paragraph of the container's `<article>` element into the BODY | **dropped**: on pages with a stated articleBody, 114 of 315 checkable inclusions were not in it (captions at `ec_primicias`, author biographies at `co_elpais`, summaries at `bo_opinion`); replaced by the adjacent lead and the stated-body rule. Final measure: 54 of 84 leads on pages with a stated articleBody are in it (the check counts pages whose stated body is partial too); restricted to pages whose stated body covers most of the BODY, an earlier iteration found 53 of 57, and the 4 others read were article leads |
| Hiding module-marked text from the container scoring | **dropped**: the container moved away from the article on 253 pages (a "cuerpo ad" class around the article at `cl_cooperativa`, `cl_biobiochile`, `cu_trabajadores`); 133 pages newly rejected |
| Module marks on the block or below the container, with a 30 % size guard | kept |
| "teaser" as a related-module mark | **dropped**: removed `cl_la_tercera`'s visible lead (`article-body__teaser--locked`) |
| Byline marks anywhere | **narrowed to the BODY's edges**: inside, "author" elements held interviewees' profile lines (`es_el_mundo`) and a pull quote |
| Templates from 3 unrelated articles | **raised to 5**: at 3–4 the table removed recipe headings ("Ingredientes", "Preparación"), a poll's technical sheet (`es_el_correo`), score lines; those are now recurring-but-kept and reported |
| One story counted once (Jaccard of the other shingles > 0.2) | kept: live-ticker lines of one page fetched three times are not templates |
| Trailing headings of any length | **narrowed to ≤ 4 words**: sentence headings lead into an embed ("Vea la entrevista completa …:") |
| Provenance notes in every `ai-disclosure/1` form | **narrowed to the text forms**: the image-credit form removed a running paragraph ending "… Foto: Imagen creada con IA" (`mx_el_universal`) |
| Repeated labels including digits and colons | **narrowed to letter-only labels**: player ratings ("6", "7") and data fields ("Fase: Primer Hexagonal") repeat in real lists |
| Boilerplate check for text reuse | per-outlet furniture inside shared text (§9) |

## 4. Why this solution

It removes what the page itself marks or repeats as furniture, and it adds only what the page states as its article or what
stands directly before it in the article element. Every rule is structural (markup, position, repetition, the page's own
statements) or a closed form already tested in the provenance layers; there is no outlet rule and no lexical deletion list.
Every decision is on the block, so nothing is lost: the BODY before the selection, the removed text and the rule are in the
record. Where precision and coverage conflicted, the measurement decided for precision (§3).

## 5. Implementation and new versions

| Component | Version | Lifecycle | Relation to the earlier |
|---|---|---|---|
| record schema | `extraction/3` = `/2` + block field `selection` (`rule`, `decision` `excluded` · `included`, closed reasons) | — | `/1`, `/2` unchanged; `record_problems` checks the field |
| extractor | `article_html/0.4.0` (`extraction_body.py`, `PREFERRED`) | `CANDIDATE` | `0.1.0`–`0.3.0` unchanged (`extraction_article.py` unchanged but for one comment) |
| selection rules | `body-select/1`; template table `body-templates/1` (`config/extraction/body-templates_1.json`, 102 digests, sha256 `826c23d3…33eed4`) | — | new |
| contamination status | `body-quality/1` (`body_quality.py`) | `NOT_VALIDATED` | new |
| agency layer | `agency-credit/3`; envelope `editorial-metadata/3` (`PREFERRED`) | `NOT_VALIDATED` | `/1`, `/2` unchanged |
| unchanged | title/subtitle surface of 0.3.0, `content-quality/3`, `section-map/1`, IPTC extracts, scope, genre, `ai-disclosure/1`, `text-reuse/2`, joint contracts | — | — |

Code: `src/coprepan/extraction.py`, `extraction_body.py` (new), `body_quality.py` (new), `provenance.py`, `enrichment.py`;
`config/extraction/body-templates_1.json`; `scripts/study_body_quality.py` (templates, derive, summarize, show, draw, merge);
`tests/test_body_quality.py` (28 tests, suite `foundation_contract`).

## 6. Old against new (4,759 stored 2xx item pages, offline, 2026-11-15)

- BODY changed on **2,286** pages, identical on 2,473; container changed on 23; no title changed; 18 subtitle sets changed
  (all `gt_prensa_libre`, where the article now replaces the author filter); no schema problem; the BODY before the selection,
  read back from every record, equals 0.3.0's BODY on all pages but the 23.
- Words: 2,553,275 → 2,527,879.

| Selection | Blocks | Pages | Words |
|---|---|---|---|
| excluded: `outlet_template` | 2,815 | 1,092 | 11,244 |
| excluded: `module_social_embed` | 765 | 269 | 14,465 |
| excluded: `module_advertising` | 759 | 238 | 884 |
| excluded: `module_related` | 695 | 276 | 2,062 |
| excluded: `module_tags` | 630 | 374 | 1,861 |
| excluded: `module_byline` | 603 | 362 | 3,719 |
| excluded: `module_share` | 477 | 146 | 1,492 |
| excluded: `form_control` | 405 | 214 | 1,058 |
| excluded: `repeated_label` | 383 | 48 | 604 |
| excluded: `module_media_controls` | 305 | 66 | 1,484 |
| excluded: `trailing_heading` | 264 | 238 | 560 |
| excluded: `module_newsletter` | 211 | 106 | 1,981 |
| excluded: `module_channel_promo` | 182 | 92 | 1,914 |
| excluded: `module_caption` | 133 | 43 | 1,632 |
| excluded: `no_text` | 111 | 61 | 116 |
| excluded: `module_date` | 95 | 9 | 142 |
| excluded: `module_page_controls` | 89 | 85 | 175 |
| excluded: `provenance_ai_note` | 35 | 35 | 794 |
| excluded: `duplicate_block` | 29 | 15 | 1,118 |
| excluded: `provenance_agency_note` | 15 | 15 | 67 |
| excluded: `module_breadcrumb` | 1 | 1 | 9 |
| **included**: `stated_article_body` | 437 | 165 | 18,932 |
| **included**: `lead_paragraph` | 146 | 146 | 9,467 |

- `body-quality/1`: `clean` 2,255, `cleaned` 1,986, `residual_suspect` 332, `incomplete` 27, `not_article` 159. Against CORE:
  `cleaned|ACCEPT` 1,851, `clean|ACCEPT` 1,921, `residual_suspect|ACCEPT` 295, every `not_article` and `incomplete` rejected.
- Every other layer has the same value and state on every page: `section-iptc/1`, `editorial-scope/1`, `genre-placement/1`,
  `genre-declared/1`, `ai-disclosure/1`, `agency-credit/2` (0.3.0) → `/3` (0.4.0).
- Cost per page: extraction 12.78 ms (0.4.0) against 11.58 ms (0.3.0), `body-quality/1` 2.12 ms (§10).

## 7. Rescued articles and corrected contaminations (named cases from the phase-3 control; verbatim from the stored pages)

| Case | Outlet | 0.3.0 → 0.4.0 |
|---|---|---|
| C01 | `cr_la_nacion` | 298 → 352 words: the lead "Hace 50 años, por disposición del Ministerio de Seguridad Pública …" back (`lead_paragraph`). The closing "Curiosidad del día" section stands in the same body component and stays (structurally part of the column) |
| C05, C54 | `gt_prensa_libre` | 523 words of an author filter → the match reports (297 / 177 / 152 words); the false "exact" relations between them gone (12 + 3 + 8) |
| C49 | `pr_el_nuevo_dia` | the submission note ("Las columnas deben enviarse a …") removed as a template; the visible opening of each column comes in from the stated articleBody; their false relation gone |
| C24 | `ar_infobae` | "Escuchar", "Puntos clave", "Resumen", "Guardar", five "PUBLICIDAD", "Compartir nota:", "Temas Relacionados" out; 634 words of article |
| C28, C31 | `ec_el_universo`, `pa_critica` | related lists, relative dates, "Publicidad", the Google promotion out |
| C14 | `pr_el_nuevo_dia` | "RELACIONADAS" and the teaser bylines out |
| C30 | `pe_diario_uno` | the breadcrumb "Home POLÍTICA …" out |
| C53 | `pa_midiario` | the audio button and the embedded tweets out |
| C62, C69 | `co_elpais`, `ar_la_nacion` | the AI production note out of the BODY (still read by `ai-disclosure/1`) |
| C66, C70 | `ni_despacho_505`, `ve_efecto_cocuyo` | "Con información de EFE" out of the BODY (still read by `agency-credit/3`) |
| C04 | `do_diario_libre` | tags and the author biography out; the image addresses glued to the victims' names stay inside their blocks → `residual_suspect` |
| C33, C39, C42, C48, C55 | various | text absent at the source (paywall footer only, JS page, listing, stubs) → still rejected; `not_article` or short |
| C64 | `hn_hondudiario` | the PR-like company note unchanged and accepted (style is no exclusion) |

27 pages are newly accepted by CORE: 11 `gt_prensa_libre` pages (the article instead of the author filter), the rest with a lead
or stated-body paragraph recovered or a repetitive furniture block removed (`co_semana`, `gt_publinews`).

## 8. False-deletion risks and remaining errors

- **Against the publisher's own articleBody** (where stated; evidence, not gold): no excluded block of the reasons `module_byline`,
  `module_caption`, `module_date`, `module_related`, `module_share`, `module_tags`, `module_advertising`, `module_newsletter`,
  `module_channel_promo`, `module_media_controls`, `module_page_controls`, `form_control`, `no_text`, `repeated_label`,
  `duplicate_block`, `trailing_heading` stands in it. In it: 33 `outlet_template` blocks (promotions the publisher writes into
  its articleBody: `pe_el_buho`, `pe_diariocorreo`), 9 embedded tweets (`cl_biobiochile`), 15 AI and 2 agency notes — removed on
  purpose.
- **Judgement calls, open to the control:** embedded social posts are not the article's text (also the outlet's own posts at
  `pa_la_prensa`); a verbatim live-blog summary repeated later on the page loses its second copy (`cr_la_nacion`); a pull quote
  can be kept in place of its original paragraph's position; 4 `cl_biobiochile` pages become `incomplete_against_stated_body`
  because the stated body counts the tweets (CPD-0041 *Not decided here* 2).
- **Remaining contamination:** 332 pages `residual_suspect` (signals: recurring-but-kept text 296, label-like blocks 127,
  addresses or paths 94, credit openings 36). The agent's reading of 24 of them: about half carry real residue (teaser kickers
  with dates, channel promotions below the template threshold, image addresses inside blocks), nearly always a few words; the
  other half are genuine structure (sub-headings set as paragraphs, line-ups, infographic numbers, book data) — the signal is an
  indicator, not a verdict.
- **Not reachable without the text:** 159 `not_article`, 27 `incomplete`.

## 9. CORE decisions and text reuse

- `content-quality/3` unchanged, applied to the new BODY: 4,066 → 4,067 accepted. 26 newly rejected — 21 below 150 words once the
  furniture is gone (the removed blocks of 9 read: embeds, promotions, labels, dates, biographies, nothing of the article), 4
  `incomplete` (`cl_biobiochile`), 1 live page; 27 newly accepted (§7). The 4,066 was not a target.
- **Text reuse** (`text-reuse/2` on both BODY versions): 547 → 293 relations. Lost: 287 within-outlet `exact` pairs, every one
  of page furniture — `gt_prensa_libre` 190 (the author filter), `co_el_espectador` 78 (the paywall footer), `pr_el_nuevo_dia`
  15 (the submission note and paywalled stubs), 4 others; no cross-outlet relation lost. New: 33 cross-outlet pairs (contained 20,
  near-identical 12, exact 1) that the furniture had kept under the threshold. Cross-outlet classes 9 / 102 / 81 (exact /
  near-identical / contained) → 15 / 146 / 64; 40 kept cross-outlet pairs move up a class (furniture gone), 3 within-outlet
  pairs move down to `contained`. C05 and C49 no longer carry a relation. This is evidence that page furniture no longer drives these relations; it is **no claim that the index is free of
  boilerplate effects** — text inside blocks and recurring-but-kept text still count.

## 10. Performance

- 0.4.0 extracts in 12.78 ms per page against 11.58 ms for 0.3.0 (+10 %, one process at below-normal priority beside CO.RA.PAN's
  production); `body-quality/1` 2.12 ms; `editorial-metadata/3` costs what `/2` costs. The template table is read once per
  process; matching is one digest per BODY block. No workspace scan, no corpus comparison per article: the table is built
  offline (`study_body_quality.py templates`, about two minutes over the 4,759 pages) and pinned; a new table is a new version.
- Storage: one optional field on changed blocks; nothing is duplicated.

## 11. Is an LLM escalation needed? — No

1. **Unsolved classes:** foreign material inside a block; small unmarked, non-recurring labels; text absent at the source.
2. **Detection:** `residual_suspect` flags 332 pages (7.0 %); the flag is imprecise by design (about half real residue in a
   reading of 24).
3. **Affected:** at most those 332 pages, 295 of them CORE-accepted; the residue is mostly a few words per page.
4. **Rescuable:** an LLM recovers no absent text (the 186 `not_article` / `incomplete` pages), and it would not change a CORE
   decision on the flagged pages.
5. **Cost of local inference:** not measured (`NOT_YET_MEASURABLE`); it would need a pinned model, a GPU or long CPU runs,
   a span-level record schema and a gold sample for its validation (AGENTS §13).
6. **Justified?** Not now: the benefit is a few words of contamination on a few percent of pages; the deterministic selection
   already removes the systematic furniture and records it.

## 12. The escalation contract, should a later run need it (not built, not proposed for activation)

- **Input:** one `residual_suspect` record — its blocks (index, kind, text, selection) and the signals; no other page text.
- **Output:** a list of `{block_index, start, end, label, reason, certainty}` with `label` in a closed vocabulary (the
  `module_*` and `outlet_template` reasons plus `foreign_span`) — markings only, never text.
- **Verification:** a proposal is kept only when `text[start:end]` of that block reproduces the proposed span exactly; a
  whole-block proposal that agrees with a deterministic signal may enter a review queue as a proposed exclusion; a partial span
  never changes the BODY (it needs a span-level schema first) and goes to review; an uncertain proposal goes to review.
- **Record:** an append-only layer (`body-span-proposal/1`) keyed by the record digest, the model and its hash, the prompt
  version; a new model is a new artifact.
- **Gate:** activation only on a reproducible net benefit against this deterministic baseline on human gold (AGENTS §13).

## 13. The independent human control

- **Frozen** before any verdict: [`docs/intake/quality/body_quality_control_2026-11-15/`](../intake/quality/body_quality_control_2026-11-15/README.md)
  — manifest, form (45 cases, 135 questions), the sealed key; the reading sheet (publisher text) local only; a second draw
  reproduced the manifest bit for bit.
- **Population:** 4,504 eligible pages — the 4,759 minus the 2026-11-15 review, the phase-3 blind control (now development
  material) and every page this run opened one by one. A holdout within the known population, not fresh data.
- **Components:** random 16 (systematic, inclusion probability 16 / 4,504 each); targeted 29 in 9 strata — large removals (4),
  inclusions (4), templates (3), modules (3), CORE newly rejected (3) and newly accepted (3), residual (4), unchanged-clean (3),
  not-article or incomplete (2).
- **Blind by construction:** each case lists every block that **either** version takes as BODY, numbered in page order, without
  saying which keeps which; the reader marks the foreign blocks, missing text and CORE. `merge` counts for both versions the
  correct removals, the **false deletions** and the **residual contamination**, random and targeted apart.
- The agent did not read the drawn cases and changed no rule after the draw.

## 14. Tests and technical checks

- `tests/test_body_quality.py`, 28 tests: the named failures and their general forms, the negative counter-examples (a mark
  around the whole article, a paywall teaser lead, profile lines, data lists, sentence headings, a paragraph ending in an AI
  image credit), the record (selection checked by `record_problems`, refused under `/2`, determinism), the pinned table (digests
  only; missing or foreign table an error), `body-quality/1` states, `agency-credit/3`, `editorial-metadata/3` (three distinct
  fingerprints), the joint export refusing `extraction/3`, the control's `merge`.
- **Full suite** (`python -m pytest tests`, final code and documents, below-normal priority beside CO.RA.PAN's production):
  **2,142 passed, 15 skipped** in 693 s (the known skips: candidate tools not installed, no symlink privilege, applied proposals).
  After it no tracked file was modified. The draw was repeated and reproduced the manifest bit for bit; every study derivation
  ran on the same cache, and the final one is the study record.

## 15. Activation, Git, push

- **Activation:** none. `article_html/0.4.0`, `body-templates/1`, `body-quality/1`, `agency-credit/3`, `editorial-metadata/3`
  are candidates; `content-quality/3` unchanged; nothing in production, intake, release or admission reads them.
- **Git:** commits on `phase3/body-quality` with explicit pathspecs — the code (schema, extractor, contamination status,
  provenance, envelope, template table, study script, tests, suite manifest), then CPD-0041 and its evidence, then this report;
  merged into `main` by fast-forward (`main` had not moved: `dd183e9`); `main` and the branch pushed; this report published on
  `main` with `scripts/publish_run_report.py publish … --status PASS`; the worktree removed last with
  `scripts/worktree_closure.py remove` (never `--force`). The outcome of the last two is stated in the operator report.
- **Local scratch:** the page cache (publisher bytes), the row files, the measurement and probe outputs and a redraw under
  `%LOCALAPPDATA%\Temp\coprepan-body` are deleted; the BODY control's reading sheet (publisher text, the operator's working copy)
  is kept outside the repository under `%LOCALAPPDATA%\Temp\coprepan-body-control-sheet\` and handed to the operator; the
  scratchpad probes are session files outside the repository. Nothing in the repository was moved, deleted or overwritten; the
  phase-3 key, manifest and form are unchanged; the four older worktrees and every other branch are untouched.

## 16. Next step

The operator's answers to the BODY control (45 cases, 135 questions). Then one decision run: adopt `article_html/0.4.0` and
`content-quality/3` as binding, or correct them from the control's false deletions and residuals. No LLM run is recommended.
