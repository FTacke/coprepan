# CPD-0024 — A wave's limits cap the canary budget; under a wave a canary may be smaller than five outlets

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the run commissioned by the operator's brief of 2026-10-09 ("Autonomous Acquisition: Safe Recovery, Delegated Operator & Three-Wave Execution"), §7: wave C2 is authorised for "nur diejenigen [Outlets] mit nachweislich qualifizierten HTML-Listing-Regeln", with "maximal zehn zusätzliche Item-Requests je betroffenem Outlet". The mechanism is the run's technical choice, subject to the operator's review |
| Kind | procedure · budgets |
| Scope | `canary_driver.canary_budget` when a canary runs under a wave of a delegated operator authorisation |
| Builds on / amends / supersedes | builds on CPD-0023. Amends CPD-0019's rule that a canary is five outlets or six to fifteen — **only for a canary under an authorised wave**. Supersedes nothing |
| Does not change | the budget of an interactive canary (five outlets, or six to fifteen, as before); the hard ceiling of 100 item requests; how requests are counted (hop by hop); any gate |
| Run report | [`docs/agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md`](../agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md) |
| Evidence | `tests/test_delegated_operator.py` (the cap, in both directions); the baselines of waves B and C1, whose budgets the capped function reproduces exactly |

Validation debt: the first canary under a capped budget smaller than the ordinary one is wave C2; the run report states how it went.

## Context

The brief limits wave C2 to the outlets of wave C1 whose listing rules are qualified, with ten item requests each. After C1
those are two outlets. The ordinary budget of a canary knows five outlets (sixteen item requests each) or six to fifteen; it
has no budget for two, and for five it would allow more per outlet than the brief does. The check of CPD-0023 would refuse
such a canary — correctly — and nothing could run within the commission.

## Decision

1. Under a wave of a delegated operator authorisation, **each limit of the canary's budget is the smaller of the ordinary limit
   and the wave's**: item requests per outlet, item requests in all, other requests per outlet. A wave can lower a budget and
   never raise it; the hard ceiling of 100 item requests stays above everything.
2. Under a wave, a canary may be **one to fifteen outlets**. A wave names its outlets exactly and its limits bound what is asked
   of them, which is what the minimum of five stood in for.
3. The budget is computed from the wave's limits wherever it is computed: by the tool before arming, by the driver for the
   baseline, by the driver before the first request. The check of CPD-0023 (no limit above the wave's) is unchanged and now
   holds by construction.
4. For the waves already run (B: eight outlets, C1: nine) the capped budget equals the ordinary one, so their frozen
   baselines pin the same budget under this rule.

## Alternatives considered

| Alternative | Why not |
|---|---|
| run C2 as all nine outlets of C1 again | asks seven outlets for articles the brief does not name for this stage |
| pad the canary to five outlets | the same, by another route |
| a general option for the item budget on the command line | a budget someone can pass is a budget someone can raise; the record is the only source |
| lower the ordinary budget for everyone | changes the interactive canary for no reason |

## Not decided here

- whether an interactive canary may be smaller than five outlets — unchanged: it may not;
- any budget for regular acquisition: a canary budget is not a crawl rate.
