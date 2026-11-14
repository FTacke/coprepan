# The 24-hour wave under `intake-controller/2` — preparation (concept, draft plan, budgets)

**State: PREPARED, NOT AUTHORIZED, NOT TO BE STARTED.** Prepared 2026-11-14 from stored evidence only (no request). It follows
the first canary `in2-20261114-canary`, which has **not run yet**: every number of the canary is still owed, and the plan below is
re-built from a then-current readiness file and the canary's evidence before it is put to the operator. A successful wave does not
activate recurring acquisition; `OPERATIONALLY_STABLE` stays bound to CPD-0025 (three verified runs on three days).

Sources: the [source-health matrix](../source_health/source_health_2026-11-14.md) (`scripts/build_source_health.py`), the 24-hour
intake `in1-20261010-24h` (`docs/intake/reports/in1-20261010-24h/`), CPD-0029, CPD-0033, CPD-0035.

## 1. What the wave is to measure

1. **Technically and operationally:** whether every planned source is acquired and preserved over a full day under the real
   storage, backup and CO.RA.PAN conditions — preservation on the share, the bounded catch-up after a `SHARE_SLOW`/`RECOVERING`, the
   next weekday backup carrying the new objects, no hold, no fall of the controller, a `PASS` receipt.
2. **Methodically (coverage):** what share of the observably new articles is found and fetched, per outlet; where missing channels,
   stale channels, rules, budgets or poll intervals prevent good coverage. The request count is **not** a success criterion.

## 2. What the October intake shows about its limits (measured from its stored measurement)

- **The per-outlet cycle allowance bound, not the totals.** `items_per_outlet_cycle` 3 over 24 cycles: the most an outlet received was
  72 item requests (6 outlets at 70–72, 27 at ≥ 60); the outlet ceiling (120) and the total (12,000; 7,173 used) were never reached.
- **New articles were left behind:** 4,412 articles first listed during the intake and new by their channel's date or a later poll;
  2,620 fetched; **1,792 not fetched (41 %)**, in 28 outlets, ≥ 20 each in 17: `uy_ladiaria` 572 of 626, `ar_clarin` 389 of 458,
  `ar_la_nacion` 163 of 232, `es_la_vanguardia` 90 of 158, `cl_la_tercera` 81 of 153, `co_semana` 50, `ec_el_universo` 48,
  `co_el_espectador` 48, `ar_perfil` 44, `ar_rio_negro` 42, … (the matrix's `new_dated_left_unfetched`). `uy_ladiaria`'s count comes
  from a sitemap index whose dates may be modification dates: a candidate for review, not a proven loss.
- **29 % of the fetched pages were not new:** 1,061 of 3,681 2xx pages were stock (466 known before the intake, 577 dated before it, 18
  undated at a first poll) — the backlog allowance of one page per outlet and cycle.
- **The cycle length is the structural limit.** One request at a time and at least 10 s per origin, outlets one after another: a cycle
  of 87 outlets took about an hour. More items per cycle lengthen the cycle; they do not add capacity. Real capacity needs interleaving
  of outlets (one request at a time, but the next origin while one waits) — an engineering change of the controller, §6.
- **15 qualified outlets gave no new article** (their channel lists only entries dated before the window, or stock only), and one
  (`pe_elperuano`) no page at all; their polls and backlog requests bought nothing.

## 3. Scope of the draft

`docs/intake/wave/in2-24h-wave-draft_plan.json` — **a draft outside `config/intake/plans/`** (a plan there is written once);
`plan_sha256` `e7573007…0693`, built with `intake_operator.py plan` from readiness `2026-10-10.1`: **71 outlets, 101 channels, all 20
countries** (RSS 66, sitemap 27, sitemap index 7, section page 1) — every qualified outlet the matrix rates `READY` (59),
`READY_WITH_LIMITATIONS` (8) or `REPAIR_REQUIRED` (4; raw acquisition does not depend on the experimental extractor, their pages are
preserved for a later extraction). Left out: `ve_efecto_cocuyo` (`HELD`) and the 15 `REQUALIFICATION_REQUIRED` (§5). Validated
offline: `validate_plan` **PASS** against the registry, the acquisition policy and the 20 holds derived from every stored answer.

## 4. Budgets (proposal; each change against October named)

| Parameter | October | Proposal | Why |
|---|---|---|---|
| duration | 24 h | 24 h | comparable with October; a 30-hour variant only if the operator wants a second night |
| cycle | 1 h | 1 h | the cycle is bound by sequential pacing; shorter cycles would overrun |
| poll interval by class | feed/sitemap 1 h, index 6 h, listing 2 h, bulk 12 h | unchanged | no evidence that a channel's stream outpaces an hourly poll except the outlets in §2, which are budget-bound, not poll-bound |
| items per outlet and cycle | 3 | 3 | more would lengthen the cycle (§2) |
| backlog items per outlet and cycle | 1 | **0** | stock is not what the wave measures; frees up to one request per outlet and cycle for new articles (29 % of October's pages were stock) |
| item requests per outlet | 120 | **80** | 3 × 24 = 72 plus margin; the ceiling was never the binding limit |
| item requests per outlet and hour | 10 | **6** | 3 per cycle; a ceiling that still binds a restart burst |
| item requests per origin | 150 | **100** | above the outlet ceiling, as before |
| total requests | 12,000 | **8,000** | 71 × 72 items ≈ 5,100 plus about 2,400 channel polls and robots (October: 2,566 polls for 87 outlets) |

**Expected load (projection from October, not a measurement):** about 2,600–3,000 new article pages, 1,500–1,800 packs, about 300 MB
(176 KiB per pack on average), about 3,400 objects plus their manifests on the share — about 20 minutes of share time over the day at
~260 ms per small file and 3.7 MiB/s. The next weekday backup copies those objects (two reads of the source each, about 60 minutes at
October's 0.53 s per object; inside its 90-minute budget, otherwise `STOPPED` and resumed the next weekday). Spool and pending bounds
(5,000 packs / 72 h) cover a share outage of about three days of such a wave.

**Fairness:** every outlet has the same allowance; the plan rotates the outlet that is served first in each cycle. The high-volume
outlets of §2 remain budget-bound; their loss is measured, not hidden (the receipt and the matrix's coverage columns).

## 5. Requalification before the wave (a separate authorization; prepared, not made)

The 15 outlets without new articles need their **news channel** found; the evidence shows which kind of fault:

| Outlet | Finding (24-hour intake) |
|---|---|
| `cl_biobiochile`, `hn_el_heraldo`, `hn_la_prensa`, `pa_el_siglo`, `pa_laestrelladepanama`, `py_ultima_hora`, `cu_juventud_rebelde` | the registered (index) sitemap lists only entries dated before the window: an archive or a section listing (`hn_el_heraldo`'s lists login, privacy and notification pages) |
| `ar_pagina12`, `gt_elsiglo`, `hn_contracorriente`, `hn_criterio`, `py_noticias_cde`, `ve_eluniversal` | stock only: nothing first listed during the intake was new |
| `hn_radio_progreso` | no page in 24 polls |
| `pe_elperuano` | robots unreachable at every poll (HTTP 404 on two documents) |

**Safe check request (for a separate authorization):** per outlet at most 6 requests — `robots.txt`, the home page, the sitemap or
feed URLs named in `robots.txt` or the home page's `<link rel="alternate">`, at most two candidate channel documents — at least 10 s
apart, within the robots and access decisions in force, no held origin; at most 100 requests in all; result: a registry change
proposal per outlet (a new channel URL with its evidence), reviewed before any plan uses it. No new publisher.

**Extraction review (no live request):** `pa_diaadia` (all pages empty), `hn_criterio`, `mx_el_universal`, `pa_metro_libre`,
`ar_la_nacion` — the review cases are in the matrix; the cause is evidenced in the run report §5 (an article container inside a
page-level `<header>`; teaser `<article>` cards before the article). A change of the experimental baseline extractor is a decision of
the extraction evaluation (CPD-0018), with two measured candidate rules.

## 6. Robustness for a long unattended run

| Question | State |
|---|---|
| End-to-end request timeout | **repaired 2026-11-14**: `FetchLimits.total_seconds` (120 s in the canary and intake limits) besides the 30 s socket timeout; tested with a slow-drip server |
| Adaptive slower polling after repeated channel failures | open; a failing channel costs at most one request per poll interval (hourly) within the budget; proposal: double a channel's interval after three consecutive failures, capped at 6 h, reset on success — a change of the poll regime (CPD-0029), for the operator |
| Own budget for non-item requests per outlet | open; bounded by the total and the discovery limits (4 documents, 4 MiB, depth 2 per poll); proposal: `other_requests_per_outlet` in the plan schema (as the canary budget has) — a plan-schema change |
| Evidence-derived holds that never expire | an access decision: unchanged; proposal for the operator: a recorded review date per hold, lifted only by a new qualified observation under a separate authorization |
| Restart of the task or the process | resumes from the state file; budgets recounted from the fetch records; the catch-up budget is in the state file (tested, CPD-0035) |
| Task identity when the account is logged off | the intake's task and `COPREPAN_PreservationBackup` are registered `Interactive`: they run only while the account is logged on, and the October report names "the task stops at log-off". A logged-off run needs the task registered to run whether the user is logged on or not, which stores the account's credentials in the Task Scheduler — **an operator decision**; nothing here reads or stores a secret |
| CO.RA.PAN's NEW_FS recovery (its Session A) | CO.PRE.PAN never reconnects or resets a session; the share gate backs off after a failed contact, and transfers wait while CO.RA.PAN is degraded, slow or recovering (CPD-0035); the wave's backlog is caught up at most 200 packs an hour afterwards |
| Outlets processed one after another | the capacity limit of §2; interleaving origins is the engineering item that would let the high-volume outlets be covered — to be designed and tested before a wave meant to measure full coverage |

## 7. Abort criteria, monitoring, measurement

- **Abort (stop file):** a hold on an origin of the plan beyond named exceptions; any 429; more than a third of the outlets failing in
  a cycle (the controller stops itself); a free-space floor; the pending bounds; any read-back or fixity failure; a CO.RA.PAN health
  problem that names CO.PRE.PAN; the operator's judgement.
- **Monitoring:** `python scripts/storage_contract.py status` (`operations`), `python scripts/intake_operator.py status --intake …`,
  CO.RA.PAN's advisory in the same block; nothing else needs to be read during the run.
- **Coverage measurement:** per outlet, new articles found vs. fetched (the matrix's columns, rebuilt from the wave's measurement),
  stock fetched (should be 0), channel availability, the delay from publication to request; quality: the anomaly flags, with review
  cases drawn for a person — no automatic flag is a scientific judgement.

## 8. The authorization the wave would need

A new `coprepan-intake-authorization/v1` record (the canary's [draft](../canary/in2-20261114-canary_AUTHORIZATION_DRAFT.json) is the
form) naming the rebuilt plan, its sha, the ceilings of §4, and the conditions: weekdays only for its start; the canary
`PASS` first; the requalification of §5 decided (or its outlets left out); CO.RA.PAN `SHARE_NORMAL` at the start; no recurring
acquisition.

## 9. Criteria for a later continuous operation (unchanged in substance from the canary preparation §7)

Source stability over three verified runs on three days (CPD-0025); real preservation of every answer; no uncovered backlog; weekday
backups `BACKUP_VERIFIED` with the new objects; no CO.RA.PAN impairment observable in its own status; status and errors explained
without logs; a production schedule policy (gate O-1) and an acquisition authorization decided by the operator.
