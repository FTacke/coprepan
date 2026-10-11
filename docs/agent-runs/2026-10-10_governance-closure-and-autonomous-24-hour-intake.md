# Run report — Governance closure and the autonomous 24-hour intake

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Commission | the operator's brief "CO.PRE.PAN 3.0 – Governance Closure & Autonomous 24-Hour Intake" |
| Decisions | [CPD-0028](../decisions/CPD-0028_confirmation-of-the-open-points-of-cpd-0025-to-cpd-0027.md), [CPD-0029](../decisions/CPD-0029_the-bounded-timed-intake.md) |
| State of this report | written in two steps: before the pilot (§1–§4) and at the launch of the 24-hour intake (§5–§8). What the intake yields is not in it: that is the finalizer's report |

## 1. Starting state

HEAD `f7bf96d` = `origin/main`, tree clean, `external_acquisition` `disabled`. Workspace diagnosis `CLEAN`; ledger 847
`RAW_PRESERVED`, 11 `FETCH_FAILED`. Readiness `2026-10-10.1`: 87 outlets (85 tier A, 2 tier B), 121 channels, 20 countries;
10 origins and 9 URLs held.

## 2. Governance closure (CPD-0028)

- **CPD-0025, threshold:** confirmed by the brief as a minimal technical proof. The rule is in one place in the builder and
  asserted by `test_a_stage_claims_what_the_evidence_shows_and_no_more`; the tracked inventory is byte for byte what the
  builder gives.
- **CPD-0026, identity adoption:** the eight conditions of the brief were checked read-only against the tables moved aside
  on 2026-10-09 and the tables in force. Exactly one document row and one observation row differ (`uy_montevideo_portal`:
  the URL-rules label v1 → v2, and the requested URL key that now keeps the nameless query). No row is lost, no document
  merged, no id reassigned; workspace `CLEAN`; the rebuild from preserved evidence gives the tables in force; the old
  directory is kept. Evidence: `docs/identity/identity_adoption_review_2026-10-10.json`.
- **CPD-0027, access policy:** applies to an intake unchanged. `es_el_pais` excluded; `ve_efecto_cocuyo` by its feed only;
  every hold kept.
- Each of the three records has one dated row pointing to CPD-0028; nothing else in them was touched. No confirmation typed
  by a person exists for any of the three, and none is recorded.

## 3. What was built (CPD-0029)

| Part | Where |
|---|---|
| plan, intake authorisation and its check, baseline pin, budgeted fetcher, selection, controller, finalizer | `src/coprepan/intake.py` |
| measurement, anomaly flags, review package, final report | `src/coprepan/intake_report.py` |
| `plan`, `start`, `tick`, `status`, `stop`, `import-report`; the disarming; the scheduled task | `scripts/intake_operator.py` |
| two optional arguments of `run_http_acquisition`: `select_due` (which due candidates, in which order) and `tables` (the caller's loaded discovery tables) | `src/coprepan/http_acquisition.py` |
| tests | `tests/test_intake.py`, `tests/test_intake_operator.py` |

Nothing of the fetcher, the gate, robots handling, discovery, the pack, preservation, identity or extraction was
reimplemented; the controller calls them.

## 4. Offline qualification

`tests/test_intake.py` and `tests/test_intake_operator.py` against a loopback outlet whose feed changes from poll to poll, a
clock that does not wait, and a temporary git repository with a bare remote: the plan and what it leaves out; hourly polls;
what is new asked before stock, and stock held to one page per cycle; every budget, with refusals on record; the hourly
limit as a sliding hour; a redirect hop counted; the deadline and its margin; a machine that slept through the window; a
restart that keeps deadline and budgets and closes the cut run as `FAILED`; a process that dies between receiving and
preserving; one controller at a time (a second process holding the lock); a changed plan refused; a stop request; permission
withdrawn; the preservation target away and back; an outlet that becomes held; the finalizer's checks, its repeatability, a
damaged preserved pack; the authorisation and its ceilings; a record and a plan committed exactly once; what a restart
re-checks; the disarming (one file, nothing else, no force, a refused push reported, off `main`); a start refused before
arming; a whole tick; a tick on changed code; the anomaly flags.

## 4a. A commit with the wrong message

Commit `227d2d0` holds everything of §2 to §4 (21 files) and was pushed under a message that belongs to an older commit
("Operator's research supplement of 2026-10-09 …"): the message file of this commit could not be written over a file of the same
name left by an earlier run, and the stale file was used. The content of the commit is right; only its message is wrong. A pushed
commit is not rewritten here (no forced push); the commit that adds this section carries the message `227d2d0` should have had.

## 5. The short integrated canary of the controller (`in1-20261010-pilot`)

Under `DIA-2026-10-10-1` (`config/intake/authorizations/2026-10-10_pilot.json`): six outlets (`ar_el_tribuno`, `cr_la_nacion`,
`cu_havanatimes`, `hn_criterio`, `uy_montevideo_portal`, `ve_efecto_cocuyo`), eleven channels, 30 minutes, cycles of ten minutes, at most
150 requests. Started by `scripts/intake_operator.py start`: armed in `8d858ac`, full suite on the arming commit, baseline `e5c9b558…`
frozen in `29c6d57`, preflight `READY`, state written at 2026-10-10T08:20:47Z (10:20:47 local), scheduled task registered and started.
The session did nothing further: the task ran the controller, finalized, disarmed (`10fe6fd`) and removed itself at 08:50:07Z.

| | |
|---|---|
| outcome | `COMPLETED`, verification `PASS` (seven checks) |
| cycles, runs, restarts, outlet errors | 3, 3, 0, 0 |
| requests | 46 of 150: 21 item (three redirect hops among them), 25 other |
| fetch records, answers | 40, all `200`, all `RAW_PRESERVED`, 40 bodies read back from the preservation root and their digests compared |
| item pages 2xx | 18, three of each outlet; all technically usable under the experimental extractor |
| last request decided | before 08:49:17Z, 90 seconds before the deadline 08:50:47Z; none at or after it |
| recovery diagnosis after the run | `CLEAN`, identity `CORRECT` |
| disarming | `disabled` in the file, in HEAD and on `origin/main`; the task is gone |
| anomaly flags | `hn_criterio`: three pages `very_short_text` and `duplicate_body_of_other_document` (median 347 body characters) — the known case |

What it showed:

- **No page of the 18 is "new".** All 327 candidates first listed were dated before the start by their channels; in half an hour that is
  what is to be expected, and the measurement says so instead of counting first sightings as new articles.
- **A cycle is slow by design.** With ten seconds between requests to one origin and outlets served one after another, the first cycle
  took 4 min 41 s for six outlets (about 47 s each). For 87 outlets that is about an hour: the hourly polls of the 24-hour intake will in
  effect be spaced by the length of a cycle, an hour or somewhat more. Not changed: it is the price of one request at a time per origin
  without concurrency in the workspace.
- **Not tested for real: a killed controller.** Ending the controller's process from this session was refused by the permission layer of
  the agent's environment and was not attempted another way. The restart is qualified offline (a process that ends mid-cycle, a process
  that ends between receiving and preserving, a second process holding the lock) and by the task having started the controller.
- Nothing was repaired after the pilot: no defect was found. The code of the 24-hour intake is the code of the pilot.

Report of the pilot: `docs/intake/reports/in1-20261010-pilot/` (imported by `import-report`).

## 6. Launch of the 24-hour intake (`in1-20261010-24h`)

| | |
|---|---|
| intake id | `in1-20261010-24h` |
| authorisation | `DIA-2026-10-10-2`, `config/intake/authorizations/2026-10-10_24h.json` (`DELEGATED_INTAKE_AUTHORIZATION`; no typed confirmation) |
| plan | `config/intake/plans/in1-20261010-24h.json`, SHA-256 `dc313e20ecf2ce2a2de46dbe4dca0d9b4aa8197d34d975eba0f6ed508ec94cc0` |
| scope | 87 outlets (85 tier A, 2 tier B), 121 channels, 20 countries; `es_el_pais`, `co_el_tiempo`, `mx_la_jornada` not in it; no held origin or URL in it |
| arming commit (pinned) | `c1bba1b`; full suite on it: 1569 passed |
| baseline | `docs/intake/BASELINE_FROZEN_2026-10-10_in1-20261010-24h.json`, digest `4d7816d9477c9c8afdc4c640cfa08efc049dbb8bd201ffe58294c063cdb486da`, commit `284b99d` |
| preflight | `READY` |
| **started** | **2026-10-10T08:59:45Z — 10:59:45 Europe/Berlin** |
| **deadline** | **2026-10-11T08:59:45Z — 10:59:45 Europe/Berlin**; no request is decided after 08:58:15Z |
| status at launch | `RUNNING`; the scheduled task `coprepan-intake-in1-20261010-24h` started the controller at 08:59:48Z |

Budgets (ceilings, enforced at the transport, counted from the fetch records): 120 item requests per outlet, 10 per outlet in any
hour, 150 per origin, 12 000 requests in all — redirects, robots files and channel documents included. Per cycle an outlet is asked
for at most three pages, at most one of them stock. Polls: feeds and news sitemaps hourly, listings every 2 h, sitemap indexes and
large sitemaps every 6 h, the three archive-sized only channels (`cu_juventud_rebelde`, `pe_elperuano`, `py_ultima_hora`) every 12 h.

## 7. What runs without this session, and where to look

- **The task** `coprepan-intake-in1-20261010-24h` (Task Scheduler, the logged-in user, every five minutes) is the controller while the
  intake runs and, after the deadline, the finalizer: preserve, verify, receipt, measurement, anomaly flags, review package, report,
  disarm (one commit of `config/acquisition_policy.json`, a plain push), remove itself.
- **State and logs:** `<RUNTIME>/intake/in1-20261010-24h/state.json`, `controller.log`, `tick.log`.
  `python scripts/intake_operator.py status --intake in1-20261010-24h` prints the state with the remaining time.
- **The final report** will be in `<RUNTIME>/intake/in1-20261010-24h/report/` (`FINAL_REPORT.md`, `receipt.json`, `measurement.json`,
  `review_package.json`). `python scripts/intake_operator.py import-report --intake in1-20261010-24h` copies it to
  `docs/intake/reports/in1-20261010-24h/`; committing it is a person's step.
- **To stop early:** `python scripts/intake_operator.py stop --intake in1-20261010-24h`, or set the switch to `disabled` in the
  policy file — it is read before every request.

## 8. Known limits at launch

- **The task runs in the logged-in user's session.** A locked screen is fine; a log-off or a shutdown pauses the intake. The deadline
  still binds: after it nothing is requested, and the finalizer and the disarming run at the next log-on. **Until then the switch stays
  `enabled` in the repository** — if the machine is to be off at the deadline, run `stop` first.
- **The repository is armed for 24 hours**: `external_acquisition` is `enabled` in HEAD and on `origin/main` from `c1bba1b` until the
  finalizer's disarming commit. Commits of documents are possible meanwhile; a change under `src`, `scripts` or `config` blocks the
  intake at the next start of its controller, and a change of a pinned file at its next request.
- **If someone pushes between now and the end**, the disarming commit is made locally and its push may be refused; the tool does not
  force. The file on disk is `disabled` either way; `tick.log` and the final report say what happened.
- **A cycle takes about as long as its interval** (§5): "hourly" means once per cycle.
- **A killed controller** was not tested on a real run (§5).
- The pilot's six outlets were polled an hour before the start; what they listed then counts as known before the intake.

## 9. Result of the 24-hour intake (`in1-20261010-24h`)

Evaluated on 2026-10-11 from `docs/intake/reports/in1-20261010-24h/` (imported with `import-report`; the numbers are the finalizer's).

| | |
|---|---|
| outcome | `COMPLETED`; verification `PASS` (seven checks); finalized 09:12:44Z, 13 minutes after the deadline, by the scheduled task; disarmed in `48446d3` (`disabled` in the file, HEAD and `origin/main`); the task removed itself |
| cycles, runs, restarts, outlet errors | 24, 24, 0, 0 |
| requests | 7 173 of 12 000 (3 822 item, 3 351 other); the most for one outlet 120 of 120; none at or after the deadline |
| answers | 6 490 with a body, all `RAW_PRESERVED`; 6 530 bodies read back from the preservation root and their digests compared |
| item pages | 3 691 requested, 3 681 answered 2xx, 3 610 technically usable under the experimental extractor |
| new by the intake's own measure | **2 572** 2xx pages first listed during the intake and dated inside its window; 48 first listed in a later poll without a date; the rest is stock or older |
| coverage | 85 of 87 outlets with at least one 2xx item page, in all 20 countries |
| recovery diagnosis after the run | `CLEAN`, identity `CORRECT` |
| failures | 10 timeouts, 16 `body_limit_exceeded`, 1 redirect limit, 6 × 404, 1 × 403, 1 × 504 — each on record, none retried to use a budget |

What was seen, as findings and not as judgements:

- **`ve_efecto_cocuyo`:** its feed answered 15 times; the sixteenth request was a challenge. The URL `https://efectococuyo.com/rss` is held
  (`bot_challenge`) from then on and was not asked again; 17 articles were fetched before. The held URL is in the state and the report.
- **`pe_elperuano`:** robots address unreachable at every poll (CPD-0027 §3: `unreachable`): no channel document and no item was requested.
  `hn_radio_progreso`: its feed lists the same ten articles at every one of 24 polls, all fetched in the recovery wave: no new page.
- **Extraction flags, the known cases first:** `pa_diaadia` (30 pages, all `empty_extraction`), `ve_eluniversal` (13, all empty),
  `hn_el_heraldo` (18 of 24 empty), `pa_metro_libre` (66 pages, median 32 characters, all `duplicate_body_of_other_document`),
  `mx_el_universal` (34, all `very_short_text`, median 174), `hn_criterio` (11, median 349). These measure the experimental extractor and
  the pages' markup; no page was removed or relabelled. Totals: 71 empty, 223 very short, 131 duplicate-body, 21 author-page URLs, 43
  front-page URLs, 11 gallery/video, 2 sponsored.
- **Stock outlets:** `cu_juventud_rebelde`, `pa_el_siglo`, `py_ultima_hora`, `hn_la_prensa`, `ar_pagina12`, `cl_biobiochile` and others got
  only their one stock page per cycle (24 each) and no new page: their channels (sitemaps) state no date or only old ones. That is the
  measurement, not necessarily the outlet.
- **Pace:** 24 cycles in 24 hours: a cycle took about an hour, as predicted in §8.

Not claimed: that these 3 681 pages are what the 87 outlets published in that day, that the 2 572 are articles (the flags and the
review package say where to look), or that any outlet is operationally stable. The review package
(`docs/intake/reports/in1-20261010-24h/review_package.json`) is prepared and every human field is empty.

## 10. Debts named after the intake (the operator, 2026-10-11)

Three things the 24 hours showed are to be worked on and are recorded here as open debts. None is started, none changes a rule or a
file; each needs its own run and, where it makes requests, its own authorisation.

**D1 — The extractors must get better, Mexico first and everywhere.**
The baseline extractor is experimental and its numbers are its own. Mexico is the clearest case and an important country: its only
outlet in the intake, `mx_el_universal`, answered 34 of 34 pages with 200 and yielded 902 words in all (median 174 characters; all
`very_short_text`), i.e. nearly nothing of the article text was recognised. Beside it: `pa_diaadia` (30 pages, all `empty_extraction`),
`ve_eluniversal` (13, all empty), `hn_el_heraldo` (18 of 24 empty), `pa_metro_libre` (66 pages, median 32 characters, all
duplicate-body), `hn_criterio` (median 349). Overall 71 pages are empty, 223 very short, 131 duplicate-body.
- To do: look at the preserved pages of these outlets (no new request: the bytes are on the preservation root) and find out whether the
  text is in another place of the markup, in an embedded JSON, or behind a script; compare the extractor candidates of CPD-0018 on them;
  decide per outlet whether a rule or a better general extractor is the answer. The word counts of the intake are the baseline against
  which any improvement is measured (`measurement.json`; per outlet in the labels).
- Replay re-derives the extraction from preserved bytes without a network, so an improved extractor re-reads the 24 hours at no cost.

**D2 — More newspapers must be discovered, Mexico first.**
The intake covered 85 outlets with pages in 20 countries, but unevenly: Mexico has one outlet in the intake (six of the registry's
seven hypotheses are not usable: three held behind a challenge, one with error answers on every channel, two deferred; §11), Honduras, Cuba and Nicaragua few pages, and 17 outlets
delivered only stock because their channels state no date. 31 hypotheses of the registry are not registered at all, 22 are only
registered, and 17 outlets have nothing usable because of an access control (CPD-0027).
- To do: a new discovery round per country, starting with the countries that have the fewest outlets or the least text per day (Mexico, the
  small Central American countries, Cuba); for outlets whose channels carry no dates, find a channel that does (a feed or a news sitemap);
  register what is found by the ordinary route (proposal, review, qualification wave) and not around it.
- Outlets with an observed access control stay held; nothing in this debt asks for a request to one.

**D3 — A criterion for the age of an article in regular intakes is to be discussed before there is one.**
The 24-hour intake asked first for what its channel dated into the window and for at most one older page per outlet and cycle; 2 572 of
3 681 pages (70 %) were dated into the window, 577 were found in the intake but dated older, 466 were known before, 48 are new without a
date, 107 cannot be placed. The age is the channel's statement, not the page's: a wrong date in a feed passes unnoticed.
- To discuss: whether a regular intake should fetch by publication age at all (only articles from the last n days, with or without a small
  allowance for older ones), how an undated candidate is treated, whether the age is read from the page when the channel has none, and
  whether old material is the business of a separate, bounded backfill with its own authorisation. The brief names historical backfills as
  a non-goal of this intake; this debt is about what the regular intake should do.
- Until it is decided, the selection of CPD-0029 §5 stands as it is: new and dated first, new and undated next, a small share of the rest.

## 11. Offline findings on D1 to D3 (2026-10-11)

Made on the preserved bytes of the 24 hours and on tracked files; **no request was made, nothing in `src`, `config` or the tests changed, no
extractor was adopted.** The scripts were throw-away (they name local paths, which the repository does not hold); what evidences the
comparison is tracked: `docs/intake/analysis/extraction_density_experiment_2026-10-11.txt`. An observation about what a page contains is
not a measure of an extractor's quality — that needs the gold sample of the validation gates.

### D1 — why the baseline extractor loses text, and what could be done

1. **Stored bodies are compressed as the server sent them** (CPD-0006 §1). Anything that reads them must decode first; a reader that
   did not saw "no text" on every page (this investigation made that mistake once and caught it).
2. **The baseline's rule** (`extraction._Parser.blocks`): the container is the *first of `article`, `main`, `body` that exists anywhere on the
   page*; a block counts as body text only inside it and not below `nav`, `aside`, `footer`, `header`, `form`, `figure`.
3. **Two failures of that rule explain the known cases:**
   - *A decoy `<article>`.* The page has a small `<article>` (a teaser tile, a related story) and the real text lies in `div`/`section`
     elsewhere: the container is the decoy and the text is outside it. `mx_el_universal` (a ~1 MB Arc page: 954 words in `<p>`, 49 in its `<article>`),
     `pa_metro_libre`, `hn_el_heraldo`, `hn_criterio`, `hn_contracorriente`, `cu_14ymedio`, `ni_confidencial`, `co_semana`, `ar_la_nacion`.
   - *Text under a `header`.* `pa_diaadia` puts the article's paragraphs in `<header>` elements inside its `<article>` (428 words in `<p>`,
     none counted).
4. **A paragraph-density rule recovers them — and loses elsewhere.** Tried as a throw-away (nearest container holding most paragraph
   characters, outside navigation and boilerplate lines), 4 pages per outlet, all 87 outlets, compared with the baseline's own count:

   | | words, baseline | words, density rule |
   |---|---|---|
   | `mx_el_universal` (4 of 34 pages) | 118 | 2 044 |
   | `pa_diaadia` | 0 | 1 188 |
   | `pa_metro_libre` | 20 | 666 |
   | `hn_criterio` / `hn_contracorriente` | 218 / 254 | 8 312 / 8 449 |
   | `ni_confidencial`, `cu_14ymedio`, `co_semana` | 489, 459, 745 | 3 566, 2 248, 2 232 |
   | all 87 outlets, 4 pages each | 212 680 | 186 049 |

   It is **better on 13 outlets and worse on about 34** (`co_elpais` 2 926 → 305, `pa_laestrelladepanama`, `pa_el_siglo`, `ar_clarin`, `gt_emisoras_unidas`
   and others): where the text is not in `<p>` elements (line breaks in a `div`), or is split over several containers, the density rule
   finds a fragment while the baseline's container is right. **Taking the larger of the two per outlet would give about 15 % more words
   than the baseline on the sample (243 569 against 212 680)** — the two rules fail on different pages, which says the answer is a choice
   per page (or per outlet rule), not one new general heuristic.
5. **What a density rule also takes:** a tail of related-story titles, a "join our WhatsApp channel" line, a signature stub ("dcs"), bylines
   and credit lines. Counting words on its output without a boilerplate rule overstates. `hn_criterio`'s 873 words on one page are real article text.
6. **Some "empty" pages are not articles at all.** `ve_eluniversal` (13 of 13 pages): section pages whose markup is an 8.7 KB shell that submits
   a form with JavaScript; its sitemap lists 375 one-segment section URLs and 75 others. `hn_el_heraldo`: login and service pages
   (`/iniciar-sesion` and the like). By URL shape alone, about 160 of the 3 681 pages are not articles (113 account/service-type, 50
   one-word section paths; an upper bound, the pattern is crude), 34 of them with an empty extraction. **For these the defect is not the
   extractor but the candidate qualification:** an outlet-specific allow or deny rule (as `hn_criterio` and `pr_noticel` have) or a generic
   non-article rule would keep them out of the 120-page budget.
7. **Dates.** Of 28 sampled pages without a publication date, 15 carry a visible Spanish date (`pa_diaadia`, `pa_el_siglo`,
   `pa_laestrelladepanama`, `cu_juventud_rebelde`), 6 a `<time datetime>`, 3 JSON-LD `datePublished`; 10 have none (login and section pages). The
   baseline reads the metadata fields it knows and misses the others: an easy gain, and it would move pages from "undated" to "dated".
8. **Not found:** no page of the problem outlets hid its text behind a script or a paywall; `mx_el_universal` shows 241 mentions of
   subscription wording in its markup, which this investigation did not resolve into a meter or a mere banner (open).

*Suggested order for the work itself (D1, for a later run with a decision):* (a) fix candidate qualification for the non-article URL shapes
and `ve_eluniversal`/`hn_el_heraldo`; (b) a fallback inside a candidate extractor: when the container yields little text, try the
densest paragraph container, with a boilerplate list; (c) read the further date fields; (d) measure each change on a frozen gold sample, per
outlet, with the 24-hour word counts as the baseline; replay re-reads the preserved bytes at no request.

### D2 — what the registry says about Mexico and the other countries

- **Mexico: seven hypotheses, one usable.** `mx_el_universal` verified; `mx_milenio`, `mx_la_jornada`, `mx_el_siglo_de_torreon` held behind a challenge
  (CPD-0027); `mx_animal_politico` registered, every channel answered with an error; `mx_el_sol_de_mexico` (no channel found) and
  `mx_expansion` (no origin) deferred. So Mexico's text in the corpus rests on one outlet whose extraction is itself poor (D1): the discovery
  work has two parts there — **new outlets** (the registry has none beyond these seven) and **channels** for the two deferred and the
  error-only one. The held three are not part of it.
- **By country, hypotheses not yet usable** (not registered, registered only or technically qualified): Bolivia 6 of 8, Costa Rica 5 of 6, Cuba
  5 of 9, Puerto Rico 3 of 6, El Salvador 4 of 6, Uruguay 5 of 7, Guatemala 4 of 9, Mexico 6 of 7. Argentina, Spain, Chile, Colombia,
  Ecuador, Panama, Peru, Venezuela, Honduras and the Dominican Republic have 4 to 8 usable outlets each.
- The intake's 17 outlets that gave only stock (their channels state no date) are a discovery question as well: a second channel with
  dates (feed or news sitemap) per outlet.

### D3 — the age of what was fetched, as a basis for the criterion

- **New in the window** (2 582 pages with a date): fetched a **median 0.7 hours** after the channel's publication time, 10 % within 0.2 h,
  90 % within 6.0 h, the latest at 22.7 h. Outlets with the longest median delay: `co_diario_del_huila` 7.5 h, `do_diario_libre` 5.4 h,
  `pr_el_nuevo_dia` 3.6 h, `ve_analitica` 3.5 h: the hourly cycle plus the three-page-per-cycle cap, not the outlet.
- **Dated older than the window** (1 020 pages): 492 under one day old, 383 from 1 to 7 days, 26 from 7 to 30, 38 from 30 days to a year,
  **81 older than a year**. The first two groups (875) are the day before the intake began and what a feed still lists; the 145 older ones are the
  stock share, taken at most one per outlet and cycle.
- 89 pages had no date in the channel at all (2.4 %).
- **Reading for the discussion:** of the 3 681 pages, 3 359 were dated less than 48 hours before the request, 88 two to seven days, 145 more than seven days, and
  89 not at all; so a rule "published within the last 2 days" would have kept 3 359 and left out 322; a criterion by age is cheap to state and to enforce at selection. The open questions of D3
  stand: the channel's date is the only basis, undated pages need a rule, and whether old material is wanted at all is for the backfill
  discussion, not for this intake's selection.

