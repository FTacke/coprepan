# 2026-11-14/15 — CO.PRE.PAN weekend source qualification, content-quality gate and checks that scale with what is new

**Status:** `PARTIAL` · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-14 (Saturday) evening – 2026-11-15 (Sunday), Europe/Berlin |
| Kind | live qualification under two delegated operator records + autonomous repairs + engineering (AGENTS §8) |
| Status | `PARTIAL`: the live qualification is **complete** in its authorised scope; the content-quality gate, the incremental checks and `intake-controller/3` are implemented and validated offline; what stays open needs the operator's scientific decision (CPD-0038 §5), a weekday (the deferred preservation) or its own authorisation (the canaries of `/8` and `/3`, the 24-hour wave) — §15 |
| External API | `EXTERNAL_API_USAGE = NONE`. No LLM, GPU or HPC; the only network traffic was the authorised requests to publishers |
| Start | `main` = `origin/main`, clean, after the published report of the source-health run of 2026-11-14; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\weekend-qualification`, branch `qualification/2026-11-14-weekend` |
| Operator briefs | (1) "CO.PRE.PAN_v3 – Wochenend-Qualifikation aller zugänglichen Pressequellen mit lokalem Spooling und autonomen Reparaturen" (2026-11-14); (2) "CO.PRE.PAN_v3 – Autonome Qualitäts- und Performance-Optimierung bis zur produktionsreifen Vorzugslösung" (2026-11-15) |
| Authorisations | `DOA-2026-11-14-2` (waves wq-1…wq-7), `DOA-2026-11-15-1` (confirmation wave wc-1); both valid to 2026-11-15; one ceiling of 1,600 transport requests for both |
| Decisions | CPD-0036 (deferred local preservation; amended for `canary-driver/7`), CPD-0037 (incremental checks, `intake-controller/3`), CPD-0038 (candidate extractor and gate; candidates only, not binding) |

The sections follow the second brief (§16, 1–15); the first brief's A–J are contained: A = §1, B = §2, C = §3, D = §4–§6,
E = §11, F = §10, G = §14 and §3, H = §3 and §12, I = §13, J = §15.

## 1. Start state and authorisation

- **Git:** `main` = `origin/main`, clean; the four older worktrees left untouched; one CO.PRE.PAN session (this one).
- **Authorisation:** the first brief authorised real qualification requests on 14–15 November up to 23:59 Europe/Berlin, at most
  1,600 transport requests, at most 18 per outlet and 8 item requests, one request at a time, waves with their own records, no
  NEW_FS or `D:` writes, local preservation only (`PRESERVATION_PENDING`). Recorded as `DOA-2026-11-14-2` (seven waves) and, for the
  thirteen outlets whose first evidence a driver defect left incomplete, `DOA-2026-11-15-1` (one wave). The prepared
  `DIA-2026-11-14-1` (the intake canary) was neither used nor changed.
- **CO.RA.PAN** read only, through its advisory (`resource_policy.sibling_advisory`); nothing of it was stopped, changed or started.
- **Incidents of this session, stated:** (a) on 2026-11-14 around 20:40 local, a preflight script of this session resolved every
  configured storage role twice; each resolution wrote and removed an empty probe file on the NEW_FS share and on `D:` — the brief
  forbade NEW_FS and `D:` writes on the weekend; nothing else was written there (CPD-0036 records the context); (b) on 2026-11-15
  during wave wq-5, an edit meant for the worktree went into the main checkout for about a minute (during the suite on the arming
  commit) and was reverted; the arming had checked a clean tree, the evidence commit and the disarm were unaffected.

## 2. The weekend waves

| Wave | Record | Run | Outlets | Requests | Item requests | Pages 2xx | Status | Driver |
|---|---|---|---:|---:|---:|---:|---|---|
| wq-1 | DOA-2026-11-14-2 | `acq1-20261114T203842339757Z-20297ef9c2c8` | 15 | 121 | 66 | 60 | COMPLETE_PRESERVATION_DEFERRED, verification PASS | /6 |
| wq-2 | DOA-2026-11-14-2 | `acq1-20261114T222008470120Z-bf7150d8be63` | 14 | 119 | 60 | 60 | idem | /6 |
| wq-3 | DOA-2026-11-14-2 | `acq1-20261115T000319772506Z-c198b373dc69` | 14 | 131 | 84 | 84 | idem | /7 |
| wq-4 | DOA-2026-11-14-2 | `acq1-20261115T013553944256Z-099a9e1e8f6e` | 14 | 152 | 84 | 80 | idem | /7 |
| wq-5 | DOA-2026-11-14-2 | `acq1-20261115T031559237344Z-22e7f225d63b` | 14 | 143 | 84 | 84 | idem | /7 |
| wq-6 | DOA-2026-11-14-2 | `acq1-20261115T045716814350Z-3bfd8c42fcca` | 14 | 143 | 84 | 80 | idem | /7 |
| wq-7 | DOA-2026-11-14-2 | `acq1-20261115T063430632173Z-ada50dbd80ed` | 14 | 153 | 73 | 70 | idem | /7 |
| wc-1 | DOA-2026-11-15-1 | `acq1-20261115T092012103473Z-621c41779dc2` | 13 | 138 | 66 | — | idem | /7 |
| **all** | | | **99 distinct** | **1,100** | **601** | | | |

Every wave: arming commit, the full suite on it, the baseline frozen, the run, the evidence verified and measured, the disarm,
pushed, the full suite again on the disarmed tree (1,921–1,922 passed each time). `external_acquisition` is `disabled` in the
file, in `HEAD` and on `origin/main`. The persistent counter of the brief's ceiling: **1,100 of 1,600**. wc-1 was held back while
CO.RA.PAN's production ran at 85–97 % CPU (no measurable impairment: `SHARE_NORMAL` throughout) and then run at below-normal
process priority with a five-minute watch on CO.RA.PAN's advisory (§10).

**Repairs during the waves** (each with tests, committed before the next wave that needed it): `canary-driver/7` — stage B now
reads every selected channel after the first (`/6` read only the second, so a third selected channel was never requested), and a
qualification wave asks for the newest pages its own channels list (`item-selection/1`) instead of the planner's oldest-due-first
order, which had sent wq-1 to pages of 2009–2022. The evaluation rates pages of one and the same length a `UNIFORM_SHELL`, not a
functional acquisition (`ve_eluniversal`: six 9,004-byte script frames).

## 3. The source matrix

[`weekend_qualification_2026-11-15.md`](../intake/qualification/weekend_qualification_2026-11-15.md) (JSON beside it), built by
`scripts/build_weekend_qualification.py` from the evidence of both records. Six dimensions, kept apart, no single READY:

| Dimension | Result (99 outlets with live evidence) |
|---|---|
| Discovery functional | FUNCTIONAL 92 · FAILED 2 · NOT_REACHED 4 · answered without entries 1 (a later wave that did not reach an outlet does not erase an earlier wave's evidence) |
| Current articles found | CURRENT 84 · UNDATED 5 · STALE_CHANNEL 3 · NO_ENTRIES 7 |
| Raw acquisition | FUNCTIONAL 88 · FAILED 2 · NOT_ATTEMPTED 9 |
| Extraction (baseline) | GOOD 65 · LIMITED 14 · POOR 9 · not measured 11 |
| Content quality accepted (`content-quality/2` on `article_html`, every weekend page of the outlet) | most pages 74 · some 10 · none 4 · not measured 11 |
| **Qualified for the next intake** | **QUALIFIED 72 · QUALIFIED_WITH_LIMITS 9 · NOT_QUALIFIED 18** |

The 27 further outlets of the registry without live evidence are listed with why: 12 not registered completely enough for a live
request (placeholder URL rules, no channel), 15 held (an origin, or every selected channel, under an evidence-based hold). **Not qualified, by reason:** robots unreachable or 5xx —
`cu_5_de_septiembre`, `cu_periodico26`, `mx_animal_politico`, `pa_panama_24_horas` (DEFER, not worked around); a channel that is not
current — `cl_biobiochile` (news sitemap of July 2025), `cu_juventud_rebelde` (index of old pages), `ve_eluniversal` (script frames,
article rendered in the browser; no publisher script is run); listing channels waiting for an allow rule — `bo_lostiempos`,
`pe_el_comercio`, `sv_diario_el_mundo`; item pages answering 5xx or failing — `bo_brujula_digital`, `hn_proceso_digital`; no current
channel answered — `cr_crhoy` (the amended news sitemap was planned in wc-1 and refused by the canary's own per-outlet budget:
two robots files and a redirected feed spent it — a budget point, §12), `ve_analitica`, `ec_expreso` (answered without entries);
pages the gate rejects — `ar_pagina12` (article body only in JSON-LD, client-rendered), `hn_la_prensa` and `pa_laestrelladepanama`
(section pages and fragments; the CMS keeps the body outside the paragraph structure). **Registry amendments:** none beyond the
additive news-channel amendment of 2026-11-14; the matrix names, per outlet, which channel a later amendment would need.

## 4. The quality study and the chosen configuration

Data: every stored 2xx item page, 4,759 pages of 91 outlets (the October pilot and 24-hour intake, the weekend waves), split by
`sha256(fetch_id)` into a development half and a held-out half. Features (`content-features/1`, `content_quality.features`): words,
distinct words, paragraphs of 25+ words, function-word share (closed-class Spanish words), sentence-end share, repeated blocks,
distinct 5-gram ratio, frame/paywall/machine-text/sponsor marks, time-stamp-led blocks, the length of the article body the page
itself states in JSON-LD. The agent read 108 stratified pages (six word bands) and 40 hard negatives (≥150 words with a suspicious
signal) of the development half — its own reading, not a gold standard.

| Configuration (development half, the agent's labels) | Bad pages accepted | Good pages rejected (of 111) |
|---|---:|---:|
| ≥ 150 words only | 7 | 23 |
| + function-word share ≥ 0.30 | 3 | 26 |
| + frame, paywall, machine-text marks | 1 | 26 |
| + stated-body shortfall, repetition, sponsor, live (the single-page rules) | 0 | 26 |
| all rules incl. template and duplicate (`content-quality/1`) | 0 | 26 |
| … with ≥ 100 words | 1 | 7 |
| … with ≥ 200 words | 0 | 37 |

Chosen: the smallest set that reaches no false accept on the development reading, with 150 words. Lexical diversity (type-token
ratio) was measured and **not** used: it falls with length and added nothing the function-word share and the 5-gram ratio do not
already separate. The full rule set and its reasons are in CPD-0038; the decision of a page is a list of machine-readable reasons
and the values it rests on (`content_quality.assess`, `assess_corpus`).

**What the reading found** (examples, all in the study record): good — complete news items from 150 words on, interviews, opinion
columns, letters to the editor, agency copy; rightly rejected — newsletter and cookie banners, copyright lines, section pages that
the baseline had extracted as teaser lists, an ad-blocker wall in full sentences (`uy_el_pais`), the column-submission terms of
`pr_el_nuevo_dia` (151 words of correct prose under six URLs: the template rule), an author filter of 524 names (`gt_prensa_libre`),
English and Basque texts, live tickers, advertorials, and **articles that declare themselves AI-generated or AI-assisted**
(`co_elpais` "creado con ayuda de una inteligencia artificial", `ar_la_nacion` "con la asistencia de la IA", `ar_clarin`,
`cl_biobiochile`, `ni_nicaragua_investiga`, AI summaries at `co_el_espectador`) — 49 pages.

## 5. Control sample and measured quality

Both controls were drawn from the held-out half **after** the rule set was frozen in a commit, and read **blind** (address, title,
the body's beginning and end; no decision, no feature), accepted and rejected pages shuffled together.

| Rule set | Accepted pages read | Good | Precision | 95 % Wilson | Rejected pages read | of them good |
|---|---:|---:|---:|---|---:|---:|
| `content-quality/1` (`15fce0d`) | 100 | 94 | 0.94 | 0.875–0.972 | 40 | 20 |
| `content-quality/2` (`18c87ca`) | 100 | 97 | 0.97 | 0.915–0.990 | 20 | 10 |

`/2` closed the five general classes of `/1`'s false accepts (more wordings of AI disclosures; institutional pages; live slugs and
titles; sponsor marks anywhere in the address). Its three false accepts: a lottery results page and two unmarked promotional texts
(a product test, a concert advertisement) — **native advertising without a mark is the residual class** simple rules do not
separate. The good pages among the rejected are complete briefs under 150 words (the recall given up by design) and later
duplicates of an article whose first copy is accepted. Variation by outlet: the matrix's content-quality column; outlets that
publish mostly briefs (`pa_metro_libre`, `cr_diario_extra`, `pr_metro_puerto_rico`) have low yield. **The 97 % is the agent's
reading, not an independent gold standard**: the human review sample
([`content_quality_review_2026-11-15.md`](../intake/quality/content_quality_review_2026-11-15.md), 66 pages, every kind of decision)
is for the operator's independent check. Cost: features and decision about 16 ms per page on one core (4,711 pages in 76 s,
including both extractions and the pack reads).

## 6. Extraction and admission repairs

`article_html/0.1.0` (CANDIDATE; the baseline unchanged): container by running-text density with parent and sibling rules, HTML's
implicit closing of paragraphs and list items, non-body elements and link-heavy blocks out. It repairs the measured cases
(`pa_diaadia` header ancestor; teaser cards at `ar_la_nacion`, `pa_metro_libre`, `mx_el_universal`, `co_elcolombiano`; unclosed
paragraphs at `ni_nicaragua_investiga`; articles split into sibling elements at `uy_el_observador`): on the 2,413 pages that state a
JSON-LD body, within 85–125 % of it on 1,987 (baseline 899). Where it still fails (`ar_pagina12`, `hn_la_prensa`,
`pa_laestrelladepanama`, live blogs) the gate rejects the page instead of a rescue rule per outlet. The content-admission gate is a
separate layer (`content-quality/2`); `admission-technical/1` and every release view are unchanged. Nothing is activated.

## 7. Performance before and after

**Before (measured on the weekend waves, `scripts/measure_weekend_capacity.py`):**

| Wave | Requests | Wall | In records (pacing + transport) | Between records (the driver's own work) | Transport share at most |
|---|---:|---:|---:|---:|---:|
| wq-1 | 109 | 4,513 s | 896 s | 3,627 s | 7.7 % |
| wq-4 | 142 | 4,387 s | 1,009 s | 3,390 s | 2.8 % |
| wq-7 | 143 | 4,546 s | 1,143 s | 3,402 s | 8.0 % |
| wc-1 | 134 | 5,141 s | 967 s | 4,185 s | 4.7 % |

(All eight in [`weekend_capacity_2026-11-15.json`](../intake/qualification/weekend_capacity_2026-11-15.json); fetch records, robots
included.) One `recovery.diagnose` of the runtime workspace:
234 s under the profiler (58,000 file opens 117 s, layer manifests 65 s, evidence anchors 63 s, 2,275 sealed packs re-hashed 30 s,
candidate consistency 23 s), 2 + 2 × outlets times a wave. Median exact transport of a first request to an origin: 0.37 s over all
waves.

**After (measured on a local copy of the runtime workspace, 6,948 pack files, 2,316 sealed packs;
[`workspace_checks_benchmark_2026-11-15.json`](../intake/performance/workspace_checks_benchmark_2026-11-15.json)):**

| Check | Seconds | Files opened | Sealed packs re-hashed | Result |
|---|---:|---:|---:|---|
| Full audit `recovery.diagnose` | 93.5 (276.5 on the first, cold attempt) | 58,496 | 2,316 | CLEAN |
| First checkpoint without state (full audit + rebase), once | 112.1 | 63,233 | 2,316 | — |
| Incremental, nothing new | 0.13 | 227 | 8 (the rotating audit) | CLEAN |
| Incremental, 100 new request pairs | 0.16 | 227 | 8 | CLEAN |
| Incremental, 1,000 new request pairs | 0.14 | 227 | 8 | CLEAN |

A wave of 14 outlets ran 30 checkpoints: under `/7` 30 full audits (2–4 minutes each, about three quarters of the wave's wall
time); under `/8` one full audit at most (only without a valid state, after a finding, or weekly) and 29 checks of well under a
second. The first attempt of this benchmark appended malformed synthetic request rows; the incremental check refused them, handed
over to the full audit, and the full audit classified them `DAMAGED` — the intended behaviour; the measurement was repeated with
well-formed rows.

## 8. The incremental consistency architecture

`incremental_check` (CPD-0037): anchors per append-only table, sealed packs verified once, row-by-row derivation checks, closed
runs' heads against the anchors; any finding → the full `recovery.diagnose` decides; a rotating fixity audit (8 packs / 64 MiB and
32 layer answers per check, longest-unaudited first, never starved); a full audit without valid state, after any finding and weekly;
the state a cache in `checks/verified-<n>.state` (not a table; a damaged cache means a full audit, never a damaged workspace).
Synthetic inventories on the local disk (`scripts/benchmark_workspace_checks.py synthetic`), nothing new since the last check:

| Verified packs | Incremental check | Files opened | Packs re-hashed | State load (once per process) | State file |
|---:|---:|---:|---:|---:|---:|
| 10,000 | 0.06 s | 0 | 0 | 0.02 s | 1.8 MB |
| 50,000 | 0.14 s | 0 | 0 | 0.08 s | 8.9 MB |
| 100,000 | 0.29 s | 0 | 0 | 0.17 s | 17.8 MB |

What remains linear in the whole stock: the listing of the pack directory's names (about 3 µs a name) and the once-per-process
load of the state. **Projection** (not a measurement): the full audit at 13 ms per sealed pack would take about 22 minutes at 100,000
packs. `canary-driver/8` checks incrementally at every stage and reads the discovery tables once per run; `intake-controller/3`
checks incrementally after each cycle and holds the request log, qualification table and ledger across its calls.

## 9. Regressions and remaining integrity risks

Tested (`tests/test_incremental_check.py`, 31): agreement with the full audit; restart from the persisted state; weekly full audit;
garbage, torn and foreign state; a second writer of the state; torn tails; chain breaks; a changed anchor row; a cut table; a
duplicate event with a valid chain; a lost pack; a new pack that does not verify; an unfitting ledger transition; an unsupported
candidate; an interrupted request; nothing new reads no pack; a whole canary run checked fully once and incrementally after; the
held request log and ledger equal a full read and refuse what does not follow. **Remaining risk, stated:** an in-place change of an
old verified object that keeps its size is found by the rotating audit when it comes round (every pack within about
`packs / 8` checks) or by the weekly full audit, not at once; a prefix rewrite of a table behind its last verified line likewise.
The finalizer's and the canary evidence check's own audits are unchanged.

## 10. CO.RA.PAN's parallel production

CO.RA.PAN's reservoir workers ran from 05:07 local, its KISSKI supervisor ticks and preflights from 09:01; the workstation ran at
43–99 % CPU. CO.RA.PAN's advisory stayed `SHARE_NORMAL` through every wave. wc-1 was held back for an hour while the load did not
settle, then run at below-normal priority (CO.PRE.PAN's suites and the driver use one core of 24). At 10:54Z, after wc-1's requests
had ended, CO.RA.PAN reported `SHARE_SLOW`; CO.PRE.PAN had made no share contact all weekend (deferred preservation) and from then
on deferred its own heavy local work (the workspace-copy benchmark, the full suite). At about 11:30Z the operator stated that the
share was normal again; CO.RA.PAN's advisory still read `state: SHARE_SLOW` (`mode: NORMAL`) at 11:29:35Z. On the operator's
statement the two local-only steps ran (local disk, below-normal priority, no share contact). No CO.RA.PAN job was stopped, changed
or started; CO.RA.PAN's repository and its NEW_FS recovery were not touched.

## 11. Raw packs and their preservation

1,045 fetch records of the eight waves: **1,018 `PRESERVATION_PENDING`** (bytes complete and verified in the runtime workspace on
`C:`), 27 `FETCH_FAILED` (no bytes); 112 packs, 51.0 MB; **none `RAW_PRESERVED`**; nothing in the spool; no second copy. The
promotion is `canary_driver preserve-deferred` (CPD-0036) per receipt, on a weekday, behind the calendar, share, backup and CO.RA.PAN
gates, at most the bounded catch-up rate, with read-back on the primary. Until then the weekend's pages are corpus evidence that is
safe only as far as the local disk is.

## 12. The 24-hour wave

[`in2-24h-wave_REVISION_2026-11-15.md`](../intake/wave/in2-24h-wave_REVISION_2026-11-15.md): a draft plan of `intake-controller/3`
(`in3-24h-wave-draft_plan.json`, not in `config/intake/plans/`), 78 outlets, 110 channels, 20 countries, allowances by October's
volume, 24 h, a 30-minute drain, 8,000 requests; `validate_plan` PASS against the registry, the policy and 24 holds; projected about
6,600 requests. The start gate in its order: the weekday backup check and the deferred preservation; the prepared canary
`in2-20261114-canary` (/2); a first short intake under /3; the operator's decision on CPD-0038; a rebuilt readiness file and plan; a
new authorisation, weekday start, `SHARE_NORMAL`. **Open budget point:** the canary's per-outlet non-item budget reserves part for
expansion; an outlet with two origins and a redirected feed can spend it before its selected channels (`cr_crhoy` in wc-1).
Not activated; nothing scheduled.

## 13. Tests, commits, integration, push

Branch `qualification/2026-11-14-weekend`, rebased onto `origin/main` after the last wave (`618deb9`, the disarm after wc-1) and
fast-forwarded to `main`. The waves' arming, baseline, evidence and disarm commits are on `main` by the canary operator; the
driver/7 repair (`be989b3`), the uniform-shell rule and the confirmation record were merged to `main` between waves. On the branch
since `618deb9`: `8241297` variant diagnostic over both records · `14bec4c` capacity measurement · `17b27dc` extraction selection
template · `2b7605a` 24-hour revision draft · `4c72967` incremental checks and canary-driver/8 · `50d0796` intake-controller/3 ·
`15fce0d` article_html and content-quality/1 (the rule set of the first control) · `18c87ca` content-quality/2 (the rule set of the
second control) · `0c199c5` matrix, study, review, CPD-0037/0038 · `57b9b5f` the /3 draft plan · `6214b17` report and STATUS ·
`e171501` benchmark · `4f265ba` the full-suite findings fixed (decision registry rows and headings; no import-time extractor
registration; no `list.remove` in the intake) · this report's final state. The rule sets were frozen before their controls in
commits that the rebase replayed unchanged (`15fce0d`, `18c87ca`). Targeted suites during the work: 358 passed. **Full suite on the
integrated state (`4f265ba`): 2,001 passed, 15 skipped** (the documented skips of applied registry proposals and rebuilt inventory
versions); the first full run had found 7 failures, all fixed in `4f265ba`. Pushed to `origin/main`; no force push.

## 14. Open scientific decisions (the operator's)

1. Whether `content-quality/2` becomes binding for corpus admission or a release view — after the human review sample.
2. Whether texts that declare themselves AI-generated or AI-assisted belong in the corpus (until then: not admitted).
3. Whether complete briefs under 150 words are wanted.
4. Whether `article_html/0.1.0` becomes the corpus extractor (`VALIDATED` needs a gold sample).
5. Whether syndicated agency copy counts once.
6. The canary budget split for two-origin outlets; the authorisations for the first canary under `/8`, the first intake under
   `/3` and the 24-hour wave; registry amendments for the outlets the matrix names.

## 15. Status and next step

**`PARTIAL`.** Done in scope: the live qualification (99 outlets, 1,100 requests, every wave verified and disarmed), the matrix,
the extraction candidate, the quality gate with two blind controls and a human review sample, the incremental checks, `/8` and `/3`
offline, the 24-hour draft plan validated. Not done, because it is not this run's to do: the scientific activation (operator), the
preservation of the weekend's packs (a weekday), the first real runs of `/8` and `/3` (their own authorisations).
**Next step:** Monday 2026-11-16 — the first weekday backup check, then `canary_driver preserve-deferred` for each of the eight
receipts with target-side verification, then the prepared canary `in2-20261114-canary`; in parallel the operator's review of the
66-page sample and the decision on CPD-0038.
