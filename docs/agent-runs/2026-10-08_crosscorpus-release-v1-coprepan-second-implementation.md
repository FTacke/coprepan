# `crosscorpus-release/v1` — CO.PRE.PAN's second, independent implementation

```text
run_started_at:      not read from a clock at the start (first clock reading: 2026-10-08T09:25:14+02:00, after the first reading pass)
run_ended_at:        2026-10-08T09:55:00+02:00 (approximate: last clock reading 09:49:49+02:00, before the final test run and the commit)
timezone:            Europe/Berlin
wall_clock_seconds:  not computed: neither boundary was read from a clock
```

**Status: PASS.** CO.PRE.PAN has implemented the joint release contract `crosscorpus-release/v1`
independently, reproduces every digest and all 52 cases of the shared vectors, has decided its
native export object, and has recorded its own adoption.

**What the status does not claim.** The joint contract is **not frozen**: CO.RA.PAN has recorded
no adoption and the pin status stays `DRAFT`. No release of the corpus exists and none can be
built (no adopted extractor). Nothing was checked on real material. No population is validated, no
distribution exists, no gate of `docs/STATUS.md` §5 changed.

**Kind of run:** implementation and decision (CPD-0011, CPD-0012). Not a scientific validation, not
an activation.

`EXTERNAL_API_USAGE = NONE`. No network access, no model inference, no storage root. CO.RA.PAN was
read and not changed.

## 1. Starting state

| | |
|---|---|
| CO.PRE.PAN | `main` = `origin/main` = `a2a5ff5eb5ea5539ea88be9f5569492b0da9c257`; working tree clean |
| Baseline suite (measured before any change) | `python -m pytest -p no:cacheprovider -q` → 897 passed, 1 skipped (symbolic links cannot be created on this account) |
| CO.RA.PAN (read-only) | `main` at `4710b9e1cbe4b339624175ad2da37afd7934920d`; untracked: the two operator plans under `docs/plans/2026-10-07_*` (operator inputs there; left as found) |

Operator brief: implement the second independent implementation of `crosscorpus-release/v1` in
CO.PRE.PAN, verify the bundle pin, take the bundle verbatim, work through the handoff (P1–P6, six
review points, PG1–PG4), decide the native export object (Q4), settle the pin semantics of
CPD-0008 (Q2), give a recommendation on Q1 without closing it, and record a CO.PRE.PAN adoption.

## 2. CO.RA.PAN sources read

Read in full: `CLAUDE.md`; `contracts/crosscorpus-release-v1/` (`CONTRACT.md`, the ten schemas,
`conformance/VECTORS.json`, the fixtures); `config/crosscorpus/contract_pins.json`;
`docs/crosscorpus/{INDEX,HANDOFF_COPREPAN,IMPLEMENTATION_PLAN_CORAPAN}.md`;
`docs/agent-runs/2026-10-08_joint-release-analysis-contract-foundation.md`.

Read in the parts the contract cites: the operator plan
`docs/plans/2026-10-07_corpus-storage-release-distribution-and-archiving-plan.md` (§1–§2.5, §5.6,
§6–§9, §12, §19–§22). Skimmed for the mechanisms the contract names:
`reservoir/export_ready.py` (store layout, id, promotion), `reservoir/layer_mirror.py`
(`tree_sha256`), `reservoir/asr_ready.py` (`canonical_json`), `corpus_supply/dating.py` (date
bases), `config/storage_retention.yml`, `config/storage_targets.yml`, `docs/export/INDEX.md`,
`docs/methodology/SCIENTIFIC_MEASUREMENT_FRAMEWORK.md` (§9.3 and the validation dimensions). Not
read: `AGENTS.md` of CO.RA.PAN beyond what `CLAUDE.md` restates (nothing was written there),
`pipeline/export.py`, `pipeline/export_contract.py`, the `storage/` package.

`src/corapan_playground/crosscorpus/release_contract.py` was **not read before CO.PRE.PAN's
implementation passed all vectors**. Afterwards a few places were read to compare readings (§8).
Nothing was imported, ported or run from CO.RA.PAN.

Authority as reconstructed: no CO.RA.PAN decision adopts the contract; the bundle (commit
`0a5f41dec`) is later than the operator plan and says where it differs from it (contract §15); the
joint run report is a record. Where plan and bundle differ, the bundle was followed (§4).

## 3. Bundle and pins

| Check | Result |
|---|---|
| Bundle changed in CO.RA.PAN since the joint run? | no: one commit touches `contracts/` and `config/crosscorpus/` (`0a5f41dec2399369488c29f7cef37b053de28bcd`); no difference to `HEAD` |
| Digest in CO.RA.PAN's pin file | `4fb72acf27abf09b29dba9de22b241471d0eb5fde3c9e75cc638d646426dbbe0`, status `DRAFT` — the pin the brief names |
| Copy | `contracts/crosscorpus-release-v1/`, 49 files, `contracts/** -text`; the git blob ids of all 49 files equal CO.RA.PAN's |
| Digest of the copy, recomputed by CO.PRE.PAN's code | `4fb72acf27abf09b29dba9de22b241471d0eb5fde3c9e75cc638d646426dbbe0` (measured) |
| Fixture pins of the brief | all five reproduced: `7b9bc998…5211`, `b595003c…677d`, `de999810…fd8b`, `7582bc37…62b6`, `4e373dfc…5673` |

No local fork: the copy is not edited, and `release_contract.load_contract` refuses any copy whose
digest is not the pinned one.

## 4. Against CO.RA.PAN's storage / release / distribution plan

| Plan | Contract and this implementation |
|---|---|
| releases logically complete, physically deduplicated; exports stored once (§2.4, §6.3) | followed: a release names exports; a correction is a new export in a later release (tested) |
| `manifest_sha256` inside the manifest (§6.4) | not followed, by the bundle's decision T2: no self-hash; the freeze record and referrers carry the digest (tested) |
| `audio_hours`, `tokens` as plain numbers | integers with states; for press `audio_ms` `not_applicable`, tokens `not_available` |
| author and ORCID in the release manifest | in the package manifest (T8) |
| study population: base release, selection, ids, digest (§7, §8) | followed; ids are the identity, the selection provenance |
| `latest` pointer (§9.5) | schema only; nothing built |
| G4 deterministic manifest, G5 immutability, G7 reconstruction, G8 population reproducibility | exercised on synthetic material (same inputs → same digests in two places; a changed manifest or export is reported; a population verifies from a package alone). **Not** on real data |
| fileservice, access groups, backup, LinguRep, DOI (G2, G3, G6, G9, G10) | not touched; nothing configured, published or deposited |

Remaining differences are listed in §16.

## 5. Handoff P1–P6

| Step | Status | Reason |
|---|---|---|
| **P1** take the bundle | **DONE** | verbatim copy, `-text`, tracked pin, a test that recomputes the digest |
| **P2** implement the checks | **DONE** | `src/coprepan/release_contract.py` on `canonical.canonical_json`; all digests and all 52 cases |
| **P3** report disagreement | **DONE** — none with the vectors | no case gave another verdict than expected; four readings differ beyond the vectors and several points are open in the text (§8) |
| **P4** native export object | **DONE** as a decision, **ADAPTED** as to its gate | CPD-0011; the handoff's gate "a real export has a member record and verifies" is met for a synthetic export only, because a real one cannot be built before an extractor is adopted |
| **P5** document index | **ADAPTED** | mapping implemented (`document_records`); `date_basis` is the three bases a publication date can rest on (`extraction.DATE_BASES`), not all of `extraction.BASES`, which also holds bases of titles and language; no date parser exists, so a date is known only when handed in |
| **P6** adoption record | **DONE** | CPD-0012 quoting the digest; CPD-0008 §7 amended; master plan O-6 updated |

## 6. The six review points

1. **Document version as the sampled unit when one document has several versions in a release.**
   It is the right unit for membership: ids are unique, each version has its own text digest. But
   the release document index does not say that two versions are one article (the native record
   and the analysis tables do). A study counting documents at release level would count an article
   twice. Whether a release selects one version per document is a selection-policy question
   (contract Q6). Proposal to the bundle: say so in §7.1, or carry the grouping id. Tested as it is.
2. **Exactly one member export per document.** Compatible, given the decision that an export is
   not a pack or an acquisition run (a version is observed in many packs). The release builder
   refuses a version delivered twice.
3. **`date` as the outlet's local calendar date.** Not available today: extraction keeps the
   published value unparsed, and the registry holds no reviewed time zone. Every real document
   would be `not_available` or `unknown` until a date parser exists. Nothing is guessed.
4. **Retention.** Recorded as a rule in the storage index §7: an export named by a frozen release
   is on hold, and so is every pack that holds a fetch such an export names. No retention code
   exists.
5. **Media suffixes and fetched pages.** The contract's list refuses audio and video only. A WARC
   file listed in a package would pass the contract's check although fetched pages are never part
   of a release. CO.PRE.PAN's package **builder** refuses `.warc`, `.warc.gz`, `.arc`, `.arc.gz`,
   `.cdx`, `.cdxj`; the **check** follows the bundle unchanged. Proposal to the bundle: add the
   suffixes.
6. **Phase order.** Reproduced from the text alone for all 52 cases. Two things the text leaves to
   the reader: the order inside phase 1 (version before schema), and what a pinned release that
   does not verify is reported as (§8).

## 7. The independent implementation

`src/coprepan/release_contract.py` (checks; reads only): strict parsing and canonical values, the
two digests, contract paths and tree listing, the schema subset evaluator, `verify_release`,
`verify_study`, `verify_package`, the closed code vocabulary, and the bundle loader. It imports
`canonical.py` and nothing of the pipeline. **No second canonical-JSON rule**: the digests use
`canonical.canonical_json` (CPD-0003), asserted by a test.

`src/coprepan/release_export.py` (writes only where told): the native export object and the
builders for release, freeze, package and study population.

Written from `CONTRACT.md`, the schemas, the fixtures and the vectors. The first run of the 52
cases passed without a change to the implementation.

## 8. Conformance results

Measured 2026-10-08, one workstation, `tests/test_release_contract.py`:

| Item | Result |
|---|---|
| canonical JSON vectors (4), record-set vectors (3) | reproduced |
| fixture digests: release manifest, members, documents, coverage, export trees, package files, package manifest, study population, selected ids — both corpora; joint study | reproduced |
| cases | 52 of 52 give exactly the expected set of codes |
| bundle identity; five kinds of drift; a missing pin; another contract version | refused |

**Four readings that differ from CO.RA.PAN's implementation, none fixed by a vector** (found by
reading its code afterwards; not run):

| # | Situation | CO.PRE.PAN | CO.RA.PAN |
|---|---|---|---|
| D1 | schema `pattern` ending in `$`, value with a trailing line feed | refused (`\Z`: JSON Schema patterns are ECMA-262) | accepted (Python `re.search`) |
| D2 | a study or package pins a release that has the pinned digest but does not verify | the release's own codes | `RELEASE_PIN_MISMATCH` |
| D3 | a selection record names a release the study does not pin | `POPULATION_NOT_RESTORABLE` | `RELEASE_PIN_MISMATCH` |
| D4 | a `provisional_export` that has a freeze record | the record is not read | the record is checked |

**Points the text leaves open** (CO.PRE.PAN's reading in brackets): a document with a known date
and a cohort that is not known (accepted: §7.2 states only the other direction); a corpus of a
declarative selection without a filter entry (selects nothing); the sum of a stateful count over
no documents (known, zero); letter-case comparison (`casefold`); the regular-expression dialect of
`\s` / `\S`. Together with review points 1 and 5 these are **proposals to the canonical home**,
each best settled by a vector case. None was changed locally, and none contradicts a vector, so
none blocks CO.PRE.PAN's adoption.

## 9. Q1 — token counts `not_available`

Recommendation (CPD-0012 §5): **a release may be frozen while token counts are `not_available`**,
because release identity and annotation completeness are separate statements that the contract
already keeps apart and makes explicit, and because it forbids the misleading cases (a count
without the denominator; a partial sum as a total). Both corpora are in that state today:
CO.RA.PAN has no token export, CO.PRE.PAN no annotator. Such a release supports no rate; counts
arrive in a later release. Tested: a release with the state explicit at all three levels verifies
and freezes; a known count without the denominator is refused.

Status: `TECHNICAL_RECOMMENDATION_READY` · `JOINT_DECISION_OPEN`. Not closed.

## 10. Q2 — pin semantics, CPD-0008

CPD-0008 §7 and the analysis contract §8 said a study pins `release_id` and `manifest_sha256`,
"nothing else". That was complete while a bundle was the only possible release. It is now
incomplete, and "nothing else" contradicts the release contract §10.1. Amended by CPD-0012 §2 (a
new decision; CPD-0008 carries a dated line and a forward link, the analysis contract a dated
amendment): a study pins the release by id and release manifest digest and, where it reads
analysis tables, that bundle's `manifest_sha256`. The two digests keep their two names;
`analysis_contract.seal` is unchanged. One definition of study pinning remains: contract §10.1.
Tested with a real sealed analysis bundle.

## 11. Q4 — the native export object

Inventory of what exists (as built): preserved fetches in sealed packs — primary evidence, fetched
pages; document and version rows in identity tables — derived, rebuildable, workspace state;
extraction records in the write-once layer store, by fingerprint and artifact id; technical
admission labels — chained evidence; the analysis bundle — a projection. None of them can be named
by a release.

Decision (CPD-0011): `coprepan-export/v1` — a tree of one outlet's document versions with their
stored extraction records and provenance by id and hash; `export_id` = `cpx1-` + 32 hex over the
canonical JSON of a manifest that pins every other file and holds no clock, host or location; no
fetched page; layer `extraction` only; a correction is a new export; a `corpus` export refused
unless the extractor is `ACTIVE`. Not decided: partitioning over time (no measured volume, O-4),
the annotation layer, the date parser.

Fixture (PG3), `tests/test_release_export.py`: the synthetic canary pages through the real code —
recorded exchange, sealed pack, preservation, identity, extraction, admission label — then export
→ member → manifest → freeze → archive package → study population, each step verified by the
contract checks, and the whole way repeated in a second place with identical digests.

## 12. Adoption status

| Gate (handoff §6; brief §22) | Status |
|---|---|
| **PG1** same contract — bundle digest of the copy = CO.RA.PAN's pin | **PASS** |
| **PG2** vectors — all digests and all cases, in `foundation_contract` | **PASS** |
| **PG3** (handoff) no local drift — a test fails when the copy differs from the pin | **PASS** |
| **PG3** (brief) native mapping on a schema-based synthetic export | **PASS** |
| **PG4** (brief) local adoption readiness — Q2 and Q4 settled, no contract inconsistency | **PASS**; adoption record: CPD-0012 |
| **PG4** (handoff, "later") a release of real CO.PRE.PAN exports verifies | **not attempted** — no real export can exist yet |

The brief's PG3 and PG4 differ from the handoff's; both are reported, the handoff's names first.

## 13. Tests

| Command | Result |
|---|---|
| `python -m pytest -p no:cacheprovider -q` (before) | 897 passed, 1 skipped |
| `python -m pytest -p no:cacheprovider -q` (after) | 1085 passed, 1 skipped |
| `python -m pytest -p no:cacheprovider -q --suite release_gate tests` | no test selected (the suite is deliberately empty) |

New: `tests/test_release_contract.py`, `tests/test_release_export.py`, both registered in
`foundation_contract`. The crash-recovery, concurrency, integrity-invariant and evidence-integrity
modules are part of the full run and pass unchanged. One intermediate failure, fixed: a test string
that looked like a drive path tripped the repository's own path scan.

`release_gate` was left empty. The handoff places the vectors in `foundation_contract`; the suite
gates changes of a production pipeline that does not exist, and a module belongs to one suite.

Regression against the integrity guarantees: building an export and a release leaves the
workspace and the preservation root byte-identical (tested); every exported text leads back to a
`RAW_PRESERVED` fetch and is reproduced by replay (tested); no export file holds a path, a fetched
page or workspace state (tested); the two new modules contain no deleting call (the existing
structural test covers every module).

## 14. Validation classification

**Reproducibility** (same inputs → same ids and digests, in two places), **robustness** (declared
manipulations are reported; drift is refused) and **independent technical conformance /
interoperability** (two implementations written separately agree on shared vectors). By this
repository's methodology *replicability* means a finding recurring in new data from the same
population; a second implementation is not that, and the word is not used. No scientific
validation, no generalisability, no validation of a production release.

Limit: the vectors' expected values were produced by CO.RA.PAN's implementation; agreement of two
implementations on 52 cases shows the cases are implementable from the text, not that the text is
complete (§8).

## 15. Open joint points

- CO.RA.PAN's adoption record; both pins `ADOPTED` — the contract freeze (contract §14.3).
- Q1 (recommendation given), Q3 producer anchors for press, Q5 coverage below the document, Q6
  selection-policy content and first population, Q7 licence / access / identifier, Q8 columnar
  storage, Q9 notice for a release that must not be used, Q10 further corpus ids.
- The proposals of §6 (points 1 and 5) and §8, for the canonical home.
- CO.RA.PAN's observed-state pin of the analysis contract names file digests of
  `ANALYSIS_CONTRACT.md` and CPD-0008; both files carry a dated amendment since this run.
- No real export of either corpus has met the contract.

## 16. Consequence for a later real release

A real CO.PRE.PAN release needs, in this order: an adopted extractor (Phase 3); a date parser and
reviewed outlet time zones; a selection policy document; a durable exports root (O-3); then, for
token counts, the annotation stage and export schema `v2`. None exists. The release mechanics
themselves are in place and will not have to be designed under time pressure.

Differences to CO.RA.PAN's plan that remain: release id form (`coprepan-YYYY.n`); one export per
outlet rather than per production job; no convenience Parquet projections; no distribution layout;
no release notes file (the contract leaves notes outside the manifest).

## Files

Created: `contracts/crosscorpus-release-v1/` (49 files, verbatim);
`config/crosscorpus/contract_pins.json`; `src/coprepan/release_contract.py`;
`src/coprepan/release_export.py`; `tests/support_release.py`; `tests/test_release_contract.py`;
`tests/test_release_export.py`; `docs/release/INDEX.md`; CPD-0011; CPD-0012; this report.

Changed: `.gitattributes` (`contracts/** -text`); `src/coprepan/extraction.py` (one constant,
`DATE_BASES`; no behaviour changed); `tests/suites/foundation_contract.txt`; `docs/STATUS.md`
(stage 11 `PARTIAL`); the master plan (O-6, §12 item 14); `docs/architecture/INDEX.md`;
`docs/architecture/TERMINOLOGY_AND_NAMING.md` (§15); `docs/crosscorpus/INDEX.md`;
`docs/crosscorpus/ANALYSIS_CONTRACT.md` (dated amendment); `docs/storage/INDEX.md` (§7);
`docs/decisions/README.md`; CPD-0008 (dated line and forward link only).

Nothing was moved, deleted or overwritten. `freeze.py` and `legacy_freeze.py` were not touched;
their freezes are different things and are named as such.

## Working tree and git

Commits on `main`, explicit pathspecs: `59a5062bd8af668fcb541865d4bae7dfcb8ac621` (bundle and
pin), `22502cafcda820b2baeae8d46ebc8b9d919b5e6b` (implementation and tests), and the commit that
adds this report (decisions and documentation). Every changed file is committed; nothing is left
untracked. **Not pushed by this run**: the push to `origin/main` is left to the operator's
confirmation (see the operator report).

## Recommended next run

The registry review for the canary outlets (O-11) — unchanged from the master plan §12 item 8.
Nothing of the release or distribution layer stands before it.
