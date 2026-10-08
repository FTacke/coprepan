# Research-TDM acquisition policy: robots evidence, eligibility and decision as three layers

```text
run_started_at:      2026-10-08T15:53:41+02:00 (first clock reading, at the state measurement)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: PASS** for the policy part: the three layers are implemented in the existing policy gate,
decided (CPD-0017), tested offline, and stated on the public crawler page, which was redeployed and
verified.

**What the status does not claim.** No publisher was asked anything in this part. The policy has met
no real server. It is **not legal advice**, has **not** been reviewed by a legal office, and claims
**no conformance with RFC 9309**. What happened after this part — arming, baseline, canary — is in
the second report of the run.

**Kind of run:** decision and implementation. Not a scientific validation.

`EXTERNAL_API_USAGE = NONE`. Network use in this part: the retrieval of the legal and standard texts
from their publishers (seven documents), and the deployment and check of the project's own public
site. No outlet.

## 1. Starting state

`main` = `origin/main` = `f5332b5f9ef270a6581f6295598755d72cf50a13`, tree clean, the acquisition switch
`disabled`, no baseline frozen, storage roles `PRESERVATION`, `RUNTIME`, `SPOOL` available and separated,
0 pending spool records, the runtime workspace empty.

Baseline suite on that commit: **1257 passed, 1 failed, 1 skipped**. The failure,
`test_a_run_is_refused_without_everything_it_stands_on`, is a defect of the previous run that a clean
tree exposes: with a pinned commit unknown to the repository, `verify_checkout` let a `git diff` error
escape instead of stopping. (The previous run's "1258 passed" was measured on a tree that was not
clean, where the same test stops earlier.) Fixed here: an unknown pinned commit is a `CanaryStopped`.

## 2. Sources

Read in their current published wording, from the publishers only; digests in CPD-0017 §1:
UrhG §§ 44b, 60d, 60g, 87c, 95b (gesetze-im-internet.de); Directive (EU) 2019/790, recitals 8–18 and
Art. 2–4, 7 (Publications Office — EUR-Lex itself answered with a challenge page, which was not worked
around; the Publications Office's own document interface serves the same Official Journal text);
RFC 9309 (rfc-editor.org). CPD-0017 §1 separates **EVIDENCE**, **INTERPRETATION**, **PROJECT POLICY**
and **EVIDENCE LIMIT**. The limits in short: no case law or commentary; the law of the publishers'
countries not examined; whether a `Disallow` or terms of use bear on "lawful access" is not settled by
the texts; the sites' terms of use were not read; no review by a legal office.

## 3. What was changed

| Piece | Where |
|---|---|
| The three layers in the gate: `robots_evidence` · `research_tdm` · `acquisition_decision`; the research override with its provenance; `legal_review_holds`; `on_parse_error`; `research_tdm_pin`; a configured policy may not use `record_only` | `src/coprepan/policy.py` (schema `coprepan-acquisition-policy/v3`) |
| Access controls as observed evidence: classes, markers, redirect targets, the `tdm-reservation` header | `src/coprepan/access_control.py` (new) |
| The fetcher records the class with every exchange, does not retry a refusal, holds the origin, does not follow a redirect to a login or paywall | `src/coprepan/fetcher.py` |
| Robots parser `/2`: a byte-order mark no longer hides the first group (a defect found here); a file with no robots line is a `parse_error` | `src/coprepan/robots.py` |
| A fetch record may say `ALLOW_RESEARCH_OVERRIDE`; the request log carries `policy_layers` | `src/coprepan/acquisition.py`, `src/coprepan/http_acquisition.py` |
| Driver `/2`: the baseline's canary block pins the research layer, the classifier, the parser and the deployed crawler page; the start state repeats them with the budgets; the receipt has `policy_layers` statistics; budget and holds are those of the **workspace's** evidence (a second start gets no second budget) | `src/coprepan/canary_driver.py` |
| The tracked policy `canary/2026-10-08.2` — the switch untouched (`disabled`) | `config/acquisition_policy.json` |
| CPD-0017; pointer in CPD-0013; STATUS, registry, index, runbook | `docs/` |
| The public crawler page and its receipt | `web/coprepan/crawler/index.html`, `web/DEPLOY_RECEIPT_2026-10-08b.json` |

No second driver, no new pipeline. Nothing was moved or deleted.

## 4. Decisions worth the operator's eye (all in CPD-0017)

- A 401 or 403 **for the robots file** counts as an access control, not as "no robots file".
- Any access control except a login/paywall redirect holds the **whole origin**, also for later runs on
  the same workspace, until a person has looked.
- A 429 is no longer retried after `Retry-After` inside a run (this changes CPD-0006 §3).
- A robots file that cannot be parsed, and an unreachable one, **hold**; an absent one allows.
- A general machine-readable reservation is recorded from the response header only; no extra request
  looks for one.
- An opt-out stops requests; it deletes nothing by itself.

## 5. Tests

`tests/test_research_tdm_policy.py`, 44 tests: the matrix of the brief — robots allow; disallow with an
eligible, an ineligible and an absent research layer; disallow with an access control, an opt-out, a
legal hold; `Crawl-delay`; specific against broader rules; the wildcard and the crawler's own group;
malformed, unavailable, unreachable; 401, 403, 429, 451, CAPTCHA and challenge markers (also gzip-coded
and by header), redirects to login and paywall — and the invariants: an override is explicit, never
silent, deterministic; no request after a refusal or hold (asserted on the server's log); identical
request headers before and after a refusal, no cookie, no credential; no request above a budget; a
restart asks a refusing origin nothing; `RAW_PRESERVED` only for verified bytes.

| Check | Result |
|---|---|
| full suite before any change (`f5332b5`) | 1257 passed, 1 failed (§1), 1 skipped |
| full suite on the changed tree, before this report existed | 1303 passed, 1 failed, 1 skipped — the failure being the link check for this very file |
| full suite on the commit | stated in the commit message |

## 6. The public page

`https://coprepan.hispanistica.com/crawler/` now says that robots files are read and recorded, that
the project does not treat every `Disallow` as an absolute exclusion for non-commercial scientific
text and data mining, that this departs from the Robots Exclusion Protocol in that point, that no
access control is bypassed, and that a direct opt-out is honoured (English and Spanish). Backup taken
first; only `crawler/index.html` changed (`55c8f311…` → `391d8316…`); virtual host unchanged, `nginx -t`
successful, no reload; HTTPS check with certificate verification: all three files equal the source;
HTTP → HTTPS 301; the neighbouring sites still answer 200.

## 7. Gates

| Gate | State after this part |
|---|---|
| O-1 (canary) | `PASS`, policy `canary/2026-10-08.2`, switch off |
| O-2 | `PASS`, page redeployed |
| O-12, canary, O-4, Phase 3 | see the second and third report of the run |

## 8. Recommended next step

A reading of CPD-0017 by the university's legal office, before any use beyond the canary.
