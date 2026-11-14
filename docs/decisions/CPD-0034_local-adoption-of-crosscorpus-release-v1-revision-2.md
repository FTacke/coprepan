# CPD-0034 — CO.PRE.PAN's local adoption of `crosscorpus-release/v1` draft revision 2, renewed

| Field | Value |
|---|---|
| Date | 2026-11-14 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the commissioned agent of the run of 2026-11-14, under the operator's brief "CO.PRE.PAN_v3 – Umfassender Architektur-, Storage-, Contract- und Acquisition-Readiness-Run", which authorises the compatible local adoption of the current joint revision when it needs no new joint normative decision and only after an independent conformance check ("keine bloße Änderung eines Pins ohne erfolgreiche unabhängige Konformitätsprüfung"). The run set the conditions: revision 2 taken over verbatim from the canonical home, this repository's own checks made to conform to its text, the pin moved **only if every case and every pattern vector passes**, the local adoption renewed (CONTRACT §17). Implemented by a sub-run of that run; subject to the operator's review. **It binds CO.PRE.PAN only** |
| Kind | architecture |
| Scope | which draft revision of the joint release contract CO.PRE.PAN works against; the conformance of its own implementation of the checks with that revision |
| Builds on / amends / supersedes | builds on CPD-0011, CPD-0012. **Supersedes in part CPD-0012**: its adoption record (revision 1, bundle `4fb72acf…dbbe0`, 52 cases) is replaced by the adoption record below; CPD-0012 §1–§5 stand unchanged |
| Does not change | the bundle (never edited here; a verbatim copy); the joint status of the contract (`DRAFT`, not jointly adopted); CPD-0012 §2 (what a study pins), §3 (release ids), §4 (terms), §5 (the recommendation on Q1); CPD-0011 (the native export object); the analysis contract (CPD-0008); anything in CO.RA.PAN; any gate |
| Run report | [`2026-11-14_coprepan-architecture-storage-contract-and-acquisition-readiness.md`](../agent-runs/2026-11-14_coprepan-architecture-storage-contract-and-acquisition-readiness.md) §5.8 (the record was written by a sub-run of that run, which writes no report of its own) |
| Evidence | `tests/test_release_contract.py` against the pinned revision-2 bundle: the bundle digest recomputed by this repository's `release_contract.bundle_digest`; every `canonical_json`, `record_sets` and `fixtures` digest; **all 93 cases** give exactly their expected set of codes; **all 30 pattern vectors** give their verdict; the two new operations `set_json` and `refreeze` executed as the vectors' note describes them. `tests/test_release_export.py`. Measured 2026-11-14 on one workstation (counts: §Evidence below) |

Validation debt: conformance on synthetic fixtures only, as under CPD-0012. No release of real CO.PRE.PAN exports has been
checked (handoff gate PG4). Listed in `docs/STATUS.md` §6.

## Adoption record

| | |
|---|---|
| Contract | `crosscorpus-release/v1`, **draft revision 2** (status in the canonical home: `DRAFT`, second revision, **not jointly adopted**) |
| Bundle digest | `429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255` |
| Bundle taken from | CO.RA.PAN, commit `374d2e44eaf78f51bbbd2261113bd03d8c1fcdd2` (2026-10-08), read-only: every file taken from its git blob, its blob id and SHA-256 checked, the tree digest recomputed here |
| Copy and pin | `contracts/crosscorpus-release-v1/` (49 files, LF, `-text`; 8 files differ from revision 1: `CONTRACT.md`, `conformance/VECTORS.json`, six schemas whose `text` pattern was rewritten into the portable subset; the fixtures are unchanged); `config/crosscorpus/contract_pins.json` (`revision: 2`; revision 1 kept under `previous_revisions` with CPD-0012) |
| CO.PRE.PAN implementation | `src/coprepan/release_contract.py`, `src/coprepan/release_export.py` at the commit that introduces this record |
| Earlier revision | revision 1, bundle `4fb72acf27abf09b29dba9de22b241471d0eb5fde3c9e75cc638d646426dbbe0`, CO.RA.PAN `0a5f41dec`: adopted locally by CPD-0012. That adoption **does not carry over** (contract §17) and is not extended by this record; it is renewed |

**This is CO.PRE.PAN's local adoption and nothing more.** The bundle stays a `DRAFT` and is **not jointly adopted**. The
joint adoption — contract §14.3 step 3: both projects have recorded their adoption against one bundle digest and the pin
status in both repositories becomes `ADOPTED` — is a separate, joint act. CO.RA.PAN has recorded no adoption of revision 2
(its D93 is a position on Q1, not an adoption). The pin here stays `DRAFT`.

## Context

CO.PRE.PAN pinned and adopted draft revision 1 on 2026-10-08 (CPD-0012). The same day CO.RA.PAN, the canonical home,
settled the points on which the two independent implementations had read the text differently, and the points the
first text left open, as draft revision 2 (contract §15 T13–T22, §17), and pinned it. From then until today the two
repositories named different digests (found by the consistency audit of 2026-10-22). The contract's §17 says that a local
adoption quoting an earlier digest does not carry over and is renewed against the revision in force; CO.RA.PAN's handoff
(`docs/crosscorpus/HANDOFF_COPREPAN.md` §8 there) listed where this repository's checker was expected to differ.

## Decision

1. **CO.PRE.PAN works against draft revision 2.** The copy is revision 2's bundle, verbatim; the pin names its digest.
   Code reaches it only through `release_contract.load_contract`, which refuses any other copy (CPD-0012 §1, unchanged).
2. **The local adoption is renewed against `429f55eb…2255`** on the evidence below. It replaces CPD-0012's adoption record
   for what is in force; CPD-0012 stays the record of the revision-1 adoption.
3. **The checks follow the contract text, not the vectors.** The changes needed for revision 2 implement its normative
   rules; no vector is special-cased:
   - §12 / T13: a schema `pattern` is translated from the portable subset into an expression with the subset's own
     meaning (`^`/`$` the very start and end; `\s` exactly the 25 White_Space code points, `\S` every other); a pattern
     outside the subset makes the schema refused (`translate_pattern`, `pattern_matches`, `PatternRefused`);
   - §13.1 / T14: a named release is identified first — its manifest read as a document, then corpus, id and digest
     compared (`RELEASE_PIN_MISMATCH` and nothing else when they differ) — and checked second, its own codes reported;
     a pinned record set is read in one step (exists, parses, its pin names this contract's record schema, schema,
     pin), the first failing of these being the objection of the set;
   - §9.1 / T16: a freeze record beside a `provisional_export` is `FREEZE_MISMATCH` by its existence and is not read;
   - §7.2 / T17: a cohort is known exactly when its date is, and otherwise has the date's state;
   - §10.3 / T18: a declarative selection has exactly one filter per input;
   - §7.3 / T19: the sum over no documents is known zero, except `tokens_counted` without a known denominator (that
     state) and `audio_ms` in a written release (`not_applicable`) — for release totals, study totals and the builder;
   - §11.3 / T20: containers of fetched pages (`.warc`, `.warc.gz`, `.arc`, `.arc.gz`, `.cdx`, `.cdxj`) are refused by the
     check, like source media, after full case folding; the builder now uses the contract's list.
   Already conformant before: T15 (a record of an unpinned release is `POPULATION_NOT_RESTORABLE`), full case folding
   (`str.casefold`) and listed paths that differ only by case (`PATH_INVALID`).

## Evidence

Measured 2026-11-14 in the run's worktree, on one workstation:

| Measurement | Result |
|---|---|
| bundle digest of the copy, recomputed with this repository's `bundle_digest` | `429f55eb1992be7adf230b501e9ecf80ba944478b3a91a31943f3cfef9442255` (equal to CO.RA.PAN's pin) |
| the 49 files against CO.RA.PAN's blobs at `374d2e44e` | 49 of 49 identical (git blob id and SHA-256) |
| revision-2 vectors with the revision-1 checker (before the change, for comparison) | 84 of 93 cases, 29 of 30 patterns: the nine cases and the one pattern of point 3 differed |
| revision-2 vectors with the changed checker | **93 of 93 cases, 30 of 30 pattern vectors** |
| `tests/test_release_contract.py` + `tests/test_release_export.py` | 312 passed |
| full suite `python -m pytest -q tests` | before (revision 1, unchanged checker): 1706 passed, 14 skipped; after: 1834 passed, 14 skipped |

## Alternatives considered

| Alternative | Why not |
|---|---|
| keep revision 1 and CPD-0012 | the two repositories would keep naming different digests; a joint adoption needs one |
| move the pin first and fix the checker afterwards | the pin is moved only on a passing run (handoff §8.5; the brief) — a pin the code does not pass is a false claim |
| make the failing cases pass by special-casing them | proves nothing about the text; the vectors are written from the text and the checker must be |
| hand `\s` and `$` to Python's `re` as they are | contract §12 forbids it: Python's `$` accepts a trailing line feed, its `\s` includes U+001C–U+001F |
| treat this as the joint adoption, or set the pin `ADOPTED` | it is a joint state (contract §14.3); CO.RA.PAN has recorded none |
| rewrite CPD-0012 to quote revision 2 | a record is immutable once active; the renewal is a new decision |

## Consequences

- The pins of both repositories name revision 2. Contract §14.3 step 3 (both adoption records quoting one digest, both
  pins `ADOPTED`) now needs only CO.RA.PAN's adoption record and the joint act; neither is made here.
- Stage 11 (release) and stage 12 (cross-corpus contract) keep `PARTIAL`; nothing is validated or activated. No release
  of the corpus exists or can be built (no extractor is adopted).
- Nothing here blocks or enables acquisition. No gate of `docs/STATUS.md` §5 changes.

## Not decided here

- The joint adoption of the contract (§14.3 step 3); CO.RA.PAN's adoption record.
- Contract §16 Q1 jointly (stated in §9.5, joint only with the adoption), Q3, Q5–Q12; in particular Q11 (a grouping key
  for the versions of one work), which CO.PRE.PAN is asked to propose.
- Q12 for CO.PRE.PAN's own exports (whether a preserved copy of an export must be byte-identical to the export a release
  names).
- Any release, selection policy, distribution target, licence, access level or identifier.
