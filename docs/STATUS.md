# COPREPAN 3.0 — Current Status

**This is the one place that says what actually exists.** Every other document describes a target,
a rule or a plan. If a document sounds as if something were built, and this file says it is not,
this file is right and the other document has a defect.

**As of 2026-10-07 (pre-canary completion run): the acquisition pipeline, including re-fetching,
is built and tested offline, and it is not activated.** Nothing has been requested from any real
site. No outlet is registered. No storage root is configured. No corpus material has been
acquired, preserved or extracted by COPREPAN 3.0. Nothing is validated. Nothing is activated.

**External acquisition is impossible as committed**, by four independent, tested refusals: the
acquisition policy is `NOT_DECIDED`, the schedule policy is `NOT_DECIDED`, the crawler identity is
`not_configured`, and no outlet is `registered`. Removing them is the operator's act, not an
agent's (§5).

**One thing was done on real data: the legacy freeze manifest** (O-10, on operator go-ahead):
32,235 files, 18,782,593,808 bytes of the legacy tree, hashed read-only and re-verified (measured).
It is a manifest, not a preserved copy.

What exists beyond documents: the complete path channel → discovery → candidate → policy gate →
HTTP fetch → fetch record → sealed pack → preservation → document identity → extraction →
document version → admission label → replay, and a second and later visit of the same candidates
(schedule, conditional request, moved URL), exercised end to end **against an HTTP server on a
loopback address serving synthetic documents, on temporary directories** (§3). It has never seen a real outlet, a
real page, a TLS connection or a real storage root.

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
| 11 | release | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 12 | cross-corpus contract | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |

What `PARTIAL` means for the seven stages, exactly:

| Stage | Exists | Does not exist |
|---|---|---|
| outlet registry | schema `coprepan-outlet-registry/v1`, validator, lookup; the legacy import, executed on a copy of the legacy database: **82 proposed outlets, 352 proposed channels**; a generated review package with a uniform id convention | **any registered outlet**; any attribute beyond what the legacy database held (type, group, time zone, URL rules); the human review |
| discovery | parsers for RSS, Atom, sitemap `urlset`, sitemap index, HTML listing; discovery events and candidates as append-only evidence; bounded expansion with cycle handling — candidate qualification with versioned rules; robots sitemaps as an optional source; channel health as a derived report — on synthetic channel documents | anything read from a real outlet; any outlet rule; decided health thresholds |
| fetch | HTTP transport (`http.client`): redirects, limits, explicit retries, `Retry-After`, pacing; policy gate in front of every request; robots evidence; crawler identity; request log; candidate lifecycle and fetch plan; conditional requests; permanent-redirect handling — against a loopback server | **any external request**; a decided schedule; TLS exercised; concurrency; behaviour against real servers and bot protection |
| raw preservation | fetch record; WARC pack writer, seal, derived and bound index, fixity check, torn-tail quarantine; state machine and ledger; fail-closed root resolution; promotion; outage spool; a preservation-target readiness check; packs read by an independent WARC reader (warcio 1.7.5, written subset) — on temporary directories | scheduled fixity, reconciliation, backup; a chosen, configured target; a run against one |
| document identity | id serialisation and canonical URL key (CPD-0003); document and version assignment, append-only identity tables, collision refusal, `duplicate_of` and `moved_to` relations (CPD-0005 §4) — on recorded exchanges | syndication clusters; URL-key aliases after a rule change; a durable home for the tables; any id minted for corpus material |
| extraction | the extraction record and its digests; storage by fingerprint; replay from the preservation root; a **baseline** extractor (`baseline_html/0.1.0`, lifecycle `EXPERIMENTAL`); an evaluation harness and review-package generator; a gold-sample design | an adopted extractor; a gold sample; any quality measurement; per-outlet rules; date parsing |
| admission labels | the technical label (`coprepan-admission-label/v1`, rule set `admission-technical/1`): usable / unusable with reasons and evidence, append-only | every content-level label: article / not article, access class, language from content, length, type; any label on corpus material |

`PARTIAL` for stages 2, 3 and 7 means "code and tests exist, offline". It is not a step towards
`ACTIVE`: activation needs validation on real material and the operator decisions of §5.

## 3. Foundation

| Item | State | Where |
|---|---|---|
| Agent instructions | in place | `AGENTS.md`, `CLAUDE.md` |
| Document hierarchy and authority index | in place | `docs/architecture/INDEX.md` |
| Decisions | CPD-0001 to CPD-0004 `ACTIVE`; CPD-0005, CPD-0006 and CPD-0007 `ACTIVE_WITH_VALIDATION_DEBT` (§6) | `docs/decisions/` |
| **Foundation Core I** (master plan §12 item 3) | **complete** as infrastructure: all six items implemented and tested; the legacy import executed and repeatable; CPD-0003 reviewed. Reproducibility / infrastructure integrity only | run report of 2026-10-07 (core pipeline) §2 |
| Naming contract — lexical rules for corpus, generation, provenance class, `country_id`, `outlet_id`, `release_id`, schema ids | implemented and unit-tested | `src/coprepan/naming.py`, `tests/test_naming.py` |
| Naming contract — serialisation of fetch, channel, document, version, unit, sentence, token ids; canonical URL key | implemented and unit-tested (CPD-0003); **no id minted** | `src/coprepan/identity.py`, `tests/test_identity.py`, [`docs/identity/INDEX.md`](identity/INDEX.md) |
| Outlet registry | schema, validator, lookup implemented and unit-tested; holds **82 proposed outlets, none registered** | `config/outlet_registry.json`, `src/coprepan/registry.py`, `tests/test_registry.py` |
| Legacy outlet import | executed 2026-10-07 on a copy of the legacy database; deterministic on repetition; real schema equal to the assumed one; legacy-name → `outlet_id` table produced as `hypothesis`. **Not reviewed by a human** | `src/coprepan/legacy_registry_import.py`, `config/registry_review/`, corpus supply §16 |
| Legacy archaeology and component dispositions | recorded | [`docs/legacy/ARCHAEOLOGY.md`](legacy/ARCHAEOLOGY.md), CPD-0004 |
| Acquisition run and fetch record | implemented and unit-tested; run kinds `recorded_replay` and `http_fetch` | `src/coprepan/acquisition.py`, [`docs/acquisition/INDEX.md`](acquisition/INDEX.md) |
| Sealed WARC pack | implemented and unit-tested (own writer, standard library); read by warcio 1.7.5 for the record subset it writes — **not a general conformance claim** | `src/coprepan/pack.py`, `tests/test_warc_interoperability.py`, storage §14 |
| Discovery | implemented; tested on synthetic channel documents | `src/coprepan/discovery.py`, `tests/test_discovery.py` |
| Policy gate | implemented and tested; **the tracked policy is `NOT_DECIDED` and denies everything** | `src/coprepan/policy.py`, `config/acquisition_policy.json` |
| Robots evidence | RFC 9309 parser implemented and tested; no robots file of a real site has been read | `src/coprepan/robots.py` |
| Crawler identity | contract implemented and tested; **the tracked identity is `not_configured`** | `src/coprepan/crawler_identity.py`, `config/crawler_identity.json` |
| HTTP fetcher | implemented; tested against a real HTTP server on a loopback address; **no TLS, no external request** | `src/coprepan/fetcher.py`, `tests/test_fetcher.py` |
| HTTP acquisition run, request log | implemented; tested in the offline canary | `src/coprepan/http_acquisition.py` |
| Candidate qualification | implemented and tested; generic rules only — **the tracked outlet rules are empty** | `src/coprepan/candidate_filter.py`, `config/candidate_rules.json`, `tests/test_schedule.py` |
| Candidate lifecycle and fetch plan | implemented and tested; **the tracked schedule policy is `NOT_DECIDED` and plans nothing** | `src/coprepan/schedule.py`, `config/schedule_policy.json`, `tests/test_schedule.py` |
| Conditional requests, permanent redirects, robots sitemaps, crawl-delay evidence | implemented; tested against the loopback server | `src/coprepan/fetcher.py`, `tests/test_refetch_e2e.py` |
| Channel health | implemented and tested as a derived report; thresholds undecided; switches nothing | `src/coprepan/channel_health.py` |
| Admission labels (technical) | implemented and tested on synthetic material | `src/coprepan/admission.py`, `tests/test_admission_eval.py` |
| Extraction evaluation harness, review package | implemented and tested on synthetic pages; **no gold, no real page, no result** | `src/coprepan/extraction_eval.py`, [`GOLD_SAMPLE_DESIGN.md`](extraction/GOLD_SAMPLE_DESIGN.md) |
| Canary planner and preflight | implemented and tested; on the repository as committed: 0 of 82 outlets eligible, preflight `NOT_READY` (measured) | `src/coprepan/canary.py`, `tests/test_canary.py` |
| Offline end-to-end canary with failure injection | passes: two independent passes are byte-identical; a later run adds and never rewrites | `tests/test_offline_e2e.py` |
| Preservation-target readiness check | implemented and tested on temporary directories; **no target chosen** | `src/coprepan/preservation_target.py`, storage §15 |
| Capacity model | calculator implemented; **bytes per real page never measured** | `src/coprepan/capacity.py`, storage §16 |
| Acquisition baseline manifest | implemented; the repository as committed is `PRE_FREEZE` with six blockers (O-11, O-1 twice, O-2, O-3, O-4) | `src/coprepan/freeze.py` |
| Registry review package | generated, checked against the registry by a test; **a recommendation, nothing registered** | corpus supply §17 |
| Document identity tables | implemented and tested on recorded exchanges | `src/coprepan/document_identity.py`, [`docs/identity/INDEX.md`](identity/INDEX.md) §7 |
| Extraction contract and baseline extractor | implemented; behaviour of the contract tested; **quality unknown, extractor not adopted** | `src/coprepan/extraction.py`, [`docs/extraction/INDEX.md`](extraction/INDEX.md) |
| Vertical canary (fixture → fetch record → pack → preservation → identity → extraction → version → replay) | passes on four synthetic pages, on temporary directories | `src/coprepan/core_pipeline.py`, `tests/test_core_pipeline.py` |
| State machine and ledger primitives | implemented and unit-tested | `src/coprepan/ledger.py`, `tests/test_ledger.py` |
| Stage-status self-check | implemented | `tests/test_repository_contract.py` |
| Test guards (no network, no storage root, suite membership) | implemented | `tests/conftest.py` |
| Storage-target configuration and root resolution | fail-closed resolver implemented and unit-tested; **no root configured** | `config/storage_targets.yml`, `src/coprepan/storage_roots.py`, `tests/test_storage_roots.py` |
| Promotion semantics and outage spool | implemented; tested **on temporary directories only** (first half of the Phase-1 gate) | `src/coprepan/preservation.py`, `src/coprepan/outage_spool.py`, `tests/test_preservation.py` |
| Write-once layer store | implemented and unit-tested; its durable location (role) is undecided | `src/coprepan/layer_store.py`, `tests/test_layer_store.py` |
| Release gate suite | scaffold; **contains no test** | `tests/suites/release_gate.txt` |
| Git | initialised 2026-10-07 on operator brief: branch `main`, remote `origin` = `https://github.com/FTacke/coprepan.git`; no history taken over from the legacy repository | [closure run report](agent-runs/2026-10-07_coprepan-repository-migration-closure.md) |
| Legacy freeze `coprepan-legacy-2026-06` | **manifest built and verified 2026-10-07** (`MANIFEST_ONLY`): 32,235 files, 18,782,593,808 bytes; release scope 3,256 files, 17,370,148,925 bytes (measured). **No preserved copy, no restore check** (need O-3) | `docs/legacy/freeze/coprepan-legacy-2026-06/`, `src/coprepan/legacy_freeze.py`, `docs/legacy/INDEX.md` §5 |

## 4. Production stack

None. No model, provider, crawler, extractor or annotator is active. The NLP pins in
`pyproject.toml` `[tool.coprepan.nlp]` are marked `PLANNED`: they are not installed and not used.
The package has no runtime dependency. `baseline_html/0.1.0`, `pack-writer/1`, `http-fetcher/1`,
`channel-parser/1`, `robots-parser/1`, `fetch-planner/1`, `candidate-filter-generic/1`,
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
| O-1 acquisition policy | `TECHNICALLY_READY` — the gate and the fetch planner enforce whatever is decided and deny / plan nothing until then | **`OPEN`** | the normative decision: robots mode, absent / unreachable robots, whether `Crawl-delay` binds, pace per origin, **the schedule policy (how often a page is asked again, when a failing or absent URL is left alone, whether conditional requests are used)**, opt-out handling, retention of raw copies; recorded as a decision and committed as `DECIDED` policy files | operator / institution |
| O-2 crawler identity | `TECHNICALLY_READY` — contract tested (`TECHNICAL_CONTRACT = PASS`) | **`READY_FOR_HUMAN_REVIEW`** (`EXTERNAL_ACTIVATION = BLOCKED`) | four values in `config/crawler_identity.json`: crawler name, organisation, contact URL, contact e-mail — and the public page the URL names | operator / institution |
| O-3 preservation target | `TECHNICALLY_READY` — readiness check built | **`OPEN`** | choosing the target; then `initialise_target`, a `READY` readiness report, and the second half of the Phase-1 gate on it | operator / institution |
| O-4 storage capacity | `TECHNICALLY_READY` — model built | **`OPEN`** | one measurement that does not exist: stored body bytes per fetch and fetches per outlet-day **on real outlets** (the Phase-2 canary) | measured, then operator |
| O-10 legacy freeze manifest | built, run on the legacy tree, verified twice (module and an independent script) | **`PASS`** (2026-10-07) | — closed. It closes the go-ahead and the manifest only: the frozen release still needs a preserved copy and a restore check (O-3) | operator |
| O-11 registry review | `TECHNICALLY_READY` — review package delivered | **`READY_FOR_HUMAN_REVIEW`** | the human decisions of corpus supply §17; registration by reviewed commit | operator, scientific |
| O-12 acquisition baseline freeze | `TECHNICALLY_READY` — manifest builder; state `PRE_FREEZE` | **`OPEN`** | O-1, O-2, O-3, O-4, O-11 answered; then the operator's freeze of a `READY_TO_FREEZE` manifest | operator |
| Phase-1 core gate (promotion, idempotence, conflict, crash recovery) | first half passes on temporary directories | **`OPEN`** | the same tests on the real preservation target (needs O-3) | engineering, then operator |
| Phase-2 canary gate | the offline canary passes; **it is not this gate** — it requests nothing external and measures no real page | **`OPEN`** | about five registered outlets acquired for real under a decided policy; every fetch traceable; restore test; measured bytes per fetch. `python -m coprepan.canary preflight` says whether it may start (`NOT_READY` today) | engineering, after O-1, O-2, O-3, O-11 |

Full list: [master plan](plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) §13.

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
| The policy gate under a decided policy; robots files of real sites | after O-1; Phase-2 canary |
| The identity policy on real URLs: per-outlet rules, the canonical-collapse diagnostic on real templates | Phase-2 canary |
| Promotion, idempotence, conflict and crash recovery on a real preservation target | second half of the Phase-1 gate; needs O-3 |
| The legacy importer's proposal reviewed | the registry-review gate (§5) |
| Baseline extractor against real pages; an adopted extractor | Phase 3: gold sample, preregistered comparison |
| Identity policy on real URLs (per-outlet rules; collision behaviour at scale) | Phase-2 canary |
| Process-kill crash tests (today: failures injected in-process) | Phase 1 on a real target |
| Re-fetching against real servers: real validators, real 304 behaviour, real permanent redirects, real `Retry-After` | Phase-2 canary and the runs after it; needs a decided schedule (O-1) |
| The generic candidate rules on real listings (what they reject, what they miss); any outlet rule | Phase-2 canary |
| Channel-health states on real channels; thresholds | after the canary |
| Technical admission labels on real pages; every content-level label | Phase 3 |
| The evaluation harness on real pages with a human reference; the metrics as diagnostics checked against reviewers | Phase 3, gold sample |
| Legacy freeze: preserved copy, restore check, a study loader reading the copy | Phase 0 closure; needs O-3 |

## 7. Machine-readable assertions

Consumed by `tests/test_repository_contract.py`. The test compares this block with
`src/coprepan/stages.py` and enforces the axis rules of §1. **Update this block, the tables above
and the code in the same run** as any change of state; a state is never raised here without the
run report that carries the evidence.

<!-- status_assertions:begin -->
```json
{
  "schema": "coprepan-status-assertions/v1",
  "as_of": "2026-10-07",
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
    "release":               {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "cross_corpus_contract": {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"}
  },
  "open_production_gates": ["O-1", "O-2", "O-3", "O-4", "O-11", "O-12", "PHASE_1_CORE", "PHASE_2_CANARY"]
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
