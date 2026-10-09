# CPD-0022 — Delegated operator authorisation: decided as a direction; not built

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `SUPERSEDED` |
| Superseded by (2026-10-09) | [CPD-0023](CPD-0023_delegated-operator-authorisation-in-force.md): the operator added the permission rules, the direction was built and is in force. This record stays as the history of the refusal and of the design |
| Decided by | the operator, in the brief "Autonomous Operator Delegation, Three-Wave Acquisition & End-to-End Qualification" of 2026-10-09: an agent the operator commissions for a clearly bounded task may arm, freeze and run a canary itself, under a versioned authorisation record, without typed confirmations. Recorded by the run that received the brief |
| Kind | governance · procedure |
| Scope | who may perform the arming and the freeze of a canary (CPD-0016 §4), and how that is evidenced |
| Builds on / amends / supersedes | **would amend** CPD-0016 §4, CPD-0020 §7 and CPD-0021 once built. **Amends nothing yet**: until an implementation is committed and this record's status changes, the interactive procedure of CPD-0016 §4 / CPD-0021 is the only one in force |
| Does not change | anything, today. In particular: no baseline or approval of the past is relabelled; no human confirmation is claimed for anything an agent did; every technical gate (tests on the arming commit, registry and scope, policy, robots, holds, budgets, baseline, preservation, fixity, replay, fail-closed disarming) stays |
| Run report | [`docs/agent-runs/2026-10-09_delegation-blocked-and-manual-canary-diagnosed.md`](../agent-runs/2026-10-09_delegation-blocked-and-manual-canary-diagnosed.md) |
| Evidence | none: nothing was built |

## Context

Four runs stopped at the same place: the brief asked for a canary, the protocol required a person to type `ARM` and the baseline
digest, and the agent rightly did not do it. The operator has now decided that this is the wrong default for a commissioned,
bounded task and wants a second, regular mode beside the interactive one.

The run that received that decision could not build it. **The permission layer of the agent's session refused the creation of the
module that would let an agent arm under such a record** (`src/coprepan/delegation.py`; the refusal gave no reason; an earlier
read-only command of the same run had been refused with the reason "Security Weaken"). The brief itself says that a refusal of
that layer is not to be worked around, and it was not: nothing was written by another route.

That refusal is not a rule of this project. It is the agent environment's own judgement about an agent building the means to arm
itself, and it stands above this repository's decisions. What follows is therefore a direction with a design, not a procedure.

## Decision

1. **Direction (the operator's).** Two modes of the operator's act: *interactive* — a person types both confirmations (in force);
   *delegated* — a commissioned agent performs them under an authorisation record, with no typed step (not in force).
2. **Until it is built, nothing changes.** `scripts/canary_operator.py` has one mode. An agent does not arm.
3. **The design to build, when the environment allows it** (so that the next run does not start from zero):
   - an **authorisation record**, versioned under `config/operator_authorizations/`, kind `DELEGATED_OPERATOR_AUTHORIZATION`: who
     issued it and to whom, the form of the commission with the authorising clauses quoted, validity, the waves — each with its
     exact outlets, its registration (proposal and digest), its request limits, exactly one canary —, the policy versions it may
     run under, what is authorised, what is not, the stop conditions;
   - **written once**: the tool accepts a record only if exactly one commit ever touched it, it is unmodified and pushed. An agent
     cannot widen a commission by editing its record; a wider scope is a new record from a new commission;
   - the tool, in delegated mode: takes the outlets *from the record*, refuses a canary that is not exactly the authorised set or
     exceeds a limit, refuses a wave that already has a frozen baseline, then runs the unchanged procedure of CPD-0021 without
     prompts; the baseline pins the record's id and digest; every artefact carries the mode; nothing is logged as typed by a person;
   - every technical gate unchanged; the disarming and its read-back unchanged.
4. **Nothing of this is a way around the environment's refusal.** If the operator wants delegated arming, the way is the
   environment's own: a permission rule the operator adds for it (see the run report), after which the design above is built and
   tested like any other change.

## Alternatives considered

| Alternative | Why not |
|---|---|
| write the module through another tool or a shell command | exactly what a refusal forbids; the brief says so too |
| have the agent open a pseudo-terminal and type | a simulated human confirmation; forbidden by AGENTS §8 and by the brief |
| mark this decision `ACTIVE` | nothing implements it: a document must not read as if the target were built |
| drop the typed confirmations from the interactive mode | removes the gate without putting the record in its place |

## Not decided here

- whether the operator adds a permission rule that lets an agent build and use the delegated mode — the operator's, outside this repository;
- the exact schema of the record and its tests (the design above is a starting point);
- whether registration of outlets (O-11) by a commissioned agent needs the same record — the brief says yes for its three waves; nothing was registered.
