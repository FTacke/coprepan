# Second real canary: stopped at the operator's gate; extended canary reviewed

```text
run_started_at:      2026-10-09T09:55+02:00 (approximate; last clock reading before the run: 2026-10-09T09:46:05+02:00)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: BLOCKED** — for the second canary, at one named gate. The extended-canary review was completed.

- **Blocked:** the second canary. Arming (runbook §1) is marked *a person's* step, and the freeze of the baseline (§3) is, by
  CPD-0016 §4, the operator's act of stating the manifest's digest. The brief grants the technical consent for one canary and
  tells the agent to keep a separate human step where one is prescribed; one is. The agent therefore did not arm, did not build
  or freeze a baseline, and made no request.
- **Done:** state check; the twelve proposed outlets rated against all existing evidence; a review file with a concrete `--only`
  command for a first wave; one test; runbook and STATUS notes.

**What the status does not claim.** No claim about the second canary, F1–F7 on real servers, or any new outlet: **the number of
outlets with verified acquisition is 1, as before** (`do_diario_libre`). F1–F5 are confirmed reproducibly offline (CPD-0019
report) and **not** on publisher material. No extractor quality statement.

**Kind of run:** diagnosis of the gate, review (recommendation). Not an implementation, validation or activation.
`EXTERNAL_API_USAGE = NONE`. **No request to any publisher.** No new web research.

## 1. Starting state and steps

| | |
|---|---|
| `HEAD` = `origin/main` | `5feee2f6b5d84dd5495e80758b83b3f0fb3a90ef` (after `git fetch`), tree clean; nothing new since the previous report |
| switch | `"external_acquisition": "disabled"` (read from the file) |
| storage (`scripts/storage_contract.py status`) | `PRESERVATION`, `RUNTIME`, `SPOOL` `AVAILABLE`, `SEPARATED`; spool 0 pending records; backup `NOT_CONFIGURED` |
| tests | 1357 passed, 8 skipped on this tree (previous run); the final count is in §9 |
| preflight for the five outlets (previous run, same tree) | `NOT_READY`: exactly `acquisition_policy_decided` (switch off), `tests_green_on_this_commit`, `no_configuration_drift` (no baseline). Every outlet check, the identity, the target and the roles `PASS` |

## 2. Why the run stops where it does

- Runbook §1 is headed *Arm (a person)*; §3's freeze is `canary_driver freeze --confirm <manifest digest>`; CPD-0016 §3–§4 call
  the freeze "the operator's act: stating the manifest's digest". An agent that builds the manifest, reads its digest and
  confirms it itself does not give the gate a second look; it removes it. The brief says to keep such a step.
- The pinned commit `P` is the arming commit. Tests, baseline, preflight and `run` all hang on it, so nothing after §1 can start
  without it. Nothing before §1 is missing: the second canary is prepared, and the pin and preflight of the previous run show no
  other open check.
- The permission layer was **not** probed again (no new error occurred, as the brief asked). The refusals of 2026-10-08 were of
  the arming chain; this run did not issue an arming edit to see whether it would be refused.

## 3. The one operator action, in one block

After it, one agent run can do tests, preflight, `run`, `verify`, `measure`, disarm, evaluation and commits.

```text
# 1. arm (runbook §1)
edit config/acquisition_policy.json: "external_acquisition": "enabled"
git add -- config/acquisition_policy.json ; git commit -m "Arm the second canary: external_acquisition enabled (CPD-0016, CPD-0019)"      # = P

# 2. tests on P (§2)  →  N
python -m pytest -p no:cacheprovider -q

# 3. baseline: build, state READY_TO_FREEZE, freeze by stating the digest (§3), commit and push as evidence
set PYTHONPATH=src
python -m coprepan.canary_driver baseline --outlet bo_el_deber --outlet do_diario_libre --outlet hn_proceso_digital --outlet py_la_nacion --outlet ve_efecto_cocuyo --commit <P> --operator "Felix Tacke" --tests-passed <N> --required-free-bytes 21474836480 --out <scratch>\baseline-canary-2.json
python -m coprepan.canary_driver freeze --manifest <scratch>\baseline-canary-2.json --operator "Felix Tacke" --confirm <manifest_sha256> --out docs\canary\BASELINE_FROZEN_2026-10-09.json
git add -- docs/canary/BASELINE_FROZEN_2026-10-09.json ; git commit -m "Second canary baseline frozen (O-12, canary scope)" ; git push origin main
```

Then ask for the same run again ("the second canary is armed and frozen"): the run does preflight and `run` (the driver refuses
anything that is not `READY`), evaluates, **disarms and commits the disarming** itself. If the operator prefers to start `run`
too, §4 gives the command; the evaluation then starts from the receipt.

## 4–6. Second-canary results, comparison with the first, F1–F7 on real servers

**None exist.** The tables the brief asks for (requests, robots and access decisions, channels, candidates, items, preservation,
fixity, replay, holds per outlet; first against second canary; F1–F7 confirmed on publisher material) are produced by the run
that follows the gate. What is known today is only what the previous report states: F1–F5 repaired and replayed on the stored
answers of 2026-10-08 (level 1, reproducible); F6 a configuration decision; F7 measured. Level 2 (confirmed on publisher
material), level 3 (successful acquisition from more than one outlet) and level 4 (operational stability, never from one run)
are **not reached**.

What the run will be held against, fixed now so it cannot be fitted afterwards: `bo_el_deber`, `py_la_nacion` and
`ve_efecto_cocuyo` yield items (F1, F4, F5); `hn_proceso_digital` is asked nothing (F2, F3 off-origin plans zero); `verify`
`PASS`; no budget exceeded; the receipt equals the evidence.

## 7. Remaining limits

As in the report of 2026-10-09 (§11): the hold on `proceso.hn` has no lifting mechanism; paywalls are never worked around.
New in this run: nothing was found; no code changed.

## 8. The twelve proposed outlets — recommendation

File: `config/registry_review/extended_canary_review_2026-10-09.json` (per outlet: legacy history, evidence, risks, value, what
to verify). Labels are recommendations, not registry states.

| Outlet | Country | Legacy class | Recommendation | Reason in one line |
|---|---|---|---|---|
| `ec_el_universo` | ec | no channel (legacy TDM heuristic) | **READY** | Arc RSS read by a third-party crawler, articles dated 2026-09-30/10-01; no Ecuadorian outlet had repeated output |
| `ec_primicias` | ec | never productive (1,155 pages, none accepted — extractor) | **READY** | `/feed/` documented 2026-03-02; legacy channels answered 200 |
| `es_el_mundo` | es | no channel | **READY** | RSS read by a crawler on 2026-09-30/10-01; feed on another registrable domain (channel origin only); freemium |
| `gt_lahora` | gt | never productive (all channels 200, judged empty) | **READY** | feed with 10 items read by a crawler; a clean test of an ordinary WordPress site |
| `ni_confidencial` | ni | never productive | **READY** | feed on the apex host; adds that origin, time zone and exile are for the reviewer; Nicaragua uncovered |
| `pe_la_republica` | pe | no channel | **READY** | section feed with items dated 2026-10-09; economy section only |
| `pe_diariocorreo` | pe | repeated (3,542 accepted, last 2026-06-15) | **READY** | a control: if it fails, the cause is ours |
| `sv_el_diario_de_hoy` | sv | repeated (1,321 accepted, last 2026-06-15) | **READY** | a second control |
| `mx_la_jornada` | mx | no channel | NEEDS_VERIFICATION | two feed generations from a directory, no 2026 item, another directory says no native RSS |
| `bo_lostiempos` | bo | sporadic (1 of 10) | NEEDS_VERIFICATION | the only listing channel: an untested code path and one hypothesised rule |
| `cl_el_mercurio` | cl | never productive | NEEDS_VERIFICATION | Emol as proxy for El Mercurio is an open operator decision; only an unexpanded index; Chile already covered |
| `pa_laestrelladepanama` | pa | sporadic (1 of 764) | DEFER | route known only from legacy; Panama has three productive legacy outlets; revisit after a real index expansion |

Of the **eight formerly unproductive** (the four "no channel" and the four "never productive" in the proposal): six READY, two
NEEDS_VERIFICATION. The two controls are READY by design.

**Recommended first wave** — the eight READY outlets, six countries (ec ×2, es, gt, ni, pe ×2, sv): 12 item requests per outlet,
96 in all (ceiling 100), no listing channel, no candidate rule, **no change to the policy** (the policy version stays
`canary/2026-10-09.1`). Tested: `tests/test_source_discovery.py::test_the_review_covers_the_proposal_and_its_first_wave_applies_to_a_copy`
applies exactly this `--only` set to a copy and pins the canary. No double assignment between the twelve and the registry was
found; the only shared host in the whole inventory is the known `elnuevodia.com` case (`pr_*`), outside the set. The three
NEEDS_VERIFICATION entries stay in the proposal for a later set.

Decisions that remain the reviewer's: the apex origin of `ni_confidencial`, its time zone; the feed host of `es_el_mundo`;
whether a freemium or metered outlet is wanted; the economy-only scope of `pe_la_republica`. All are listed in the proposal.

## 9. Phase 3 material base

Unchanged: thirteen pages of one outlet, `PHASE3_SAMPLE = INSUFFICIENT_FROM_CANARY`; the pilot package, its blinding key and
all decision forms untouched (no file of `docs/extraction/phase3/` or of the package was opened or changed). A second canary
that yields items from several outlets and CMS families would be the first step towards the design's strata; nothing is claimed
before it exists.

## 10. Tests, files, git

- Full suite on the final tree (switch off): **1358 passed, 8 skipped** (7 need the candidate tools of the extra `phase3`, 1 the
  symbolic-link test this account cannot run); one test more than before. No tracked file was modified by the tests.
- Added: `config/registry_review/extended_canary_review_2026-10-09.json`, one test in `tests/test_source_discovery.py`, this
  report. Changed: `docs/canary/RUNBOOK.md` (who does what; the review), `docs/STATUS.md` (history entry only; no table or
  assertion). Nothing moved, deleted or overwritten; no frozen baseline, evidence, review decision or raw datum touched.
- Reference repositories and the workspace: not touched in this run.
- **A slip against AGENTS §5, for the record:** appending the new test to `tests/test_source_discovery.py` was done with a shell
  here-document (`cat >> … <<'PYEOF'`), and one earlier command of this run contained an empty one. The content was checked by
  running the test and by reading the diff; the rule exists because of quoting and line-ending risk, and the file is LF with the
  intended content. It should have been an edit-tool append. (CO.RA.PAN blocks heredocs with a hook; the proposal to adopt it
  here is still open.)
- Commit: the closing commit of this run (see `git log`); switch `disabled`.

## Operator report

- **Ergebnis.** Nein: noch nicht mehrere Zeitungen. Der zweite Canary lief nicht; es gab keinen Request. Nachgewiesen bleibt eine
  Zeitung (`do_diario_libre`).
- **Status: `BLOCKED`** — nur der zweite Canary, an einem benannten Gate. Die Bewertung der zwölf Quellen ist abgeschlossen.
- **Methodische Bedeutung.** F1–F5: offline reproduzierbar bestätigt; auf realem Publisher-Material noch nicht. Nichts davon ist
  generalisierbar, und Stabilität lässt sich aus einem Einzelrun ohnehin nicht belegen.
- **Erweiterter Canary.** Zur Registrierung empfohlen: `ec_el_universo`, `ec_primicias`, `es_el_mundo`, `gt_lahora`,
  `ni_confidencial`, `pe_la_republica`, `pe_diariocorreo`, `sv_el_diario_de_hoy`. Nicht jetzt: `mx_la_jornada`, `bo_lostiempos`,
  `cl_el_mercurio` (Route oder Scope unbelegt bzw. offene Operator-Entscheidung), `pa_laestrelladepanama` (zurückgestellt).
- **Nächster Schritt — eine Aktion des Operators:** Arming-Commit, Tests, Baseline bauen und einfrieren, pushen (Block in §3), dann
  denselben Run erneut anstoßen. Die achtköpfige erste Welle ist entscheidungsreif: nach dem zweiten Canary
  `apply_registration_proposal.py … --only …` (Befehl in der Review-Datei), dann derselbe Ablauf. Blockierend ist nur das
  Gate, kein weiterer Audit- oder Architekturlauf.
