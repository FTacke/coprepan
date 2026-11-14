# 2026-11-14 — CO.PRE.PAN source health and 24-hour-wave preparation (the live qualification BLOCKED until a weekday)

**Status:** `PARTIAL` · `EXTERNAL_API_USAGE = NONE`

| Field | Value |
|---|---|
| Date | 2026-11-14 (Saturday; session from 14:13 local, +01:00) |
| Kind | evidence analysis + targeted repairs + operator preparation (AGENTS §8). **No request to any publisher, no canary, no backup run, no cache seed, no activation** |
| Status | `PARTIAL`: the live part (first real incremental backup, cache seed, the authorized canary) is **`BLOCKED`** — it cannot happen before Monday 2026-11-16 (§2–§4); everything independent of it is done |
| External API | `EXTERNAL_API_USAGE = NONE` |
| Start | `main` = `origin/main` at `261805f`, clean; worktree `C:\dev\panhispanic_media_corpora\worktrees\coprepan\source-health`, branch `readiness/2026-11-14-source-health` |
| Operator brief | "CO.PRE.PAN_v3 – Erste Realqualifikation von Backup und Intake; vollständige Source-Health-Prüfung und Vorbereitung der 24-Stunden-Welle" (2026-11-14) |
| Decision | an amendment of [CPD-0035](../decisions/CPD-0035_weekday-maintenance-calendar-transfer-priority-and-bounded-catch-up.md) (resource policy `2026-11-14.3`); no new CPD |

## 1. Start state and sources

- **Git:** `main` = `origin/main` = `261805f` (the report publication of the backup-calendar run), clean; the four older worktrees
  untouched; no other CO.PRE.PAN session.
- **Task `COPREPAN_PreservationBackup`:** Monday–Friday 08:00, last run 2026-11-13 04:45 (result 0), next 2026-11-16 08:00, 0 missed
  runs since the re-timing.
- **CO.RA.PAN (read only)** at 14:13 local: `mode NORMAL`, reachable, not slow, last probe 13:13:32Z, nothing owed. The brief names a
  NEW_FS/SMB recovery of CO.RA.PAN in its Session A; nothing of CO.PRE.PAN contacted the share in this run.
- **Read:** AGENTS, CPD-0025, CPD-0029, CPD-0033, CPD-0035, both reports of 2026-11-14 before this one, the registry, the inventory,
  the readiness file, the access-hold snapshot, the acquisition policy, the 24-hour intake's plan, measurement, receipt and state, the
  baseline extractor, the fetcher, the selector. The workspace (local `C:`) was read for the holds derived from the evidence and for the
  stored bytes of the replay (§5); nothing in it was written.

## 2. Backup: real evidence — none yet

The first incremental run has not happened: the task's next start is Monday 2026-11-16 08:00 (a Saturday is the calendar's pause).
On the BACKUP root the newest receipt is still the FULL run of 2026-11-13 05:04Z (8,816 objects, 395,018,230 B, verified); there is no
`_backup/last_run.json` (no run under the new code has started). No backup was started (the brief excludes runs outside the calendar).

**Health correction (brief §2):** confirmed and repaired. The calendar of CPD-0035, in force from 2026-11-14, counted Friday
2026-11-13's 08:00 slot as missed because the real receipt (06:04 local, from the old 04:45 task) preceded it. Resource policy
`2026-11-14.3` adds `maintenance_calendar.effective_from` (2026-11-14): no slot before the calendar existed counts; the real age stays
visible; every real slot counts as before. Tested on the real receipt's instant: Saturday 0 missed (31 h old), Monday 09:59 0, Monday
10:01 1 (`OK`), Tuesday 2 (`WARNING`). The previous report's statement is corrected in place (it also gave the time of its status run as
~14:50; the commits show ~13:28 — corrected).

## 3. Manifest cache — not seeded

No verified incremental backup exists yet, and `seed-cache` runs on the calendar's days only: `BLOCKED` until after Monday's backup.
The cache directory does not exist in the workspace. No fallback read of the share was made.

## 4. Canary — authorized, not run (`BLOCKED`)

The brief authorizes exactly one intake `in2-20261114-canary` (seven outlets, ≤ 3 h, ≤ 300 requests). On 2026-11-14 three of its
mandatory start conditions cannot hold: a weekday (1), `BACKUP_VERIFIED` (3), the cache seeded (4). The authorization record is
**prepared** from the brief's words
([`in2-20261114-canary_AUTHORIZATION_DRAFT.json`](../intake/canary/in2-20261114-canary_AUTHORIZATION_DRAFT.json): `DIA-2026-11-14-1`,
issued 2026-11-14, the plan's sha, ceilings equal to the plan's budget, the brief's clauses and exclusions). One field is left to the
executing day: `valid_until` — the brief names no end date, so the run that starts the intake sets it to that day (the narrowest
validity), files it once under `config/intake/authorizations/` and commits it once, as `start` requires. The plan is unchanged and
still validates (`validate_plan` **PASS** against registry, policy and the 20 evidence holds, 2026-11-14). Nothing was armed.

## 5. Source-health matrix

[`docs/intake/source_health/source_health_2026-11-14.md`](../intake/source_health/source_health_2026-11-14.md) (human) and `.json`
(machine, every channel's counts and up to five review cases per outlet), built by `scripts/build_source_health.py` from stored
evidence only (reproducible; tested). The starting figures are confirmed by the files: 145 documented outlets (114 registered, 12
proposed, 19 not registered); 87 qualified with 121 channels in 20 countries; 18 `HELD`; 0 `OPERATIONALLY_STABLE`.

| Recommendation | Qualified (87) | Not qualified (58) |
|---|---|---|
| `READY` | 59 | — |
| `READY_WITH_LIMITATIONS` | 8 (`ar_clarin`, `cl_la_tercera`, `es_la_vanguardia`: most new articles left by the budget; `cu_14ymedio`, `ec_el_mercurio`: duplicate bodies; `cu_trabajadores`, `pa_panama_america`, `pr_noticel`: undated channels) | — |
| `REPAIR_REQUIRED` | 4 (`ar_la_nacion` 42/70, `mx_el_universal` 34/34, `pa_diaadia` 30/30, `pa_metro_libre` 66/66 pages empty or very short) | — |
| `REQUALIFICATION_REQUIRED` | 15 (no new article in 24 h; `pe_elperuano`, `hn_radio_progreso`: no page) | 22 (registered, not qualified: the readiness file's reasons) |
| `HELD` | 1 (`ve_efecto_cocuyo`) | 17 |
| `NOT_REGISTERED` | — | 19 |

Screening thresholds are named in the matrix (a share of 0.5 short/empty pages for `REPAIR_REQUIRED`, 0.2 for a limitation, …); they
are technical criteria for review, **not quality judgements**. Every outlet's failure stays visible in its own row.

**Evidenced defects, and what was done:**

- **Channels that are not news streams** (7 outlets): the registered sitemaps of `cl_biobiochile` (entries of July 2025),
  `ar_pagina12`, `py_ultima_hora`, `pa_el_siglo`, `pa_laestrelladepanama`, `cu_juventud_rebelde` list only entries dated before the
  window; `hn_el_heraldo`'s and `hn_la_prensa`'s list section pages (`iniciar-sesion`, `politica-de-privacidad`, `notificaciones`), which
  were fetched as items. The repair is a new channel URL per outlet, found by a live check → **a prepared requalification request**
  (wave preparation §5), not an offline change. A generic URL filter was examined and rejected: of 34 fetched URLs that match
  service-page words, only the 11 of the two Honduran outlets are service pages; the others are article slugs ("registro", "contacto").
- **The baseline extractor's ancestor rule** (`pa_diaadia`: all 30 pages 0 characters). Replay of all 3,681 stored 2xx pages of the
  24-hour intake (local bytes, 51 s): the page's `<main>`/`<article>` sits inside a page-level `<header>` (a Drupal theme), and the rule
  "no block under a `header`, `nav`, `aside`, `footer`, `form` or `figure` ancestor" drops the whole article. Rule A ("only such elements
  between the container and the block exclude") changes 18 outlets and adds teaser text in some (`cl_biobiochile` median 3,694 → 7,707
  characters); rule B (A, but above the container still `nav`, `aside`, `footer`) changes 4: `pa_diaadia` 0 → 2,837, `hn_criterio`
  327 → 773 (both verified as article text: title, paragraphs, author, date), `hn_la_prensa` 1,134 → 1,208, `ec_el_mercurio`
  1,253 → 1,458 — the last is related-article headlines, boilerplate. `mx_el_universal`, `pa_metro_libre` and `ar_la_nacion` are another
  cause: several small teaser `<article>` cards, the text outside them. **Not changed in this run:** where the article boundary lies is
  the extraction evaluation's decision (CPD-0018; the baseline is `EXPERIMENTAL` and not adopted); both rules and their measured effects
  are the material for it. Raw acquisition does not depend on it.
- **Not a defect:** the selector (it fetched what its order says; the 9 undated candidates of `ar_pagina12` were never due); content
  coding (every examined body is declared and decoded gzip).

## 6. 24-hour wave — prepared, not authorized

[`docs/intake/wave/in2-24h-wave_PREPARATION.md`](../intake/wave/in2-24h-wave_PREPARATION.md) and the draft plan
`docs/intake/wave/in2-24h-wave-draft_plan.json` (`e7573007…0693`; outside `config/intake/plans/`): 71 outlets, 101 channels, 20
countries; `validate_plan` **PASS**. Evidence from October: the per-outlet cycle allowance (3) bound — 1,792 of 4,412 new articles
(41 %) in 28 outlets were not fetched; 1,061 of 3,681 fetched pages (29 %) were stock; outlets served one after another at ≥ 10 s per
origin make a cycle about an hour. Proposed: backlog 0, 80 items per outlet, 6 per outlet-hour, 100 per origin, 8,000 in all, polls
unchanged; expected about 2,600–3,000 new pages, 1,500–1,800 packs, ~300 MB (a projection). Before the wave: the canary `PASS`, the
requalification of the 15 outlets (a bounded live check, ≤ 100 requests, prepared for a separate authorization), and — for a wave meant
to measure full coverage — interleaving of outlets in the controller (an engineering item). Robustness: the end-to-end timeout is
repaired; polling back-off, a non-item budget per outlet, the expiry of evidence holds and the task identity when logged off are
proposals or operator decisions (§6 there).

## 7. CO.RA.PAN

Untouched, read only (its state file, at 14:13 local `NORMAL`). No share contact by CO.PRE.PAN in this run; no reconnection, no SMB
session touched. The replay and the hold derivation read the local workspace on `C:` (about 60 s in all); nothing ran on `D:` or the
share.

## 8. Tests and evidence gaps

All temporary directories on `C:`. New: `tests/test_source_health.py` (3; registered in the foundation suite), the calendar transition
and a slow-drip total-timeout test; `tests/test_resource_isolation.py` 55 and `tests/test_fetcher.py` 38 pass. Full suite (the gate before integration): **1,897 passed, 14 skipped** (516.6 s; the previous run's gate: 1,892).

Gaps: everything real — the first incremental backup, the seed, the canary with its preservation on the share and finalization, any
coverage beyond October's one day; the extraction defect is evidenced but not repaired; the 15 outlets' news channels are unknown.

## 9. Changes, commits, integration, push

- Branch `readiness/2026-11-14-source-health`: one commit with the code (calendar `effective_from`, `FetchLimits.total_seconds`, the
  matrix builder), the tests, the policy `2026-11-14.3`, the matrix, the wave preparation and draft plan, the canary's prepared record,
  the docs and this report; merged into `main` with `--no-ff`; `main` was `origin/main` (`261805f`) at the merge.
- Pushed (`main` and the branch, no force). This report, and the corrected report of the backup-calendar run (`--update`), published on
  `main` with `scripts/publish_run_report.py`. The worktree closed last with `scripts/worktree_closure.py remove`; the branch is kept.
- Nothing outside git changed: no scheduled task, no `.env`, nothing in the workspace, on `D:` or on the share.

## 10. Status and next step

`PARTIAL` (the live part `BLOCKED` by the calendar and the missing first incremental backup). **Next step:** on Monday 2026-11-16
after 10:00 local, read `preservation_backup.py status`; if `BACKUP_VERIFIED` (incremental), run `seed-cache`, then — CO.RA.PAN
`SHARE_NORMAL` — file the canary's authorization record with `valid_until` that day and run `intake_operator.py start`. The 24-hour
wave and any recurring acquisition are not authorized by the brief.
