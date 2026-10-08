# First real canary: verified, evaluated, measured; disarmed; a pilot review package for Phase 3

```text
run_started_at:      2026-10-08T22:40+02:00 (approximate; first measured instant of this run: the verification of the receipt)
run_ended_at:        see the closing commit of the run (first clock reading while writing: 2026-10-08T22:53:53+02:00)
timezone:            Europe/Berlin
```

**Status: PARTIAL.**

- The canary ran once, by the operator's hand, and is **`PARTIAL` within its technical scope**: everything it
  fetched is preserved, verified, replayable and accounted for, and no budget was touched — but **only one of the
  five outlets yielded items**, three defects of our own code and one unrecognised bot challenge are the reasons, and
  after that challenge one further request went to the same site (§6).
- `external_acquisition` is **`disabled`** again (commit `4cb4ea1`).
- O-4 has its first real measurement and is **not** closed (§8).
- Phase 3: `PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY`. A **pilot** review package on the thirteen preserved pages
  exists and is ready for a human; it is not a gold package (§10).

**What the status does not claim.** Nothing here is generalisable: one outlet's pages, one evening. The canary's
result is not a production activation and not a statement about the press of any country. No extractor was compared
with a reference; no candidate is better or worse than another by anything in this report. The research override of
CPD-0017 was **not exercised** on a real server. No gold exists.

**Kind of run:** evaluation of a finished activation (the canary), a measurement (O-4), a de-activation (disarming),
a decision (CPD-0018) with its implementation, and the preparation of a human review. No diagnosis found here was
repaired: the defects of §6 are reported, their repair is a separate, authorised step.

`EXTERNAL_API_USAGE = NONE` for this run. **No request to any publisher was made by this run** (the canary's 27
requests were made by the operator's run of the driver, before it). The package index was read to install three
pinned tools into an environment outside the repository (§10).

## 1. Starting state (measured)

| Item | Value |
|---|---|
| `HEAD` = `origin/main` | `be9e3da00d6553654184f241feefeafb7b0486a3`, tree clean |
| pinned commit of the canary | `15ec1fdabf1b5e4e2cb3c4a05a978e57dff3bed0` (`HEAD` differed from it in `docs/canary/` and `docs/agent-runs/` only) |
| frozen baseline | `docs/canary/BASELINE_FROZEN_2026-10-08b.json`, digest `96c271e373dc59dbbb8cccae9301556397e553041de71647f31bbd4dbed7863f` |
| `external_acquisition` | `enabled` (the operator's arming) |
| receipt found | `<RUNTIME root>/canary/canary-receipt-acq1-20261008T203414628095Z-ed630d8e8a14.json`, with its start-state record |

The start-state record (written by the driver before its first request, 2026-10-08T20:34:14Z) names: `HEAD` =
`origin/main` = `be9e3da`, pinned commit `15ec1fd`, tree clean, baseline `96c271e3…`, policy `canary/2026-10-08.2`
(file digest `b9f62bcb…e43f`), research-TDM policy `SCIENTIFIC_TDM_POLICY_V1` (digest `c4923d8a…969e`,
`robots-decision/2`), crawler identity and the deployed crawler page (receipt `DEPLOY_RECEIPT_2026-10-08b.json`),
preservation target `coprepan-preservation-interim-d` by its marker, spool 0 pending, the five outlets, the budgets,
1309 tests, preflight `READY`.

## 2. The run

`acq1-20261008T203414628095Z-ed630d8e8a14`, 2026-10-08T20:34:14Z to 20:37:35Z (3 min 21 s), driver
`canary-driver/2`, User-Agent `PanhispanicMediaResearchBot/0.3.0 (+https://coprepan.hispanistica.com/crawler/; felix.tacke@uni-marburg.de)`.
Status `COMPLETE`. Five packs, one per outlet. Evidence of record, copied unchanged into the repository:
[`docs/canary/evidence/acq1-20261008T203414628095Z-ed630d8e8a14/`](../canary/evidence/acq1-20261008T203414628095Z-ed630d8e8a14/)
(start state, receipt, verification, measurement; no page content).

## 3. Requests (measured from fetch records and the request log)

**27 real requests** (every redirect hop and robots file counted), in 24 fetch records. Answers: 22 × 200, 1 × 307,
1 × 404 (the three other requests were the first hops of 301 redirects).

| Outlet | Real requests | What they were | Items |
|---|---|---|---|
| `bo_el_deber` | 1 | `robots.txt` 200 | 0 |
| `do_diario_libre` | 17 | `robots.txt` 200; RSS (301 → 200, 2 requests); news sitemap 200; 13 item pages, all 200 | **13** |
| `hn_proceso_digital` | 3 | `robots.txt` 200; RSS **307 with a JavaScript challenge page**; news sitemap 404 | 0 |
| `py_la_nacion` | 1 | `robots.txt` 200 | 0 |
| `ve_efecto_cocuyo` | 5 | `robots.txt` 200; RSS (301 → 200); sitemap index (301 → 200) | 0 |

Budget: 13 item requests of 80 (ceiling 100); at most 16 per outlet (13 used by one outlet); 14 robots /
channel-document requests, at most 5 for one outlet of 8. One attempt per request, no retry; one request at a
time. The pace between requests was the fetcher's; it was not re-measured from the evidence in this run.

## 4. The 162 refusals — none of them is a publisher's refusal

A "refusal" is a request the driver planned and **did not send**. The request log has 181 planned requests: 19
answered, 162 not sent.

| Count | Reason on record | What it was |
|---|---|---|
| 92 | `canary_budget_exhausted` | the 92 child sitemaps named by the sitemap index of `ve_efecto_cocuyo`. That outlet had used 5 of its 8 robots / channel-document requests; a fetch is only started when a whole fetch — up to 3 redirects, so 4 requests — still fits; 3 were left. Working as designed; the consequence is that this budget does not reach the second level of a sitemap index (§6, F4) |
| 3 | `canary_budget_exhausted` | the 14th to 16th item of `do_diario_libre`: 13 of 16 used, 3 left, 4 needed for a whole fetch. As designed |
| 64 | `off_origin` | **a defect of ours (F3)**: for each of the four other outlets the driver planned 16 item requests for candidates of `do_diario_libre` (`https://www.diariolibre.com/…`) under the other outlet's id. The policy gate refused every one before anything was sent |
| 3 | `robots_parse_error` (deferred, a hold) | **a defect of ours (F1)**: the two channel documents of `bo_el_deber` and the one of `py_la_nacion`. Their `robots.txt` arrived gzip-compressed and was parsed without being decompressed |

## 5. Robots, research-TDM, access control (the three layers on real servers)

| Outlet | `robots.txt` as served | What the run made of it | What it says when read correctly (read from the preserved bytes, after the run) |
|---|---|---|---|
| `bo_el_deber` | 200, `Content-Encoding: gzip` | `ROBOTS_PARSE_ERROR` → hold; nothing more asked | `Allow: /`; `Disallow` for `/partido_detalle/`, `/portadas/`, `/buscar/`, `*.pdf`, `?utm_`, `/service/`; five sitemaps. Neither channel URL of the canary is disallowed |
| `do_diario_libre` | 200, plain | `ROBOTS_ALLOW` for all 15 requests | `Disallow: /xstatic/`, `/XStatic/`; applies to nothing that was asked |
| `hn_proceso_digital` | 200, plain | `ROBOTS_ALLOW`; `Crawl-delay: 3` recorded (below the 10 s the policy keeps anyway) | no rule |
| `py_la_nacion` | 200, `Content-Encoding: gzip` | `ROBOTS_PARSE_ERROR` → hold | `Disallow` for `/foco`, `/vos`, `/category/semanales/`, `/semanales/`; `Allow: /`. The channel URL is not disallowed |
| `ve_efecto_cocuyo` | 200, plain | `ROBOTS_ALLOW` | empty `Disallow` (everything allowed) |

- **Robots `Disallow` that applied to a request: none.** Requests allowed by robots: 19. Under a hold: 3.
- **`ALLOW_RESEARCH_OVERRIDE`: 0.** The override was never needed and never used. Its path is therefore still untested
  on a real server.
- Direct opt-outs: 0. Legal-review holds: 0. Machine-readable TDM reservation in a response header: 0 observed.
- **Technical access control: one was met and not recognised (F2).** `https://proceso.hn/rss` answered 307 with no
  `Location`, `Server: Sucuri/Cloudproxy`, and a 1,331-byte page: "You are being redirected… Javascript is required",
  with an obfuscated script that sets a cookie. That is a bot challenge in the sense of CPD-0017. It was **not
  worked around** — no script was run, no cookie set, no retry, no other User-Agent. But the classifier
  (`access-control/1`) recorded `none_observed`, so the origin was **not put on hold**, and stage B sent **one more
  request** to it (`/sitemap-news.xml`, answered 404 by the same proxy with the site's ordinary not-found page).
  Under the policy that second request should not have been sent. Re-running the classifier on the preserved answer
  gives `none_observed` again: the miss is reproducible.

## 6. Findings — defects and limits the canary exposed (reported, **not repaired here**)

| | Finding | Where | Effect in the canary | Kind |
|---|---|---|---|---|
| F1 | The robots answer is parsed as received; the fetcher asks for `gzip` and does not undo it before parsing | `fetcher.robots_evidence` → `robots.evidence_from_response(status, body)` | two outlets held with nothing read; fail-closed, no publisher affected | defect; the loopback tests never serve a compressed robots file |
| F2 | The access-control classifier does not know the Sucuri JavaScript challenge (status 307, no `Location`, `sucuri_cloudproxy_js`) | `access_control.classify_response` | one request more than the policy allows to `proceso.hn`; the challenge page preserved as a "channel document" | defect of a guarantee: a false negative the module's own text anticipates |
| F3 | Item planning takes the candidates of the whole workspace, not of the outlet being run | `http_acquisition.run_http_acquisition` (`tables.candidates`, unfiltered) | 64 foreign-origin plans, all refused by the gate, nothing sent. With several outlets holding candidates, an outlet's item budget could be spent on plans that are refused | defect; found because a real workspace held several outlets |
| F4 | A whole fetch must fit (4 requests with 3 redirects allowed) into 8 robots / channel requests per outlet | driver budget | after two redirecting channel documents nothing of a sitemap index's second level is read; `ve_efecto_cocuyo` got no candidate that way | design consequence, to be decided |
| F5 | The channel parser refuses a feed in which the string `<!DOCTYPE` occurs — also inside CDATA | `channel-parser/1` (`dtd_or_entity_declaration_refused`) | the RSS of `ve_efecto_cocuyo` (10 items, each embedding an HTML document in CDATA) gave no candidate | defect or over-strict guard |
| F6 | `hn_proceso_digital`: the registered news-sitemap URL is 404 | registry | no candidate | registry fact |
| F7 | 232 candidates from one outlet's feed and sitemap; the 534 sitemap entries hit the candidate limit of 200 per discovery | discovery budget | as designed; noted for O-4 (discovery evidence dominates the workspace bytes) | observation |

None of these is evidence loss, a wrong `RAW_PRESERVED`, a fixity failure, a budget violation or a circumvention.
F2 is the one point where a guarantee of our own policy was not kept.

## 7. Preservation, fixity, replay, recovery (`canary_driver verify`: `PASS`)

| Check | Result |
|---|---|
| recovery diagnosis with identity rebuild | `CLEAN`; identity `CORRECT` |
| read-back and fixity | 24 bodies read back from the preservation root; all verify; pack and index masters verified against their manifests |
| `RAW_PRESERVED` equals verified bytes | 24 = 24 = 24 |
| replay with the network made unavailable | 13 extractions replayed from preserved bytes; 0 differ |
| receipt re-derived from evidence | every count equal |
| the fetcher's own counter | 27 = 27 derived from fetch records |
| pending | 0 spooled records; route `direct` for all five packs (the outage spool was not needed) |
| budget | respected |

On the preservation root: five packs (972,174 bytes) and five indexes (12,152 bytes) with ten manifests; the target
marker. Derived: 13 documents, 13 versions, 13 observations; 13 baseline extractions; 13 technical admission labels
(`admission-technical/1`), each carrying `extractor_not_active`. After this run's Phase-3 work the workspace still
diagnoses `CLEAN`, identity `CORRECT`.

This is **reproducibility and robustness** evidence. The outage path, the drain and a crash were not exercised by
the real run.

## 8. O-4 (`canary_driver measure`)

All sizes are of this run. `MEASURED` = read from files; `DERIVED` = a quotient of measured values; `ASSUMED` /
`PROJECTED` = a stated scenario.

| Quantity | Value | Label |
|---|---|---|
| item pages, 200 | 13; received body mean **53,895 B** (as served, gzip); stored response member mean 55,048 B; stored metadata member mean 1,611 B | MEASURED |
| channel documents, 200 | 4; received mean 47,902 B | MEASURED |
| channel documents, other status | 2; received mean 10,204 B | MEASURED |
| `robots.txt` | 5; received mean 149 B; stored member mean 917 B | MEASURED |
| preserved objects (packs + indexes) | 984,326 B for 24 fetch records | MEASURED |
| pack bytes per fetch record | 40,507 B; overhead beyond the members 65 B | DERIVED |
| index bytes per fetch record | 506 B | DERIVED |
| pack and preservation manifests | 2,565 B and 8,386 B in all | MEASURED |
| workspace evidence other than packs (ledger, request log, discovery, identity, labels, runs) | 1,506,604 B = 62,775 B per fetch record — **the largest component**; it follows the number of discovered entries (659 events, 232 candidates), not the number of fetches | MEASURED / DERIVED |
| extraction layer | 582,580 B; 44,814 B per extracted item (uncompressed records) | MEASURED / DERIVED |
| stored bytes per fetch by outlet | 2,371 · 2,914 · 7,491 · 8,616 · 57,312 B | DERIVED |

| Scenario | Basis | All layers per fetch | per 1,000 fetches | per 100,000 fetches |
|---|---|---|---|---|
| LOW | smallest outlet mean | 89,941 B | 85.8 MiB | 8.38 GiB |
| CENTRAL | mean over all fetch records | 128,012 B | 122.1 MiB | 11.92 GiB |
| UPPER | largest outlet mean | 144,882 B | 138.2 MiB | 13.49 GiB |

(PROJECTED.) Annual figures only as conditional statements on the legacy system's sourced fetch counts (ASSUMED):
at its median of 115 fetches per outlet-day, 5 / 53 / 82 outlets give 0.02 / 0.18–0.29 / 0.28–0.45 TiB a year; at
its maximum of 367, 82 outlets give 0.90–1.45 TiB a year. Against the 2 TB the operator stated for the planned file
system that is 4.0–6.5 years (median) or 1.3–2.0 years (maximum) for 82 outlets.

**How far these numbers carry.** Item sizes come from **one outlet** (thirteen pages of one template). The "smallest
outlet mean" of LOW is an outlet whose only fetch was a 143-byte robots file: it is not a lower bound for a page.
The spread across outlets is a spread of what the defects let through, not of the press. The canary measures sizes,
not a crawl rate: fetches per outlet-day were not measured. Bodies are stored as served (gzip here); an outlet that
serves uncompressed pages stores several times as much per page.

**Conclusion.** `O-4` stays **`OPEN`**. For the *initial* horizon — a second bounded canary, or a first small
operation on the interim target — capacity is not a constraint: 100,000 fetches project to 8–14 GiB against 3.8 TB
free on the interim target (stated by the readiness check), two orders of magnitude of margin even if a page were
ten times larger. That is enough to proceed with a second canary. It is **not** a basis for sizing the institutional
file system: that needs item sizes from several outlets and a measured fetch rate.

## 9. Disarming

`"external_acquisition": "disabled"` — commit `4cb4ea11dc9ba9ec70b7ea7cd90d9575c92cd320`, alone, pushed.
`config/acquisition_policy.json` is byte for byte the file of `73a6311` (before any arming). The edit was accepted by
the permission layer this time. Done directly after the verification and before the Phase-3 work, rather than after
it as the brief ordered: nothing in Phase 3 needs the switch, and an armed checkout is not left armed longer than
necessary.

## 10. Phase 3

### 10.1 Material

Frame: item fetches of the canary run that are `RAW_PRESERVED`, read from the preservation root with the masters
verified — **13**, all `do_diario_libre`, country `do`, outlet type `unknown` (registry), channel kind `rss`,
response class `2xx_html`, time slice 2026-10-08: **one cell** of the design's six strata. No error status, no
non-HTML, no second outlet, no second channel kind. Purposive cases (design §4) need a person browsing the frame and
were not chosen.

**`PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY`.** A gold sample by the design cannot be drawn from this: there is
nothing to stratify. Acquisition was not widened and nothing was fetched again.

### 10.2 What was built instead: a pilot

Because the instrument, the codebook and the candidates had never met a real page, the thirteen pages were made into
a **pilot package**: the whole cell (`per_stratum = 16`, the item budget of an outlet; seed
`coprepan-phase3-pilot-canary-2026-10-08`), sample id `phase3-pilot-canary-2026-10-08`, `sample_sha256`
`4f6ee043eb0159846e08f6f64ddb91b5ecc276da3955d85a307bcd33db65f1de`. What a human can get from it: whether the review
form and codebook v1 work on real pages, and how four arms treat one template. What they cannot get: a comparison of
extractors that holds beyond `do_diario_libre`.

### 10.3 Candidates (CPD-0018)

| Arm | Tool | Licence (distribution metadata) |
|---|---|---|
| `baseline_html/0.1.0` | this repository | — |
| `trafilatura/2.3.1.w1` | trafilatura 2.3.1 | Apache-2.0 |
| `readability_lxml/0.9.w1` | readability-lxml 0.9 | Apache-2.0 |
| `justext/3.0.2.w1` | jusText 3.0.2, Spanish stop list | BSD 2-Clause |

Chosen by technical criteria before any output was looked at (offline, deterministic, a current release that
installs, a stated licence, three different method families); reasons for leaving the others out are in CPD-0018 §2.
Versions are the newest on the package index on 2026-10-08. Installed into an environment outside the repository;
the extra `phase3` in `pyproject.toml` carries the pins; the package still has no runtime dependency. The whole
environment (28 distributions, Python 3.12.10) is stored with the package (`operator_only/environment.txt`). No LLM.

### 10.4 Input equivalence

Every arm received the **same preserved bytes** of each case — the harness checks each body against the digest the
sample froze and stops otherwise — with the same content decoding and character decoding (the baseline's, recorded in
every record) and **no address**. The socket guard of the canary verification was on for the whole build. Each arm ran
twice per case: 52 arm runs, all `OK`, no arm gave two answers.

### 10.5 Blinding and the hidden key

Labels `A`–`D` per case, in an order derived from a seed generated at build time and stored **only** in the key file.
The key was moved out of the reviewer directory; the build then checks that no reviewer file contains an arm's name
and that every decision form is empty, and fails otherwise.

| | |
|---|---|
| package (outside the repository: it holds page text) | `<RUNTIME root>/phase3/phase3-pilot-canary-2026-10-08/` |
| **for the reviewer** | `reviewer/` — `index.html`, `index.json`, `cases/` (13 files), `REVIEW_CODEBOOK_v1.md` |
| not for a reviewer before all cases are decided | `operator_only/` — `blinding_key.json`, `evaluation.json`, `arm_outputs/` (4 × 13 records side by side), `environment.txt` |
| hidden key, SHA-256 | `aaa5521ea2b9c956bc91a8c5a54ca998dbc708b2ca5be370bab6b5303cce803e` |
| evaluation record, digest | `56484cf73d28e2c62ca234d5eabfb906fceba79c2a7fb6a28c89adc1d49602b0` |
| package manifest, digest | `73269a65a9aa2874c50a0a7fb727c9ae829ddc7d8ef3ad3d7982ce96fc7153ac` |
| in the repository | [`docs/extraction/phase3/phase3-pilot-canary-2026-10-08/`](../extraction/phase3/phase3-pilot-canary-2026-10-08/): the sample manifest and the package manifest (digests of every file; no page text, no arm output, no label-to-arm mapping) |

Known limit: the arms differ in **shape** — one states metadata bases and keeps non-body blocks, one has no title —
so a reviewer who knows the tools could guess. Names, the key, scores and ranks are not shown.

### 10.6 Automatic diagnostics

Reported here only what cannot rank: 13 cases, 4 arms, 52 outputs, all `EXTRACTED`; every arm deterministic. The
per-arm figures (body token counts, pairwise disagreement) are in `operator_only/evaluation.json`. They are
diagnostics, not quality, and are deliberately **not** printed in this report: the operator is also the reviewer.
Open that file after the review.

### 10.7 Endpoint

```text
PHASE3_SAMPLE         = INSUFFICIENT_FROM_CANARY
PHASE3_PILOT_PACKAGE  = READY_FOR_HUMAN_REVIEW      (13 cases, one outlet; a pilot, not gold)
PHASE3_GOLD_PACKAGE   = NOT_BUILT
```

No decision form was filled. No gold was created.

## 11. Checks

| Check | Result |
|---|---|
| `canary_driver verify` | `PASS` (8 of 8) |
| `canary_driver measure` | written; values in §8 |
| classifier re-run on the preserved 307 answer | `none_observed` (reproduces F2) |
| robots files decoded and parsed after the run | parse error only on the undecoded bytes (reproduces F1) |
| `tests/test_extractor_candidates.py` in the candidate environment | 11 passed |
| the same in the main environment | 4 passed, 7 skipped (the tools are not installed there, by design) |
| full suite, switch off, final tree (main environment) | **1314 passed, 8 skipped** — 7 are the candidate tests that need the tools, 1 is the symbolic-link test this account cannot run |
| policy, readiness, canary and repository-contract tests directly after the disarming edit | 133 passed |
| recovery diagnosis of the workspace after the Phase-3 build | `CLEAN`, identity `CORRECT` |

## 12. Files and git

Created: `src/coprepan/extractor_candidates.py`, `scripts/phase3_review_package.py`,
`tests/test_extractor_candidates.py`, CPD-0018, `docs/canary/evidence/acq1-…/` (four files, copies),
`docs/extraction/phase3/phase3-pilot-canary-2026-10-08/` (two manifests), this report. Changed:
`config/acquisition_policy.json` (the switch, back to `disabled`), `pyproject.toml` (extra `phase3`),
`tests/suites/foundation_contract.txt`, `docs/STATUS.md`, `docs/canary/RUNBOOK.md`, `docs/extraction/INDEX.md`,
`docs/extraction/EXTRACTOR_CANDIDATES.md`, `docs/decisions/README.md`, `docs/architecture/INDEX.md`,
`docs/architecture/TERMINOLOGY_AND_NAMING.md`. Outside the repository: the review package and the two files
`verification.json`, `measurement.json` in the runtime workspace; a temporary Python environment in the session
scratchpad. Nothing was moved, deleted or overwritten. No historical report was edited. No code of the acquisition
path was changed: the defects of §6 are open.

Untouched: the reference repositories, CO.RA.PAN, the three cross-corpus contracts, the public crawler page.

## 13. Gates

| Gate | State |
|---|---|
| O-12 (canary scope) | **`PASS`** — frozen `96c271e3…7863f` on `15ec1fd`; the canary ran under it |
| Phase-2 canary | **`OPEN`** — run once, `PARTIAL`: one outlet of five acquired; F1–F5 open |
| O-4 | **`OPEN`** — first measurement; not a constraint for a second canary |
| O-1 | `PASS` for the canary scope; the override path unexercised on real servers; `external_acquisition` `disabled` |
| Phase 3 | pilot package ready for a human; sample insufficient; no gold |

## 14. Recommended next run

One run: repair F1, F2, F3 and F5 with regression tests (a compressed robots file; the Sucuri challenge page as a
recorded fixture; a workspace with candidates of two outlets; a feed with `<!DOCTYPE` inside CDATA), decide F4 and
F6, and prepare a second bounded canary of the same five outlets — to be armed by the operator. The pilot review can
be done by a person in parallel; it needs no further technical step.
