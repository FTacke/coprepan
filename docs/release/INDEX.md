# Release — component index

**Status: EXPORT OBJECT AND RELEASE MECHANICS IMPLEMENTED, OFFLINE, ON SYNTHETIC PAGES — NOT
VALIDATED, NOT ACTIVATED. NO RELEASE OF THE CORPUS EXISTS, AND NONE CAN BE BUILT TODAY.** No
extractor is adopted, no selection policy exists, no exports root is configured. Governing
decisions: [CPD-0011](../decisions/CPD-0011_native-export-object-and-release-layer-mapping.md)
(the native export object),
[CPD-0012](../decisions/CPD-0012_local-adoption-of-crosscorpus-release-v1-and-study-pin-semantics.md)
(the joint release contract as CO.PRE.PAN works against it; its adoption record of revision 1 superseded by)
[CPD-0034](../decisions/CPD-0034_local-adoption-of-crosscorpus-release-v1-revision-2.md)
(the local adoption renewed against draft revision 2). Current state:
[`docs/STATUS.md`](../STATUS.md).

Entry point for: what a CO.PRE.PAN export is, how a release names exports, what a release freeze
is, packages and study populations. The contract itself is the bundle
[`contracts/crosscorpus-release-v1/CONTRACT.md`](../../contracts/crosscorpus-release-v1/CONTRACT.md)
("contract §n"); the cross-corpus side is in [`docs/crosscorpus/INDEX.md`](../crosscorpus/INDEX.md).

*Note 2026-10-22 (consistency audit):* the bundle here is draft revision 1 (`4fb72acf…6dbbe0`). The canonical home pins draft
revision 2 (`429f55eb…442255`) since 2026-10-08; this repository has not taken it over. Everything this index says about
conformance is conformance with revision 1 ([`docs/crosscorpus/INDEX.md`](../crosscorpus/INDEX.md) §1a).

*Note 2026-11-14 (release-contract revision 2 taken over; supersedes the note above for the current state):* the bundle here is
**draft revision 2** (`429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255`, verbatim from CO.RA.PAN commit
`374d2e44e`; recomputed here), and the pin names it. This repository's own checks reproduce every digest, **all 93 cases and
all 30 pattern vectors** of that bundle; the local adoption is renewed by CPD-0034. The bundle stays `DRAFT` and is **not
jointly adopted** (contract §14.3 step 3 is a separate joint act). What the checker now does differently, by the revision's
rules (CPD-0034 §3): a schema pattern in the portable subset (§12), a named release identified before it is
checked (§13.1), a freeze record beside a provisional export refused by its existence (§9.1), the cohort derived from the date
in both directions (§7.2), exactly one filter per input (§10.3), the sum over no documents (§7.3), and fetched-page containers
refused by the check itself (§11.3). Where this index says "the contract" below it now means revision 2.

---

## 1. Words that are not the same thing

| Term | Is | Is not |
|---|---|---|
| **export** (`coprepan-export/v1`) | one immutable, content-addressed tree of one outlet's document versions | a release; a pack; a file a study opens |
| **release** | a manifest, its pinned record sets and the exports they name — once frozen | the live state of the corpus; a software release |
| **release freeze** | `RELEASE_FREEZE.json`: the record that names a manifest by its digest, written by an explicit act | the **acquisition baseline freeze** (`freeze.py`, O-12); the **legacy freeze manifest** (`legacy_freeze.py`, O-10); frozen evidence |
| **projection** | a deterministic derivative of a release — the `crosscorpus-analysis/v1` bundle | a second source of truth |
| **package** | a distribution or archive copy of one frozen release | the release: a package may be rebuilt |
| **distribution copy** | a package placed on the `DISTRIBUTION` role | built or placed by anything here |
| **study population** | the frozen ids one analysis read, with their selection provenance | a physical copy of data |
| **`release_gate`** | a test suite that gates software changes (`tests/suites/release_gate.txt`) | a statement about a corpus release |

## 2. What exists

| Thing | Code | Test |
|---|---|---|
| The checks of `crosscorpus-release/v1` — CO.PRE.PAN's own implementation; bundle loader that refuses a drifted copy; `python -m coprepan.release_contract bundle · verify-release · verify-package · verify-study` | `src/coprepan/release_contract.py` | `tests/test_release_contract.py` |
| The pinned bundle and its pin | `contracts/crosscorpus-release-v1/`, `config/crosscorpus/contract_pins.json` | same |
| Native export object: builder, verifier, member and document records | `src/coprepan/release_export.py` | `tests/test_release_export.py` |
| Release manifest builder and the explicit freeze; package builder; study-population builder | same | same |

## 3. The export (`coprepan-export/v1`)

```text
<exports root>/<export_id>/
├─ EXPORT_MANIFEST.json                       schema, corpus, kind, outlet, layers, pins, components, code commit
├─ DOCUMENTS.jsonl                            one coprepan-export-document/v1 record per document version
└─ extraction/<fingerprint[:2]>/<artifact_id>.json   the stored extraction records, byte for byte
```

| Property | Rule |
|---|---|
| identity | `export_id` = `cpx1-` + 32 hex of SHA-256 over the canonical JSON of the manifest; the manifest does not contain the id and pins every other file |
| determinism | no clock, host or location in the object: the same versions and the same code commit give the same id anywhere |
| granularity | one outlet per export; a version in exactly one member export of a release; partitioning over time not decided |
| content | extracted text and provenance by id and hash (`fetch_id`, body digest, `pack_id`, fingerprint, artifact id, admission label). **No fetched page** |
| layers | `["extraction"]`. No annotation: token counts are `not_available` |
| kind | `corpus` (refused unless the extractor is `ACTIVE`) · `fixture` (enters a fixture release only) |
| correction | a new document version in a new export; nothing overwritten |
| reading | `read_export` refuses a tree that does not verify, and another schema version by name |

Document record: `document_version_id`, `document_id`, `outlet_id`, `extracted_text_sha256`,
`body_text_sha256`, `extraction` (`path`, `sha256`, `size`, `fingerprint`, `artifact_id`,
`extractor`), `source` (`fetch_id`, `body_sha256`, `pack_id`), `admission` (`ruleset`,
`technical_status`, `informing_reasons`), `date`°, `date_basis`°.

## 4. From export to release

| Step | Function | Gate |
|---|---|---|
| member and document records | `member_record`, `document_records` | the export verifies |
| manifest and record sets | `build_release` | own id form (`coprepan-YYYY.n`; year `0000` exactly for a fixture); fixture exports only in a fixture release; one member per version; a `release` pins its selection policy; the written manifest passes the check with every export present |
| **freeze** | `freeze_release` | the check with every export present passes; the person freezing states the manifest's digest; once |
| package | `build_package` | a frozen release that verifies; never a fetched page or source media (the contract's suffix list, plus `.warc`, `.warc.gz`, `.arc`, `.arc.gz`, `.cdx`, `.cdxj`; *since revision 2, 2026-11-14, those six are on the contract's own list and the package check refuses them too*) |
| study population | `build_study_population` | every id resolves against the pinned releases; an anchor kind the release declares |

Mapping of fields: CPD-0011 §8. A date is never guessed; a retrieval date is never a date.

## 5. Rules

- The contract bundle is a verbatim copy and is never edited here. A disagreement is reported and
  resolved in the canonical home.
- **No document contains its own digest.** The digest of a manifest is recorded by what refers to
  it: the freeze record, a later release, a study, a package.
- Digests of contract documents are taken over canonical content; payload files are hashed as
  bytes; a tree is identified by its `{path, sha256, size}` listing. No address enters a digest.
- A check reads and never repairs. A check without the exports says so.
- Building an export, a release, a package or a population writes only where it is told to and
  changes nothing it reads.
- An export named by a frozen release is on hold, and so are the packs its sources lie in
  ([storage](../storage/INDEX.md) §7).

## 6. Open

| Item | Kind |
|---|---|
| a real export: needs an adopted extractor | Phase 3 |
| partitioning of an outlet's versions into exports; sizes; cadence | technical, after O-4 |
| annotation layer of an export (`v2`); token counts | Phase 4 |
| date parser; outlet time zone for a local calendar date | Phase 3; registry review (O-11) |
| selection policy document; one version per document or all | scientific (contract §16 Q6) |
| exports root and release storage on a real target; distribution | O-3; institutional |
| the joint freeze of the contract; contract §16 Q1, Q3, Q5–Q10 (*revision 2, 2026-11-14:* also Q11, a grouping key for the versions of one work, which CO.PRE.PAN is asked to propose, and Q12) | joint |
| proposals to the canonical bundle | [run report](../agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md) §8 |

## 7. Milestones

- 2026-10-08 — joint release contract taken and pinned; own implementation conformant with the
  bundle's vectors; native export object decided (CPD-0011) and exercised on synthetic pages;
  local adoption recorded (CPD-0012). Stage 11 `PARTIAL`. No release built.
  Run report: [`docs/agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md`](../agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md).
- 2026-11-14 — draft revision 2 taken over verbatim and pinned (`429f55eb…2255`); own checks changed to the revision's rules
  and conformant with all 93 cases and 30 pattern vectors; local adoption renewed (CPD-0034; CPD-0012's adoption record
  superseded in part). Still `DRAFT`, not jointly adopted. Stage 11 stays `PARTIAL`. No release built.
