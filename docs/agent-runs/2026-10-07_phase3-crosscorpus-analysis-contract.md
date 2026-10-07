# COPREPAN 3.0 — Phase-3 architecture and the cross-corpus analysis contract

```text
run_started_at:      2026-10-07T23:32:41+02:00   (first clock reading, after the previous run was pushed)
run_ended_at:        2026-10-07T23:54:22+02:00   (last clock reading, after the final full test run; the commits and the push followed)
timezone:            Europe/Berlin
wall_clock_seconds:  1301   (between the two readings above)
status:              PASS   — for the scope of §0
kind of run:         diagnosis (read-only archaeology of two reference repositories) + decision
                     + implementation of a prototype, with reproducibility and robustness checks.
                     No scientific validation. No production activation.
EXTERNAL_API_USAGE = NONE   (no model API, no external service, no request to any website)
NETWORK USE:         `git push` to `origin` only. Nothing was installed.
```

This is a **separate run** from the pre-canary completion run that ended immediately before it
(report `2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md`). It started from
that run's pushed result, `main` = `origin/main` = `c93c4e9af4c108cbd1acdae770dbf0a41bcbe966`,
with a clean working tree and 705 tests passing.

## 0. What `PASS` covers, and what it does not

**Covers:** the Phase-3 layer architecture and the cross-corpus analysis contract are internally
consistent, documented, and reproducibly tested as a prototype: one validator, an adapter on
COPREPAN's side, a press fixture and a radio fixture that both conform, and invalid bundles that
are refused.

**Does not cover, and must not be read into it:** no scientific validation of anything; no
annotation equivalence (no annotator is installed here and none was run); **no adoption of the
contract by CO.RA.PAN** — nothing was changed there and nobody there was asked; no export of
corpus material (none exists); no cross-corpus study capability on published releases (there are
no releases). O-6 is **not** closed.

## 1. Brief, and how the plan was adapted to the repository as found

Brief: `docs/plans/COPREPAN3_PHASE3_CROSS_CORPUS_ANALYSIS_CONTRACT_RUN.md`, re-read in full at
the start. Deviations from it, each because the latest repository state said otherwise:

| Plan | Found | Done instead |
|---|---|---|
| names its example report `2026-10-08_…` | the run took place on 2026-10-07 | dated by the actual run |
| "legacy tense-v3 ↔ current verbal-complex layer" as the bridge | the studies compared press `tense-v3` with radio `tense-v4-coprepan-compatible` | the bridge is designed with **two legs** (§7) |
| assumes a CO.RA.PAN token/sentence layer to align with | CO.RA.PAN exports no tokens, has no string token id and no release | the contract is written as a proposal with a list of what CO.RA.PAN would need (contract §15) |
| value states "such as" six upper-case names | this repository's rule is lower-case vocabulary values; CO.RA.PAN's scientific enums are lower case too | five lower-case states; `NOT_OBSERVED` folded into `unknown` with the reason stated |
| the previous run's admission and extraction scaffolding as the basis of Phase E | present as built (CPD-0007) | used as the fixed starting point; not redesigned |

## 2. Reference repositories (read-only)

| Repository | Commit | Working tree | How read |
|---|---|---|---|
| `corapan` (CO.RA.PAN 3.0) | `3a6972ffb973d6a1ea9c3a2e3314468b2d2bcbb1` | two untracked plan documents, no tracked change | files only; no test, pipeline or database opened |
| `legacy\\corapan_coprepan_studies` | `679e14c10a05632d2da631a8d0a9f193dc174ee4` | **not clean**: one modified config file, two untracked run notes, one untracked study directory | files only; nothing run |
| `legacy\\coprepan` | `3e6bdd3350913d55c07efe500036bf752de65cc2` | clean | one `grep` for the tense rule version |

Method: two read-only search agents produced the inventories (one per repository), each
instructed to cite file and line and to separate what is implemented from what is only specified.
I then re-read the passages the decisions rest on myself: the `speech_mode` vocabulary, the
value-state vocabulary, the analysis-token and parse-view schemas, the verbal-complex
vocabularies, the masked event types, the tense rule versions. **Not re-read by me**: most of the
studies' individual scripts; the counts the studies' own notes report (cited as sourced).
Nothing was written into any of the three.

## 3. Phase A — CO.RA.PAN 3.0 as it is

Recorded in [`ANALYSIS_CONTRACT.md`](../crosscorpus/ANALYSIS_CONTRACT.md) §2. The findings that
shaped the contract:

1. No `corpus_id`, no release, no freeze; the export bundle calls itself provisional.
2. **No token table is exported; no string token id exists**; tokens live in three layers with
   three index conventions.
3. Turns and contribution units are declared technical in CO.RA.PAN's own documents; no utterance
   layer exists.
4. `speech_mode` is region-based, projected to turns, has an abstention value distinct from
   `not_applicable`, and is described there as conceptually provisional.
5. No token denominator is defined.
6. The verbal-complex layer is derived on demand and never stored.
7. The NLP pins are the ones COPREPAN planned to mirror.

## 4. Phase B — the studies as a requirements catalogue

Contract §3: twenty-one workarounds, each with the requirement it implies and where the contract
meets it (the master plan had ten). New relative to the master plan: three different rate
conventions; context windows of different reach in the two corpora; the title as "previous
sentence" of the first body sentence; a role code used as an id; two scope classifiers that
disagree; the `tense-v3` / `tense-v4` finding.

## 5. Phase C/D — O-6 and the contract

Decided for COPREPAN in
[CPD-0008](../decisions/CPD-0008_cross-corpus-analysis-contract-and-phase3-layer-architecture.md):

| Point | Decision |
|---|---|
| contract | `crosscorpus-analysis/v1`; namespace `crosscorpus-` kept |
| shared field | `production_mode`: `unscripted`, `scripted`, `prerecorded`, `written_edited`; spoken values unchanged from `speech_mode`; nothing spoken mapped onto written |
| value states | `known`, `unknown`, `not_applicable`, `undecided`, `not_available`; value null exactly when the state is not `known` |
| units | declared kind and `segmentation_nature`; no unit kind is an utterance |
| tokens | parser tokens; string ids; id-valued heads; `morph` a dict of plain UD features; project labels refused |
| anchors | one schema; characters in both modalities, time for spoken words, state otherwise |
| denominator | `crosscorpus-token-denominator/v1`: words on the primary surface of in-scope units |
| release | manifest with per-table hashes and its own hash; kinds `release`, `provisional_export`, `fixture` |
| compatibility | a separate alias view; an alias in a canonical table is a violation |

**O-6: `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN`.** Open jointly: adoption; the form of
CO.RA.PAN's `release_id` (its inactive plan and this repository's rule differ); its freeze
semantics.

## 6. Phase E — COPREPAN's Phase-3 architecture

[`PHASE3_SCIENTIFIC_ARCHITECTURE.md`](../architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md): the
layer chain; what later layers may rely on in an extraction record; technical admission, content
admission and scientific taxonomies as three kinds of statement; normalisation as a closed,
versioned, offset-recorded operation set that never changes wording (its contents undecided);
BODY as the primary linguistic surface, one block per parser input, the title a separate surface;
language as declaration, identification layer and label; section, production mode, register,
article type and opinion as five variables; where human gold attaches.

## 7. NLP alignment, equivalence design, tense bridge

Contract §10–§12. Alignment: same tokenizer, model and pins by plan; sentence segmentation,
masking and numeral handling different by necessity and declared. Equivalence design: the same
written text through both instrument paths, expected result identity, every difference
investigated, no threshold. Bridge: two legs — `tense-v3` against `tense-v4` on the same text
(nobody has compared them; CO.RA.PAN's archaeology calls them the same logic "by construction"),
and legacy labels against `corapan3-verbal-complex/v2`, with a hypothesised correspondence table
marked as hypothesis. **Nothing was implemented or run for any of the three**; the old rules were
not ported.

## 8. Conformance prototype

| File | Content |
|---|---|
| `src/coprepan/analysis_contract.py` | vocabularies, table schemas, `validate` (fail closed), `seal`, bundle storage, `counts_in_denominator`, `legacy_studies_view`, four demonstration queries |
| `src/coprepan/analysis_export.py` | COPREPAN's adapter: registry rows, identity, extraction records and a supplied annotation → a sealed, validated bundle; refuses what would need a guess |
| `tests/support_crosscorpus.py` | the two fixtures |
| `tests/test_analysis_contract.py` | 28 tests |

The press fixture runs through real code as far as real code exists: an invented HTML page → the
baseline extractor → real document, version, unit, sentence and token ids → the adapter. Its
tokens are written by hand. The radio fixture is modelled on CO.RA.PAN's observed field
semantics and built by a test-side sketch of the adapter CO.RA.PAN would need; **it is not
CO.RA.PAN code and no CO.RA.PAN export produces such tables.** Both are marked as fixtures in
their release record (`release_kind: fixture`, release ids with year `0000`).

Refused in tests (each by the validator or the adapter, after resealing so that hashes hold):
duplicate ids within a bundle and across corpora; an orphan unit; a token in another unit; a head
in another sentence; an unknown outlet; a gap in an order index; two roots; a sentence without
tokens; crossed neighbours; a silent null; a value beside a non-`known` state; an invented state;
an empty string; a missing state field; a date basis without a date; a cohort that does not
contain its date; a spoken mode on press and the written mode on radio; a turn declared
editorial; an out-of-scope unit without reason; an undeclared reason; a missing parent unit;
`morph` as a string; a project label in `morph`; an undeclared feature; a `SPACE` token; time on
a written token; a spoken word without a time state; reversed offsets; half an anchor; counted
punctuation; a wrong token sum; a masked event as a token; a production event in print; a
relation to itself, stated twice, or lying about its target; two versions of one document;
an undeclared layer; a layer value outside its vocabulary; a layer target that does not exist or
is labelled twice; an alias in a canonical table; an alpha-3 country code; an unknown alias; an
unregistered outlet; offsets that do not point at the form; a tampered table; a tampered release
record; a "release" without pinned selection policy or with an unvalidated layer.

Query fixtures over both bundles through the contract alone: row counts per table; counted
tokens by `country_id × modality × production_mode`; verb tense values by modality;
verbal-complex values per modality; a sentence with its neighbours by id. **Their outputs are
arithmetic on invented sentences and are not reported as numbers here**: they show that the
queries need nothing but the contract.

## 9. Comparability matrix and hypotheses

Contract §13 and §14. In one line each:

- comparable with declared caveat: token, lemma, POS and morphology frequencies; verbal-complex
  shares (the most robust family: no token denominator needed); rates per counted token;
  clause-internal dependencies;
- not comparable as a modality contrast: sentence-level syntax; punctuation;
- modality-specific: unit lengths; temporal anchors; section and programme;
- undecided: lexical diversity; named entities.

| | Verdict |
|---|---|
| H1 shared token contract without essential artefacts | partially supported — schema and rule fit; residual artefacts unmeasured |
| H2 `production_mode` without falsifying `speech_mode` | supported as a design |
| H3 one layer with medium-typed anchors | supported at prototype level |
| H4 legacy studies through a compatibility view | partially supported — aliases separable; the legacy groups also encode selections |
| H5 same NLP pins | supported as far as pins go; undecided in practice (nothing installed; unlocked transitive dependencies) |

The matrix is a design judgement on the evidence read. **No measure was computed on any data.**

## 10. Files

New: `src/coprepan/analysis_contract.py`, `src/coprepan/analysis_export.py`,
`tests/support_crosscorpus.py`, `tests/test_analysis_contract.py`,
`docs/crosscorpus/INDEX.md`, `docs/crosscorpus/ANALYSIS_CONTRACT.md`,
`docs/architecture/PHASE3_SCIENTIFIC_ARCHITECTURE.md`, CPD-0008, this report.

Changed: `tests/suites/foundation_contract.txt`; `docs/STATUS.md`; the master plan; the decision
registry; the architecture index; the terminology; the NLP and extraction indexes.

Nothing was moved, deleted or overwritten. No file of the previous run's scope was changed in
behaviour: no acquisition, preservation, identity, extraction or admission code was touched.
`config/` is unchanged.

## 11. Tests

`python -m pytest -p no:cacheprovider -q` (Python 3.12.10, pytest 9.1.1):

| | Result |
|---|---|
| at the start | 705 passed, 1 skipped |
| at the end | **734 passed, 1 skipped** (28 contract tests and one decision-header check added) |
| the skip | unchanged from the previous run: symbolic links cannot be created on this account |

No existing test changed. Mistakes made and corrected, kept on record: two expectations of mine
in the new tests were wrong (a string length, a row count) and the code was right; one shell call
again contained a heredoc against the repository rule — it was empty and did nothing.

## 12. Gate and status changes

| | Before | After |
|---|---|---|
| stage 12, cross-corpus contract | `NOT_STARTED` | `PARTIAL` / `NOT_VALIDATED` / `INACTIVE` |
| O-6 | open, working names | `TECHNICAL_PROPOSAL_READY` · `JOINT_DECISION_OPEN` |
| every production gate (O-1, O-2, O-3, O-4, O-11, O-12, Phase 1, Phase 2) | as after the previous run | unchanged |
| Phase-3, Phase-4, Phase-7 gates | open | open: none was attempted |

## 13. Validation classification

| Kind | What this run supports |
|---|---|
| reproducibility | the same inputs give the same bundle and the same manifest hash; a bundle read back from disk equals the one written |
| robustness | the refusals of §8 |
| replicability | **nothing.** One implementation of the validator and of each adapter exists, all written in this run. The radio fixture is not an independent implementation: I wrote it against my own validator |
| generalisability | **nothing.** Two documents of invented text per corpus |

## 14. Known limitations and real risks

1. **The contract has been tested only against data shaped by its own author.** The first real
   test is CO.RA.PAN's review and an adapter written there.
2. The radio side rests on a reading of CO.RA.PAN's code on one day. That repository is moving
   (two untracked plans on release and hardening were present); a release design there may land
   differently from §8 of the contract.
3. `production_mode` inherits the unvalidated state of `speech_mode`. The contract carries the
   value and its share; it cannot make the value right.
4. The denominator counts disfluency words. That is a decision with consequences for every rate;
   it is declared, but a reader of a results table will not see a declaration.
5. Five value states are a lossy reduction of eleven. If a study needs to tell "stage failed"
   from "not run", the contract as proposed cannot say it.
6. The prototype stores JSON lines. Token tables of a real corpus need a columnar format; the
   canonical-bytes rule for hashing will have to be restated for it.
7. Two of this repository's earlier statements were imprecise and are corrected forward-only in
   the NLP index: which CO.RA.PAN token layer its field list describes; and the tense rule
   versions the studies compared.
8. The studies repository's working tree is not clean; what I cite from an untracked study there
   is not pinned by its commit.

## 15. What CO.RA.PAN would need later

Contract §15, seven items: a token and sentence export with string ids; time anchors on exported
tokens; the verbal-complex layer written out; a `corpus_id` and a named, hash-pinned export or
release; a value state for speech mode; ownership of the state mapping; agreement on the names.
Recommended as a **separate run in CO.RA.PAN**, after its own closure work, reviewing the proposal
and writing its adapter against the validator here. Nothing of it was started.

## 16. Next step, and the question the brief asked

**Is the shared analysis contract technically mature enough to be implemented jointly after the
first real COPREPAN canary and the Phase-3 gold validation?** As a design with a checkable
definition: yes — every table, state and rule is executable, and both data models have been shown
to fit on fixtures. As an agreed interface: not yet, and it cannot become one from this side
alone. Three things stand before joint implementation, none of them engineering in COPREPAN:
CO.RA.PAN's review and adoption (O-6); a CO.RA.PAN export of tokens, which does not exist; and on
COPREPAN's side an installed annotator, which waits for Phase 4.

Sensible next runs, in the order the dependencies allow:

1. operator: O-11, O-1 (with the schedule policy), O-2, O-3 — unchanged from the previous run;
2. the canary, then the Phase-3 gold sample and extractor comparison;
3. independent of 1–2 and cheap: the first leg of the tense bridge (`tense-v3` against `tense-v4`
   on the same text), which tells whether the finished studies compared like with like — it
   needs an operator-ordered environment for legacy code;
4. in CO.RA.PAN, as its own run: review of the contract proposal.
