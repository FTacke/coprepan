# The 24-hour wave — revision after the weekend qualification (2026-11-15)

**State: DRAFT PLAN BUILT AND VALIDATED, NOT AUTHORIZED, NOT TO BE STARTED, NOT ACTIVATED.** A revision of the
[preparation of 2026-11-14](in2-24h-wave_PREPARATION.md). The draft plan is
[`in3-24h-wave-draft_plan.json`](in3-24h-wave-draft_plan.json) (summary: [`in3-24h-wave-draft_summary.json`](in3-24h-wave-draft_summary.json)),
built by `scripts/build_24h_revision_plan.py`. It is **not** in `config/intake/plans/`, where a plan is written once. The older
draft `in2-24h-wave-draft_plan.json` (intake-controller/2) stays as it is. Every number marked **measured** comes from the
weekend's fetch records or receipts. Every number marked **projection** is arithmetic on October's measurement. Nothing here
starts, schedules or activates anything.

## 1. What the weekend measured that changed the plan

- **The request time is mostly the pacing wait (measured).** The canary measurements' `request_seconds` (median about 9.8 s) are
  the 10-second pacing wait plus the transport: `fetch_started_at` is taken before `Fetcher._pace`. The exact transport of a first
  request to an origin had a median of 0.2–0.8 s across the waves (`scripts/measure_weekend_capacity.py`).
- **The workspace check, not the publishers, bounded a wave (measured).** 76–80 % of a wave's wall time lay between fetch records.
  At each checkpoint the driver ran a whole-workspace `recovery.diagnose`: 234 s for one run on 6,825 pack files, and
  2 + 2 × outlets runs per wave. The intake controller ran one per hourly cycle. Repaired by CPD-0037; see §3.
- **Sequential outlets waste the origins' intervals (measured offline).** With two loopback outlets at the policy's 10 s and a
  clock that moves only while waiting, the pacing waits for the same twelve items were 140 s under /2 and 80 s under /3.

## 2. The draft plan (`in3-24h-wave-draft`, intake-controller/3)

| | Value | Basis |
|---|---|---|
| Outlets / channels / countries | 78 / 110 / 20 | the weekend matrix's `QUALIFIED` and `QUALIFIED_WITH_LIMITS` outlets that the intake-readiness file of 2026-10-10.1 holds; `co_elcolombiano`, `cr_diario_extra` and `uy_el_pais` are qualified by the weekend but not in that readiness file, so they are left out until it is rebuilt |
| Holds | every hold derived from the stored evidence (24) left out when the plan is made | `validate_plan`: **PASS** against the registry, the policy and those holds |
| Duration / cycle / drain | 24 h / 1 h / the last 30 min poll nothing | the drain period requests what the last polls listed |
| Allowance per outlet | items per cycle = min(30, max(3, ⌈1.5 × new per hour⌉)); per hour the same; in all min(900, max(80, ⌈1.5 × new in 24 h⌉)) | October's new articles per outlet: dated inside the window plus first listed undated at a later poll. 47 outlets keep 3 per cycle; the largest are 29 and 30 per cycle (`uy_ladiaria`: 626 new in October) |
| Backlog per cycle | 0 | stock is not what the wave measures |
| Selection | newest listed first, never a page fetched before | `selector` (as /2), handed out one item per outlet and turn |
| Total requests | 8,000 | **projection**: 4,320 item requests if October repeats, plus about 2,300 channel polls, ≈ 6,600 |
| Items left at a cycle's end | stay due; counted per outlet in the state (`items_left_at_cycle_end`) | /3 |
| Check after a cycle | incremental (CPD-0037); a full audit at the start when there is no check state, after any finding, and weekly | the finalizer's audit of its own packs is unchanged |

**Expected load (projection from October, not a measurement).** About 280 requests an hour on average, spread over about 80
origins: less than one request per origin every ten minutes. The busiest outlet's allowance of 30 an hour is a twelfth of what an
origin's 10-second interval permits. The executor spends about 2 minutes an hour on transport. Each cycle's incremental check
costs well under a second (0.06 s at 10,000 verified packs, 0.29 s at 100,000, measured synthetically). Preservation of about
4,300 pages, roughly 1,500–2,000 packs, follows the bounded catch-up of CPD-0035 on the share.

## 3. What was built for it (2026-11-15, tested offline)

| Proposal of the morning | State |
|---|---|
| Interleaving outlets | **built**: `intake-controller/3` (CPD-0037). Polls outlet after outlet, then items round the outlets, one per outlet and turn; one request at a time; pacing and Crawl-delay per origin unchanged |
| Allowances by volume | **built**: an `allowance` per outlet in a /3 plan, none above the budget's maxima (`validate_plan`) |
| Newest first, backlog 0 | **built** (the /2 selector, per outlet and cycle) |
| Cycle deadline, carry-over, drain | **built**: what is due at the cycle's end stays due and is counted; `drain_seconds` |
| Scoped per-cycle workspace check | **built**: `incremental_check` instead of the whole-workspace diagnose, with a rotating fixity audit and a weekly full audit |
| The request log, qualification table and ledger read once per process | **built** (`RequestLog`, `Ledger.refresh`) |
| A recorded `paced_until` in the fetch record | **not built**: a fetch-record schema change, for its own decision |
| Two-origin outlets and the canary's non-item budget | **open**: under the canary budget (8 non-item requests per outlet, part reserved for expansion), `cr_crhoy`'s two robots files and a redirected feed left nothing for its news sitemap (`canary_budget_exhausted`, wc-1). The intake has no such per-outlet reservation; the canary budget's split is for a later decision |

## 4. Start gate (all of them, in this order)

1. The first weekday backup check after the weekend, and the deferred preservation of the weekend's packs
   (`canary_driver preserve-deferred`, CPD-0036) behind every weekday, share, backup and CO.RA.PAN gate, with target-side
   verification.
2. The prepared canary `in2-20261114-canary` (intake-controller/2) with its `PASS`, under its own authorisation.
3. A first real intake under intake-controller/3: a short canary of a few outlets and a few hours, its own authorisation. /3 has run
   only offline so far.
4. The operator's decision on the content-quality gate (CPD-0038). It does not gate acquisition, but it says which of the 24 hours'
   pages count.
5. A rebuilt intake-readiness file (it predates the weekend: three newly qualified outlets are missing, every hold must be in it)
   and a plan rebuilt from it.
6. A `coprepan-intake-authorization/v1` record naming the rebuilt plan, its sha and the ceilings of §2; a weekday start;
   CO.RA.PAN `SHARE_NORMAL` at the start; no recurring acquisition.

## 5. Unchanged

The abort criteria, monitoring and coverage measurement of the preparation §7; the criteria for continuous operation (§9,
CPD-0025); every access, robots and TDM decision; the pending bounds and free-space floors of CPD-0033/0035.
