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

### 1a. The joint release contract `crosscorpus-release/v1` (added 2026-10-08)

A second cross-corpus contract exists beside the analysis contract. It was drafted in CO.RA.PAN,
which is its canonical home; this repository holds a **verbatim, pinned copy** and its own
implementation of the checks.

| Thing | Where | Status |
|---|---|---|
| The bundle: text, schemas, fixtures for both corpora, vectors | [`contracts/crosscorpus-release-v1/`](../../contracts/crosscorpus-release-v1/CONTRACT.md) | `DRAFT` in its canonical home; **adopted by CO.PRE.PAN** (CPD-0012); not adopted by CO.RA.PAN; not jointly frozen. *2026-11-14: the copy is draft revision 2, adopted locally by CPD-0034; still `DRAFT`, not jointly adopted* |
| Pin | `config/crosscorpus/contract_pins.json` — bundle digest `4fb72acf27abf09b29dba9de22b241471d0eb5fde3c9e75cc638d646426dbbe0` (draft revision 1, CO.RA.PAN commit `0a5f41dec`) | equalled CO.RA.PAN's pin when read on 2026-10-08 (morning). **No longer equal (found 2026-10-22):** CO.RA.PAN pins draft revision 2 (`429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255`, its commit `374d2e44e` of 2026-10-08, "not yet taken by CO.PRE.PAN"); see below. *2026-11-14: the pin here names revision 2 (`429f55eb…2255`, `revision: 2`; revision 1 under `previous_revisions`), so both pins name the same digest again* |
| CO.PRE.PAN's implementation and native export object | [`docs/release/INDEX.md`](../release/INDEX.md) | conformant with every digest and all 52 cases of revision 1; revision 2 (93 cases, 30 pattern vectors) not run here. *2026-11-14: conformant with every digest, all 93 cases and all 30 pattern vectors of revision 2 (CPD-0034)* |

**The two revisions (dated note 2026-10-22, consistency audit).** Revision 2 keeps the fixtures and the 52 cases of revision 1
and adds 41 cases, 30 pattern vectors and rules on points the two implementations read differently (among them a freeze
record beside a provisional export, sums over no documents, release-forbidden suffixes checked by the check itself, the
portable pattern subset). Its §17 says a local adoption that quotes an earlier digest does not carry over. CPD-0012 quotes
revision 1. So the joint check "same digest on both sides" does not hold, and the readings of this repository's checker at
those points are those of revision 1. Taking revision 2 over (copy, pin, the new cases, a renewed local adoption) is a
decision that has not been taken; the audit changed neither the copy nor the pin. Evidence: CO.RA.PAN
`config/crosscorpus/contract_pins.json` (`draft_revision: 2`, `other_side.pinned_revision: 1`); digests recomputed with this
repository's tree-listing algorithm (audit report §E).

**Revision 2 taken over (dated note 2026-11-14; the current state — the note above is history).** The bundle was copied
verbatim from CO.RA.PAN commit `374d2e44e` (every file from its git blob, blob id and SHA-256 checked; CO.RA.PAN read only, none
of its code run); its digest, recomputed with this repository's `bundle_digest`, is `429f55eb…2255`. Of the revision-2 vectors,
the unchanged checker passed 84 of 93 cases and 29 of 30 patterns — the divergences CO.RA.PAN's handoff (§8.3 there) expected,
except the letter-case cases (already conformant: `casefold`, and listed paths were already compared) and the study input
without a filter (already refused, for another reason). The checker was changed to the revision's rules (CPD-0034 §3) and now passes all 93 cases and all 30
pattern vectors; only then was the pin moved. The local adoption is renewed against `429f55eb…2255` (CPD-0034; CPD-0012's
adoption record superseded in part). **The bundle remains `DRAFT` and is not jointly adopted**: the joint adoption (contract
§14.3 step 3 — both adoption records quoting this digest, both pins `ADOPTED`) is a separate joint act and needs CO.RA.PAN's
adoption record, which does not exist. CO.RA.PAN's pin file still records this side as revision 1 (`other_side.pinned_revision: 1`,
`local_adoption` CPD-0012; read at its commit `58307cb2a` on 2026-11-14); updating it is CO.RA.PAN's matter, not done from here.

**The analysis contract and the radio side (dated note 2026-10-22).** CO.RA.PAN's D116 (2026-10-16) retired speech mode from
its regular processing and made the communicative situation type (`PRESENTATIONAL` / `INTERACTIONAL` / `UNDETERMINED`, over
professional-speaker core turns) its main annotation; its D101 reads a stored `prerecorded` as `unknown`. The shared field
`production_mode` of this contract (§4.2 of the contract) takes its spoken values from speech mode. The contract text is
unchanged; whether and how it is versioned is a joint decision (O-6), recorded as a debt in `docs/STATUS.md` §6.

How the two contracts relate: the release contract defines a release, its exports, freeze,
coverage, study populations and packages; the analysis contract defines the tables a study reads.
An analysis bundle is a **projection** of a release. The release contract takes the namespace, the
value states, the date rules, the unit kinds, `release_kind`, the pin shape and the token
denominator from the analysis contract unchanged, fills its two open items (coverage; the place of
the selection policy) and replaces one sentence of it (what a study pins: CPD-0012 §2).

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
run; columnar storage. The coverage schema is given by the release contract (§7.3 there); of the
selection policy only its pin is specified.

Release contract: its joint freeze (CO.RA.PAN's adoption record; both pins `ADOPTED`); its §16 Q1
(CO.PRE.PAN's recommendation: CPD-0012 §5), Q3, Q5–Q10; the proposals of the
[run report](../agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md) §8.
Noted so that it is not found late: the analysis tables carry `production_mode_share` as a
fraction; a fraction is not a canonical value of the release contract (§4.1 there). No conflict
today — no release document holds a share — but analysis tables could not be pinned as record sets
of the release contract in that form.

## 5. Milestones

- 2026-10-07 — contract proposed (CPD-0008), validator and COPREPAN adapter built, two synthetic
  fixtures conformant, invalid bundles refused. Stage 12 `PARTIAL`. O-6:
  `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN`.
  Run report: [`docs/agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md`](../agent-runs/2026-10-07_phase3-crosscorpus-analysis-contract.md).
- 2026-10-08 — joint release contract `crosscorpus-release/v1` taken verbatim from CO.RA.PAN and
  pinned; CO.PRE.PAN's own implementation reproduces the bundle's digests and all 52 cases; local
  adoption CPD-0012; study pin semantics of CPD-0008 §7 amended. Not jointly frozen.
  Run report: [`docs/agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md`](../agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md).
- 2026-11-14 — draft revision 2 of `crosscorpus-release/v1` taken over verbatim and pinned (`429f55eb…2255`); own checks
  conformant with all 93 cases and 30 pattern vectors; local adoption renewed (CPD-0034). Still `DRAFT`; not jointly adopted.
