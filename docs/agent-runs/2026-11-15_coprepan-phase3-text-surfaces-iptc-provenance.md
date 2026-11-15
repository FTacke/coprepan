# 2026-11-15 — CO.PRE.PAN Phase-3 integration: text surfaces, IPTC, AI and agency provenance, CORE quality

**Status:** `PASS` (technical implementation and preparation of the scientific acceptance) · `EXTERNAL_API_USAGE = IPTC_REFERENCE_VOCABULARY_ONLY`

| Field | Value |
|---|---|
| Date | 2026-11-15 (Sunday), Europe/Berlin, from about 14:40 |
| Kind | implementation + offline measurement on stored raw evidence (AGENTS §8). **Not** a validation and **not** an activation |
| Status | `PASS` for the technical scope of the brief (§16 of the brief, each point in §13–§15 below). It does **not** claim that any layer, the extractor or the gate is validated or adopted: every component is a `CANDIDATE` / `NOT_VALIDATED`; the human review and the operator's adoption are open (§14), and one joint act with CO.RA.PAN (§10) |
| External calls | 2 requests to the IPTC CV server (`cv.iptc.org`, Media Topics and Genre JSON, reference vocabularies the brief names); 4 IPTC web pages (Media Topics, NewsCodes terms, CV guidelines, NewsML-G2 2.36 note) and 1 GitHub page (404) read with the agent's web tool (which summarises a page with a model of the agent harness). **No publisher request, no LLM provider call by repository code, no GPU, no HPC** |
| Start | `main` = `origin/main` = `4132fb7`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\phase3-provenance`, branch `phase3/text-surfaces-provenance` |
| Operator brief | "CO.PRE.PAN_v3 – Phase-3-Integration: IPTC, Textoberflächen, KI-/Agenturprovenienz und CORE-Qualität" (2026-11-15) |
| Decision | [CPD-0039](../decisions/CPD-0039_text-surfaces-iptc-provenance-and-core-quality.md) (amends CPD-0038, now `PARTIALLY_SUPERSEDED`) |
| Evidence | [study record](../intake/quality/phase3_metadata_study_2026-11-15.json), [human review sample](../intake/quality/phase3_review_2026-11-15.md), [joint change request](../crosscorpus/SUBTITLE_UNIT_KIND_CHANGE_REQUEST_2026-11-15.md) |

## 1. Start state, branch, authorisation

- **Repository:** `main` = `origin/main` = `4132fb7` (the published report of the weekend run), clean. Four older worktrees
  (`legacy-archive-contract`, `legacy-freeze`, `newfs-phase-b`, `newfs-phase-d`) left untouched. No CO.PRE.PAN process running.
- **Monday's programme had not run and was not touched:** it is Sunday; the 1,018 weekend fetches (112 packs) are still
  `PRESERVATION_PENDING` in the runtime workspace on `C:` (last pack written 11:48 today, by wc-1); the `/2` canary
  `in2-20261114-canary` is prepared and unrun; its plan, the 24-hour draft and the baseline extractor are unchanged by this run.
- **CO.RA.PAN production was running** (scheduler, preservation sidecar, reservoir drive with six workers; CPU 60–75 % from it).
  It was read only (process list); nothing was stopped, changed or started. Every heavy step of this run ran at below-normal or idle
  priority.
- **Authorised:** implementation, read-only analysis of the repository and the stored raw evidence, offline experiments, tests,
  documentation, Git closure. **Not authorised and not done:** any publisher request, acquisition, 24-hour wave, recurring
  production, backfill or reprocessing, HPC / GPU / LLM provider calls, NEW_FS migration or preservation promotion, changes to
  CO.RA.PAN, changes to pinned canary or intake states, activation of a scientific layer.
- **Raw evidence read:** the 4,759 stored 2xx item pages of the workspace (pilot and 24-hour intake of October, weekend waves),
  read once from the local packs and kept in a local page cache under `%LOCALAPPDATA%\Temp\coprepan-phase3` on `C:` (outside the
  repository and every shared root; deleted at the end, §15). `FTacke/coprepan-app` was **not reachable** (no local checkout, no
  `gh`, the repository answers 404 to an anonymous read); the legacy section mapping was read instead from the frozen legacy
  repository (`legacy/coprepan/config/sections/section_map_v1.yml`, read-only), which is the mapping of the legacy pipeline.

## 2. Scientific target decisions (the operator's, recorded in CPD-0039 §1)

1. **CORE = general text quality.** Section, scope, genre, opinion, metadata completeness, declared AI use and agency origin do not
   decide CORE membership. AI-generated, AI-assisted and agency texts are wanted corpus material.
2. **Unknown is not negative.** Missing metadata is a value state with a reason; no AI disclosure ≠ made without AI; no agency
   credit ≠ own reporting.
3. **IPTC Media Topics** (sections) and **IPTC Genre** (declared genres) are the reference taxonomies.
4. **No mandatory LLM classification** in the ingest; textual properties (narrativity, opinion, reportage style) are later study
   layers.

## 3. Changes to the extraction contract

- **`extraction/2`** (`coprepan-extraction/v2`) = v1 + block kind **`subtitle`** (role `title`, with `basis` `stated_by_page` or
  `subtitle_markup`) + optional block field **`module`** (closed vocabulary `ai_summary`; never BODY). Digests as in v1 (kind, role,
  text of every block), so a page whose blocks keep kind, role and text keeps its document version. `Extractor.record_schema` names
  the schema an extractor writes; `Extractor.run` checks every record against it (`extraction.record_problems`); a stored record is
  read only as the schema its extractor writes (`core_pipeline`). `extraction/1`, `baseline_html/0.1.0` and `article_html/0.1.0`
  are byte-identical in output to before.
- **`article_html/0.2.0`** (new version beside 0.1.0, `CANDIDATE`): 0.1.0's container rule plus
  - *subtitle*: a block between the title and the first body block whose text the page states as the article's
    `alternativeHeadline` / `description` (JSON-LD, `og:description`, `description`, `twitter:description`; a shortened statement
    matches on its first 60 characters), or the **first** block whose element carries a subtitle mark (`subtitle`, `subtitulo`,
    `subheadline`, `bajada`, `copete`, `standfirst`, `sumario`, `deck`, `dek`, `entradilla`, `excerpt`, `epigraph`; at least 40
    characters; never beside a caption, credit, byline or date mark); a leading body *heading* stated by the page; never a body
    *paragraph* (the *entradilla* stays BODY), never a link, never when the `h1` is not the article's headline (site names as `h1`);
  - *machine summary*: blocks inside an element whose class / id / itemprop pairs `ai`/`ia` with `summary`/`resumen` are `non_body`
    with `module: ai_summary`.
- **Why a unit kind on the `title` surface and not a new surface:** the surfaces `primary` / `title` / `auxiliary` are shared with
  CO.RA.PAN and the denominator is defined on `primary`; the subtitle belongs to the headline apparatus, is never counted, and is
  separated from the title by `unit_kind`. No shared vocabulary and no count changes (§10).
- **Measured on the 4,759 pages:** BODY identical under 0.1.0 and 0.2.0 on **4,734**; the **25** others lost an AI summary that
  0.1.0 had put into the BODY (`co_el_espectador` 23, `cl_biobiochile` 2). Document version (text structure) changed on 2,971
  pages, because subtitles moved from `non_body` to the title surface. Subtitles on **2,953 pages** (3,038 blocks: 2,789 by the
  page's statement, 249 by markup alone) in **66 of 91 outlets**; 103 pages carry an AI-summary module. No body paragraph moved.

## 4. IPTC taxonomy and mapping

- **Vocabularies (checked 2026-11-15):** Media Topics, `dateReleased` 2026-09-30, 1,394 concepts (335 retired), labels in 13
  languages incl. `es`; Genre, `dateReleased` 2024-02-13, 58 concepts, `en-GB` only. Format: IPTC CV server JSON
  (`?format=json&lang=x-all`). Licence: **CC BY 4.0**, copyright IPTC; IPTC asks for credit. Retrieved once each; pinned as
  extracts (`config/taxonomy/iptc-mediatopic_2026-09-30.json`, `iptc-genre_2024-02-13.json`, schema `coprepan-iptc-extract/v1`)
  with the SHA-256 of the retrieved bytes (`16216d08…2166e8`, `8595892d…6b64f`), the release date and the attribution; built by
  `scripts/build_iptc_extract.py`, which refuses to overwrite an extract (a vocabulary update is a new file).
- **`section-map/1`** (`config/taxonomy/section-map_1.json`, the agent's, `NOT_VALIDATED`): written from the observed labels (682
  distinct folded values). 111 topical labels → Media Topic qcodes with the SKOS relation of the label to the concept
  (`closeMatch` or `broadMatch`; **no `exactMatch`**: a placement is never the same thing as a subject); 30 scope labels and 25
  country labels; 46 place labels of 23 outlets (`subnational`, for that outlet only); 24 genre-placement labels; 77 labels
  deliberately not mapped (31 `generic`, 39 `ambiguous`, 7 `outlet_or_template`), with notes (`Sociedad`, `Sucesos`, `Seguridad`,
  `El País`, country labels).
  The loader refuses a retired or unknown code, a non-SKOS relation, a label in two tables and a key given twice.
- **Rules of derivation:** the published value is kept verbatim with its basis; sources in precedence — JSON-LD `articleSection`,
  `article:section`, `parsely-section`, `section`, the breadcrumb (without home and article), the first URL path segment only when it
  is a label the map knows (a slug is not a section); a comma list longer than two entries is the section followed by tags (only its
  first entry is read — found at `sv_el_diario_de_hoy`, `hn_contracorriente`, `ve_correo_del_caroni`, where tags such as "China" or
  "San Salvador" would otherwise have been read as placements).
- **Coverage (measured):** `section-iptc/1` known on **1,655 of 4,759 pages (34.8 %)**; 1,959 pages name only a reach or a kind of
  text (scope or placement instead), 303 an ambiguous label (`undecided`), 276 an unmapped label, 218 only a generic or template
  label, 348 no section at all. Top branches: sport 566, politics 276, arts/culture/entertainment 256, economy 256, crime/law 123.
  Among the /3-accepted pages 36.3 %; per country from 8 % (`mx`, 50 pages) to 54 % (`cr`) — study record `core_candidate_coverage`.
- **Template and channel constants:** six outlets publish one label on ≥ 90 % of ≥ 10 pages; four are the channel the intake read
  (`ar_infobae` Mundo, `gt_emisoras_unidas` Deportes, `pe_la_republica` Economía, `cl_cooperativa` noticias — one URL segment), two
  are template suspects (`py_noticias_cde` ACTUALIDAD, `ve_eluniversal` EL UNIVERSAL — 10 and 17 different URL segments); both
  labels are in the map's not-mapped tables, so no topic is read from them.
- **Legacy comparison** (`section-map-v1` of the frozen legacy system, recomputed for comparison only): the legacy `hard_news`
  contains 745 pages whose section names only a reach (444 international, 301 national) and no topic; 790 pages are
  `other_unclear` there and have neither a topic nor a scope here. The legacy classes are kept as historical comparison; nothing is re-labelled.

## 5. Scope and published genre

- **`editorial-scope/1`:** known on 1,728 pages (international 675, national 722, subnational 224, local 94, regional 13); 2,683
  name no reach, 348 no section. A country label is national for the outlet's own registry country and international otherwise; a
  place label is `subnational` only for the outlet that publishes it (`subnational`: local or regional is not decided from the
  name). No place name in the text is read; the outlet's country stays registry metadata.
- **`genre-placement/1`** (a section that names a kind of text): 364 pages — opinion 278, reportage 21, editorial 16, obituary 16,
  letters 15, analysis 9, cartoon 4, essay 4, interview 1.
- **`genre-declared/1`** (the page's own declaration, with IPTC Genre): 126 pages — live coverage 70, opinion 50, analysis 2,
  background 2, editorial 1, review 1, satire 1. 263 pages state a genre value that declares nothing (`News`, `Noticia`, section URLs
  in the `genre` field at `ar_perfil`). **`ReportageNewsArticle` is not read as a genre**: schema.org defines it as ordinary news
  reporting, and it is a CMS default (`es_el_mundo` 77 of 81 pages, `pe_diariocorreo` 63 of 85).
- **Placement and declaration are different facts:** of the 278 pages in an opinion section, 27 declare opinion; 20 pages declare
  opinion outside any opinion section; one page in an opinion section declares analysis.

## 6. AI provenance — findings

- **Rule (`ai-disclosure/1`):** a statement is a block that *begins* with a disclosure form (subject + production verb + AI as
  means), at most 400 characters, or a caption crediting an AI image; a mention of AI in reporting has no such form. Values for the
  article text: `generated`, `assisted`, `translated`, `unclear`; components: `summary`, `audio`, `image`. Kept per statement:
  verbatim text, block index, role, kind, module, form, scope, tools named, whether a human review is stated. A statement about the
  article that an outlet prints on ≥ 80 % of ≥ 10 pages is a site notice and not applied (none was found); a module on most pages
  (summary, audio) stays a component of each page. **Orientation, IPTC NewsML-G2 2.36** (released 2026-11-11, read 2026-11-15):
  `contentMeta/aiInfo` with `system` (name, provider, version), `promptInfo`, `promptWriter`, and `hopHistory` actions that point at
  the parts an AI changed (`targetrefs`). The layer keeps the tool a statement names (≈ `system`) and the place and scope of the
  statement (≈ `targetrefs`); no page states a prompt or its writer, so those are not represented. **No stored page carries
  structured AI metadata** — searched in all 4,759 raw bodies for `aiInfo`, `digitalSourceType`, `trainedAlgorithmicMedia`,
  `compositeSynthetic`, `algorithmicMedia`, `isAiGenerated`: no hit. Every finding is a visible statement.
- **The 49 pages of the weekend's `machine_text`, read again from the raw evidence:** 22 articles **AI-assisted**
  (`ni_nicaragua_investiga` 12 "elaborado mediante la colaboración estratégica entre nuestro equipo editorial y herramientas de
  inteligencia artificial", `co_elpais` 7 "creado con ayuda de una inteligencia artificial … y curado por un periodista",
  `ar_la_nacion` 3 "producido por un equipo de LA NACION con la asistencia de la IA"); 1 **AI-generated** under human supervision
  (`ar_clarin`, "Nota generada con inteligencia artificial bajo supervisión y edición humana"); 25 articles with an **AI summary**
  (and at `co_el_espectador` an AI audio) **beside** the article (`co_el_espectador` 23, `cl_biobiochile` 2) — the summary had stood
  in the BODY under 0.1.0; 1 page (`do_diario_libre`) a report *about* an AI video, no disclosure. So the 49 did not all declare the
  same thing, and 26 of them declared nothing about the article text.
- **Found beyond the 49 (not caught by /2):** 10 **machine-translated** articles — BBC News Mundo partner copy "escrito originalmente
  en inglés y usamos una herramienta de inteligencia artificial para traducirlo; un periodista de la BBC revisó el texto"
  (`bo_el_deber` 2, `gt_prensa_libre` 3, `pa_la_prensa` 1) and `pr_el_nuevo_dia` 4 ("traducida … con una herramienta de inteligencia
  artificial y … revisada por un editor"); 1 more assisted (`ve_eldiario`, ChatGPT named, "Supervisado y verificado por el equipo
  editorial").
- **Totals:** article-level disclosures on 34 pages (generated 1, assisted 23, translated 10); components only on 239 (audio at
  `es_la_vanguardia` 74, `co_el_espectador` 66, `cl_the_clinic` 22, `es_el_mundo` 14, `es_el_pais` 4; summaries at
  `co_el_espectador` 66, `cl_biobiochile` 33, `cl_the_clinic` 4; images at 10 outlets); 4,486 pages `unknown`
  (no disclosure observed — not "without AI").
- **Wrong assignments found and repaired while measuring:** two headlines of related articles *about* AI images had been read as
  image credits (now only captions or non-body non-headings, credit closing the block); site-notice detection had swallowed the
  summary and audio modules of `co_el_espectador`, `cl_biobiochile`, `es_la_vanguardia` (now restricted to statements about the
  text); "bajo supervisión y edición humana" was not read as a human review (added).

## 7. Agency and syndication provenance — findings

- **Rule (`agency-credit/1`):** only credit positions — JSON-LD `author` / `creator` / `sourceOrganization` / `copyrightHolder` /
  `provider` / `creditText` / `dateline`, the author meta tags, a wire dateline opening the BODY ("Washington, 10 oct (EFE).-",
  "GULF BREEZE (AP).—", "EFE – …"), a byline block beginning *Por* / *Redacción*, a credit note ("Con información de EFE", "La
  información es de Agencia EFE"). A photo credit ("Foto: AFP", a caption ending "(EFE)") and an agency quoted in the text ("según
  informó la agencia EFE") are never read. 19 agencies in a closed list (EFE, AFP, Reuters, AP, dpa, Europa Press, ANSA, Xinhua,
  Prensa Latina, Sputnik, Bloomberg, IPS, ATON, Télam, Notimex, Colprensa, Andina, ACAN, and `unspecified` for "Agencias").
- **Findings:** credits on **407 pages (8.6 %)** — EFE 247, AFP 74, AP 47, unspecified 25, Europa Press 11, ATON 2, IPS 2, ACAN 2,
  Colprensa 1; positions: JSON-LD author 301, byline block 134, meta author 125/64, body dateline 20, edited note 15. `agency_use`:
  credit only 376, **joint credit** (agency and own newsroom / publisher name: "EFE / Redacción Primicias", "Redacción Web con AFP",
  "EFE/14ymedio") 16, **edited material declared** ("Con información de …", "Elaborado con información de EFE") 15. **No page says
  that it reproduces a wire text unchanged** — `verbatim_declared` is in the vocabulary and assigned by no rule.
- **Wrong assignment repaired:** places, dates and social-media handles beside an agency ("Madrid| EFE| @PanamaAmerica", "Por: EFE -
  Viernes 09 …", "Efe | @EFEnoticias") had been read as a second party (joint credit); now only a newsroom word or the page's own
  publisher name makes a joint credit. Remaining known miss: "Efe / Canarias Ahora" at `es_eldiario_es` (Canarias Ahora is the
  outlet's regional edition, not its publisher name) is `credit_only`.
- **Text reuse (`text-reuse/1`, a different kind of evidence):** 547 relations — 192 across outlets (`syndicated_copy_of`: 111
  identical, 81 one text contained in the other), 355 within one outlet (`duplicate_of`); 78 cross-outlet clusters. 147 of the 192
  cross-outlet pairs have an agency credit on at least one side, 45 have none — identical text without any credit (e.g. BBC partner
  copy, AFP/EFE stories printed without byline). An identical text is never excluded, and no agency is inferred from it. Known limit
  of the bottom-k sketch: a short text contained in a much longer one may be missed (comparable lengths are found).

## 8. Quality gate before / after

| | `content-quality/2` on `article_html/0.1.0` | `content-quality/3` on `article_html/0.2.0` |
|---|---:|---:|
| accepted | 4,017 | **4,066** |
| rejected | 742 | 693 |

- **Transitions:** 49 REJECT → ACCEPT, 0 ACCEPT → REJECT, all else unchanged. The 49 are exactly /2's `machine_text`-only rejections
  (§6); none is rejected for another reason under /3. No page was newly rejected by the new text structure; the 25 pages whose BODY
  lost an AI summary keep their decisions apart from `machine_text`.
- **Rules kept unchanged:** 150 words, function-word share 0.30, frame, paywall, sponsored (block-initial and URL), live coverage,
  not-editorial pages, completeness against the stated body, repetition, template body, duplicate within an outlet. Agency copy
  across outlets kept. First reasons under /3: too short 540, duplicate within outlet 38, not running prose 32, no body 23,
  incomplete 17, live 16, not editorial 8, template 6, sponsored 5, repetitive 5, paywall 3.
- **Accepted by provenance:** 34 AI-declared articles (1 generated, 23 assisted, 10 translated) and 391 agency-credited ones are
  among the 4,066 — CORE does not depend on either (test `test_core_quality_does_not_depend_on_provenance_or_placement`).
- The 97/100 of the weekend's control is historical evidence for /2 and is **not** quoted as a quality figure of /3.

## 9. Samples, validation results, errors

All readings below are **the agent's own reading of the raw evidence, not a human gold standard.**

| Sample (seeded, drawn across outlets) | Read | Correct |
|---|---:|---:|
| subtitles by the page's statement | 40 | 39 (one caption that `ar_clarin` states as its description) |
| subtitles by markup alone | 20 | 18 (a newsletter promotion at `co_el_espectador`, event opening hours at `cu_14ymedio`) |
| agency credits (agency named) | 40 | 40 |
| agency credits (kind of take-over) | 40 | 39 (`Efe / Canarias Ahora`) |
| article-level AI statements (all 8 distinct texts on 34 pages) | 8 | 8 |
| AI component notes (all 45 distinct texts on 323 page statements, after the repair of §6) | 45 | 45; before the repair two headlines about AI images had been read as image credits |

Errors found and repaired during the measurement: the subtitle rules first read a site name as the title and the region below it
(fixed by the headline check), a link to another article (link share), short kicker labels and dialogs (first marked block, 40
characters); the tag-list sections; the template genre type; the four provenance errors of §6 and §7. The full set of decisions is
in the study record; the compact **[human review sample](../intake/quality/phase3_review_2026-11-15.md)** (21 groups, 109 rows,
one page per outlet in a group) is the instrument for the operator's acceptance — nothing in it is filled in.

## 10. Consequences for CORE, release and cross-corpus

- **CORE:** the candidate CORE view is `content-quality/3` on `article_html/0.2.0`; it reads the text only. A study selects by the
  layers afterwards (IPTC branch, explicit genre, AI value, agency, text-reuse cluster, surface), and the study record reports the
  share of known metadata per country and outlet (`core_candidate_coverage`): among the 4,066 accepted pages section 36.3 %, scope
  38.7 %, genre placement 7.5 %, declared genre 1.1 %, article-level AI disclosure 0.8 %, agency credit 9.6 %. **A document with
  unknown AI or agency provenance is never called human-written or agency-free.**
- **Analysis contract (this repository's proposal `crosscorpus-analysis/v1`):** unit kind `subtitle` added (`editorial`, surface
  `title`, never counted); exported and validated end to end; the shared denominator is identical for a page with and without the
  subtitle separated (test). `syndicated_copy_of` / `duplicate_of` documented as text-reuse relations. The layers can be declared in
  a bundle of kind `provisional_export` (a `release` bundle carries validated layers only, contract §5.7).
- **Joint release contract `crosscorpus-release/v1` (canonical home CO.RA.PAN): unchanged.** Its written anchor kinds do not name
  `subtitle`; the native export (`release_export.py`) therefore stays on `extraction/1` and refuses an `extraction/2` record
  (fail-closed, tested). The joint revision is prepared as a **change request**, not made — the actual external gate.
- **Document identity:** unchanged; a new extraction version is a new document version where the text structure changed (2,971
  pages), the BODY digest is unchanged where the BODY is (4,734 pages).

## 11. Performance and integrity

| Step, on 4,759 stored pages (local, below-normal priority beside CO.RA.PAN's load) | Seconds | Per page |
|---|---:|---:|
| `article_html/0.1.0` | 32.5 | 6.8 ms |
| `article_html/0.2.0` | 50.2 | 10.5 ms |
| all six metadata layers (`enrichment.derive`) | 3.3 | 0.7 ms |
| text reuse over the whole set (incremental index) | 2.2 | 0.5 ms |
| content features under both extractors | 15.6 | 3.3 ms |

- **No new workspace scan in any path:** the enrichment needs one page and its extraction record; the derivation is a write-once
  layer keyed by a fingerprint over the body digest, the extraction payload digest, the mapping and taxonomy digests and the rule
  versions, reused while none changes (`enrichment.derive_stored`, tested); text reuse compares a new document only with the
  candidates its sketch shares. The intake, canary and incremental-check code is not touched; no publisher request is needed for
  any metadata (everything is read from stored bytes).
- **Integrity:** no stored artefact rewritten; the raw evidence read only; `extraction/1` records, `content-quality/2` and the CPD-0038
  history unchanged; CPD-0038's record received only its dated status line.

## 12. Technical tests

- New: `tests/test_phase3_metadata.py`, 76 tests, in suite `foundation_contract` — subtitle by statement and by markup, entradilla
  kept, link / caption / site-name title refused, AI-summary module out of the BODY, determinism, schema refusals; IPTC pins and
  digest refusal, no retired or invented code, no `exactMatch`, duplicate keys refused, tag lists; section, scope (own vs foreign
  country, outlet place labels, no place names from text), placement vs declaration, generic types; every AI form, tools and human
  review, mentions not read, components, captions vs headlines, site notices; agency credit, edited, joint vs place/handle, dateline,
  quoted source and photo credit not read; text reuse across and within outlets, incremental index; /3 keeps every other rule and
  drops `machine_text`, /2 unchanged; CORE independent of provenance; write-once enrichment reuse; the subtitle unit in the analysis
  export with an unchanged denominator; the joint release export unchanged and fail-closed.
- Affected modules (extraction, extractor candidates, content quality, analysis and release contracts, integrity invariants): 497
  passed, 7 skipped (optional pinned candidate tools not installed).
- **Full suite on the final code state** (branch, idle priority beside CO.RA.PAN): **2,079 passed, 15 skipped** (the 15 known skips:
  optional candidate tools, symbolic links, applied proposals and rebuilt inventories), 692 s; no tracked file modified. The
  repository-contract and phase-3 modules were run again after the last documentation edits: 170 passed.

## 13. Activation status of every layer

| Component | Lifecycle / validation | Activation |
|---|---|---|
| `extraction/2`, `article_html/0.2.0` | `CANDIDATE`, `NOT_VALIDATED` | `INACTIVE` (not in `extraction.EXTRACTORS`; `require_active` refuses) |
| `content-quality/3` | `CANDIDATE` (preferred), `NOT_VALIDATED` | not binding for admission or release |
| `section-map/1`, IPTC extracts | `NOT_VALIDATED` | study layer only |
| `publisher-metadata/1`, `section-iptc/1`, `editorial-scope/1`, `genre-placement/1`, `genre-declared/1`, `ai-disclosure/1`, `agency-credit/1`, `text-reuse/1` | `NOT_VALIDATED` | study layers; none stored for corpus material; none a release field |
| stage *enrichment* (`docs/STATUS.md`) | `PARTIAL` / `NOT_VALIDATED` | `INACTIVE` |

## 14. Open scientific approvals (the operator's)

1. Adopt **`article_html/0.2.0`** as the corpus extractor (needs the gold sample, CPD-0007 §7) and **`content-quality/3`** as the
   binding CORE standard — on the human review sample.
2. Accept **`section-map/1`** (the mapping review: in particular the `broadMatch` / `closeMatch` choices, the not-mapped labels, and
   `subnational` as a scope value), the scope and genre rules, and the two provenance rules as release fields.
3. The **joint** revision of `crosscorpus-release/v1` naming `subtitle` (with CO.RA.PAN).
4. Unchanged from before: whether titles and subtitles are annotated in the first release; whether complete briefs under 150 words
   are wanted.

**One preferred solution each:** text surfaces — `subtitle` unit kind on the `title` surface; IPTC — `section-map/1` with SKOS
relations on the pinned 2026-09-30 extract; genre — the page's declaration with IPTC Genre, the section only as a placement; AI —
`ai-disclosure/1`; agency — `agency-credit/1` plus `text-reuse/1` as separate evidence; gate — `content-quality/3`; extractor —
`article_html/0.2.0`.

## 15. Git commits and push status

| Fact | State |
|---|---|
| Changes committed | branch `phase3/text-surfaces-provenance`: `31bf09c` (code, config, tests), `dec2579` (CPD-0039, documentation, evidence), the commit of this report |
| Merged into `main` | yes, fast-forward (main had not moved since `4132fb7`) |
| Pushed | `main` and the branch to `origin`, no force |
| Report published on `main` | with `scripts/publish_run_report.py publish --status PASS` (documentation-only commit, `docs/agent-runs/INDEX.md`) |
| Worktree removed | last act, with `scripts/worktree_closure.py remove` |

Integration check before the merge: the Monday programme is not affected — the canary's baseline is frozen by its own `start` at
run time, its component versions (baseline extractor, admission rule set, fetcher, planner …) are unchanged by this run, its plan
and authorisation are untouched, and the full suite (its gate) passes. Working tree at the end: every change committed; the local
page cache, the derived rows and the scratch probes under `%LOCALAPPDATA%\Temp\coprepan-phase3` (outside the repository, on `C:`)
deleted after closure; the harness keeps its own task logs on `D:\ClaudeTmp` (session infrastructure, no corpus data written
there by this run).

## 16. Next step

**One recommended next run:** the operator's review of the [review sample](../intake/quality/phase3_review_2026-11-15.md)
(109 rows, one column to fill), then — on its result — a decision run that adopts or corrects `content-quality/3`,
`article_html/0.2.0` and `section-map/1`. Independently and on a weekday: Monday's programme as planned (backup check,
`preserve-deferred`, the `/2` canary), which this run did not touch.
