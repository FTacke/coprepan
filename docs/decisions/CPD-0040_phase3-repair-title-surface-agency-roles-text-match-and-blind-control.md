# CPD-0040 — Phase-3 repair: the title surface, the agency's role apart from the declared use, exact against near-identical text, and a frozen blind control

| Field | Value |
|---|---|
| Date | 2026-11-15 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| What is active | the repaired rules as **the preferred candidates** beside the versions they repair: `article_html/0.3.0`, `agency-credit/2` (in `editorial-metadata/2`), `text-reuse/2`. **None is validated or activated**; nothing binds a release, an admission or a stored record. Their activation, and that of `content-quality/3` and `section-map/1`, is the operator's after the blind control (*Not decided here*) |
| Decided by | the operator's brief of 2026-11-15 ("CO.PRE.PAN_v3 – Gezielter Phase-3-Repair und wissenschaftliche Blindvalidierung": the three repairs and their validation are authorised; the scientific decisions of CPD-0039 §1 are not reopened); the rules are the commissioned agent's |
| Kind | scientific method · extraction · provenance |
| Execution | `extraction_article.py` (`article_html/0.3.0`, `PREFERRED`), `provenance.py` (`agency-credit/2`), `enrichment.py` (`editorial-metadata/2`, `PREFERRED`), `text_reuse.py` (`text-reuse/2`); `scripts/study_phase3_repair.py`; `tests/test_phase3_repair.py` |
| Builds on / amends / supersedes | builds on CPD-0039 and keeps its evidence; **partially supersedes CPD-0039** as the preferred candidate for three components: `article_html/0.2.0` → `0.3.0`, `agency-credit/1` → `/2`, `text-reuse/1` → `/2`. The earlier versions stay in the code unchanged, as history and for their records |
| Does not change | `extraction/2` (no schema change), `article_html/0.1.0` / `0.2.0`, every stored record; `content-quality/3` and its 150-word minimum (decisions measured identical, §4); `section-map/1`, the IPTC extracts, `editorial-scope/1`, `genre-placement/1`, `genre-declared/1`, `ai-disclosure/1` (records identical on every page, §4); the relation kinds `duplicate_of` / `syndicated_copy_of` and the joint contracts (the match class is a [change request](../crosscorpus/RELATION_MATCH_CLASS_CHANGE_REQUEST_2026-11-15.md)); the intake controller, storage and preservation contracts |
| Run report | [`2026-11-15 phase-3 repair`](../agent-runs/2026-11-15_coprepan-phase3-repair-blind-control.md) |
| Evidence | [study record](../intake/quality/phase3_repair_study_2026-11-15.json) (the 4,759 stored item pages of CPD-0039); [blind control](../intake/quality/phase3_blind_control_2026-11-15/manifest.json) (frozen before review) |

## Context

The operator's reading of the CPD-0039 review sample found three wrong title surfaces (an event field "Lugar: Teatro Martí, …" and
a newsletter promotion as subtitles, the newspaper's name "La Nación" as the title of sports articles), an agency label stronger
than its evidence ("Con información de EFE" as `edited_declared`), and a text-reuse class (`identical`) that did not mean the same
text. The review sample showed the machine's findings, so it diagnoses; it cannot be the acceptance test.

## Decision

### 1. `article_html/0.3.0` (record schema `extraction/2`, unchanged)

0.2.0's BODY rule and machine-summary modules; only the title surface changes.

- **Title.** The first `h1` that is the headline the page states (JSON-LD `headline`, `og:title`, `twitter:title`, `<title>`:
  equal, contained, or one separator-delimited part) — so a logo or edition `h1` before the article's own gives way. Where no
  `h1` is a stated headline, the first `h1` stays (the printed headline often differs from the search title), unless it is the
  site's branding (`og:site_name`, `application-name`, JSON-LD publisher, the rest of a stated title once a stated headline is
  taken out) or a section the page states (`articleSection`, `article:section`, a breadcrumb item but the last). Then there is
  **no title block**: the title is unknown on the text surface, `metadata.title` keeps the page's statement with its basis. An
  `h1` that is not the title is a `heading` and never BODY.
- **Subtitle.** 0.2.0's two paths, with five exclusions: a block inside a newsletter / subscription / promotion module (not the
  element around the title); a field of a data sheet (label and colon, beside a block of the same shape); caption, credit and
  gallery marks on both paths; one subtitle per stated text and no stated "description" that is the headline itself; by markup
  alone only within `MAX_MARKED_GAP` = 12 blocks of the title (measured: all marked subtitles of 0.2.0 within 9, the 13 beyond 30
  newsletter boxes and teasers).

### 2. `agency-credit/2` (in `editorial-metadata/2`)

Two properties instead of one: **`agency_roles`** — `credited` (author or source of the published text: author fields, byline,
wire dateline, JSON-LD source / provider / copyright / credit), `co_credited` (with the outlet's newsroom or publisher, named
verbatim in `credited_with`; a place, a date, a handle or the agency's own desk — "Redacción EFE" — is not a party),
`material_source` ("Con información de EFE", "Con datos de", "La información es de") — and **`use_declared`** — `verbatim_declared`,
`edited_declared`, `material_used_declared`, `not_stated`, set only by an explicit statement. Unknown has two reasons:
`agency_named_as_quoted_source_only` and `no_agency_credit_observed`. Credits are kept verbatim with their position; several
agencies are kept. `agency-credit/1` and `editorial-metadata/1` are unchanged; `/2` is a new artifact under a new fingerprint.

### 3. `text-reuse/2`

/1's candidates, threshold and relation kinds, with a versioned **`text_match`**: `exact` (the canonical BODY text is the same
string — NFC, invisible format characters removed, white space incl. paragraph breaks folded; case, punctuation, quotation marks,
digits and wording kept), `near_identical` (not exact, each text ≥ 0.9 of its 8-word shingles in the other), `contained` (only the
shorter one is). The measured values travel with the relation (both containments, shingle and word counts, shared shingles,
bag-of-words differences). Exactness is never read from containment; direction is order of appearance in this corpus, never
origin or authorship; no relation excludes a document.

### 4. What the repair changes and does not change (measured, 4,759 stored 2xx item pages, offline)

- **BODY identical on all 4,759 pages** (digest), machine-summary modules identical; extracted-text digest changed on 294 pages
  (title surface). Titles changed on 246 pages: another `h1` on 162 (`py_la_nacion` 81, `ec_primicias` 78, `py_noticias_cde` 3),
  no title block on 84 (`bo_opinion` 52 section labels, `cu_juventud_rebelde` 31 site name, `hn_el_heraldo` 1). Subtitle surface
  changed on 121 pages: 73 gained (`ec_primicias`, now that its title is found), 48 lost a block (event fields 15, newsletter
  boxes 9, repeats of a stated text — captions, galleries, share boxes, paywalled copies — and marked blocks far from the title
  24); pages with a subtitle 2,953 → 3,004.
- **CORE decisions and reasons identical on every page** under `content-quality/3` (4,066 accepted, 693 rejected); every feature
  but the title text is identical.
- **Every other layer record identical on every page**: `section-iptc/1`, `editorial-scope/1`, `genre-placement/1`,
  `genre-declared/1`, `ai-disclosure/1`.
- **Agency:** the same 407 pages and the same agencies on each. Roles per page: `credited` 368, `co_credited` 21 (the 16 former
  `joint_credit` and 5 bylines /1 read as credit only — "Redacción Web con AFP", "Redacción / EFE"), `credited`+`co_credited` 1,
  `material_source` 12, `credited`+`material_source` 5. `use_declared`: `material_used_declared` 17 (the 15 former
  `edited_declared` and 2 credit notes), `not_stated` 390; no page states editing or a verbatim take-over. Unknown: 66 pages name
  an agency only as a quoted source, 4,286 show no credit.
- **Text reuse:** the same 547 pairs. Across outlets (192): `exact` 9, `near_identical` 102, `contained` 81 — /1's 111
  "identical" pairs are 9 exact texts and 102 near-identical ones. Within one outlet (355): `exact` 347 (30 of them two fetches
  of one address), `near_identical` 3, `contained` 5. No pair rests on outlet furniture (largest share of shared shingles that
  recur in unrelated documents of one outlet: 0.36).
- **Cost per page:** 0.3.0 10.5 ms against 0.2.0 10.4 ms; `editorial-metadata/2` 0.86 ms against `/1` 0.67 ms; `text-reuse/2`
  3.5 s for the whole population against 2.2 s.

### 5. The blind control (frozen before any human verdict)

70 cases (253 questions) from the 4,626 pages left after excluding the 2026-11-15 review sample and every page this run opened
one by one: a **random component** of 24 (systematic sample with random start over pages ordered by country, outlet and a seeded
digest; inclusion probability 24 / 4,626 each) and **46 targeted cases** in 15 strata (title, subtitle, AI, agency, CORE
rejection, IPTC, and 8 text-reuse pairs of the three classes), drawn by seeded digest with one page per outlet. The reading
sheet shows only page evidence; the machine's answers, strata and evidence are in a separate key whose SHA-256 is in the
manifest; `merge` refuses a changed key and reports the random and the targeted component apart.

## How it was chosen

The three failures were opened on the stored raw pages; each repair is the general form of the cause (a logo `h1` before the
article's, a description that concatenates event fields, a header region that spans the page when the body is missing). Every
rule was then run over the whole population against its predecessor; every removed subtitle, every former `edited_declared` and
`joint_credit` credit, every new co-credit and sample pages of every title-change pattern were read (the agent's reading, not gold). Outlet-specific rules were not needed.

## Alternatives considered

- **The metadata headline as a title block** when no `h1` is the headline — a reconstruction; the text surface holds printed
  text only, the statement stays in `metadata.title`.
- **Dropping every description whose text is longer than the block** — Clarín, Cooperativa and others state longer descriptions
  for real subtitles (201 such subtitles under 0.2.0).
- **A lexical list of service labels** ("Lugar", "Horario") — the field-sheet shape (label and colon, repeated) is the general form.
- **`identical` redefined in place** — would change the meaning of stored /1 relations; a new version with a new attribute.
- **Exactness from containment = 1.0** — misses case, punctuation and wording differences (10 pairs that are not exact have the
  same bag of lower-cased words).
- **Changing the joint relation vocabulary** — not this repository's to change; the class travels in `basis` and as an attribute.

## Not decided here (the operator's decision)

1. After the blind control: whether `article_html/0.3.0` becomes the corpus extractor and `content-quality/3` the binding CORE
   standard (CPD-0007 §7, CPD-0039 *Not decided here* 1).
2. Whether `section-map/1`, `agency-credit/2`, `ai-disclosure/1` and `text-reuse/2` are validated as release fields.
3. The joint change requests: the unit kind `subtitle` (2026-11-15) and the relation match class (this run) — joint acts with
   CO.RA.PAN.
4. Unchanged from CPD-0039: titles and subtitles in the first release's annotation; complete briefs under 150 words.
