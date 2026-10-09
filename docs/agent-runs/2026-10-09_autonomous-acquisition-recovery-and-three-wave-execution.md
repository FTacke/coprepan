# Autonomous acquisition: safe recovery, the delegated operator mode, and the waves

```text
run_started_at:      2026-10-09T15:36:00+02:00 (first clock reading of the run, approximate to the minute)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**This report is written in stages.** A section exists only for what has happened; a later commit of the same run adds the
later phases. The status line below is that of the commit it is in.

**Status at this commit: Phase 0 `PASS` · Phase A `PARTIAL` (run by the operator, evaluated here) · Phase 1 `PASS` offline,
not yet used for a real canary · Phases B, C1, C2 not yet run.**

`EXTERNAL_API_USAGE = NONE`.

## Phase 0 — the canary that was under way

The brief reported a second canary armed and waiting for a digest. The state found was another one, and nothing was closed by
this run.

| Checked | Found |
|---|---|
| operator process | `scripts/canary_operator.py --operator "Felix Tacke" --label second …`, started 15:35:40, alive until 15:59:41 |
| baseline | built and **frozen by the operator in person** (typed digest): `docs/canary/BASELINE_FROZEN_2026-10-09_second.json`, digest `9bd2da67d435a439c5ae1b52f7d3561c19c5907e18717f792381757bd8173977`, commit `a0b3843` |
| arming commit | `7ec0fa3598b22cf57de6e400acdcb40a9bdc1e81` (the tests of that commit passed: the repair of the earlier run held) |
| requests | under way from 15:46:34; the run `acq1-20261009T134634374845Z-3d6f4bf8adea` finished 15:52:55 |
| evidence | commit `81c8273`: receipt, start state, `verification.json`, `measurement.json` under `docs/canary/evidence/<run>/` |
| disarming | commit `21a17a3`, pushed |

Because a process was still producing a consistent commit and baseline state, **nothing was changed in the repository until it
had exited** — including during its closing test run on the disarmed tree (15:53–15:59). The state was then read independently,
not taken from an exit code: `external_acquisition` is `disabled` in the file, in `HEAD` and on `origin/main`
(`21a17a3abe3bdabcb5a5a9df901d2039a3bdd36d` both), the tree was clean, and no canary or operator process was left (the process
list was read; what remains are CO.RA.PAN's own capture processes and three stale test children of 2026-10-08, none of them
this repository's acquisition).

No `--disarm-only` was needed and none was run. No baseline was confirmed after the fact; the authorisation of this canary is
the operator's own typed confirmation and is not reinterpreted.

## Phase A — the second canary (the operator's run, evaluated by this run)

Authorisation: **interactive, the operator in person**. Not delegated; no record. It was not repeated.

Receipt `COMPLETE`; verification `PASS` on all eight checks (67 bodies read back and verified; 43 `RAW_PRESERVED` = 43 verified
= 43 expected; 32 extractions replayed without network, 0 differ; receipt re-derived from evidence; 45 transport calls = 45
derived; no pending object; 32 item requests against a ceiling of 100).

| Outlet | Robots | Channel documents | Entries → candidates | Item requests | 2xx article pages, preserved and replayed | Result |
|---|---|---|---|---|---|---|
| `bo_el_deber` | 200, allow | RSS 200 (25 entries), sitemap 200 (55) | 80 → 80 (79 qualified, the site root rejected) | 16 | **15** (one 301 to another origin, not followed) | **`ACQUISITION_VERIFIED`, new** |
| `do_diario_libre` | 200, allow | RSS 200 (39), news sitemap 200 (527) | 566 → 463 (64 over the candidate budget, the oldest) | 16 | **16** | verified a second time, on a second day |
| `py_la_nacion` | 200, allow | Arc sitemap 200 (100) | 100 → **0**: every entry `off_origin` | 0 | 0 | **finding F8**, a defect of this project; repaired offline, below |
| `ve_efecto_cocuyo` | 200, allow | RSS 200 (10); `/sitemap.xml` **403, a JavaScript browser check** | 10 → 10 qualified | 0 (10 refused: `access_control_observed`) | 0 | **hold**: bot challenge; nothing further was asked |
| `hn_proceso_digital` | not asked | 2 refused before transport (`access_control_observed`) | — | 0 | 0 | hold of 2026-10-08 respected: **not contacted** |

Body text of the preserved article pages (baseline extractor, experimental; a measurement, not a quality claim): `bo_el_deber`
median 3 745 characters (1 630–5 554), `do_diario_libre` median 3 152 (1 981–7 582); every page ≥ 500 characters.

### The offline assumptions F1–F7 against real servers

| Finding | What the real run showed | Kind of validation |
|---|---|---|
| F1 gzip robots | `eldeber.com.bo` and `lanacion.com.py` served `robots.txt` gzip-coded; both were read (`ROBOTS_ALLOW`) and preserved as received | robustness: confirmed on two real servers |
| F2 challenge → hold | a new challenge page (WordPress.com "Checking your browser…", status 403) was classified `bot_challenge`; the origin was held and ten planned item requests were refused; the Sucuri hold of 2026-10-08 kept `hn_proceso_digital` uncontacted | generalisability: a second, different challenge product recognised |
| F3 own candidates only | each outlet requested only its own candidates (16 + 16; none across outlets) although the workspace held 13 documents of 2026-10-08 | reproducibility on the real workspace |
| F4 sitemap-index expansion | **not exercised**: 0 expansion requests — the only index channels belonged to the two held outlets | open |
| F5 DOCTYPE in CDATA | **not exercised**: the feed that carried it is `hn_proceso_digital`'s | open |
| F6 disabled channels | the three disabled channels were not selected | confirmed |
| F7 candidate budget, newest first | `do_diario_libre`: 527 sitemap entries, 64 not given a candidate — the allotment is by date; the 16 pages requested were of 2026-10-09 | confirmed on one outlet |

### Finding F8 (new): a publisher's own sitemap states its pages with `http`

`py_la_nacion`'s Arc sitemap listed all 100 pages as `http://www.lanacion.com.py/…`; the outlet is registered under
`https://www.lanacion.com.py`. The identity rule treated every entry as off-origin, so the run made no item request. That is this
project's defect, not the publisher's refusal. Repair (`channel-parser/4`): an entry stated with `http` whose host is registered
under `https` **and not** under `http`, with no port and no user part, is read as the `https` URL; the observed URL stays as
stated and the event says `scheme_read_as: https`. Nothing else is widened. Replayed offline on the preserved answer of the
run: **0 of 100** entries on the registered origin under `channel-parser/3`, **100 of 100** under `/4`. `py_la_nacion` was not
asked again: no wave of this commission covers it.

### What Phase A does not show

One run per outlet is not `OPERATIONALLY_STABLE` (three runs on three days within fourteen days). `do_diario_libre` now has two
runs on two days. `ve_efecto_cocuyo`'s feed answered; whether its articles would have is unknown and was not tried.

## Phase 1 — the delegated operator mode

Decision [CPD-0023](../decisions/CPD-0023_delegated-operator-authorisation-in-force.md) (CPD-0022, the direction, is superseded
by it; CPD-0016, CPD-0020 and CPD-0021 carry a forward link and are otherwise unchanged).

| Part | What |
|---|---|
| `src/coprepan/delegation.py` | the authorisation record (`coprepan-operator-authorization/v1`), its validation, and the one question: does this record cover exactly this canary — outlets in both directions, every limit, the policy version, the validity, a wave used once |
| `config/operator_authorizations/2026-10-09_waves-b-c1.json` | record `DOA-2026-10-09-1`: waves `wave-b` (8 outlets, 12 item requests each, at most 100) and `wave-c1` (9 outlets, 10 each, at most 90), each with its registration proposal by digest; the brief's authorising clauses quoted; what is not authorised; the holds; the gates; the stop conditions; the duty to disarm. Wave A is not in it (the operator ran it in person); C2 is not in it (the brief asks for its own versioned scope after C1) |
| `src/coprepan/canary_driver.py` | `baseline --authorization … --wave …` pins the record (id, SHA-256, path, wave) in the canary block; `run` reads the record again, checks again and compares; start state and receipt carry `operator_authorization` (for an interactive baseline: `INTERACTIVE_OPERATOR` and the name the freeze states) |
| `scripts/canary_operator.py` | `--authorization <record> --wave <label>` and nothing else: no prompt, outlets and label from the record, the record written once (one commit, tracked, clean tree, pushed), the registration proposal by digest; the freeze only when the manifest pins exactly this authorisation; commit messages name the record. The interactive mode is unchanged and refuses a baseline that pins a record. No force, skip or budget option exists |
| tests | `tests/test_delegated_operator.py`: the record (21 damaged or widened forms), the check (11 refusals with their reason), a wave used once, the driver's re-check, and the tool end to end against a temporary git repository with a bare remote — the same steps without a prompt, every step failing in turn, failing tests, an interruption, an incomplete run, a failed push, an unpushable disarming and `--disarm-only`, a record changed in a second commit, untracked, elsewhere, unpushed, edited, out of date, another proposal, an unregistered outlet; the interactive mode beside it |

The heredoc hook of the brief's §3.5 exists since the previous run (`scripts/hooks/block_heredocs.py`, 23 tests).

**The environment's permission layer.** With the operator's two `autoMode.allow` rules in place, the module and the tool were
written without a refusal. Nothing was routed around a refusal in this run, because none occurred up to this commit.

**Slips of this run against AGENTS §5** (disclosed, none wrote a file): three shell commands used a one-line bash here-string
(`<<<`) with an empty string where no input was needed; AGENTS §5 names heredocs and PowerShell here-strings, and the hook lets
this form through, but they were pointless and are not a pattern to keep. One inline `python -c` contained backticks that the
shell interpreted; the edit it made was read back and corrected by hand.

## Registration of wave B (under `DOA-2026-10-09-1`)

`scripts/apply_registration_proposal.py --proposal config/registry_review/extended_canary_proposal_2026-10-09.json --only …`
for the eight outlets of the brief, approved-by naming the delegate under the record. Result: 13 registered outlets, 69
proposed, 357 channels (five new: the feeds of `ec_el_universo`, `ec_primicias`, `es_el_mundo`, `ni_confidencial`,
`pe_la_republica`); record `config/registry_review/extended_canary_registration_2026-10-09.json`; the acquisition policy is
unchanged (`canary/2026-10-09.1`, the same three disabled channels). The operator's decided points are the proposal's values:
El Mundo's `uecdn.es` host carries the feed and no item; Confidencial has the apex origin beside `www` and `America/Managua`
(the seat in exile is a note, not a rule); La República is one section feed (economy); El Universo's access model is unknown.

The inventory (`…2026-10-09.1`) and the overview (`…2026-10-09.2`) are dated snapshots of the registry before the waves; their
tests now hold them against that registry instead of the live one, and neither file was rewritten.
