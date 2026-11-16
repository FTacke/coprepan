# CPD-0042 — The BODY control evaluated: the operator's verdicts, three bounded repairs, and what a release still needs

| Field | Value |
|---|---|
| Date | 2026-11-16 |
| Status | `PARTIALLY_SUPERSEDED` |
| What is active | the preferred candidates `article_html/0.4.1` (`extraction/3`, the pinned `body-templates/1`), `content-quality/4` (on `content-features/2`) and `body-quality/2`. **None is validated or activated**; nothing binds a release, an admission or a stored record. Scientific acceptance and activation are the operator's (*Not decided here*) |
| Decided by | the operator's brief of 2026-11-15 ("CO.PRE.PAN_v3 – Operator-Review übernehmen, BODY-Blindkontrolle auswerten und Phase 3 entscheidungsreif abschließen": the operator's verdicts confirmed; clearly evidenced, technically bounded defects may be repaired as new versions; no new broad optimisation); the repairs are the commissioned agent's |
| Kind | extraction · scientific method · quality gate |
| Execution | `extraction_body.py` (`article_html/0.4.1`), `content_quality.py` (`content-features/2`, `content-quality/4`), `body_quality.py` (`body-quality/2`); `scripts/study_body_quality.py` (`merge` v2, `repair`); `tests/test_body_control_repairs.py`, `tests/test_body_quality.py` |
| Builds on / amends / supersedes | builds on CPD-0041; **partially supersedes CPD-0041** as the preferred extractor (`0.4.0` → `0.4.1`) and contamination status (`body-quality/1` → `/2`), and **CPD-0039** as the preferred CORE gate (`content-quality/3` → `/4`). Every earlier version stays in the code unchanged |
| Does not change | `article_html/0.1.0`–`0.4.0`, `extraction/1`–`/3`, `body-templates/1`, `content-quality/1`–`/3` (their thresholds, their reasons), `body-quality/1`, the 150-word minimum, every metadata layer (`editorial-metadata/3`), `text-reuse/2`; the frozen control's manifest, blank form, sheet and key; the joint contracts |
| Run report | [`2026-11-16 BODY control review`](../agent-runs/2026-11-16_coprepan-body-control-review.md) |
| Evidence | [filled form](../intake/quality/body_quality_control_2026-11-15/verdicts_filled_2026-11-15.csv) (committed before the key was opened, `81749ba`), [control result](../intake/quality/body_quality_control_2026-11-15/result_2026-11-15.json), [repairs on every stored page](../intake/quality/body_control_repairs_2026-11-15.json) |

*Status line 2026-11-16 (later the same day):* **partially superseded by [CPD-0043](CPD-0043_final-body-candidate-and-local-reviewer.md)**
(was `ACTIVE_WITH_VALIDATION_DEBT`) as the preferred extractor: `article_html/0.4.2` replaces `0.4.1`. `content-quality/4` and
`body-quality/2` stay the preferred candidates; the open questions 2–4 are measured there. Nothing here is rewritten.

## Context

The operator read the frozen BODY control of 2026-11-15 (45 cases, 135 questions) and confirmed the joint verdicts in the brief.
The control was to show whether `article_html/0.4.0` removes foreign material without deleting article text, whether text is
missing, and whether CORE decides right on the new BODY.

## Decision

### 1. The verdicts, kept apart by basis, before the key

The filled working copy of the frozen form carries, per question, the `answer`, its `basis` and, verbatim, the operator's
`operator_answer` and `operator_open` (the blocks the operator left "to check"):

| Basis | FOREIGN | MISSING | CORE | All |
|---|---|---|---|---|
| `OPERATOR_CONFIRMED` (human gold) | 42 | 0 | 41 | 83 |
| `TECHNICALLY_VERIFIED` (from the stored page) | 1 | 43 | 2 | 46 |
| `AGENT_ASSESSED` | 2 | 2 | 2 | 6 |
| `UNRESOLVED` | 0 | 0 | 0 | 0 |

MISSING was checked for every case against the stored page (every paragraph, heading and quote of the markup and the JSON-LD
`articleBody` against the sheet blocks); a standfirst outside the blocks is title surface, not missing BODY. The CORE word
counts use the gate's own word definition (letters only). The form was committed and pushed (`81749ba`) before the key was
read; `merge` (result schema `/2`) scores the operator's gold alone (open blocks left out) and all answers apart, random and
targeted apart.

### 2. What the frozen control shows (predictions fixed before review)

On the operator's gold:

- **`article_html/0.4.0` deleted no article text**: 0 false deletions in both components; correct removals 45 blocks (201
  words) random, 539 (1,735) targeted. `0.3.0` missed article text that 0.4.0 included: 1 block (38 words) random, 38 blocks
  (1,176 words) in 9 targeted cases.
- **Residual contamination** under 0.4.0: 15 blocks, 219 words in 6 of 16 random cases (2.2 % of their BODY words); 18
  blocks, 153 words in 8 targeted cases. Under 0.3.0: 59 blocks, 329 words random; 556 blocks, 1,886 words targeted.
- **CORE** (`content-quality/3`): random 15 of 16 on both versions (`B42`); targeted 21 of 25 on 0.4.0 — two `cl_biobiochile`
  articles rejected as incomplete (`B20`, `B42` in the random part), two live blogs accepted (`B28`, `B43`), one re-fetched
  duplicate (`B40`, rightly counted once).
- **MISSING** (no gold): an opening paragraph lost in both versions in `B03` (random) and `B39`; three short items of a
  column (`B02`); live-entry headings (`B28`, `B43`); text only in the JSON-LD (`B08`, `B27`, `ar_pagina12`).

### 3. The repairs (new versions; the defects are measured, not inferred from the sample)

- **`article_html/0.4.1`** = 0.4.0 with two corrections of the inclusions:
  1. **no copy**: a paragraph is never included when its text, a trailing ellipsis set aside, is the *beginning* of a block
     the BODY already holds (the hidden paywall teaser cut off with "…" that made `B37` begin twice). Only the beginning,
     because the article's own paragraph may stand word for word in an embed the rules do not see.
  2. **teaser cards are not a list**: an `<article>` holding other `<article>` elements gives up the lead only when those
     hold at least 30 % of its text. A "Noticia relacionada" card inside the article cost `es_abc` its opening paragraph
     (`B03`).
- **`content-quality/4`** = `/3` with two measurements corrected, on `content-features/2` (`/1`'s features unchanged, two
  added):
  1. `incomplete_against_stated_body` compares with the stated articleBody **as text** (`stated_body_text_characters`:
     markup, scripts and embedded social posts out). `cl_biobiochile` states its body as HTML, about twice its text in
     characters; complete articles failed.
  2. `live_coverage` also when the page **declares itself a schema.org `LiveBlogPosting`** (top level or `@graph`), unless it
     is a static article in live-blog markup: at least two `liveBlogUpdate` items, all at one time (`cr_la_nacion`). The
     time-stamp share alone missed live blogs whose times are not in the BODY, and 0.4.0's stated-body inclusions diluted it.
- **`body-quality/2`** = `/1` with `incomplete` read against the stated text as `/4` reads it.

No social post goes back into the BODY; the 150-word minimum, the thresholds and the reasons are `/3`'s.

### 4. Measured on the 4,759 stored pages (offline)

- `0.4.1` against `0.4.0`: BODY changed on 45 pages — 21 copies left out (1,160 words; 18 `co_el_espectador` teasers, 3
  `bo_opinion` echoes), 24 opening paragraphs in (2,297 words; `es_abc` 17, `co_el_nuevo_siglo` 5, `es_el_correo` 1,
  `pr_metro_puerto_rico` 1). Every left-out block is the beginning of a kept block; every added block was read: an opening
  paragraph of the article, none from a list page. No metadata layer changed; text reuse 293 relations, unchanged.
  11.4 ms per page.
- CORE, `content-quality/3` on 0.4.0 → `/4` on 0.4.1: **4,067 → 4,074 accepted**. In: 19 (17 `cl_biobiochile`, whose BODY
  covers 76–96 % of the stated text; 2 `co_el_nuevo_siglo` with their opening back). Out: 12 (11 declared live blogs —
  `es_abc` 4, `ar_la_nacion` 2, `ec_primicias` 2, `co_elpais`, `cr_la_nacion`, `uy_el_observador` — each read; 1
  `bo_opinion` page that reached 150 words only through its duplicated paragraph: 151 → 123).
- A stated articleBody with markup: 690 pages of 30 outlets; incomplete among them 35 → 14 (the 14 left: the BODY covers 0–11
  % of the stated text — JS-rendered pages).
- `body-quality/2`: `incomplete` 27 → 10; `not_article` 159 and `residual_suspect` 332 unchanged.
- An opening paragraph missed (the agent's heuristic, not gold: on pages stating an articleBody of at least 1,000 text
  characters, the BODY covers at least 60 % of its 5-word shingles but under 20 % of its first 30, title surface counted):
  33 of 2,081 pages under 0.4.1 without the card rule, **14 with it** (`uy_el_observador` 6 — no `<article>` element —,
  `ec_primicias` 2, `es_abc` 2, `pr_el_nuevo_dia` 2, `co_semana`, `es_el_correo`).
- The candidate on the control (**not blind**: written after the key was opened; it checks the repairs, it does not
  validate them): CORE on the gold random 16 of 16, targeted 24 of 25 (`B40`, the duplicate); false deletions 0; residual
  random 14 blocks, 128 words (1.3 %); `B03`'s opening (133 words) in.

### 5. Not repaired (kept visible, reported)

- **Residue inside the BODY** (control, gold): name and credit lines (`B03`, `B05`, `B11`, `B13`, `B32`, `B40`), short labels
  (`B05`, `B10`, `B16`, `B39`, `B40`, `B43`), pull quotes with names (`B03`), a summary box (`B16`), photo credits inside
  captions (`B18`), an author's note (`B37`), a related title (`B06`). Each is a few words; a rule for them is lexical or
  outlet-specific and would endanger real text (CPD-0041 §4). No LLM stage.
- **Openings and items still missing**: a lead that is mostly a link (`B39`, `gt_prensa_libre`; the link-share guard against
  teasers), one-line items under 12 words (`B02`), live-entry headings (`B28`, `B43`; live pages are not CORE).
- **Text only in the JSON-LD** (`ar_pagina12`): the BODY is taken from the page's markup only (*Not decided here*).
- **Title surface**: a standfirst written as the first body paragraph (`B01`); no title block on `B10`.

## Alternatives considered

- **A copy anywhere inside a BODY block** — left out the article's own paragraph on a page whose embedded police post quotes
  it (`ec_primicias`); narrowed to the beginning.
- **Any declared LiveBlogPosting** — rejected two `cr_la_nacion` previews whose CMS wraps every paragraph as an update at one
  time; those are now excluded.
- **Counting only the running prose for CORE** (`B21`, `B29`) — a change of the CORE denominator; not made (*Not decided
  here*).
- **Re-including social posts so the completeness check passes** — excluded by the operator's brief; the measurement was
  corrected instead.

## Not decided here (the operator's decision)

1. Scientific acceptance and activation of `article_html/0.4.1` (with `body-templates/1`), `content-quality/4` and
   `body-quality/2` (recommended in the run report, §13).
2. **Structured text types and the 150 words**: the gate counts every word of the BODY. A recipe (`B21`: 125 words of method,
   179 with the ingredients) is accepted; a match report with tables (`B29`: 172 words of running report; the tables bring
   the function-word share to 0.289 under 0.30) is rejected. Whether the standard counts running prose only is the
   operator's.
3. The word definition at the threshold: the gate counts letter-only words (`B19` 149, `B30` 147; 155 and 150 by
   white space).
4. Whether a stated `articleBody` may serve as the BODY of a page that renders its text by script (`ar_pagina12`).
5. Unchanged from CPD-0041: a layer of its own for embedded social posts; whether `body-quality` is shown in a release.
6. `B28` (blocks 4–6, an entry on another match in the same live blog): assessed by the agent as text of the blog, not an
   embedded foreign item; no effect on CORE.
