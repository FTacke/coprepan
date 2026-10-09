# Autonomous acquisition: safe recovery, the delegated operator mode, and the waves

```text
run_started_at:      2026-10-09T15:36:00+02:00 (first clock reading of the run, approximate to the minute)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

This report was written in stages, one commit after each phase; this is its final state.

**Status: `PARTIAL`** — every phase ran and ended disarmed; none delivered everything it was aimed at.

| Phase | Status | In one line |
|---|---|---|
| 0 — the canary under way | `PASS` | it completed on its own; nothing was touched while its process lived; the disarmed state was read independently |
| 1 — delegated operator mode | `PASS` | built, tested, and used for four real armings without a typed confirmation and without a refusal by the environment |
| A — second canary (the operator's, in person) | `PARTIAL` | 31 article pages from 2 of 5 outlets; one new outlet; two held; one lost to a defect of this project (F8, repaired) |
| B — eight outlets | `PARTIAL` | 72 pages from 6 of 8 outlets, five countries new; two outlets lost to a defect (F10, repaired) and a registration gap (F11, open); one outlet reached by a route that should not have been taken (F9, repaired) |
| C1 — nine new outlets | `PARTIAL` | 40 article pages from 6 of 9 outlets (5 with five or more), three countries new; two held; one lost to URL identity (F12, open); listings preserved |
| C2 — articles from HTML listings | `PASS` with a recorded incident | 20 article pages from the two qualified listing outlets, one country new; before that, two starts that stopped at a gate — the second after two requests whose answers were not recorded (F14, repaired) |

**What the status does not claim.** No outlet is `OPERATIONALLY_STABLE` (three runs on three days within fourteen days; the
most any outlet has is two). No production activation: every gate of `docs/STATUS.md` that was open is open. The extractor is
experimental; body-text figures measure it, not the pages. Nothing here is a statement about the corpus's representativeness.
No human confirmation was simulated, and none is recorded for anything the delegate did.

**In numbers** (all from receipts, verifications and the request log): four canaries completed today, 250 real requests in
them plus the two unrecorded ones of the interrupted start; **163 item pages answered 200 and are preserved, verified and
replayed** — 157 of them articles (five section pages of `ec_primicias`, one advertisement in `cu_14ymedio`'s feed). Outlets
with verified acquisition: **14** (1 before today); countries: **11** (1 before today): do, bo, ec, es, ni, pe, sv, ar, cu, hn, pr.

`EXTERNAL_API_USAGE = NONE`.

## Phase 0 — the canary that was under way

The brief reported a second canary armed and waiting for a digest. The state found was another one, and nothing was closed by
this run.

| Checked | Found |
|---|---|
| operator process | `scripts/canary_operator.py --operator "Felix Tacke" --label second …`, started 15:35:40, alive until 15:59:41 |
| baseline | built and **frozen by the operator in person** (typed digest): `docs/canary/BASELINE_FROZEN_2026-10-09_second.json`, digest `9bd2da67d435a439c5ae1b52f7d3561c19c5907e18717f792381757bd8173977`, commit `a0b3843` |
| arming commit | `7ec0fa3598b22cf57de6e400acdcb40a9bdc1e81` (the tests of that commit passed: the repair of the earlier run held) |
| requests | under way from 15:46:34; the run `acq1-20261009T134634374845Z-3d6f4bf8adea` finished 15:52:55 |
| evidence | commit `81c8273`: receipt, start state, `verification.json`, `measurement.json` under `docs/canary/evidence/<run>/` |
| disarming | commit `21a17a3`, pushed |

Because a process was still producing a consistent commit and baseline state, **nothing was changed in the repository until it
had exited** — including during its closing test run on the disarmed tree (15:53–15:59). The state was then read independently,
not taken from an exit code: `external_acquisition` is `disabled` in the file, in `HEAD` and on `origin/main`
(`21a17a3abe3bdabcb5a5a9df901d2039a3bdd36d` both), the tree was clean, and no canary or operator process was left (the process
list was read; what remains are CO.RA.PAN's own capture processes and three stale test children of 2026-10-08, none of them
this repository's acquisition).

No `--disarm-only` was needed and none was run. No baseline was confirmed after the fact; the authorisation of this canary is
the operator's own typed confirmation and is not reinterpreted.

## Phase A — the second canary (the operator's run, evaluated by this run)

Authorisation: **interactive, the operator in person**. Not delegated; no record. It was not repeated.

Receipt `COMPLETE`; verification `PASS` on all eight checks (67 bodies read back and verified; 43 `RAW_PRESERVED` = 43 verified
= 43 expected; 32 extractions replayed without network, 0 differ; receipt re-derived from evidence; 45 transport calls = 45
derived; no pending object; 32 item requests against a ceiling of 100).

| Outlet | Robots | Channel documents | Entries → candidates | Item requests | 2xx article pages, preserved and replayed | Result |
|---|---|---|---|---|---|---|
| `bo_el_deber` | 200, allow | RSS 200 (25 entries), sitemap 200 (55) | 80 → 80 (79 qualified, the site root rejected) | 16 | **15** (one 301 to another origin, not followed) | **`ACQUISITION_VERIFIED`, new** |
| `do_diario_libre` | 200, allow | RSS 200 (39), news sitemap 200 (527) | 566 → 463 (64 over the candidate budget, the oldest) | 16 | **16** | verified a second time, on a second day |
| `py_la_nacion` | 200, allow | Arc sitemap 200 (100) | 100 → **0**: every entry `off_origin` | 0 | 0 | **finding F8**, a defect of this project; repaired offline, below |
| `ve_efecto_cocuyo` | 200, allow | RSS 200 (10); `/sitemap.xml` **403, a JavaScript browser check** | 10 → 10 qualified | 0 (10 refused: `access_control_observed`) | 0 | **hold**: bot challenge; nothing further was asked |
| `hn_proceso_digital` | not asked | 2 refused before transport (`access_control_observed`) | — | 0 | 0 | hold of 2026-10-08 respected: **not contacted** |

Body text of the preserved article pages (baseline extractor, experimental; a measurement, not a quality claim): `bo_el_deber`
median 3 745 characters (1 630–5 554), `do_diario_libre` median 3 152 (1 981–7 582); every page ≥ 500 characters.

### The offline assumptions F1–F7 against real servers

| Finding | What the real run showed | Kind of validation |
|---|---|---|
| F1 gzip robots | `eldeber.com.bo` and `lanacion.com.py` served `robots.txt` gzip-coded; both were read (`ROBOTS_ALLOW`) and preserved as received | robustness: confirmed on two real servers |
| F2 challenge → hold | a new challenge page (WordPress.com "Checking your browser…", status 403) was classified `bot_challenge`; the origin was held and ten planned item requests were refused; the Sucuri hold of 2026-10-08 kept `hn_proceso_digital` uncontacted | generalisability: a second, different challenge product recognised |
| F3 own candidates only | each outlet requested only its own candidates (16 + 16; none across outlets) although the workspace held 13 documents of 2026-10-08 | reproducibility on the real workspace |
| F4 sitemap-index expansion | **not exercised**: 0 expansion requests — the only index channels belonged to the two held outlets | open |
| F5 DOCTYPE in CDATA | **not exercised**: the feed that carried it is `hn_proceso_digital`'s | open |
| F6 disabled channels | the three disabled channels were not selected | confirmed |
| F7 candidate budget, newest first | `do_diario_libre`: 527 sitemap entries, 64 not given a candidate — the allotment is by date; the 16 pages requested were of 2026-10-09 | confirmed on one outlet |

### Finding F8 (new): a publisher's own sitemap states its pages with `http`

`py_la_nacion`'s Arc sitemap listed all 100 pages as `http://www.lanacion.com.py/…`; the outlet is registered under
`https://www.lanacion.com.py`. The identity rule treated every entry as off-origin, so the run made no item request. That is this
project's defect, not the publisher's refusal. Repair (`channel-parser/4`): an entry stated with `http` whose host is registered
under `https` **and not** under `http`, with no port and no user part, is read as the `https` URL; the observed URL stays as
stated and the event says `scheme_read_as: https`. Nothing else is widened. Replayed offline on the preserved answer of the
run: **0 of 100** entries on the registered origin under `channel-parser/3`, **100 of 100** under `/4`. `py_la_nacion` was not
asked again: no wave of this commission covers it.

### What Phase A does not show

One run per outlet is not `OPERATIONALLY_STABLE` (three runs on three days within fourteen days). `do_diario_libre` now has two
runs on two days. `ve_efecto_cocuyo`'s feed answered; whether its articles would have is unknown and was not tried.

## Phase 1 — the delegated operator mode

Decision [CPD-0023](../decisions/CPD-0023_delegated-operator-authorisation-in-force.md) (CPD-0022, the direction, is superseded
by it; CPD-0016, CPD-0020 and CPD-0021 carry a forward link and are otherwise unchanged).

| Part | What |
|---|---|
| `src/coprepan/delegation.py` | the authorisation record (`coprepan-operator-authorization/v1`), its validation, and the one question: does this record cover exactly this canary — outlets in both directions, every limit, the policy version, the validity, a wave used once |
| `config/operator_authorizations/2026-10-09_waves-b-c1.json` | record `DOA-2026-10-09-1`: waves `wave-b` (8 outlets, 12 item requests each, at most 100) and `wave-c1` (9 outlets, 10 each, at most 90), each with its registration proposal by digest; the brief's authorising clauses quoted; what is not authorised; the holds; the gates; the stop conditions; the duty to disarm. Wave A is not in it (the operator ran it in person); C2 is not in it (the brief asks for its own versioned scope after C1) |
| `src/coprepan/canary_driver.py` | `baseline --authorization … --wave …` pins the record (id, SHA-256, path, wave) in the canary block; `run` reads the record again, checks again and compares; start state and receipt carry `operator_authorization` (for an interactive baseline: `INTERACTIVE_OPERATOR` and the name the freeze states) |
| `scripts/canary_operator.py` | `--authorization <record> --wave <label>` and nothing else: no prompt, outlets and label from the record, the record written once (one commit, tracked, clean tree, pushed), the registration proposal by digest; the freeze only when the manifest pins exactly this authorisation; commit messages name the record. The interactive mode is unchanged and refuses a baseline that pins a record. No force, skip or budget option exists |
| tests | `tests/test_delegated_operator.py`: the record (21 damaged or widened forms), the check (11 refusals with their reason), a wave used once, the driver's re-check, and the tool end to end against a temporary git repository with a bare remote — the same steps without a prompt, every step failing in turn, failing tests, an interruption, an incomplete run, a failed push, an unpushable disarming and `--disarm-only`, a record changed in a second commit, untracked, elsewhere, unpushed, edited, out of date, another proposal, an unregistered outlet; the interactive mode beside it |

The heredoc hook of the brief's §3.5 exists since the previous run (`scripts/hooks/block_heredocs.py`, 23 tests).

**The environment's permission layer.** With the operator's two `autoMode.allow` rules in place, the module and the tool were
written without a refusal. Nothing was routed around a refusal in this run, because none occurred up to this commit.

**Slips of this run against AGENTS §5** (disclosed, none wrote a file): three shell commands used a one-line bash here-string
(`<<<`) with an empty string where no input was needed; AGENTS §5 names heredocs and PowerShell here-strings, and the hook lets
this form through, but they were pointless and are not a pattern to keep. One inline `python -c` contained backticks that the
shell interpreted; the edit it made was read back and corrected by hand.

## Registration of wave B (under `DOA-2026-10-09-1`)

`scripts/apply_registration_proposal.py --proposal config/registry_review/extended_canary_proposal_2026-10-09.json --only …`
for the eight outlets of the brief, approved-by naming the delegate under the record. Result: 13 registered outlets, 69
proposed, 357 channels (five new: the feeds of `ec_el_universo`, `ec_primicias`, `es_el_mundo`, `ni_confidencial`,
`pe_la_republica`); record `config/registry_review/extended_canary_registration_2026-10-09.json`; the acquisition policy is
unchanged (`canary/2026-10-09.1`, the same three disabled channels). The operator's decided points are the proposal's values:
El Mundo's `uecdn.es` host carries the feed and no item; Confidencial has the apex origin beside `www` and `America/Managua`
(the seat in exile is a note, not a rule); La República is one section feed (economy); El Universo's access model is unknown.

The inventory (`…2026-10-09.1`) and the overview (`…2026-10-09.2`) are dated snapshots of the registry before the waves; their
tests now hold them against that registry instead of the live one, and neither file was rewritten.

## Phase B — eight outlets, the first canary armed and frozen by the delegate

| | |
|---|---|
| Authorisation | `DOA-2026-10-09-1`, wave `wave-b`, mode `DELEGATED_OPERATOR_AUTHORIZATION`; record SHA-256 `5bff88088e75ba27f337900ab18fbd030206ce87f10cc560c9c33ba56f6a8d38`. **No `ARM`, no digest was typed, asked for or simulated** |
| Arming commit | `eb8cd4c621eeb58521c3fba9fe41d4d5f9418ae5` — tests on it: **1496 passed** |
| Baseline | `docs/canary/BASELINE_FROZEN_2026-10-09_wave-b.json`, digest `cf78a8ecb9a2172abd0f32629a98608fd1c79e5e5e1df081ab6460772456d45b`, commit `583a241`; the freeze names the delegate under the record |
| Run | `acq1-20261009T142840328590Z-ba05d926eee9`, 16:28:40–16:43:23 local; receipt `COMPLETE` |
| Evidence | commit `c90fda4`, `docs/canary/evidence/acq1-20261009T142840328590Z-ba05d926eee9/` |
| Disarming | commit `ff4cd7f77bcd0250fe09351a4c038e57668f80eb`; read independently afterwards: `disabled` in the file, in `HEAD`, on `origin/main`; tree clean; tests on the disarmed tree **1496 passed** |

The environment's permission layer refused nothing: the arming, the freeze and the run went through as the operator's rules allow.

**Requests:** 103 real requests — 72 item, 31 other (8 robots files, the channel documents, 3 expansion requests, redirect
hops); every answer a 200; limits: 96 item requests (12 per outlet), 8 other per outlet. No hold, no challenge, no refusal.
One request ran under the research-TDM override of CPD-0017 (below). **Verification `PASS`** on all eight checks: 165 bodies
read back and verified, 98 `RAW_PRESERVED` = 98 verified = 98 expected, 72 extractions replayed without network with 0
differing, receipt re-derived, 103 transport calls = 103 derived, nothing pending, budget respected. 5 442 768 bytes preserved.

| Outlet | Channel documents | Entries → candidates | Item requests (all 200) | Body text, median characters (min–max) | Result |
|---|---|---|---|---|---|
| `es_el_mundo` | feed on `e00-elmundo.uecdn.es` 200 (28) | 28 → 28 | 12 | 5 140 (2 821–12 835) | **`ACQUISITION_VERIFIED`**; no item from the feed host, no paywall redirect met |
| `ni_confidencial` | feed on the apex host 200 (60); sitemap 200 (13) | 73 → 60 | 12 | 777 (436–973) | **`ACQUISITION_VERIFIED`**; short bodies — two are cartoons; whether the rest is a teaser or the extractor is for Phase 3 |
| `pe_diariocorreo` | feed 200 (100); sitemap 200 (100) | 200 → 156 | 12 | 2 649 (1 467–5 106) | **`ACQUISITION_VERIFIED`** |
| `pe_la_republica` | economy feed 200 (13) | 13 → 13 | 12 | 8 234 (3 821–9 966) | **`ACQUISITION_VERIFIED`** (one section only) |
| `sv_el_diario_de_hoy` | feed 200 (50); Yoast index 200 (92 children), **3 children read** (1 + 1 000 + 1 000 entries) | 2 143 → 250 (1 759 over the candidate budget) | 12 | 5 651 (568–8 088) | **`ACQUISITION_VERIFIED`**; F4 exercised on a real index |
| `ec_primicias` | the registered feed URL answered **301 to the home page** (HTML, 361 links); news sitemap 200 (173) | 534 → 284 | 12, **all from the home page**: 7 articles, 5 section or author pages | 3 230 (1 822–6 724) | 7 article pages preserved and replayed — verified by the letter of the criterion, **by a route that should not have been taken (finding F9)** |
| `ec_el_universo` | Arc feed 200 (100), read under `ALLOW_RESEARCH_OVERRIDE` (`robots.txt`: `Disallow: /arc/outboundfeeds/rss/*` for every agent) | 100 → **0**: every entry is on `https://eluniverso.com`, the registry holds `https://www.eluniverso.com` | 0 | — | no acquisition: **a registration gap (F11)**, not a refusal. No login or paywall was met because no article was asked for |
| `gt_lahora` | feed 200 and Yoast index 200, both **unparseable**: three empty lines before the XML declaration | 0 | 0 | — | no acquisition: **a defect of this project (F10)** |

**New in this wave:** 6 outlets with article pages preserved, verified and replayed (5 cleanly, `ec_primicias` with the caveat
above), in **five countries that had no verified outlet before: ec, es, ni, pe, sv** (verified before: do, bo). Of the six, four were never productive or had no channel in the legacy system (`ec_primicias`,
`ni_confidencial`, `es_el_mundo`, `pe_la_republica`); two were productive there (`pe_diariocorreo`, `sv_el_diario_de_hoy`).
Ecuador and Nicaragua, which had no accepted article in the legacy corpus, each have one outlet with preserved articles.

### Findings of wave B and their repair (offline; none was asked again)

| | Finding | Repair | Shown by |
|---|---|---|---|
| F9 | a channel registered as `rss` answered with an HTML page (a redirect to the home page); the page was read as a listing and what it linked was requested without an allow rule, because the rule looked at the channel's registered kind only | `canary-driver/5`: a candidate first listed by an **HTML document** waits for an allow rule, whatever kind its channel is registered as | regression test (fails without the repair); replay of the preserved answer: 361 links, 336 on the outlet's host — all would wait |
| F10 | white space before the XML declaration made a feed and a sitemap index unparseable | `channel-parser/5`: leading white space is dropped for reading; the preserved bytes are the received ones; a DTD is still refused, white space alone is still an empty document | regression test; replay of the two preserved answers: feed `PARSED`, 10 items; index `PARSED`, 350 children |
| F11 | `ec_el_universo`'s own feed names the apex host for every article; the registry holds the `www` host only | **not applied**: adding an origin is a registration, and no further canary of this wave is authorised to use it. Proposed to the operator: register `https://eluniverso.com` beside `www`, as was decided for Confidencial | the preserved feed (100 of 100 entries on the apex host) |

The five section pages requested from `ec_primicias` are preserved like every answer and are not deleted; they are not
articles and no label says they are. A wave is one canary: neither `gt_lahora` nor the two Ecuadorian outlets were asked a
second time.

The scheme repair of F8 was live in this wave and changed nothing here: no entry of these eight outlets used `http`.

## Registration of wave C (under `DOA-2026-10-09-1`)

Checked before applying, against the registry as it stood: each of the nine ids is free, no host of theirs is an origin of a
registered or proposed outlet, every id carries the prefix of its `country_id`, every channel lies on its outlet's own origin,
no similar id exists. The countries are those reported on (`cu_cubanet`, the Nicaraguan outlets: exile seats are notes, not the
country). The discovery evidence is the operator's research supplement of 2026-10-09 — passive, no request by this project.

Applied from `config/registry_review/wave_c_proposal_2026-10-09.json` (digest pinned by the record): 91 outlets, **22
registered**, 69 proposed, 373 channels; record `config/registry_review/wave_c_registration_2026-10-09.json`; the policy is
unchanged. The review package's naming convention would spell two of the new ids differently (`hn_criterio_hn`,
`ni_articulo_66`); they are registered under the ids of the proposal, and the package only recommends.

## Phase C1 — nine outlets new to the registry

| | |
|---|---|
| Authorisation | `DOA-2026-10-09-1`, wave `wave-c1`, mode `DELEGATED_OPERATOR_AUTHORIZATION` (record SHA-256 as in wave B). Nothing typed, nothing simulated |
| Arming commit | `25a182614ed69bb035c0b9d12286acd391535023` — tests on it: **1500 passed** |
| Baseline | `docs/canary/BASELINE_FROZEN_2026-10-09_wave-c1.json`, digest `455b04bea0e46cb85b0ab96db3ec1114714267dc37b6555b0066b717545caf62`, commit `9cd3f3f` |
| Run | `acq1-20261009T151252138498Z-114b77603c1f`, 17:12:52–17:22:19 local; receipt `COMPLETE`; driver `canary-driver/5`, parser `channel-parser/5` |
| Evidence | commit `0d53ca3`, `docs/canary/evidence/acq1-20261009T151252138498Z-114b77603c1f/` |
| Disarming | commit `fe63275df537707fcdca6ed1de162f4b11acf85d`; read independently: `disabled` in the file, in `HEAD`, on `origin/main`; tree clean; tests on the disarmed tree **1500 passed** |

**Requests:** 73 real requests — 47 item, 26 other; limits: 90 item requests (10 per outlet), 8 other per outlet. Answers: 62 ×
200, 2 × 403, 1 × 404, 1 × 503. Refused before transport: 4 (`access_control_observed`), 5 (`canary_budget_exhausted`).
**Verification `PASS`** on all eight checks: 231 bodies read back and verified, 66 `RAW_PRESERVED` = 66 verified = 66 expected,
41 extractions replayed without network with 0 differing, receipt re-derived, 73 transport calls = 73 derived, nothing pending,
budget respected. 2 026 480 bytes preserved.

| Outlet | Channel documents | Entries → candidates | Item requests | Article pages (200), preserved and replayed | Result |
|---|---|---|---|---|---|
| `ar_el_tribuno` | two feeds 200 (25 + 25) | 50 → 40 | 10 | **10** | **`ACQUISITION_VERIFIED`** |
| `bo_opinion` | two feeds 200 (20 + 20) | 40 → 37 | 10 | **10** | **`ACQUISITION_VERIFIED`** |
| `cu_14ymedio` | feed 200 (148); section page 200 (122 links) | 270 → 197: 148 qualified (feed), **47 waiting** (listing) | 10 | **9** (one 503) | **`ACQUISITION_VERIFIED`**; the feed also carries sponsored blog entries (one of the nine is an advertisement for a crypto exchange) |
| `hn_criterio` | feed 200 (5), read under `ALLOW_RESEARCH_OVERRIDE` (`Disallow: /feed/$`); category page 200 and **two further pages by numbered pagination** (90 + 92 + 93 links) | 280 → 54: 5 qualified (feed), **47 waiting** (listing) | 5 | **5** | **`ACQUISITION_VERIFIED`** (exactly the five the feed lists) |
| `ni_nicaragua_investiga` | `robots.txt` 404 (`ROBOTS_UNAVAILABLE`); feed 200 (13) | 13 → 13 | 10 requests for 5 pages; 5 further refused by the budget | **5** | **`ACQUISITION_VERIFIED`**; feed links carry `utm_` parameters that the site redirects, and every hop is a request |
| `uy_montevideo_portal` | two feeds 200 (8 + 52) | 60 → **1** | 2 requests | 1 | not verified: **finding F12**, below |
| `pr_noticel` | category page 200 and two further pages (234 + 233 + 233 links) | 700 → 112: **110 waiting**, 2 rejected | 0 | 0 | as designed: a listing is its only channel; preserved, nothing requested |
| `cu_cubanet` | `robots.txt` **403, a browser challenge** | — | 0 (2 channel documents refused) | 0 | **hold**; one request was made and nothing after it |
| `ni_articulo66` | `robots.txt` **403, a browser challenge** | — | 0 (2 refused) | 0 | **hold**; one request was made and nothing after it |

Body text under the experimental baseline extractor (a measurement of the extractor, not of the pages): `ar_el_tribuno` median
2 936 characters, `bo_opinion` 1 919, `ni_nicaragua_investiga` 4 734, `uy_montevideo_portal` 3 200; `cu_14ymedio` 719 and
`hn_criterio` 314 — **the preserved pages of those two are full article pages** (22 to 111 paragraph elements each; read from the
packs), so the short text is the extractor's, and is material for Phase 3, not a doubt about the acquisition.

**New in this wave:** 5 outlets with article pages preserved, verified and replayed, all new to the project; **ar, cu and hn**
had no verified outlet before (bo and ni did, from waves A and B). Three listing outlets have real listing answers preserved
(8 pages in all).

### What the wave qualified, as the brief asked

| Asked | Result |
|---|---|
| official RSS catalogues, section and regional feeds | the front-page and regional feeds of El Tribuno (Salta) and Opinión (Cochabamba) yield articles; Montevideo Portal's two `anxml.aspx` feeds parse (60 entries) and fail at identity (F12) |
| HTML archives | `ni_articulo66`'s yearly archive and `cu_cubanet`'s list were **not reached**: both origins challenge even `robots.txt` |
| numbered pagination | **exercised on real servers for the first time**: `/category/…/page/2/` and `/page/3/` followed for `hn_criterio` and `pr_noticel` within the reserved expansion budget (2 each) |
| dates | not evaluated from these pages in this run |
| candidate filter | every link of a listing waited (204 candidates); nothing a listing named was requested |
| navigation links | on the preserved pages 23 of 47 (`hn_criterio`), 95 of 110 (`pr_noticel`) and 27 of 47 (`cu_14ymedio`) waiting links are navigation, corporate pages, video or paging — the reason a listing needs a rule |

### Findings of wave C1

| | Finding | Status |
|---|---|---|
| F12 | `uy_montevideo_portal`'s feeds link articles as `auc.aspx?<number>`: a query without a parameter name. The URL key drops it, so 60 entries are **one candidate** | not repaired: it needs a URL rule that can keep a nameless query, i.e. a new URL-key rule version for that outlet, with its own tests. Recorded for the next run |
| F13 | feed links with `utm_` parameters cost two requests per article where the site redirects them | by design (a hop is a request); a candidate could be requested by its key instead — a change to weigh, not made |
| — | two more origins answer `robots.txt` with a browser challenge (403, a "Just a moment..." page): a third kind of challenge page, recognised by the classifier of F2 | held; four challenged origins in all now |
| — | `canary-driver/5` (F9) and `channel-parser/5` (F10) were live: no feed of this wave answered with HTML or leading white space, so neither was exercised on a real server | open |

## Preparing C2 — the allow rules, written from the preserved pages

The eight listing pages of C1 were read from the packs (copies in the session scratchpad, nothing fetched). For each outlet
every waiting candidate was sorted by eye into article and not-article from the visible structure of the address and the page,
and a rule was written and applied to all of them offline:

| Outlet | Rule (`allow_path_patterns`) | Waiting in C1 | Qualified under the rule | Not qualified | Checked |
|---|---|---|---|---|---|
| `pr_noticel` | `^/ultima-hora/[0-9]{8}/[a-z0-9-]+/?$` | 110 | 15 — all articles (`/ultima-hora/20261008/…`, `/ultima-hora/20261009/…`) | 95: categories (58), authors (29), paging (2), the English tree (3), login, contact, privacy (3) | no article among the 95; no non-article among the 15 |
| `hn_criterio` | `^/[a-z0-9]+(-[a-z0-9]+){3,}/?$` (a root-level slug of at least four words) | 47 | 24 — all articles | 23: categories and paging (16), `/contacto`, `/nosotros`, `/quienes-somos`, `/especiales`, `/redes`, `/donaciones/`, `/politica-de-privacidad` | as above. The rule is a heuristic of this site's addresses: an article with a slug of three words or fewer is missed, which errs on the safe side |
| `cu_14ymedio` | `^/(cuba\|internacional)/[a-z0-9-]+_1_[0-9]+[.]html$`, rejecting the terms page | 47 | 20 — all articles | 27: sections, topics, corporate pages, four videos (`_7_`), the terms page | **developed and not installed** — see below |

**Which outlets C2 concerns, and why not the third.** `pr_noticel` and `hn_criterio`: a qualified rule, no access or policy
problem, and the listing is what the item budget would go to (`pr_noticel` has no other channel; `hn_criterio`'s feed has five
entries, all fetched). `cu_14ymedio` is left out for two reasons that are facts of the design, not of the site: an allow rule
applies to every candidate of the outlet, so it would narrow the outlet's **feed** to two sections — a content decision this
run was not given —, and 138 qualified feed candidates are due before any listing candidate, so its ten requests would not
test the listing route at all. `cu_cubanet` and `ni_articulo66` are held (an unresolved access problem, by the brief's own
condition). The other four outlets of C1 have no listing channel.

The two rules are in `config/candidate_rules.json` with versions, a regression test holds them against the addresses the
preserved pages named, and the scope is its own record: `config/operator_authorizations/2026-10-09_wave-c2.json`
(`DOA-2026-10-09-2`, wave `wave-c2`: two outlets, ten item requests each, 20 in all, the ordinary eight other requests each).
A canary of two outlets under ten requests each needed one rule: a wave's limits cap the budget
([CPD-0024](../decisions/CPD-0024_wave-limits-cap-the-canary-budget.md)); for waves B and C1 the capped budget equals the one
they ran under.

## Phase C2 — articles from HTML listings: two starts that stopped, and the run

### First start: stopped at the tests (no request)

`fec8088` armed under `DOA-2026-10-09-2`; the suite on the arming commit: **1 failed**, 1504 passed. `tests/test_schedule.py`
asserted that `config/candidate_rules.json` has no entry, and I had committed the two rules after running only the test files
I thought concerned — not the whole suite. The tool stopped and disarmed (`2676d6b`; read back). No baseline, no request; the
wave was not used. Repair: the test holds the file to the two reviewed entries (`9bd6422`; full suite 1505 passed).

### Second start: frozen, then stopped at its first answer — two requests without a record (F14)

`fd943e0` armed (tests on it 1505 passed), baseline frozen (`ab2a85f`, digest
`ac6d68aefd66b154a2a794c3385d522306180e9d85fc627644d453def6e0237f`), preflight `READY`. The run
`acq1-20261009T160824878550Z-12eea03e3f04` then failed while recording its first answer: wave C1 had sealed
`pk1-hn_criterio-20261009-000` earlier the same UTC day, and `record_exchange` always chose rollover number `000` — "a sealed
pack is never appended to". Disarmed (`2d753c6`; read back).

**What went out and was lost.** By the code path the fetch had completed before the record failed: **two requests to
`criterio.hn`, its `robots.txt` and its feed. Their answers were received and are not recorded** — no fetch record, no preserved
bytes; the request log holds the planned row of the feed and no end. That is a gap in this project's first rule (what is asked
is kept), caused by this project. No item was requested. It is not papered over: the run's record now carries a result
`FAILED` that states the two requests and that it was written afterwards by this agent run, with the project's own `close_run`.

Why no test had met it: a second run for one outlet on one UTC day in one workspace had never happened — the first canaries
were a day apart. Repair (`1305eae`): `record_exchange` writes to the first pack of that outlet and day that is not sealed
(`pack.first_unsealed_id`). Regression test: two runs in one workspace on one day; the second records into `-001`, every sealed
file is byte-identical afterwards; it fails without the repair. Full suite 1506 passed.

The frozen baseline of that start used up `wave-c2` (a wave is one canary), and a repair changes the commit a baseline pins. The
brief allows, after a repaired defect of our own, one further live attempt "innerhalb einer gültigen Autorisierung und der
verbleibenden Budgets" and names "begrenzte erneute Validierung" among the agent's own decisions. That attempt is its own
write-once record, `DOA-2026-10-09-3` (`wave-c2-repeat`): the same two outlets, the same item limits (none had been used),
**other requests lowered from eight to six per outlet** for the two already made, and no further repetition under it. Whether
that reading of the brief is the operator's is for the operator to say; it is recorded as the agent's reading.

### The run

| | |
|---|---|
| Authorisation | `DOA-2026-10-09-3`, wave `wave-c2-repeat`, mode `DELEGATED_OPERATOR_AUTHORIZATION`; record SHA-256 `6f285fc40624ab8ae45f8a3cbb148a03cb228179cce09ebd7f47e62e9e28b4b9` |
| Arming commit | `69bd5fea1f471bc0b8971d83275b70276c16b236` — tests on it: **1506 passed** |
| Baseline | `docs/canary/BASELINE_FROZEN_2026-10-09_wave-c2-repeat.json`, digest `462604a3f6856ca07ad736467b5429e073780af357ba2b7660fc2e683b8b9f7e`, commit `0e6d667`; it pins the candidate rules |
| Run | `acq1-20261009T162552356454Z-75371bad809b`, 18:25:52–18:30:17 local; receipt `COMPLETE` |
| Evidence | commit `63022d9`, `docs/canary/evidence/acq1-20261009T162552356454Z-75371bad809b/` |
| Disarming | commit `8310c030af7ea3986251188bf4897655ebb3d336`; read independently: `disabled` in the file, in `HEAD`, on `origin/main`; tree clean; tests on the disarmed tree 1506 passed |

**Requests:** 29 — 20 item, 9 other (limits: 20 item, 10 per outlet; 6 other per outlet: `hn_criterio` 5, `pr_noticel` 4);
every answer a 200; nothing refused; one request under the research override (`hn_criterio`'s feed, as in C1). 944 819 bytes
preserved, in the packs `-001` of the day; the sealed packs `-000` are unchanged.

| Outlet | Listing pages read | Candidates decided under the rule | Item requests | Article pages (200), preserved and replayed |
|---|---|---|---|---|
| `pr_noticel` | 3 (the category page and two numbered pages) | 17 qualified, 97 rejected (categories 60, authors 29, the English tree 3, login 1, others) | 10 | **10**, all articles of `/ultima-hora/2026100[89]/…` — **`ACQUISITION_VERIFIED`, a new outlet and a new country (pr)** |
| `hn_criterio` | 3, and its feed (5 entries, all fetched in C1) | 29 qualified, 25 rejected | 10 | **10**, all articles, none of them in the feed: articles reached only through the listing |

All twenty pages were read from the packs: each is an article page (42 to 70 paragraph elements; titles of articles). No
navigation page was requested. Under the baseline extractor `pr_noticel`'s body text has a median of 6 213 characters and
`hn_criterio`'s 349 — the extractor's result on that site, as in C1.

**Verification.** As the tool ran it: **`FAIL` — seven checks `PASS`, `recovery_diagnosis` `FAIL`** (`INCOMPLETE_RESUMABLE`: the
interrupted run above had no result). That file is the evidence of record and is unchanged. After the interrupted run was
closed as `FAILED`, the same verification was run again into a second file beside it,
`verification_after_closing_the_interrupted_run.json`: **`PASS`** on all eight (260 bodies read back and verified; 29
`RAW_PRESERVED` = 29 verified = 29 expected; 20 extractions replayed, 0 differ; receipt re-derived; 29 = 29 transport calls;
nothing pending; budget respected; workspace `CLEAN`).

**What C2 shows and does not.** A reviewed allow rule turns a preserved listing into article requests without one navigation
page, on two sites with different address schemes, and numbered pagination is followed within the reserved budget. It does
not show that the rules hold beyond the three pages each was written from, nor that a listing is a complete route (thirty
entries of one category are not an outlet's production).

## The defects of this run, in one place

| | Where it showed | Whose | State |
|---|---|---|---|
| F8 | A: `py_la_nacion`, 100 entries stated with `http` | ours | repaired (`channel-parser/4`), replayed offline; not seen live since |
| F9 | B: `ec_primicias`, a feed URL that answers with the home page | ours | repaired (`canary-driver/5`), replayed offline; not seen live since |
| F10 | B: `gt_lahora`, white space before the XML declaration | ours | repaired (`channel-parser/5`), replayed offline; not seen live since |
| F11 | B: `ec_el_universo`, feed on the apex host | registration | open: a second origin is for the operator |
| F12 | C1: `uy_montevideo_portal`, a nameless query identifies the article | URL rules | open: needs a URL-key rule version |
| F13 | C1: `ni_nicaragua_investiga`, `utm_` redirects cost a request each | by design | noted |
| F14 | C2: a sealed pack of the same day | ours | repaired, regression-tested, **and exercised live** in the repeat |
| — | C2: a test that pinned the rules file empty; a commit without the whole suite | mine | repaired; the arming gate caught it before any request |

Validation classes, as the brief asks: the preservation, fixity and replay checks of each run are **reproducibility** (the same
bytes, the same extraction, without network). F1 on two more servers, the challenge classifier on two more products, and
pagination on two sites are **robustness** of single mechanisms. Thirteen new outlets with feeds, sitemaps and
listings of different makes are a first, small step of **generalisability** of the acquisition path — and the four defects
found only on real servers are the measure of how far offline replay had carried. **Replicability** (the same result on
another day, by another run) is not shown for any outlet but `do_diario_libre`, and there only twice.

## Phase-3 review readiness

There are now 157 article pages of 14 outlets in 11 countries, preserved with their raw bytes — more varied material than the
thirteen pages of one outlet the extractor comparison was prepared on. The baseline extractor's body text ranges from a median
of 314 characters (`hn_criterio`) to 8 234 (`pe_la_republica`) on pages that are all full articles: that spread is the case
for the comparison, and the material for it. Ready: the pages, their replay, the candidates' wrappers (CPD-0018). Not done and
not claimed: any comparison on these pages, any human gold — a scientific step of its own.

## Tests

| When | Result |
|---|---|
| on the arming commit of the second canary (the operator's tool) | passed (the tool does not arm otherwise; the count is in its baseline) |
| on the arming commits of waves B / C1 / C2-repeat, and again on each disarmed tree | **1496 / 1500 / 1506 passed**, twice each |
| on the arming commit of the first C2 start | 1 failed, 1504 passed → stopped, disarmed |
| on the arming commit of the second C2 start | 1505 passed |
| full suite on the final tree, switch off | **1506 passed, 14 skipped** |

Skipped throughout: 7 tests that need the extractor tools of the extra `phase3`, 1 symbolic-link test this account cannot
run, and 6 that hold a proposal or an inventory version against a registry that has since been registered into (each says so).
New in this run: `tests/test_delegated_operator.py` (69 tests) and ten tests in `tests/test_canary_findings.py` (F8, F9,
F10, F14, the two listing rules).

## Files and git

Created: `src/coprepan/delegation.py`; `config/operator_authorizations/` (three records); `tests/test_delegated_operator.py`;
`docs/decisions/CPD-0023_…`, `CPD-0024_…`; `config/registry_review/extended_canary_registration_2026-10-09.json`,
`wave_c_registration_2026-10-09.json`; three frozen baselines and four evidence directories under `docs/canary/` (written by
the operator tool; one further verification file added beside the last); this report.
Changed: `scripts/canary_operator.py`, `src/coprepan/canary_driver.py`, `canary_evidence.py`, `discovery.py`,
`http_acquisition.py`, `core_pipeline.py`, `pack.py`; `config/outlet_registry.json`, `config/candidate_rules.json`,
`config/registry_review/outlet_review_package.json`; tests of readiness, source discovery, source expansion, schedule, canary
findings, the operator tool; the suite manifest; `docs/STATUS.md`, the runbook (§11), the decision registry, the architecture
index, the terminology table, forward links in CPD-0016, CPD-0019 to CPD-0022.
Not changed: any frozen baseline or receipt of the past; the acquisition policy other than the switch, which is `disabled`;
the inventory and overview of 2026-10-09; CO.RA.PAN and the legacy repositories (not opened in this run).
Outside the repository: the runtime workspace and the preservation root (written by the canaries; one run result written by
this run, as stated); read-only copies of packs in the session scratchpad.

Commits of this run on `main`, all pushed: the delegated mode (`a5f0977`), the registrations (`1000bee`, `94a8ccc`), the
evaluations and repairs (`febb3d7`, `22f4503`, `9bd6422`, `1305eae`), the tool's own arming, baseline, evidence and disarming
commits of each canary, and the closing commit.

## Open gates

- `OPERATIONALLY_STABLE` for any outlet: two more runs on two more days for thirteen outlets, one more for `do_diario_libre`.
- The four held origins: nothing is to be tried; whether to write to the publishers is the operator's.
- F11 and F12; a live confirmation of F8, F9 and F10 (the next canary that includes `py_la_nacion`, `gt_lahora`, `ec_primicias`).
- Whether `cu_14ymedio` is to be narrowed to sections by an allow rule; whether sponsored feed entries are to be told apart.
- The operator's review of CPD-0023 and CPD-0024, of the three authorisation records as transcriptions of the brief — in
  particular of `DOA-2026-10-09-3` — and of the seventeen registrations made under them.
- Every production gate of `docs/STATUS.md` §5, unchanged.

## Operator report

1. **Ergebnis.** 13 neue Zeitungen liefern tatsächlich Artikel (14 mit der schon verifizierten), in 10 neuen Ländern (11
   insgesamt: do, bo, ec, es, ni, pe, sv, ar, cu, hn, pr). 163 Seiten sind konserviert, verifiziert und ohne Netz replayt, 157
   davon Artikel. Ecuador und Nicaragua, im Legacy-Korpus ohne einen akzeptierten Artikel, haben je mindestens eine Zeitung mit
   Artikeln (Nicaragua zwei).
2. **Status.** Gesamt `PARTIAL`. Phase 0 `PASS`; Delegation `PASS`; A `PARTIAL` (2 von 5); B `PARTIAL` (6 von 8); C1 `PARTIAL`
   (5 von 9 mit mindestens fünf Artikeln); C2 `PASS` (2 von 2, 20 Artikel aus HTML-Listings) – nach zwei gestoppten Starts,
   von denen einer zwei Requests an `criterio.hn` ohne konservierte Antwort hinterlassen hat. Das ist dokumentiert, nicht
   geheilt.
3. **Autonomie.** Ja: Der delegierte Operator-Modus ist implementiert (CPD-0023) und viermal real end-to-end gelaufen –
   armieren, Tests auf dem Arming-Commit, Baseline, Freeze, Lauf, Verifikation, Disarming mit Rücklesen – ohne `ARM`, ohne
   Digest-Eingabe, ohne simulierte Bestätigung. Die Berechtigungsschicht von Claude Code hat mit Ihren Regeln nichts verweigert.
   Zwei Starts wurden real gestoppt (Testfehler auf dem Arming-Commit; Abbruch bei der ersten Antwort) und jedes Mal sauber
   disarmt.
4. **Technik.** Auf echten Websites funktionieren jetzt: RSS (WordPress, Arc, eigene Systeme, auch auf fremdem Feed-Host),
   News-Sitemaps, ein Yoast-Sitemap-Index mit Expansion, gzip-codierte `robots.txt`, HTML-Listings mit nummerierter Pagination
   und geprüften Allow-Regeln, Challenge-Erkennung bei drei verschiedenen Challenge-Seiten mit sofortigem Hold. Vier eigene Fehler
   wurden erst an echten Servern sichtbar und sind repariert (F8, F9, F10, F14); zwei sind offen (F11 El Universo, F12
   Montevideo Portal).
5. **Wissenschaft.** Nachgewiesen ist technische Erreichbarkeit einer breiteren Quellenbasis: von einer Zeitung in einem Land
   auf vierzehn in elf, darunter vier, die im Legacy-System nie produktiv waren oder keinen Kanal hatten (`ec_primicias`,
   `ni_confidencial`, `es_el_mundo`, `pe_la_republica`), und sechs, die es dort gar nicht gab. Nicht nachgewiesen: Stabilität (ein Lauf je Zeitung),
   Vollständigkeit einer Quelle, Repräsentativität. Vier unabhängige Medien (Efecto Cocuyo, CubaNet, Artículo 66, Proceso
   Digital) bleiben hinter Bot-Challenges – eine neue, benennbare Selektionsverzerrung zulasten genau solcher Medien.
6. **Nächster Schritt.** An zwei weiteren Tagen dieselben 22 Outlets erneut laufen lassen (das Drei-Läufe-Kriterium; dabei
   werden F8, F9 und F10 erstmals live geprüft). Von Ihnen brauche ich dafür nur: die Durchsicht der drei
   Autorisierungsdatensätze und der beiden CPDs, und die Entscheidung zu F11 (Apex-Origin für El Universo).
