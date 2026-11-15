# Change request to `crosscorpus-release/v1`: the written unit kind `subtitle` (2026-11-15)

**Status: PROPOSED BY CO.PRE.PAN — NOT APPLIED, NOT ADOPTED.** A request to the joint contract, whose canonical home is the
CO.RA.PAN repository. The pinned bundle in this repository (`contracts/crosscorpus-release-v1/`) is not edited; CO.RA.PAN is not
changed. Decision on CO.PRE.PAN's side: [CPD-0039](../decisions/CPD-0039_text-surfaces-iptc-provenance-and-core-quality.md).

## What is asked

In contract §8 (*Anchors*), add `subtitle` to the written `unit_kinds` (subset of):

> `title`, **`subtitle`**, `heading`, `paragraph`, `list_item`, `quote_block`, `caption`, `unstructured_text`

and the same value to the check that refuses foreign anchor kinds (§13), with one conformance vector (a written release that
declares `subtitle` passes; a spoken one that declares it is refused).

## Why

CO.PRE.PAN's extraction now keeps the publisher's subtitle (bajada, standfirst) apart from the title and the BODY
(`extraction/2`, on 2,953 of 4,759 stored pages). In CO.PRE.PAN's analysis-contract proposal it is a unit of kind `subtitle` on the
existing surface `title`, never counted (`crosscorpus-analysis/v1` §5.4, amendment of 2026-11-15). For a study population to select
or exclude subtitle units **by id**, the release must be allowed to declare the kind as an anchor.

## What does not change

No surface, no denominator, no spoken vocabulary, no digest rule, no existing kind. A release that declares no `subtitle` is valid
under the revised contract as before. Until the revision is jointly adopted, CO.PRE.PAN's native export stays on `extraction/1`
(`release_export.py` refuses an `extraction/2` record) — fail-closed, so no release can carry a unit kind the pinned contract does
not know.
