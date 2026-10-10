# CPD-0029 — The bounded, timed intake: a controller, a binding deadline, an unattended end

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief "CO.PRE.PAN 3.0 – Governance Closure & Autonomous 24-Hour Intake" of 2026-10-10 (the intake, its budgets, its deadline, its unattended end and its start are commissioned there); the design inside those bounds by the commissioned agent |
| Kind | acquisition · operation · governance |
| Scope | one bounded intake at a time over the qualified outlets: how it is planned, authorised, started, run, ended and reported. Not a production schedule |
| Builds on / amends / supersedes | builds on CPD-0016 (canary, baseline, arming), CPD-0017 and CPD-0027 (policy, holds), CPD-0023 (delegated authorisation), CPD-0025 (readiness), CPD-0028 (the three confirmations). Supersedes nothing |
| Does not change | the fetcher, the policy gate, robots handling, the hold rule, discovery, candidate qualification, the pack, preservation, identity, extraction, labels: the controller calls them and reimplements none. `external_acquisition` stays a switch that is `disabled` except between an arming and a disarming |
| Run report | [`docs/agent-runs/2026-10-10_governance-closure-and-autonomous-24-hour-intake.md`](../agent-runs/2026-10-10_governance-closure-and-autonomous-24-hour-intake.md) |
| Evidence | `src/coprepan/intake.py`, `src/coprepan/intake_report.py`, `scripts/intake_operator.py`; `tests/test_intake.py`, `tests/test_intake_operator.py` |

Validation debt: the controller is qualified offline against a scripted outlet and a clock that does not wait. What it does
over real hours on real servers — cycle length, event volume, how new what it finds is — is what the first intake measures.
The poll intervals and the per-cycle numbers are starting values, not measured rates.

## Context

A canary asks each outlet once and ends. To learn what the qualified outlets publish in a day, they must be asked again and
again for a fixed time — and that run must not depend on the session that started it, must end by itself at a time fixed in
advance, and must leave the repository disarmed and its evidence verified without anybody watching.

## Decision

1. **A plan** (`intake.build_plan`, schema `coprepan-intake-plan/v1`) is derived from an intake-readiness file and decides
   nothing that file did not: its outlets, their usable channels, a poll interval per channel, the budgets. Left out: a
   disabled channel, a held URL, an outlet with a held origin, and a channel that lists more than 5 000 entries when the
   outlet has another (an archive must not dominate an intake). A plan is a tracked file, committed once.
2. **Poll intervals** by what a channel is: feed and news sitemap 1 h; HTML listing 2 h; sitemap index and a sitemap of more
   than 500 entries 6 h; an outlet's only channel that is an archive (more than 5 000 entries) 12 h.
3. **Budgets are ceilings, enforced at the transport** (`intake.IntakeFetcher`, a subclass of the ordinary fetcher): per
   outlet in the intake, per outlet in any hour, per origin, and in all — redirects, robots files and channel documents
   included. A request that does not fit is not made and the refusal is on record. They are counted **from the fetch records**
   at every start: a restart gets no second budget. Nothing raises them, and nothing is repeated to use them up.
4. **The deadline is fixed when the state is written** (`started_at + duration`) and never moved. No request is decided in
   the last 90 seconds (`PACE_MARGIN_SECONDS`), so that the longest pacing ends before the deadline; a request whose pacing
   would still pass it is not sent. A machine that slept through the window asks nothing when it wakes.
5. **What is requested** (`intake.selector`, passed to `run_http_acquisition` as `select_due`): never a page that was fetched
   before; first what was first listed during the intake **and** is dated inside its window (newest first); then what a
   *later* poll listed first without a date; then at most one page of the rest per outlet and cycle. A URL found for the first
   time is not thereby an article published during the intake — what a channel lists at its first poll is stock — and the
   measurement keeps the classes apart (`intake.novelty`).
6. **Cycles.** One acquisition run per cycle; in it each outlet in turn (the order rotates), one call of
   `run_http_acquisition` for its due channels and at most a few pages, then that outlet's pack is sealed, preserved and
   derived. After every outlet the state file is rewritten atomically; after every cycle the workspace is diagnosed, and a
   damaged workspace ends the intake. An outlet's error is that outlet's; more than a third of the outlets failing in one
   cycle is a systemic fault and ends the intake.
7. **Preservation first.** While a pack is pending because the target is away, no further request is made; when it returns,
   what was pending is preserved and the intake goes on.
8. **Holds** are derived from every preserved answer at every start and added to as answers come (CPD-0027). An outlet whose
   origin becomes held is passed over for the rest of the intake.
9. **The permission is re-read from disk before every request**: the switch in the policy file, and the digests of every file
   the baseline pins (registry, policy, crawler identity, schedule policy, candidate rules, the plan). Turning the switch off
   in the file stops a running intake at its next request. A restart also requires the code of the pinned commit: HEAD may
   have moved on by documents only.
10. **Authorisation** (`coprepan-intake-authorization/v1`, records under `config/intake/authorizations/`, kind
    `DELEGATED_INTAKE_AUTHORIZATION`): written once, names one plan by path and digest, ceilings the plan may not exceed,
    excluded outlets, the policy versions and the days it holds for. It stands in the place of the typed confirmations as in
    CPD-0023, adds no permission the commission did not give, and nothing in the tool can switch a check off.
11. **Start** (`scripts/intake_operator.py start`): clean tree at `origin/main`, switch `disabled`, no unfinished intake, an
    empty spool, a `CLEAN` workspace, the plan valid against registry, policy and holds → arm → the full suite on the arming
    commit → baseline of canary scope with the intake's pin (`intake.intake_pin`), frozen and pushed → the canary preflight →
    the state (the clock starts) → a scheduled task of the operating system. Whatever fails before the task runs disarms.
12. **Unattended operation.** A scheduled task runs `intake_operator.py tick` every five minutes. A tick is the controller
    while the intake runs (one at a time, by an operating-system lock), and afterwards the finalizer. It needs no session and
    no console.
13. **The end** (`intake.finalize`, then the tick): preserve what is open; close what is open; verify — nothing left open,
    every answer `RAW_PRESERVED`, every body read back from the preservation root and its digest compared, the full recovery
    diagnosis with the identity rebuild, the budgets, no request at or after the deadline —; the receipt; the measurement,
    the anomaly flags and a review package; the report; **disarm**; remove the task. The disarming is attempted whatever the
    verification says. Each step is repeatable.
14. **Unattended git is limited to the disarming**: a commit of the one policy file and a plain push. Never a forced push, a
    rebase, or another path; a refused push is reported, and the file on disk — which is what the controller obeys — is
    `disabled` either way. The report is written to the runtime workspace and brought into the checkout by a separate,
    deterministic command (`import-report`) that commits nothing.
15. **Measurement, not judgement** (`intake_report`): counts per channel, outlet and country; anomaly flags derived from a
    page's URL and the extraction's own measurements (`intake-anomaly-flags/1`); a stratified review package whose every
    human field is empty. Nothing is filtered, removed or released on a flag, and no flag is a label a person gave.

## Alternatives considered

| Alternative | Why not |
|---|---|
| a long-lived process started from the session | it ends with the session, or with a reboot; nothing would finalize or disarm |
| a Windows service | needs elevation and an installer; a scheduled task of the logged-in user is enough for a bounded run |
| many canaries in a loop | a canary's budget, receipt and baseline are per run; twenty-four of them is twenty-four armings |
| budgets kept in the state file | a file a crash can lose is not what a ceiling may rest on; the fetch records cannot be lost without the answers |
| fetch the oldest due candidate first (the planner's order) | the first poll's stock would use the whole budget before anything new was asked |
| ask again for pages fetched earlier | re-fetching is a schedule question of its own; an intake measures what is new |
| let the finalizer commit and push the report | an unattended commit of many files into a tree somebody may be working in; the import is one command for a person |
| a `--force` to start over a failed check | a check that can be switched off is not a check |

## Not decided here

- a production schedule, an intake without an end, or any standing activation of acquisition;
- the poll intervals and per-cycle numbers after the first measurement;
- what an anomaly flag means for admission, and any quality filter;
- whether a review of the package is made, and by whom;
- retention of the discovery events an intake adds.
