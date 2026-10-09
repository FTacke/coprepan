# Three-wave real acquisition qualification: the wrapper reviewed, the waves laid out, stopped at the operator's gate

```text
run_started_at:      2026-10-09T13:59:00+02:00 (first clock reading of the run)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: `BLOCKED`** — all three phases, each at its own named gate. Preparation and the review of the operator's tool are complete.

| Phase | Status | Gate it stands at |
|---|---|---|
| A — second canary | `BLOCKED` | the operator types `ARM` and the baseline digest (CPD-0016 §4) |
| B — eight outlets | `BLOCKED` | O-11: the operator's review and application of the registration; then the same two typed confirmations for a baseline of its own |
| C — nine outlets | `BLOCKED` | as B; and for the second stage of C, a reviewed allow rule and a new baseline |

**What the status does not claim.** No request was made to any publisher; no canary ran; nothing was armed, registered or frozen; the
outlets with verified acquisition are **1** (`do_diario_libre`), in 1 country, as on 2026-10-08. F1–F5 remain confirmed only offline.
The tool review is `reproducibility` / `robustness` evidence on a recorder-driven procedure, not the real integration test.

`EXTERNAL_API_USAGE = NONE`. No web research. The operator's tool was started once from a non-terminal shell, to see it refuse: it
stopped at "the working tree is not clean" (this run's uncommitted work), before any step that could arm.

## 1. Starting state

| | |
|---|---|
| `HEAD` = `origin/main` | `197a097e05bf4cc4ad825b4a518414ad05619e45`, tree clean at the start |
| switch | `disabled` |
| canaries since 2026-10-08 | none (`docs/canary/`, `<RUNTIME>/canary/`, `git log` checked); no process running |
| tests | 1382 passed, 8 skipped (previous report) |

## 2. The brief's order: the operator's tool first

Read against the questions of the brief. Ten defects were found, each reproduced by a test before it was changed — full table and
the decision in [CPD-0021](../decisions/CPD-0021_operator-workflow-hardening.md). The three that matter most:

1. **A test run with errors counted as a pass** (`"1380 passed, 2 errors"`): a canary could be armed and frozen on it.
2. **The disarming could report failure for a disarmed checkout** (nothing to commit) and **never read the state back**, so "disarmed"
   was a belief; it is now read from the file, `HEAD` and `origin/main` and each problem is named separately.
3. **No way back from a killed process**, and a wrong scope was found only after arming. Now: `--disarm-only`, SIGTERM/SIGBREAK
   handled, the scope and budget printed before `ARM` and a wrong one refused without arming.

| Question of the brief | Finding |
|---|---|
| exactly the runbook's steps | yes: §0 checks, §1 arm, §2 tests on `P`, §3 baseline/digest/freeze/commit/push, §4 preflight/run, §5 verify/measure/evidence, §6 disarm, tests, push (tested: order and arguments) |
| arming commit, test commit, baseline linked | the baseline, preflight and run take the arming commit as `--commit` / `--tests-commit` / `--pinned-commit` (tested against the real `git rev-parse`); tests run with `HEAD` = arming commit and the switch on |
| digest visible before the freeze | printed with the manifest summary, before the prompt (tested on the output order) |
| `ARM` and digest independent human inputs | two separate reads; a wrong value for either stops; `ARM` is asked after the scope, the digest after the tests and the baseline build |
| can a confirmation be replaced by argument, pipe or file | no: refused (tested for pipes, files, empty input, eleven wrong answers; the command line has no such option and an unknown option is a usage error). **Limit:** a pseudo-terminal could type; the tool cannot tell (CPD-0021) |
| registry, policy, storage, identity, budgets | pinned and printed before arming (registry, policy, candidate rules, budget); storage, identity, drift, clean tree, pushed `HEAD`, empty spool: the unchanged checks of preflight and driver |
| error messages and intermediate states | each step's failure is named; the disarming reports file / commit / push / read-back separately |
| repeated or interrupted runs | a second baseline of the same label and day is refused; a restart under the same baseline is the driver's (its budget is that of the evidence), run by hand — **the wrapper does not resume**, so it cannot duplicate requests |
| disarm after success, regular failure, interruption, `SIGTERM` | tested for a failure at every step, `KeyboardInterrupt`, a failed baseline push, an incomplete run |
| process killed, console closed, git error | `--disarm-only` (tested for a pushed arming commit, an uncommitted switch, nothing to do); a failed disarming push → exit 2 with the remote still `enabled`, then recovered by `--disarm-only` (tested) |
| can it trigger another canary or widen the scope | no: the scope is the outlets named on the command line, validated against 5 or 6–15, the registry and duplicates; no option adds any |

The permission classifier was not involved and was not probed.

## 3. Phase A — second canary (not run)

Command, verified against the current CLI (the tool starts, parses, reaches its first check; scope printing and pinning exercised
against the real registry in the tests):

```text
python scripts/canary_operator.py --operator "Felix Tacke" --label second --outlet bo_el_deber --outlet do_diario_libre --outlet hn_proceso_digital --outlet py_la_nacion --outlet ve_efecto_cocuyo
```

Pinned scope (real registry, `canary-driver/4`, policy `canary/2026-10-09.1`): 5 outlets, 16 items per outlet and 80 in all, 8
non-item requests per outlet of which 3 reserved for index expansion, two channels per outlet, ceiling 120 requests. Expected, so that
it is not mistaken for a fault: `hn_proceso_digital` is asked nothing (the origin is held from the preserved answer); `py_la_nacion`
has one channel; `do_diario_libre` holds 232 candidates from the first canary.

Held against: `bo_el_deber`, `py_la_nacion`, `ve_efecto_cocuyo` yield items (F1, F4, F5); no off-origin plan (F3); `verify` `PASS`;
no budget exceeded; `external_acquisition` `disabled` at the end in the file, `HEAD` and `origin/main` (the tool reads it back).

## 4. Phase B — eight outlets (not registered, not run)

`apply_registration_proposal.py` with the eight `--only` outlets, dry-run against the current registry: valid, 8 outlets, 5 new
channels, policy version unchanged. Pin: 8 outlets × 12 items = 96 (ceiling 100). The decision sheet (§6) carries the points the
brief names; none is decided here.

## 5. Phase C — nine outlets (not registered, not run)

Dry-run: valid, 9 outlets, 16 channels, policy unchanged. Pin: 9 × 10 items = 90. Plan in two stages, as the brief says, and as the
implementation enforces (`candidate-filter-generic/2`):

1. **C-1 (feeds and listings).** RSS channels of `ar_el_tribuno`, `bo_opinion`, `hn_criterio`, `ni_articulo66`, `ni_nicaragua_investiga`,
   `cu_14ymedio`, `cu_cubanet`, `uy_montevideo_portal` yield items; five listing channels (`ni_articulo66` archive, `cu_cubanet`
   archive, `cu_14ymedio`, `hn_criterio`, `pr_noticel` section pages) are read, paginated within the reserved budget and
   preserved; **what they list is not requested**. `pr_noticel` will show no item. Reasons for every outcome are in the receipt.
2. **Rules.** From the preserved pages: narrow allow patterns per outlet, tested offline on those exact bytes, reviewed, applied to
   `config/candidate_rules.json` as their own commit.
3. **C-2.** A new baseline (a rule changes `candidate_rules`, which the drift check pins), its own arming, and the listing outlets'
   articles. A changed rule is never introduced into a frozen canary.

## 6. Decision sheet — everything that needs a person, in order

*Recommendations are the run's; each is the operator's to change.*

| # | Decision | Recommended |
|---|---|---|
| 1 | Run the second canary | yes — nothing else produces evidence; one command above, two typed confirmations, ~1 h incl. tests |
| 2 | Wave B: register the eight outlets | yes, as proposed (`--only` list in `extended_canary_review_2026-10-09.json`) |
| 2a | `es_el_mundo`: authorise `e00-elmundo.uecdn.es` as a **channel origin only** | yes — items stay on `elmundo.es`; the gate allows a feed host for channel documents only |
| 2b | `ni_confidencial`: apex `confidencial.digital` as a second origin; time zone `America/Managua`; English section not excluded | yes to the apex and the zone (country reported on); accept that `/english/` pages may be acquired in this canary and filtered at release |
| 2c | `pe_la_republica`: economy feed only | yes — a Peruvian publisher of another group; the result says what one section yields |
| 2d | `ec_el_universo`: access model unknown, ownership changed 2026-02 | yes — a paywall redirect ends that path only; the legacy TDM mark was a legacy heuristic, which CPD-0017 does not treat as a prohibition |
| 2e | freemium / metered outlets (`es_el_mundo`, `ec_el_universo`) | accept; the policy never works around a paywall |
| 3 | Wave B canary | after 2: `python scripts/canary_operator.py --operator "Felix Tacke" --label wave-b --outlet ec_el_universo --outlet ec_primicias --outlet es_el_mundo --outlet gt_lahora --outlet ni_confidencial --outlet pe_diariocorreo --outlet pe_la_republica --outlet sv_el_diario_de_hoy` |
| 4 | Wave C: register nine new outlets | yes, with the judgement points of the proposal: country = country reported on (Nicaragua, Cuba: newsrooms abroad); `uy_montevideo_portal` is a portal; `cu_cubanet` is Miami-based by research |
| 5 | Wave C canary C-1 | after 4: the tool with `--label wave-c1` and the nine outlets |
| 6 | `co_el_tiempo` | leave out until a licence / TDM decision; not in any wave |
| 7 | identity cases | not needed for these waves (`pr_primera_hora`, Emol, origin changes are outside them) |

Each wave is its own arming, baseline and budget; three arming commits, three frozen baselines, three evidence directories. The tool
refuses to start while the switch is on or the tree is dirty, so the waves cannot be merged into one crawl.

## 7. After each wave (what the agent run does from the evidence)

`verify` and `measure` are in the evidence directory; the evaluation run reads them and the preserved packs: per outlet channels asked,
HTTP results, candidates (qualified / deferred / rejected), item requests, `RAW_PRESERVED`, fixity, replay, deduplication, holds and
errors; `ACQUISITION_VERIFIED` per the existing yardstick (≥ 5 pages 2xx, preserved, verified, replayed); the legacy comparison;
a Phase-3 review package only when several CMS families have yielded final pages. Small deterministic repairs follow from
reproducible findings only; a repair after a live run is **not** live-validated.

## 8. Tests

| | Result |
|---|---|
| `tests/test_canary_operator.py` (new, 24) | whole procedure against a real temporary git repository with a bare remote; failure injected at each of the seven steps; interruption; incomplete run; wrong digests; no terminal; scope refusals; dirty tree / unpushed `HEAD` / armed switch / used label; failed pushes; `--disarm-only` in three states; no option can carry a confirmation |
| full suite, final tree, switch off | **1407 passed, 8 skipped** (7 need the candidate tools of the extra `phase3`, 1 the symbolic-link test this account cannot run); 25 more than before. The first run had one failure — the new decision record lacked the `## Context` and `## Alternatives considered` headings the contract test requires; added, re-run of the contract tests green, the rest of the suite unchanged between the two runs |

## 9. Files and git

Created: `tests/test_canary_operator.py`, `docs/decisions/CPD-0021_operator-workflow-hardening.md`, this report.
Changed: `scripts/canary_operator.py` (rewritten along the ten findings, same interface plus `--disarm-only`),
`tests/suites/foundation_contract.txt`, `docs/STATUS.md` (history entry), `docs/canary/RUNBOOK.md` (§9), `docs/decisions/README.md`,
`docs/architecture/INDEX.md`. Nothing moved or deleted; no baseline, evidence, registry, policy or rule touched.
Reference repositories, workspace and preservation root not touched.

Against AGENTS §5, for the record: once more in this run a shell command carried an **empty** here-document (the dry-run command of §4),
no content, no effect. That is the third such slip across the three runs of today; the rule is still enforced only by my care. The hook
CO.RA.PAN uses would make it mechanical and is still only proposed.

## Operator report

- **Ergebnis.** Es liefert weiterhin **eine** Zeitung in **einem** Land Artikel (`do_diario_libre`). Keine der drei Wellen lief: keine
  neue Zeitung, kein neues Land, nichts Neues gegenüber Legacy. Der Grund ist ausschließlich das Gate (Tippen von `ARM` und Digest;
  Registrierungsreview für B und C).
- **Status: `BLOCKED`** je Phase A, B, C an dem oben genannten Gate; Vorbereitung und Werkzeugprüfung vollständig.
- **Technischer Fortschritt.** Der Operator-Wrapper war nicht betriebssicher und ist jetzt gegen zehn Fehlerpfade geprüft; das
  Wichtigste: Tests mit Fehlern konnten als bestanden zählen, ein Abbruch ließ den Schalter ungeprüft, und nach einem Prozess-Kill gab
  es keinen Rückweg. Nachgewiesen nur gegen ein temporäres Repository mit Attrappen für Treiber und Tests; die Discovery-Strukturen
  sind weiterhin nicht auf realen Seiten bestätigt.
- **Wissenschaftliche Bedeutung.** Unverändert offen: Es gibt keinen Beleg, dass die Quellenvielfalt gewachsen ist.
- **Produktive Konsequenz.** Für einen längerfristigen Stabilitätstest ist noch keine Quelle bereit; dafür braucht es mindestens drei
  verifizierte Läufe über 14 Tage.
- **Nächster Schritt.** Im Terminal: der Befehl aus §3 (zweiter Canary); danach „zweiter Canary ist gelaufen“ für die Auswertung. Welle B
  und C: die Entscheidungen aus §6, Punkte 2 und 4.
