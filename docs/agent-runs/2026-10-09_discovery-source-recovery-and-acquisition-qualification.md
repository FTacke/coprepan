# Integrated discovery, source recovery, adapter engineering and acquisition qualification

```text
run_started_at:      2026-10-09T09:10+02:00 (approximate; first clock reading of the run: a scratch file written 2026-10-09T09:12:43+02:00)
run_ended_at:        see the closing commit of the run (last clock reading while writing: 2026-10-09T09:46:05+02:00)
timezone:            Europe/Berlin
```

**Status: PARTIAL.**

- **Done, with evidence:** the legacy import audited against a copy of the legacy database (complete, no discrepancy); passive
  prediscovery for all 82 outlets; a versioned source-discovery inventory; the findings F1–F7 of the first canary repaired with
  regression tests and replayed on the preserved answers of 2026-10-08; a second canary prepared; an extended canary of twelve
  outlets prepared as a registration proposal; the permission refusals of 2026-10-08 diagnosed.
- **Not done, by gate:** no canary ran. The second canary waits for the operator's arming; the extended canary waits for the
  operator's review of the proposal (O-11) and then the arming. `external_acquisition` is `disabled`.
- **Therefore not shown:** that more outlets deliver articles than before. The number of outlets with verified acquisition is
  **1**, as it was after the first canary.

**What the status does not claim.** No repair has met a real server: each is shown on synthetic fixtures, a loopback server and
the stored answers of one evening (reproducibility and robustness). Nothing here is replicability or generalisability. No
address found by research was requested: every researched channel is a hypothesis. No quantitative progress over the legacy
system is claimed. No extractor was evaluated. Nothing was registered, armed or activated.

**Kind of run:** diagnosis (legacy audit, permission diagnosis, replay), research (prediscovery), implementation (repairs, coverage
report, inventory, proposal tooling), one decision (CPD-0019). Not a validation and not an activation.

`EXTERNAL_API_USAGE`: web search and third-party pages for prediscovery (three research agents; search engine and reference sites
such as IPTC Metawatch, Feedspot, Feeder, Wikipedia). **No request to any publisher's domain was made** — not by the crawler, not
by a research tool. `git fetch` against the project's own remote.

## 1. Starting state, decisions, gates

| Item | Value (measured) |
|---|---|
| `HEAD` = `origin/main` at start | `e84827457c673980e88c571f22e22b7407c9be9a`, tree clean; no run or decision after the report of 2026-10-08 |
| registry | 82 outlets (5 registered, 77 proposed), 352 channels |
| policy | `canary/2026-10-08.2`, `external_acquisition: disabled` |
| workspace | the first canary's: 5 packs, 232 candidates (all `do_diario_libre`), recovery `CLEAN` |
| tests before any change | 1314 passed, 8 skipped |
| reference repositories | legacy `3e6bdd33…` (clean), CO.RA.PAN `75dad4f7…` (two untracked plan files that were there before this run) |

Gates in force and untouched: O-1 (switch off), O-11 (77 proposed), O-12 (a baseline per armed commit), the arming protocol of
CPD-0016 §4, the Phase-2 canary gate (`OPEN`).

## 2. Legacy import audit (brief §A)

`scripts/legacy_discovery_audit.py` on a copy of `data/db/coprepan.sqlite` (with its WAL sibling: without it 142 article rows
and 25 feed rows differ); the legacy tree was read, never written; digest of the database before and after equal
(`7fe49907…8ed5b7`). Output: `config/source_discovery/legacy_discovery_audit_2026-10-09.json` (byte-identical on repetition).

**Import: no discrepancy.** All columns of 82 source rows and 352 feed rows equal the registry's `legacy_observed`; every source
maps to one outlet, every feed to one channel under the right outlet; no loss, fold, duplicate or changed address. 46 notes, none
a defect of the import: 29 channel ids re-slugged by the registration of 2026-10-08; 6 outlet slugs are ASCII folds of non-ASCII
legacy codes; 7 feeds of legacy type `unknown`; **three sitemap indexes of `elnuevodia.com` are stored under both
`pr_el_nuevo_dia` and `pr_primera_hora`**, so `pr_primera_hora` has no channel of its own; legacy source id 53 is absent. Nothing
was changed in the registry: no deterministic repair was needed, and the Puerto Rico case is a review decision.

What the legacy database holds: `sources` 82, `feeds` 352, `discovery_runs` 771, `crawl_runs` 32, `articles` 64,932 (fetched
2025-12-18 to 2026-06-15). `articles` carries no feed id and `feeds` keeps one overwritten success stamp: **repetition is never
provable per channel**.

| Legacy class (rule in the file) | Channels | | Outlets |
|---|---|---|---|
| `PRODUCTIVE_REPEATED` (by exclusion — an inference) | 6 | `LEGACY_PRODUCTIVE_REPEATED` (accepted rows in runs on ≥ 2 days) | 33 |
| `PRODUCTIVE_ONCE_OR_SPORADIC` (a success stamp exists) | 110 | `LEGACY_PRODUCTIVE_SPORADIC` | 9 |
| `NEVER_SUCCESSFUL` | 148 | `LEGACY_NEVER_PRODUCTIVE` | 17 |
| `NO_EVIDENCE` (82 are sitemap indexes never expanded) | 88 | `LEGACY_NO_CHANNEL` | 23 |

- "Accepted" is the legacy status `ok` (at least 100 extracted words): 35,810 rows from **42 outlets in 18 countries**. The ten
  largest outlets hold 20,426 of them (57 %). Other statuses: `too_short` 13,989, `discarded_gallery` 8,663,
  `discarded_homepage` 4,255, `discarded_binary` 2,128, `fetch_error` 64, `discarded_paywall_teaser` 23.
- Of the 33 "repeated" outlets, 12 had their last accepted fetch in June 2026 and 21 on or before 2026-02-21. **Repeated is not
  lasting**, and a single success stamp proves one success.
- **"51" and "39" re-measured, and they count different things.** 51 = sources without a feed row flagged `is_active` at the
  snapshot (of them 23 without any feed, 14 never productive, 6 sporadic, 8 repeated). 39 = `<COUNTRY>/<slug>` directories under
  `json_raw` with at least one file (38 outlets and the unmapped `MEX/universal`). Eleven outlets have no active feed and do have
  files; four have an active feed and none.
- **Why outlets had no channel.** 14 of the 23: every legacy discovery run stopped on the legacy "TDM opt-out" heuristic (a
  `robots.txt` that names an AI crawler or `noai`); 7: discovery completed and found nothing; 1: timeouts; 1: mixed. Sitemap
  indexes were never expanded (all 82 inactive). Read errors were swallowed (no feed has an error message). Several outlets with
  thousands of fetched rows have almost none accepted (`ar_la_nacion` 1 of 1,806; `cr_diario_extra` 0 of 1,346, all
  `discarded_homepage`; `hn_la_prensa` 6 of 2,316): **extractor verdicts, not channel failures** — and the legacy extractor is
  the one whose word-splitting and paragraph filters are not to be taken over.
- No blocklist or per-domain exception exists in the legacy code; the special handling is generic (references by file and line in
  the audit agent's notes; the heuristics are named in corpus supply §19).

## 3. Prediscovery over the 82 outlets (brief §B)

Method: passive research on 2026-10-09 — search results and third-party pages. The strongest source is IPTC Metawatch, a
third-party crawler that publishes, per site, the feed it reads and the dates of articles it sampled (30 Sep – 1 Oct 2026).
Files: `config/source_discovery/prediscovery_2026-10-09_group{1,2,3}.json`, kept as delivered. Evidence levels per channel:
`search_evidence`, `legacy_evidence`, `cms_pattern_inference`, `unknown`.

| | Count (measured from the files) |
|---|---|
| researched candidate channels | 301 — 155 `legacy_evidence`, 79 `search_evidence`, 51 `cms_pattern_inference`, 16 `unknown` |
| operating status | 72 operating, 6 uncertain, 2 moved, 2 closed |
| closed | `bo_pagina_siete` (last edition 2023-06-29), `gt_elperiodico` (2023-05-15) |
| moved | `bo_la_razon` → `larazon.bo`; `ni_la_prensa` → `laprensani.com` (exile) |
| proposed new outlets | 60 (three per country), proposals only |

Inventory (`config/source_discovery/source_discovery_inventory_2026-10-09.1.json`, page
`docs/corpus_supply/SOURCE_DISCOVERY_INVENTORY.md`), per outlet: origins, legacy channels with class and provenance, researched
channels with type, address, evidence and date, structure notes, obstacles, route class, flags, priority with its factors.

| Flag (rule: CPD-0019 §8) | Outlets |
|---|---|
| `IMPORTED` | 82 |
| `DISCOVERED` | 79 |
| `QUALIFIED` | 2 (`do_diario_libre`, `ve_efecto_cocuyo`) |
| `REGISTERED` | 5 |
| `ACQUISITION_VERIFIED` | 1 (`do_diario_libre`) |
| `OPERATIONALLY_STABLE` | 0 |

Route classes: 67 `STANDARD_CHANNEL_CANDIDATE`, 3 `INDEX_EXPANSION_CANDIDATE`, 6 `LISTING_ONLY`, 1 `ACCESS_CONTROL_HOLD`, 2
`CLOSED`, 3 `NO_ROUTE_KNOWN` (`bo_eldiario`, `sv_la_prensa_grafica`, `uy_larepublica`). The class says a route is *known*, not
that it works. Limits: search rarely shows exact feed addresses; owner, type and city entries marked "background knowledge" in
the files are unverified and were not copied into the registry.

## 4. New and updated discovery channels (brief §B, §I)

**The registry was not changed.** In the policy, one channel was disabled (`hn_proceso_digital:ch:sitemap_news`, §5 F6). Eight
channels from research are *proposed* for the extended canary (§8) and are not in the registry: `ec_el_universo` (Arc RSS),
`ec_primicias` (`/feed/`), `es_el_mundo` (RSS on a CDN host), `mx_la_jornada` (RSS and Atom), `ni_confidencial` (feed on the apex
host), `pe_la_republica` (section feed), `bo_lostiempos` (front page as a listing).

## 5. The findings F1–F7 (brief §C)

| | Repair | Regression test | On the preserved answers of 2026-10-08 (`canary_replay_2026-10-09.json`) |
|---|---|---|---|
| F1 | robots answer decoded for parsing; preserved bytes and digest unchanged; undecodable → `parse_error` → hold | a gzip-coded robots file served by a loopback server; three undecodable variants | both gzip files parse (`bo_el_deber`: 7 rules, 5 sitemaps; `py_la_nacion`: 5 rules, 1 sitemap); no channel of the canary is disallowed |
| F2 | Sucuri marker; small bodies inspected whatever the status; holds re-derived from stored answers | the challenge as 307 without `Location` (fixture after the stored answer); no further request, no cookie, one user agent; driver stops before the second channel; a stored answer the old classifier missed holds its origin | the 307 of `https://proceso.hn/rss` is `bot_challenge`; `https://proceso.hn` is held for a next canary (recorded class alone: no hold) |
| F3 | a run qualifies, schedules and requests its own outlet's candidates only | two outlets, two servers, one workspace: no foreign plan, no `off_origin`, budgets per outlet exact, no request twice | 64 candidates of `do_diario_libre` carry a `DENIED` row; due again under the new policy version (measured) |
| F4 | hop-wise accounting; 3 of 8 non-item requests reserved for expansion; read order `expansion-order/1`; `max_documents` bounds documents asked for; the budget is the baseline's | the situation of the canary rebuilt (robots, redirecting feed, redirecting index of 31 children): the three newest post sitemaps read within 8 requests, no taxonomy sitemap, no request storm | the index of `ve_efecto_cocuyo` parses with 92 children; read order starts `post-sitemap.xml`, `post-sitemap85.xml`, `post-sitemap84.xml` |
| F5 | the DTD guard ignores CDATA and comments, left to right | the feed shape of the canary; seven hidden-declaration variants still refused | the refused feed parses: 10 items |
| F6 | channel disabled in the policy; **no replacement** | selection for the outlet skips it | — the 404 is the evidence; the origin challenges this client, so no other path is tried |
| F7 | measured (`discovery_coverage`), limit unchanged | 534 entries, budget 200: what is turned away, and that later passes continue | 534 listed, 231 kept, **303 turned away; 44 of them newer than the oldest kept** (the sitemap is not strictly newest-first) |

F7 in words: the candidate budget does lose coverage on a long news sitemap — mostly its old end, partly not. For a canary of 16
items per outlet it is not the binding constraint. The limit was not raised; ordering dated entries before the budget is applied
is left as an open decision (CPD-0019).

The receipt of the first canary still verifies under the changed driver: `verify` `PASS` (8 of 8), with the workspace
byte-identical before and after (142 files, tree digest `27a6f00c…c1a30`).

## 6. Parser, configuration and adapter work (brief §D)

- **Generic:** content-coded robots files; CDATA-aware declaration guard; index expansion with a stated read order and a real
  budget; the coverage report and the frontier of an index (`src/coprepan/discovery_coverage.py`).
- **Configurable:** the driver now applies `config/candidate_rules.json` (it passed no rules before); a listing channel
  (`archive`, `section_page`) is selected only for an outlet with an allow rule; channel order and disabled channels steer which
  two channels a canary reads. A wider canary of 6–15 outlets has a budget (`canary_budget`).
- **Source-specific adapters: none built.** Nothing observed needs one: the four channel documents of the first canary and the
  structures research describes (WordPress/Yoast, Arc XP outbound feeds, "megasitemap" indexes, Atom, a feed on a foreign host)
  are covered by the generic parsers plus configuration — untested against the real servers. The interface an adapter would have
  is stated in acquisition §13.
- **Not built:** pagination of HTML archives beyond `rel=next`; date extraction from listings; incremental continuation across
  runs (the frontier is derivable, nothing reads it).

## 7. Tests

| Check | Result |
|---|---|
| full suite before any change | 1314 passed, 8 skipped |
| `tests/test_canary_findings.py` (new) | 32 passed |
| `tests/test_source_discovery.py` (new) | 10 passed |
| full suite on the final tree, switch off | see the closing note of this section |
| replay of the first canary's answers | written; workspace unchanged |
| `canary_driver verify` of the stored receipt of 2026-10-08 | `PASS` |
| `canary preflight` for the five outlets | `NOT_READY`: only `acquisition_policy_decided` (switch off), `tests_green_on_this_commit`, `no_configuration_drift` (no baseline) fail |

Tests changed, none weakened: `test_discovery.py` (the parser version is read from the module); `test_readiness.py` (a third
fixture manifest is expected); `test_registry.py` (two assertions made exact — the five-country rule is the rule of the 2026-10-08
record; the import's channel count counts channels that carry a legacy row). An intermediate full run had two expected failures
from files not yet wired (suite membership, fixture list); both are fixed.

**Closing note:** the full suite on the final tree, switch off: **1357 passed, 8 skipped** (7 need the candidate tools of the
extra `phase3`, 1 is the symbolic-link test this account cannot run) — 43 tests more than at the start; `git status` afterwards
showed no tracked file modified by the tests.

## 8. Canaries (brief §E, §F)

**None was run.** No end-to-end acquisition beyond the first canary exists, so the questions of brief §E about real pages
(dates, teasers, CMS variety, wrong deletions) have no new evidence; the thirteen pages of 2026-10-08 remain the only real
material, and `PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY` stands. No review material was extended; no gold, no simulated label.

| | State | Stops at |
|---|---|---|
| second canary: `bo_el_deber`, `do_diario_libre`, `hn_proceso_digital`, `py_la_nacion`, `ve_efecto_cocuyo` | prepared; driver pin and preflight run; expected behaviour in runbook §8.1 (`hn_proceso_digital` is held and asked nothing) | the operator's arming |
| extended canary: `bo_lostiempos`, `cl_el_mercurio`, `ec_el_universo`, `ec_primicias`, `es_el_mundo`, `gt_lahora`, `mx_la_jornada`, `ni_confidencial`, `pa_laestrelladepanama`, `pe_diariocorreo`, `pe_la_republica`, `sv_el_diario_de_hoy` | a registration **proposal** with evidence and the reviewer's judgements per outlet; applies cleanly to a copy and gives a pin of 12 outlets × 8 items (tested) | O-11 review, then the arming |

The twelve by legacy class: 4 `NO_CHANNEL`, 4 `NEVER_PRODUCTIVE`, 2 `SPORADIC`, 2 `REPEATED` (controls); ten countries, Ecuador and
Nicaragua among them; WordPress, Arc XP, proprietary RSS, Atom, a feed on a foreign host, a section feed, three kinds of sitemap
index, one HTML listing. Not chosen for ease: eight of the twelve never gave the legacy system a usable article.

## 9. Outlet and country coverage with verified acquisition

1 outlet (`do_diario_libre`), 1 country (`do`), 13 item pages, one run, 2026-10-08. Unchanged by this run.

## 10. Quantitative comparison with the legacy system (brief §G)

Scopes differ and are stated: legacy = 32 crawl runs over six months, judged by the legacy extractor; v3 = one bounded canary of
27 requests. **The two columns are not comparable as performance**; the table says what exists.

| Measure | Legacy (2025-12-18 – 2026-06-15; measured from the database copy) | COPREPAN 3.0 (as of 2026-10-09; measured) |
|---|---|---|
| outlets available | 82 listed | 82 imported; 5 registered |
| channels that yielded article candidates | 116 with a success stamp (6 "repeated" by inference) of 352; 82 indexes never read | 3 channel documents with item entries (2 outlets), from preserved bytes |
| outlets with real articles | 42 with ≥ 1 accepted row; 33 "repeated" | **1** `ACQUISITION_VERIFIED` |
| countries with material | 18 | 1 |
| concentration | 10 outlets hold 57 % of accepted rows | not meaningful (one outlet) |
| discovery success | 547 of 771 discovery runs completed; 184 stopped on the TDM heuristic | of 6 channel documents answered in the canary, 4 were 200 and 3 of those parsed (one refused: F5); read again after the repair, 4 of 4 parse. 3 more were never asked (F1) |
| fetch success | 64 `fetch_error` of 64,932 rows (errors were partly swallowed: a lower bound) | 13 of 13 item requests answered 200 |
| preservation | none: no raw response was kept | 24 of 24 answers preserved, fixity verified, replayed |
| extraction quality | 35,810 of 64,932 rows accepted by an extractor with known defects | `NOT_YET_MEASURABLE` (no gold, no adopted extractor) |
| repeated success | 33 outlets by the audit's rule; 12 still in June 2026 | `NOT_YET_MEASURABLE` (one run) |
| failure causes | TDM heuristic (14 outlets without channel), indexes not expanded, extractor rejections, timeouts | F1–F5 (own defects, repaired offline), one bot challenge (external), one 404 (external) |

What can be said: the legacy system delivered accepted articles from 42 outlets at some point and from 12 until its end; v3 has
verified acquisition from 1. **A broader real coverage than the legacy system is not shown and not claimed.** What changed is
the cause structure: for three of the four outlets without items in the first canary the reason was our own code, and it is
repaired; the two largest
legacy causes (the TDM heuristic, unexpanded indexes) do not exist in v3 by design. Whether that becomes coverage is what the
two canaries measure.

Qualification yardstick (CPD-0019 §8): an outlet counts as productive in the short term as `ACQUISITION_VERIFIED` (≥ 5 item pages
2xx, preserved, verified, replayed in one bounded run), in the long term only as `OPERATIONALLY_STABLE` (three such runs on three
days within at least fourteen days, no hold in between). Country coverage is not balanced representation, and neither flag says
anything about text quality.

## 11. Remaining source problems and technical limits

- `hn_proceso_digital`: held (bot challenge). A third-party crawler reads `/feed/` there; that is not a reason to try it.
- Paywalls and registration walls (reported for `ar_clarin`, `ar_la_nacion`, `co_el_tiempo`, `es_*`, `hn_el_heraldo`,
  `hn_la_prensa`, `pr_el_nuevo_dia`, `uy_el_pais`, `uy_ladiaria` and others): never worked around; what a metered wall serves
  this crawler is unknown.
- `mx_el_universal`: a third party reports a robots restriction for its crawler; ours has not read that file.
- Origins: `bo_la_razon`, `ni_la_prensa`, `uy_larepublica`, `ve_eluniversal` need an origin decision before anything else.
- Listing-only outlets need a reviewed allow rule each; none exists in the tracked rules.
- 26 outlets carried the legacy TDM mark at some point. Under CPD-0017 a general reservation is recorded and does not decide a
  research request; whether the operator wants those publishers approached is his decision, not a technical one.
- The candidate budget turns away part of long listings (§5 F7).
- Extraction: nothing new; the baseline is `EXPERIMENTAL`.

## 12. Operator gates

| Gate | State | What only the operator can do |
|---|---|---|
| arming of the second canary (O-1 switch, O-12 baseline) | ready | runbook §1–§6 with §8.1 |
| O-11 for the extended canary | proposal ready | review; `scripts/apply_registration_proposal.py … --write`; commit |
| lifting the hold on `proceso.hn` | no mechanism | a decision; possibly contact with the publisher |
| Phase-3 pilot review | unchanged, ready since 2026-10-08 | review the thirteen cases |

## 13. Permissions (brief §L)

**Cause of the refusals of 2026-10-08 (from the recorded messages, not conjecture).** Every one concerned the arming chain and
nothing else: the edit of `external_acquisition` to `enabled` (reason given: "production deploy"), running commands on the armed
tree, and the driver's `run` command (reason given: `[Security Weaken]`). They came from the session's permission classifier.
They were **not** caused by file permissions, attributes, locks, workspace boundaries or a project rule:

| Checked on 2026-10-09 | Finding |
|---|---|
| project configuration | this repository has no `.claude/settings.json` and no `.claude/settings.local.json`: no deny rule, no hook |
| user configuration | allow rules for another project only; nothing that concerns this repository; no deny rule |
| CO.RA.PAN, for comparison | one hook that blocks heredocs; no permission rule. Its runs never switch on an external effect — that, not a configuration, is the difference |
| `config/acquisition_policy.json` | ordinary file (archive attribute only), writable, LF; no git hook, no `core.hooksPath` |
| the same file, edited in this run | twice, without objection: the policy version and one disabled channel — edits that do **not** arm |
| read access | legacy tree, runtime workspace, preservation root on `D:` (via `verify`): all worked |
| write access | scratchpad, repository: worked; nothing was written to a storage root |

So the refusals coincide with a boundary the project has on purpose (CPD-0016 §4: the operator arms). **No correction was made
and none is needed for the technical workflow**: everything in this run — research, legacy reading, code, tests, replay,
documentation — ran under `AUTO` without a single refusal. The switch was not touched, and no other way to set it was tried.

Remaining limit, by design: arming and starting a canary. If the operator wants an agent to do that under an explicit brief, the
narrowest rule would be an allow rule for exactly the driver's `run` command and the one-line edit — his to add, in
`.claude/settings.json`, not something a run should give itself. Recommendation: leave it with a person; it is one command
sequence in the runbook.

One self-inflicted slip, for the record: two shell commands of this run contained an empty bash here-document or here-string
(no content, no effect), against AGENTS §5. CO.RA.PAN blocks these with a hook; adopting that hook here would make the rule
mechanical (a restriction, not a permission) — proposed, not done.

## 14. Files and git

Created: `src/coprepan/discovery_coverage.py`; `scripts/legacy_discovery_audit.py`, `replay_canary_findings.py`,
`build_source_discovery_inventory.py`, `apply_registration_proposal.py`; `tests/test_canary_findings.py`,
`tests/test_source_discovery.py`, `tests/fixtures/qualification/` (two fixtures, manifest); `config/source_discovery/` (audit,
three prediscovery files, replay, inventory); `config/registry_review/extended_canary_proposal_2026-10-09.json`;
`docs/corpus_supply/SOURCE_DISCOVERY_INVENTORY.md`; CPD-0019; this report.

Changed: `src/coprepan/robots.py`, `access_control.py`, `discovery.py`, `fetcher.py`, `http_acquisition.py`, `canary_driver.py`,
`canary_evidence.py`; `config/acquisition_policy.json` (version, one disabled channel; the switch stays `disabled`);
`tests/test_discovery.py`, `test_readiness.py`, `test_registry.py`, `tests/suites/foundation_contract.txt`,
`tests/fixtures/README.md`; `docs/STATUS.md`, `docs/canary/RUNBOOK.md`, `docs/acquisition/INDEX.md`,
`docs/corpus_supply/INDEX.md`, `docs/architecture/INDEX.md`, `docs/architecture/TERMINOLOGY_AND_NAMING.md`,
`docs/decisions/README.md`.

Nothing was moved or deleted. No historical report, frozen baseline, canary evidence file, review decision or raw datum was
changed. Two inventory and proposal files were regenerated *before* their first commit (a write-once file is write-once from its
commit on). Outside the repository: scratch files in the session scratchpad only; the runtime workspace and the preservation
root were read, not written (tree digest of the workspace equal before and after).

Reference repositories: not modified. `git status` and `git rev-parse` were run in the legacy and CO.RA.PAN checkouts to record
their state — read-only commands, though `git status` may refresh a checkout's index cache; no file of either tree was touched.
The legacy test suite was not run; the legacy database was opened only as a copy.

Commits: see `git log` from `e848274`; the closing commit carries this report.

Open, explicitly: no canary run; no registration; no adapter; no HTML pagination; no hold-lifting mechanism; ordering before the
candidate budget; extraction quality; everything in STATUS §6.

## 15. Recommended next activation, in steps

1. **Operator: arm and run the second canary** (runbook §8.1). Then one agent run evaluates it: per outlet items, the three
   repaired paths on real servers, `ACQUISITION_VERIFIED` per outlet, O-4 with sizes from more than one outlet.
2. Operator: review the proposal of the extended canary; apply all or part; arm and run it as a separate canary.
3. Only after both: the next set by country need (inventory priority), again as proposal and canary. Repeating a canary on
   different days is what makes an outlet `OPERATIONALLY_STABLE`; nothing else does.
4. Scheduled crawling stays behind O-1 and is not prepared by any of this.

## Operator report

- **Result.** The three defects of our own code and the missed bot challenge that cost the first canary four of five outlets
  are repaired and shown on that evening's stored answers: the two gzip robots files parse, the Sucuri answer is recognised and
  its origin held, the refused feed yields 10 items, the 92-child index is read to its newest sitemaps within the old limit of 8
  requests, and no outlet plans another's pages. The legacy import is verified complete, and for all 82 outlets it is now on
  file what the legacy records show and what routes exist today by research.
- **Status: `PARTIAL`** — engineering, audit, research and preparation complete; **no live acquisition**, so no new outlet is
  qualified. Offline evidence only.
- **Legacy comparison.** Historically 42 outlets (18 countries) delivered at least one accepted article and 33 did so
  repeatedly, 12 of them until June 2026. Verified in COPREPAN 3.0 today: **1 outlet, 1 country**. No progress in coverage is
  claimed.
- **Productive consequence.** Next in line: the four other registered outlets (three of them now unblocked, one held), then the
  twelve of the proposal — among them the only two countries the legacy system never read, Ecuador and Nicaragua.
- **Next step — one action:** arm and run the second canary (runbook §1–§6, §8.1). In parallel, if wanted: review
  `config/registry_review/extended_canary_proposal_2026-10-09.json`.
