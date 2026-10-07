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
| Storage, preservation, provenance | [`docs/storage/INDEX.md`](../storage/INDEX.md) | not started |
| Corpus supply (registry attributes, cohorts, targets, monitoring) | [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md) | not started |
| NLP, enrichment, LLM policy | [`docs/nlp/INDEX.md`](../nlp/INDEX.md) | not started |
| Legacy system and legacy corpus | [`docs/legacy/INDEX.md`](../legacy/INDEX.md) | rules in force; freeze not executed |

Acquisition (discovery, fetch), document identity, extraction, admission, normalisation and release
have no component index yet: until their first implementation run they are specified in the target
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
| Logical storage targets (contract only; no resolver) | `config/storage_targets.yml` | `tests/test_repository_contract.py` |

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
