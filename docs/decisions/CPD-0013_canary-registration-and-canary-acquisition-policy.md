# CPD-0013 — Registration of the canary subset by record; the acquisition and schedule policy of the first real canary

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the gate-closure and real-canary run (2026-10-08), which authorised that run to register unambiguous routine cases of the registry review for the canary, and gave the conservative canary acquisition policy as the operator's direction, to be worked out technically by the run. Recorded by that run; subject to the operator's review |
| Kind | policy |
| Scope | how an outlet becomes `registered`; the five outlets registered for the canary; the acquisition policy and the schedule policy **of the first real canary**; `Crawl-delay` in the policy schema |
| Builds on / amends / supersedes | builds on CPD-0006 (policy gate, crawler identity), CPD-0007 (schedule, candidate lifecycle), CPD-0009 (operation semantics). Amends the policy document schema (`coprepan-acquisition-policy/v1` → `v2`, forward-only: no `v1` policy was ever decided) and the rule "no run sets `registered`" of the registry tests |
| Does not change | the 77 outlets that stay `proposed`; any id; the crawler identity (O-2); the preservation target (O-3); the rule that no access control is ever bypassed |
| Run report | [`docs/agent-runs/2026-10-08_registry-policy-storage-real-acquisition-canary.md`](../agent-runs/2026-10-08_registry-policy-storage-real-acquisition-canary.md) |
| Evidence | `config/registry_review/canary_subset_registration_2026-10-08.json`; `config/acquisition_policy.json`; `config/schedule_policy.json`; `tests/test_registry.py`, `tests/test_policy.py`, `tests/test_schedule.py`, `tests/test_fetcher.py` |

Validation debt: nothing here has met a real server. The policy is validated by the canary it is
written for, or not at all. Listed in `docs/STATUS.md` §6.

## Context

Three things stood between the built pipeline and a first real request that an agent could
prepare: no outlet was registered (O-11), and neither the acquisition policy nor the schedule
policy was decided (O-1). The operator's brief settles both for the scope of one bounded canary and
keeps the general questions open.

## Decision

### 1. An outlet is registered by a registration record

`registered` is set only together with a dated record beside the registry
(`config/registry_review/*_registration_<date>.json`, `coprepan-registry-registration/v1`) that
names the authority, the rule of selection, every attribute set with its source and how the source
was obtained, the URL-rule version with its basis, the channel ids, and what was left unknown. A
test fails when a registered outlet has no record or differs from it. This replaces the earlier
test rule that nothing may be registered by a run; the principle behind it — registration is a
review step with evidence, never a side effect — stands.

**A run may register a routine case** when the operator's brief authorises it: the review
package's action is `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES`, it carries no warning that needs a
judgement, and its recommended id equals its imported id. Anything else is deferred to the
operator.

### 2. The canary subset (O-11)

Registered on 2026-10-08: `bo_el_deber`, `do_diario_libre`, `hn_proceso_digital`, `py_la_nacion`,
`ve_efecto_cocuyo` — five countries; RSS and sitemap channels; one sitemap-only outlet; one
digital-native outlet. Deferred: `cr_diario_extra` (a closure and change of owner in 2023 was
found; its current site was not confirmed).

- Time zone: the one zone the IANA database lists for the country. Seat, medium and type only
  where a named source states them; everything else stays `unknown`.
- URL rules `v1` are the generic rules (no significant query parameter, no variant marker). They
  were not derived from the outlet's URLs; the canary's collision diagnostic confirms or replaces
  them, by a new version.
- Channel ids follow the review package's convention. Whether a channel is alive is not known.
- **It is a technical subset, not a sample.** It supports no statement about any country's press.

`O-11` for the canary subset: `PASS`. The full registry review (77 outlets, the id convention as a
whole, the Puerto Rico attribution case) is open.

### 3. The acquisition policy of the canary (O-1) — `canary/2026-10-08.1`

| Question | Decision |
|---|---|
| what may be requested | public, unauthenticated, ordinary HTTP(S) only |
| access controls | never worked around: no authentication, paywall, bot challenge, CAPTCHA or rate limit is bypassed. A refusal is recorded and that path stops |
| `robots.txt` | `enforce`: an explicit `Disallow` denies. Absent file: allow. Unreachable file: defer |
| explicit opt-out | denies (`opt_outs`) |
| `Crawl-delay` | **binds as the minimum pause for its origin** when it is an unambiguous non-negative decimal number; the line for the crawler's own token wins over `*`. An origin that asks for more than 60 s is not fetched at all (`robots_crawl_delay_exceeds_limit`) |
| `Sitemap:` lines | may serve as a discovery source |
| pace | one process, one request at a time; at most one request per origin in 10 s |
| `Retry-After` | respected; a server that asks for more patience than a run has ends that request |
| raw bodies | preserved in full, for research and project access; never part of a distribution package; never published by this decision |
| comment feeds | the two registered comment feeds are disabled channels |

**This is an acquisition policy for one bounded canary. It is not a policy for scheduled crawling
and not a legal statement about `robots.txt`.**

`external_acquisition` stays `disabled` in the committed policy. The switch is turned in the commit
that pins the pre-canary baseline, after O-2 and O-3. Until then the decided policy denies every
external request.

Budget consequence of CPD-0009: after a process abort exactly the request in flight may be asked
again. With one request per origin in 10 s that is at most one extra request per origin and abort.

### 4. The schedule policy of the canary — `canary/2026-10-08.1`

| Outcome of a request | What follows |
|---|---|
| success (channel document or item) | not asked again within 1 day; each unchanged answer doubles the interval, up to 7 days; no revisit after 7 days from the first success |
| 404, 410 | looked at once more after 7 days, then retired |
| 429, 5xx, transport failure | 1 hour, doubling, at most 1 day; a `Retry-After` that asks for longer wins; after 3 in a row suspended for 7 days |
| refusal by the server (other 4xx), redirect not followed | 7 days |
| denied or deferred by the policy | 7 days, or the instant the policy names; a new policy version is a new question |
| permanent redirect | the candidate moves to its target; the old URL is not asked again |
| conditional requests | used where a validator and the preserved body exist |

No value adapts by itself. Within the canary nothing is asked twice except by an explicit,
recorded retry.

### 5. Policy schema `v2`

`rate_limit` has three keys: `min_interval_seconds_per_origin`, `crawl_delay` (`binding_minimum` ·
`record_only`), `crawl_delay_max_seconds`. A decided policy decides all three. The gate records the
`Crawl-delay` as written in every case and, when it binds, the number applied.

## Alternatives considered

| Alternative | Why not |
|---|---|
| wait for the full review of all 82 outlets | a canary needs five; the review of the rest does not get better by waiting for it |
| register by editing the registry alone | the earlier rule existed so that a registration has an author and evidence; a record keeps that |
| fill type, group and seat from general knowledge | an attribute without a named source is a guess |
| `robots.txt` as recorded advisory evidence only (CO.RA.PAN's stance) | the operator's direction for this canary is the conservative one |
| honour any `Crawl-delay`, however long | a run that waits an hour per request is not bounded; not fetching is the conservative answer |
| ignore `Crawl-delay` because RFC 9309 does not define it | a publisher who wrote it meant it |
| unreachable robots file: allow | a server in trouble is not a licence |
| turn `external_acquisition` on now | two gates are still open; a switch that is on while nothing can run teaches the wrong habit |
| a schedule tuned for coverage | the canary measures; it does not collect |

## Consequences

- Stage 1 (outlet registry) stays `PARTIAL`: five outlets registered, 77 proposed.
- The baseline manifest loses the blockers of O-11 and of the schedule policy; O-1 keeps one (the
  switch), with O-2, O-3 and O-4.
- What stands before the first request: the crawler identity (O-2) and the preservation target
  (O-3), both the operator's.

## Not decided here

- The registration of the other 77 outlets; the id convention for those whose id it changes.
- A policy for scheduled crawling: pace, revisit intervals, retention, access to raw copies.
- Whether `robots.txt` binds beyond this canary; opt-out handling as a process.
- The crawler identity and its public page (O-2); the preservation target (O-3).
- Per-outlet candidate rules: none exists; the generic rules apply.
