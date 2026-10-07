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
| Acquisition (run, fetch record, pack) | [`docs/acquisition/INDEX.md`](../acquisition/INDEX.md) | contracts for recorded exchanges; no discovery, no fetcher |
| Extraction (record, blocks, metadata, replay) | [`docs/extraction/INDEX.md`](../extraction/INDEX.md) | contract and a baseline extractor; nothing validated or adopted |
| NLP, enrichment, LLM policy | [`docs/nlp/INDEX.md`](../nlp/INDEX.md) | not started |
| Legacy system and legacy corpus | [`docs/legacy/INDEX.md`](../legacy/INDEX.md) | rules in force; freeze not executed |

Discovery and the live fetcher (inside acquisition), admission, normalisation and release
have no component index or no content of their own yet: until their first implementation run they are specified in the target
architecture (§1). The run that starts implementing one of them creates its `docs/<component>/INDEX.md`
and adds it here.

## 1. Core — authoritative

| Document | Scope | Status | Governed by |
|---|---|---|---|
| [`AGENTS.md`](../../AGENTS.md) | agent and developer rules | NORMATIVE | — |
| [`docs/STATUS.md`](../STATUS.md) | what is planned / implemented / validated / activated; open gates | AUTHORITATIVE for the current state; self-checked by the test suite | — |
| [`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md) | stages, stage contracts, common rules, identity, extraction and release design | NORMATIVE TARGET — not implemented | CPD-0001 |
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
| [CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) | Core pipeline contracts (run, fetch record, pack, identity, extraction, layers) | `ACTIVE_WITH_VALIDATION_DEBT` |

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
| No deletion call outside the five named places, over every module | — | `tests/test_preservation.py` |
| Tracked registry proposal agrees with its review report; nothing registered | `config/outlet_registry.json`, `config/registry_review/` | `tests/test_registry.py` |

## 4. Open decisions and gates

| Register | Scope |
|---|---|
| Master plan §13 (O-1 … O-10) | operator and institutional decisions |
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
| [`config/registry_review/`](../../config/registry_review/) | review report of the legacy registry import | evidence of one import run; the proposal it describes is not a registration |
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
