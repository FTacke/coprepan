# Gate closure towards the real canary: registry subset, canary policy — stopped at the crawler identity

```text
run_started_at:      2026-10-08T10:07:26+02:00 (first clock reading, at the start of the pre-push checks)
run_ended_at:        2026-10-08T10:35:00+02:00 (approximate: last clock reading 10:24:56+02:00, before the final test run and the commits)
timezone:            Europe/Berlin
wall_clock_seconds:  not computed: the end was not read from a clock
```

**Status: BLOCKED** — at O-2, before any external request, by a precondition only the operator can
supply: the crawler's real contact identity. What could be closed before it is closed:
`O-11_CANARY_SUBSET = PASS`, `O-1_CANARY = PASS`.

**What the status does not claim.** No request was made to any outlet. There is no canary, no
measurement of bytes per fetch, no capacity statement, no extraction sample, no gold package. O-2
and O-3 are open. The full registry review is open. Nothing is validated on real material.

**Kind of run:** decision and implementation (CPD-0013); technical and institutional gate
evidence. Not a scientific validation, not an activation.

`EXTERNAL_API_USAGE`: **public web search only** — six queries on 2026-10-08 to confirm the official
domain and seat of six outlets for the registry review, as the operator brief allows. No page of
any outlet was fetched, the acquisition pipeline was not used, no model API was called. CO.RA.PAN
was not opened.

## 1. Brief and scope reached

Operator brief: push the finished release-contract run; then, strictly in sequence, O-11 → O-1 →
O-2 → O-3 with the Phase-1 gate on the real target → pre-canary baseline → a bounded real canary
on about five outlets → O-4 → Phase 3 up to the human-gold gate. Stop before any external request
when O-2 lacks real contact data or O-3 has no clear target.

| Stage | Result |
|---|---|
| push of the release-contract run | done |
| O-11 | `PASS` for the canary subset; full review `PARTIAL` |
| O-1 | `PASS` for the canary scope (decided; the enabling switch is left off until arming) |
| O-2 | **`BLOCKED`** — values needed from the operator (§5) |
| O-3 | not decided; inventory only (§6) — the choice is the operator's |
| Phase-1 gate on the real target, baseline, canary, O-4, Phase 3 | **not started** |

## 2. Starting state and push

`main` at `5efabc66931e87142f1005dd9dae30e76d5118dd`, three commits ahead of `origin/main`
(`a2a5ff5…`), working tree clean; `python -m pytest -p no:cacheprovider -q` → 1085 passed, 1
skipped. Then `git push origin main`: `a2a5ff5..5efabc6`; afterwards `HEAD` = `origin/main` =
`5efabc6…`, tree clean.

## 3. O-11 — the canary subset

Decision: CPD-0013 §1–§2. Record:
`config/registry_review/canary_subset_registration_2026-10-08.json`.

Selection rule, applied to the review package: action `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES`; no
warning other than a display name shared across countries; recommended id equal to the imported
id; at least one channel that was active in the legacy system; a country with exactly one time
zone; five different countries; RSS and sitemap channels both present.

| Outlet | Origin | Time zone | Channels | Set from a source |
|---|---|---|---|---|
| `bo_el_deber` | `https://eldeber.com.bo` | `America/La_Paz` | 5 sitemap, 1 rss | seat, `print_and_web` |
| `do_diario_libre` | `https://www.diariolibre.com` | `America/Santo_Domingo` | 8 rss, 1 sitemap, 1 sitemap index | `print_and_web` |
| `hn_proceso_digital` | `https://proceso.hn` | `America/Tegucigalpa` | 4 rss, 1 sitemap, 1 sitemap index | nothing (directory evidence only) |
| `py_la_nacion` | `https://www.lanacion.com.py` | `America/Asuncion` | 1 sitemap | `print_and_web` |
| `ve_efecto_cocuyo` | `https://efectococuyo.com` | `America/Caracas` | 4 rss, 2 sitemap index | `digital_native`, `web_only` |

Evidence: time zones from the IANA database 2026c as installed locally (`tzdata` 2026.3,
`zone1970.tab`: one zone per country); domain, seat, medium and type from the web-search results
listed per outlet in the record, retrieved 2026-10-08. Deferred: `cr_diario_extra` — a closure and
change of owner in 2023 turned up and the current site was not confirmed.

What is not known and is said so: whether any channel is alive; whether the generic URL rules fit
these outlets' URLs; access model, group and (for four) type. One finding from outside the
repository, not acted on: Efecto Cocuyo has been reported as blocked by providers *inside*
Venezuela; that says nothing about reachability from here.

A rule changed, by decision: the test "the tracked registry registers nothing yet — no run may set
`registered`" became "every registered outlet has a registration record and agrees with it"
(CPD-0013 §1).

## 4. O-1 — the canary policy

Decision: CPD-0013 §3–§5. Files: `config/acquisition_policy.json`, `config/schedule_policy.json`,
both `canary/2026-10-08.1`.

Acquisition: public unauthenticated HTTP(S) only; no access control ever bypassed; robots
enforced (absent: allow; unreachable: defer); opt-out denies; `Crawl-delay` binds as a minimum
pause, and an origin asking for more than 60 s is not fetched; 10 s per origin; one request at a
time; raw bodies for research access only. Schedule: a day before a revisit, an hour after a
transient failure (doubling; `Retry-After` wins when longer), three failures then a week, one
recheck of a 404/410, a week after a refusal or denial, conditional requests on.

**Implemented for it:** the policy could only record `Crawl-delay`. It can now apply it
(`PolicyGate.crawl_delay_seconds`, `interval_seconds`; the fetcher's pace; a new refusal
`robots_crawl_delay_exceeds_limit`). Policy schema `v1` → `v2`; no `v1` policy was ever decided.

**Left off on purpose:** `external_acquisition` is `disabled` in the committed policy. The brief
asks for the policy to be decided; turning the switch belongs to arming the canary, after O-2 and
O-3. As committed the decided policy therefore denies every external request
(`external_acquisition_disabled`), and the preflight still shows one open O-1 check.

No authoritative institutional rule was found in the repository that contradicts the policy; none
was found that confirms it either. It rests on the operator's direction in the brief.

## 5. O-2 — blocked: what the operator has to give

Searched: every tracked file for an address or URL suitable as a crawler contact. Found: only
fixtures and placeholders (`…@uni-ficticia.es`, `research@university.edu`, `.invalid`, `.test`).
The git author address is a personal address and was not used. Nothing was invented.

```text
NEEDED (config/crawler_identity.json):
crawler_name     a token of 3 to 64 letters, digits, "_" or "-", beginning with a letter
organisation     the responsible institution, as it should appear to a publisher
contact_url      a public page a publisher can read (what the crawler is, who runs it, how to opt out)
contact_email    an address that is meant to receive crawler contact
```

The contract refuses placeholder domains. The page behind `contact_url` has to exist before the
first request: it is what a publisher finds.

## 6. O-3 — inventory, no decision

Measured 2026-10-08 on the workstation; no `COPREPAN_*_ROOT` is set in the environment and none is
in tracked configuration.

| Volume | Kind | File system | Size | Free | Reading |
|---|---|---|---|---|---|
| `C:` | local system disk | NTFS | 951.6 GB | 183.7 GB | the workstation; holds the checkouts |
| `D:` (label `RESEARCH_BACKUP`) | local | NTFS | 3,815.4 GB | 3,583.5 GB | by its label a backup drive |
| `K:` (label `FREMDSPRACHEN_K$`) | network share of the university computing centre | NTFS | 1,321.2 GB | 200.4 GB | an institutional group share, shared with others |

These are three different institutional kinds — a workstation disk, a drive whose role by its
name is backup, a shared group allocation — and nothing in this repository says which is CO.PRE.PAN's
preservation target, who owns the allocation or what backup it has. That is the case in which the
brief says to stop. **Nothing was written to any of them; no readiness check was run.** CO.RA.PAN's
storage configuration was not read (the brief keeps that repository closed in this run), so its
use of these volumes is unknown here.

What is needed: the preservation root (and a workspace root, which may be local) as a decision —
after which `initialise_target`, the readiness check and the crash and concurrency tests on that
file system can run.

## 7. Files

Created: `config/registry_review/canary_subset_registration_2026-10-08.json`; CPD-0013; this
report.

Changed: `config/outlet_registry.json` (five outlets: status, time zone, attributes with a source,
URL-rule version, channel ids); `config/registry_review/outlet_review_package.json` and
`docs/corpus_supply/REGISTRY_REVIEW_PACKAGE.md` (regenerated); `config/acquisition_policy.json`,
`config/schedule_policy.json` (decided); `src/coprepan/policy.py`, `src/coprepan/fetcher.py`
(`Crawl-delay`); `tests/test_registry.py`, `test_canary.py`, `test_readiness.py`,
`test_policy.py`, `test_schedule.py`, `test_fetcher.py`; `docs/STATUS.md`, the master plan (§12
item 15), `docs/acquisition/INDEX.md`, `docs/corpus_supply/INDEX.md` (§18),
`docs/architecture/INDEX.md`, `docs/architecture/TERMINOLOGY_AND_NAMING.md` (§16),
`docs/decisions/README.md`.

Nothing was moved or deleted. The registry was rewritten in place by a one-off script; the diff
touches the five outlets only. `config/crawler_identity.json` is unchanged.

## 8. Checks

| Check | Result |
|---|---|
| full suite before the push | 1085 passed, 1 skipped |
| full suite after O-11 and O-1 | 1102 passed, 1 skipped |
| `python -m coprepan.canary plan --outlets 5 --seed canary-1` | 5 selected, sufficient; 77 not eligible (not registered) |
| `python -m coprepan.canary preflight` for the five outlets | `NOT_READY`; O-11 five checks `PASS`; schedule policy `PASS`; open: O-1 (the switch), O-2, O-3 (two), tests on the commit, approved baseline |
| registry diff | 55 lines changed, five outlets |

Intermediate failures, all expected and resolved by decision: eight tests asserted that nothing is
registered, five that the policies are undecided.

## 9. Validation classification

Technical and institutional gate evidence. The new code (binding `Crawl-delay`) is tested for
robustness against a loopback server. Nothing here is reproducibility on real material,
replicability or generalisability; a five-outlet subset supports no statement about the press.

## 10. Gates

| Gate | Before | After |
|---|---|---|
| O-11 | `READY_FOR_HUMAN_REVIEW` | canary subset `PASS`; full review `PARTIAL` |
| O-1 | `OPEN` | `PASS` for the canary scope; `OPEN` for scheduled crawling |
| O-2 | `READY_FOR_HUMAN_REVIEW` | `BLOCKED` on the operator |
| O-3, O-4, O-12, Phase 1 on a real target, Phase-2 canary | `OPEN` | `OPEN` |

## 11. Working tree and git

Commits on `main`, explicit pathspecs: `e5eb617` (registry subset), then the policy commit and
the documentation commit that adds this report. Everything changed is committed; nothing is
untracked. Pushed to `origin/main` under the brief's instruction to push validated intermediate
states.

## 12. Recommended next run

The same brief, continued at O-2: with the four identity values and the choice of the preservation
root given, configure and test the identity, qualify the target on its real file system, pin and
arm the baseline, and run the bounded canary.
