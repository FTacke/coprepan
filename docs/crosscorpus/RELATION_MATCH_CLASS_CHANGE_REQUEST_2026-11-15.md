# Change request to `crosscorpus-analysis/v1` §5.6 `relations`: an optional, versioned match class (2026-11-15)

**Status: PROPOSED BY CO.PRE.PAN — NOT APPLIED, NOT ADOPTED.** The analysis contract is CO.PRE.PAN's proposal whose adoption is a
joint decision with CO.RA.PAN (O-6); a field added to a table schema is therefore asked for, not made. The pinned joint release
contract `crosscorpus-release/v1` defines no relations table and is not concerned. CO.RA.PAN is not changed. Decision on
CO.PRE.PAN's side: [CPD-0040](../decisions/CPD-0040_phase3-repair-title-surface-agency-roles-text-match-and-blind-control.md).

## What is asked

In §5.6, after `basis`, two optional fields of a relation row:

| Field | Value |
|---|---|
| `match_class`° | `exact` · `near_identical` · `contained` — the kind of textual match the relation rests on, where a text comparison made it |
| `match_rule`° | the versioned rule that assigned it (CO.PRE.PAN: `text-reuse/2`) |

with the validator rule: `match_class` is given exactly when `match_rule` is; both are absent for a relation that is not made by
a text comparison (`earlier_version_of`, an identity relation). The relation vocabulary (`duplicate_of` · `syndicated_copy_of` ·
`earlier_version_of`) is unchanged.

## Why

`duplicate_of` / `syndicated_copy_of` say *that* two documents carry the same text, not *how far*: on CO.PRE.PAN's 4,759 stored
pages, of 192 cross-outlet relations 9 are the same text word for word, 102 nearly the same (another opening or close, quotation
marks, a sentence) and 81 a text contained in a longer one (study record of CPD-0040). For a linguistic study the difference
decides whether a pair may be treated as one text. Today the class travels only inside the free-text `basis`
("`text-reuse/2: exact -- …`"), which a study cannot select on.

## What does not change

No relation kind, no direction rule (the target is the earlier document in the corpus — an order of appearance, never a finding
of origin), no surface, no denominator. A relation without the two fields stays valid. Until the request is adopted, CO.PRE.PAN
writes the class into `basis` and keeps the full record (both containments, counts) in its own `text-reuse/2` relation.
