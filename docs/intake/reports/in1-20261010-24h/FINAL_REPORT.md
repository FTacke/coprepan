# Intake in1-20261010-24h — final report

Written by the finalizer from the intake's evidence. No number here was typed by hand: each is in `receipt.json` or `measurement.json` beside this file.

## Outcome

- Outcome: **COMPLETED**
- Started 2026-10-10T08:59:45.209544Z, deadline 2026-10-11T08:59:45.209544Z, finalized 2026-10-11T09:12:44.268660Z (UTC)
- Cycles 24, acquisition runs 24, restarts of the controller 0, outlet errors on record 0
- Verification: **PASS**
- Disarming: `external_acquisition` is `disabled` in the file, in HEAD and on origin/main

## Scope and budgets

- Plan: 87 outlets (85 tier A, 2 tier B), 121 channels, 20 countries; policy `canary/2026-10-10.1`
- Requests: 7173 of at most 12000 (3822 item, 3351 other)
- Per outlet at most 120 item requests (10 in an hour), per origin 150

## Verification

| Check | Status | Detail |
|---|---|---|
| `nothing_left_open` | PASS | 0 open packs with content |
| `every_answer_is_raw_preserved` | PASS | 6490 RAW_PRESERVED of 6490 answers with a body |
| `preservation_readback_and_fixity` | PASS | 6530 bodies read back from the preservation root; all verify |
| `raw_preserved_matches_verified_bytes` | PASS | 6490 of 6490 RAW_PRESERVED answers have verified preserved bytes |
| `recovery_diagnosis` | PASS | CLEAN; identity CORRECT |
| `budget_respected` | PASS | 7173 requests of 12000; the most for one outlet 120 of 120 |
| `no_request_after_the_deadline` | PASS | 0 requests started at or after 2026-10-11T08:59:45.209544Z |

## What was fetched

- Item pages requested 3691, answered 2xx 3681, technically usable under the experimental extractor 3610
- Of the 2xx pages: 2572 first listed during the intake and dated inside its window; 48 first listed in a later poll without a date; the rest is stock or older
- Candidates first listed during the intake, by class: {"first_poll_undated": 210, "new_dated_in_window": 3783, "new_undated_later_poll": 629, "older_than_window": 10227}
- Outlets with at least one 2xx item page: 85 of 87
- Answers by class: {"200": 6473, "301": 9, "403": 1, "404": 6, "504": 1, "failed:body_limit_exceeded": 16, "failed:redirect_limit_exceeded": 1, "failed:timeout": 10}

A URL found for the first time is not thereby an article published during the intake. Only the two classes named above say *new*; see `novelty_classes` in the measurement.

## By country

| Country | Outlets | With 2xx pages | Item requests | 2xx | New, dated in window | New, undated | Technically usable |
|---|---|---|---|---|---|---|---|
| ar | 7 | 7 | 404 | 404 | 340 | 0 | 404 |
| bo | 2 | 2 | 98 | 89 | 63 | 0 | 89 |
| cl | 5 | 5 | 221 | 221 | 150 | 0 | 221 |
| co | 5 | 5 | 253 | 253 | 199 | 0 | 253 |
| cr | 1 | 1 | 70 | 70 | 67 | 0 | 70 |
| cu | 4 | 4 | 105 | 105 | 29 | 0 | 105 |
| do | 4 | 4 | 244 | 244 | 213 | 0 | 244 |
| ec | 6 | 6 | 286 | 286 | 226 | 0 | 286 |
| es | 5 | 5 | 331 | 331 | 304 | 0 | 331 |
| gt | 5 | 5 | 228 | 228 | 148 | 0 | 228 |
| hn | 6 | 5 | 101 | 101 | 7 | 0 | 79 |
| mx | 1 | 1 | 34 | 34 | 11 | 0 | 34 |
| ni | 3 | 3 | 68 | 68 | 23 | 0 | 68 |
| pa | 8 | 8 | 328 | 328 | 172 | 19 | 295 |
| pe | 6 | 5 | 153 | 153 | 98 | 0 | 153 |
| pr | 3 | 3 | 131 | 131 | 100 | 1 | 131 |
| py | 4 | 4 | 167 | 166 | 129 | 0 | 163 |
| sv | 2 | 2 | 71 | 71 | 44 | 0 | 71 |
| uy | 3 | 3 | 164 | 164 | 106 | 28 | 164 |
| ve | 7 | 7 | 234 | 234 | 143 | 0 | 221 |

## By outlet

| Outlet | Tier | Item requests | 2xx | New, dated | New, undated | Usable | Median body characters | Without a flag | Held |
|---|---|---|---|---|---|---|---|---|---|
| ar_clarin | A | 70 | 70 | 69 | 0 | 70 | 3880 | 68 |  |
| ar_el_tribuno | A | 64 | 64 | 55 | 0 | 64 | 3964 | 63 |  |
| ar_infobae | A | 41 | 41 | 20 | 0 | 41 | 5961 | 41 |  |
| ar_la_nacion | A | 70 | 70 | 69 | 0 | 70 | 458 | 25 |  |
| ar_pagina12 | A | 24 | 24 | 0 | 0 | 24 | 485 | 0 |  |
| ar_perfil | A | 63 | 63 | 56 | 0 | 63 | 4015 | 44 |  |
| ar_rio_negro | A | 72 | 72 | 71 | 0 | 72 | 6085 | 72 |  |
| bo_el_deber | A | 62 | 53 | 48 | 0 | 53 | 2309 | 53 |  |
| bo_opinion | A | 36 | 36 | 15 | 0 | 36 | 2433 | 36 |  |
| cl_biobiochile | A | 24 | 24 | 0 | 0 | 24 | 3653 | 21 |  |
| cl_cooperativa | A | 57 | 57 | 40 | 0 | 57 | 1667 | 57 |  |
| cl_la_discusion | A | 34 | 34 | 20 | 0 | 34 | 3283 | 34 |  |
| cl_la_tercera | A | 72 | 72 | 72 | 0 | 72 | 7331 | 69 |  |
| cl_the_clinic | A | 34 | 34 | 18 | 0 | 34 | 4261 | 34 |  |
| co_diario_del_huila | A | 26 | 26 | 10 | 0 | 26 | 1476 | 26 |  |
| co_el_espectador | A | 65 | 65 | 60 | 0 | 65 | 5344 | 60 |  |
| co_el_nuevo_siglo | A | 32 | 32 | 8 | 0 | 32 | 4449 | 32 |  |
| co_elpais | A | 62 | 62 | 55 | 0 | 62 | 4858 | 53 |  |
| co_semana | A | 68 | 68 | 66 | 0 | 68 | 1141 | 67 |  |
| cr_la_nacion | A | 70 | 70 | 67 | 0 | 70 | 2479 | 70 |  |
| cu_14ymedio (watched) | A | 37 | 37 | 17 | 0 | 37 | 733 | 22 |  |
| cu_havanatimes | A | 28 | 28 | 4 | 0 | 28 | 2137 | 28 |  |
| cu_juventud_rebelde | A | 22 | 22 | 0 | 0 | 22 | 1924 | 0 |  |
| cu_trabajadores | A | 18 | 18 | 8 | 0 | 18 | 2666 | 0 |  |
| do_diario_libre | A | 59 | 59 | 51 | 0 | 59 | 3531 | 59 |  |
| do_el_nacional | A | 57 | 57 | 49 | 0 | 57 | 2831 | 57 |  |
| do_hoy | A | 64 | 64 | 57 | 0 | 64 | 3434 | 64 |  |
| do_listin_diario | A | 64 | 64 | 56 | 0 | 64 | 2962 | 62 |  |
| ec_el_comercio | A | 47 | 47 | 31 | 0 | 47 | 2696 | 47 |  |
| ec_el_mercurio | A | 30 | 30 | 18 | 0 | 30 | 1319 | 9 |  |
| ec_el_universo | B | 60 | 60 | 57 | 0 | 60 | 2794 | 56 |  |
| ec_expreso | A | 67 | 67 | 63 | 0 | 67 | 3721 | 67 |  |
| ec_la_republica_ec | A | 26 | 26 | 11 | 0 | 26 | 2252 | 25 |  |
| ec_primicias | A | 56 | 56 | 46 | 0 | 56 | 3499 | 56 |  |
| es_abc | A | 72 | 72 | 71 | 0 | 72 | 5761 | 72 |  |
| es_el_correo | A | 70 | 70 | 68 | 0 | 70 | 4266 | 70 |  |
| es_el_mundo | A | 63 | 63 | 53 | 0 | 63 | 4767 | 63 |  |
| es_eldiario_es | A | 56 | 56 | 44 | 0 | 56 | 4829 | 56 |  |
| es_la_vanguardia | A | 70 | 70 | 68 | 0 | 70 | 4040 | 69 |  |
| gt_elsiglo | A | 24 | 24 | 0 | 0 | 24 | 4882 | 24 |  |
| gt_emisoras_unidas | A | 38 | 38 | 18 | 0 | 38 | 4117 | 38 |  |
| gt_lahora | A | 59 | 59 | 50 | 0 | 59 | 3384 | 59 |  |
| gt_prensa_libre | A | 64 | 64 | 59 | 0 | 64 | 3845 | 62 |  |
| gt_publinews | A | 43 | 43 | 21 | 0 | 43 | 1779 | 43 |  |
| hn_contracorriente | A | 11 | 11 | 0 | 0 | 11 | 398 | 1 |  |
| hn_criterio (watched) | A | 11 | 11 | 0 | 0 | 11 | 349 | 0 |  |
| hn_el_heraldo | A | 24 | 24 | 0 | 0 | 6 | 0 | 0 |  |
| hn_hondudiario | A | 31 | 31 | 7 | 0 | 31 | 3623 | 31 |  |
| hn_la_prensa | A | 24 | 24 | 0 | 0 | 20 | 969 | 0 |  |
| hn_radio_progreso | A | 0 | 0 | 0 | 0 | 0 | — | 0 |  |
| mx_el_universal (watched) | A | 34 | 34 | 11 | 0 | 34 | 174 | 0 |  |
| ni_confidencial (watched) | A | 30 | 30 | 6 | 0 | 30 | 875 | 27 |  |
| ni_despacho_505 | A | 21 | 21 | 12 | 0 | 21 | 3138 | 21 |  |
| ni_nicaragua_investiga | A | 17 | 17 | 5 | 0 | 17 | 4715 | 17 |  |
| pa_critica | A | 46 | 46 | 30 | 0 | 46 | 3671 | 46 |  |
| pa_diaadia (watched) | A | 30 | 30 | 14 | 0 | 0 | 0 | 0 |  |
| pa_el_siglo | A | 24 | 24 | 0 | 0 | 24 | 3151 | 0 |  |
| pa_la_prensa | A | 55 | 55 | 40 | 0 | 55 | 3554 | 55 |  |
| pa_laestrelladepanama | A | 24 | 24 | 0 | 0 | 21 | 2742 | 0 |  |
| pa_metro_libre (watched) | A | 66 | 66 | 62 | 0 | 66 | 32 | 0 |  |
| pa_midiario | A | 43 | 43 | 26 | 0 | 43 | 2263 | 43 |  |
| pa_panama_america | A | 40 | 40 | 0 | 19 | 40 | 2766 | 39 |  |
| pe_diario_los_andes | A | 10 | 10 | 2 | 0 | 10 | 806 | 10 |  |
| pe_diario_uno | A | 39 | 39 | 21 | 0 | 39 | 2332 | 39 |  |
| pe_diariocorreo | A | 67 | 67 | 64 | 0 | 67 | 2637 | 67 |  |
| pe_el_buho | A | 30 | 30 | 9 | 0 | 30 | 3638 | 30 |  |
| pe_elperuano (watched) | A | 0 | 0 | 0 | 0 | 0 | — | 0 |  |
| pe_la_republica | A | 7 | 7 | 2 | 0 | 7 | 7917 | 7 |  |
| pr_el_nuevo_dia | A | 60 | 60 | 53 | 0 | 60 | 1391 | 58 |  |
| pr_metro_puerto_rico | A | 56 | 56 | 47 | 0 | 56 | 2506 | 56 |  |
| pr_noticel | A | 15 | 15 | 0 | 1 | 15 | 6632 | 15 |  |
| py_abc_color | A | 65 | 65 | 58 | 0 | 65 | 3103 | 65 |  |
| py_la_nacion | A | 72 | 71 | 71 | 0 | 71 | 2614 | 70 |  |
| py_noticias_cde | A | 6 | 6 | 0 | 0 | 6 | 2462 | 6 |  |
| py_ultima_hora | A | 24 | 24 | 0 | 0 | 21 | 3143 | 21 |  |
| sv_diario_co_latino | A | 22 | 22 | 11 | 0 | 22 | 4280 | 22 |  |
| sv_el_diario_de_hoy | A | 49 | 49 | 33 | 0 | 49 | 5504 | 47 |  |
| uy_el_observador | A | 53 | 53 | 35 | 0 | 53 | 4371 | 53 |  |
| uy_ladiaria | A | 60 | 60 | 26 | 28 | 60 | 5911 | 60 |  |
| uy_montevideo_portal | B | 51 | 51 | 45 | 0 | 51 | 2505 | 35 |  |
| ve_analitica | A | 18 | 18 | 5 | 0 | 18 | 4626 | 18 |  |
| ve_correo_del_caroni | A | 33 | 33 | 17 | 0 | 33 | 1018 | 32 |  |
| ve_efecto_cocuyo | A | 17 | 17 | 10 | 0 | 17 | 4344 | 17 |  |
| ve_el_nacional | A | 62 | 62 | 56 | 0 | 62 | 2372 | 61 |  |
| ve_eldiario | A | 37 | 37 | 14 | 0 | 37 | 8502 | 37 |  |
| ve_eluniversal (watched) | A | 13 | 13 | 0 | 0 | 0 | 0 | 0 |  |
| ve_ultimas_noticias | A | 54 | 54 | 41 | 0 | 54 | 2274 | 54 |  |

## Automated anomaly flags

Flagger `intake-anomaly-flags/1`: mechanical hints from the URL and the extraction's measurements. A flag is a reason to look, not a judgement; no page was removed.

- `author_page_url`: 21
- `duplicate_body_of_other_document`: 131
- `empty_extraction`: 71
- `front_or_top_level_page_url`: 43
- `gallery_or_video_url`: 11
- `publication_date_unknown`: 222
- `sponsored_url`: 2
- `very_short_text`: 223

## Holds that arose

- `https://efectococuyo.com/rss`: bot_challenge

## What this is not

counts of one bounded intake under an experimental extractor; flags are mechanical hints, not labels a person gave; no statement about an outlet's output, about the press of a country or about suitability for a release.
