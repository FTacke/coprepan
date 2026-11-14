# CPD-0036 — A qualification wave may defer its preservation to the runtime workspace; a wave may read up to four channels

| Field | Value |
|---|---|
| Date | 2026-11-14 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Execution | implemented and tested offline (`tests/test_deferred_preservation.py`, the existing suites); `canary-driver/6`. Used for real by the weekend qualification waves under `DOA-2026-11-14-2` (run report of 2026-11-14/15). The later promotion (`canary_driver preserve-deferred`) has **not** run against the share: it is gated to a weekday |
| Builds on / amends / supersedes | builds on CPD-0015 (P4/P5: an honest `PENDING`), CPD-0016, CPD-0023, CPD-0024, CPD-0033, CPD-0035; amends CPD-0024 in one point (decision 4); supersedes nothing |
| Does not change | the joint storage contract; P2 (`RAW_PRESERVED` still needs the bytes re-read on the primary); the acquisition policy (`external_acquisition` stays `disabled` outside an armed wave) and every access, robots and TDM decision; every hold; the pending bounds and free-space floors of CPD-0033/0035; the maintenance calendar; any request limit of CPD-0016/0024; the canary baseline's other pins; the intake controller |
| Decided by | the operator's brief of 2026-11-14 ("CO.PRE.PAN_v3 – Wochenend-Qualifikation aller zugänglichen Pressequellen mit lokalem Spooling und autonomen Reparaturen", §3: "Neue Rohdaten müssen am Wochenende nicht auf NEW_FS übertragen werden … Keine NEW_FS- oder D:-Schreiboperationen am Wochenende … Falls die vorhandenen Tools nicht sauber lokal spoolen können, diese Fähigkeit gezielt und vertragskonform ergänzen"); the form is the commissioned agent's |
| Run report | `docs/agent-runs/2026-11-15_coprepan-weekend-source-qualification.md` |

## Context

The canary driver preserves each pack at once on the PRESERVATION root (or spools it when the root is away). Its baseline reads the
target's identity, its preflight runs the target readiness check, and every role resolution probes a root with a write
(`storage_roots._writable`). A weekend qualification that must not touch NEW_FS or `D:` could not use it. Found while preparing the
weekend run: the agent's own preflight script resolved every configured role twice (2026-11-14 ~20:40 local), which created and at
once removed an empty probe file on the share and on `D:` each time — recorded in the run report.

## Decision

1. **A wave of a delegated authorisation may set `"preservation": "deferred_local"`.** The baseline pins it in the authorisation
   block. A direct wave's block and every earlier record are unchanged.
2. **Deferred means: the target is never resolved by the run.** O-3 is passed by `preservation_target.deferred_readiness` — the
   runtime workspace usable and above the stated free space; status `DEFERRED_LOCAL`, which is never `READY` — and only for a canary
   baseline (an acquisition baseline is still blocked). The storage block of the pin is `{"mode": "deferred_local", "target_id": null}`.
   Only the local roles (`RUNTIME`, `SPOOL`) are resolved; the preservation and backup roots are not.
3. **What the run leaves:** every pack sealed and verified in the workspace, every body `PRESERVATION_PENDING`
   (`route: workspace`, reason `PreservationDeferred`) — `RAW_AVAILABLE` locally, never `RAW_PRESERVED`; nothing in the spool; no
   derivation (stage E reads preserved input only). Receipt status `COMPLETE_PRESERVATION_DEFERRED`, field `preservation`. The
   verification (`canary-verification-deferred/1`) re-reads every sealed pack and body in the workspace, checks that pending equals
   received and nothing is claimed preserved, runs the baseline extraction twice from the local bytes with the network unavailable
   (nothing stored), re-derives the receipt and checks the budget. It says nothing about the target.
4. **Amends CPD-0024 in one point:** a wave's limits may also name `channels_per_outlet`, 1 to 4 (default 2). It is the one limit a
   wave may raise; every request limit is still the smaller of the ordinary one and the wave's, so the channel documents still draw on
   `other_requests_per_outlet` (at most 8).
5. **The later promotion** (`python -m coprepan.canary_driver preserve-deferred --receipt … --out …`) makes no publisher request and
   starts only when, checked before any contact: no `PAUSE_IO`; a weekday of the maintenance calendar outside CO.RA.PAN's quiet
   windows and without a fresh observation of a degraded, slow or recovering share; the backup health `OK`; the share gate's transfer
   purpose open. Then at most `catch_up_packs_per_hour` packs, oldest first, each preserved (P2) and derived like any pack; the first
   pack that stays pending ends the step. Repeatable. It is authorised for the packs of the qualification waves only.
6. **Amended the same day, after the first wave (`wq-1`), `canary-driver/7`.** (a) Stage B reads every selected channel after
   the first. `canary-driver/6` selected up to four and read only the second: in `wq-1` the third channel of every outlet was
   selected and never requested (no request was made beyond the budget; the defect lost coverage, not control). (b) A wave with
   deferred preservation, a qualification, requests its items in the order `item-selection/1`: only pages never fetched before;
   first those this run's channel documents listed with a date, newest first; then those listed undated in this run; then the
   rest, the most recently listed first. The planner's own order (oldest due first), which a direct canary keeps, had sent `wq-1`
   to pages first listed in October 2026 and earlier (biobiochile pages of July 2025, pagina12 pages of 2022). The selection
   chooses only among what the planner says is due; it adds nothing and raises no limit. Waves `wq-1` and `wq-2` ran under
   `canary-driver/6`; their baselines pin it.

## Alternatives considered

- **Spool the packs** (the outage path of CPD-0015): the spool is on C: too, but a spooled object makes the next canary refuse to
  start ("the spool holds pending objects"), so a second wave could not run; and spooling is meant for an outage, not for a plan.
- **Run the waves through the intake controller**, whose share gate already holds transfers: it is the productive intake switch,
  which the brief says not to bypass, and it has no per-outlet item cap of a qualification.
- **A separate qualification fetcher**: a second raw-data path beside the pipeline, which the brief excludes.
- **Raise the channel limit by changing the canary's default**: it would change every later canary; a wave's own, recorded limit
  is narrower.

## Not decided here

- Whether deferred preservation may be used for anything but a qualification wave (it is not: the intake is unchanged).
- Any extractor, access, robots or TDM question; the hold of any origin; the 24-hour wave.

## Validation debt

- The promotion has not run against the share. After it, the target-side checks of a canary (read-back and fixity there, replay
  from preserved bytes, the recovery diagnosis) are still to be run for the promoted packs.
- Pending packs left by the weekend waves make the workspace not clean: the prepared Monday canary `in2-20261114-canary` requires a
  clean workspace, so the promotion comes first.
