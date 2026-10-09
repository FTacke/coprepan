# CPD-0023 — Delegated operator authorisation: built and in force beside the interactive mode

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief "CO.PRE.PAN 3.0 – Autonomous Acquisition: Safe Recovery, Delegated Operator & Three-Wave Execution" of 2026-10-09 ("Dieser Auftrag autorisiert ausdrücklich die eigenständige Durchführung der nachfolgend definierten Arbeiten und begrenzten Akquisitionswellen A, B, C1 und C2"; "Der Operator genehmigt den Scope; der Agent führt die darin autorisierten Arbeiten selbstständig aus"), after adding two `autoMode.allow` rules for this repository to his own Claude Code settings. The schema of the record and the checks are the run's technical choices, subject to the operator's review |
| Kind | governance · procedure |
| Scope | who may perform the arming and the freeze of a canary, and how that is evidenced |
| Builds on / amends / supersedes | builds on CPD-0022 (the direction and its design). **Amends, forward-only and for the delegated mode only:** CPD-0016 §4 (the arming and the freeze as a person's act), CPD-0020 §7 and CPD-0021 (the operator tool has one mode). Supersedes nothing: the interactive mode stays as those records describe it |
| Does not change | any technical gate — the tests on the arming commit, registry and scope, policy, robots, holds, budgets and the hard ceiling, baseline and digest, preflight, preservation, fixity, replay, the fail-closed disarming and its read-back. No baseline, receipt or approval of the past is relabelled: everything frozen before this record was armed and frozen by the operator in person and says so |
| Run report | [`docs/agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md`](../agent-runs/2026-10-09_autonomous-acquisition-recovery-and-three-wave-execution.md) |
| Evidence | `tests/test_delegated_operator.py`; `config/operator_authorizations/2026-10-09_waves-b-c1.json`; the baselines and receipts of the waves run under it (run report) |

Validation debt: in the tests the driver, the preflight and the test run are recorders. The first wave run under a record is
the first real test of those joints; the run report states how it went.

## Context

CPD-0022 recorded the operator's decision that a commissioned agent may arm and freeze a bounded canary under a versioned
record, and that it could not be built: the agent session's permission layer refused the module. That refusal was the
environment's, not this project's, and was not worked around. The operator has since added permission rules for exactly this —
the delegated-operator module, and the temporary arming for the bounded waves — and repeated the commission in a new brief.
With that the direction can be built.

Before it was built, the operator's own interactive second canary of 2026-10-09 completed (armed and frozen by the operator in
person). It is not part of any delegation and needs none.

## Decision

1. **Two modes of the operator's act.** *Interactive* — a person types `ARM` and the baseline digest at a terminal (CPD-0016 §4,
   CPD-0021); unchanged. *Delegated* — an agent the operator has commissioned performs both steps under an **authorisation
   record**, with no typed step. A canary is armed in one of the two modes and its artefacts say which.
2. **The authorisation record** (`config/operator_authorizations/<name>.json`, schema `coprepan-operator-authorization/v1`, kind
   `DELEGATED_OPERATOR_AUTHORIZATION`): id; who issued it and to whom; the form of the commission with the authorising clauses
   **quoted**; validity; the policy versions it may run under; what is authorised and what is not; the holds in force; the
   technical gates; the stop conditions; the duty to disarm; and the **waves** — each with its exact outlets, its registration
   (proposal and digest, outlets), its request limits and exactly one canary. A record is the agent's transcription of the
   operator's commission and says so; it adds nothing to the commission. Origins are not copied into it: they are those the
   named proposal registers, pinned by the proposal's digest.
3. **Written once.** The tool accepts a record only if it is tracked, exactly one commit ever touched it, the working tree is
   clean and `HEAD` is `origin/main`. A wider or different scope is a new record from a commission that grants it; an agent
   cannot widen a commission by editing its record.
4. **Exactly the wave.** The canary's outlets are the wave's outlets, no more and no fewer; no limit of its budget exceeds the
   wave's; the policy version is one the record names; the record is in date; the wave has no frozen baseline yet. The check is
   made three times — by the tool before arming, by the driver when it builds the baseline, by the driver again before the first
   request, against the record as it then is.
5. **The baseline pins the authorisation**: the record's id, its SHA-256, its path and the wave are part of the `canary` block and
   so of the baseline digest. The freeze names as operator the delegate *under* the record, with the mode. The start state and the
   receipt carry `operator_authorization`; the commit messages of the arming, the baseline and the evidence name the record. The
   digest remains what it was — an integrity control. Nothing is recorded as typed, confirmed or approved by a person.
6. **No switch for the gates.** The delegated mode takes `--authorization` and `--wave` and nothing else; the outlets, the label
   and the operator are the record's. There is no force, skip or budget option, in either mode.
7. **Registration under a record.** A wave may name the registration proposal (path and digest) and the outlets it registers;
   the agent applies it with `scripts/apply_registration_proposal.py`, naming the record as the approving authority. The tool
   refuses a wave whose proposal is not the one named or whose outlets are not registered.
8. **The agent environment stays above this.** A refusal by the session's permission layer is recorded and not worked around,
   whatever a record says.

## Alternatives considered

| Alternative | Why not |
|---|---|
| let the agent type the two confirmations, or accept them as arguments | a simulated human confirmation; CPD-0021 closed exactly that door and it stays closed |
| a general `--non-interactive` flag without a record | the gate would be gone with nothing in its place: no scope, no limit, no provenance |
| a record the tool reads from outside the repository or from an environment variable | not versioned, not reviewable, not pinned by a baseline |
| allow the record to be amended in place | an agent could widen its own commission; one commit per record makes that visible and refused |
| copy every origin into the record | a second, hand-copied source of truth beside the proposal; the proposal's digest pins them without transcription |
| rewrite CPD-0022 as `ACTIVE` | the record of the refusal and of the direction is history; a new record is the forward-only way |

## Not decided here

- whether delegation becomes the usual way to run a canary, or stays for commissions like this one — the operator's;
- any production activation: a record authorises bounded canaries only, and a canary's `PASS` activates nothing;
- wave C2 (articles of HTML listings under new allow rules): the brief authorises it under conditions and asks for its own
  versioned scope; it gets its own record once C1 has shown which outlets it concerns, or none if the conditions do not hold;
- who may write a record besides the commissioned agent, and whether the operator signs records in a stronger sense than a
  commit under his review (today: the record quotes the brief, and the brief is the operator's).
