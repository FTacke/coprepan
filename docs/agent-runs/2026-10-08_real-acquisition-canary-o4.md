# Real acquisition canary and O-4: not executed — stopped at the permission boundary of the arming step

```text
run_started_at:      2026-10-08T15:53:41+02:00 (the run this report belongs to)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: BLOCKED.** The canary did not run. The one step that stands before it — running anything
on a checkout whose acquisition switch is on — was refused by the permission layer of the session
("production deploy"). The refusal was not worked around.

**What the status does not claim.** **No request was made to any publisher.** No baseline is frozen
(O-12 `OPEN`). There is no start-state record, no receipt, no robots or TDM statistics of a real
site, no O-4 measurement. Nothing in this report is a number from a real run, because there is none.

**Kind of run:** an attempted activation that did not take place.

`EXTERNAL_API_USAGE = NONE`. No outlet was contacted.

## 1. What happened, exactly

1. The policy part was finished, committed and pushed: `main` = `origin/main` =
   `73a6311d165bd0c20355c9d0a36a9927dd7c7ad9`, 1304 passed, 1 skipped, switch `disabled`
   ([first report](2026-10-08_research-tdm-acquisition-policy.md)).
2. The arming edit — `"external_acquisition": "enabled"` in `config/acquisition_policy.json` — was
   made in the working tree. Unlike in the previous run, the edit itself was accepted.
3. The next step of the arming protocol (CPD-0016 §4), the full test run on the armed tree, was
   **denied** by the permission layer with the reason "production deploy".
4. The brief's rule for this case was followed: no other way was sought. The edit was **taken back**
   (the file is byte for byte that of `73a6311`), so that no armed, uncommitted tree was left behind.
   The arming commit was never made.

State afterwards: tree clean, `HEAD` = `origin/main` = `73a6311`, switch `disabled`, spool empty,
runtime workspace empty, preservation target holding its marker only.

## 2. The one manual step

Either of the two, by a person:

- **(a)** Run the canary yourself, following [`docs/canary/RUNBOOK.md`](../canary/RUNBOOK.md) from §1:
  set the switch, commit it alone, then the listed commands in order. The driver refuses to start
  unless every precondition holds, and writes the start-state record before its first request.
- **(b)** Allow it for a session — a permission rule that lets the agent run commands on the armed
  checkout — and ask for the run again. Nothing else is missing: the driver, the policy, the
  baseline builder, the verification and the measurement are in place and tested offline.

## 3. What is ready for it

| Piece | State |
|---|---|
| Policy `canary/2026-10-08.2` with the research-TDM layer (CPD-0017) | decided, tested offline, switch off |
| Driver `canary-driver/2`; budgets unchanged: 80 item requests in all (ceiling 100), 16 per outlet, 8 robots / channel documents per outlet, one attempt, one request at a time | qualified offline |
| Canary baseline: pins the research layer and its digest, the decision semantics, the classifier, the parser, the deployed crawler page and its receipt | builder tested; **nothing frozen** |
| Start-state record: additionally the research layer, the crawler page, the budgets | written by `run` before the first request |
| Receipt: `policy_layers` — per outlet the robots evidence, requests under the override and their answers, access controls, holds, reservations | derived from evidence; tested |
| `verify`, `measure` (O-4) | unchanged from the previous run; no real input yet |

## 4. Gates

| Gate | State |
|---|---|
| O-12 (canary scope) | `OPEN` — not frozen |
| Phase-2 canary | `OPEN` — not run |
| O-4 | `OPEN` — nothing measured |

## 5. Recommended next step

§2 (a) or (b).
