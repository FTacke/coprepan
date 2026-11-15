# CPD-0039 — Text surfaces, IPTC section mapping, declared AI and agency provenance, and CORE quality independent of origin

| Field | Value |
|---|---|
| Date | 2026-11-15 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| What is active | the operator's scientific decisions (§1) are in force. **Every component built for them is a `CANDIDATE` / `NOT_VALIDATED` layer and binds nothing**: `extraction/2` with `article_html/0.2.0`, `content-quality/3`, `section-map/1` and the six metadata layers. Their activation is the operator's, after the human review (*Not decided here*) |
| Decided by | the operator's brief of 2026-11-15 ("CO.PRE.PAN_v3 – Phase-3-Integration", §1, §3–§11: the scientific decisions are authorised there); the rules and mappings are the commissioned agent's |
| Kind | architecture · scientific policy |
| Execution | `extraction.py` (`extraction/2`), `extraction_article.py` (`article_html/0.2.0`), `publisher_metadata.py`, `iptc.py`, `editorial_metadata.py`, `provenance.py`, `text_reuse.py`, `enrichment.py`, `content_quality.py` (`content-quality/3`), `analysis_contract.py` (unit kind `subtitle`); `config/taxonomy/`; `scripts/build_iptc_extract.py`, `scripts/study_phase3_metadata.py`; `tests/test_phase3_metadata.py` |
| Builds on / amends / supersedes | builds on CPD-0005 (extraction contract), CPD-0007 (lifecycle), CPD-0008 (layer architecture, analysis contract), CPD-0011 (export object); **amends CPD-0038**: its open question 2 is decided (AI-declared texts belong in the corpus) and the `machine_text` rule is withdrawn in `content-quality/3`; `content-quality/2` and its controls stay unchanged as history |
| Does not change | `extraction/1`, `baseline_html/0.1.0`, `article_html/0.1.0` and every stored record; `content-quality/2`; `admission-technical/1`; the pinned joint release contract `crosscorpus-release/v1` (the subtitle is a change *request* to it, §5); any release view or gate; the advertising rules (`sponsored` unchanged) |
| Run report | [`2026-11-15 phase-3 integration`](../agent-runs/2026-11-15_coprepan-phase3-text-surfaces-iptc-provenance.md) |
| Evidence | [study record](../intake/quality/phase3_metadata_study_2026-11-15.json) (4,759 stored item pages, 91 outlets, 20 countries), [human review sample](../intake/quality/phase3_review_2026-11-15.md) |

## Context

CPD-0038 left the AI question open and excluded AI-declared texts; the operator decided it on 2026-11-15. The same brief fixes the
target architecture of the text layers: CORE is the quality-assured Spanish-language press text; section, scope, genre, declared AI
use and agency origin are documented, never conditions of CORE membership. The extraction contract kept only `title` / `body` /
`non_body`; the weekend pages showed subtitles on two thirds of them and machine summaries placed inside the article container.

## Decision

### 1. Scientific decisions (the operator's)

1. **CORE = general text quality.** A complete, coherent, usable press text is CORE whatever its section, scope, genre, opinion
   orientation, metadata completeness, declared AI use or agency origin. AI-generated, AI-assisted and agency texts are wanted.
2. **Unknown is not negative.** Missing metadata is a value state (`unknown`, `undecided`); no AI disclosure is not "made without
   AI", no agency credit is not "own reporting", no section is not "general news".
3. **IPTC Media Topics** is the reference taxonomy for editorial sections; **IPTC Genre** for declared genres.
4. **No mandatory LLM classification** of genre, narrativity or opinion in the ingest; such properties are later study layers.

### 2. Text surfaces (`extraction/2`, `article_html/0.2.0`)

`extraction/2` = `extraction/1` plus the block kind **`subtitle`** (role `title`, a `basis`: `stated_by_page` or `subtitle_markup`)
and an optional block field **`module`** (closed vocabulary: `ai_summary`; such a block is never BODY). The digests are defined as
before. `article_html/0.2.0` keeps 0.1.0's body rule and adds two structural rules: a block between the title and the first body
block becomes the subtitle when the page states its text as the article's `alternativeHeadline` / `description` (JSON-LD,
`og:`/`twitter:description`) or its element carries a subtitle mark (first marked block only, at least 40 characters); a body
*paragraph* is never moved (the *entradilla* stays BODY), a leading body *heading* only on the page's own statement; no subtitle is
read when the `h1` is not the article's headline or the block is a link. Blocks inside an element marked as an AI summary are
`non_body` with `module: ai_summary`. **Why a unit kind on the existing `title` surface and not a new surface:** the three surfaces
are shared with CO.RA.PAN and the denominator is defined on `primary`; a subtitle belongs to the headline apparatus, is never
counted, and a study separates it from the title by `unit_kind` — no shared vocabulary changes, no count moves.

### 3. Metadata layers (each `NOT_VALIDATED`, write-once, keyed by fingerprint)

| Layer | Value | Evidence kind |
|---|---|---|
| `publisher-metadata/1` | the page's statements verbatim (JSON-LD article types, sections, genre, authors, organisations, credit, dateline; meta section/author; breadcrumb; URL path) | publisher statement |
| `section-iptc/1` | IPTC Media Topic qcodes of the published *placement* under `section-map/1`, with SKOS relation (`closeMatch` / `broadMatch`, never `exactMatch`) | derivation |
| `editorial-scope/1` | `local` · `regional` · `subnational` · `national` · `international`, from sections that name a reach or a place (a country label against the outlet's registry country) | derivation |
| `genre-placement/1` | the kind of text a *section* names (`opinion`, `editorial`, `letters`, `analysis`, …) — a placement, not a property of the text | derivation |
| `genre-declared/1` | the genre the page declares (schema.org NewsArticle subtypes, `genre`) with its IPTC Genre code | derivation |
| `ai-disclosure/1` | the article text `generated` · `assisted` · `translated` · `unclear`; components `summary` · `audio` · `image`; each with the verbatim statement, place, tool named, human review stated | derivation |
| `agency-credit/1` | credited agencies (closed vocabulary) and `agency_use`: `edited_declared` · `joint_credit` · `credit_only` (`verbatim_declared` reserved: no page states it) | derivation |
| `text-reuse/1` | relations `syndicated_copy_of` (across outlets) / `duplicate_of` (one outlet), 8-word-shingle containment ≥ 0.9, target = the earlier document, "not a finding of origin" | document relation |

The taxonomy is pinned as an extract with the SHA-256 of the retrieved bytes (Media Topics released 2026-09-30, source
`16216d08…2166e8`; Genre released 2024-02-13, `8595892d…6b64f`) and carries IPTC's CC BY 4.0 attribution; a taxonomy update is a
new extract and a new mapping version, never an edit.

### 4. `content-quality/3`

`content-quality/2` with the `machine_text` rejection **withdrawn** (the feature stays as evidence) and read on the BODY of
`article_html/0.2.0`. Every other rule and threshold is /2's; the 150-word minimum is kept. A page that offers only a summary still
fails — on length or completeness, never on its origin. The gate reads no metadata layer.

### 5. Release and cross-corpus

The analysis contract proposal (this repository's `crosscorpus-analysis/v1`) carries the unit kind `subtitle` (`editorial`, surface
`title`, never counted). The **joint** release contract is unchanged: its written anchor kinds lack `subtitle`, so the native export
stays on `extraction/1` until a joint revision adds it — a change request, not an edit (run report §10).

## How it was chosen and measured (2026-11-15, 4,759 stored 2xx item pages; agent readings are not gold)

- **BODY unchanged** on 4,734 pages between 0.1.0 and 0.2.0; the 25 changes are all AI-summary modules that 0.1.0 had put into the
  BODY (`co_el_espectador` 23, `cl_biobiochile` 2). Subtitles on 2,953 pages in 66 of 91 outlets; agent reading 39/40 correct by
  the page's statement, 18/20 by markup alone.
- **Quality:** /2 on 0.1.0 accepted 4,017, /3 on 0.2.0 accepts 4,066; the 49 changes are exactly /2's `machine_text`-only
  rejections; no page is newly rejected.
- **The 49 weekend AI pages read again:** 22 articles AI-assisted (`ni_nicaragua_investiga` 12, `co_elpais` 7, `ar_la_nacion` 3),
  1 AI-generated under human supervision (`ar_clarin`), 25 an article with an AI summary or audio module beside it, 1 a text *about*
  an AI video (no disclosure). Not caught by /2 at all: 10 machine-translated articles (BBC Mundo partner copy at `bo_el_deber`,
  `gt_prensa_libre`, `pa_la_prensa`; `pr_el_nuevo_dia`).
- **Coverage among the /3-accepted pages:** section → IPTC 36.3 %, scope 38.7 %, genre placement 7.5 %, declared genre 1.1 %,
  article-level AI disclosure 0.8 %, agency credit 9.6 % (per country in the study record). Agency credits: agent reading 40/40
  agencies, 39/40 kinds of take-over.
- **Cost:** 0.2.0 extracts in 10.5 ms per page against 6.8 ms (0.1.0); all six metadata layers 0.7 ms per page; text reuse over all
  4,759 pages 2.2 s. No workspace scan and no publisher request.

## Alternatives considered

- **A new surface `subtitle`** — would change the vocabulary shared with CO.RA.PAN for a distinction a unit kind already carries.
- **The JSON-LD `description` as the subtitle text** — often the first body paragraph or a teaser; used only as evidence for a block.
- **An LLM or a topic model for sections, genre or provenance** — against the brief; not needed for the publisher statements.
- **Mapping every published label** — 682 distinct labels, many generic, brand-like or ambiguous; forced completeness would invent
  equivalences. Unmapped stays `unknown` with its reason.
- **`ReportageNewsArticle` as a declared genre** — schema.org defines it as ordinary news reporting and the pages show it as a CMS
  default; read as generic.
- **Excluding agency copies or identical texts** — they are publication events of their own; counting is the study's selection.

## Not decided here (the operator's decision)

1. Whether `article_html/0.2.0` becomes the corpus extractor (`VALIDATED` needs a gold sample, CPD-0007 §7) and `content-quality/3`
   the binding CORE standard — after the human review sample.
2. Whether `section-map/1`, the scope and genre rules and the two provenance rules are validated as release fields (each needs its
   review; until then they are study layers only).
3. The joint revision of `crosscorpus-release/v1` that names the unit kind `subtitle` (a joint act with CO.RA.PAN).
4. Whether subtitles and titles are annotated in the first release (PHASE3 architecture §10), and whether complete briefs under
   150 words are wanted (CPD-0038 open question 3, unchanged).
