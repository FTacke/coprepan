# Intake in1-20261010-pilot — final report

Written by the finalizer from the intake's evidence. No number here was typed by hand: each is in `receipt.json` or `measurement.json` beside this file.

## Outcome

- Outcome: **COMPLETED**
- Started 2026-10-10T08:20:47.030693Z, deadline 2026-10-10T08:50:47.030693Z, finalized 2026-10-10T08:50:03.386291Z (UTC)
- Cycles 3, acquisition runs 3, restarts of the controller 0, outlet errors on record 0
- Verification: **PASS**
- Disarming: `external_acquisition` is `disabled` in the file, in HEAD and on origin/main

## Scope and budgets

- Plan: 6 outlets (5 tier A, 1 tier B), 11 channels, 6 countries; policy `canary/2026-10-10.1`
- Requests: 46 of at most 150 (21 item, 25 other)
- Per outlet at most 8 item requests (8 in an hour), per origin 10

## Verification

| Check | Status | Detail |
|---|---|---|
| `nothing_left_open` | PASS | 0 open packs with content |
| `every_answer_is_raw_preserved` | PASS | 40 RAW_PRESERVED of 40 answers with a body |
| `preservation_readback_and_fixity` | PASS | 40 bodies read back from the preservation root; all verify |
| `raw_preserved_matches_verified_bytes` | PASS | 40 of 40 RAW_PRESERVED answers have verified preserved bytes |
| `recovery_diagnosis` | PASS | CLEAN; identity CORRECT |
| `budget_respected` | PASS | 46 requests of 150; the most for one outlet 6 of 8 |
| `no_request_after_the_deadline` | PASS | 0 requests started at or after 2026-10-10T08:50:47.030693Z |

## What was fetched

- Item pages requested 18, answered 2xx 18, technically usable under the experimental extractor 18
- Of the 2xx pages: 0 first listed during the intake and dated inside its window; 0 first listed in a later poll without a date; the rest is stock or older
- Candidates first listed during the intake, by class: {"older_than_window": 327}
- Outlets with at least one 2xx item page: 6 of 6
- Answers by class: {"200": 40}

A URL found for the first time is not thereby an article published during the intake. Only the two classes named above say *new*; see `novelty_classes` in the measurement.

## By country

| Country | Outlets | With 2xx pages | Item requests | 2xx | New, dated in window | New, undated | Technically usable |
|---|---|---|---|---|---|---|---|
| ar | 1 | 1 | 3 | 3 | 0 | 0 | 3 |
| cr | 1 | 1 | 3 | 3 | 0 | 0 | 3 |
| cu | 1 | 1 | 3 | 3 | 0 | 0 | 3 |
| hn | 1 | 1 | 3 | 3 | 0 | 0 | 3 |
| uy | 1 | 1 | 3 | 3 | 0 | 0 | 3 |
| ve | 1 | 1 | 3 | 3 | 0 | 0 | 3 |

## By outlet

| Outlet | Tier | Item requests | 2xx | New, dated | New, undated | Usable | Median body characters | Without a flag | Held |
|---|---|---|---|---|---|---|---|---|---|
| ar_el_tribuno | A | 3 | 3 | 0 | 0 | 3 | 3879 | 3 |  |
| cr_la_nacion | A | 3 | 3 | 0 | 0 | 3 | 7736 | 3 |  |
| cu_havanatimes | A | 3 | 3 | 0 | 0 | 3 | 4430 | 3 |  |
| hn_criterio (watched) | A | 3 | 3 | 0 | 0 | 3 | 347 | 0 |  |
| uy_montevideo_portal | B | 3 | 3 | 0 | 0 | 3 | 2648 | 3 |  |
| ve_efecto_cocuyo | A | 3 | 3 | 0 | 0 | 3 | 2667 | 3 |  |

## Automated anomaly flags

Flagger `intake-anomaly-flags/1`: mechanical hints from the URL and the extraction's measurements. A flag is a reason to look, not a judgement; no page was removed.

- `duplicate_body_of_other_document`: 3
- `very_short_text`: 3

## Holds that arose

- none

## What this is not

counts of one bounded intake under an experimental extractor; flags are mechanical hints, not labels a person gave; no statement about an outlet's output, about the press of a country or about suitability for a release.
