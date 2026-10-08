# CPD-0012 — CO.PRE.PAN's adoption of `crosscorpus-release/v1`; what a study pins

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the second-implementation run of `crosscorpus-release/v1` (2026-10-08), which ordered a CO.PRE.PAN adoption record once the bundle is verified, the independent implementation passes the shared vectors and the local questions are settled, and authorised the amendment of CPD-0008. Recorded by that run; subject to the operator's review. **It binds CO.PRE.PAN only** |
| Kind | architecture |
| Scope | the joint release contract as CO.PRE.PAN works against it; the pin semantics of a study; the terms of the release layer; a technical recommendation on contract §16 Q1 |
| Builds on / amends / supersedes | builds on CPD-0003, CPD-0008, CPD-0011. **Amends CPD-0008 §7** (one sentence: what a study pins) and the corresponding rows of the analysis contract §8 and §16 |
| Does not change | the contract bundle (never edited here); the analysis tables, value states and denominator of CPD-0008; `analysis_contract.seal`; anything in CO.RA.PAN |
| Run report | [`docs/agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md`](../agent-runs/2026-10-08_crosscorpus-release-v1-coprepan-second-implementation.md) |
| Evidence | `tests/test_release_contract.py` (bundle digest; every digest and all 52 cases of the bundle's vectors); `tests/test_release_export.py`; the comparison with CO.RA.PAN's implementation in the run report §8 |

Validation debt: conformance on synthetic fixtures only. No release of real CO.PRE.PAN exports has
been checked (handoff gate PG4). Listed in `docs/STATUS.md` §6.

## Adoption record

| | |
|---|---|
| Contract | `crosscorpus-release/v1` (status in the canonical home: `DRAFT`) |
| Bundle digest | `4fb72acf27abf09b29dba9de22b241471d0eb5fde3c9e75cc638d646426dbbe0` |
| Bundle taken from | CO.RA.PAN, commit `0a5f41dec2399369488c29f7cef37b053de28bcd`; unchanged there up to `4710b9e1cbe4b339624175ad2da37afd7934920d` (read 2026-10-08) |
| Copy and pin | `contracts/crosscorpus-release-v1/` (49 files, `-text`); `config/crosscorpus/contract_pins.json` |
| CO.PRE.PAN implementation | `src/coprepan/release_contract.py`, `src/coprepan/release_export.py` at commit `22502cafcda820b2baeae8d46ebc8b9d919b5e6b` (bundle and pin: `59a5062bd8af668fcb541865d4bae7dfcb8ac621`) |
| Analysis contract | `crosscorpus-analysis/v1` (CPD-0008), as amended below |
| Local decisions | CPD-0011 (native export object, Q4); this record (Q2; Q1 as a recommendation) |
| Conformance | every `canonical_json`, `record_sets` and `fixtures` digest of `conformance/VECTORS.json` reproduced; all 52 cases give exactly their expected set of codes; measured 2026-10-08 on one workstation |

**This is CO.PRE.PAN's adoption and nothing more.** The joint contract is frozen when both
projects have recorded their adoption against one bundle digest and the pin status in both
repositories becomes `ADOPTED` (contract §14.3). CO.RA.PAN has recorded none; the pin here stays
`DRAFT`. Until then the bundle may still change in its canonical home, and CO.PRE.PAN then moves
its pin deliberately, in one commit that runs the vectors again.

## Context

CO.RA.PAN drafted the joint release contract on 2026-10-08 with one implementation — its own. The
expected values of its vectors had only ever agreed with the code that produced them. The handoff
asked CO.PRE.PAN for a second implementation, a decision on its native export object, and an
amendment of one sentence of CPD-0008.

## Decision

### 1. CO.PRE.PAN works against the pinned bundle

- The bundle is a verbatim copy. **It is never edited here**; a needed change is requested in the
  canonical home and re-pinned on both sides.
- Code reaches the bundle only through `release_contract.load_contract`, which recomputes the
  bundle digest and refuses a copy that is not the pinned one.
- The checks are CO.PRE.PAN's own code. They share nothing with CO.RA.PAN's but the vectors.
- Canonical JSON is `canonical.canonical_json` (CPD-0003). No second serialisation exists.

### 2. What a study pins (amends CPD-0008 §7; contract §16 Q2)

CPD-0008 §7 says: "A study pins `release_id` and `manifest_sha256`." The analysis contract §8 adds
"nothing else identifies its input". When that was written an analysis bundle was the only thing a
release could be. Under `crosscorpus-release/v1` a bundle is a **projection** of a release, and
the sentence is no longer complete; read literally ("nothing else") it contradicts the release
contract §10.1. It is replaced by:

> A study pins, per corpus, **the release** — `release_id` and `release_manifest_sha256`, the
> document digest of the release manifest — and, **where it reads analysis tables**, the
> `manifest_sha256` of that `crosscorpus-analysis/v1` bundle (`inputs[].analysis_layer`). The
> frozen ids of its population are pinned by the digest of the study-population manifest.

- The two digests are different things with different names and neither stands in for the other:
  `release_manifest_sha256` identifies a corpus state and is recorded only by what refers to the
  manifest; the bundle's `manifest_sha256` is the bundle's own seal over its release record
  (`analysis_contract.seal`) and stays as it is.
- A projection never contains the digest of a release manifest that names it.
- There is one definition of study pinning: contract §10.1. CPD-0008 and the analysis contract
  point to it.

### 3. Release ids

`corapan-YYYY-MM` and `coprepan-YYYY.n` stand side by side; only the corpus prefix is shared
(contract §5.4). `naming.is_release_id` is unchanged and stays the rule for CO.PRE.PAN's own ids;
the shared, wider form is checked by `release_contract`. A suffix beginning with `0000` marks a
fixture — the convention of CPD-0008.

### 4. Terms

A release, an export, a release freeze, a projection, a package and a study population are
different things, and none of them is the acquisition baseline freeze (O-12), the legacy freeze
manifest, a software release or the test suite `release_gate`
([terminology](../architecture/TERMINOLOGY_AND_NAMING.md) §15).

### 5. Contract §16 Q1 — a technical recommendation, not a joint decision

Question: may a `release` be frozen while token counts are `not_available`?

**Recommendation: yes** (the draft's position), on the evidence of both contracts:

- A release is an identity and a fixity statement about a corpus state. Whether that state has
  been annotated is a different statement, and the contract already keeps them apart at three
  levels: `token_denominator_state`, `tokens_counted_state` in documents, coverage and totals, and
  `analysis_layer.state`.
- The contract forbids the one thing that would mislead: a count without the shared denominator
  (§5.2 rule 2), and a partial sum reported as a total (§7.3). Both are enforced and tested.
- Requiring counts would forbid a release of either corpus today — CO.RA.PAN has no token export,
  CO.PRE.PAN no annotator — and would make a release wait for a derived layer.
- The cost is declared: such a release supports no rate. A study over it has `not_available`
  totals, and a cross-corpus rate needs `known` counts on both sides.
- Counts that arrive later arrive in a **later release**; a frozen release is not completed in
  place.

Status: `TECHNICAL_RECOMMENDATION_READY` · `JOINT_DECISION_OPEN`. The question is listed as joint
and scientific; CO.PRE.PAN does not close it alone.

## Alternatives considered

| Alternative | Why not |
|---|---|
| import or port CO.RA.PAN's checks | one implementation twice proves nothing about the contract text |
| keep CPD-0008 §7 and read "manifest" as the release manifest | the bundle's seal has that name and is a different digest; two meanings under one name |
| rewrite CPD-0008 in place | a record is immutable once active; an amendment is a new decision |
| drop the bundle's own `manifest_sha256` | the bundle is self-contained on purpose; the handoff asks for no change |
| pin status `ADOPTED` here | it is a joint state |
| close Q1 here | joint and scientific by the contract's own listing |
| correct the points of §8 of the run report in the local copy | the copy is never edited; they are proposals to the canonical home |

## Consequences

- Stage 12 keeps `PARTIAL`; it now holds two contracts: analysis (CO.PRE.PAN's proposal) and
  release (CO.RA.PAN's draft, adopted here).
- O-6 is not closed. Its release and freeze semantics have a joint draft that both sides
  implement; adoption by CO.RA.PAN and the joint points are open.
- Nothing here blocks or enables acquisition. No gate of `docs/STATUS.md` §5 changes.

## Not decided here

- The joint freeze of the contract; CO.RA.PAN's adoption record.
- Contract §16 Q1 (jointly), Q3, Q5–Q10.
- The places where the two implementations read the text differently beyond the vectors, and the
  points the text leaves open (run report §8): they are proposals to the canonical home.
- Any release, selection policy, distribution target, licence, access level or identifier.
