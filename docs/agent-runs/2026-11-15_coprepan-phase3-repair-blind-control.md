# 2026-11-15 — CO.PRE.PAN Phase-3 repair: title surface, agency roles, exact against near-identical text, and a frozen blind control

**Status:** `PASS` (technical repair, its measurement on the stored pages, and the preparation of the blind acceptance) · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-15 (Sunday), Europe/Berlin, from about 18:15 |
| Kind | implementation + offline measurement on stored raw evidence + preparation of a human control (AGENTS §8). **Not** a validation and **not** an activation |
| Status | `PASS` for the brief's completion criteria (§11 of the brief; each in §2 below). It does **not** claim that any extractor, gate or layer is validated or adopted: every component is a `CANDIDATE` / `NOT_VALIDATED`; the blind control is prepared and frozen, not answered |
| External calls | none. No publisher request, no web page, no provider, LLM, GPU or HPC call |
| Start | `main` = `origin/main` = `e8964d79a0bf4c5a97e4fd334ba70ba6b20304b9`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\phase3-repair`, branch `phase3/repair-blind-validation` |
| Operator brief | "CO.PRE.PAN_v3 – Gezielter Phase-3-Repair und wissenschaftliche Blindvalidierung" (2026-11-15) |
| Decision | [CPD-0040](../decisions/CPD-0040_phase3-repair-title-surface-agency-roles-text-match-and-blind-control.md) (partially supersedes CPD-0039 for three preferred candidates) |
| Evidence | [study record](../intake/quality/phase3_repair_study_2026-11-15.json), [blind control](../intake/quality/phase3_blind_control_2026-11-15/README.md) (manifest, form, sealed key), [change request](../crosscorpus/RELATION_MATCH_CLASS_CHANGE_REQUEST_2026-11-15.md) |

## 1. Actual start state

- **Repository:** `main` = `origin/main` = `e8964d7` (the published report of the Phase-3 integration), clean. Four older worktrees
  (`legacy-archive-contract`, `legacy-freeze`, `newfs-phase-b`, `newfs-phase-d`) belong to other runs and were left untouched
  (`worktree_closure.py status`: `KEEP`, no report named). No CO.PRE.PAN process was running.
- **CO.RA.PAN production was running** (scheduler, preservation sidecar, reservoir drive, six reservoir-controller workers,
  observatory, backup reconcile, KISSKI supervisor; CPU about 26 % at the start, 24 logical processors). It was read only (process
  list, `git log` / `git status` of its checkout); nothing was stopped, changed or started there. Every heavy step of this run ran
  at below-normal priority, one process at a time.
- **Monday's programme** (backup, preservation, the `/2` canary) had not run and was not touched; no pinned canary or intake state
  was read for writing.
- **Raw evidence read:** the 4,759 stored 2xx item pages of the CPD-0039 study, read once from the local packs of the workspace
  into a page cache under `%LOCALAPPDATA%\Temp\coprepan-phase3r` (outside the repository and every shared root; deleted at the
  end, §11). The scientific decisions of CPD-0039 §1 were taken as given (brief §2) and not reopened.

## 2. Fulfilment, repair by repair

| Brief | Done | Where |
|---|---|---|
| A — the three title / subtitle errors | fixed: event field and newsletter box are no subtitle; "La Nación" is replaced by the article's headline | §3, §6 |
| A — no relevant regression of other titles / subtitles | every changed and every removed item read; BODY identical on all 4,759 pages; no correct subtitle found lost | §5 |
| A — versioned, earlier versions intact | `article_html/0.3.0` beside `0.2.0` (unchanged); same record schema `extraction/2` | §7 |
| B — "Con información de EFE" no longer editing | `agency-credit/2`: role and declared use apart; all 15 former `edited_declared` read again | §5, §6 |
| C — exact, near-identical, contained apart | `text-reuse/2` with `text_match`; exactness from the canonical text, never from overlap; boilerplate checked | §5, §6 |
| C — joint contract untouched | relation kinds unchanged; a change request for an optional match class | §4 |
| CORE strategy unchanged | `content-quality/3` untouched; decisions and reasons identical on every page | §5 |
| Blind control frozen | 70 cases, 253 questions; manifest, form and sealed key committed; reproducible bit for bit | §8 |
| No activation | none: every component `CANDIDATE` / `NOT_VALIDATED` | §12 |

## 3. Causes of the observed errors (read on the stored raw pages)

1. **`cu_14ymedio`, "Lugar: Teatro Martí, …" as subtitle** (`87bceea3aa73f0e6`). The event listing prints three `h2` fields
   ("Lugar: …", "Fecha de inicio: …", "Fecha de fin: …"); the page's `og:description` is their concatenation. 0.2.0's prefix
   match (a stated description that *begins* with the block) took the first field as the page's own subtitle. General form: a
   description that strings several header fields together; 15 event pages of the outlet, 2 more fields ("Entrada:",
   "Horario:") taken by markup alone.
2. **`co_el_espectador`, newsletter promotion as subtitle** (`dcf263e57c33ed75`). The article is behind the paywall ("Lee este
   contenido exclusivo para suscriptores"); the only "body" block 0.1.0's density rule finds is the footer, so the header region
   between the title and the first body block spanned 230 blocks of the page, and the first block with a `subtitle` class in it
   was the newsletter box's ("block-header__subtitle" inside a `newsletter` element), 58 blocks after the title. General form: a
   marked block far from the title (13 such under 0.2.0, all more than 30 blocks away: 9 newsletter boxes, teasers of other
   articles); and a promotion module.
3. **`py_la_nacion`, "La Nación" as title** (`52a11ea14f886779`, `2f1d2b667ad0b3b3`; the second accepted by the gate). The page
   prints the logo as its first `h1` and the headline as the second; 0.1.0 and 0.2.0 take the first `h1`. 0.2.0 noticed that the
   `h1` is not the stated headline (so it read no subtitle) but kept it as the title. General form: a branding or edition `h1`
   before the article's own (`py_la_nacion` 81, `ec_primicias` 78 "Primicias Ecuador 9 de octubre de 2026", `py_noticias_cde` 3),
   and an `h1` that is the site's name (`cu_juventud_rebelde` 31) or a section label (`bo_opinion` 52: "Cochabamba", "El País",
   "Mundo") where the headline is only in the metadata.
4. Found on the way, the same family: a stated description repeated further down (a gallery's captions, a share box, the
   paywalled copy) became a second, third, … subtitle (`pe_diariocorreo`: 11 on one page); and a stated "description" that is
   the headline itself made a caption a subtitle.

## 4. The technical solution

- **`article_html/0.3.0`** (record schema `extraction/2` unchanged, so no contract moves). Title: the first `h1` that is a
  stated headline (JSON-LD `headline`, `og:title`, `twitter:title`, `<title>`; equal, contained, or one separator-delimited part);
  otherwise the first `h1`, unless it is branding (`og:site_name`, `application-name`, JSON-LD publisher, the rest of a stated
  title once a stated headline is taken out) or a stated section label — then **no title block**, and `metadata.title` keeps the
  page's statement with its basis. An `h1` that is not the title is a `heading`, never BODY. Subtitle: 0.2.0's two paths, with
  five exclusions — promotion / newsletter / subscription modules (not the element around the title), data-sheet fields (label
  and colon beside a block of the same shape), caption / credit / gallery marks on both paths, one subtitle per stated text and
  no description that is the headline, markup alone only within 12 blocks of the title. No outlet rule; the only textual form
  read is the field label. A printed headline that differs from the search title (`ar_clarin`, `mx_el_universal`,
  `cl_the_clinic`, `es_eldiario_es`, …; with section index pages 128 pages whose first `h1` is not a stated headline, measured
  under 0.2.0) stays the title.
- **`agency-credit/2`** in **`editorial-metadata/2`**: `agency_roles` (`credited` · `co_credited` · `material_source`) and
  `use_declared` (`verbatim_declared` · `edited_declared` · `material_used_declared` · `not_stated`) as two properties per credit
  and per page; `credited_with` names the newsroom or publisher verbatim (a place, a date, a handle or the agency's own desk —
  "Redacción EFE" — is not a party); unknown says why (`agency_named_as_quoted_source_only` / `no_agency_credit_observed`). Only
  an explicit statement sets a use. `/1` and `editorial-metadata/1` are unchanged (their fingerprint is byte-identical; tested).
- **`text-reuse/2`**: the same candidates, threshold and relation kinds; `text_match` `exact` (same canonical BODY text: NFC,
  invisible format characters removed, white space incl. paragraph breaks folded — nothing else) · `near_identical` (each ≥ 0.9
  of its shingles in the other) · `contained`; the measured values on the relation; direction an order of appearance, never
  origin or authorship. The index stays incremental (one digest and one word count per document more; no all-pairs comparison).
  The joint vocabulary is not touched: the class leads the `basis`, and an optional `match_class` / `match_rule` is a
  [change request](../crosscorpus/RELATION_MATCH_CLASS_CHANGE_REQUEST_2026-11-15.md) to the analysis contract proposal.

## 5. Old against new (4,759 stored 2xx item pages, 91 outlets; measured offline 2026-11-15)

**Text structure** (`article_html/0.2.0` → `0.3.0`):

| Measure | 0.2.0 | 0.3.0 |
|---|---|---|
| BODY digest identical | — | **4,759 of 4,759** |
| machine-summary modules identical | — | 4,759 of 4,759 |
| extracted-text digest changed | — | 294 pages (title surface only) |
| title block changed | — | 246: another `h1` 162 (`py_la_nacion` 81, `ec_primicias` 78, `py_noticias_cde` 3); none 84 (`bo_opinion` 52, `cu_juventud_rebelde` 31, `hn_el_heraldo` 1) |
| pages without a title block | 174 | 258 |
| pages with a subtitle | 2,953 | 3,004 |
| subtitle blocks by basis (page statement / markup) | 2,789 / 249 | 2,819 / 232 |
| outlets with a subtitle | 66 | 66 |
| subtitle surface changed | — | 121 pages: 73 gained (`ec_primicias`, its title now found), 48 lost a block (event fields 15, newsletter boxes 9, repeats and far marked blocks 24) |

What was read (agent reading, **not gold**): every removed subtitle block (all 48 pages) — event fields, newsletter boxes,
repeated copies of a subtitle that is kept once, captions and teasers; none was the only real subtitle of its page. The 246 title
changes fall into the six outlet patterns of the table, each read on sample pages: the 162 new titles are the page's stated
headline; the 84 pages without a title block printed a logo, the site's name or a section label as `h1`. Of the 73 added
subtitles (`ec_primicias` standfirsts after the now-found headline), 4 were read.

**CORE** (`content-quality/3`, on 0.2.0 and on 0.3.0): ACCEPT 4,066 / REJECT 693 on both; **decision and reasons identical on
every page**; every feature but the title text identical (the title only reaches the gate through the live-page title rule, and
no title change touched it). The 4,066 is the measured result, not a target.

**Other layers** (`editorial-metadata/1` on 0.2.0 → `/2` on 0.3.0): `section-iptc/1`, `editorial-scope/1`, `genre-placement/1`,
`genre-declared/1`, `ai-disclosure/1` — the record is identical on all 4,759 pages (IPTC coverage stays 34.8 %; AI provenance
unchanged).

**Agency** (`agency-credit/1` → `/2`, the same 407 pages and the same agencies on each):

| /1 `agency_use` | → /2 role / declared use | Pages |
|---|---|---|
| `credit_only` | `credited` / `not_stated` | 368 |
| `joint_credit` | `co_credited` / `not_stated` | 16 |
| `credit_only` | `co_credited` / `not_stated` ("Redacción Web con AFP", "Redacción internacional con AFP", "Redacción / EFE" — bylines /1 cut at "Redacción") | 5 |
| `credit_only` | `credited`+`co_credited` / `not_stated` (`co_el_espectador`: "Redacción Mundo y Agencia AFP" beside "Por Agencia AFP") | 1 |
| `edited_declared` | `material_source` / `material_used_declared` | 10 |
| `edited_declared` | `credited`+`material_source` / `material_used_declared` | 5 |
| `credit_only` | `material_source` / `material_used_declared` ("La información es de …") | 2 |

No page states editing or a verbatim take-over (`edited_declared`, `verbatim_declared`: 0). Several agencies on one page: 4.
Unknown: 66 pages name an agency only as a quoted source ("según informó la agencia EFE", "dijo Murillo a la agencia EFE"),
4,286 show no credit. Agencies: EFE 247, AFP 74, AP 47, unspecified ("Agencias") 25, Europa Press 11, ATON 2, IPS 2, ACAN 2,
Colprensa 1.

**Text reuse** (`text-reuse/1` → `/2`, the same 547 pairs):

| /1 | → /2 | Pairs |
|---|---|---|
| `syndicated_copy_of` · `identical` | `exact` | 9 |
| `syndicated_copy_of` · `identical` | `near_identical` | 102 |
| `syndicated_copy_of` · `contained` | `contained` | 81 |
| `duplicate_of` · `identical` | `exact` | 347 (30 of them two fetches of one address) |
| `duplicate_of` · `identical` | `near_identical` | 3 |
| `duplicate_of` · `contained` | `contained` | 5 |

Near-identical pairs: word-sequence ratio 0.907–0.9997 (median 0.972); 10 pairs that are not exact have the same bag of
lower-cased words (only quotation marks, case or punctuation differ). **Boilerplate:** the share of a pair's shared shingles that
one of its outlets prints in at least three unrelated documents is at most 0.36 (18 pairs above 0.1, none at 0.5): no relation
rests on site furniture. The first check, against any document outside the pair, flagged 462 pairs — all variants of the same
wire stories below the threshold, not furniture; it was replaced by the per-outlet check. **Questionable relations:** the 30
same-address `duplicate_of` pairs are re-fetches of one page (the study compares fetches; the repository's document identity
folds them into one document); of the 347 within-outlet exact pairs the gate rejects the later copy in 346 (for its own reasons:
it reads no relation). Across outlets the later copy is accepted in 182 of 192 pairs: reuse removes nothing from CORE.

**Cost** (one process, below-normal priority, beside CO.RA.PAN's production): extraction 10.5 ms per page (0.3.0) against
10.4 ms (0.2.0); metadata 0.86 ms (`/2`) against 0.67 ms (`/1`); text reuse over all pages 3.5 s (`/2`) against 2.2 s (`/1`).

## 6. Corrected original examples (verbatim, stored pages)

- **Title.** `py_la_nacion` `52a11ea14f886779`: "La Nación" → "Se sacudió con una goleada"; `2f1d2b667ad0b3b3` (accepted): "La
  Nación" → "Con la obligación de sumar de los líderes"; `ec_primicias` `c0106871339bd4dc`: "Primicias Ecuador 10 de octubre de
  2026" → "Max Verstappen se lleva la clasificación y saldrá primero en Singapur"; `bo_opinion` `e0a02c2b74bf7022`: "El País" →
  no title block (metadata, JSON-LD: "Reservas Internacionales alcanzan a $us 3.932,8 mi…"); `cu_juventud_rebelde`
  `219cc25cc8f3bf2f`: "Juventud Rebelde - Diario de la Juventud Cubana" → no title block (metadata, `og:title`).
- **Subtitle.** `cu_14ymedio` `87bceea3aa73f0e6`: "Lugar: Teatro Martí, calle Dragones, esquina a Zulueta, La Habana Vieja,
  Cuba." → none; `co_el_espectador` `dcf263e57c33ed75`: "Lo bueno que es estar informado y de una manera diferente desde tu
  correo electrónico." → none; `ar_clarin` `17f1ff5ebb537ad2`: the subtitle and its repetition as a photo caption ("… Foto:
  gentileza") → the subtitle once; `ec_primicias` `43c72da09d32b3cd`: none → "Papers del Centro de Investigación para la Salud en
  América Latina de la PUCE y la Universidad de Ohio abren e…".
- **Agency.** "Con información de EFE." (`ec_el_comercio`, `ni_confidencial`, `sv_el_diario_de_hoy`, `uy_el_observador`, …):
  `edited_declared` → `material_source` / `material_used_declared`; "EFE / Redacción Primicias": `co_credited`, `credited_with`
  "Redacción Primicias"; "Redacción EFE" (`gt_prensa_libre`): `credited` (the agency's desk); "Madrid| EFE| @PanamaAmerica":
  `credited` (a place and a handle).
- **Text pairs** (word-level differences from the study record):
  - `exact`: `gt_prensa_libre` within the outlet, 524 / 524 words, containment 1.0 / 1.0, no differing segment;
  - `near_identical`, outlet furniture in the BODY: `bo_el_deber` → `do_hoy`, 160 / 175 words, containment 0.99 / 0.90 — the
    copy adds "Publicado por Actualizado: 10.10.2026 | 15:55 En: Washington" and "El Mundo";
  - `near_identical`, typography: `bo_el_deber` / `ni_despacho_505` — `"ha` against `«ha`, `presidente".` against
    `presidente».`; `pa_metro_libre` within the outlet — "cerrado" against "cerrrado";
  - `contained`: `ar_el_tribuno` (392 words) inside `ar_perfil` (751 words), containment 0.96 / 0.50.

## 7. New and changed versions

| Component | Version | Lifecycle | Relation to the earlier |
|---|---|---|---|
| extractor | `article_html/0.3.0` (`PREFERRED`) | `CANDIDATE` | beside `0.2.0` and `0.1.0`, both unchanged; record schema `extraction/2` unchanged |
| agency layer | `agency-credit/2` | `NOT_VALIDATED` | beside `/1`, unchanged |
| metadata artifact | `editorial-metadata/2` (`PREFERRED`) | `NOT_VALIDATED` | `/1` with `agency-credit/2`; `/1` default and fingerprint unchanged |
| text relation rule | `text-reuse/2` | `NOT_VALIDATED` | beside `/1` (default, unchanged) |
| unchanged | `extraction/2`, `content-quality/3`, `section-map/1`, IPTC extracts, `editorial-scope/1`, `genre-placement/1`, `genre-declared/1`, `ai-disclosure/1`, `intake-controller/3`, storage and preservation contracts | — | — |

Code: `src/coprepan/extraction_article.py`, `provenance.py`, `enrichment.py`, `text_reuse.py`; `scripts/study_phase3_repair.py`;
`tests/test_phase3_repair.py` (31 tests, suite `foundation_contract`). Documents: CPD-0040; CPD-0039 (status
`PARTIALLY_SUPERSEDED`, dated status line); decision registry and architecture index; PHASE3 architecture §5, §7.1, §10;
terminology §27; analysis contract §5.6 (dated note); crosscorpus and extraction indexes; STATUS.

## 8. The blind control

- **Population:** the 4,759 stored pages; **excluded** 133 — the 109 pages of the 2026-11-15 review sample and every page this run
  opened one by one while repairing (listed in the script) — **eligible 4,626**.
- **Random component (24):** systematic sample with a random start (seed `phase3-blind-control-2026-11-15/random`) over the
  eligible pages ordered by country, outlet and a seeded digest; inclusion probability 24 / 4,626 = 0.0052 for every page,
  accepted, rejected and unextractable alike. Every applicable question is asked.
- **Targeted component (46), 15 strata**, each drawn as the first *k* by seeded digest, one page (or one outlet pair) per outlet,
  asked only the questions of its feature:

| Stratum | Population | Drawn | Questions |
|---|---|---|---|
| title changed by 0.3.0 | 237 | 5 | TITLE, SUBTITLE |
| a 0.2.0 subtitle 0.3.0 does not keep | 27 | 4 | TITLE, SUBTITLE |
| subtitle from the page's statement | 2,725 | 3 | TITLE, SUBTITLE |
| subtitle by markup alone | 173 | 3 | TITLE, SUBTITLE |
| no subtitle, CORE accepted (recall) | 1,298 | 3 | TITLE, SUBTITLE |
| AI use declared for the article | 23 | 4 | AI_TEXT, AI_COMPONENT |
| AI components only | 219 | 2 | AI_TEXT, AI_COMPONENT |
| agency `/1` edited or joint | 22 | 4 | AGENCY_ROLE, AGENCY_USE |
| agency `credited` only | 353 | 2 | AGENCY_ROLE, AGENCY_USE |
| agency quoted only | 61 | 3 | AGENCY_ROLE, AGENCY_USE |
| CORE rejected | 656 | 3 | BODY_COMPLETE, BODY_CLEAN, CORE |
| a published section, IPTC unknown / undecided | 2,640 | 2 | IPTC |
| text pairs `exact` / `near_identical` / `contained` | 286 / 92 / 74 | 2 / 3 / 3 | REUSE |

- **Blinding:** the reading sheet shows the page's own evidence — headline candidates from every `h1`, the JSON-LD headline,
  `og:title` and `<title>` in a fixed order; the blocks after each `h1`; the stated description; the extracted BODY; the
  published section; every block mentioning AI; every credit and mention of an agency; for a pair both BODY texts and their
  word-level differences — never the machine's answer, the stratum or the component. Case ids are in a neutral digest order.
  The key (predictions, evidence, rule versions, feature values, strata, inclusion probabilities) is a separate file; the
  manifest holds its SHA-256 and those of the form and the sheet; `merge` refuses a changed key and reports the two components
  apart. A second draw reproduced the manifest bit for bit.
- **Files:** `docs/intake/quality/phase3_blind_control_2026-11-15/` — `README.md`, `manifest.json`, `verdicts_form.csv`
  (253 rows), `KEY_machine_predictions_open_only_after_the_verdicts.json`; the reading sheet (publisher text) is local only and
  was handed to the operator; it is regenerated by `study_phase3_repair.py draw` with the digest in the manifest.
- **What it can say:** the random component speaks to the population, coarsely (24 of 24 agreements: 95 % lower bound about
  0.86); a targeted stratum finds errors and is no precision. The rules were repaired on aggregate measurements of the same
  population; the control is independent of the cases opened, not fresh data. BODY questions judge the text shown. The agent
  did not read the drawn cases and changed no rule after the draw.

## 9. Regressions and performance

- **Tests:** `tests/test_phase3_repair.py` 31 tests — the three failures and their general forms (logo / site-name / section
  `h1`, event fields, newsletter box, far marked block, repeated and caption copies, description that is the headline), negative
  counter-examples (a printed headline different from the search title stays; a promotion mark around the title does not exclude
  the subtitle; the entradilla rule; a good BODY without a title is accepted), the agency roles and uses (material, joint, desk,
  place, handle, explicit editing and verbatim statements, several agencies, quoted source, photo credit), `editorial-metadata/2`
  (layers, `/1` fingerprint unchanged, write-once reuse), `text-reuse/2` (canonical exactness against case, punctuation and wording
  differences at full containment, near-identical against contained, measured values, direction, `/1` unchanged, incremental
  index), the systematic sample and `merge`'s refusal of a changed key. The 76 tests of `test_phase3_metadata.py` pass unchanged.
- **Determinism:** each extraction run twice gives the same record (tested); repeated derivations on the same cache gave
  identical results for every rule not changed in between; the draw reproduced bit for bit.
- **Digests:** BODY digests identical on all pages; extracted-text digests change only with the title surface; layer records
  identical where their rule is unchanged.
- **Denominator and release:** the BODY — the counted surface — is unchanged; the joint release export still refuses an
  `extraction/2` record (the CPD-0039 test passes unchanged).
- **Incremental behaviour:** no workspace scan beyond the one read of the stored packs into the local cache; the reuse index adds
  one document at a time against its sketch candidates.
- Full suite: §11.

## 10. Remaining quality limits

- **BODY defects seen, not repaired here** (the brief keeps BODY unchanged): on paywalled pages (`co_el_espectador`,
  `ar_rio_negro`) the density rule finds only the footer — such pages are rejected as too short, but their header region is
  unreliable; outlet furniture inside some BODY texts ("Publicado por Actualizado: …", "Escuchar audio noticia", "+info"), visible
  in near-identical pairs. A body repair is its own versioned step.
- **Titles:** 258 pages have no title block (174 had none before: listing pages, pages without `h1`); a printed headline that is
  neither a stated headline nor branding is kept as it is — correct for the measured cases, not proven for every CMS.
- **Subtitle recall** is not measured: 1,298 accepted pages carry none; the blind control's recall stratum is small.
- **Text reuse:** recall is not measured (no claim); texts under 50 words are never compared; the threshold 0.9 and the 8-word
  shingle are /1's; the study compares fetches, so re-fetches of one address appear as relations (30).
- **Agency:** the agency list is closed; the quoted-source form is a pattern (66 pages), not exhaustive; no page states its use
  beyond "material used", so `edited_declared` and `verbatim_declared` are untested on real pages.

## 11. Tests, commits, push, worktree

- **Full suite** (`python -m pytest tests`, on the final code, below-normal priority beside CO.RA.PAN's production): **2,112
  passed, 15 skipped** in 715 s (the 15 skips are the known ones: candidate tools not installed, no symlink privilege, applied
  proposals). After it no tracked file was modified. `test_repository_contract.py` with both Phase-3 test files re-run after the
  last document edit: 203 passed.
- **Commits** on `phase3/repair-blind-validation` (explicit pathspecs): `7640bcf` code (extractor, provenance, enrichment, text
  reuse, study script, tests, suite manifest); `5b0c62e` CPD-0040 and its evidence (study record, blind control, change request,
  STATUS, architecture, terminology, indexes); then this report.
- **Closing states** (each a different fact): changes committed on the branch; **merged** into `main` by fast-forward (`main` had
  not moved: `e8964d7`); `main` and the branch **pushed** to `origin`; this report **published on `main`** with
  `scripts/publish_run_report.py publish … --status PASS`; the worktree **removed** last with `scripts/worktree_closure.py remove`
  (never `--force`). The outcome of the last two is stated in the operator report.
- **Local scratch:** the page cache (publisher bytes), the row file, the measurement files and a redraw under
  `%LOCALAPPDATA%\Temp\coprepan-phase3r` are deleted; the reading sheet of the blind control (publisher text, the operator's
  working copy) is kept outside the repository under `%LOCALAPPDATA%\Temp\coprepan-phase3-blind-sheet\` and handed to the
  operator; the scratchpad probes are session files outside the repository. Nothing in the repository was moved, deleted or
  overwritten; the four older worktrees and every other branch are untouched.

## 12. Scientific decisions that are actually open (the operator's)

1. **The blind control** — the only next act: answer `verdicts_form.csv` from the reading sheet; then `merge`.
2. After it: adopt `article_html/0.3.0` as the corpus extractor and `content-quality/3` as the binding CORE standard, or correct
   them (CPD-0040 *Not decided here* 1).
3. Validate `section-map/1`, `ai-disclosure/1`, `agency-credit/2`, `text-reuse/2` as release fields, or keep them study layers.
4. Joint with CO.RA.PAN: the unit kind `subtitle` (change request of 2026-11-15) and the relation match class (this run).
5. Unchanged from CPD-0039: titles and subtitles in the first release's annotation; complete briefs under 150 words.

## 13. Next step

The operator's answers to the blind control (`docs/intake/quality/phase3_blind_control_2026-11-15/`, 70 cases, 253 questions).
No further agent run is needed before it. Monday's programme (backup, preservation, `/2` canary) is independent of this run.
