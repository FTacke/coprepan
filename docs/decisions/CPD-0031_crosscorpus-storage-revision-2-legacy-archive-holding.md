# CPD-0031 — `crosscorpus-storage/v1` revision 2: the archive holding LEGACY taken over (available, not planned here)

| Field | Value |
|---|---|
| Status | **ACCEPTED, IN FORCE**: this repository pins revision 2 (bundle `49a3ca88c084eee26e40caa1dd987155bf8062c99c81d8cb734a7990a8afb036`, a verbatim copy of CO.RA.PAN's canonical home, commit `003ec84d524ec6e4791b3a248800850908e80434`) and its conformance suite reproduces every case |
| Execution | the contract and its decision functions are in force; **CO.PRE.PAN has no LEGACY holding**: none is configured, planned or created (topology `NOT_PLANNED`, storage index §20.3) |
| Decided by | the operator, in the brief "Cross-Corpus Storage — LEGACY-Archiv-Holding verbindlich einführen" of 2026-10-19 (run from the CO.RA.PAN repository with write scope over both): the holding is introduced for both corpora; CO.RA.PAN uses it, CO.PRE.PAN may later, without activation now |
| Sister decision | CO.RA.PAN D127 |
| Run report | CO.RA.PAN `docs/agent-runs/2026-10-19_crosscorpus-legacy-archive-contract-adoption.md` (joint) |

## Context

Revision 1 (CPD-0015) knew the holdings PRODUCTION and HISTORIC. CO.RA.PAN needs an institutional archive for the originals of its
superseded system (the legacy repository) and asked for an amendment that both corpora can use.

## Decision

1. Take revision 2 of the joint contract verbatim (the bundle is never edited here): the archive holding `LEGACY` (§2.3 A1–A9), its
   namespace `projects/panhispanic_media_corpora/legacy/<corpus>/<tree>` with the reserved segments `historic` and `legacy` (§5.2),
   the reference table `archive_tree` (§12, §13). The revision is additive; no state, code or invariant of revision 1 changed.
2. Implement the decision functions in this repository's own code (`src/coprepan/storage_contract.py`: `namespace` with
   `NamespaceRefused`, `archive_tree`) and reproduce every case (`tests/test_storage_contract.py`).
3. **No activation.** The press corpus's own legacy material (`legacy\coprepan` on the workstation, with its verified D: secondary of
   2026-10-15) stays where it is. CO.PRE.PAN's HISTORIC holding stays the place for the legacy press corpus as source material
   (contract §2.2); LEGACY would hold the superseded system around it.

## Not decided here

Whether CO.PRE.PAN archives anything as LEGACY, and when; its root, identity and backup. Any release of a local original (A7).
