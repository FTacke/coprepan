# CPD-0044 — The independent BODY/CORE validation: design, model-independent gold, design-based scoring; the acquisition prepared

| Field | Value |
|---|---|
| Date | 2026-11-16 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| What is active | the gold tooling (`docview/1`, `gold-body-codebook/1` as proposed, `gold_review`, `gold_score`, `survey_stats`; schemas `gold-body-package/v1`, `gold-body-event/v1`, `gold-body/v1`, `gold-body-predictions/v1`, `gold-body-result/v1`); the holdout register `coprepan-holdout-runs/v1` and its exclusion from every development study; the classification of the 120-case package as `DEVELOPMENT_DIAGNOSTIC / NOT_INDEPENDENT_HOLDOUT`; the design-weighted scoring of `body_review` (`coprepan-body-review-result/v2`). **Proposed, the operator's:** the validation plan v1 and the codebook. **Blocked:** the holdout acquisition (no commission with limits) |
| Decided by | the operator's brief of 2026-11-16 ("CO.PRE.PAN_v3 – Unabhängige BODY-/CORE-Validierung methodisch absichern und HTML-Reviewer qualifizieren": no further optimisation; a methodically independent validation; new data welcome within the acquisition rules; model-independent gold; correct statistics; no gold annotation, no acceptance, no activation by the agent); the tooling and the proposals are the commissioned agent's |
| Kind | scientific method · validation · tooling |
| Execution | `src/coprepan/docview.py`, `gold_review.py` (+ `gold_review_app/`), `gold_score.py`, `survey_stats.py`, `validation_holdout.py`; `body_review.py` (scoring); `scripts/gold_review.py`, `check_gold_reviewer_browser.py`, `study_gold_effort.py`; `scripts/study_content_quality.py`, `study_phase3_metadata.py` (holdout exclusion); `config/validation/holdout_runs.json`; `tests/test_gold_review.py` |
| Builds on / amends / supersedes | builds on CPD-0043, CPD-0023/0036 (acquisition), the principles; **partially supersedes CPD-0043 §5**: its prepared 120-case package is not the validation |
| Does not change | every extractor, gate, status and threshold (`article_html/0.4.2` and earlier, `content-quality/1`–`/4`, `body-quality/1`–`/2`, templates); the frozen controls and the 120-case package with its manifest (only a dated note beside it); the joint contracts; the acquisition rules |
| Run report | [`2026-11-16 independent validation`](../agent-runs/2026-11-16_coprepan-independent-validation-design.md) |
| Evidence | [validation guide](../intake/validation/README.md), [plan v1](../intake/validation/BODY_CORE_VALIDATION_PLAN_2026-11-16.md), [codebook](../intake/validation/GOLD_CODEBOOK_1.md), [acquisition preparation](../intake/validation/holdout_acquisition_PREPARATION_2026-11-16.md), [development population](../intake/validation/development_population_2026-11-16.json), [effort](../intake/validation/gold_effort_2026-11-16.json) |

## Context

The validation prepared under CPD-0043 drew its 120 cases from the 4,759 pages development had read in full, chose its targeted
cases with the candidate's output, showed the candidate's candidate blocks and offered "all open blocks = article text". Its
scoring treated a stratified sample with unequal inclusion probabilities as a simple one. None of that can carry an independent
validation under the principles (§5: disjoint by outlet and document; gold frozen before predictions; the selector frozen first).

## Decision

1. **What development has seen** is recorded: every stored 2xx item page (4,759, 91 outlets, 46 runs, 2026-10-08 … 2026-11-15) — the
   [development population](../intake/validation/development_population_2026-11-16.json) with fetch ids and address digests.
2. **The 120-case package is `DEVELOPMENT_DIAGNOSTIC / NOT_INDEPENDENT_HOLDOUT`**: kept unchanged, copied (verified) to the runtime
   workspace, usable for diagnosis and practice only.
3. **The independent validation** ([plan v1](../intake/validation/BODY_CORE_VALIDATION_PLAN_2026-11-16.md), proposed): new
   documents of the corpus's qualified outlets acquired after the development cutoff — document- and time-disjoint; **not
   outlet-disjoint, because no outlet outside development is reachable** (all 81 qualified outlets are development outlets; every
   other registered outlet is not qualified or held). The claim is replicability for these outlets, not generalisability. Every
   outlet a certainty stratum, 2 documents per outlet at random (replicate 1 first, a sample on its own); no targeted component in
   the holdout; candidate against the realistic baseline `article_html/0.3.0` + `content-quality/3`, paired.
4. **Model-independent gold**: the reviewer marks ranges and spans on `docview/1` — the page's body text split at HTML block
   boundaries only, sharing no rule with any extractor — beside the inert original; seven labels and confirmed unlabelled text; case
   answers for the source, text outside the view, CORE with reasons, page types. No machine output exists in a gold package; the
   server has no endpoint for one. Gold is frozen without publisher text and **committed** before `predict` will run.
5. **Scoring** aligns the machine BODY word by word to the gold (independent of the extractor's blocks) and estimates by the design:
   weights from the realised sample, two estimands (outlets, documents), Taylor-linearised variances (collapsed strata when an
   outlet holds one gold case), Wilson on the effective sample size; outlet and country results descriptive. `body_review`'s scoring
   is corrected the same way.
6. **Separation from development**: holdout runs are registered before their pages are read; every development study leaves them
   out (a page cache holding one is refused).
7. **Acquisition `BLOCKED`**: the rules admit requests only under a record quoting the operator's limits (CPD-0023); the brief names
   none. The [preparation](../intake/validation/holdout_acquisition_PREPARATION_2026-11-16.md) holds the plan (81 outlets, ≤ 4 items
   each, about 650–900 requests in 6 waves, local preservation) and the commission text to issue. No request was made.

## Alternatives considered

- **Use the 120 package as the validation** — not independent (§Context).
- **Annotate the extractor's candidate blocks** (CPD-0043's reviewer) — the machine's segmentation would define what the reviewer
  sees and what can be missing; replaced by the model-independent view.
- **A targeted holdout component** — selecting hard cases needs the candidate's signals; kept to the development material.
- **Outlet-disjoint holdout now** — no reachable outlet; registering and qualifying new outlets is a separate, optional component.
- **3 documents per outlet** — upper bound of a zero rate 2.3 % → 1.6 % for 50 % more work; not recommended.

## Not decided here (the operator's decision)

- **V1** accepting a replicability claim on the corpus's own outlets (no outlet-disjoint holdout possible today);
- **V2** the acquisition commission (window, limits, seed) — the acquisition is blocked until then;
- **V3** the sample size (recommended: 2 per outlet, replicate 1 the minimum);
- **V4** the primary estimand (recommended: outlets; documents reported beside);
- **V5** an outlet-disjoint component B (registration and qualification of new outlets);
- **V6** the acceptance of the candidate after the frozen result; and the codebook (proposed) and plan (proposed) themselves.
