# Cross-corpus analysis contract — component index

**Status: TECHNICAL PROPOSAL WITH A CONFORMANCE PROTOTYPE. JOINT DECISION WITH CO.RA.PAN OPEN
(master plan O-6). NO EXPORT OF CORPUS MATERIAL EXISTS. NOTHING VALIDATED, NOTHING ACTIVATED.**
Governing decision:
[CPD-0008](../decisions/CPD-0008_cross-corpus-analysis-contract-and-phase3-layer-architecture.md).
Current state: [`docs/STATUS.md`](../STATUS.md).

Entry point for: the shared analysis tables, the value states, the token denominator, the
compatibility view, the comparability of measure families, and the designs of the shared-text
equivalence test and the tense bridge.

---

## 1. Documents

| Document | Content |
|---|---|
| [`ANALYSIS_CONTRACT.md`](ANALYSIS_CONTRACT.md) | the contract: evidence from both repositories, O-6 proposals, tables, tokens and counting, value states, release semantics, compatibility view, NLP alignment, equivalence and bridge designs, comparability matrix, hypotheses, proposal to CO.RA.PAN |
| [`../architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md`](../architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md) | COPREPAN's text layers from extraction to the contract export |

## 2. What exists

| Thing | Code | Test |
|---|---|---|
| Contract vocabularies, table schemas, validator (fail closed), manifest sealing, storage of a bundle | `src/coprepan/analysis_contract.py` | `tests/test_analysis_contract.py` |
| The denominator rule `crosscorpus-token-denominator/v1` | same (`counts_in_denominator`) | same |
| Compatibility view builder; four demonstration queries | same | same |
| COPREPAN adapter: registry rows, identity, extraction records and a *supplied* annotation → a bundle | `src/coprepan/analysis_export.py` | same |
| A press fixture (through the real extractor and id code) and a radio fixture (modelled on CO.RA.PAN 3.0 as observed) | `tests/support_crosscorpus.py` | same |

A bundle on disk: `release.json`, one `<table>.jsonl` per table, `layers/<layer id>.jsonl`,
`compatibility.jsonl`. `write_bundle` refuses a non-conformant bundle; `read_bundle` refuses one
whose hashes do not hold.

## 3. Rules

- The contract is an analysis layer. No stage of the pipeline reads it; nothing internal is
  shaped to look like the other corpus.
- No bare null: a stateful field carries its state.
- A compatibility alias never appears in a canonical table.
- A derived layer is its own table with its own version and validation status.
- Counts and rates name their denominator.
- **A fixture is marked as a fixture** (`release_kind: fixture`, a release id with year `0000`)
  and proves implementability only.
- CO.RA.PAN is not changed from here. What it would need is a proposal (contract §15).

## 4. Open

Contract §16. In short: adoption by CO.RA.PAN; the two legs of the tense bridge; the equivalence
run; coverage and selection-policy schemas; columnar storage.

## 5. Milestones

- 2026-10-07 — contract proposed (CPD-0008), validator and COPREPAN adapter built, two synthetic
  fixtures conformant, invalid bundles refused. Stage 12 `PARTIAL`. O-6:
  `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN`.
  Run report: [`docs/agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md`](../agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md).
