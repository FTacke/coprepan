# Run report — Governance closure and the autonomous 24-hour intake

| Field | Value |
|---|---|
| Date | 2026-10-10 |
| Commission | the operator's brief "CO.PRE.PAN 3.0 – Governance Closure & Autonomous 24-Hour Intake" |
| Decisions | [CPD-0028](../decisions/CPD-0028_confirmation-of-the-open-points-of-cpd-0025-to-cpd-0027.md), [CPD-0029](../decisions/CPD-0029_the-bounded-timed-intake.md) |
| State of this report | written in two steps: before the pilot (§1–§4) and at the launch of the 24-hour intake (§5–§8). What the intake yields is not in it: that is the finalizer's report |

## 1. Starting state

HEAD `f7bf96d` = `origin/main`, tree clean, `external_acquisition` `disabled`. Workspace diagnosis `CLEAN`; ledger 847
`RAW_PRESERVED`, 11 `FETCH_FAILED`. Readiness `2026-10-10.1`: 87 outlets (85 tier A, 2 tier B), 121 channels, 20 countries;
10 origins and 9 URLs held.

## 2. Governance closure (CPD-0028)

- **CPD-0025, threshold:** confirmed by the brief as a minimal technical proof. The rule is in one place in the builder and
  asserted by `test_a_stage_claims_what_the_evidence_shows_and_no_more`; the tracked inventory is byte for byte what the
  builder gives.
- **CPD-0026, identity adoption:** the eight conditions of the brief were checked read-only against the tables moved aside
  on 2026-10-09 and the tables in force. Exactly one document row and one observation row differ (`uy_montevideo_portal`:
  the URL-rules label v1 → v2, and the requested URL key that now keeps the nameless query). No row is lost, no document
  merged, no id reassigned; workspace `CLEAN`; the rebuild from preserved evidence gives the tables in force; the old
  directory is kept. Evidence: `docs/identity/identity_adoption_review_2026-10-10.json`.
- **CPD-0027, access policy:** applies to an intake unchanged. `es_el_pais` excluded; `ve_efecto_cocuyo` by its feed only;
  every hold kept.
- Each of the three records has one dated row pointing to CPD-0028; nothing else in them was touched. No confirmation typed
  by a person exists for any of the three, and none is recorded.

## 3. What was built (CPD-0029)

| Part | Where |
|---|---|
| plan, intake authorisation and its check, baseline pin, budgeted fetcher, selection, controller, finalizer | `src/coprepan/intake.py` |
| measurement, anomaly flags, review package, final report | `src/coprepan/intake_report.py` |
| `plan`, `start`, `tick`, `status`, `stop`, `import-report`; the disarming; the scheduled task | `scripts/intake_operator.py` |
| two optional arguments of `run_http_acquisition`: `select_due` (which due candidates, in which order) and `tables` (the caller's loaded discovery tables) | `src/coprepan/http_acquisition.py` |
| tests | `tests/test_intake.py`, `tests/test_intake_operator.py` |

Nothing of the fetcher, the gate, robots handling, discovery, the pack, preservation, identity or extraction was
reimplemented; the controller calls them.

## 4. Offline qualification

`tests/test_intake.py` and `tests/test_intake_operator.py` against a loopback outlet whose feed changes from poll to poll, a
clock that does not wait, and a temporary git repository with a bare remote: the plan and what it leaves out; hourly polls;
what is new asked before stock, and stock held to one page per cycle; every budget, with refusals on record; the hourly
limit as a sliding hour; a redirect hop counted; the deadline and its margin; a machine that slept through the window; a
restart that keeps deadline and budgets and closes the cut run as `FAILED`; a process that dies between receiving and
preserving; one controller at a time (a second process holding the lock); a changed plan refused; a stop request; permission
withdrawn; the preservation target away and back; an outlet that becomes held; the finalizer's checks, its repeatability, a
damaged preserved pack; the authorisation and its ceilings; a record and a plan committed exactly once; what a restart
re-checks; the disarming (one file, nothing else, no force, a refused push reported, off `main`); a start refused before
arming; a whole tick; a tick on changed code; the anomaly flags.

## 4a. A commit with the wrong message

Commit `227d2d0` holds everything of §2 to §4 (21 files) and was pushed under a message that belongs to an older commit
("Operator's research supplement of 2026-10-09 …"): the message file of this commit could not be written over a file of the same
name left by an earlier run, and the stale file was used. The content of the commit is right; only its message is wrong. A pushed
commit is not rewritten here (no forced push); the commit that adds this section carries the message `227d2d0` should have had.
