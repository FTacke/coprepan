# Canary runbook — from the qualified driver to the O-4 measurement

**Status: EXECUTED ONCE (2026-10-08); THE SWITCH IS OFF AGAIN.** The first canary ran through §1–§6 —
run `acq1-20261008T203414628095Z-ed630d8e8a14`, 27 requests, `COMPLETE`, verification `PASS`, result `PARTIAL`
(one outlet of five yielded items; findings F1–F6); its evidence is in [`evidence/`](evidence/), its evaluation in
[the run report](../agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md). **Do not run §4 again as it
stands**: a second canary needs the defects repaired first, then a new arming commit, new tests and a newly frozen
baseline (§1–§3 from the start, with a new file name for the baseline). The paragraphs below are kept as the record
of how the first one was reached.

*Before the run:* the driver ([CPD-0016](../decisions/CPD-0016_canary-driver-budgets-and-canary-baseline.md))
was built and qualified offline; twice the permission layer of the
agent's session refused the arming path (first the edit of the switch, then any command on the armed
checkout)
([`docs/agent-runs/2026-10-08_real-acquisition-canary-o4.md`](../agent-runs/2026-10-08_real-acquisition-canary-o4.md) §2).
**State on the evening of 2026-10-08, before the run:** the operator armed (`1f59e01`) and froze a first baseline; its
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

## 8. The second canary and the extended canary (2026-10-09, CPD-0019)

**§0–§7 are the procedure of every canary; this section says what differs for the next two.** The policy is now
`canary/2026-10-09.1`, the driver `canary-driver/3`. A canary has the budget of its frozen baseline: a new arming and a new
freeze start a new budget, a restart under the same baseline does not. The baselines of 2026-10-08 are evidence of the first
canary and authorise nothing further.

### 8.1 Second canary — the five registered outlets

**Who does what (checked 2026-10-09, [report](../agent-runs/2026-10-09_second-real-canary-and-extended-readiness.md)).** §1 is marked a person's step and CPD-0016 §4 makes the
freeze (§3) the operator's act of stating the digest; the agent therefore stops before §1 and does not arm, whatever the brief
says about the canary itself. Everything else (tests, baseline *build*, preflight, `run`, `verify`, `measure`, disarm, the
evaluation) can follow in one agent run once §1 and the freeze are done by the operator and committed and pushed.

No preparation is open. In order: arm (§1) → tests on `P` (§2) → baseline with a new file name (§3) → preflight and run (§4)
→ verify and measure (§5) → disarm (§6).

```text
--outlet bo_el_deber --outlet do_diario_libre --outlet hn_proceso_digital --outlet py_la_nacion --outlet ve_efecto_cocuyo
baseline file: docs/canary/BASELINE_READY_<date>.json, frozen: docs/canary/BASELINE_FROZEN_<date>.json
```

What to expect, so that it is not mistaken for a fault:

- **`hn_proceso_digital` is asked nothing.** Its origin answered the first canary with a bot challenge; the driver reads that
  stored answer again and holds the origin. Its requests appear in the receipt as `DENIED:access_control_observed`. Lifting a
  hold is a person's decision and has no mechanism yet.
- `do_diario_libre` holds 232 candidates from the first canary; the 16 items of this run are taken from those not yet fetched.
- Per outlet at most 8 non-item requests, of which 3 are reserved for the sitemaps an index names; redirects are counted one by
  one, and a redirect that no longer fits is not followed (`redirect_not_followed: DENY: canary_budget_exhausted`).

What the run is held against: whether `bo_el_deber`, `py_la_nacion` and `ve_efecto_cocuyo` now yield items (F1, F4, F5), whether
nothing is planned off-origin (F3), and `verify` `PASS`. `ACQUISITION_VERIFIED` for an outlet: at least five item pages answered
2xx, preserved, verified and replayed.

### 8.2 Extended canary — twelve outlets, after the operator's review (gate O-11)

The set is a **proposal**: `config/registry_review/extended_canary_proposal_2026-10-09.json` (twelve outlets of ten countries; eight
channels and one origin come from research and are hypotheses; one candidate rule; two disabled channels). Read it — each
outlet carries `judgements_for_the_reviewer` — then:

```text
python scripts/apply_registration_proposal.py --proposal config/registry_review/extended_canary_proposal_2026-10-09.json --approved-by "<name>"            (dry run)
python scripts/apply_registration_proposal.py --proposal … --approved-by "<name>" [--only <outlet_id> …] --write
python -m pytest        → commit registry, candidate rules, policy, the registration record and the regenerated review package
```

`--only` registers a part; what is struck stays `proposed`. A canary is five outlets or six to fifteen: with twelve, each gets 8
item requests (96 in all, ceiling 100). Then §1–§6 with the twelve `--outlet` arguments. It is a separate canary with its own
arming, baseline and budget; do not run it in the same arming as the second canary.

**Review of 2026-10-09.** `config/registry_review/extended_canary_review_2026-10-09.json` rates the twelve entries: eight
`READY_FOR_REGISTRATION_REVIEW`, three `NEEDS_VERIFICATION` (`mx_la_jornada`, `bo_lostiempos`, `cl_el_mercurio`), one `DEFER`
(`pa_laestrelladepanama`). Its recommended first wave is eight outlets of six countries (a canary of eight: 12 item requests
each, 96 in all); the file carries the exact `--only` command. The wave needs no candidate rule and changes no policy value.

A proposal that has been applied cannot be applied again (it is written for the registry it names by digest); a later set is a new
proposal.
