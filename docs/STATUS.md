# COPREPAN 3.0 — Current Status

**This is the one place that says what actually exists.** Every other document describes a target,
a rule or a plan. If a document sounds as if something were built, and this file says it is not,
this file is right and the other document has a defect.

**As of 2026-10-08 (after the first real canary): the acquisition pipeline is built, has run once
against five real outlets in a bounded canary, and is not activated.** That run — armed and started
by the operator, 27 requests, 2026-10-08 — preserved 24 answers and **13 article pages, all of one
outlet**; its evidence verifies, and it exposed three defects of our own code and a bot challenge our
classifier did not recognise (§5a). It was `PARTIAL`, not a pass. Five outlets are registered for the canary; 77 are
proposed. Three storage roots are configured on the workstation (runtime, spool and an interim primary
preservation root). The thirteen pages are canary evidence, not corpus material: no extractor is
adopted, nothing is validated, nothing is activated.

**Since 2026-10-09 the defects that canary exposed are repaired and tested offline** (CPD-0019): on synthetic fixtures, a
loopback server and the preserved answers of 2026-10-08 read again — not on any real server. A second canary of the same five
outlets is prepared and waits for the operator's arming; an extended canary of twelve outlets exists as a registration
**proposal** and waits for the operator's review (§5b). A source-discovery inventory joins, for all 82 outlets, the legacy
system's own records with passive research of 2026-10-09: 1 outlet is `ACQUISITION_VERIFIED`, 2 are `QUALIFIED`, none is
operationally stable. **No request was made to any publisher on 2026-10-09.**

**State at the end of 2026-10-09 (§5d; this paragraph is the current one, the two around it are history):** four canaries ran with
real requests — the operator's second canary and three waves armed and frozen by a commissioned agent under versioned
authorisation records (CPD-0023). 22 outlets are registered; **14 have verified acquisition, in 11 countries; none is
operationally stable**; four origins are held behind browser challenges. Nothing is activated and the switch is `disabled`.

**Later on 2026-10-09** (CPD-0020): the operator's external research (19 entries) was consolidated with every earlier file into one
qualification overview; discovery now reads paginated and dated HTML listings and gives a pass's candidate budget to the newest entries;
a third wave of nine outlets that were never in the legacy system exists as a proposal; the canary procedure is one operator command.
All of it offline, on synthetic documents and one preserved listing. **Still one outlet with verified acquisition; still no request since
2026-10-08; no canary has run.**

**External acquisition is impossible again as committed**, by one tested refusal: the acquisition
policy — decided for the first canary on 2026-10-08 (CPD-0013, CPD-0017), like the schedule policy and the
registration of five outlets — has `external_acquisition: disabled`. It was `enabled` between the
operator's arming commit and the disarming commit of the same evening, for the canary only. The
crawler identity is configured and its public page is live (O-2, CPD-0014); an interim primary
preservation root is configured and qualified (O-3 interim, CPD-0014). A next canary needs a new
arming, the tests on that commit and a newly frozen baseline.

**One thing was done on real data: the legacy freeze manifest** (O-10, on operator go-ahead):
32,235 files, 18,782,593,808 bytes of the legacy tree, hashed read-only and re-verified (measured).
It is a manifest, not a preserved copy.

**The persistence layer has been attacked with real process kills and real concurrent
processes** (CPD-0009): six defect groups were found and repaired, one writer per workspace is
enforced, and an interrupted workspace has a named state and a deterministic way on —
`PRE_CANARY_ROBUSTNESS = PASS` for the failure, recovery and concurrency tests defined in that run
(§3), on temporary directories of one workstation. It closes no gate.

**Evidence tables are protected and derived tables rebuildable** (CPD-0010): the request log, the
discovery inputs and events, the candidate qualifications and the admission labels are chained like
the ledger and anchored when a run closes; the discovery candidates are checked against the
evidence; the identity tables are rebuilt from preserved packs and compared
(`PRE_CANARY_EVIDENCE_INTEGRITY = PASS`, §3). It closes no gate.

**The cross-corpus analysis contract exists as a technical proposal with a validator**
(`crosscorpus-analysis/v1`, CPD-0008). Two synthetic fixtures conform to it. It is not adopted by
CO.RA.PAN, no corpus material has passed through it, and it validates nothing scientific.

**The joint release contract `crosscorpus-release/v1` is implemented a second time, independently,
and adopted by CO.PRE.PAN** (CPD-0012; bundle digest `4fb72acf…dbbe0`, a verbatim pinned copy of
CO.RA.PAN's draft): this repository's own checks reproduce every digest and all 52 cases of the
shared vectors. A native export object exists (`coprepan-export/v1`, CPD-0011) and has carried
synthetic pages into a fixture release, a package and a study population. **The joint contract is
not frozen** (CO.RA.PAN has recorded no adoption), **no release of the corpus exists, and none can
be built**: no extractor is adopted. It closes no gate.

**The joint storage-management contract `crosscorpus-storage/v1` is in force in both repositories**
(CPD-0015; bundle digest `8d17fc21…18fb3`, a verbatim pinned copy of the bundle whose home is CO.RA.PAN): roles,
holdings, configuration states, separation, what a preservation step may claim, pending objects,
protection from cleanup, backup status and the procedure of a root migration. **The outage spool is
now in the acquisition path** (`preserve_pack`): an unavailable preservation target leaves a
verified, resumable pending copy and never a success. Tested on temporary directories with synthetic
packs; the canary driver calls the path, and the real canary took the direct route for all five packs
(the spool was not needed). **No backup exists; the interim primary on `D:` is a sole copy** and holds
its target marker and the five packs of the canary with their indexes and manifests (984,326 bytes,
measured). It closes no gate.

What exists beyond documents: the complete path channel → discovery → candidate → policy gate →
HTTP fetch → fetch record → sealed pack → preservation → document identity → extraction →
document version → admission label → replay, and a second and later visit of the same candidates
(schedule, conditional request, moved URL), exercised end to end against an HTTP server on a
loopback address serving synthetic documents, on temporary directories (§3) — **and once, for the first
visit only, against five real outlets over TLS on the real storage roots** (§5a). The second and later
visit, the outage path and a crash have never happened on real material.

---

## 1. Three separate axes

| Axis | Values | Meaning |
|---|---|---|
| implementation | `NOT_STARTED` · `PARTIAL` · `IMPLEMENTED` | code and tests exist |
| validation | `NOT_VALIDATED` · `VALIDATED` | measured against its gate on real or gold material, with a run report |
| activation | `INACTIVE` · `ACTIVE` | switched on for corpus material by an explicit decision |

`ACTIVE` requires `IMPLEMENTED` and `VALIDATED`. A stage that is planned and nothing else is
`NOT_STARTED` / `NOT_VALIDATED` / `INACTIVE`. The self-check enforces these rules.

## 2. Pipeline stages

| # | Stage | Implementation | Validation | Activation |
|---|---|---|---|---|
| 1 | outlet registry | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 2 | discovery | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 3 | fetch | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 4 | raw preservation | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 5 | document identity | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 6 | extraction | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 7 | admission labels | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 8 | normalisation | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 9 | NLP | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 10 | validated enrichment | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 11 | release | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 12 | cross-corpus contract | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |

What `PARTIAL` means for the nine stages, exactly:

| Stage | Exists | Does not exist |
|---|---|---|
| outlet registry | schema `coprepan-outlet-registry/v1`, validator, lookup; the legacy import, executed on a copy of the legacy database: **82 proposed outlets, 352 proposed channels**; a generated review package with a uniform id convention | **any registered outlet**; any attribute beyond what the legacy database held (type, group, time zone, URL rules); the human review |
| discovery | parsers for RSS, Atom, sitemap `urlset`, sitemap index, HTML listing; discovery events and candidates as append-only evidence; bounded expansion with cycle handling — candidate qualification with versioned rules; robots sitemaps as an optional source; channel health as a derived report — on synthetic channel documents | anything read from a real outlet; any outlet rule; decided health thresholds |
| fetch | HTTP transport (`http.client`): redirects, limits, explicit retries, `Retry-After`, pacing; policy gate in front of every request; robots evidence; crawler identity; request log; candidate lifecycle and fetch plan; conditional requests; permanent-redirect handling — against a loopback server | **any external request**; a decided schedule; TLS exercised; concurrency; behaviour against real servers and bot protection |
| raw preservation | fetch record; WARC pack writer, seal, derived and bound index, fixity check, torn-tail quarantine; state machine and ledger; fail-closed root resolution; promotion; outage spool; a preservation-target readiness check; packs read by an independent WARC reader (warcio 1.7.5, written subset) — on temporary directories | scheduled fixity, reconciliation, backup; a chosen, configured target; a run against one |
| document identity | id serialisation and canonical URL key (CPD-0003); document and version assignment, append-only identity tables, collision refusal, `duplicate_of` and `moved_to` relations (CPD-0005 §4) — on recorded exchanges | syndication clusters; URL-key aliases after a rule change; a durable home for the tables; any id minted for corpus material |
| extraction | the extraction record and its digests; storage by fingerprint; replay from the preservation root; a **baseline** extractor (`baseline_html/0.1.0`, lifecycle `EXPERIMENTAL`); an evaluation harness and review-package generator; a gold-sample design | an adopted extractor; a gold sample; any quality measurement; per-outlet rules; date parsing |
| admission labels | the technical label (`coprepan-admission-label/v2`, chained; rule set `admission-technical/1`): usable / unusable with reasons and evidence, append-only | every content-level label: article / not article, access class, language from content, length, type; any label on corpus material |
| release | the native export object `coprepan-export/v1` (builder, verifier); release manifest builder and explicit freeze; package and study-population builders; CO.PRE.PAN's own checks of `crosscorpus-release/v1` — on synthetic pages, on temporary directories | **any corpus export** (refused while no extractor is `ACTIVE`); a selection policy; an annotation layer and token counts; a date parser; an exports root on a real target; any release, distribution copy or deposit |
| cross-corpus contract | `crosscorpus-analysis/v1` as a proposal: vocabularies, table schemas, a fail-closed validator, manifest sealing, the token denominator, a compatibility view; COPREPAN's adapter from extraction records and a *supplied* annotation; a press and a radio fixture, both synthetic | **adoption by CO.RA.PAN** (O-6 is a joint decision); any export of corpus material; any annotation by an instrument; the selection-policy content; columnar storage; **the joint freeze of `crosscorpus-release/v1`** (adopted here by CPD-0012, not by CO.RA.PAN) |

`PARTIAL` for stages 2, 3, 7, 11 and 12 means "code and tests exist, offline". It is not a step towards
`ACTIVE`: activation needs validation on real material and the operator decisions of §5.

**Since the canary of 2026-10-08 the "does not exist" column above is out of date in four cells, and stays as
written for the record of what the stages are:** discovery has read real channel documents of three outlets
(one feed and one sitemap parsed, one feed refused by the parser, one sitemap index read); fetch has made 27
external requests over TLS; raw preservation has run once against the configured interim target; the baseline
has extracted thirteen real pages. None of this validates a stage: one bounded run, one outlet with items, open
defects (§5a).

## 3. Foundation

| Item | State | Where |
|---|---|---|
| Agent instructions | in place | `AGENTS.md`, `CLAUDE.md` |
| Document hierarchy and authority index | in place | `docs/architecture/INDEX.md` |
| Decisions | CPD-0001 to CPD-0004 `ACTIVE`; CPD-0005 to CPD-0021 and CPD-0023 to CPD-0025 `ACTIVE_WITH_VALIDATION_DEBT`; CPD-0022 `SUPERSEDED` by CPD-0023 (§6; see the registry for each) | `docs/decisions/` |
| **Foundation Core I** (master plan §12 item 3) | **complete** as infrastructure: all six items implemented and tested; the legacy import executed and repeatable; CPD-0003 reviewed. Reproducibility / infrastructure integrity only | run report of 2026-10-07 (core pipeline) §2 |
| Naming contract — lexical rules for corpus, generation, provenance class, `country_id`, `outlet_id`, `release_id`, schema ids | implemented and unit-tested | `src/coprepan/naming.py`, `tests/test_naming.py` |
| Naming contract — serialisation of fetch, channel, document, version, unit, sentence, token ids; canonical URL key | implemented and unit-tested (CPD-0003); **no id minted** | `src/coprepan/identity.py`, `tests/test_identity.py`, [`docs/identity/INDEX.md`](identity/INDEX.md) |
| Outlet registry | schema, validator, lookup implemented and unit-tested; holds **91 outlets: 22 registered (each by a registration record: 5 for the first canary, 8 of wave B and 9 of wave C on 2026-10-09 under a delegated operator authorisation), 69 proposed** | `config/outlet_registry.json`, `src/coprepan/registry.py`, `tests/test_registry.py` |
| Legacy outlet import | executed 2026-10-07 on a copy of the legacy database; deterministic on repetition; real schema equal to the assumed one; legacy-name → `outlet_id` table produced as `hypothesis`. **Not reviewed by a human** | `src/coprepan/legacy_registry_import.py`, `config/registry_review/`, corpus supply §16 |
| Legacy archaeology and component dispositions | recorded | [`docs/legacy/ARCHAEOLOGY.md`](legacy/ARCHAEOLOGY.md), CPD-0004 |
| Acquisition run and fetch record | implemented and unit-tested; run kinds `recorded_replay` and `http_fetch` | `src/coprepan/acquisition.py`, [`docs/acquisition/INDEX.md`](acquisition/INDEX.md) |
| Sealed WARC pack | implemented and unit-tested (own writer, standard library); read by warcio 1.7.5 for the record subset it writes — **not a general conformance claim** | `src/coprepan/pack.py`, `tests/test_warc_interoperability.py`, storage §14 |
| Discovery | implemented; tested on synthetic channel documents | `src/coprepan/discovery.py`, `tests/test_discovery.py` |
| Policy gate | implemented and tested; policy schema `v2` (`Crawl-delay` may bind). **The tracked policy is the decided canary policy `canary/2026-10-09.1` (the policy of CPD-0013 / CPD-0017 with one more disabled channel, CPD-0019 §6) with `external_acquisition: disabled`: it denies everything until a canary is armed** | `src/coprepan/policy.py`, `config/acquisition_policy.json` |
| Robots evidence | parser after RFC 9309 implemented and tested (`robots-parser/3`: a byte-order mark, a file that is no robots file, a content-coded file decoded for reading and preserved as received). What the evidence means is the policy's: three layers, CPD-0017 — the project does **not** claim RFC 9309 conformance | `src/coprepan/robots.py`, `src/coprepan/policy.py` |
| Access controls as observed evidence | implemented (`access-control/2`); tested against the loopback server: 401, 403, 429, 451, CAPTCHA and challenge pages — the Sucuri challenge of 2026-10-08 among them, whatever its status —, login and paywall redirects are classified, recorded, not retried, and hold the origin; a canary re-derives holds from stored answers | `src/coprepan/access_control.py`, `tests/test_research_tdm_policy.py` |
| Crawler identity | contract implemented and tested; **the tracked identity is the decided one** (`PanhispanicMediaResearchBot`, Marburg University; CPD-0014). Its public page is live at `https://coprepan.hispanistica.com/crawler/` (verified 2026-10-08) | `src/coprepan/crawler_identity.py`, `config/crawler_identity.json`, `web/coprepan/`, `web/DEPLOY_RECEIPT_2026-10-08b.json` (the page as redeployed for CPD-0017) |
| Storage roles and roots | roles shared with CO.RA.PAN 3.0; separation enforced (no shared or nested roots, a backup never on the primary's volume); runtime and spool roots and an **interim primary preservation root** on `D:` configured; backup, distribution and exchange `NOT_CONFIGURED`. **Governed by the joint contract `crosscorpus-storage/v1`** (CPD-0015): pinned copy, own implementation, shared reference cases, joint check with the sister checkout | `src/coprepan/storage_roots.py`, `src/coprepan/storage_contract.py`, `scripts/storage_contract.py`, `config/storage_targets.yml`, `tests/test_storage_architecture.py`, `tests/test_storage_contract.py`, [`docs/storage/INDEX.md`](storage/INDEX.md) §19, CPD-0014 |
| HTTP fetcher | implemented; tested against a real HTTP server on a loopback address; **no TLS, no external request** | `src/coprepan/fetcher.py`, `tests/test_fetcher.py` |
| HTTP acquisition run, request log | implemented; tested in the offline canary | `src/coprepan/http_acquisition.py` |
| Candidate qualification | implemented and tested; generic rules only — **the tracked outlet rules are empty** | `src/coprepan/candidate_filter.py`, `config/candidate_rules.json`, `tests/test_schedule.py` |
| Candidate lifecycle and fetch plan | implemented and tested; **the tracked schedule policy is the decided canary policy `canary/2026-10-08.1`** (slow on purpose; not a policy for scheduled crawling) | `src/coprepan/schedule.py`, `config/schedule_policy.json`, `tests/test_schedule.py` |
| Conditional requests, permanent redirects, robots sitemaps, crawl-delay evidence | implemented; tested against the loopback server | `src/coprepan/fetcher.py`, `tests/test_refetch_e2e.py` |
| Channel health | implemented and tested as a derived report; thresholds undecided; switches nothing | `src/coprepan/channel_health.py` |
| Admission labels (technical) | implemented and tested on synthetic material | `src/coprepan/admission.py`, `tests/test_admission_eval.py` |
| Extraction evaluation harness, review package | implemented and tested on synthetic pages; **no gold, no real page, no result** | `src/coprepan/extraction_eval.py`, [`GOLD_SAMPLE_DESIGN.md`](extraction/GOLD_SAMPLE_DESIGN.md) |
| Cross-corpus analysis contract `crosscorpus-analysis/v1` | **technical proposal**; validator, sealing, denominator rule, compatibility view implemented and tested on two synthetic fixtures; **not adopted by CO.RA.PAN** | `src/coprepan/analysis_contract.py`, `tests/test_analysis_contract.py`, [`docs/crosscorpus/INDEX.md`](crosscorpus/INDEX.md) |
| COPREPAN contract adapter | implemented and tested; takes its annotation as an argument — **COPREPAN has no annotator** | `src/coprepan/analysis_export.py` |
| Joint release contract `crosscorpus-release/v1` — pinned bundle | verbatim copy of CO.RA.PAN's draft (49 files), pinned by bundle digest; a drifted copy is refused by the loader and fails the suite. Status `DRAFT`; **adopted by CO.PRE.PAN only** (CPD-0012) | `contracts/crosscorpus-release-v1/`, `config/crosscorpus/contract_pins.json` |
| Joint release contract — CO.PRE.PAN's own checks | implemented independently; every digest and all 52 cases of the bundle's vectors reproduced (measured 2026-10-08). Synthetic fixtures only | `src/coprepan/release_contract.py`, `tests/test_release_contract.py`, [`docs/release/INDEX.md`](release/INDEX.md) |
| Native export object `coprepan-export/v1`; release, freeze, package, study-population builders | implemented and tested on the synthetic canary through the real pipeline code; **no corpus export can be built** (extractor `EXPERIMENTAL`) | `src/coprepan/release_export.py`, `tests/test_release_export.py`, CPD-0011 |
| Phase-3 layer architecture | written; decides order and boundaries of the text layers, no tool and no threshold | [`docs/architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md`](architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md) |
| **Canary driver** (stages A–E, real-request budgets, receipt) and the end-of-canary `verify` / `measure` | implemented; qualified against a scripted loopback outlet (38 tests); **run once for real on 2026-10-08** (27 requests, `COMPLETE`; `verify` `PASS`; result `PARTIAL`, §5a); the acquisition switch is off again | `src/coprepan/canary_driver.py`, `src/coprepan/canary_evidence.py`, [`docs/canary/RUNBOOK.md`](canary/RUNBOOK.md), [`docs/canary/evidence/`](canary/evidence/), CPD-0016 |
| Canary planner and preflight | implemented and tested; on the repository as committed: preflight `NOT_READY` (the switch is off). It was `READY` on each armed commit of a canary: once on 2026-10-08 (`15ec1fd`, baseline `96c271e3…`) and for the four canaries of 2026-10-09 (§5d) | `src/coprepan/canary.py`, `tests/test_canary.py` |
| Wrappers of three classical extractor candidates (trafilatura 2.3.1, readability-lxml 0.9, jusText 3.0.2) | implemented and tested; tools in the extra `phase3`, **not** runtime dependencies; all `EXPERIMENTAL`, nothing adopted; a **pilot** review package on the thirteen real pages exists outside the repository, no decision filled | `src/coprepan/extractor_candidates.py`, `scripts/phase3_review_package.py`, `tests/test_extractor_candidates.py`, [`docs/extraction/INDEX.md`](extraction/INDEX.md) §9, CPD-0018 |
| Offline end-to-end canary with failure injection | passes: two independent passes are byte-identical; a later run adds and never rewrites | `tests/test_offline_e2e.py` |
| Preservation-target readiness check | implemented and tested on temporary directories; **no target chosen** | `src/coprepan/preservation_target.py`, storage §15 |
| Capacity model | calculator implemented; **bytes per real page measured once, on thirteen pages of one outlet** (received body mean 53,895 B as served; measured 2026-10-08) — not enough to size anything but a next canary (§5, O-4) | `src/coprepan/capacity.py`, storage §16 |
| Acquisition baseline manifest | implemented; a frozen manifest now verifies the digest it was frozen with (a defect of the check, repaired 2026-10-08). The repository as committed is `PRE_FREEZE` (the switch is off). **Two frozen canary baselines are kept as evidence**: the first (`f7ae73c3…`, superseded: its commit preceded the repair) and the one the canary ran under (`96c271e3…` on `15ec1fd`) | `src/coprepan/freeze.py`, `docs/canary/BASELINE_FROZEN_2026-10-08.json`, `docs/canary/BASELINE_FROZEN_2026-10-08b.json` |
| Registry review package | generated, checked against the registry by a test; **a recommendation, nothing registered** | corpus supply §17 |
| Document identity tables | implemented and tested on recorded exchanges | `src/coprepan/document_identity.py`, [`docs/identity/INDEX.md`](identity/INDEX.md) §7 |
| Extraction contract and baseline extractor | implemented; behaviour of the contract tested; **quality unknown, extractor not adopted** | `src/coprepan/extraction.py`, [`docs/extraction/INDEX.md`](extraction/INDEX.md) |
| Vertical canary (fixture → fetch record → pack → preservation → identity → extraction → version → replay) | passes on four synthetic pages, on temporary directories | `src/coprepan/core_pipeline.py`, `tests/test_core_pipeline.py` |
| State machine and ledger primitives | implemented and unit-tested; record format `v2` with a hash chain since 2026-10-08 | `src/coprepan/ledger.py`, `tests/test_ledger.py` |
| Evidence classes; chained primary-evidence tables (`previous_row_sha256`); heads recorded when a run closes | implemented; manipulation of earlier rows detected in every chained table and refused; torn tail told apart from a manipulation; newest row anchored from a clean close on | `src/coprepan/jsonl.py`, `src/coprepan/evidence.py`, `tests/test_evidence_integrity.py`, CPD-0010 §1–§3 |
| Candidates as derived state | implemented; checked against events and request log; missing rows completed, never judged | `src/coprepan/http_acquisition.py`, `src/coprepan/discovery.py` |
| Identity tables as rebuildable derived state | implemented; rebuilt from preserved evidence in a temporary directory and compared (`CORRECT` · `REBUILDABLE` · `CONFLICTING` · `SOURCE_EVIDENCE_DAMAGED`); adoption moves the old directory aside, never deletes | `src/coprepan/identity_rebuild.py`, `tests/test_evidence_integrity.py` |
| **`PRE_CANARY_EVIDENCE_INTEGRITY`** | **`PASS`** (2026-10-08) — the last local evidence-integrity point found before the real canary is closed, for the tests defined in that run. **Not** a gate; says nothing about a real target, a power failure or a real server | [run report](agent-runs/2026-10-08_evidence-table-integrity-closure.md) |
| Writer lock (one writer per workspace) | implemented; tested with real processes, including release when the holder is killed | `src/coprepan/exclusive.py`, `tests/test_crash_recovery.py` |
| Recovery: diagnosis and repair of an interrupted workspace | implemented; 24 pipeline and 4 HTTP crashpoints killed for real, each recovered by an independent process to the state of an uninterrupted run | `src/coprepan/recovery.py`, `tests/test_crash_recovery.py` |
| Concurrency semantics of ledger, tables, layer store, promotion, workspace | measured before and after repair; asserted with real concurrent processes | `tests/test_concurrency.py`, CPD-0009 §3 |
| **`PRE_CANARY_ROBUSTNESS`** | **`PASS`** (2026-10-08) — the local pipeline passed the adversarial failure, recovery and concurrency tests defined by the audit. **Not** a gate; not a statement about a real target, a network share, a power failure or a real server | [run report](agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md) |
| Stage-status self-check | implemented | `tests/test_repository_contract.py` |
| Test guards (no network, no storage root, suite membership) | implemented | `tests/conftest.py` |
| Storage-target configuration and root resolution | fail-closed resolver implemented and unit-tested; **no root configured** | `config/storage_targets.yml`, `src/coprepan/storage_roots.py`, `tests/test_storage_roots.py` |
| Promotion semantics and outage spool | implemented; **the spool is in the acquisition path** (`core_pipeline.preserve_pack`, `drain_spooled_packs`; CPD-0015): outage → verified pending copy (spool, or workspace when no spool is usable) → drain verifies on the target before release; nothing deleted. Tested **on temporary directories only**, also on the interim primary's file system; no driver calls it yet | `src/coprepan/preservation.py`, `src/coprepan/outage_spool.py`, `src/coprepan/core_pipeline.py`, `tests/test_preservation.py`, `tests/test_storage_contract.py` |
| Write-once layer store | implemented and unit-tested; its durable location (role) is undecided | `src/coprepan/layer_store.py`, `tests/test_layer_store.py` |
| Release gate suite | scaffold; **contains no test**. It gates software changes of a pipeline that does not exist yet; the release-contract conformance tests are in `foundation_contract` (handoff gate PG2) | `tests/suites/release_gate.txt` |
| Git | initialised 2026-10-07 on operator brief: branch `main`, remote `origin` = `https://github.com/FTacke/coprepan.git`; no history taken over from the legacy repository | [closure run report](agent-runs/2026-10-07_coprepan-repository-migration-closure.md) |
| Legacy freeze `coprepan-legacy-2026-06` | **manifest built and verified 2026-10-07** (`MANIFEST_ONLY`): 32,235 files, 18,782,593,808 bytes; release scope 3,256 files, 17,370,148,925 bytes (measured). **No preserved copy, no restore check** (need O-3) | `docs/legacy/freeze/coprepan-legacy-2026-06/`, `src/coprepan/legacy_freeze.py`, `docs/legacy/INDEX.md` §5 |

## 4. Production stack

None. No model, provider, crawler, extractor or annotator is active. The NLP pins in
`pyproject.toml` `[tool.coprepan.nlp]` are marked `PLANNED`: they are not installed and not used.
The package has no runtime dependency. `baseline_html/0.1.0`, `pack-writer/1`, `http-fetcher/1`,
`channel-parser/3`, `robots-parser/3`, `access-control/2`, `canary-driver/4`, `expansion-order/2`, `candidate-budget-order/1`, `numbered-pagination/1`, `fetch-planner/1`, `candidate-filter-generic/2`,
`admission-technical/1`, `channel-health/1`, `extraction-eval/1` and `legacy-freeze/1` are component versions recorded in artefacts; none is an
adopted production component. `warcio==1.7.5` is a test-only dependency (the independent WARC
reader); no runtime code imports it.

No external API is used by any code in this repository.

## 5. Open gates blocking production crawling

Two columns, because "the code is ready" and "the gate is passed" are different statements.
Technical state: `TECHNICALLY_READY` (built and tested offline) · `NOT_BUILT`. Gate state:
`OPEN` · `READY_FOR_HUMAN_REVIEW` (everything an agent can prepare is delivered) · `PASS`.
**One gate is `PASS`: O-10, which is a go-ahead and a manifest, not a production gate.**

| Gate | Technical state | Gate state | What closes it | Owner |
|---|---|---|---|---|
| O-1 acquisition policy | `TECHNICALLY_READY` — decided **for the first canary** (CPD-0013, amended by CPD-0017): robots always read and recorded, a `Disallow` overridden only as a recorded research override (`SCIENTIFIC_TDM_POLICY_V1`), access controls never worked around, `Crawl-delay` binding, 10 s per origin, a slow schedule; `external_acquisition` still `disabled` | **`PASS` for the canary scope** (`O-1_CANARY`); the switch is turned at arming. **`OPEN`** for scheduled crawling | the normative decision: robots mode, absent / unreachable robots, whether `Crawl-delay` binds, pace per origin, **the schedule policy (how often a page is asked again, when a failing or absent URL is left alone, whether conditional requests are used)**, opt-out handling, retention of raw copies; recorded as a decision and committed as `DECIDED` policy files | operator / institution |
| O-2 crawler identity | `TECHNICALLY_READY` — configured with the operator's values (CPD-0014) | **`PASS`** (2026-10-08): the contact page is public over HTTPS, the User-Agent is built by the existing contract | four values in `config/crawler_identity.json`: crawler name, organisation, contact URL, contact e-mail — and the public page the URL names | operator / institution |
| O-3 preservation target | `TECHNICALLY_READY` — readiness check built; **interim primary on `D:` qualified** | **`PASS` for the interim scope** (`O-3_INTERIM`, 2026-10-08): temporary primary for the small canary only — not the long-term institutional target, not a backup, no capacity statement. **`OPEN`** for the long-term target (the new university file system). Inventory: ([run report](agent-runs/2026-10-08_registry-policy-storage-real-acquisition-canary.md) §6) | choosing the target; then `initialise_target`, a `READY` readiness report, and the second half of the Phase-1 gate on it | operator / institution |
| O-4 storage capacity | `TECHNICALLY_READY` — model built; **first real measurement 2026-10-08** (24 fetch records, 13 pages of one outlet): 128,012 B per fetch over all layers (CENTRAL; 89,941–144,882), i.e. 8.4–13.5 GiB per 100,000 fetches (projected) | **`OPEN`** — not a constraint for a second canary on the interim target; no basis for sizing the institutional file system | item sizes from several outlets and a measured number of fetches per outlet-day ([run report](agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md) §8) | measured, then operator |
| O-10 legacy freeze manifest | built, run on the legacy tree, verified twice (module and an independent script) | **`PASS`** (2026-10-07) | — closed. It closes the go-ahead and the manifest only: the frozen release still needs a preserved copy and a restore check (O-3) | operator |
| O-11 registry review | `TECHNICALLY_READY` — review package delivered; five routine outlets registered by record | **`PASS` for the canary subset** (`O-11_CANARY_SUBSET`); full review `PARTIAL`: 77 outlets, the id convention as a whole and one attribution case are **`READY_FOR_HUMAN_REVIEW`** | the human decisions of corpus supply §17; registration by reviewed commit | operator, scientific |
| O-12 acquisition baseline freeze | `TECHNICALLY_READY` — manifest builder with a **canary scope** (CPD-0016: does not wait for O-4); state `PRE_FREEZE` while the switch is off | **`PASS` for the first canary** (`O-12_CANARY`, 2026-10-08): frozen `96c271e373dc…7863f` on `15ec1fd`, and the canary ran under it. **`OPEN`** for every later run: a baseline is frozen per armed commit | for a next canary: a new arming commit, then the baseline built on it and frozen by stating its digest — [`docs/canary/RUNBOOK.md`](canary/RUNBOOK.md) §1–§3 | operator |
| Phase-1 core gate (promotion, idempotence, conflict, crash recovery) | passes on temporary directories **and, 2026-10-08, with the temporary files on the interim `D:` file system** (real process kills, real concurrent processes) | **`PASS` for the interim target** (`PHASE1_INTERIM_TARGET`); **`OPEN`** on the long-term target | the same tests on the real preservation target (needs O-3) | engineering, then operator |
| Phase-2 canary gate | the offline canary passes; **it is not this gate**. The first real canary ran on 2026-10-08: every fetch traceable, read-back and fixity of all 24 bodies, replay of 13 extractions without network, bytes measured — and **items from one outlet of five** | **`OPEN`** — first run `PARTIAL` (§5a) | **the defects of §5a are repaired with regression tests (2026-10-09, §5b)**; what is left: a second bounded canary in which the registered outlets are actually acquired; `python -m coprepan.canary preflight` says whether it may start (`NOT_READY` today: the switch and a new frozen baseline) | engineering, then the operator's arming |

### 5a. What the first real canary showed (2026-10-08) — the findings as they stood that evening

*The "State" column is the state of 2026-10-08 and is kept as written. What each finding is now: §5b.*

Run `acq1-20261008T203414628095Z-ed630d8e8a14`, 27 real requests, five outlets, `COMPLETE`; verification `PASS`
(read-back and fixity of 24 bodies, `RAW_PRESERVED` = verified bytes, 13 extractions replayed without network, the
receipt re-derived from evidence, nothing pending, budgets respected). Result within its scope: **`PARTIAL`**.
Evidence: [`docs/canary/evidence/`](canary/evidence/); report:
[`2026-10-08_real-canary-evaluation-o4-phase3-pilot.md`](agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md).
**Reproducibility and robustness of one run; nothing generalisable; not an activation.**

| | Finding | State |
|---|---|---|
| F1 | a `robots.txt` served gzip-compressed is parsed without being decompressed: two outlets (`bo_el_deber`, `py_la_nacion`) were held with nothing read | **open defect** |
| F2 | the access-control classifier does not recognise the Sucuri JavaScript challenge (`proceso.hn`, status 307 without `Location`): the origin was not held and **one more request was sent to it**. Nothing was worked around | **open defect of a policy guarantee** |
| F3 | item planning takes the candidates of the whole workspace: 64 requests for another outlet's pages were planned and all refused by the policy gate (`off_origin`); none was sent | **open defect** |
| F4 | the robots / channel budget (8 per outlet, a whole fetch of 4 must fit) does not reach the second level of a sitemap index: 92 child sitemaps of `ve_efecto_cocuyo` not read | open, a budget decision |
| F5 | the channel parser refuses a feed containing `<!DOCTYPE` inside CDATA (`ve_efecto_cocuyo` RSS) | **open defect** |
| F6 | the registered news sitemap of `hn_proceso_digital` answers 404 | open, registry |
| — | no robots `Disallow` applied to any request; **the research override (CPD-0017) was not used and is untested on a real server**; no opt-out, no legal hold, no TDM reservation header observed | observation |

Phase 3 on this material: `PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY` (thirteen pages, one outlet, one cell of the
design's strata). A **pilot** review package is ready for a human reviewer outside the repository
([extraction](extraction/INDEX.md) §9); no gold exists.

### 5b. After the repair run of 2026-10-09 (CPD-0019)

Offline evidence only: `tests/test_canary_findings.py`, `tests/test_source_discovery.py`, and the preserved answers of the
first canary read again by the repaired code (`config/source_discovery/canary_replay_2026-10-09.json`). Report:
[`2026-10-09`](agent-runs/2026-10-09_discovery-source-recovery-and-acquisition-qualification.md).

| | Now | Shown on the preserved answers of 2026-10-08 |
|---|---|---|
| F1 | repaired: a robots file is decoded for reading, preserved as received | both gzip-coded files parse; neither disallows a channel of the canary |
| F2 | repaired: the challenge is `bot_challenge`; holds are re-derived from stored answers | the 307 of `proceso.hn` is classified; that origin is **held for every later canary on this workspace** |
| F3 | repaired: a run sees its own candidates | — (64 candidates carry a `DENIED` row from that evening; due again under the new policy version) |
| F4 | repaired: hop-wise budgets, 3 of 8 non-item requests reserved for index expansion, a stated read order | the index of `ve_efecto_cocuyo` (92 children) would be read to its three newest post sitemaps |
| F5 | repaired: the declaration guard reads markup only | the refused feed parses: 10 items |
| F6 | the 404 channel is disabled; nothing replaces it | — |
| F7 | measured, limit unchanged: 303 of 534 entries of one news sitemap turned away, 44 of them newer than the oldest kept | — |

| Canary | State | Gate |
|---|---|---|
| second (the five registered outlets) | **prepared**; preflight `NOT_READY` only for the switch and a new frozen baseline | the operator's arming, [runbook](canary/RUNBOOK.md) §8 |
| extended (twelve outlets, ten countries) | **proposal** — nothing registered | O-11: the operator's review and `scripts/apply_registration_proposal.py --write`; then the arming |

**Superseded as a state on 2026-10-09 by §5d**: the second canary ran, and eight of the twelve outlets were registered and asked.

### 5c. After the source-expansion run of 2026-10-09 (CPD-0020)

Offline evidence only (`tests/test_source_structures.py`, `tests/test_source_expansion.py`; one preserved listing replayed). Report:
[`2026-10-09`](agent-runs/2026-10-09_integrated-source-expansion-and-acquisition-qualification.md).

- **F7 corrected.** The first canary's budget lost no newer entry: 0 of the 303 entries turned away are newer than anything that pass kept
  (the "44" of §5b counted candidates a feed had made). The budget now goes to the newest dated entries all the same; the limit is unchanged.
- **Listings.** `rel=next` on anchors, numbered pagination, dates from `<time>`; what a listing lists waits for a reviewed allow rule, so a
  listing can be read and preserved before any rule exists. No real listing has been read.
- **Three waves, none run:**

| Wave | Outlets | State | Gate |
|---|---|---|---|
| second canary | the five registered | prepared | the operator: `python scripts/canary_operator.py --operator "…" --label second --outlet …` ([runbook](canary/RUNBOOK.md) §9) |
| first extended wave | 8 of the 12 proposed (review of 2026-10-09) | proposal, reviewed, nothing registered | O-11 (`apply_registration_proposal.py --only … --write`), then the same command |
| wave C | 9 outlets that were never in the legacy system, 7 countries | proposal, nothing registered | O-11, then the same command |

- **Overview** `config/source_discovery/source_qualification_overview_2026-10-09.2.json`: 82 registry outlets (79 `CANDIDATE`, 2
  `TECHNICALLY_QUALIFIED`, 5 `REGISTERED`, 1 `ACQUISITION_VERIFIED`, 0 stable) and 63 outlet candidates outside the registry.

Not a production gate, but open and recorded here because a stage depends on it: **O-6
(cross-corpus naming and semantics)** — `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN`.
COPREPAN's side is decided (CPD-0008); the contract is in force between the corpora only when
CO.RA.PAN adopts it. Its release and freeze semantics now have a joint draft,
`crosscorpus-release/v1`, implemented on both sides and adopted here (CPD-0012); the joint freeze
needs CO.RA.PAN's adoption record. One joint point has a recommendation from this side and no
decision: whether a release may be frozen with token counts `not_available` (contract §16 Q1).

Full list: [master plan](plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) §13.


### 5d. After the acquisition run of 2026-10-09 (CPD-0023, CPD-0024)

Real requests, four completed canaries. Report: [`2026-10-09`](agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md). **The three waves of §5c ran**; the table there is history.

| Canary | Armed and frozen by | Outlets | Item pages (200), preserved, verified, replayed | Verification |
|---|---|---|---|---|
| second (A) | the operator in person | 5 | 31 from 2 outlets | `PASS` |
| wave B | the delegate under `DOA-2026-10-09-1` | 8 | 72 from 6 outlets (5 of them section pages, F9) | `PASS` |
| wave C1 | the delegate under `DOA-2026-10-09-1` | 9 | 40 from 6 outlets | `PASS` |
| wave C2 (repeat) | the delegate under `DOA-2026-10-09-3` | 2 | 20 from 2 outlets, all first listed by an HTML listing | `FAIL` on one check when it ran (an earlier interrupted run had no result); `PASS` after that run was closed as `FAILED` |

- **Outlets with verified acquisition (five or more item pages in one bounded run): 14**, in 11 countries — `do_diario_libre`, `bo_el_deber`,
  `ec_primicias` (by a route since closed), `es_el_mundo`, `ni_confidencial`, `pe_diariocorreo`, `pe_la_republica`, `sv_el_diario_de_hoy`,
  `ar_el_tribuno`, `bo_opinion`, `cu_14ymedio`, `hn_criterio`, `ni_nicaragua_investiga`, `pr_noticel`. **None is operationally stable**: one
  outlet has two runs on two days, the others one.
- **Held** (a browser challenge; nothing further asked, nothing worked around): `hn_proceso_digital`, `ve_efecto_cocuyo`, `cu_cubanet`,
  `ni_articulo66`.
- **Registered and without acquisition:** `py_la_nacion` (F8, repaired, not asked again), `gt_lahora` (F10, repaired, not asked again),
  `ec_el_universo` (F11: its feed names the apex host, the registry holds `www`; open), `uy_montevideo_portal` (F12: article links are a nameless
  query, 60 entries are one candidate; open).
- **Delegated operator mode** (CPD-0023): in force and used for real; the interactive mode is unchanged. A wave's limits cap the budget (CPD-0024).
- **Repaired in this run, each with a regression test:** F8 `http` entries of an `https` origin; F9 an HTML answer of a feed channel is a
  listing; F10 white space before the XML declaration; F14 a second run on a day whose pack is sealed. **Not yet seen on a real server after
  the repair:** F8, F9, F10. F14's repair ran for real in the C2 repeat.
- **An evidence gap, recorded:** the first C2 start made two requests to `criterio.hn` whose answers were not recorded (F14). Its run record
  says `FAILED` and says so.
- **Candidate rules:** two outlets (`hn_criterio`, `pr_noticel`), written from preserved listing pages. Every other outlet has generic rules only.
- **Nothing is activated.** The switch is `disabled`; every production gate that was open is open.

## 6. Validation debt

Everything scientific. No extraction, annotation, enrichment or release has been validated. The
first validations are defined by the gates of Phases 1–4 (master plan §11).

What the tests of 2026-10-07 establish is **reproducibility** (same inputs, same ids and bytes;
two independent acquisition passes byte-identical; replay from preserved bytes; the same history
gives the same fetch plan; the same sample and arms give the same evaluation) and
**robustness** against injected failures (parse failure, policy denial, transport failure, retry
exhaustion, truncated bodies, interrupted runs, failed promotion, damaged pack, index and layer;
stale validators, a 304 nobody asked for, a revalidation with no known target, conflicting
candidate rules, a non-deterministic extractor arm, a changed, added or removed legacy file)
— on synthetic documents and a loopback server. The legacy freeze manifest is the one exception:
it is reproducibility evidence on real files (built once, re-verified by the module and by an
independent script). They establish nothing about replicability or
generalisability, and nothing about any real outlet. Reading the packs with warcio is
*interoperability with one independent reader*; it is not replication of any result.

Named debts of CPD-0005, CPD-0006 and CPD-0007 (`ACTIVE_WITH_VALIDATION_DEBT`):

| Debt | Closed by |
|---|---|
| `pack-writer/1` output read by an independent WARC reader | **paid 2026-10-07** for the written record subset with warcio 1.7.5 (storage §14). Other tools: not tried |
| Discovery against real feeds, sitemaps and listing pages | Phase-2 canary |
| The fetcher against real servers: TLS, real redirect and error behaviour, bot protection, real `Retry-After` | Phase-2 canary |
| The policy gate under a decided policy; robots files of real sites; the canary policy itself (binding `Crawl-delay`, the pace, the schedule) on real servers | Phase-2 canary |
| The five registered outlets: whether their channels are alive; whether the generic URL rules `v1` fit their URLs | Phase-2 canary (collision diagnostic); a new rule version where they do not |
| The identity policy on real URLs: per-outlet rules, the canonical-collapse diagnostic on real templates | Phase-2 canary |
| Promotion, idempotence, conflict and crash recovery on a real preservation target | second half of the Phase-1 gate; needs O-3 |
| The legacy importer's proposal reviewed | the registry-review gate (§5) |
| Baseline extractor against real pages; an adopted extractor | Phase 3: gold sample, preregistered comparison |
| Identity policy on real URLs (per-outlet rules; collision behaviour at scale) | Phase-2 canary |
| Process-kill crash tests | **done 2026-10-08 on temporary directories and on the interim `D:` file system** (28 crashpoints, real kills; CPD-0009). Still owed: the same on the long-term target (the new university file system); power failure is not simulated |
| Re-fetching against real servers: real validators, real 304 behaviour, real permanent redirects, real `Retry-After` | Phase-2 canary and the runs after it; needs a decided schedule (O-1) |
| The generic candidate rules on real listings (what they reject, what they miss); any outlet rule | Phase-2 canary |
| Channel-health states on real channels; thresholds | after the canary |
| Technical admission labels on real pages; every content-level label | Phase 3 |
| The evaluation harness on real pages with a human reference; the metrics as diagnostics checked against reviewers | Phase 3, gold sample |
| Legacy freeze: preserved copy, restore check, a study loader reading the copy | Phase 0 closure; needs O-3 |
| The analysis contract on real material: a COPREPAN export of annotated corpus text; a CO.RA.PAN adapter and export; adoption | after the canary and Phase 3 / 4 here; a separate run in CO.RA.PAN |
| Annotation equivalence of the two instrument paths on shared written text | Phase 4 (design: contract §11) |
| `tense-v3` (press) against `tense-v4` (radio) on the same text; legacy labels against the verbal-complex layer | bridge sample (design: contract §12) |
| Every "comparable with caveat" of the comparability matrix | the measurements the matrix names; none exists |
| The release contract on real material: a release of real CO.PRE.PAN exports verified with exports present (handoff gate PG4); the export object with an adopted extractor, an annotation layer, parsed dates | after Phase 3 / 4; needs O-3 for a durable exports root |
| The points where the two implementations of `crosscorpus-release/v1` read the text differently beyond the vectors (four found by reading) | a change of the bundle in its canonical home, with new vector cases; then both pins move |
| Writer lock and append locks on the file system the runtime workspace will really use; exclusive publication on the real preservation target (a share) | Phase-1 gate on the chosen target (O-3) |
| Integrity of the *descriptive* fields of pack manifests, preservation manifests and run results (a single changed bit was not noticed in about a third of cases: storage §17), and of rows written after the last closed run (until the next close) | not decided (CPD-0010, "Not decided here"); none is evidence that cannot be recomputed or has no other copy |
| Recovery after a power failure (un-synced data, directory entries) | not testable here; an operational assumption to state with O-3 |

## 7. Machine-readable assertions

Consumed by `tests/test_repository_contract.py`. The test compares this block with
`src/coprepan/stages.py` and enforces the axis rules of §1. **Update this block, the tables above
and the code in the same run** as any change of state; a state is never raised here without the
run report that carries the evidence.

<!-- status_assertions:begin -->
```json
{
  "schema": "coprepan-status-assertions/v1",
  "as_of": "2026-10-09",
  "production_pipeline_exists": false,
  "external_api_in_production_path": false,
  "git_initialised_by_bootstrap": false,
  "stages": {
    "outlet_registry":       {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "discovery":             {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "fetch":                 {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "raw_preservation":      {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "document_identity":     {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "extraction":            {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "admission_labels":      {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "normalisation":         {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "nlp":                   {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "enrichment":            {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "release":               {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "cross_corpus_contract": {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"}
  },
  "open_production_gates": ["O-1", "O-3", "O-4", "O-11", "O-12", "PHASE_1_CORE", "PHASE_2_CANARY"]
}
```
<!-- status_assertions:end -->

## 8. History

- 2026-10-06 — repository bootstrap: foundation documents, naming module, tests. No pipeline.
  Run report: [`docs/agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md`](agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md).
- 2026-10-07 — repository and path migration (infrastructure only; no stage state changed). The
  legacy repository and the studies repository were archived unchanged; the rename of this
  repository to its new place is handed to the operator. Git is still not initialised.
  Run report: [`docs/agent-runs/2026-10-07_repository-and-path-migration.md`](agent-runs/2026-10-07_repository-and-path-migration.md).
- 2026-10-07 — migration closure (infrastructure only; no stage state changed). The operator
  renamed this repository to `C:\dev\panhispanic_media_corpora\coprepan`; the suite was confirmed
  from the new place; git was initialised (`main`) with the foundation as its first commit and
  `origin` set to `https://github.com/FTacke/coprepan.git`. This entry supersedes the two
  "handed to the operator" / "not initialised" statements of the entry above.
  Run report: [`docs/agent-runs/2026-10-07_coprepan-repository-migration-closure.md`](agent-runs/2026-10-07_coprepan-repository-migration-closure.md).
- 2026-10-07 — Foundation Core I (implementation; reproducibility / infrastructure integrity
  only). Id serialisation and canonical URL key frozen (CPD-0003); outlet registry schema;
  ledger and state machine; fail-closed root resolution, promotion and outage spool; write-once
  layer store. Stages 1, 4 and 5 move to `PARTIAL`. **Not done: the legacy import was built but not
  run on the legacy database**, so the registry is empty and no legacy-name mapping exists. No
  validation, no activation, no gate closed.
  Run report: [`docs/agent-runs/2026-10-07_foundation-core-i.md`](agent-runs/2026-10-07_foundation-core-i.md).
- 2026-10-07 — foundation, architecture and core-pipeline run (implementation; reproducibility and
  robustness only). Foundation Core I closed: the legacy import ran on a copy of the legacy
  database (82 proposed outlets, 352 proposed channels, nothing registered) and CPD-0003 was
  reviewed (kept). This supersedes the "not run" statement of the entry above. Legacy archaeology
  recorded; CPD-0004 (legacy dispositions) and CPD-0005 (core pipeline contracts) decided.
  Implemented on recorded exchanges: acquisition run, fetch record, sealed pack, raw preservation
  wiring, document identity, extraction contract with a baseline extractor, replay; vertical
  canary on synthetic fixtures. Stage 6 moves to `PARTIAL`. No network code, no registered outlet,
  no validation, no activation, no gate closed; one gate added (registry review).
  Run report: [`docs/agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md`](agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md).
- 2026-10-07 — discovery and acquisition-readiness run (implementation; reproducibility and
  robustness only). CPD-0004 and CPD-0005 audited; CPD-0005 amended forward-only by CPD-0006
  (fetch kind, the stored body, observation keys). Built and tested offline: discovery, HTTP
  fetcher, policy gate, robots evidence, crawler identity, HTTP acquisition run with request log,
  preservation-target readiness check, capacity model, acquisition baseline manifest, registry
  review package; the complete offline canary with failure injection against a loopback server;
  packs read by warcio 1.7.5. Stages 2 and 3 move to `PARTIAL`. **No external request was made and
  none can be made as committed.** No outlet registered, no policy decided, no target chosen, no
  validation, no activation, no gate passed. Gate O-12 (acquisition baseline freeze) added; the
  gate named `REGISTRY_REVIEW` in the previous entry is O-11.
  Run report: [`docs/agent-runs/2026-10-07_discovery-acquisition-readiness-offline-e2e.md`](agent-runs/2026-10-07_discovery-acquisition-readiness-offline-e2e.md).
- 2026-10-07 — pre-canary completion run (implementation; reproducibility and robustness only).
  **O-10 `PASS`**: on operator go-ahead the legacy freeze manifest `coprepan-legacy-2026-06` was
  built read-only and re-verified (32,235 files, 18,782,593,808 bytes; legacy tree unchanged); the
  frozen release itself stays open on O-3. Decided (CPD-0007) and built offline: candidate
  qualification, candidate lifecycle and fetch plan, conditional requests, permanent-redirect
  handling, robots sitemaps and crawl-delay evidence, channel health, technical admission labels,
  extractor lifecycle, the extraction evaluation harness with review package, a gold-sample design,
  an extractor-candidate list, the canary planner and preflight. Stage 7 moves to `PARTIAL`. A
  fourth refusal exists: the schedule policy is `NOT_DECIDED` (part of O-1). **No external request
  was made and none can be made as committed.** No outlet registered, no policy decided, no target
  chosen, no gold created, no extractor adopted, no validation, no activation.
  Run report: [`docs/agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md`](agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md).
- 2026-10-07 — Phase-3 and cross-corpus analysis contract run (decision + implementation of a
  prototype; reproducibility and robustness only). CO.RA.PAN 3.0 and the studies repository read
  read-only. Decided for COPREPAN's side (CPD-0008): the analysis contract
  `crosscorpus-analysis/v1`, the shared field `production_mode`, five value states, the token
  denominator, release and manifest semantics, the compatibility view, and the order and
  boundaries of COPREPAN's text layers. Built: validator, adapter, two synthetic fixtures. Stage 12
  moves to `PARTIAL`. **O-6 is not closed**: `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN`.
  Nothing changed in CO.RA.PAN. No corpus material, no annotation by an instrument, no gold, no
  validation, no activation. Finding on record: the finished studies compared `tense-v3` press
  labels with `tense-v4` radio labels; their equivalence was never tested.
  Run report: [`docs/agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md`](agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md).
- 2026-10-08 — adversarial persistence, crash-recovery and concurrency audit (diagnosis + repair;
  robustness and reproducibility only). Measured with real processes on the code of the previous
  run: two writers silently lost ledger and table records (389 of 600; 597 of 900 on disk);
  different contents were both "promoted" under one identity; conflicting layer answers left every
  slot unreadable; four interruption states had no way on; one lost a relation for good. Repaired
  (CPD-0009): an enforced writer lock per workspace, serialised and read-back appends, a chained
  ledger record (`v2`), exclusive binding on the preservation root, a layer store that keeps one
  answer, atomic run records, re-derived relations, reconciliation of the ledger from a verified
  pack, `recovery.diagnose` / `repair`, a 304 believed only for a preserved body. 90 tests added,
  40 of them with real process kills or real concurrent processes. `PRE_CANARY_ROBUSTNESS = PASS`
  for that scope. **No gate closed**; no external request; nothing validated scientifically.
  Run report: [`docs/agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md`](agent-runs/2026-10-08_adversarial-persistence-crash-recovery-concurrency.md).
- 2026-10-08 — evidence-table integrity closure (implementation; robustness and reproducibility
  only). Decided (CPD-0010): primary evidence is chained, derived state is rebuildable. Measured
  before: of 40 single-bit changes per file, 39–40 were not noticed in the request log, discovery
  inputs, events and candidates, qualifications and labels, and 4–22 in the identity tables. Now:
  chained request log, discovery inputs and events, qualifications and labels (row schemas `v2`);
  heads of all chained tables and the ledger recorded when a run closes (run result `v2`); the
  candidate table checked against its evidence and completable; the identity tables rebuilt from
  preserved packs and compared, with the four statuses of CPD-0010 §5. After: 0 of 40 not noticed
  in every table except the labels (7 of 40, all in the last row, written after the run closed).
  A run now refuses to start on a request log or discovery table that does not authenticate.
  `PRE_CANARY_EVIDENCE_INTEGRITY = PASS`. **No gate closed**; no external request; nothing
  validated scientifically.
  Run report: [`docs/agent-runs/2026-10-08_evidence-table-integrity-closure.md`](agent-runs/2026-10-08_evidence-table-integrity-closure.md).
- 2026-10-08 — second, independent implementation of the joint release contract
  `crosscorpus-release/v1` (implementation + decision; reproducibility, robustness and independent
  technical conformance only). CO.RA.PAN read read-only; its bundle taken verbatim and pinned
  (digest `4fb72acf…dbbe0`, unchanged since its commit `0a5f41dec`). CO.PRE.PAN's own checks
  reproduce every digest and all 52 vector cases; no contradiction found in the bundle; four
  readings that differ beyond the vectors recorded as proposals. Decided: the native export object
  `coprepan-export/v1` (CPD-0011); local adoption, study pin semantics amending CPD-0008 §7, and a
  recommendation on Q1 that is not a joint decision (CPD-0012). Stage 11 moves to `PARTIAL`.
  **The joint contract is not frozen; no release was built; nothing changed in CO.RA.PAN.** No gate
  closed; no external request; nothing validated scientifically.
  Run report: [`docs/agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md`](agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md).
- 2026-10-08 — gate closure towards the real canary, as far as it does not need the operator
  (decision + implementation; technical gate evidence only). The release-contract run was pushed.
  **O-11, canary subset `PASS`**: five routine outlets registered, each by a registration record
  with its evidence (CPD-0013); 77 stay proposed. **O-1 `PASS` for the canary scope**: the
  acquisition policy and the schedule policy of the first canary are decided; `Crawl-delay` can
  now bind as a minimum pause (policy schema `v2`); `external_acquisition` stays `disabled` until
  the canary is armed. **O-2 `BLOCKED` on the operator**: no crawler contact exists in the
  repository and none was invented. **O-3 `OPEN`**: no root is configured; three reachable volumes
  of different institutional kind were inventoried, none chosen. **No external request was made**
  (public web search for registry facts only; no page of an outlet was fetched). No canary, no
  capacity measurement, no Phase-3 work.
  Run report: [`docs/agent-runs/2026-10-08_registry-policy-storage-real-acquisition-canary.md`](agent-runs/2026-10-08_registry-policy-storage-real-acquisition-canary.md).
- 2026-10-08 — crawler identity, public site, storage architecture and the interim preservation
  target (decision + implementation + one deployment; reproducibility and robustness only).
  **O-2 `PASS`**: the identity of the operator's decision is configured after its contact page
  went live at `coprepan.hispanistica.com/crawler/` (static files on the existing nginx virtual
  host; the vhost, the certificate and every other site unchanged; receipt versioned). Storage
  roles aligned with CO.RA.PAN 3.0 under this repository's names, separation enforced, runtime
  and spool roots configured, **interim primary preservation root on `D:` qualified** (readiness
  `READY`; persistence, crash and concurrency suites with their temporary files on that file
  system; spool failover on the real roots). `D:` is not a backup and not the long-term target;
  the move to the new university file system is a verified copy and a switch of one variable.
  Decided: CPD-0014. **No external request to any outlet was made; no canary; the enabling switch
  of the acquisition policy is still off.**
  Run report: [`docs/agent-runs/2026-10-08_crawler-site-storage-o2-o3-interim.md`](agent-runs/2026-10-08_crawler-site-storage-o2-o3-interim.md).
- 2026-10-08 — joint storage-management contract (run from the CO.RA.PAN repository with write scope here; no stage state changed).
  `crosscorpus-storage/v1` in force in both repositories (bundle `8d17fc214076b21e47774d228e016dfe36484b29ce0ecad693456c07f9018fb3`, pinned copy here,
  CO.RA.PAN D95). Role separation is decided by the contract's function; **the outage spool is wired into the
  acquisition path** (`preserve_pack`, `drain_spooled_packs`), spool records are named per area; read-only
  status, joint-check and migration-inventory tools. The storage roots of this workstation are unchanged:
  no backup, the interim primary a sole copy holding its marker only, the institutional file system not
  configured. Decided: CPD-0015. **No external request to any outlet was made; no canary; the enabling switch
  of the acquisition policy is still off.**
  Run report: [`docs/agent-runs/2026-10-08_joint-storage-contract-and-spool-wiring.md`](agent-runs/2026-10-08_joint-storage-contract-and-spool-wiring.md).
- 2026-10-08 — canary driver, verification and measurement tools, runbook (implementation + decision;
  reproducibility and robustness only). The staged driver is built and qualified offline against a
  scripted outlet (CPD-0016); the baseline manifest has a canary scope; the end-of-canary `verify`
  (read-back, fixity, replay without network, receipt re-derived from evidence) and the O-4 `measure`
  exist; a review codebook for the Phase-3 gold is drafted. **The arming step was refused by the
  permission layer of the session and is left to a person; no baseline is frozen, no request was made,
  the switch is off, no O-4 measurement exists.** Run report: [`docs/agent-runs/2026-10-08_canary-driver-and-arming-prepared.md`](agent-runs/2026-10-08_canary-driver-and-arming-prepared.md).
- 2026-10-08 — research-TDM acquisition policy (decision + implementation; reproducibility and robustness
  only). Robots evidence, research-TDM eligibility and the acquisition decision are three layers
  (CPD-0017): a `Disallow` is recorded and overridden only as `ALLOW_RESEARCH_OVERRIDE` with its
  provenance; technical access controls are classified, never worked around, and hold the origin; opt-out
  and legal hold stop a source for a person. The primary sources read and the limits of that reading are in
  the decision. The public crawler page says so and was redeployed. **Not legal advice, not reviewed by a
  legal office, no claim of RFC 9309 conformance.** Run report: [`docs/agent-runs/2026-10-08_research-tdm-acquisition-policy.md`](agent-runs/2026-10-08_research-tdm-acquisition-policy.md).
  In the same run the arming was attempted under the operator's explicit authorisation: the edit of the
  switch was accepted, the test run on the armed tree was **refused by the permission layer**; the edit
  was taken back. **No baseline is frozen, no request was made to any publisher, no O-4 measurement and
  no Phase-3 package exist.** Reports:
  [`docs/agent-runs/2026-10-08_real-acquisition-canary-o4.md`](agent-runs/2026-10-08_real-acquisition-canary-o4.md),
  [`docs/agent-runs/2026-10-08_phase3-real-extraction-review-package.md`](agent-runs/2026-10-08_phase3-real-extraction-review-package.md).
- 2026-10-08 — authorised canary, third attempt (no state changed). On the operator's explicit authorisation
  the arming edit was attempted again and **refused by the permission layer at the edit itself**; not worked
  around. The switch is `disabled`, no baseline is frozen, no request was made to any publisher, no O-4
  measurement and no Phase-3 package exist. Run report:
  [`docs/agent-runs/2026-10-08_canary-arming-refused-third-attempt.md`](agent-runs/2026-10-08_canary-arming-refused-third-attempt.md).
- 2026-10-08 — the operator armed (`1f59e01`) and froze a first baseline; the preflight refused it ("does not match
  its own digest"). Diagnosis: the digest covered `state`, which a freeze changes — no frozen manifest could ever
  verify; the artefact was correct. Repaired with regression tests (`15ec1fd`, the new pinned commit), a second
  baseline frozen on it (`96c271e3…`), preflight `READY`. The driver's `run` command was refused to the agent by the
  permission layer; no request was made in that run. Run report:
  [`docs/agent-runs/2026-10-08_baseline-digest-repair-real-canary-o4-phase3.md`](agent-runs/2026-10-08_baseline-digest-repair-real-canary-o4-phase3.md).
  That entry and the two before it are superseded in one point by the next: the canary has since run.
- 2026-10-08 — **the first real canary** (started by the operator) evaluated: 27 requests, 24 answers preserved
  and verified, 13 article pages — all of one outlet; `PARTIAL`. Findings F1–F6 (§5a) reported, not repaired. O-4
  measured for the first time, still `OPEN`. **`external_acquisition` set back to `disabled`** (`4cb4ea1`). Three
  classical extractor candidates selected, pinned and wrapped (CPD-0018); a pilot review package built on the thirteen
  preserved pages; `PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY`; no gold. No stage state changed. Run report:
  [`docs/agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md`](agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md).

- 2026-10-09 — integrated discovery, source-recovery and acquisition-qualification run (diagnosis + implementation; reproducibility
  and robustness only; **no request to any publisher**). The legacy import was audited against a copy of the legacy database: complete,
  no discrepancy; legacy classes per channel and outlet with their rules. Passive prediscovery for all 82 outlets; a versioned
  source-discovery inventory with six analytic flags (1 `ACQUISITION_VERIFIED`, 2 `QUALIFIED`, 5 `REGISTERED`, 0 stable). The findings
  F1–F7 of the first canary repaired with regression tests and replayed on the preserved answers (CPD-0019): `robots-parser/3`,
  `access-control/2`, `channel-parser/2`, `canary-driver/3`. Policy `canary/2026-10-09.1` (one more disabled channel; the switch
  `disabled`). A second canary prepared; an extended canary of twelve outlets as a registration proposal. The permission refusals of
  2026-10-08 were diagnosed: all were the arming chain, none a file or configuration fault. No stage state changed; no gate closed.
  Run report: [`docs/agent-runs/2026-10-09_discovery-source-recovery-and-acquisition-qualification.md`](agent-runs/2026-10-09_discovery-source-recovery-and-acquisition-qualification.md).

- 2026-10-09 (later) — second canary: **not run; stopped at the operator's gate** (arming, §1 of the runbook, and the freeze of the
  baseline are a person's acts). No request to any publisher; the switch stays `disabled`. In the same run the proposal of the
  extended canary was reviewed: 8 of 12 outlets `READY_FOR_REGISTRATION_REVIEW` (recommended first wave of six countries), 3
  `NEEDS_VERIFICATION`, 1 `DEFER` (`config/registry_review/extended_canary_review_2026-10-09.json`; a recommendation, nothing
  registered). No stage state changed. Run report: [`docs/agent-runs/2026-10-09_second-real-canary-and-extended-readiness.md`](agent-runs/2026-10-09_second-real-canary-and-extended-readiness.md).

- 2026-10-09 (third run of the day) — integrated source expansion (consolidation + implementation; reproducibility and robustness only;
  **no request to any publisher, no canary**: the arming is the operator's). The operator's research supplement of 19 entries classified against
  the registry, the 301 channel hypotheses and the 60 proposals (1 identical, 4 additional evidence, 1 new channel, 10 already proposed, 3 new
  outlets). CPD-0020: candidate budget newest-first (and the F7 reading of CPD-0019 corrected), paginated and dated HTML listings whose
  candidates wait for a rule, incremental index reading, outlets new to the registry, the operator's one-command workflow. A third wave of nine
  new outlets proposed. `channel-parser/3`, `candidate-filter-generic/2`, `canary-driver/4`. No stage state changed; no gate closed.
  Run report: [`docs/agent-runs/2026-10-09_integrated-source-expansion-and-acquisition-qualification.md`](agent-runs/2026-10-09_integrated-source-expansion-and-acquisition-qualification.md).

- 2026-10-09 (fourth run of the day) — three-wave qualification: **prepared and stopped at the operator's gate; no request, no canary, nothing
  registered**. The operator's wrapper was reviewed on its error paths and ten defects repaired (CPD-0021); the three waves are laid out as
  one decision sheet. Still one outlet with verified acquisition. Run report: [`docs/agent-runs/2026-10-09_three-wave-qualification-prepared.md`](agent-runs/2026-10-09_three-wave-qualification-prepared.md).

- 2026-10-09 (fifth run of the day) — **the operator started the second canary by hand; it stopped after the tests on the arming commit and
  disarmed itself** (`17cde55` armed, `fb912a1` disarmed, six minutes; no baseline, no request). Cause, reproduced: 22 tests written on
  2026-10-09 copied the tracked policy and assumed its switch was `disabled`; on the arming commit it is not. Repaired; the suite passes in
  both states of the switch again. The disarming of the tool worked on its first real use (file, `HEAD`, remote read back). A hook now refuses
  heredocs mechanically (AGENTS §5). **Delegated operator authorisation was decided by the operator as a direction (CPD-0022) and not built**:
  the permission layer of the agent's session refused it, and it was not worked around. Still one outlet with verified acquisition; no
  request since 2026-10-08. Run report: [`docs/agent-runs/2026-10-09_delegation-blocked-and-manual-canary-diagnosed.md`](agent-runs/2026-10-09_delegation-blocked-and-manual-canary-diagnosed.md).

- 2026-10-09 (sixth run of the day) — **real acquisition in four canaries; the delegated operator mode built and used** (CPD-0023, CPD-0024).
  The operator's interactive second canary completed; waves B, C1 and C2 were armed and frozen by the commissioned agent under versioned
  authorisation records, with no typed confirmation. 163 item pages preserved, verified and replayed; outlets with verified acquisition
  1 → 14, countries 1 → 11; 17 outlets registered (22 in all). Four defects of this project found on real servers and repaired (F8, F9, F10,
  F14), two recorded and open (F11, F12); four origins held. One interrupted start left two unrecorded requests. The switch is `disabled`.
  Run report: [`docs/agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md`](agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md).
