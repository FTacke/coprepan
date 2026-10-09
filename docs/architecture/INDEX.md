# Architecture Index — which document is authoritative

**Purpose.** Answer one question: *which document is authoritative for X, right now?* This index
is the only map of authority in the repository. A document appears in exactly one of §1–§3, §5,
§6.

**How authority is determined.** By the decision that governs a document and by the status line in
its header — never by its age, its length or its file name.

**Reading order.** [`AGENTS.md`](../../AGENTS.md) → [`docs/STATUS.md`](../STATUS.md) → this index →
the document for your area → the decisions it cites.

**Nothing listed here is implemented** unless `docs/STATUS.md` says so. "Normative target" means:
this is what is to be built and what work is measured against; it does not mean it exists.

---

## 0. Component entry points

One entry point per subsystem. A component index holds the current rules, state and navigation of
its area.

| Subsystem | Entry point | Implementation state |
|---|---|---|
| Storage, preservation, provenance | [`docs/storage/INDEX.md`](../storage/INDEX.md) | root resolution, promotion, spool, ledger, layer store; packs promoted in tests only; no configured root |
| Corpus supply (registry attributes, cohorts, targets, monitoring) | [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md) | registry schema; 82 outlets *proposed* by the legacy import; none registered |
| Identity (id serialisation, canonical URL key, identity tables) | [`docs/identity/INDEX.md`](../identity/INDEX.md) | serialisation, URL key, document and version assignment — on recorded exchanges only |
| Acquisition (run, discovery, fetcher, policy gate, crawler identity, fetch record, pack) | [`docs/acquisition/INDEX.md`](../acquisition/INDEX.md) | built and tested offline (loopback server, synthetic documents), including re-fetching; externally not activatable as committed |
| Extraction (record, blocks, metadata, replay) | [`docs/extraction/INDEX.md`](../extraction/INDEX.md) | contract, a baseline extractor (`EXPERIMENTAL`), an evaluation harness and a gold-sample design; no gold; nothing validated or adopted |
| Admission labels | [`docs/admission/INDEX.md`](../admission/INDEX.md) | the technical label only, offline; no content-level label |
| NLP, enrichment, LLM policy | [`docs/nlp/INDEX.md`](../nlp/INDEX.md) | not started |
| Cross-corpus analysis contract | [`docs/crosscorpus/INDEX.md`](../crosscorpus/INDEX.md) | a technical proposal with a validator, COPREPAN's adapter and synthetic fixtures; not adopted by CO.RA.PAN |
| Release (native export object, release manifest and freeze, package, study population) | [`docs/release/INDEX.md`](../release/INDEX.md) | export object and release mechanics built and tested offline on synthetic pages; no corpus export can be built (no adopted extractor); no release exists |
| Legacy system and legacy corpus | [`docs/legacy/INDEX.md`](../legacy/INDEX.md) | rules in force; freeze manifest built and verified (O-10); no preserved copy |

Normalisation has no component index yet: until its first implementation run it is specified in the target
architecture (§1). The run that starts implementing it creates its `docs/<component>/INDEX.md`
and adds it here.

**A contract this repository does not own:** [`contracts/crosscorpus-release-v1/`](../../contracts/crosscorpus-release-v1/CONTRACT.md)
is a verbatim, digest-pinned copy of the joint release contract, whose canonical home is the
CO.RA.PAN repository. It is normative here by CPD-0012 and is never edited here.

## 1. Core — authoritative

| Document | Scope | Status | Governed by |
|---|---|---|---|
| [`AGENTS.md`](../../AGENTS.md) | agent and developer rules | NORMATIVE | — |
| [`docs/STATUS.md`](../STATUS.md) | what is planned / implemented / validated / activated; open gates | AUTHORITATIVE for the current state; self-checked by the test suite | — |
| [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) | stages, stage contracts, common rules, identity, extraction and release design | NORMATIVE TARGET — not implemented | CPD-0001 |
| [`PHASE3_SCIENTIFIC_ARCHITECTURE.md`](PHASE3_SCIENTIFIC_ARCHITECTURE.md) | order and boundaries of the text layers from extraction to the contract export; where human gold attaches | NORMATIVE TARGET — partly implemented; nothing validated | CPD-0008 |
| [`TERMINOLOGY_AND_NAMING.md`](TERMINOLOGY_AND_NAMING.md) | terms, human-facing names, identifiers, vocabularies, legacy naming | NORMATIVE | CPD-0002 |
| [`docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md`](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md) | how transformations are developed, evaluated and validated; evidence rules; forward-only evolution | NORMATIVE | CPD-0001 §8 |
| [`docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md`](../plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) | goal, scope, phases, gates, open operator and institutional decisions, next run | ACTIVE PLAN | CPD-0001, CPD-0002 |

## 2. Decisions — active

Registry and rules: [`docs/decisions/README.md`](../decisions/README.md).

| ID | Decision | Status |
|---|---|---|
| [CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) | Strategy C and the foundation principles | `ACTIVE` |
| [CPD-0002](../decisions/CPD-0002_terminology-and-naming-model.md) | Terminology and naming model | `ACTIVE` |
| [CPD-0003](../decisions/CPD-0003_id-serialisation-and-canonical-url-key.md) | Id serialisation and canonical URL key | `ACTIVE` |
| [CPD-0004](../decisions/CPD-0004_legacy-component-dispositions.md) | Legacy component dispositions | `ACTIVE` |
| [CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) | Core pipeline contracts (run, fetch record, pack, identity, extraction, layers) | `ACTIVE_WITH_VALIDATION_DEBT`; amended by CPD-0006 §1 |
| [CPD-0006](../decisions/CPD-0006_discovery-transport-policy-gate-and-readiness.md) | Discovery, HTTP transport, policy gate, crawler identity, readiness contracts | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0007](../decisions/CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md) | Legacy freeze manifest; candidate qualification; re-fetch lifecycle and plan; conditional requests; channel health; technical admission labels; extractor lifecycle; evaluation harness; canary preflight | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0008](../decisions/CPD-0008_cross-corpus-analysis-contract-and-phase3-layer-architecture.md) | Cross-corpus analysis contract (technical proposal; binds COPREPAN only) and the Phase-3 layer architecture | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0009](../decisions/CPD-0009_single-writer-recovery-and-operation-semantics.md) | One writer per workspace; recovery after interruption; operation semantics (at-least-once requests, exactly-once evidence identity); chained ledger records; exclusive binding on the preservation root | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0010](../decisions/CPD-0010_evidence-classes-chained-evidence-and-rebuildable-identity.md) | Evidence classes: chained primary evidence with anchored heads; derived candidates and identity tables checked against and rebuildable from the evidence | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0011](../decisions/CPD-0011_native-export-object-and-release-layer-mapping.md) | The native export object `coprepan-export/v1` and its mapping into a release | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0012](../decisions/CPD-0012_local-adoption-of-crosscorpus-release-v1-and-study-pin-semantics.md) | CO.PRE.PAN's adoption of the joint release contract `crosscorpus-release/v1` (binds CO.PRE.PAN only; not jointly frozen); what a study pins | `ACTIVE_WITH_VALIDATION_DEBT`; amends CPD-0008 §7 |
| [CPD-0013](../decisions/CPD-0013_canary-registration-and-canary-acquisition-policy.md) | Registration by record and the canary subset (O-11); acquisition and schedule policy of the first real canary (O-1); `Crawl-delay` may bind (policy schema `v2`) | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0014](../decisions/CPD-0014_crawler-identity-and-storage-roles-with-interim-preservation.md) | Crawler identity and its public page (O-2); storage roles shared with CO.RA.PAN, role separation, interim primary preservation root, planned move to the university file system | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0015](../decisions/CPD-0015_joint-storage-contract-and-outage-spool-in-the-acquisition-path.md) | Joint storage-management contract `crosscorpus-storage/v1` in force (pinned copy, own implementation, shared cases); the outage spool wired into the acquisition path | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0016](../decisions/CPD-0016_canary-driver-budgets-and-canary-baseline.md) | The staged canary driver, budgets of real requests, the canary-scope baseline, the arming protocol | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0017](../decisions/CPD-0017_scientific-tdm-acquisition-and-robots-policy.md) | Scientific TDM acquisition and robots policy: three layers, the research override, access controls that end a path | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0018](../decisions/CPD-0018_classical-extractor-candidates-of-the-first-comparison.md) | The classical extractor candidates of the first comparison, their pins (extra `phase3`, not a runtime dependency) and wrappers | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0019](../decisions/CPD-0019_canary-findings-repair-budget-reservation-and-source-discovery-inventory.md) | Repair of the first canary's findings F1–F7; hop-wise budgets with a part reserved for index expansion; the source-discovery inventory and its analytic flags; second and extended canary | `ACTIVE_WITH_VALIDATION_DEBT`; amends CPD-0016 §1–§2 |
| [CPD-0020](../decisions/CPD-0020_candidate-budget-order-listings-new-outlets-and-operator-workflow.md) | Candidate budget newest-first; HTML listings (pagination, dates, waiting candidates); an index read incrementally; outlets new to the registry; the consolidated qualification overview; the operator's canary workflow | `ACTIVE_WITH_VALIDATION_DEBT`; amends CPD-0019 §7, §9 |
| [CPD-0021](../decisions/CPD-0021_operator-workflow-hardening.md) | The operator's canary workflow after its review: scope shown before `ARM`, disarming read back from file, HEAD and remote, `--disarm-only`, an incomplete run keeps its evidence | `ACTIVE_WITH_VALIDATION_DEBT`; amends CPD-0020 §7 |
| [CPD-0022](../decisions/CPD-0022_delegated-operator-authorisation.md) | Delegated operator authorisation: a direction with a design; the history of the refusal | `SUPERSEDED` by CPD-0023 |
| [CPD-0023](../decisions/CPD-0023_delegated-operator-authorisation-in-force.md) | Delegated operator authorisation in force: the authorisation record (`config/operator_authorizations/`), `src/coprepan/delegation.py`, the delegated mode of `scripts/canary_operator.py`; the interactive mode unchanged | `ACTIVE_WITH_VALIDATION_DEBT` |
| [CPD-0024](../decisions/CPD-0024_wave-limits-cap-the-canary-budget.md) | A wave's limits cap the canary budget; a canary under a wave may be one to fifteen outlets | `ACTIVE_WITH_VALIDATION_DEBT` |

## 3. Component specifications — active

The component indexes of §0. Each is authoritative for its own area, under the core documents and
the decisions above.

Machine-checked contracts:

| Contract | Code | Test |
|---|---|---|
| Lexical naming rules | `src/coprepan/naming.py` | `tests/test_naming.py` |
| Stage list and status vocabulary; `docs/STATUS.md` assertions | `src/coprepan/stages.py` | `tests/test_repository_contract.py` |
| No absolute path in tracked logic/config; decision registry consistency; fixture size; suite membership | — | `tests/test_repository_contract.py` |
| No network and no storage root in tests | `tests/conftest.py` | `tests/test_test_guards.py` |
| Logical storage targets and fail-closed root resolution | `config/storage_targets.yml`, `src/coprepan/storage_roots.py` | `tests/test_repository_contract.py`, `tests/test_storage_roots.py` |
| Id serialisation and canonical URL key (CPD-0003) | `src/coprepan/identity.py`, `src/coprepan/canonical.py` | `tests/test_identity.py` |
| Outlet registry schema `coprepan-outlet-registry/v1`; legacy import | `config/outlet_registry.json`, `src/coprepan/registry.py`, `src/coprepan/legacy_registry_import.py`, `config/legacy_country_codes.json` | `tests/test_registry.py` |
| State machine and ledger (ledger before state) | `src/coprepan/ledger.py` | `tests/test_ledger.py` |
| Promotion semantics, no deletion path, outage spool | `src/coprepan/preservation.py`, `src/coprepan/outage_spool.py` | `tests/test_preservation.py` |
| Write-once layer store (fingerprint, artifact id) | `src/coprepan/layer_store.py` | `tests/test_layer_store.py` |
| Acquisition run and fetch record (CPD-0005 §2–§3) | `src/coprepan/acquisition.py` | `tests/test_acquisition_pack.py` |
| Sealed WARC pack with derived, bound index | `src/coprepan/pack.py` | `tests/test_acquisition_pack.py` |
| Document identity tables and relations (CPD-0005 §4) | `src/coprepan/document_identity.py`, `src/coprepan/jsonl.py` | `tests/test_core_pipeline.py` |
| Extraction record; baseline extractor (CPD-0005 §5) | `src/coprepan/extraction.py` | `tests/test_extraction.py` |
| Stage order and gates of the core section; replay | `src/coprepan/core_pipeline.py` | `tests/test_core_pipeline.py` |
| No deletion call outside the six named places, over every module | — | `tests/test_preservation.py` |
| Discovery: parsers, events, candidates, budgets (CPD-0006 §2) | `src/coprepan/discovery.py` | `tests/test_discovery.py` |
| Policy gate: nothing allowed by default; the tracked canary policy is decided and denies everything until armed; a binding `Crawl-delay` | `src/coprepan/policy.py`, `config/acquisition_policy.json` | `tests/test_policy.py`, `tests/test_fetcher.py` |
| Every registered outlet has a registration record and agrees with it | `config/outlet_registry.json`, `config/registry_review/*_registration_*.json` | `tests/test_registry.py` |
| Robots evidence (RFC 9309 parser) | `src/coprepan/robots.py` | `tests/test_policy.py` |
| Crawler identity: no default, placeholders refused | `src/coprepan/crawler_identity.py`, `config/crawler_identity.json` | `tests/test_policy.py` |
| HTTP transport: limits, redirects, retries, policy before transport | `src/coprepan/fetcher.py` | `tests/test_fetcher.py` |
| HTTP acquisition run and request log; the complete offline canary | `src/coprepan/http_acquisition.py` | `tests/test_offline_e2e.py` |
| Pack interoperability with an independent reader (warcio 1.7.5) | `src/coprepan/pack.py` | `tests/test_warc_interoperability.py` |
| Preservation-target readiness; capacity model; baseline manifest (`PRE_FREEZE` as committed) | `src/coprepan/preservation_target.py`, `capacity.py`, `freeze.py` | `tests/test_readiness.py` |
| Registry review package equals what the generator produces from the tracked registry | `src/coprepan/registry_review.py`, `config/registry_review/outlet_review_package.json`, `docs/corpus_supply/REGISTRY_REVIEW_PACKAGE.md` | `tests/test_readiness.py` |
| Tests reach at most a literal loopback address | `tests/conftest.py` | `tests/test_test_guards.py` |
| Tracked registry proposal agrees with its review report; nothing registered | `config/outlet_registry.json`, `config/registry_review/` | `tests/test_registry.py` |
| Legacy freeze manifest: builder, verifier; the tracked manifest is self-consistent | `src/coprepan/legacy_freeze.py`, `docs/legacy/freeze/coprepan-legacy-2026-06/` | `tests/test_legacy_freeze.py` |
| Candidate qualification; candidate lifecycle and fetch plan; the tracked schedule policy plans nothing | `src/coprepan/candidate_filter.py`, `src/coprepan/schedule.py`, `config/candidate_rules.json`, `config/schedule_policy.json` | `tests/test_schedule.py` |
| Channel health as a derived report | `src/coprepan/channel_health.py` | `tests/test_schedule.py` |
| Conditional requests, permanent redirects, robots sitemaps, re-fetching end to end | `src/coprepan/fetcher.py`, `src/coprepan/http_acquisition.py` | `tests/test_refetch_e2e.py` |
| Technical admission labels; extractor lifecycle; evaluation harness and review package | `src/coprepan/admission.py`, `src/coprepan/extraction.py`, `src/coprepan/extraction_eval.py` | `tests/test_admission_eval.py` |
| Wrappers of the classical extractor candidates (CPD-0018): pins equal the extra, refusal without the pinned tool; with the tools: record shape, determinism, blinding | `src/coprepan/extractor_candidates.py`, `scripts/phase3_review_package.py` | `tests/test_extractor_candidates.py` (tool tests skipped outside the `phase3` environment) |
| Canary planner and fail-closed preflight (`NOT_READY` as committed) | `src/coprepan/canary.py` | `tests/test_canary.py` |
| One writer per workspace; diagnosis and repair after an interruption | `src/coprepan/exclusive.py`, `src/coprepan/recovery.py` | `tests/test_crash_recovery.py` (real process kills) |
| Concurrent writers: no lost record, no double binding, no two layer answers | `src/coprepan/jsonl.py`, `ledger.py`, `preservation.py`, `layer_store.py` | `tests/test_concurrency.py` (real processes) |
| Chained primary evidence (request log, discovery inputs and events, qualifications, labels); heads at run close; candidates and identity tables derived and rebuildable | `src/coprepan/jsonl.py`, `evidence.py`, `identity_rebuild.py`, `recovery.py` | `tests/test_evidence_integrity.py` |
| No false success: preserved, sealed, promoted, version, 304 and replay refuse when what they claim is broken | `src/coprepan/core_pipeline.py`, `recovery.py` | `tests/test_integrity_invariants.py` |
| Cross-corpus analysis contract: schemas, value states, denominator, manifest, compatibility view; conformance of a press and a radio fixture; invalid bundles refused | `src/coprepan/analysis_contract.py`, `src/coprepan/analysis_export.py` | `tests/test_analysis_contract.py` |
| Joint release contract `crosscorpus-release/v1`: the copy is the pinned bundle; a drifted copy is refused; the bundle's digests and all vector cases reproduced by this repository's own checks | `contracts/crosscorpus-release-v1/`, `config/crosscorpus/contract_pins.json`, `src/coprepan/release_contract.py` | `tests/test_release_contract.py` |
| Native export object `coprepan-export/v1`; export → release member → manifest → freeze → package → study population; no corpus export without an adopted extractor | `src/coprepan/release_export.py` | `tests/test_release_export.py` |
| Storage roles stay apart (no shared or nested root, a backup never on the primary's volume), nothing falls back, a preservation root can be switched without a new identity | `src/coprepan/storage_roots.py`, `config/storage_targets.yml`, `.env.example` | `tests/test_storage_architecture.py`, `tests/test_storage_roots.py` |
| Crawler identity is the decided one; the public crawler page in the repository says what the identity says | `config/crawler_identity.json`, `web/coprepan/` | `tests/test_policy.py` |
| The canary driver: stages, real-request budgets, refusals, outage and interruption, receipt; end-of-canary verification and O-4 measurement | `src/coprepan/canary_driver.py`, `src/coprepan/canary_evidence.py`, [`docs/canary/RUNBOOK.md`](../canary/RUNBOOK.md) | `tests/test_canary_driver.py`, `tests/test_canary_evidence.py` |
| The findings of the first canary, each as a regression: coded robots file, the Sucuri challenge and the hold, foreign candidates, hop-wise budgets and index expansion, DOCTYPE in CDATA, the disabled 404 channel, candidate-budget coverage (CPD-0019) | `src/coprepan/robots.py`, `access_control.py`, `discovery.py`, `discovery_coverage.py`, `http_acquisition.py`, `canary_driver.py` | `tests/test_canary_findings.py` |
| The source-discovery inventory is the join of its evidence files; the registration proposal of the extended canary applies to a copy and gives a canary the driver can pin | `config/source_discovery/`, `config/registry_review/extended_canary_proposal_2026-10-09.json`, `scripts/build_source_discovery_inventory.py`, `scripts/apply_registration_proposal.py` | `tests/test_source_discovery.py` |
| Feed families, the newest-first candidate budget, paginated and dated HTML listings, incremental index reading, a listing outlet end to end — on synthetic documents (CPD-0020) | `src/coprepan/discovery.py`, `candidate_filter.py`, `http_acquisition.py`, `canary_driver.py` | `tests/test_source_structures.py` |
| The operator's workflow run against a real temporary git repository with a bare remote, a failure injected at every step: after any outcome the switch is off in the file, HEAD and remote, or the tool says so and exits 2 (CPD-0021) | `scripts/canary_operator.py` | `tests/test_canary_operator.py` |
| The qualification overview is the join of its inputs; an outlet new to the registry enters only by an applied proposal and never by collision; the operator's workflow accepts a confirmation from a terminal only | `config/source_discovery/source_qualification_overview_*.json`, `config/registry_review/wave_c_proposal_2026-10-09.json`, `scripts/consolidate_source_discovery.py`, `scripts/apply_registration_proposal.py`, `scripts/canary_operator.py` | `tests/test_source_expansion.py` |
| No heredoc or here-string in a shell command (AGENTS §5), enforced by a hook | `scripts/hooks/block_heredocs.py`, `.claude/settings.json` | `tests/test_block_heredocs_hook.py` |
| The research-TDM layer of the policy gate; access controls as observed evidence | `src/coprepan/policy.py`, `src/coprepan/access_control.py`, `src/coprepan/fetcher.py` | `tests/test_research_tdm_policy.py` |

## 4. Open decisions and gates

| Register | Scope |
|---|---|
| Master plan §13 (O-1 … O-12) | operator and institutional decisions |
| `docs/STATUS.md` §5 | gates blocking production crawling |
| "Open" section of each component index | technical and scientific open points of that area |
| "Not decided here" of each decision | what a decision deliberately left open |

Nothing in these registers is a defect. They are the honest boundary of what is known.

## 5. Historical and external evidence — not normative

| Document | What it is | Standing |
|---|---|---|
| Architecture, Migration, Corpus Supply & Naming Audit, 2026-10-06 — in `corapan_playground`, `docs/agent-runs/2026-10-06_coprepan3-architecture-and-migration-audit.md` | the diagnostic run whose findings this foundation consolidates | historical evidence. Cited as "audit §n". Where it differs from a document of §1–§3, that document governs. Its measurements are of 2026-10-06 and are quoted with that date. |
| [`docs/agent-runs/`](../agent-runs/README.md) | one report per run | historical records; never specifications |
| [`docs/legacy/ARCHAEOLOGY.md`](../legacy/ARCHAEOLOGY.md) | reconstruction of the legacy system and its failure mechanisms, 2026-10-07 | historical evidence; the evidence base of CPD-0004 and CPD-0005 |
| [`config/registry_review/`](../../config/registry_review/) | review report of the legacy registry import; the generated review package | evidence of one import run and a recommendation for review; neither is a registration |
| [`config/source_discovery/`](../../config/source_discovery/), [`docs/corpus_supply/SOURCE_DISCOVERY_INVENTORY.md`](../corpus_supply/SOURCE_DISCOVERY_INVENTORY.md) | the legacy discovery audit, prediscovery research files, the replay of the first canary's answers, and the inventory that joins them (2026-10-09) | evidence and a reading aid; research entries are hypotheses; nothing in them is a registration |
| [`docs/corpus_supply/REGISTRY_REVIEW_PACKAGE.md`](../corpus_supply/REGISTRY_REVIEW_PACKAGE.md) | the review package as a page | generated; a recommendation, not normative |
| Documentation inside the legacy repository | legacy design and run notes | historical; partly describes layouts the legacy code no longer writes |
| Documents of `corapan_playground` (storage targets, retention policy, evolution policy, corpus supply, NLP index, methodology) | the CO.RA.PAN 3.0 sources that principles here were adapted from | authoritative *for CO.RA.PAN 3.0*. Here: reference. A rule binds this repository only where a document of §1–§3 states it. |

## 6. Proposals — non-normative

None. A proposal document carries `STATUS: PROPOSAL / OPEN` in its header and is listed here until
a decision adopts or rejects it.

## 7. Maintaining this index

- A new authoritative document is added here in the run that creates it; a new decision is added
  to §2 and to the decision registry in the same run.
- A document appears in exactly one of §1–§3, §5, §6. When a document is superseded it moves to §5
  with a pointer to its successor; its text is kept and gets a supersession notice in its header.
- A conflict between two authoritative documents is recorded and raised, not resolved by picking
  one.
- Do not add a second authoritative document for a topic that already has one.
