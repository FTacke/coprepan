# Integrated source expansion, discovery recovery, adapter qualification — and no real acquisition yet

```text
run_started_at:      2026-10-09T11:59:54+02:00 (first clock reading of the run)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: PARTIAL.**

- **Done, with evidence:** the operator's research supplement consolidated with every earlier file into one qualification
  overview; F7 re-measured, **an earlier reading of it corrected**, and settled; discovery extended to paginated and dated HTML
  listings, with candidates that wait for a reviewed rule; an index read incrementally; outlets new to the registry given a
  procedure; a third wave of nine such outlets proposed; the operator's canary procedure reduced to one command.
- **Not done, by gate:** no canary ran — not the second, not a wave. Arming and the freeze are the operator's acts
  (CPD-0016 §4) and nobody had done them when this run started or ended. No outlet was registered.
- **Therefore:** the number of outlets with verified acquisition is **1** (`do_diario_libre`), in 1 country, as on 2026-10-08.
  **No additional newspaper and no additional country has been acquired.**

**What the status does not claim.** Everything new is shown on **synthetic** documents, on a loopback server and on one preserved
listing: reproducibility and robustness. Nothing is replicability or generalisability; no real listing page, paginated archive,
sitemap child or new outlet has been read. No statement about extraction quality. No statement that source variety has improved.

**Kind of run:** consolidation of research (diagnosis), implementation, one decision (CPD-0020), preparation of registrations.
Not a validation, not an activation.

`EXTERNAL_API_USAGE = NONE`. **No request to any publisher. No web research by this run**: the supplement is the operator's
delivery, used as delivered.

## 1. Starting state, commits, gates

| | Measured |
|---|---|
| `HEAD` = `origin/main` | `0c3b386f429b4c34e46972f61414668c94ed3d58`; untracked: the two supplement files the operator placed |
| switch | `external_acquisition: disabled`; no arming commit, no new baseline, no new receipt in the runtime workspace |
| second canary | **not run in the meantime** (checked: `git log`, `docs/canary/`, `<RUNTIME>/canary/`) |
| supplement | `config/source_discovery/coprepan_prediscovery_ergaenzung_2026-10-09.json` (18,900 B) and `docs/corpus_supply/coprepan_prediscovery_ergaenzung_2026-10-09.md` at the expected paths; committed unchanged |
| tests at start | 1358 passed, 8 skipped (previous report) |

Gates in force and untouched: O-1 (switch), O-11 (registration), O-12 (a baseline per arming), the operator's arming and freeze.

## 2. The 19 supplement entries

Status of the delivery, kept: `RESEARCH_ONLY / NOT_REGISTERED / NOT_LIVE_VALIDATED`. Its own limit — it could not be checked
against the three prediscovery files and the 60 proposals — is what this run did, in
`scripts/consolidate_source_discovery.py` (addresses compared without scheme, leading `www.` and trailing slash, query sorted; a
match ignoring the query is a *variant*; outlets matched by registry id, then host, then country and title).

| Classification (computed) | Entries | Which |
|---|---|---|
| `KNOWN_IDENTICAL` — a registry channel | 1 | `ec_el_comercio` (`/feed/`) |
| `KNOWN_ADDITIONAL_EVIDENCE` | 4 | `ec_el_universo` (the hub documents the Arc feed of the reviewed wave), `pr_el_nuevo_dia`, `co_el_tiempo`, `py_abc_color` (the registry's feed without its query: a variant) |
| `NEW_CHANNEL_FOR_EXISTING_OUTLET` | 1 | `uy_el_observador` (`/rss/pages/ultimo-momento.xml`) |
| `OUTLET_ALREADY_PROPOSED` — among the 60 | 10 | Artículo 66, Nicaragua Investiga, 14ymedio, CubaNet, Montevideo Portal, Opinión, NotiCel, Criterio.hn, El Faro, El Siglo de Torreón |
| `NEW_OUTLET_CANDIDATE` — in no earlier file | 3 | Diario de Cuba, El Tribuno, Expansión México |

Against the supplement's own count (13 new outlets, 5 routes, 1 identical): 10 of its 13 "new" outlets were already proposed in
the repository; 4 of its 5 "new routes" were known or variants. What the supplement adds that nothing had: three outlets, one
channel, and **publisher-side documentation** for addresses earlier research had only from directories — plus the listing routes
(archives, section pages) for outlets known by a feed only.

| Disposition (a judgement of this run, with its reason in the overview) | Entries |
|---|---|
| `WAVE_C` | 9: `ar_el_tribuno`, `bo_opinion`, `cu_14ymedio`, `cu_cubanet`, `hn_criterio`, `ni_articulo66`, `ni_nicaragua_investiga`, `pr_noticel`, `uy_montevideo_portal` |
| `LATER_WAVE` | 3: `cu_diario_de_cuba`, `pr_el_nuevo_dia`, `uy_el_observador` |
| `EVIDENCE_FOR_REVIEWED_WAVE` / `EVIDENCE_ONLY` | 1 / 2: `ec_el_universo` / `ec_el_comercio`, `py_abc_color` |
| `NEEDS_CURRENT_EVIDENCE` | 2: `mx_expansion` (a hub page, no feed address), `mx_el_siglo_de_torreon` (documentation of 2008; a directory names another address) |
| `DIFFERENT_CADENCE` | 1: `sv_el_faro` (monthly editions, a beta host) |
| `HOLD_LEGAL_REVIEW` | 1: `co_el_tiempo` — see §13 |

## 3. Deduplication against the 301 hypotheses and the 60 proposals

- Outlet candidates outside the registry after merging: **63** (60 + 3), no outlet twice, none on a host that is an origin of a
  registry outlet (tested).
- The reviewed first wave is unchanged; `ec_el_universo` gains evidence only.
- **Identity cases** — facts in the overview, nothing decided, nothing relabelled:

| Case | Fact (from the files) | Open |
|---|---|---|
| `pr_primera_hora` | all three channels are on `elnuevodia.com`, the same addresses as `pr_el_nuevo_dia`; origin `primerahora.com` | give it no foreign channel; two titles of one group stay two outlets |
| `cl_el_mercurio` | origin `emol.com`, the group's free portal | Emol or El Mercurio: the operator's |
| `ni_confidencial` | feed read on the apex host; newsroom in Costa Rica | apex as second origin; country stays the country reported on |
| `bo_la_razon`, `ni_la_prensa` | research finds them on other domains | an origin is added by review with a date, never rewritten |
| `bo_pagina_siete`, `gt_elperiodico` | closed in 2023 by research; 10 and 0 accepted legacy articles | no registry attribute for "closed" exists |
| same title in several countries | listed in the overview | the id's country prefix keeps them apart |

## 4. New and additionally qualified outlets

**Qualified: none.** `TECHNICALLY_QUALIFIED` stays at 2 outlets and `ACQUISITION_VERIFIED` at 1: both need this project's own
observation of a server, and there was none. Proposed, not registered:

| Wave | Outlets | Countries |
|---|---|---|
| wave C (new to the registry) | `ar_el_tribuno`, `bo_opinion`, `cu_14ymedio`, `cu_cubanet`, `hn_criterio`, `ni_articulo66`, `ni_nicaragua_investiga`, `pr_noticel`, `uy_montevideo_portal` | ar, bo, cu ×2, hn, ni ×2, pr, uy |

The second canary, the recommended first wave (8) and wave C (9) together name 22 outlets in 15 countries; Chile, Colombia, Costa
Rica, Mexico and Panama are in none. Priority followed the brief: Nicaragua and Cuba first (5 of the 9), then outlets that add a
publisher or a region (Opinión in Cochabamba, El Tribuno in Salta, Montevideo Portal, NotiCel, Criterio), then structures no wave
had. Owner independence is **not** established for most: ownership was not researched and is `unknown` in every proposal.

## 5. Sources with identified official routes

| Route (by the supplement; publisher-documented unless said) | Outlets |
|---|---|
| RSS catalogue or page of the publisher | `uy_montevideo_portal`, `bo_opinion`, `ar_el_tribuno`, `ec_el_universo`, `ec_el_comercio`, `pr_el_nuevo_dia`, `uy_el_observador`, `py_abc_color` (2019), `co_el_tiempo` (restricted), `mx_expansion` (hub only), `mx_el_siglo_de_torreon` (2008) |
| archive or section page observed | `ni_articulo66` (yearly archive, numbered pages), `cu_cubanet` (news archive), `cu_14ymedio`, `cu_diario_de_cuba`, `hn_criterio`, `pr_noticel`, `ni_nicaragua_investiga` (front page), `sv_el_faro` (editions) |
| sitemap | none new |

"Documented" is not "answers": none was requested.

## 6. Generic improvements; no adapter

| Change | Version | What it does |
|---|---|---|
| allotment of the candidate budget | `candidate-budget-order/1` | newest dated entries first, then undated in document order; events stay in document order |
| HTML listings: next page | `numbered-pagination/1`, `channel-parser/3` | `rel="next"` on anchors; the one link that is the same listing one page further (`/page/N`, `/pagina/N`, `?page=`…); one page per step |
| HTML listings: dates | `channel-parser/3` | the first `<time datetime>` of an `<article>` is the hint of its links |
| listing candidates wait | `candidate-filter-generic/2`, `canary-driver/4` | a listing is read and preserved without a rule; what it lists is `DEFERRED` until a reviewed allow pattern exists |
| incremental index reading | `expansion-order/2` | a child read completely before and stated with the same `lastmod` is not asked again |
| coverage measure | `discovery-coverage/2` | tells what a pass kept from what was a candidate already |
| outlets new to the registry | `apply_registration_proposal.py` | `new_outlets`: registered only with a record; an id or origin host the registry holds is refused |

**F7, corrected.** The previous report and CPD-0019 §7 said 44 of 303 entries turned away were newer than the oldest kept and
concluded that the sitemap was not newest-first. **That conclusion was wrong, and it was mine.** The preserved sitemap is
newest-first. The 44 came from counting as "kept" entries a *feed* had already made candidates, some older. Re-measured
(`config/source_discovery/candidate_budget_replay_2026-10-09.json`; workspace byte-identical before and after): from an empty
table both orders keep the same 200 of 534 (2026-10-07T15:41 to 10-08T16:05, local) and turn away the 334 older ones; on the
canary's own tables, 0 of 303 are newer than anything that pass kept. The first canary lost the old end of one listing and
nothing newer. The newest-first rule is kept as a rule of form — an ascending listing would otherwise fill its budget with its
oldest entries — and is **not** a repair of a measured loss. The limit of 200 is unchanged.

**Adapters: none**, and none is needed by anything on file. A publisher's RSS hub page is evidence for feeds, not a channel.
Limits stated: a listing without `<time>` gives no date; a page that needs JavaScript ("load more") is not read
(`pr_noticel`'s `/latest-articles/` is such a page by the supplement; its category page is not).

## 7. Tests

| | Result |
|---|---|
| `tests/test_source_structures.py` (new, 14) | RSS 1.0, Atom, Arc-style and WordPress-style feeds; dates with and without time or offset; a feed on a foreign host; the same article in two section feeds; the newest-first budget and its continuation; numbered pagination by path, by query and by `rel`; what is not a next page; endless and self-pointing archives end at the budget; teaser dates; incremental index reading; a child cut by the budget is re-read; **a listing outlet end to end** against a loopback server: read and preserved without a rule (4 requests, 0 items), then 9 articles and no navigation link under a rule, extracted and `RAW_PRESERVED` |
| `tests/test_source_expansion.py` (new, 9) | the overview is the join of its inputs and deterministic; classification and stages; identity cases decide nothing; wave C applies to a copy (91 outlets, no existing row changed, review package builds, a pin of 9 × 10 items); wave C after the first wave; id and host collisions refused; the operator's tool refuses a confirmation that is not typed at a terminal and offers no argument for one; the switch is turned alone and back to the same bytes |
| regressions F1–F7 (`tests/test_canary_findings.py`, 32) | pass; one test rewritten for the decided change (a listing channel is now selected, its candidates wait) |
| changed expectations, none weakened | version literals in `test_schedule.py`, `test_canary_findings.py`, `test_source_discovery.py`; `test_registry.py`: the import's outlets are those with a legacy row (so a new outlet is covered by its record) |
| a failure on the way, kept on record | the first full run had **4 failures** in `test_crash_recovery.py` (an HTTP run killed mid-request and resumed recorded 16 instead of 14 fetches): the incremental index rule skipped children the *same* run had read, so the resumed run no longer repeated its own requests. Repaired — only earlier runs count — and a regression added |
| full suite, final tree, switch off | **1382 passed, 8 skipped** (7 need the candidate tools of the extra `phase3`, 1 the symbolic-link test this account cannot run); 24 tests more than at the start; no tracked file modified by the tests |

Evidence types: all `reproducibility` (same inputs, same rows) and `robustness` (budgets, cycles, refusals). None is
`replicability` or `generalisability`.

## 8–9. Canaries, preservation, fixity, replay

**No canary ran.** Nothing new was preserved; fixity and replay evidence is that of 2026-10-08 (24 answers, 13 extractions,
`verify` `PASS`), unchanged. The per-outlet measurements the brief lists (channels asked, candidates, item requests, HTTP results,
fixity, replay, deduplication, holds) do not exist for any outlet beyond the first canary.

What changed is how the gate is operated (§13).

## 10. Extraction and Phase 3

Nothing new: no new real page exists. The pilot package, its key and its forms were not opened or changed.
`PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY` stands. The listing work touches discovery only; the legacy word-splitting and paragraph
filters were not taken over anywhere.

## 11. Comparison with the legacy system

Observation periods are not comparable (legacy: 32 crawl runs over six months; v3: one canary of 27 requests). The table states
what exists.

| Measure | Legacy (measured from the database copy, 2026-10-09) | COPREPAN 3.0 today |
|---|---|---|
| outlets in the register | 82 | 82 (5 registered); 63 outlet candidates outside it |
| outlets with a plausible discovery route | — | 79 registry outlets `CANDIDATE`; 51 of the 63 outside with a concrete address |
| technically checked channels | 116 of 352 with a success stamp | 3 channel documents with entries, 2 outlets |
| successful article acquisitions | 35,810 accepted rows | 13 pages |
| outlets with real articles | 42 (33 repeatedly, 12 until June 2026) | **1** |
| countries | 18 | **1** |
| outlets new against legacy | — | **0** |
| formerly unproductive outlets now productive | — | **0** |
| publisher / CMS diversity acquired | — | one outlet, one template |
| repeated success | 33 by the audit's rule | `NOT_YET_MEASURABLE` |
| failure categories | TDM heuristic, unexpanded indexes, extractor rejections | none new: nothing ran |

Of the outlets in the three waves, 6 of the first wave never gave the legacy system a usable article, and all 9 of wave C were
never in it. That is what the waves *could* show. **Whether the selection bias of technical crawlability is reduced is open: no
evidence yet, in either direction.**

## 12. Negative results, holds, remaining problems

- The second canary still has not run; every claim about F1–F5 on real servers is still open.
- `proceso.hn` stays held (no mechanism to lift a hold).
- `co_el_tiempo`: restricted by its publisher's terms — not to be requested before a decision.
- No allow rule exists for any listing: wave C will show **no article** for `pr_noticel` and none from the four other listing
  channels. That is the design; the rules follow from the preserved pages.
- Two Mexican candidates of the supplement have no current address; `sv_el_faro` does not fit a daily procedure.
- Coverage counted by outlets says nothing about owners, types, regions or time: those attributes are `unknown` for almost all.
- My error in the F7 reading (§6) stood in a decision for some hours; it is corrected forward (CPD-0020 §1, a dated note in
  CPD-0019).

## 13. Operator gates and decisions

**The gate, made operable** (CPD-0020 §7, runbook §9): `scripts/canary_operator.py` runs the whole procedure for the person who
arms — checks, `ARM` typed, arming commit, tests, baseline, **the digest shown and typed**, freeze, push, preflight, run, verify,
measure, evidence, and the disarming whatever happens. Both confirmations are read from a terminal and refused from a pipe, a
file or an argument (tested), so this session's shell cannot give them: it does not replace the operator's confirmation by an
agent's. Not tested: the tool's git and driver steps end to end — that needs an arming, which is the operator's. Its first real
use is therefore also its first test; every step is the runbook's own command, and the driver's refusals apply unchanged.

| What only the operator can do | Command or file |
|---|---|
| **second canary** | `python scripts/canary_operator.py --operator "Felix Tacke" --label second --outlet bo_el_deber --outlet do_diario_libre --outlet hn_proceso_digital --outlet py_la_nacion --outlet ve_efecto_cocuyo` |
| first wave (8 outlets): review, apply | the `--only` command in `config/registry_review/extended_canary_review_2026-10-09.json`, then tests, commit, push, then the tool with `--label wave-b` |
| wave C (9 new outlets): review, apply | `config/registry_review/wave_c_proposal_2026-10-09.json`, `apply_registration_proposal.py … --write`, then the tool with `--label wave-c` |
| `co_el_tiempo` | a licence / TDM decision. What is on file: the publisher's RSS page conditions use on personal, non-commercial purposes and restricts AI use (supplement); the legacy system stopped at this outlet on its TDM heuristic; CPD-0017 treats a general reservation as recorded evidence that does not by itself decide a research request — but **terms of use of a feed are not a robots line**, and CPD-0017 does not cover them. Options: leave it out; ask the publisher; a legal view on feed terms under the research exception. Until then: not registered, not requested |
| identity cases | §3 |

No permission problem occurred in this run; none was diagnosed.

## 14. Files, decisions, git

Decision: **CPD-0020**; a dated correction line in CPD-0019.

Created: `scripts/consolidate_source_discovery.py`, `scripts/replay_candidate_budget.py`, `scripts/canary_operator.py`;
`tests/test_source_structures.py`, `tests/test_source_expansion.py`;
`config/source_discovery/source_qualification_overview_2026-10-09.2.json`, `candidate_budget_replay_2026-10-09.json`;
`config/registry_review/wave_c_proposal_2026-10-09.json`; `docs/corpus_supply/SOURCE_COVERAGE_REPORT.md`; this report.
Committed as delivered (the operator's): the two supplement files.

Changed: `src/coprepan/discovery.py`, `discovery_coverage.py`, `candidate_filter.py`, `http_acquisition.py`, `canary_driver.py`;
`scripts/apply_registration_proposal.py`; `tests/test_canary_findings.py`, `test_source_discovery.py`, `test_schedule.py`,
`test_registry.py`, `tests/suites/foundation_contract.txt`; `docs/STATUS.md`, `docs/canary/RUNBOOK.md`,
`docs/acquisition/INDEX.md`, `docs/corpus_supply/INDEX.md`, `docs/architecture/INDEX.md`,
`docs/architecture/TERMINOLOGY_AND_NAMING.md`, `docs/decisions/README.md`, CPD-0019 (one dated line).

Not changed: the registry, the policy, the candidate rules, any baseline, any canary evidence, the inventory `2026-10-09.1`, the
three prediscovery files, the earlier proposal and its review, the pilot package. Nothing moved or deleted. The runtime workspace
was read (tree digest equal before and after); the preservation root, the legacy tree and CO.RA.PAN were not touched.

For the record, against AGENTS §5: once in this run a shell command carried an **empty** here-document (no content, no effect).
Files were written with the edit and write tools and with script files. The hook that would make this mechanical is still only
proposed.

Commits: see `git log` from `0c3b386`.

## 15. The next productive step

The second canary — one operator command (§13). Nothing else produces the evidence this project lacks. The evaluation run
follows from its evidence directory. The first wave and wave C are ready for review in parallel and should run after it, in that
order, each as its own canary.

## Operator report

- **Ergebnis.** Zusätzlich tatsächlich erschlossen: **0 Zeitungen, 0 Länder**. Nachgewiesen bleibt eine Zeitung in einem Land.
  Nur recherchiert bzw. offline qualifiziert: die Konsolidierung der 19 Rechercheeinträge (3 wirklich neue Zeitungen, 10 bereits
  vorgeschlagen, 1 neuer Kanal), paginierte und datierte HTML-Listings, datumspriorisiertes Kandidatenbudget, inkrementelles
  Lesen von Sitemap-Indizes, eine dritte Welle aus neun neuen Zeitungen als Vorschlag.
- **Status: `PARTIAL`** — Integration, Implementierung, Tests und Vorbereitung vollständig; **keine reale Aufnahme**, weil Arming und
  Freeze beim Operator liegen und nicht erfolgt sind.
- **Wichtigster technischer Fortschritt.** Nachweislich *offline*: Quellen ohne Feed (Archiv- und Rubrikseiten mit Pagination)
  können gelesen und konserviert werden, ohne Navigationslinks abzurufen; neue Zeitungen außerhalb des Legacy-Bestands haben
  einen Weg ins Register. Auf realen Servern funktioniert davon noch nichts nachweislich.
- **Wissenschaftliche Konsequenz.** Der Nachweis ist offen. Die tatsächliche Quellenvielfalt hat sich noch nicht verbessert.
  Korrektur: Der im letzten Report genannte Verlust von 44 neueren Sitemap-Einträgen war ein Messfehler von mir; real ging kein
  neuerer Eintrag verloren.
- **Operator-Entscheidung.** (1) Zweiter Canary: ein Befehl, zwei getippte Bestätigungen (`ARM`, Digest). (2) Review der
  Achter-Welle und (3) der Neuner-Welle C. (4) Lizenz-/TDM-Entscheidung zu `co_el_tiempo`. (5) Identitätsfälle.
- **Nächster Schritt.** `python scripts/canary_operator.py --operator "Felix Tacke" --label second --outlet …` im Terminal
  starten; danach ein Auswertungs-Run.
