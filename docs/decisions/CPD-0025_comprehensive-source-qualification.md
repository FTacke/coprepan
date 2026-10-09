# CPD-0025 — Qualifying the whole known source stock: registration by rule, amendments, and four small repairs

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief "CO.PRE.PAN 3.0 – Comprehensive Source Qualification, Registry Expansion & Intake Readiness" of 2026-10-09 ("Dieser Auftrag autorisiert einen zeitlich auf diesen Run begrenzten, technisch kontrollierten Qualifizierungsbetrieb für sämtliche bereits im Repository dokumentierten Outlet-Kandidaten"; the budgets of four item requests and eight other requests per outlet and 1 800 requests in all). The rules, the mechanisms and the repairs are the run's technical choices, subject to the operator's review |
| Kind | governance · registry · discovery |
| Scope | how an outlet hypothesis becomes a registered outlet for qualification; how a registration is amended; the URL key for a nameless query; the scope of an allow rule; the URL that is requested; the size of an authorised wave |
| Builds on / amends / supersedes | builds on CPD-0013 (registration by record), CPD-0023, CPD-0024. Amends CPD-0003 (the URL-key rule: one declared extension), CPD-0020 §3 (an allow rule applies to listed candidates only), CPD-0024 §2 (a wave is at most 24 outlets, not 15). Supersedes nothing |
| Does not change | any gate; the hard ceiling of 100 item requests per canary; the policy and its research-TDM layer; any URL key of an outlet that does not declare the extension; any registration record, baseline or receipt of the past |
| Run report | [`docs/agent-runs/2026-10-09_comprehensive-source-qualification-and-intake-readiness.md`](../agent-runs/2026-10-09_comprehensive-source-qualification-and-intake-readiness.md) |
| Evidence | `config/source_discovery/qualification_dispositions_2026-10-09.json`; `config/registry_review/qualification_registration_2026-10-09.json`, `findings_f11_f12_amendment_2026-10-09.json`; the tests named below; the waves' baselines and receipts (run report) |

Validation debt: what the registrations and the repairs yield on real servers is what the qualification waves measure; the
run report states it. A registered outlet is not an outlet that yields articles.

## Context

After 2026-10-09 the repository knew 145 outlet hypotheses — 91 in the registry (22 registered) and 54 from research alone —
and 14 outlets with verified acquisition. Earlier registrations were small, reviewed selections. The operator now asks that
the whole stock be either qualified or deferred with a concrete reason, by bounded real requests, and gives the budget. The
policy gate requests nothing of an outlet that is not registered, so a hypothesis can only be tested once it is registered:
registration here is the precondition of a test, not its result.

## Decision

1. **Registration by rule.** `scripts/build_qualification_proposal.py` gives every hypothesis exactly one disposition by
   rules stated in the script, in order: already registered; `LEGAL_HOLD`; `CLOSED`; `DOMAIN_CHANGE`; `IDENTITY_OPEN`;
   `NO_ORIGIN` / `HOST_HELD`; `NO_EVIDENCED_CHANNEL`; else `REGISTER`. An address inferred from how a content system usually
   looks is a guess and is not registered or requested. The dispositions are a tracked file; the proposal is applied by the
   existing applier, with a registration record. Different titles are never merged because they share an owner.
2. **Four stages stay apart**: `REGISTERED` (a record exists), `TECHNICALLY_QUALIFIED` (a channel document of the outlet was
   read from its server and listed items), `ACQUISITION_VERIFIED` (item pages preserved, verified and replayed in one bounded
   run — at the qualification budget of four requests, **at least three**; the earlier threshold of five belonged to budgets
   of ten and more and is kept for those runs), `OPERATIONALLY_STABLE` (three runs on three days within fourteen days).
3. **Amendments.** A registration record is not rewritten. `scripts/amend_registration.py` adds to a registered outlet — an
   origin at the end of its list, a new version of its URL rules, a channel — by a dated amendment record with reason and
   evidence. It removes nothing. The registry test folds amendments onto registrations.
4. **A nameless query can be declared significant** (F12). The empty name in `significant_query_params` keeps query components
   that have no `=`; named parameters are dropped as before. Only an outlet that declares it is affected
   (`uy_montevideo_portal-url-rules/v2`); every other key is byte-identical, so the rule set keeps its id.
5. **An allow pattern applies to what a listing names** (`candidate-filter-generic/3`). It no longer narrows the feed or the
   sitemap of the same outlet; reject rules still apply to every candidate.
6. **`utm_` parameters are not requested** (`channel-parser/6`, F13). The event keeps the URL as listed and says what was
   removed; a parameter an outlet declares significant is kept. Measured cause: five articles of `ni_nicaragua_investiga` cost
   ten requests on 2026-10-09 because the site redirects the tags away.
7. **A wave is at most 24 outlets** — what the ceiling of 100 item requests leaves at four per outlet.
8. **The run's total** of 1 800 requests is held by construction: the waves of its authorisation record allow 1 164.

## Alternatives considered

| Alternative | Why not |
|---|---|
| request the channel hypotheses of unregistered outlets by a separate probe tool | a second path to a publisher beside the policy gate; the gate is the point |
| register pattern-inferred addresses too | 51 addresses nobody has seen; a guess is not requested |
| a new field for the nameless query | changes the registry schema of every outlet for one case; a reserved name is declared per outlet and versioned |
| a new id for the URL-key rule set | would re-key nothing and relabel everything; no existing key changes |
| per-channel candidate rules | the distinction that matters is listing or not, which the filter already knows |
| strip every known tracking parameter | only `utm_` is evidenced here; the others can be added when a run shows them |

## Not decided here

- whether any outlet belongs in the corpus: kind of outlet, owner, editorial independence are left unknown where not evidenced;
- the deferred hypotheses: each needs what its disposition names (an origin, an evidenced channel, an identity or legal decision);
- any intake: a 12- or 24-hour run is a separate step with its own authorisation.
