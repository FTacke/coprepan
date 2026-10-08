# Canary driver built and qualified offline; arming prepared and stopped at the permission boundary

```text
run_started_at:      2026-10-08T14:18:52+02:00 (first clock reading, at the state measurement)
run_ended_at:        see the closing commit (approximate: shortly after 16:30+02:00)
timezone:            Europe/Berlin
```

**Status: PARTIAL.** The driver, its offline qualification, the canary-scope baseline, the end-of-canary
verification and the O-4 measurement tools are built and tested. The run **stopped at the arming step**:
the edit that turns `external_acquisition` on in `config/acquisition_policy.json` was refused by the
permission layer of the session ("production deploy"). I did not look for another way to make that edit —
the refusal is the boundary, whatever the brief says — and everything that depends on it was not done.

**What the status does not claim.** No baseline is frozen. The switch is off. **No request was made to any
publisher.** There is no canary, no receipt of a real run, no O-4 measurement, no Phase-3 sample, no
review package. Nothing is validated on real material.

**Kind of run:** implementation and decision (CPD-0016). Not a scientific validation, not an activation.

`EXTERNAL_API_USAGE = NONE`. No network use except the local loopback server of the tests.

## 1. Starting state

`main` = `origin/main` = `0e71ad2cdc0d9439150b8134ffcaa227b709999d`, tree clean. Baseline suite on that commit:
**1219 passed, 1 skipped**. Gates as the previous reports left them: O-11 canary subset `PASS`, O-1 canary `PASS`
(switch off), O-2 `PASS`, O-3 interim `PASS`, `crosscorpus-storage/v1` `IN_FORCE` (`8d17fc21…8fb3`, unchanged),
`BACKUP`, `DISTRIBUTION`, `EXCHANGE` `NOT_CONFIGURED`. The CO.RA.PAN report named in the brief changes nothing
for this repository and was not acted on; CO.RA.PAN was not opened.

## 2. What was built

| Piece | Where |
|---|---|
| The staged driver — A probe, B discovery over all outlets, then C item fetch, D preserve (`preserve_pack`, spool, drain) and E derive per outlet; recovery diagnosis after every stage | `src/coprepan/canary_driver.py` |
| `BudgetedFetcher` — counts every transport call (hops and robots files included) per outlet and in total; refuses a fetch that does not fit; raises `BudgetExceeded` on a call over budget; counts re-derived from fetch records after a restart | same |
| Run receipt built from evidence only (fetch records, request log, ledger, manifests, spool) | same (`build_receipt`) |
| Canary-scope baseline: `freeze.build_manifest(scope="canary", canary=…)`; the `canary` block pins driver, budgets, transport limits, the five outlets as registered, the storage-contract digest, the preservation target's identity — no disk location | `src/coprepan/freeze.py`, `canary_driver.canary_pin` |
| Commands: `pin`, `baseline`, `freeze`, `run` (refuses without a frozen baseline that verifies, a READY preflight, a clean tree, `HEAD` = last fetched `origin/main`, an empty spool and an unchanged pin; writes a start-state record first), `verify`, `measure` | `python -m coprepan.canary_driver` |
| `verify` — recovery diagnosis with identity rebuild, read-back and fixity of every preserved body, `RAW_PRESERVED` = verified bytes, replay of every extraction with the network made unavailable, receipt re-derived from evidence, nothing pending, budget | `src/coprepan/canary_evidence.py` |
| `measure` — the O-4 sizes with labels (`MEASURED`, `DERIVED`, `ASSUMED`, `PROJECTED`), LOW / CENTRAL / UPPER per 1,000 and 100,000 fetches, annual figures only as conditional statements on sourced volumes, comparison with a target only when its size is stated | same |
| The runbook (arming through disarming) | `docs/canary/RUNBOOK.md` |
| The review codebook v1 for the Phase-3 gold, written before any page was seen | `docs/extraction/REVIEW_CODEBOOK_v1.md` |
| CPD-0016 | `docs/decisions/` |

The channels the driver would read, from `pin`: `bo_el_deber` → `rss_main`, `sitemap_main`; `do_diario_libre` →
`rss_main`, `sitemap_sitemapnews`; `hn_proceso_digital` → `rss_main`, `sitemap_news`; `py_la_nacion` → its one sitemap;
`ve_efecto_cocuyo` → `rss_main`, `sitemap_index_main`. Budgets: 80 item requests in all (ceiling 100), 16 per outlet,
8 robots / channel-document requests per outlet, one attempt per request, one request at a time.

## 3. Where and why the run stopped

The brief authorises the freeze of the canary baseline and the arming of the switch if every gate holds.
They held as far as this run could check (§4). The edit that arms the switch was then **denied by the permission
layer** with the reason "production deploy"; a following status command was denied as well, and the same
commands then worked individually. Instructions from the permission layer outrank the brief, so I did not retry
the edit by other means and did not touch the policy file by any route. The consequences, all following from
that one refusal: the baseline cannot be built `READY_TO_FREEZE` (its O-1 precondition is the switch), so it cannot
be frozen; the preflight cannot be READY; the canary does not run; nothing after it exists.

To continue, either of: (a) turn the switch yourself — `"external_acquisition": "enabled"` in
`config/acquisition_policy.json`, commit it alone — and follow [`docs/canary/RUNBOOK.md`](../canary/RUNBOOK.md) from
§2; or (b) allow the edit for a session (a permission rule for it) and ask for the same run again; the runbook's
steps are the ones to execute, in that order.

## 4. Checks

| Check | Result |
|---|---|
| full suite before any change | 1219 passed, 1 skipped (on `0e71ad2`) |
| `tests/test_canary_driver.py` | 27 passed — see §5 |
| `tests/test_canary_evidence.py` | 11 passed |
| full suite on the final tree | see §7 |
| `python -m coprepan.canary_driver pin` | deterministic; names no location |
| preflight with the switch off | `NOT_READY`, the switch and the baseline being the open items (as designed) |

## 5. Offline qualification of the driver

Against a scripted loopback outlet, on temporary directories, with a clock that does not wait:

- all five stages in order (robots first; probe, then discovery, then items) ending preserved, identified, extracted and labelled;
- every answer class — 200, 404, 410, 429 with `Retry-After`, 500, a timeout, a refused connection, a temporary and a
  permanent redirect, a malformed sitemap, a duplicate candidate — recorded as evidence, each asked **once**, no retry loop;
- `robots` disallow and an opt-out: no request to anything denied (asserted on the server's log); a disabled channel is never selected;
- budgets: real requests (redirect hops included) never exceed them; a tight budget yields recorded `canary_budget_exhausted` refusals; a restart starts from the evidence's counts; a call outside or over a budget raises; the ceiling of 100 cannot be configured past;
- the pace: no two requests to one origin closer than the policy's interval, measured at the instant of sending;
- an unreachable preservation target → the pack and its index are spooled, nothing is `RAW_PRESERVED`, nothing is identified or extracted, the run stays open; when the target returns the spool drains and the rest follows with no new request;
- a process killed between the pack and its index, and after both masters but before the ledger: never `RAW_PRESERVED` on a half-finished step, the second run completes with no new request;
- a repeated run makes no request and changes nothing; a late second pass revalidates with `If-None-Match` and records the 304;
- the workspace diagnoses `CLEAN` after a whole run; the receipt equals the fetcher's own counter and is deterministic.

The persistence, crash, concurrency, integrity and evidence suites are part of the full run and were not touched.

## 6. Findings on the way

- The previous design could not freeze a canary baseline (it required O-4 and an enabled switch at once). Resolved by the canary scope and the arming protocol (CPD-0016 §3–§4); the frozen baseline is committed **after** the arming commit as evidence, because a file cannot contain the digest of the commit that contains it.
- Several tests of the tracked configuration asserted the state of the switch rather than its invariants; they now hold in both states, so that arming and disarming do not break the suite.
- `max_attempts = 1` for the canary: a failed request is not retried inside a call; the schedule policy decides (an hour, or a day), which is slower and politer.

## 7. Files, tests, git

Created: `src/coprepan/canary_driver.py`, `src/coprepan/canary_evidence.py`, `tests/test_canary_driver.py`, `tests/test_canary_evidence.py`,
`docs/canary/RUNBOOK.md`, `docs/extraction/REVIEW_CODEBOOK_v1.md`, CPD-0016, this report. Changed: `src/coprepan/freeze.py`
(scope, canary block), the tests of the tracked configuration, the suite manifest, `docs/STATUS.md`, `docs/decisions/README.md`,
`docs/architecture/INDEX.md`. Nothing was moved or deleted; `config/acquisition_policy.json` was **not** changed.

The final test count and the commits are in the closing commit's message and the operator report.

## 8. Gates

| Gate | State |
|---|---|
| O-12 (canary scope) | `OPEN`; builder ready, nothing frozen |
| Phase-2 canary | `OPEN`; driver and runbook ready, not run |
| O-4 | `OPEN`; the measurement tool is ready, no real measurement exists |
| Phase 3 | not begun on real material; codebook v1 drafted |

## 9. Recommended next step

Arm (a person, §3), then follow the runbook. The driver stops by itself at any precondition that does not hold.
