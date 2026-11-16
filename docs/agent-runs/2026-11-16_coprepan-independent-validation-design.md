# 2026-11-16 — CO.PRE.PAN independent BODY/CORE validation: design, model-independent gold reviewer, acquisition prepared

**Status:** `PARTIAL` (design, gold tooling, statistics, separation, practice package, documentation done and tested; the holdout
acquisition `BLOCKED` — it needs the operator's commission with limits) · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-16 (Monday), Europe/Berlin |
| Kind | method design + tooling + offline measurement on development pages (AGENTS §8). **Not** a validation, **not** a gold annotation, **not** an acceptance or activation |
| Status | `PARTIAL`: everything the brief asks is done except the new data — the acquisition is prepared and blocked by an authorisation gate (CPD-0023). It does **not** claim any quality of the candidate; no gold exists; no prediction was made on any holdout |
| External calls | none. No publisher request, no web page, no provider, LLM, GPU or HPC call. The browser checks used a literal loopback server only |
| Start | `main` = `origin/main` = `14ebc22`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\independent-validation`, branch `phase3/independent-validation` |
| Operator brief | "CO.PRE.PAN_v3 – Unabhängige BODY-/CORE-Validierung methodisch absichern und HTML-Reviewer qualifizieren" (2026-11-16) |
| Decision | [CPD-0044](../decisions/CPD-0044_independent-body-core-validation-design-and-gold-reviewer.md) (partially supersedes CPD-0043 §5) |
| Evidence | [validation guide](../intake/validation/README.md) with plan, codebook, acquisition preparation, development population, effort |

## 1. Start state, norms, decisions

- **Git:** `main` = `origin/main` = `14ebc22`, clean; no change since CPD-0043. Four older worktrees of other runs left untouched.
- **Running elsewhere:** a CO.RA.PAN consolidated release freeze (`corpus_release_v1.py freeze`, Session A, started 11:05) — not
  touched; every heavy step here ran below normal priority, one at a time, on `C:` only.
- **Norms read:** AGENTS.md; TRANSFORMATION_AND_VALIDATION_PRINCIPLES (§4 no generic floors, §5 disjoint by outlet and document,
  gold frozen before predictions, selector frozen first, §6 checklist, §10 human review); storage INDEX §7 (frozen evidence
  permanent); CPD-0023 (delegated authorisation), CPD-0036 (deferred local preservation), CPD-0038…0043.

## 2. Methodological problems of the prepared review (CPD-0043)

1. **Not independent**: all 4,759 stored pages were read in full by development (the template table was built from all of them);
   the 120 cases are drawn from them. → `DEVELOPMENT_DIAGNOSTIC / NOT_INDEPENDENT_HOLDOUT`.
2. **Targeted strata from the candidate's own output** (changed by 0.4.2, CORE changed, residual_suspect …) — selection by the model.
3. **Machine-shaped reference**: the reviewer judged the candidate's candidate blocks; text outside them was hard to see; "all open
   = article text" made the machine's structure the default.
4. **Statistics**: a country-stratified sample with unequal inclusion probabilities scored with plain Wilson intervals.

## 3. What development has seen

[`development_population_2026-11-16.json`](../intake/validation/development_population_2026-11-16.json): 4,759 pages, 91 outlets, 46
runs, fetched 2026-10-08T20:35Z … 2026-11-15T10:46Z; fetch ids (SHA-256 of the list `1f298d81…`) and address digests. Nothing newer
exists in the workspace.

## 4. The validation design and why

- **Reachability decides the claim.** All 81 qualified outlets are development outlets; the 23 registered outlets without pages are
  `NOT_QUALIFIED` (10: discovery or acquisition failed) or `HELD` (13: bot challenges, blocks); 12 are only proposed. An
  outlet-disjoint holdout is impossible without circumvention or new registrations. → **primary claim = replicability on the
  corpus's own outlets** (document- and time-disjoint), stated as a named deviation from "disjoint by outlet" (V1); outlet-disjoint
  generalisability is an optional later component (V5).
- **Design**: outlets as certainty strata, 2 documents per outlet at random from what the intake fetches after the cutoff; replicate 1
  (one per outlet) first and complete on its own; no targeted component in the holdout (it would need the candidate's signals);
  baseline `article_html/0.3.0` + `content-quality/3`, paired.
- **Sample size**: low expected rates make the upper bound the informative quantity — 0 of 81 → ≤ 4.5 %, 0 of 162 → ≤ 2.3 %, 0 of 240
  → ≤ 1.6 % (Wilson, design effect 1, arithmetic). Recommended 2 per outlet (~162), replicate 1 the minimum (V3).
- Full plan: [`BODY_CORE_VALIDATION_PLAN_2026-11-16.md`](../intake/validation/BODY_CORE_VALIDATION_PLAN_2026-11-16.md) (`PROPOSED`,
  to be frozen at approval and before acquisition), with the principles' checklist answered in its sections (baseline, target,
  harms, robustness limits, gates: none, population adequacy).

## 5. Data origin, acquisition scope, requests, costs

- **Requests made: 0. Costs: none.** The acquisition is `BLOCKED`: CPD-0023 admits requests only under a record quoting the
  operator's commission (validity, outlets, limits); the brief names none, and an agent setting them would widen the commission.
- **Prepared** ([preparation](../intake/validation/holdout_acquisition_PREPARATION_2026-11-16.md)): 81 outlets, ≤ 4 item requests each,
  about 650–900 transport requests in 6 waves of 13–14 outlets, 6–8 h (*estimates* from the measured weekend waves), local
  preservation only, runs registered in the holdout register in the arming commit, the commission text ready to issue.
- **Separation built now**: `config/validation/holdout_runs.json` (empty) and its enforcement — every development study
  (`study_content_quality.pages`, `study_phase3_metadata.stored_pages`) leaves registered runs out; a page cache holding one is refused.

## 6. Independence of development, sampling and gold

| Stage | How independence is kept |
|---|---|
| sampling | `draw_per_outlet` reads outlet and fetch id only; development fetch ids and addresses excluded |
| package | `gold_review.write_package`: no extractor, gate or status runs; manifest `predictions: none`; design sealed, never served |
| display | `docview/1` (HTML block boundaries only) beside the inert original; no machine field, no machine endpoint |
| annotation | ranges and spans on the whole page; unlabelled text confirmed explicitly; `N` checks every longer unlabelled segment |
| freeze | `gold-body/v1` without publisher text; package closed afterwards; `predict` requires the gold committed and unchanged |
| scoring | frozen gold, sealed design, predictions written once and bound to the gold digest |

Remaining limits, stated: the reviewer knows the outlets from the development control (familiarity, not leaked labels); the
codebook was written with knowledge of development pages; the holdout shares outlets with development (§4).

## 7. Implementation and technical validation

- `src/coprepan/docview.py` — `docview/1`.
- `src/coprepan/gold_review.py` + `gold_review_app/` — packages (`HOLDOUT`, `DIAGNOSTIC`, `PRACTICE`), codebook vocabularies,
  events (ranges with a digest over their segments, spans with offsets and the segment digest), replay with a torn-last-line rule,
  closing with explicit rest confirmation, reopen recorded, freeze (all or replicates 1..N), loopback server (Host/Origin checks, no
  machine or design endpoint, CSP).
- `src/coprepan/gold_score.py` — predictions after the freeze (candidate, baseline, predecessor; pinned versions), word alignment,
  per-case metrics, design-based estimates, paired difference.
- `src/coprepan/survey_stats.py` — weighted ratios and proportions, Taylor linearisation, collapsed strata, Korn–Graubard-style
  Wilson on the effective sample size, t quantiles for few units; reports singleton strata.
- `src/coprepan/validation_holdout.py`, `config/validation/holdout_runs.json`.
- `scripts/gold_review.py` (development-population, prepare-practice, prepare-holdout, serve, status, snapshot, freeze, predict,
  score); `scripts/check_gold_reviewer_browser.py`; `scripts/study_gold_effort.py`.
- `body_review.py`: scoring design-weighted (`coprepan-body-review-result/v2`).
- **Tests**: `tests/test_gold_review.py` (12) — text view, package without machine output, tamper refusal, event checks, replay and torn
  line, resolution with spans, freeze without publisher text and closed afterwards, replicate freeze and collapsed strata, alignment
  and the five error classes, estimators (variance against the closed form, p = 0, singleton strata, paired difference), the draw,
  development never reading a holdout run, the server without machine or design endpoint. `tests/test_body_review.py` adjusted to
  the weighted estimate.
- **Real browser** (Chrome via Playwright, `scripts/check_gold_reviewer_browser.py`, on a technical test package of 2 development
  pages and a hostile page, deleted afterwards): **20 of 20 checks pass** — heading key, range by click and Shift+click, J/K and
  Shift+J, span from a text selection with exact offsets, removing a span, a folded footer labelled at once, search from the
  original, refusal to close CORE "no" without a reason, Ctrl+Enter from a text field, resume after reload, lock and reopen, typed
  text kept with its own case when switching, every segment of a real page reachable, no script of the hostile page ran, **no request
  beyond the local server**. The checks found and fixed five client defects: a folded group selected only its last segment; Ctrl+Enter
  ignored in text fields; the rest confirmation silently reset by other answers; a comment typed just before switching could land in
  the next case; and a layout that let the banner slide under the bar.
- **Full suite**: `python -m pytest tests` — **2,199 passed, 15 skipped** (the known skips), 781 s, below normal priority; no tracked
  file modified by the run.

## 8. Statistics and their limits

Estimands `outlets` (recommended primary) and `documents`. Weights from the realised gold (`N_h / n_h`, `1 / n_h`). Variance:
outlet strata with documents as units when every outlet holds ≥ 2 gold cases, otherwise collapsed strata (country, outlet as unit;
conservative). Proportions: Wilson on the effective sample size (for 0 or 1 the design effect cannot be estimated — `n_eff = n`,
flagged). Word ratios cluster-aware. Limits: few outlets per country — no country rates; 1–2 documents per outlet — no outlet rates
(a systematic outlet defect shows as a SOFT WARNING when both cases fail); the estimates hold for the frame period; corpus-level CORE
rules (duplicates) are outside the page-level comparison.

## 9. Effort (measured structure, scenario time)

[200 development pages](../intake/validation/gold_effort_2026-11-16.json): median 148 segments, 447 article words, 2 article runs, 2
overrides, 15 longer outside segments; ~38 actions per case. At 2–4 s per action and 220–400 words per minute (*scenario
assumptions*): 3.6–6.9 min per case on average → replicate 1 (~81 cases) ≈ 5–9 h, both replicates ≈ 10–19 h. The practice package
gives the first real measure of the operator's pace.

## 10. Open decisions, risks, blockers

- **V1** replicability on the corpus's own outlets as the claim · **V2** the acquisition commission (**blocker**) · **V3** sample size
  (2 per outlet; replicate 1 minimum) · **V4** primary estimand (outlets) · **V5** an outlet-disjoint component (registration and
  qualification first) · **V6** acceptance after the frozen result; plan and codebook approval.
- Risks: the holdout's raw bytes stay `PRESERVATION_PENDING` on `C:` until promoted; the gold depends on them. A design effect above 1
  widens every interval. Annotation fatigue over 10–19 h: sittings, replicate 1 first.

## 11. Local artefacts, git, closure

- **Local** (runtime workspace, publisher text, outside the repository): `coprepan_workspace\review\practice_2026-11-16` (`PRACTICE`,
  `d206afc1789208b0a32def29`, 5 cases); `coprepan_workspace\review\body_final_review_2026-11-16_a24462c3c84a7691b2ab12d7` (the 120-case
  package, copied and verified; the original under `%LOCALAPPDATA%\Temp\coprepan-body-final-review\package` left in place). The
  technical test packages of the browser checks were deleted. Scratch in the session's scratchpad only.
- **Repository**: code, tests, docs, the development population (ids and digests), the effort study — no publisher text.
- **Committed** on `phase3/independent-validation` with explicit pathspecs (tooling; decision and evidence; this report),
  **merged** into `main` by fast-forward (`main` had not moved since `14ebc22`), **pushed** (`main` and the branch), the report
  **published** on `main` with `scripts/publish_run_report.py`, the worktree **removed** last with `scripts/worktree_closure.py`.
- **Tree classification:** every change committed; nothing left in the repository.
- Untouched: CO.RA.PAN and its running release freeze, the reference repositories, the joint contracts, every frozen control and
  the 120-case package's manifest, the four other worktrees.

## 12. Next step for the operator

Read the [plan](../intake/validation/BODY_CORE_VALIDATION_PLAN_2026-11-16.md) and the [codebook](../intake/validation/GOLD_CODEBOOK_1.md),
try the [practice package](../intake/validation/README.md) for 10–20 minutes, and decide V1–V4 — with V2 issued as the commission in
the [preparation](../intake/validation/holdout_acquisition_PREPARATION_2026-11-16.md). Then the agent acquires the holdout and builds
its package; the gold annotation follows.
