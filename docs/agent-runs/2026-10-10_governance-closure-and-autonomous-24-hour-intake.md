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

## 5. The short integrated canary of the controller (`in1-20261010-pilot`)

Under `DIA-2026-10-10-1` (`config/intake/authorizations/2026-10-10_pilot.json`): six outlets (`ar_el_tribuno`, `cr_la_nacion`,
`cu_havanatimes`, `hn_criterio`, `uy_montevideo_portal`, `ve_efecto_cocuyo`), eleven channels, 30 minutes, cycles of ten minutes, at most
150 requests. Started by `scripts/intake_operator.py start`: armed in `8d858ac`, full suite on the arming commit, baseline `e5c9b558…`
frozen in `29c6d57`, preflight `READY`, state written at 2026-10-10T08:20:47Z (10:20:47 local), scheduled task registered and started.
The session did nothing further: the task ran the controller, finalized, disarmed (`10fe6fd`) and removed itself at 08:50:07Z.

| | |
|---|---|
| outcome | `COMPLETED`, verification `PASS` (seven checks) |
| cycles, runs, restarts, outlet errors | 3, 3, 0, 0 |
| requests | 46 of 150: 21 item (three redirect hops among them), 25 other |
| fetch records, answers | 40, all `200`, all `RAW_PRESERVED`, 40 bodies read back from the preservation root and their digests compared |
| item pages 2xx | 18, three of each outlet; all technically usable under the experimental extractor |
| last request decided | before 08:49:17Z, 90 seconds before the deadline 08:50:47Z; none at or after it |
| recovery diagnosis after the run | `CLEAN`, identity `CORRECT` |
| disarming | `disabled` in the file, in HEAD and on `origin/main`; the task is gone |
| anomaly flags | `hn_criterio`: three pages `very_short_text` and `duplicate_body_of_other_document` (median 347 body characters) — the known case |

What it showed:

- **No page of the 18 is "new".** All 327 candidates first listed were dated before the start by their channels; in half an hour that is
  what is to be expected, and the measurement says so instead of counting first sightings as new articles.
- **A cycle is slow by design.** With ten seconds between requests to one origin and outlets served one after another, the first cycle
  took 4 min 41 s for six outlets (about 47 s each). For 87 outlets that is about an hour: the hourly polls of the 24-hour intake will in
  effect be spaced by the length of a cycle, an hour or somewhat more. Not changed: it is the price of one request at a time per origin
  without concurrency in the workspace.
- **Not tested for real: a killed controller.** Ending the controller's process from this session was refused by the permission layer of
  the agent's environment and was not attempted another way. The restart is qualified offline (a process that ends mid-cycle, a process
  that ends between receiving and preserving, a second process holding the lock) and by the task having started the controller.
- Nothing was repaired after the pilot: no defect was found. The code of the 24-hour intake is the code of the pilot.

Report of the pilot: `docs/intake/reports/in1-20261010-pilot/` (imported by `import-report`).

## 6. Launch of the 24-hour intake (`in1-20261010-24h`)

| | |
|---|---|
| intake id | `in1-20261010-24h` |
| authorisation | `DIA-2026-10-10-2`, `config/intake/authorizations/2026-10-10_24h.json` (`DELEGATED_INTAKE_AUTHORIZATION`; no typed confirmation) |
| plan | `config/intake/plans/in1-20261010-24h.json`, SHA-256 `dc313e20ecf2ce2a2de46dbe4dca0d9b4aa8197d34d975eba0f6ed508ec94cc0` |
| scope | 87 outlets (85 tier A, 2 tier B), 121 channels, 20 countries; `es_el_pais`, `co_el_tiempo`, `mx_la_jornada` not in it; no held origin or URL in it |
| arming commit (pinned) | `c1bba1b`; full suite on it: 1569 passed |
| baseline | `docs/intake/BASELINE_FROZEN_2026-10-10_in1-20261010-24h.json`, digest `4d7816d9477c9c8afdc4c640cfa08efc049dbb8bd201ffe58294c063cdb486da`, commit `284b99d` |
| preflight | `READY` |
| **started** | **2026-10-10T08:59:45Z — 10:59:45 Europe/Berlin** |
| **deadline** | **2026-10-11T08:59:45Z — 10:59:45 Europe/Berlin**; no request is decided after 08:58:15Z |
| status at launch | `RUNNING`; the scheduled task `coprepan-intake-in1-20261010-24h` started the controller at 08:59:48Z |

Budgets (ceilings, enforced at the transport, counted from the fetch records): 120 item requests per outlet, 10 per outlet in any
hour, 150 per origin, 12 000 requests in all — redirects, robots files and channel documents included. Per cycle an outlet is asked
for at most three pages, at most one of them stock. Polls: feeds and news sitemaps hourly, listings every 2 h, sitemap indexes and
large sitemaps every 6 h, the three archive-sized only channels (`cu_juventud_rebelde`, `pe_elperuano`, `py_ultima_hora`) every 12 h.

## 7. What runs without this session, and where to look

- **The task** `coprepan-intake-in1-20261010-24h` (Task Scheduler, the logged-in user, every five minutes) is the controller while the
  intake runs and, after the deadline, the finalizer: preserve, verify, receipt, measurement, anomaly flags, review package, report,
  disarm (one commit of `config/acquisition_policy.json`, a plain push), remove itself.
- **State and logs:** `<RUNTIME>/intake/in1-20261010-24h/state.json`, `controller.log`, `tick.log`.
  `python scripts/intake_operator.py status --intake in1-20261010-24h` prints the state with the remaining time.
- **The final report** will be in `<RUNTIME>/intake/in1-20261010-24h/report/` (`FINAL_REPORT.md`, `receipt.json`, `measurement.json`,
  `review_package.json`). `python scripts/intake_operator.py import-report --intake in1-20261010-24h` copies it to
  `docs/intake/reports/in1-20261010-24h/`; committing it is a person's step.
- **To stop early:** `python scripts/intake_operator.py stop --intake in1-20261010-24h`, or set the switch to `disabled` in the
  policy file — it is read before every request.

## 8. Known limits at launch

- **The task runs in the logged-in user's session.** A locked screen is fine; a log-off or a shutdown pauses the intake. The deadline
  still binds: after it nothing is requested, and the finalizer and the disarming run at the next log-on. **Until then the switch stays
  `enabled` in the repository** — if the machine is to be off at the deadline, run `stop` first.
- **The repository is armed for 24 hours**: `external_acquisition` is `enabled` in HEAD and on `origin/main` from `c1bba1b` until the
  finalizer's disarming commit. Commits of documents are possible meanwhile; a change under `src`, `scripts` or `config` blocks the
  intake at the next start of its controller, and a change of a pinned file at its next request.
- **If someone pushes between now and the end**, the disarming commit is made locally and its push may be refused; the tool does not
  force. The file on disk is `disabled` either way; `tick.log` and the final report say what happened.
- **A cycle takes about as long as its interval** (§5): "hourly" means once per cycle.
- **A killed controller** was not tested on a real run (§5).
- The pilot's six outlets were polled an hour before the start; what they listed then counts as known before the intake.

