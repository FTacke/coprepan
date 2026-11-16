# The independent BODY/CORE validation — plan v1 (CPD-0044)

**Status: `PROPOSED`.** This plan is frozen as the pre-registration when the operator approves it and **before** the holdout is
acquired; from then on it is never edited (a change is a dated v2 beside it, made before any gold exists). It states what will be
measured, on what, against what, and how — before any human gold or any prediction exists on the holdout.

| | |
|---|---|
| Under test | `article_html/0.4.2` + `body-templates/1`; `content-features/2` / `content-quality/4`; `body-quality/2` (CPD-0043) |
| Realistic baseline | `article_html/0.3.0` + `content-quality/3` — the container-only extractor before the BODY selection (CPD-0040), the feasible alternative. Diagnostic: `article_html/0.4.1` + `content-quality/4` |
| Gold | [codebook `gold-body-codebook/1`](GOLD_CODEBOOK_1.md) on the model-independent text view `docview/1` |
| Tools | `scripts/gold_review.py`, `src/coprepan/gold_review.py`, `gold_score.py`, `survey_stats.py`, `docview.py` |
| Development population | [4,759 pages, 91 outlets, 46 runs, fetched 2026-10-08 … 2026-11-15](development_population_2026-11-16.json) |

## 1. The problem this plan answers

Every stored page (4,759) was read by the development of CPD-0038 … CPD-0043 — the BODY template table was even built from all of
them. The prepared 120-case package of 2026-11-16 draws from these pages and its targeted strata use the candidate's own output:
it is **`DEVELOPMENT_DIAGNOSTIC / NOT_INDEPENDENT_HOLDOUT`**. Its block list came from the candidate's candidate blocks, and its
"all open blocks = article text" key let the machine's structure shape the reference. Neither can carry the final validation.

## 2. Target population and the claim

**Primary (replicability):** item pages (2xx HTML) that the corpus's own qualified outlets publish **after** the development
cutoff (2026-11-15T10:46Z), as the intake acquires them. The claim: how well the candidate represents the published text and
selects CORE on new documents of this corpus.

- **Document- and time-disjoint**, by construction (fetch ids and addresses of the development population are excluded).
- **Not outlet-disjoint — unavoidably.** All 81 currently qualified outlets (72 `QUALIFIED`, 9 `QUALIFIED_WITH_LIMITS`, 20 countries)
  are development outlets; every registered outlet without development pages is `NOT_QUALIFIED` (discovery or acquisition failed)
  or `HELD` (bot challenge, block) — none is reachable without circumventing an access control, which is excluded. The candidate
  holds outlet-specific knowledge (the template table) by design; the primary estimate is valid **for these outlets** and says
  nothing about unseen outlets. This deviation from the principle "disjoint by outlet" (TRANSFORMATION_AND_VALIDATION_PRINCIPLES
  §5) is named here and needs the operator's acceptance (**decision V1**).
- **Not claimed:** generalisability to other outlets, outlet types or later periods; country-level rates (1–7 outlets per country
  cannot carry them; country is reported descriptively); a statement about corpus-level CORE rules (duplicates across pages).

**Optional (generalisability), component B:** outlets outside the development population — today none is reachable. Candidates:
the 12 `proposed` outlets (registration is the operator's) and `NOT_QUALIFIED` outlets whose discovery works but whose items were
not attempted (`bo_lostiempos`, `pe_el_comercio`, `sv_diario_el_mundo`). Requires registration and qualification first (**V5**).

## 3. Design (component A)

- **Frame:** the 2xx item pages of the holdout runs (registered in `config/validation/holdout_runs.json` **before** anything reads
  them), minus every development fetch id and address. What the intake fetches is what the corpus would contain: the frame is
  the intake's own selection (newest items first, allowances per outlet), not a reconstruction.
- **Draw:** every outlet a stratum, taken with certainty; **2 documents per outlet** at random without replacement (seeded,
  `gold_review.draw_per_outlet`), all when an outlet has fewer. The draw reads outlet and fetch id only — no extractor, gate or
  status. Exact inclusion probabilities `n_h / N_h`.
- **Replicates:** the first document of every outlet (replicate 1, ~81 cases) is presented first and is a probability sample on its
  own; replicate 2 completes the design. Stopping after replicate 1 is admissible when decided on effort alone, before any
  prediction (`freeze --replicate 1`); the scoring weights the cases the gold actually holds.
- **No targeted component in the holdout.** Hard cases chosen by the machine's own signals would leak its decisions into the
  sample. Diagnosis of known error classes uses the development material (the 120-case package), counted apart, never weighted.

## 4. Sample size

Expected rates are low (the frozen control: 0 false deletions, residue in 6 of 16 random cases, CORE 15–16 of 16). The informative
quantity is therefore the **upper bound** of an interval. Wilson 95 % at design effect 1 (*arithmetic, not a result*; a design
effect above 1 widens these):

| observed share | n = 81 (replicate 1) | n = 162 (both) | n = 240 (3 per outlet) |
|---|---|---|---|
| 0 | 0 – 4.5 % | 0 – 2.3 % | 0 – 1.6 % |
| 2 % | 0.5 – 7.9 % | 0.7 – 5.5 % | 0.8 – 4.7 % |
| 5 % | 2.0 – 12.1 % | 2.6 – 9.5 % | 2.9 – 8.5 % |
| 20 % | 12.7 – 30.0 % | 14.6 – 26.8 % | 15.4 – 25.5 % |

Two per outlet halves the upper bound of a rare error against one per outlet and lets a systematic outlet defect show twice; a
third per outlet buys little (2.3 → 1.6 %) for 50 % more work. **Recommendation: 2 per outlet (~162 cases), replicate 1 the
minimum (decision V3).**

**Effort** ([measured structure](gold_effort_2026-11-16.json), 200 development pages): median 148 segments, 447 article words,
2 article runs, 2 overrides inside them, 15 longer segments to check outside; about 38 actions per case. At 2–4 s per action and
220–400 words per minute (*scenario assumptions*): **3.6–6.9 min per case on average** → replicate 1 about **5–9 h**, both
replicates about **10–19 h**, in sittings of any length. The practice package is the first measurement of the real pace.

## 5. Independence and leakage control

| Point | Control |
|---|---|
| selection | random within outlet; no extractor runs to build a package (`gold_review.write_package`; manifest `predictions: none`) |
| display | the text view is `docview/1` (HTML block boundaries only); the page is shown inert; no machine field exists in a package and the server has no endpoint for one |
| annotation | ranges and spans on the whole page text; no "accept the machine's blocks"; unlabelled text is confirmed "not article text" explicitly at closing; `N` walks every longer unlabelled segment |
| reviewer | blind to versions and decisions; the operator knows the outlets from the development control — familiarity, not leaked labels; stated as a limit |
| gold | frozen (`gold-body/v1`, no publisher text) and **committed** before any prediction; `predict` refuses otherwise |
| predictions | made once, written once, pinned to the gold's digest; scoring reads frozen gold, design and predictions only |
| development | holdout runs are invisible to every development study (`study_content_quality.pages`, `study_phase3_metadata.stored_pages`); a run is registered before its pages are read and never removed |

## 6. Measures (all `DIAGNOSTIC`; no hard gate)

Per case and system, after the word alignment of the machine BODY to the gold (`gold_score`): gold BODY words; included, missed;
**missed spans** (≥ 3 consecutive missed BODY words); included words by gold label (title, standfirst, caption, embed, foreign,
unlabelled-foreign = contamination; unsure = doubt); unaligned machine words; CORE decision.

| Error kind | Measure | Unit / estimand |
|---|---|---|
| article text removed or missing | word recall (ratio); share of cases with a missed span | words; documents |
| contamination | word precision (ratio); share of cases with contamination | words; documents |
| CORE false accept | share of gold `no` among machine accepts | documents |
| CORE false reject | share of machine rejects among gold `yes` | documents |
| doubt | share of gold `unsure` (CORE) and unsure words | documents; words |
| net benefit | candidate − baseline, paired (word recall, contamination share) | words |

**Estimation.** Weighted by the realised design (`survey_stats`): two estimands, **outlets** (each outlet once; recommended as
primary — the release's selection view is not decided and the corpus is built per outlet) and **documents** (each fetched
document once) (**V4**). Ratio estimators with Taylor-linearised variances; outlets as strata and documents as units when every
outlet holds ≥ 2 gold cases, otherwise collapsed strata (country, outlet as unit; conservative). Proportions: Wilson on the
effective sample size. Word-level ratios are cluster-aware (words within documents). Outlet- and country-level results are
descriptive only.

**Excluded from denominators, stated:** cases with no gold BODY (source not visible, not an article page) from the word measures;
gold `unsure` from the CORE error rates (reported apart); unaligned machine words from both (reported).

## 7. How the result is used

No number is a gate (§4 of the principles). The operator weighs, with the frozen result: harms in order of seriousness —
**article text lost** (authenticity), **CORE false accepts** (contaminated core), **CORE false rejects** (lost material, possible
bias across outlets), **contamination** (noise) — the candidate against the baseline (paired differences), and the cases behind
every error. A `SOFT WARNING` is any outlet with a missed span or a CORE error in both its cases (a systematic outlet defect). The
acceptance is the operator's decision with that evidence (**V6**).

## 8. Order of work

1. Operator approves this plan (V1, V3, V4) and issues the acquisition commission ([preparation](holdout_acquisition_PREPARATION_2026-11-16.md), **V2**). The plan is frozen.
2. Acquisition waves under a delegated record; the runs are registered in `config/validation/holdout_runs.json` in the arming commit.
3. `gold_review.py prepare-holdout` (seed fixed in the commission); the package is written outside the repository.
4. The operator annotates ([guide](README.md)); `status` and `snapshot` along the way.
5. `freeze` (all, or `--replicate 1`); the gold file is committed and pushed.
6. `predict`, then `score`; the result is committed; the evaluation is written up separately.
