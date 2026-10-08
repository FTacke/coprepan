# CPD-0017 — Scientific TDM acquisition and robots policy: three layers, access controls that end a path

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the research-TDM policy run of 2026-10-08, which ordered that robots evidence, research-TDM eligibility and the acquisition decision be kept apart, that a `Disallow` alone no longer deny, and that technical access controls never be worked around. Recorded and worked out technically by that run; subject to the operator's review and to a review by the university's legal office, which has **not** taken place |
| Kind | policy |
| Scope | what a robots file, a machine-readable reservation, a technical access control, a publisher's direct opt-out and a legal review hold each mean for a request of this project's crawler |
| Builds on / amends / supersedes | builds on CPD-0006 (policy gate), CPD-0014 (crawler identity, protected storage), CPD-0016 (driver, canary baseline). **Amends CPD-0013 §acquisition policy**: "an explicit `Disallow` denies" is replaced by §2–§3 below; the policy schema goes `coprepan-acquisition-policy/v2` → `v3` (forward-only: no request was ever made under `v1` or `v2`); the policy version goes `canary/2026-10-08.1` → `canary/2026-10-08.2`. Amends the transport rule of CPD-0006 §3 for 429 (§4). Supersedes nothing |
| Does not change | the budgets, the pace, `Crawl-delay` as a binding minimum, the five outlets, the storage roles, any identifier or stored artefact; the rule that no access control is ever bypassed — it is made observable and enforced |
| Run report | [`docs/agent-runs/2026-10-08_research-tdm-acquisition-policy.md`](../agent-runs/2026-10-08_research-tdm-acquisition-policy.md) |
| Evidence | `tests/test_research_tdm_policy.py`, `tests/test_policy.py`, `tests/test_fetcher.py`, `tests/test_canary_driver.py`; the sources of §1 |

Validation debt: the policy has met no real server. **This document is not legal advice** and claims
no universal entitlement; it records which texts were read, what this project concludes from them
for its own conduct, and where the reading ends.

## Context

Under CPD-0013 a `Disallow` line denied a request, with the same finality as a server's refusal.
That treated two different things as one: a robots file is a publisher's machine-readable request
to crawlers; a login, a 403 or a CAPTCHA is a fact of access. It also left unstated on what basis a
university project reads public press pages at all. The operator ordered both to be stated.

## Decision

### 1. What was read (primary sources only), and what follows

Retrieved 2026-10-08 from the publishers of the texts; the digests are of the files as retrieved.

| Source | Retrieved from | SHA-256 of the retrieved file |
|---|---|---|
| UrhG § 44b | gesetze-im-internet.de `/urhg/__44b.html` | `ad76fc4b77b7e1ca7d22b56472dbcc7f033b9b6c6186e71d1458fe3877aebec1` |
| UrhG § 60d | `/urhg/__60d.html` | `fe5d6824fb24d3ce425a038c2dd484fb0e91dc503475a1a4f353a98aa020a321` |
| UrhG § 60g | `/urhg/__60g.html` | `af0e579d54f78962b7e961c8e1c209a6f909580e5031d968b452e49e6338b3a5` |
| UrhG § 87c | `/urhg/__87c.html` | `234794995b359e60a248c28ec9e8db03dc1d86ac618e42806dd1e83ff1063a56` |
| UrhG § 95b | `/urhg/__95b.html` | `61b75eeeb4bae442b56772a5a5719b173204798b7c1221ad0baa874691cb13af` |
| Directive (EU) 2019/790, OJ L 130, 17.5.2019, p. 92 (English) | Publications Office, `publications.europa.eu/resource/celex/32019L0790` | `fb2e98e5b0028eda05de854dfc82f4c0eccbad7d02a82f82885091121fedf860` |
| RFC 9309, Robots Exclusion Protocol | `rfc-editor.org/rfc/rfc9309.txt` | `f633915daaa15b943cae56545d333bcf3ba4d156599e4555499686d6699fb207` |

**EVIDENCE** — what the texts say.

- § 60d (1) UrhG permits reproductions for text and data mining "(§ 44b Absatz 1 und 2 Satz 1)" for purposes of
  scientific research. It refers to § 44b (1) and (2) sentence 1 — works that are "rechtmäßig zugänglich" — and
  **not** to § 44b (3).
- § 44b (3) UrhG: uses "nach Absatz 2 Satz 1" are permitted only if the rightholder has not reserved them; for works
  accessible online a reservation is effective only "in maschinenlesbarer Form". The reservation is written for
  the general permission of § 44b.
- § 60d (2) names "Hochschulen" among the research organisations entitled, provided they pursue non-commercial
  purposes, reinvest all profits in research, or act under a state-recognised public-interest mandate.
- § 60d (5): such copies may be kept "mit angemessenen Sicherheitsvorkehrungen gegen unbefugte Benutzung" as long
  as needed for research or for the verification of scientific findings. § 60d (4): making them available is limited
  to a defined circle for joint research and to individual third parties for quality review, and ends with it.
- § 60d (6): rightholders may take the measures required so that the security and integrity of their networks and
  databases are not endangered.
- § 60g (1): a rightholder cannot rely on agreements that restrict or prohibit the uses of §§ 60a–60f to the
  detriment of those entitled. § 87c (1) no. 5 and (6) carry the research permission and § 60g (1) over to the database right.
- § 95b (1) no. 11 obliges a rightholder who applies technical measures to give beneficiaries of § 60d — "soweit sie
  rechtmäßig Zugang … haben" — the necessary means; § 95b (2) gives a **claim** for that. The text gives no licence
  to remove a measure oneself.
- Directive 2019/790 Art. 3 (1): an exception for research organisations for text and data mining "of works or other
  subject matter to which they have lawful access"; Art. 3 (2): copies "shall be stored with an appropriate level of
  security" and may be retained "including for the verification of research results"; Art. 3 (3): rightholders may
  apply measures for the security and integrity of networks and databases, not beyond what is necessary.
- Art. 4 (3): the general exception applies on condition that the use "has not been expressly reserved by their
  rightholders in an appropriate manner, such as machine-readable means"; Art. 4 (4): "This Article shall not affect
  the application of Article 3". Art. 7 (1): contractual provisions contrary to Art. 3 are unenforceable.
- Recital 14: "Lawful access should also cover access to content that is freely available online." Recital 16:
  security measures could ensure "that only persons having lawful access to their data can access them, including
  through IP address validation or user authentication". Recital 18: the general exception "should leave intact the
  mandatory exception for text and data mining for scientific research purposes".
- RFC 9309 §1: "These rules are not a form of access authorization." §2.2.2: the most specific match (most octets)
  is used; on an equivalent `allow` and `disallow` the `allow` should be used. §2.3.1.1: a crawler that has
  downloaded the file "MUST follow the parseable rules". §2.3.1.3: 4xx — "unavailable", the crawler may access any
  resource. §2.3.1.4: 5xx — "unreachable", complete disallow is to be assumed. §3: the protocol "is not a substitute
  for valid content security measures". The RFC does not mention `Crawl-delay`.

**INTERPRETATION** — this project's reading, not a court's.

- The permission for scientific text and data mining is not made conditional on the absence of a machine-readable
  reservation; the reservation belongs to the general exception (§ 44b (3); Art. 4 (3)–(4); recital 18).
- A robots file is, by the standard's own words, not access authorisation, and none of the statutory texts read names
  it. A `Disallow` is therefore treated as the publisher's stated preference towards crawlers: evidence that is always
  read and recorded, not a lock.
- What the texts do tie the permission to is *lawful access*, and they treat authentication and IP validation as the
  rightholder's legitimate means (recital 16; § 60d (6)). A technical access control is therefore never worked around.

**EVIDENCE LIMIT** — where the reading ends.

- No case law and no commentary was consulted. Whether a robots `Disallow` or a site's terms of use bear on "lawful
  access" is **not settled by the texts read**; the terms of use of the five canary sites were not read.
- German and Union law were read. The law of the publishers' countries (Bolivia, the Dominican Republic, Honduras,
  Paraguay, Venezuela) was **not examined**; nothing here says how it applies.
- § 95a UrhG, the press publishers' right as such, data protection and personality rights were not examined.
- The university's legal office has not reviewed this decision. Whether the project is a "Forschungsorganisation" in
  the sense of § 60d (2) is taken from the operator's statement (a university project without commercial purpose).

**PROJECT POLICY** — §2 to §7.

### 2. Three layers, never one

```text
ROBOTS PROTOCOL EVIDENCE   ≠   RESEARCH-TDM ELIGIBILITY   ≠   ACQUISITION DECISION
```

| Layer | Values | Where |
|---|---|---|
| robots evidence | `ROBOTS_ALLOW` · `ROBOTS_DISALLOW_OBSERVED` · `ROBOTS_UNAVAILABLE` (4xx) · `ROBOTS_UNREACHABLE` (5xx, no answer) · `ROBOTS_PARSE_ERROR` · `ROBOTS_NOT_EVALUATED` | `policy.py`, from `robots.py` |
| research-TDM eligibility | `RESEARCH_TDM_ELIGIBLE` · `RESEARCH_TDM_NOT_APPLICABLE` · `RESEARCH_TDM_REVIEW` | `PolicyGate.research_tdm` |
| acquisition decision | `ALLOW` · `ALLOW_RESEARCH_OVERRIDE` · `REFUSE` · `HOLD` | `PolicyDecision.acquisition_decision` |

The gate's existing `ALLOW` · `DENY` · `DEFER` stay what the transport and the schedule act on; the acquisition
decision says what kind of allowance or refusal it is (`DENY` is a `REFUSE`, or a `HOLD` when a person has to look:
an access control, an opt-out, a legal hold; `DEFER` is a `HOLD`). What stops a request is named
`ACCESS_CONTROL_OBSERVED`, `DIRECT_OPT_OUT` or `LEGAL_REVIEW_HOLD`. The decision semantics are versioned
(`robots-decision/2`).

### 3. A `Disallow` and the research override

The robots file is always requested first, parsed as RFC 9309 says (group of the crawler's own token before `*`,
longest match, allow on a tie) and recorded with its digest. If it allows the path: `ALLOW`. If a `Disallow`
applies: `ROBOTS_DISALLOW_OBSERVED`, and the request is made **only** as `ALLOW_RESEARCH_OVERRIDE`, which exists only
if all of the following hold — the first eight as statements of the decided policy (`research_tdm.conditions`, each
`true`), the rest as things the gate and the fetcher check where they occur:

1. the purpose is scientific research; 2. the operator is a research organisation (a university); 3. no commercial
purpose; 4. only public, unauthenticated HTTP(S); 5. no access control is circumvented; 6. conservative rate limits;
7. raw material stays in protected research storage; 8. it is not redistributed publicly; 9. the request is a plain
`http`/`https` one without credentials; 10. no access control has been observed at the origin in the run; 11. no
direct opt-out and no legal review hold names the source; 12. the override is recorded in full.

The record of an override: the basis (`SCIENTIFIC_TDM_POLICY_V1`), this decision, the rule that applied, the digest of
the robots file, the product token, the URL and the instant — in the request log (`policy_layers.override`) — and in
the fetch record `policy_decision = ALLOW_RESEARCH_OVERRIDE` with `robots_decision = disallowed` and the robots file's
digest; the robots file itself is preserved like any fetch. There is no other path from a `Disallow` to a request: the
mode `record_only` is refused for any policy loaded from configuration, and a test enumerates the combinations.

A file that is absent (4xx other than a refusal, see §4) allows. An unreachable one and one in which not a single
line is a robots line (`ROBOTS_PARSE_ERROR`: an HTML page served at `/robots.txt`, say) **hold**: neither is read as a
permission.

**The project does not claim to be "RFC 9309 compliant".** It follows the RFC's parsing and matching, and is
stricter than it for an unreachable file; the research override departs from §2.3.1.1, openly.

### 4. Technical access controls end the path

Observed by the fetcher from the answer and recorded in the fetch record (`access_class_observed`):
`auth_required` (401, 407), `forbidden` (403), `unavailable_for_legal_reasons` (451), `rate_limited` (429), `captcha`,
`bot_challenge` (also when it arrives as 200 or 503), `login_redirect`, `paywall_redirect`. Then:

- the answer is not retried in the call — this changes CPD-0006 for 429, which was retried after `Retry-After`: the
  time the server named is recorded for the schedule and nothing waits it out;
- for every class except the two redirects, **nothing more is asked of that origin** — in the run, and in any later
  run on the same workspace, until a person has looked (`ACCESS_CONTROL_OBSERVED → HOLD`); a redirect to a login or a
  paywall is not followed and ends that URL only;
- a 401 or 403 **for the robots file itself** is an access control, not an absent robots file;
- nothing about the client changes afterwards: no other User-Agent, no cookie, no credential, no proxy, no other
  address, no search for another interface. A test asserts that every request of a refused fetcher carries identical headers.

The markers for CAPTCHA and challenge pages are few and conservative (`access-control/1`); a false positive stops a
path that could have been read, a false negative stores a challenge page that the review then shows. Neither leads to
a request that should not have been made.

### 5. Machine-readable reservations

A general reservation — the `tdm-reservation` response header — is counted in the run receipt as
`general_tdm_reservation_observed` and is in the preserved headers. It does not decide a request for scientific
research (§1). No additional request is made to look for one (`/.well-known/tdmrep.json` is not fetched; a
reservation in page metadata is in the preserved body and is not parsed yet).

### 6. Direct opt-out and legal review hold

A publisher's direct request (`opt_outs`) stops every request to that source at once, the robots file included, and
is a `HOLD` for the operator: **nothing already preserved is deleted automatically** — what happens to it is a
person's decision, to be recorded. A `LEGAL_REVIEW_HOLD` (`research_tdm.legal_review_holds`) needs a named source, a
reason and a date: concrete, source-specific evidence, not a general unease.

### 7. Pace

Unchanged and binding under an override as without one: the pause between two requests to an origin is
`max(project minimum, the origin's Crawl-delay)`; an origin that asks for more than `crawl_delay_max_seconds` is not
fetched at all; a `Retry-After` is never undercut — in the canary (one attempt per request) the URL is simply not asked again.

### 8. What a baseline pins

The canary block of the baseline now carries `research_tdm` (the basis, this decision, the semantics version, the
robots mode and one digest over the robots block, the rate limit, the basis and the conditions), the versions of the
access-control classifier and the robots parser, and `crawler_page`: the latest deployment receipt and the digest of
the public crawler page, which must be byte for byte the page of the checkout. The start-state record repeats them
together with the budgets. Driver `canary-driver/2`.

## Alternatives considered

| Alternative | Why not |
|---|---|
| keep "`Disallow` denies" | it settles by default a question the operator decided otherwise, and conflates a preference with a lock |
| ignore robots files | the evidence would be lost, `Crawl-delay` with it, and the project could not say what it overrode |
| a silent `record_only` mode | an override nobody can count is the thing this decision forbids |
| retry a 429 after `Retry-After` inside the run | an enforced rate limit is the server refusing this client; the schedule can come back another day |
| hold only the URL on a 403 | a server that refuses this client refuses it for the next URL too; asking sixteen times is not polite |
| fetch `tdmrep.json` for every origin | an additional request per origin for a signal that does not decide research TDM |
| delete preserved material on an opt-out | deletion is irreversible and may itself be wrong; a person decides |

## Consequences

- The public crawler page says this in plain words (it no longer says that every `Disallow` is followed) and was
  redeployed; the receipt is `web/DEPLOY_RECEIPT_2026-10-08b.json`.
- A canary's receipt reports, per outlet, what the robots file said, how many requests went out under the override
  and what came back, and every access control met.

## Not decided here

- Whether this policy holds for scheduled crawling or for more outlets: it is the canary's policy.
- Any legal question listed under EVIDENCE LIMIT; the review by the university's legal office.
- What is done with preserved material after an opt-out; retention periods; who may be given access for verification.
- Whether page-level reservation metadata is parsed, and whether `tdmrep.json` is ever requested.
