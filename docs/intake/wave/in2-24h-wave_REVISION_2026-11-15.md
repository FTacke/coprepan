# The 24-hour wave — revision after the weekend qualification (2026-11-15)

**State: DRAFT, NOT AUTHORIZED, NOT TO BE STARTED, NOT ACTIVATED.** A revision of the
[preparation of 2026-11-14](in2-24h-wave_PREPARATION.md). The draft plan `in2-24h-wave-draft_plan.json` stays as it is (no
`config/intake/plans/` file is written). What changes is shown against it, each with the weekend's evidence. Every number marked
**measured** comes from the weekend's own fetch records or receipts (`scripts/measure_weekend_capacity.py`,
`scripts/build_weekend_qualification.py`). Numbers marked **projection** are arithmetic on those measurements, not measurements.
Nothing here starts, schedules or activates anything. The wave still needs its own authorization (preparation §8), after the canary
`in2-20261114-canary`.

## 1. What the weekend measured that changes the plan

### 1.1 The request time is mostly the pacing wait, not the network (measured)

A fetch record's `fetch_started_at` is taken before the fetcher's origin pacing (`Fetcher._pace` waits inside `_request`). The
`request_seconds` of the canary measurements (median about 9.8 s) are therefore the 10-second pacing wait plus the transport. They
are not a latency. Separated:

| Wave | Requests | Wall | Transport, first request per origin (exact), median | Transport, later requests (upper bound), median | Time between records |
|---|---:|---:|---:|---:|---:|
| wq-1 | 109 | 4,513 s | 0.76 s | 1.03 s | 3,627 s |
| wq-2 | 114 | 3,946 s | 0.63 s | 0.88 s | 3,111 s |
| wq-3 | 127 | 3,934 s | 0.20 s | 0.22 s | 2,988 s |
| wq-4 | 142 | 4,387 s | 0.21 s | 0.24 s | 3,390 s |

*(Fetch records, robots included. The receipt's request count is the transport count, redirects included, and is slightly
higher. The later waves are added in the run report.)*

At most 3–8 % of a wave's wall time was spent on the network. 76–80 % lay **between** records, when no request and no pacing wait
was under way.

### 1.2 The time between records is CO.PRE.PAN's own workspace check (measured)

In wq-4 the pauses sit at the stage boundaries: 245 s after stage A, 215 s after stage B, and about 180 s before each outlet's item
stage (16 outlets). One `recovery.diagnose` of the runtime workspace (6,825 pack files, 426 MB, CLEAN) took **234 s** under the
profiler. About 58,000 file opens took 117 s of it, the layer-store manifest checks 65 s, the evidence comparison 63 s,
`verify_sealed` of 2,275 packs 30 s, and the candidate consistency check (with two loads of 883,713 discovery events) 23 s. The
canary driver checks the whole workspace after stages A and B and twice per outlet (after C and after E). The intake controller
checks it once per hourly cycle (`intake.py`, after each cycle).

Consequences:

- **For the canary**, the check, not the publishers, bounds a wave's length: 2 + 2 × outlets diagnoses of a few minutes each.
- **For the 24-hour wave**, one diagnose per cycle costs about 4 minutes of the 60 today. It grows with the workspace: every
  pack the wave adds is checked again in every later cycle, so 1,500–1,800 new packs (preparation §4) make the last cycles' check
  about a quarter longer (**projection**, linear in the pack files).

### 1.3 The capacity that interleaving would open (projection)

One request at a time stays the rule. A median transport of about 0.4 s (wq-1 to wq-4, first requests) gives one executor a
transport ceiling of about 8,700 requests an hour. An origin at the policy's 10 s minimum takes at most about 345 an hour. It takes
**about 25 origins in rotation** to keep the one executor busy. October's cycle served outlets one after another: within an outlet,
each request waited its 10 s, so 71 outlets × about 4.4 requests × 10 s ≈ 52 minutes of pacing made the hourly cycle (preparation
§2). Interleaving uses that wait for the next origin. It does not raise any origin's rate.

## 2. Changes to the plan (proposal)

| Item | Draft of 2026-11-14 | Revision | Evidence |
|---|---|---|---|
| Order of requests within a cycle | outlet after outlet | **interleaved**: a round-robin over the outlets that have something due, one request each per turn, and the next origin whenever one is still inside its pacing interval. Each origin keeps its pacing and Crawl-delay, and the executor still makes one request at a time. | §1.1, §1.3 |
| Item allowance per outlet and cycle | 3 for every outlet | **by measured volume**: `min(cap, ceil(1.5 × new articles per hour observed for the outlet))`, at least 3, with a cap of 30. An outlet without an observation keeps 3. | the October loss is concentrated where the allowance of 3 was below the publishing rate: `uy_ladiaria` 626 new in 24 h (about 26 an hour), `ar_clarin` 458 (about 19), `ar_la_nacion` 232 (about 10) |
| Item selection | the planner's order, backlog 0 | **newest listed first** (`item-selection/1` of canary-driver/7, CPD-0036 decision 6) for the new pages; backlog stays 0 | wq-1 under the oldest-first order requested pages of 2009–2022; wq-3 and later under newest-first requested pages of the day |
| Deadline handling | none: what a cycle does not reach waits for the next cycle's allowance | a **cycle deadline**: the share of the hour left after the polls. Items still due at the deadline are carried into the next cycle ahead of new ones of the same outlet, never dropped. After the last cycle comes a **drain period** of 30 minutes with no new polls, for the items listed in the final hour. Each item left unfetched at the end is recorded with its cause (`allowance`, `deadline`, `policy`, `access`). | the 1,792 new articles left unfetched in October had no recorded cause |
| Workspace check per cycle | `recovery.diagnose` of the whole workspace | **scoped to the cycle's own packs** (the `master_scope` mechanism the finalizer already has, extended to the pack and ledger checks), plus a full diagnose at the start and at the end of the wave | §1.2 |
| Total requests | 8,000 | 8,000 (unchanged) | volume budgets move items to the high-volume outlets. October's 4,412 new articles plus about 2,400 polls fit within 8,000 (**projection**) |
| Per-outlet ceilings | 80 items, 6 per hour | **by volume**: 1.5 × the outlet's October new articles, at least 80, at most 900; per hour, its cycle allowance | `uy_ladiaria` would need about 940 for full coverage. The cap of 900 leaves the uncertain part (its index sitemap may give modification dates, preparation §2) visible as a measured shortfall |

**Projection of the load:** about 300 requests an hour on average (4,412 new articles ÷ 24 plus about 100 polls an hour), spread
over 71 origins. That is under 1 request per origin per minute on average. The busiest outlet's peak, about 40 an hour, is still
a ninth of the 10-second minimum. Executor transport would be about 2 minutes an hour.

## 3. What must exist before such a wave (engineering, each with tests)

1. **Interleaving in `intake-controller`** (a new controller version): a per-origin ready queue, the fetcher's pacing as the only
   wait, budgets and holds unchanged. Offline tests with several loopback origins: no origin's interval is broken, a hold stops
   only its origin, a restart resumes the queue from the state file.
2. **Volume-based allowances in the plan schema** (`items_per_outlet_cycle` per outlet), with the volume observation named in the
   plan (the October measurement or a later one), validated by `validate_plan`.
3. **The deadline, carry-over and drain**, and the recorded cause of each unfetched item in the wave's measurement.
4. **A scoped per-cycle workspace check**, plus a regression test that a damaged pack outside the scope is still found by the
   wave's closing full check.
5. **The fetch record's pacing** (optional but cheap): a `paced_until` instant beside `fetch_started_at`, so that latency is
   measured, not bounded. That is a change of the fetch-record schema and needs its own CPD.

None of these is built. The canary `in2-20261114-canary` does not depend on them.

## 4. Unchanged

Duration 24 h; hourly cycle; poll intervals by class; the abort criteria, monitoring and coverage measurement of the
preparation §7; the authorization of §8 (weekday start, canary `PASS` first, CO.RA.PAN `SHARE_NORMAL` at the start, no recurring
acquisition); the criteria for continuous operation (§9, CPD-0025).

## 5. Sources outside the plan after the weekend

Which outlets go into a rebuilt plan, and through which channel, follows from the four dimensions of the weekend matrix
(`docs/intake/qualification/weekend_qualification_2026-11-15.md`), not from a single readiness rating. An outlet whose channels
are `STALE_CHANNEL` or `NO_ENTRIES`, or whose raw acquisition is a `UNIFORM_SHELL`, gives a 24-hour wave nothing to measure. It
stays outside the plan until a registry amendment with evidence gives it a current channel.
