# CPD-0027 — Access holds have a scope, and a refused robots address is not a refused origin

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief "CO.PRE.PAN 3.0 – Evidence-Based Access Policy Liberalisation & Source Recovery" of 2026-10-09/10: "So offen wie fachlich, rechtlich und technisch vertretbar; so restriktiv wie tatsächlich erforderlich"; "Eine gewöhnliche HTTP-4xx-Antwort ausschließlich auf /robots.txt führt nicht automatisch zu einem dauerhaften Hold aller anderen Ressourcen desselben Origins"; "Holds möglichst präzise nach Origin, Pfad und Ursache führen"; "Bei fachlich ausreichend klaren technischen Fragen selbstständig entscheiden und implementieren". The scope table and the mechanisms are the run's technical choices, subject to the operator's review |
| Kind | policy · access control · robots |
| Scope | what an observed access control holds; how the answer to a robots address is read; nothing about what may lawfully be used |
| Builds on / amends / supersedes | builds on CPD-0017 (three layers; an access control is never overridden) and CPD-0026. **Amends CPD-0017 §4, forward-only:** the rule "what is observed ends every further request to that origin in the run" becomes the scope table of §2; the reading of a 401/403 for a robots address as an access control of the origin is replaced by §3. Supersedes nothing |
| Does not change | that no access control is worked around — no challenge is solved, no other client identity, network or address form is tried, no login or paywall is passed; that an explicit `Disallow` is a rule of the source and is overridden only under the research-TDM layer of CPD-0017 as it stands; opt-outs and legal review holds; the pace; any preserved answer, receipt or baseline; any hold a real control on an item page or a challenge on a robots address caused |
| Run report | [`docs/agent-runs/2026-10-10_access-policy-liberalisation-and-source-recovery.md`](../agent-runs/2026-10-10_access-policy-liberalisation-and-source-recovery.md) |
| Evidence | `config/source_discovery/access_restriction_review_2026-10-09.json` (the 18 holds); `tests/test_canary_findings.py`, `tests/test_research_tdm_policy.py` (the scope table; the three cases replayed on their preserved answers; robots 401/403/404/410/429/5xx); the recovery wave's baseline and receipt (run report) |

Validation debt: what the changed policy yields on the real servers is what the recovery wave measures. A released hold is
not an outlet that yields articles.

## Context

After the qualification of 2026-10-09 eighteen origins were held "behind an access control". Read one by one against their
preserved answers, they were not one thing: ten challenges on the first request, a block page, a JavaScript challenge — and
a 403 for the robots address of a feed host (`es_el_pais`), a 403 for a robots address from a load balancer
(`gt_nuestrodiario`), a challenge on one sitemap beside a feed that answered (`ve_efecto_cocuyo`), a 403 on one feed
(`py_adn_digital`), and a 410 of a retired feed misread as a challenge (`mx_la_jornada`). The policy of CPD-0017 treated all
of them alike: any class of access control, on any answer, held the whole origin, and — because holds are re-derived from
preserved answers — held it in every later run.

**The scientific cost was concrete:** El País (Spain), 1 142 full articles in the legacy corpus until 2026-02-21, was never
asked for its feed; Efecto Cocuyo (443 articles until 2026-02-10) had a working feed whose articles were not requested;
Mexico had one verified outlet of five. None of these was the publisher refusing the crawler what it asked for.

## Decision

1. **Source coverage is a quality goal of the access policy.** A rule that removes a source without an observed restriction
   on what is asked needs a reason. That goal replaces no external restriction and no legal basis.
2. **What a control holds depends on what was asked** (`access_control.hold_scope`, `access-hold-scope/1`):

   | Asked | Observed | Held |
   |---|---|---|
   | anything | rate limit (429) | the origin |
   | an **item page** | any control (401, 403, challenge, CAPTCHA, block page, 451) | the origin: the thing itself is protected, nothing more is asked |
   | a **channel document** (feed, sitemap, listing) | any control | **that URL**: the route is not asked again; the outlet's other channels answer for themselves |
   | a **robots address** | challenge, CAPTCHA, a firewall's block page, 451 | the origin: a server that meets even this address so meets this client |
   | a **robots address** | a plain 401 or 403 | **nothing** (§3) |
   | anything | 404, 410, other 4xx | nothing: a route that is gone is gone (a retired channel is disabled in the policy when it is known) |

   A login or paywall redirect ends its path as before and holds nothing.
3. **The robots address** (`robots-decision/3`), by RFC 9309 §2.3.1 and as the policy already did for 404:
   - 2xx: parsed and applied. An explicit `Disallow` is unchanged, and so is the research-TDM layer that weighs it.
   - **4xx except 429: the robots file is unavailable** (§2.3.1.3) — the request for the resource is weighed without robots
     rules (`on_absent`), and the resource's own answer decides. The class of the answer (`forbidden`, `auth_required`) is still
     recorded on the fetch record.
   - **429 and 5xx, or no answer: unreachable** (§2.3.1.4) — nothing is requested of that origin (`on_unreachable: defer`);
     a 429 also holds the origin as a rate limit.
   - a 2xx answer that is not a robots file: a parse error, held as before.
   - a redirect to a host that is not registered is not followed, as before; the origin is amended when the server's own
     redirect names it (CPD-0026 §4).
4. **Each host answers for itself.** A feed on another host has that host's robots file, controls and holds; the article host
   has its own. A feed that answers opens nothing on the article host.
5. **Holds are re-derived in both directions.** Every preserved answer is read again under the classifier in force when a
   run starts: an answer the classifier of its day missed holds, an answer it misread no longer does. (Until now only the first
   direction existed; CPD-0026 §3 claimed the second, and it was not true until this change.) The stored record is never
   rewritten.
6. **A block page is named.** `access-control/4` adds the class `blocked` for a content-delivery firewall's own block page
   (two marks of the same page, on a 403/429/503), because a plain 403 for a robots address no longer holds anything and such a
   page must (`mx_milenio`).
7. **Requalification.** An origin or URL that is held is asked again only (a) when the classifier in force no longer reads its
   preserved answer as a control, or (b) under a new, explicit authorisation that names it and its basis (a publisher's
   permission, a changed address). Never because time has passed, and never by the same request repeated.
8. **Provenance.** The policy file carries a new version (`canary/2026-10-10.1`); baselines pin it, the classifier version and
   the robots-decision semantics; an authorisation record names the policy version it may run under, so no record of
   2026-10-09 can arm under this policy.
9. **Rollback.** If a recovery run meets a control on an item page of a released origin, that origin is held again by this
   same table — the rule needs no rollback for that. The rule itself is rolled back (a new decision restoring origin-wide
   holds) if released origins answer with rate limits or challenges in a pattern that shows the scoped reading puts load or
   pressure on publishers that the origin-wide reading did not.

## What this decision is not

It is not a statement that a request is lawful. Protocol reading (this record), technical access control (never passed) and
the legal basis of text and data mining (CPD-0017 §5, the operator's and the institution's) are three layers. For El País in
particular: a metered paywall is reported by research, and whether the publisher has declared a TDM reservation is recorded
when a response states one; neither is decided here.

## Alternatives considered

| Alternative | Why not |
|---|---|
| keep origin-wide holds and add per-outlet exceptions | exceptions to an access classifier are how a real control gets missed; a general rule is testable |
| treat every 4xx on a robots address as unavailable, 429 included | a rate limit says "not now"; RFC 9309 does not make it a missing file, and asking on would be exactly what it asks not to |
| a control on a channel document holds the origin if no other channel has answered yet | order-dependent: the same outlet would be held or not by which channel was read first |
| a plain 403 on an item holds only that URL | a refusal of the thing itself is the signal this policy exists to respect; ten further requests to find out are not bounded restraint |
| let a hold expire after some days | a publisher's refusal does not lapse because the crawler waited |

## Not decided here

- the legal questions named above;
- whether an outlet whose every channel is held is to be contacted;
- any intake.
