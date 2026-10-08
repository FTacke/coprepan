# Baseline digest defect repaired; real five-outlet canary, O-4 and the Phase-3 review package

```text
run_started_at:      2026-10-08 (evening, Europe/Berlin; first measured instant: the freeze of the second baseline, §4)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: BLOCKED** (at the canary's `run` command, by the session's permission layer; §5). Done before it: the
digest defect diagnosed and repaired, the baseline frozen on the repaired commit, the preflight `READY`.

**What the status does not claim.** No request was made to any publisher. There is no canary result, no O-4
measurement, no Phase-3 sample or package. The repair is reproducibility evidence about a verification function,
nothing else. **`external_acquisition` is still `enabled`** (§6).

**Kind of run:** diagnosis and repair of a defect (verification of a frozen baseline), then the activation of the
bounded canary the operator armed, its verification and measurement, then the preparation of a human review.

## 1. Starting state (measured)

| Item | Value |
|---|---|
| `HEAD` = `origin/main` | `7e3b59a80600faa6205234a305dbc1be19b9f5fb` ("Canary baseline frozen (O-12, canary scope)"), tree clean |
| armed commit of the operator, `P` | `1f59e0149d5c69804d65f0e71dc5cd7fa06dec08` — the operator turned the switch personally; `7e3b59a` adds only `docs/canary/BASELINE_FROZEN_2026-10-08.json` |
| `external_acquisition` | `enabled` (operator's act; not touched by this run until the disarming) |
| preflight as the operator found it | `NOT_READY`, one failure: `no_configuration_drift` — "the approved baseline does not match its own digest" |
| requests to any publisher so far | none |

## 2. The defect: root cause (measured, not assumed)

`freeze.build_manifest` computed `manifest_sha256` over the whole manifest, **including `state`**, at a moment when
`state` is `READY_TO_FREEZE`. `freeze.freeze` then returned the manifest with `state = FROZEN` and a `freeze` record.
`freeze.verify_manifest` excluded `manifest_sha256` and `freeze` from what it hashed — but not the changed `state`. A
frozen manifest therefore could never match its own digest. Both the preflight (`canary.py`) and the driver's own
precondition (`canary_driver.py`, "a frozen manifest that verifies") call that function: no frozen baseline could ever
have started a canary.

Measured on `docs/canary/BASELINE_FROZEN_2026-10-08.json` (read-only, a script in the session scratchpad):

| Hashed content | Digest | Equals the stored `f7ae73c3…5eaaf` |
|---|---|---|
| as the old verification hashed it (`state = FROZEN`, without digest and freeze record) | `79c6037a…a6cf` | no |
| the same with `state = READY_TO_FREEZE` | `f7ae73c3e9f0e7eeac31bbcf07f35e4ae186736327a5a05078994b5d1d75eaaf` | **yes** |
| with the freeze record included | `11901345…f4bc` | no |
| with `manifest_sha256` itself included | `dfac3dfa…3805` | no |

Ruled out by measurement: line endings (the file has 400 LF, 0 CRLF, no byte-order mark; the working-tree file is
byte-identical to the committed blob); encoding; a self-hash (the digest never entered its own input); a different
digest function between build and verification (both `sha256_bytes(canonical_json(…))`); a difference between the
scratch manifest and the frozen one other than `state` and the freeze record. The verification reads parsed JSON, so
the file's serialisation does not enter the digest at all.

Why it was not seen: no test verified a manifest *after* its freeze. The offline qualification of the driver calls
`run_canary` directly, below the command-line preconditions.

**The artefact of the operator was correct.** Its digest is the digest of the baseline it confirms.

## 3. The repair

`src/coprepan/freeze.py`, one function for build, freeze and verification:

- `manifest_digest` — hashes every field except `manifest_sha256` and the `freeze` record; a `FROZEN` manifest is
  hashed in the state it was confirmed in (`READY_TO_FREEZE`, the only state a freeze starts from).
- `verify_manifest` — the digest must match; a `FROZEN` manifest must carry a freeze record whose `confirms` is exactly
  that digest, with an operator and an instant, and nothing blocking; a manifest that is not frozen carries no freeze
  record.

What the freeze record's `operator` and `confirmed_at` are: an attestation beside the baseline, not part of its
identity. The digest does not cover them; the committed file does.

Not done: no stored digest was recomputed or edited; the preflight and its drift check are unchanged; no gate was
weakened.

Regression tests (`tests/test_readiness.py`, five):

| Test | Asserts |
|---|---|
| build → `READY_TO_FREEZE` → digest D → `freeze` command (confirm = D) → file written → file read → verified, digest D | the path the canary takes; a second freeze and a wrong confirmation are refused |
| change of protected content of a frozen manifest | operator, scope, creation instant, blocking, code commit, a policy hash, a component version, the digest, an added or removed field, the state: each fails |
| the freeze record | missing, empty, confirming another digest, without operator or instant: fails; a record on an unfrozen manifest: fails; a different operator name or instant: the baseline's digest is unchanged and verifies (stated semantics) |
| line endings | the same content written with LF, CRLF and as `record_json` reads back to the same digest — because the digest is of the parsed content |
| the first frozen baseline | hashed as the old check did: not its digest; under the repaired function: verifies as `f7ae73c3…` |

## 4. Commits, the superseded freeze and the new one

| | |
|---|---|
| first armed commit `P` | `1f59e01…` — **superseded as the canary's code commit**: the repair changed code |
| first frozen baseline | `docs/canary/BASELINE_FROZEN_2026-10-08.json`, digest `f7ae73c3…5eaaf`, pins `1f59e01`. **Kept unchanged as historical evidence; superseded** because of a technical defect of the verification, not of the artefact. No scientific or policy decision changed with it |
| repair commit = new pinned commit `P2` | `15ec1fdabf1b5e4e2cb3c4a05a978e57dff3bed0`; `external_acquisition` still `enabled` in it (unchanged file) |
| full suite | 1309 passed, 1 skipped — on the tree before the commit and again on the committed `P2` (the skip: a symbolic link cannot be created on this account) |
| second baseline, built on `P2` | `READY_TO_FREEZE`, no blocker, digest `96c271e373dc59dbbb8cccae9301556397e553041de71647f31bbd4dbed7863f` |
| frozen | `docs/canary/BASELINE_FROZEN_2026-10-08b.json`, same digest. The freeze command was executed by the agent of this run on the operator's brief; the freeze record says so. **`O-12_CANARY_BASELINE = FROZEN`** |
| preflight with it (`--commit P2 --tests-passed 1309`) | **`READY`**; `no_configuration_drift = PASS` ("unchanged since approval"); nothing open |

## 5. The canary: not started — the `run` command was refused by the permission layer

After the baseline commit (`HEAD` = `origin/main` = `e3a32c9143dacdb1749187fa70feb3240a194979`, tree clean, spool 0
pending, preflight `READY`) the driver's `run` command was issued once. **The session's permission layer denied it**
(reason given: `[Security Weaken]`). The denied command, exactly:

```text
PYTHONPATH=src python -m coprepan.canary_driver run --outlet bo_el_deber --outlet do_diario_libre --outlet hn_proceso_digital --outlet py_la_nacion --outlet ve_efecto_cocuyo --pinned-commit 15ec1fdabf1b5e4e2cb3c4a05a978e57dff3bed0 --approved-baseline docs/canary/BASELINE_FROZEN_2026-10-08b.json --tests-passed 1309 --required-free-bytes 21474836480 --receipt-dir <RUNTIME root>/canary
```

It was not retried in another form (no script wrapper, no other shell). Everything before it was allowed on the armed
checkout: diagnosis, tests, `baseline`, `freeze`, `preflight`, commits and pushes.

**No request was made to any publisher.** No start-state record, no receipt, no robots or research-TDM outcome, no
access-control observation, no preserved object exist. `EXTERNAL_API_USAGE = NONE`.

## 6. What therefore did not happen

| Step | State |
|---|---|
| canary, `verify`, `measure` | not run; Phase-2 canary `OPEN`; O-4 `OPEN`, `NOT_YET_MEASURABLE` |
| disarming | **not done, on purpose**: the canary the operator armed for has not run, and a disarming commit would change `config/` — the frozen baseline would no longer describe the checkout and the arming would have to be repeated with a third baseline. **`external_acquisition` is `enabled`** in `HEAD`, as the operator set it. Nothing in the repository makes a request by itself; a request needs the `run` command |
| Phase 3 | `PHASE3_GOLD_PACKAGE = NOT_BUILT` — there is no real material. Candidate wrappers were not written now either: code committed after `P2` would move `HEAD` beyond evidence files and the driver would refuse to start |
| `docs/STATUS.md` | **not updated in this run, on purpose**: between `P2` and `HEAD` only `docs/canary/` and `docs/agent-runs/` may differ (`verify_checkout`). STATUS still says that no baseline is frozen and that the switch is off; both are out of date until the run after the canary updates it. This report and the runbook carry the current state |

## 7. The one manual step

Run the command of §5 yourself (PowerShell: `$env:PYTHONPATH="src"` first), with `<RUNTIME root>` as configured on
the workstation. It repeats the preflight, writes the start-state record, and takes roughly 20–40 minutes. Then, as
in [`docs/canary/RUNBOOK.md`](../canary/RUNBOOK.md) §5–§6: `verify`, `measure`, and the disarming commit. Do not
commit anything outside `docs/canary/` and `docs/agent-runs/` before the run. If the canary is not going to be run
soon, disarm instead (set the switch to `disabled`, tests, commit, push) and arm again later with a new baseline.

Alternatively a permission rule that allows the agent that one command; verification, measurement, disarming and
Phase 3 can then be done by an agent run on the evidence.

## 8. Checks

| Check | Result |
|---|---|
| reproduction of the defect on the committed artefact | `verify_manifest` false; digests of §2 |
| `tests/test_readiness.py` | 33 passed (5 new) |
| full suite on `P2` | 1309 passed, 1 skipped |
| preflight, first baseline, repaired code, commit `1f59e01` (diagnostic only; not used) | all checks `PASS` — confirms the digest was the only failure |
| preflight, second baseline, commit `P2` | `READY` |
| storage status before the attempted start | `PRESERVATION`, `RUNTIME`, `SPOOL` `AVAILABLE`; 0 pending; `crosscorpus-storage/v1` `IN_FORCE` |

## 9. Files and git

Changed: `src/coprepan/freeze.py`, `tests/test_readiness.py` (commit `15ec1fd`). Created:
`docs/canary/BASELINE_FROZEN_2026-10-08b.json`, this report (`e3a32c9` and the closing commit). Changed in the closing
commit: `docs/canary/RUNBOOK.md` (status, the commit and the baseline to use). Nothing moved, deleted or overwritten;
`config/acquisition_policy.json` not touched; the first frozen baseline not touched. Reference repositories and
CO.RA.PAN untouched; no cross-corpus contract touched.

## 10. Gates

| Gate | State |
|---|---|
| O-12 (canary scope) | **`FROZEN`** — `96c271e3…7863f` on `15ec1fd` (evidence: §4) |
| preflight | `READY` |
| Phase-2 canary | `OPEN` — not run |
| O-4 | `OPEN` |
| `external_acquisition` | `enabled` (operator's arming, awaiting the run) |
