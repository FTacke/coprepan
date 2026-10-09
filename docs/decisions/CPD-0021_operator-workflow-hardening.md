# CPD-0021 — The operator's canary workflow: what its review found, and what was changed

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Amended by (2026-10-09) | [CPD-0023](CPD-0023_delegated-operator-authorisation-in-force.md): beside the interactive mode described here, a commissioned agent may arm and freeze under a versioned authorisation record (delegated mode). This record is otherwise unchanged |
| Decided by | the operator, in the brief of the three-wave qualification run of 2026-10-09, which ordered the wrapper of CPD-0020 §7 examined on all its error paths before any real use, small repairs and regression tests, and no change of the gate protocol; the repairs are the run's technical choices. Subject to the operator's review |
| Kind | procedure · tooling |
| Scope | `scripts/canary_operator.py` only |
| Builds on / amends / supersedes | amends CPD-0020 §7 (the tool described there is this tool, changed). Supersedes nothing |
| Does not change | the gate: `ARM` and the baseline digest are typed by a person at a terminal, as CPD-0016 §4 requires; any check of the driver, the preflight or the policy; any budget |
| Run report | [`docs/agent-runs/2026-10-09_three-wave-qualification-prepared.md`](../agent-runs/2026-10-09_three-wave-qualification-prepared.md) |
| Evidence | `tests/test_canary_operator.py` (24): the whole procedure against a real temporary git repository with a bare remote, failures injected at every step |

Validation debt: the driver, the preflight and the test run were recorders in these tests. The first real
use of the tool is the first test of those joints.

## Context

CPD-0020 §7 gave the operator one command for the whole canary procedure. It had been tested only in its parts. The brief of the
three-wave run asked for the whole examined on every error path before it is used for real, since a wrapper that arms the checkout is
the one place where a defect leaves `external_acquisition` on.

## What the review found (each reproduced before it was changed)

| # | Defect | Effect |
|---|---|---|
| 1 | the test summary counted `"1380 passed, 2 errors"` as a pass | a canary could be armed and frozen on a tree with erroring tests |
| 2 | the disarming committed unconditionally | when the arming commit had not been made yet, `git commit` found nothing, and the tool reported "NOT DISARMED" for a checkout that was disarmed |
| 3 | one `except` for file, commit and push | a failed push read like a switch left on; the tool did not read the state back |
| 4 | a driver `run` that ended `INCOMPLETE_PENDING` (exit 1) stopped the tool | the receipt and the evidence of that run were not copied, verify and measure not run |
| 5 | no way back after a killed process (closed console, power cut) | the next start only said "the switch is not `disabled`" |
| 6 | SIGTERM / SIGBREAK ended the process without the disarming | the same |
| 7 | the scope was validated by the preflight, after the arming | a wrong outlet list armed the checkout and was refused afterwards |
| 8 | no tests on the disarmed tree (runbook §6) | the disarming was never held against the suite |
| 9 | `date.today()` read three times | a run over midnight would have looked for another baseline file |
| 10 | the tool could not be tested without the real checkout | the reason it was untested |
| 11 | found by starting the repaired tool from a shell with `< /dev/null`: on Windows `isatty()` is true for the `NUL` device, so the `ARM` prompt was shown to a stream that can only answer empty | harmless (an empty answer arms nothing) but the check did not check what it claimed; `is_console` now reads the Windows console mode |

## Decision

1. All ten are repaired in place; the tool is parameterised on the repository, the runner, the terminal and the day, so the whole
   procedure runs against a temporary repository.
2. **Before `ARM`:** the scope is pinned and printed — outlets, the budget (items per outlet and in all, requests per outlet, the
   ceiling), the channels each would read, the policy version — and an unregistered outlet, a duplicate or a wrong number
   (five, or six to fifteen) is refused without arming anything.
3. **After any outcome** the disarming runs when the switch has been touched, and reads back three states — the file, `HEAD`,
   `origin/main` — and reports each problem separately (file or commit; push; read-back). Exit codes: 0 done, 1 stopped or a
   result to look at, 2 not disarmed cleanly.
4. **`--disarm-only`:** turns the switch off, commits, pushes; starts nothing; takes no other argument. The only way back after a
   killed process, and the message every refusal on an armed checkout points to.
5. The tests run again on the disarmed tree; their result is reported, not a condition.
6. A run that ended incomplete keeps its receipt and evidence, is verified and measured, and ends with exit 1.

## Alternatives considered

| Alternative | Why not |
|---|---|
| leave the tool alone until its first real use | its failures are the ones that leave the switch on |
| make it confirm through a stronger channel (a code on a second device) | a redesign of the gate, which the brief excludes |
| let the tool resume a canary | a resume is the driver's, by hand; a second code path to duplicate requests |
| let the tool apply registration proposals | registration is the operator's review (O-11); one command would hide it |

## Limits, stated

- **A terminal is not proof of a person.** A program can open a pseudo-terminal and type. What the tool guarantees is that a
  confirmation cannot be *passed* (argument, pipe, file, script input: all refused, tested); that it cannot be *simulated* is
  what AGENTS §8 and the brief forbid an agent to do. No stronger mechanism is added: it would be a redesign of the gate.
- A console window closed with the mouse or a power cut kills the process without a handler; `--disarm-only` is the recovery.
- The tool does not resume an interrupted canary. A restart under the same baseline is the driver's (its budget is that of the
  evidence), run by hand as runbook §4 says; the tool refuses a second baseline of the same label and day.
- Not tested: real `pytest`, driver, preflight; the Windows console; a push to the real remote.

## Not decided here

Whether the tool should offer to apply a registration proposal; resuming a canary through it; a hook that makes AGENTS §5 mechanical.
