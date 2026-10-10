# CPD-0028 — Confirmation of the open points of CPD-0025, CPD-0026 and CPD-0027

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Status | `ACTIVE` |
| Decided by | the operator, in the brief "CO.PRE.PAN 3.0 – Governance Closure & Autonomous 24-Hour Intake" of 2026-10-10, which confirms the three points in its own words (quoted below) — two of them outright, one under a condition this record shows to be met. The review of the condition was made by the commissioned agent, read-only, and is tracked. **No confirmation typed by a person at a terminal exists for any of the three, and none is claimed.** |
| Kind | governance · confirmation record (forward-only) |
| Scope | the three decisions the earlier records left to the operator: the verification threshold (CPD-0025), the adoption of the rebuilt identity tables (CPD-0026), the scoped access policy as it applies to an intake (CPD-0027) |
| Builds on / amends / supersedes | builds on CPD-0025, CPD-0026, CPD-0027. Supersedes nothing and rewrites nothing: each of the three records keeps its text and gets a dated note pointing here |
| Does not change | any rule, threshold, table, hold or record. This record states who confirmed what, on which evidence |
| Run report | [`docs/agent-runs/2026-10-10_governance-closure-and-autonomous-24-hour-intake.md`](../agent-runs/2026-10-10_governance-closure-and-autonomous-24-hour-intake.md) |
| Evidence | [`docs/identity/identity_adoption_review_2026-10-10.json`](../identity/identity_adoption_review_2026-10-10.json) (the eight criteria); `tests/test_source_qualification.py` (the threshold); `tests/test_canary_findings.py`, `tests/test_research_tdm_policy.py` (the access policy) |

## Context

Three records of 2026-10-09/10 were taken by a commissioned agent inside a run and marked as awaiting the operator:

- **CPD-0025** lowered the floor of `ACQUISITION_VERIFIED` to three item pages for runs whose budget is four requests per
  outlet, and said so as a decision the run had taken itself;
- **CPD-0026** adopted rebuilt identity tables after a URL-rule amendment — a step the code reserves for a person
  (`identity_rebuild.adopt(replace_conflicting=True)`) — and said plainly that the operator's approval had not been given;
- **CPD-0027** changed what an observed access control holds, on the operator's brief, and left open how it applies to an
  intake and to the outlets it released.

The brief of 2026-10-10 addresses each. This record sets down what it says, what was checked, and what follows — without
turning a commission into a signature.

## Decision

1. **CPD-0025, the threshold — confirmed by the operator.** In the brief's words: three preserved, verified and replayed
   item pages of one bounded run are sufficient *as a minimal technical proof* that an outlet can be acquired.
   `ACQUISITION_VERIFIED` therefore says exactly that and no more. It is **not** evidence of operational stability, of
   extraction quality, of coverage, or of suitability for a release — each of those is a later stage with its own evidence
   (`OPERATIONALLY_STABLE` needs three verified runs on three days and is held by no outlet).
   - *Checked:* the rule is in one place (`scripts/build_intake_readiness.py`: five pages at a budget of ten or more, three
     below it), the tracked inventory is byte for byte what that builder gives, and
     `test_a_stage_claims_what_the_evidence_shows_and_no_more` asserts the floor for every verified outlet. A changed floor
     changes the inventory and fails the test: the semantics cannot drift silently.
   - *Tier B* (item pages preserved, fewer than the stage asks: two outlets) may take part in a bounded intake and stays
     tier B; taking part verifies nothing by itself.
2. **CPD-0026, the adoption of the rebuilt identity tables — confirmed under the operator's condition, which is met.** The
   brief authorises "die dokumentierte Übernahme des neuen kanonischen Zustands unter der Bedingung, dass diese Kriterien
   nachweislich erfüllt sind". The eight criteria were checked independently and read-only on 2026-10-10, against the tables
   that were moved aside (`identity.replaced-0`) and the tables in force:

   | # | Criterion | Finding |
   |---|---|---|
   | 1 | the old and the new tables exist | yes; the old ones are kept with their digests |
   | 2 | the difference is known exactly | one document row and one observation row, of one outlet (`uy_montevideo_portal`): the label `outlet_url_rules_version` v1 → v2, and on the observation the `requested_url_key` that now keeps the nameless query |
   | 3 | no document, observation or version is lost | none |
   | 4 | no documents were merged | no fetch changed its document; no document changed its URL key |
   | 5 | no identity was reassigned | every `document_id` and every `document_version_id` of the old tables is unchanged |
   | 6 | preservation and replay hold | workspace `CLEAN`; 847 `RAW_PRESERVED`, 11 `FETCH_FAILED`; no preserved master fails verification |
   | 7 | the rebuild is reproducible | rebuilding from the preserved evidence gives the tables in force (`CORRECT`, no row missing, none unsupported) |
   | 8 | a rollback is possible | the old directory is kept; moving it back restores the earlier state, and the rebuild then reports the same two rows |

   The tables in force are the canonical identity state. What this is **not**: a person's act at a terminal. The code's
   reservation stands for every future conflict — a rebuild that would change an id, merge documents or drop a row is not
   covered by this record and is not adopted by an agent.
3. **CPD-0027, the scoped access policy — applies to an intake, with three exclusions the operator names.**
   - The scope table of CPD-0027 §2 and the reading of a robots address of §3 are the rule of a bounded intake, as they are
     of a canary: the intake controller uses the same fetcher, the same gate and the same derivation of holds, and adds none
     of its own.
   - **El País (`es_el_pais`) stays excluded.** Five articles and then a CAPTCHA is a real control. No further request is
     made, and nothing is tried to find out when or how the control would not appear — no timing, no other route, no other
     client. The origin `https://elpais.com` is held and no intake plan may name the outlet.
   - **Efecto Cocuyo (`ve_efecto_cocuyo`)** takes part through its feed; its sitemap, which answered with a challenge, stays
     held as that URL.
   - **La Jornada (`mx_la_jornada`) and every other origin or URL that is held** stay deferred. A hold ends only by
     CPD-0027 §7.
   - `co_el_tiempo` is not part of any intake (standing instruction of the operator).

## Alternatives considered

| Alternative | Why not |
|---|---|
| rewrite the "Decided by" lines of CPD-0025 to CPD-0027 | a historical record says what was true when it was written; the confirmation is a later fact and gets its own record |
| record the operator's brief as a typed confirmation | it is not one. The brief itself forbids simulating a human approval; the record says "commission, condition, evidence" because that is what there is |
| confirm the identity adoption without re-checking it | the operator made the confirmation conditional; a condition nobody checked is not met |
| leave the three points open and start the intake regardless | an intake on an identity state nobody confirmed would add documents to tables under question |

## Not decided here

- whether El País is ever asked again: that needs the publisher's position and the institution's, not a technical step;
- the legal questions of CPD-0017 §5 and CPD-0027;
- the deferred hypotheses of CPD-0025;
- any activation of acquisition beyond a bounded, separately authorised run.
