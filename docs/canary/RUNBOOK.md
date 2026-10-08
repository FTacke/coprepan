# Canary runbook — from the qualified driver to the O-4 measurement

**Status: PREPARED, NOT EXECUTED.** The driver ([CPD-0016](../decisions/CPD-0016_canary-driver-budgets-and-canary-baseline.md))
is built and qualified offline. The steps below were not run: twice the permission layer of the
agent's session refused the arming path (first the edit of the switch, then any command on the armed
checkout), and it is the one step left to a person
([`docs/agent-runs/2026-10-08_real-acquisition-canary-o4.md`](../agent-runs/2026-10-08_real-acquisition-canary-o4.md) §2).
**State since the evening of 2026-10-08:** the operator armed (`1f59e01`) and froze a first baseline; its
verification failed on a defect of the check, which was repaired in `15ec1fdabf1b5e4e2cb3c4a05a978e57dff3bed0` — **that
is the pinned commit `P` now**, with `N` = 1309 and the frozen baseline
`docs/canary/BASELINE_FROZEN_2026-10-08b.json` (digest `96c271e3…7863f`; the first file is kept as superseded
evidence). §1–§3 are done; the preflight of §4 is `READY`; **the `run` command of §4 is the next step and was refused
to the agent** ([report](../agent-runs/2026-10-08_baseline-digest-repair-real-canary-o4-phase3.md) §5, with the
command written out). Use the `…08b.json` file wherever a command below names the baseline.

Everything else is a command. Run from the checkout; on Windows use `set PYTHONPATH=src` (or
`$env:PYTHONPATH="src"`) instead of the `PYTHONPATH=src` prefix.

The policy the canary runs under is `canary/2026-10-08.2` ([CPD-0017](../decisions/CPD-0017_scientific-tdm-acquisition-and-robots-policy.md)): a robots file is
always read first; a `Disallow` is recorded and overridden only as `ALLOW_RESEARCH_OVERRIDE`; an access
control ends the path and holds the origin. The baseline pins that layer and the deployed crawler page.

The five outlets: `bo_el_deber` `do_diario_libre` `hn_proceso_digital` `py_la_nacion` `ve_efecto_cocuyo`
(`--outlet` once for each). Budget, per `python -m coprepan.canary_driver pin …`: at most 80 item
requests in all (ceiling 100), 16 per outlet, 8 robots / channel-document requests per outlet, two
channels per outlet, one attempt per request, one request at a time, at least ten seconds between two
requests to one site.

## 0. Before anything

```text
git status                      # clean
git fetch origin ; git rev-parse HEAD origin/main     # equal
python scripts/storage_contract.py status            # PRESERVATION, RUNTIME, SPOOL AVAILABLE; 0 pending records
```

## 1. Arm (a person)

In `config/acquisition_policy.json` set `"external_acquisition": "enabled"` and commit it alone:

```text
git add -- config/acquisition_policy.json
git commit -m "Arm the first canary: external_acquisition enabled (CPD-0016)"
```

That commit is the **pinned commit** `P` of everything below. The tests of the tracked configuration
hold in both states of the switch.

## 2. Tests on `P`

```text
python -m pytest -p no:cacheprovider -q        # note N = the number passed
```

## 3. Baseline: build, freeze, commit as evidence

```text
PYTHONPATH=src python -m coprepan.canary_driver baseline --outlet bo_el_deber --outlet do_diario_libre --outlet hn_proceso_digital --outlet py_la_nacion --outlet ve_efecto_cocuyo --commit <P> --operator "Felix Tacke" --tests-passed <N> --required-free-bytes 21474836480 --out <scratch>/baseline-canary.json
   # state must be READY_TO_FREEZE with no blocker; it prints manifest_sha256
PYTHONPATH=src python -m coprepan.canary_driver freeze --manifest <scratch>/baseline-canary.json --operator "Felix Tacke" --confirm <manifest_sha256> --out docs/canary/BASELINE_FROZEN_2026-10-08.json
git add -- docs/canary/BASELINE_FROZEN_2026-10-08.json ; git commit -m "Canary baseline frozen (O-12, canary scope)" ; git push origin main
```

Only evidence files may differ between `P` and `HEAD` (`docs/canary/`, `docs/agent-runs/`); the driver
checks it.

## 4. Preflight (must be READY) and the run

```text
PYTHONPATH=src python -m coprepan.canary preflight --outlet … ×5 --commit <P> --tests-passed <N> --tests-commit <P> --required-free-bytes 21474836480 --approved-baseline docs/canary/BASELINE_FROZEN_2026-10-08.json
PYTHONPATH=src python -m coprepan.canary_driver run --outlet … ×5 --pinned-commit <P> --approved-baseline docs/canary/BASELINE_FROZEN_2026-10-08.json --tests-passed <N> --required-free-bytes 21474836480 --receipt-dir <RUNTIME root>/canary
```

`run` repeats the preflight and refuses on anything that is not READY, on a dirty tree, on a `HEAD`
that is not the last fetched `origin/main`, on a pending spool and on any drift from the baseline;
it writes `canary-start-state-<run id>.json` before the first request. It takes roughly 20–40
minutes (the pace is real). It can be interrupted and run again: the budgets are those of the evidence.
Exit 0 and `COMPLETE` only when nothing is pending; otherwise `INCOMPLETE_PENDING` (the run stays
open, nothing is drained away).

## 5. After the run (read-only, no request)

```text
PYTHONPATH=src python -m coprepan.canary_driver verify  --receipt <receipt> --out <RUNTIME root>/canary/verification.json
PYTHONPATH=src python -m coprepan.canary_driver measure --receipt <receipt> --new-filesystem-bytes 2000000000000 --out <RUNTIME root>/canary/measurement.json
```

`verify`: recovery diagnosis with an identity rebuild, read-back and fixity of every preserved body,
`RAW_PRESERVED` equals verified bytes, replay of every extraction with the network made unavailable,
the receipt re-derived from evidence, nothing pending, budget. `measure`: the O-4 sizes with their labels
and the projections. `2000000000000` is the nominal 2 TB of the planned file system as the operator
named it; it is a statement, not a measurement.

## 6. Disarm

Set `"external_acquisition": "disabled"` again, run the tests, commit, push. The canary is not the start
of scheduled crawling.

## 7. Then

Phase 3 on the preserved pages: `docs/extraction/GOLD_SAMPLE_DESIGN.md`, the review codebook
[`REVIEW_CODEBOOK_v1.md`](../extraction/REVIEW_CODEBOOK_v1.md); stop at the blinded review package.
