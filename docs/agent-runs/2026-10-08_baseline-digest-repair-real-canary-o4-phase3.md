# Baseline digest defect repaired; real five-outlet canary, O-4 and the Phase-3 review package

```text
run_started_at:      2026-10-08 (evening, Europe/Berlin; first measured instant: the freeze of the second baseline, §4)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: IN PROGRESS** — this report is written while the run goes on; the status line is set at the end.

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

Sections on the canary, the verification, O-4, the disarming and Phase 3 follow below as the run proceeds.
