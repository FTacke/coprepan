# Source-health matrix — 2026-11-14

Built by `scripts/build_source_health.py` from stored evidence only (no request). Evidence: the 24-hour intake `in1-20261010-24h`, readiness `2026-10-10.1`, `source_inventory_2026-10-10.1`; holds from the workspace's stored answers (20). **a technical screening from stored evidence; no outlet is OPERATIONALLY_STABLE (CPD-0025: three verified runs on three days); no access decision is made or changed.**

Documented outlets 145 (registered 114, proposed 12, not registered 19); qualified for an intake 87 with 121 channels in 20 countries. Recommendations: `HELD` 18, `NOT_REGISTERED` 19, `READY` 59, `READY_WITH_LIMITATIONS` 8, `REPAIR_REQUIRED` 4, `REQUALIFICATION_REQUIRED` 37.

Screening thresholds: repair_short_or_empty_share 0.5, limitation_short_or_empty_share 0.2, limitation_duplicate_share 0.2, limitation_undated_share 0.5, budget_left_behind_share 0.5, item_ceiling_per_outlet 120 — screening thresholds of the source-health matrix (2026-11-14); technical findings for review, not quality judgements.

## Qualified outlets (24-hour evidence)

| Country | Outlet | Channels (kind: status) | 2xx / requested | New dated found → fetched (left) | Undated-new 2xx | Short/empty · dup · undated | Access | Recommendation | Because |
|---|---|---|---|---|---|---|---|---|---|
| ar | `ar_clarin` | sitemap: OK; rss: OK | 70 / 70 | 458 → 69 (389) | 0 | 2 · 0 · 0 | no hold | `READY_WITH_LIMITATIONS` | 389 of 458 new dated articles discovered were not fetched (budget) |
| ar | `ar_el_tribuno` | rss: OK; rss: NO_NEW_ENTRIES | 64 / 64 | 63 → 55 (8) | 0 | 1 · 0 · 0 | no hold | `READY` |  |
| ar | `ar_infobae` | rss: OK | 41 / 41 | 20 → 20 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| ar | `ar_la_nacion` | sitemap: HISTORICAL_ENTRIES_ONLY; rss: OK | 70 / 70 | 232 → 69 (163) | 0 | 42 · 7 · 0 | no hold | `REPAIR_REQUIRED` | 42 of 70 pages empty or very short: review the extraction and the URL selection on the review cases |
| ar | `ar_pagina12` | sitemap: OK; —: NOT_USABLE | 24 / 24 | 0 → 0 (0) | 0 | 16 · 0 · 24 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours (stock pages only) |
| ar | `ar_perfil` | rss: OK | 63 / 63 | 100 → 56 (44) | 0 | 10 · 1 · 0 | no hold | `READY` |  |
| ar | `ar_rio_negro` | rss: OK | 72 / 72 | 113 → 71 (42) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| bo | `bo_el_deber` | sitemap: NO_NEW_ENTRIES; rss: OK | 53 / 62 | 68 → 48 (20) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| bo | `bo_opinion` | rss: OK; rss: NO_NEW_ENTRIES | 36 / 36 | 15 → 15 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| cl | `cl_biobiochile` | sitemap: HISTORICAL_ENTRIES_ONLY; —: NOT_USABLE | 24 / 24 | 0 → 0 (0) | 0 | 0 · 3 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: cl_biobiochile:ch:sitemap_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| cl | `cl_cooperativa` | rss: OK | 57 / 57 | 40 → 40 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| cl | `cl_la_discusion` | rss: OK | 34 / 34 | 20 → 20 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| cl | `cl_la_tercera` | rss: OK; —: NOT_USABLE | 72 / 72 | 153 → 72 (81) | 0 | 0 · 0 · 0 | no hold | `READY_WITH_LIMITATIONS` | 81 of 153 new dated articles discovered were not fetched (budget) |
| cl | `cl_the_clinic` | rss: OK | 34 / 34 | 18 → 18 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| co | `co_diario_del_huila` | rss: OK | 26 / 26 | 10 → 10 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| co | `co_el_espectador` | sitemap: OK; rss: OK | 65 / 65 | 108 → 60 (48) | 0 | 5 · 0 · 0 | no hold | `READY` |  |
| co | `co_el_nuevo_siglo` | rss: OK | 32 / 32 | 8 → 8 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| co | `co_elpais` | rss: OK; sitemap: OK | 62 / 62 | 55 → 55 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| co | `co_semana` | rss: OK; sitemap: OK | 68 / 68 | 116 → 66 (50) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| cr | `cr_la_nacion` | sitemap: OK; rss: NO_NEW_ENTRIES | 70 / 70 | 80 → 67 (13) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| cu | `cu_14ymedio` | rss: OK; —: NOT_USABLE | 37 / 37 | 17 → 17 (0) | 0 | 0 · 15 · 0 | no hold | `READY_WITH_LIMITATIONS` | many duplicate bodies |
| cu | `cu_havanatimes` | rss: OK; sitemap_index: HISTORICAL_ENTRIES_ONLY | 28 / 28 | 4 → 4 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| cu | `cu_juventud_rebelde` | sitemap_index: HISTORICAL_ENTRIES_ONLY | 22 / 22 | 0 → 0 (0) | 0 | 0 · 0 · 22 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: cu_juventud_rebelde:ch:sitemap_index_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| cu | `cu_trabajadores` | rss: PARTIALLY_UNAVAILABLE; —: NOT_USABLE | 18 / 18 | 8 → 8 (0) | 0 | 0 · 0 · 18 | no hold | `READY_WITH_LIMITATIONS` | channels give no dates: novelty only from later polls; a channel unavailable in some or all polls |
| do | `do_diario_libre` | sitemap: OK; rss: OK | 59 / 59 | 54 → 51 (3) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| do | `do_el_nacional` | rss: OK | 57 / 57 | 49 → 49 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| do | `do_hoy` | rss: OK | 64 / 64 | 64 → 57 (7) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| do | `do_listin_diario` | sitemap: OK; —: NOT_USABLE | 64 / 64 | 86 → 56 (30) | 0 | 1 · 0 · 0 | no hold | `READY` |  |
| ec | `ec_el_comercio` | rss: OK; sitemap: HISTORICAL_ENTRIES_ONLY | 47 / 47 | 31 → 31 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| ec | `ec_el_mercurio` | rss: OK | 30 / 30 | 18 → 18 (0) | 0 | 0 · 21 · 0 | no hold | `READY_WITH_LIMITATIONS` | many duplicate bodies |
| ec | `ec_el_universo` | rss: OK | 60 / 60 | 105 → 57 (48) | 0 | 1 · 0 · 0 | no hold | `READY` |  |
| ec | `ec_expreso` | rss: OK | 67 / 67 | 68 → 63 (5) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| ec | `ec_la_republica_ec` | rss: OK | 26 / 26 | 11 → 11 (0) | 0 | 0 · 1 · 0 | no hold | `READY` |  |
| ec | `ec_primicias` | sitemap: OK; —: NOT_USABLE | 56 / 56 | 46 → 46 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| es | `es_abc` | rss: OK | 72 / 72 | 96 → 71 (25) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| es | `es_el_correo` | rss: OK | 70 / 70 | 89 → 68 (21) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| es | `es_el_mundo` | rss: OK | 63 / 63 | 53 → 53 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| es | `es_eldiario_es` | rss: OK | 56 / 56 | 80 → 44 (36) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| es | `es_la_vanguardia` | rss: OK; rss: OK | 70 / 70 | 158 → 68 (90) | 0 | 0 · 0 · 0 | no hold | `READY_WITH_LIMITATIONS` | 90 of 158 new dated articles discovered were not fetched (budget) |
| gt | `gt_elsiglo` | sitemap: NO_NEW_ENTRIES; rss: NO_NEW_ENTRIES | 24 / 24 | 0 → 0 (0) | 0 | 0 · 0 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours (stock pages only) |
| gt | `gt_emisoras_unidas` | rss: OK | 38 / 38 | 18 → 18 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| gt | `gt_lahora` | rss: OK; sitemap_index: HISTORICAL_ENTRIES_ONLY | 59 / 59 | 50 → 50 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| gt | `gt_prensa_libre` | sitemap: OK; rss: OK | 64 / 64 | 60 → 59 (1) | 0 | 2 · 0 · 0 | no hold | `READY` |  |
| gt | `gt_publinews` | rss: OK; sitemap: OK | 43 / 43 | 21 → 21 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| hn | `hn_contracorriente` | rss: NO_NEW_ENTRIES | 11 / 11 | 0 → 0 (0) | 0 | 10 · 1 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours (stock pages only) |
| hn | `hn_criterio` | rss: NO_NEW_ENTRIES; section_page: NO_NEW_ENTRIES | 11 / 11 | 0 → 0 (0) | 0 | 11 · 10 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours (stock pages only) |
| hn | `hn_el_heraldo` | sitemap: HISTORICAL_ENTRIES_ONLY; —: NOT_USABLE | 24 / 24 | 0 → 0 (0) | 0 | 20 · 0 · 24 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: hn_el_heraldo:ch:sitemap_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| hn | `hn_hondudiario` | rss: OK; sitemap_index: HISTORICAL_ENTRIES_ONLY | 31 / 31 | 7 → 7 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| hn | `hn_la_prensa` | sitemap: HISTORICAL_ENTRIES_ONLY; —: NOT_USABLE | 24 / 24 | 0 → 0 (0) | 0 | 10 · 4 · 24 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: hn_la_prensa:ch:sitemap_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| hn | `hn_radio_progreso` | rss: NO_NEW_ENTRIES | 0 / 0 | 0 → 0 (0) | 0 | 0 · 0 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no item page in the 24-hour intake; no entry first listed during the intake was new by its channel's dates or later polls |
| mx | `mx_el_universal` | sitemap: OK; rss: OK | 34 / 34 | 11 → 11 (0) | 0 | 34 · 0 · 0 | no hold | `REPAIR_REQUIRED` | 34 of 34 pages empty or very short: review the extraction and the URL selection on the review cases |
| ni | `ni_confidencial` | rss: OK; sitemap: NO_NEW_ENTRIES | 30 / 30 | 6 → 6 (0) | 0 | 2 · 1 · 0 | no hold | `READY` |  |
| ni | `ni_despacho_505` | rss: OK | 21 / 21 | 12 → 12 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| ni | `ni_nicaragua_investiga` | rss: OK | 17 / 17 | 5 → 5 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pa | `pa_critica` | rss: OK; sitemap: OK | 46 / 46 | 30 → 30 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pa | `pa_diaadia` | rss: OK; —: NOT_USABLE | 30 / 30 | 14 → 14 (0) | 0 | 30 · 0 · 30 | no hold | `REPAIR_REQUIRED` | 30 of 30 pages empty or very short: review the extraction and the URL selection on the review cases |
| pa | `pa_el_siglo` | sitemap_index: HISTORICAL_ENTRIES_ONLY; sitemap: NO_NEW_ENTRIES | 24 / 24 | 0 → 0 (0) | 0 | 2 · 0 · 24 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: pa_el_siglo:ch:sitemap_index_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| pa | `pa_la_prensa` | sitemap: OK; —: NOT_USABLE | 55 / 55 | 40 → 40 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pa | `pa_laestrelladepanama` | sitemap: NO_NEW_ENTRIES; sitemap_index: HISTORICAL_ENTRIES_ONLY | 24 / 24 | 0 → 0 (0) | 0 | 7 · 0 · 24 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: pa_laestrelladepanama:ch:sitemap_index_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| pa | `pa_metro_libre` | sitemap: OK; sitemap_index: HISTORICAL_ENTRIES_ONLY | 66 / 66 | 77 → 62 (15) | 0 | 66 · 66 · 0 | no hold | `REPAIR_REQUIRED` | 66 of 66 pages empty or very short: review the extraction and the URL selection on the review cases |
| pa | `pa_midiario` | sitemap: OK; sitemap: OK | 43 / 43 | 26 → 26 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pa | `pa_panama_america` | rss: OK | 40 / 40 | 0 → 0 (0) | 19 | 1 · 0 · 0 | no hold | `READY_WITH_LIMITATIONS` | channels give no dates: novelty only from later polls |
| pe | `pe_diario_los_andes` | rss: OK | 10 / 10 | 2 → 2 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pe | `pe_diario_uno` | rss: OK | 39 / 39 | 21 → 21 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pe | `pe_diariocorreo` | rss: OK; sitemap: OK | 67 / 67 | 88 → 64 (24) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pe | `pe_el_buho` | rss: OK | 30 / 30 | 9 → 9 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pe | `pe_elperuano` | sitemap: UNAVAILABLE; —: NOT_USABLE | 0 / 0 | 0 → 0 (0) | 0 | 0 · 0 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no item page in the 24-hour intake; 2 polls, no document read (2 unavailable); HTTP_404 |
| pe | `pe_la_republica` | rss: OK | 7 / 7 | 2 → 2 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pr | `pr_el_nuevo_dia` | sitemap_index: OK; —: NOT_USABLE | 60 / 60 | 60 → 53 (7) | 0 | 2 · 0 · 0 | no hold | `READY` |  |
| pr | `pr_metro_puerto_rico` | rss: OK; sitemap: NO_NEW_ENTRIES | 56 / 56 | 47 → 47 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| pr | `pr_noticel` | section_page: OK | 15 / 15 | 0 → 0 (0) | 1 | 0 · 0 · 0 | no hold | `READY_WITH_LIMITATIONS` | channels give no dates: novelty only from later polls |
| py | `py_abc_color` | rss: OK; sitemap: NO_NEW_ENTRIES | 65 / 65 | 58 → 58 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| py | `py_la_nacion` | sitemap: OK | 71 / 72 | 105 → 71 (34) | 0 | 1 · 0 · 0 | no hold | `READY` |  |
| py | `py_noticias_cde` | rss: NO_NEW_ENTRIES | 6 / 6 | 0 → 0 (0) | 0 | 0 · 0 · 0 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours (stock pages only) |
| py | `py_ultima_hora` | sitemap_index: HISTORICAL_ENTRIES_ONLY; —: NOT_USABLE | 24 / 24 | 0 → 0 (0) | 0 | 3 · 0 · 3 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours: py_ultima_hora:ch:sitemap_index_001 listed only entries dated before the window (not a news stream); find the outlet's news channel (a live requalification) |
| sv | `sv_diario_co_latino` | rss: OK | 22 / 22 | 11 → 11 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| sv | `sv_el_diario_de_hoy` | rss: OK; sitemap_index: OK | 49 / 49 | 33 → 33 (0) | 0 | 1 · 0 · 0 | no hold | `READY` |  |
| uy | `uy_el_observador` | sitemap: OK; —: NOT_USABLE | 53 / 53 | 36 → 35 (1) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| uy | `uy_ladiaria` | rss: OK; sitemap_index: OK | 60 / 60 | 26 → 26 (0) | 28 | 0 · 0 · 0 | no hold | `READY` |  |
| uy | `uy_montevideo_portal` | rss: OK; rss: OK | 51 / 51 | 51 → 45 (6) | 0 | 0 · 0 · 16 | no hold | `READY` |  |
| ve | `ve_analitica` | rss: OK | 18 / 18 | 5 → 5 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| ve | `ve_correo_del_caroni` | rss: OK | 33 / 33 | 17 → 17 (0) | 0 | 0 · 1 · 0 | no hold | `READY` |  |
| ve | `ve_efecto_cocuyo` | rss: HELD; —: NOT_USABLE; —: NOT_USABLE | 17 / 17 | 10 → 10 (0) | 0 | 0 · 0 · 0 | HELD: every channel held | `HELD` | HELD: every channel held |
| ve | `ve_el_nacional` | sitemap: OK; rss: OK | 62 / 62 | 56 → 56 (0) | 0 | 1 · 0 · 0 | no hold | `READY` |  |
| ve | `ve_eldiario` | sitemap: OK; rss: NO_NEW_ENTRIES | 37 / 37 | 14 → 14 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |
| ve | `ve_eluniversal` | sitemap: NO_NEW_ENTRIES | 13 / 13 | 0 → 0 (0) | 0 | 13 · 0 · 13 | no hold | `REQUALIFICATION_REQUIRED` | no new article in 24 hours (stock pages only) |
| ve | `ve_ultimas_noticias` | rss: OK; —: NOT_USABLE | 54 / 54 | 41 → 41 (0) | 0 | 0 · 0 · 0 | no hold | `READY` |  |

## Not qualified for an intake (registered, proposed, held or not registered)

| Country | Outlet | Registration | Inventory stage | Recommendation | Because |
|---|---|---|---|---|---|
| bo | `bo_brujula_digital` | registered | REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: CHANNEL_HTTP_ERROR |
| bo | `bo_correo_del_sur` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| bo | `bo_eldiario` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: NO_EVIDENCED_CHANNEL |
| bo | `bo_la_razon` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: DOMAIN_CHANGE |
| bo | `bo_lostiempos` | registered | TECHNICALLY_QUALIFIED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: LISTING_NEEDS_RULE |
| bo | `bo_pagina_siete` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: CLOSED |
| cl | `cl_el_mercurio` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: IDENTITY_OPEN |
| co | `co_el_tiempo` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: LEGAL_HOLD |
| co | `co_elcolombiano` | registered | TECHNICALLY_QUALIFIED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: LISTING_NEEDS_RULE |
| co | `co_la_silla_vacia` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| cr | `cr_crhoy` | registered | REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: CHANNEL_HTTP_ERROR |
| cr | `cr_delfino_cr` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| cr | `cr_diario_extra` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| cr | `cr_el_observador` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| cr | `cr_semanario_universidad` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| cu | `cu_5_de_septiembre` | registered | REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: ROBOTS_UNREADABLE |
| cu | `cu_cubanet` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| cu | `cu_diario_de_cuba` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: research names the outlet and no origin |
| cu | `cu_granma` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: NO_EVIDENCED_CHANNEL |
| cu | `cu_periodico26` | registered | REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: ROBOTS_NOT_REACHED |
| do | `do_acento` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| do | `do_el_caribe` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| es | `es_el_pais` | registered | ACQUISITION_VERIFIED | `HELD` | HELD: captcha |
| gt | `gt_elperiodico` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: CLOSED |
| gt | `gt_nuestrodiario` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| gt | `gt_plaza_publica` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| gt | `gt_prensa_comunitaria` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| hn | `hn_diariotiempo` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| hn | `hn_latribuna` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: NO_EVIDENCED_CHANNEL |
| hn | `hn_proceso_digital` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| mx | `mx_animal_politico` | registered | REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: CHANNEL_HTTP_ERROR |
| mx | `mx_el_siglo_de_torreon` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| mx | `mx_el_sol_de_mexico` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| mx | `mx_expansion` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: research names the outlet and no origin |
| mx | `mx_la_jornada` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| mx | `mx_milenio` | registered | REGISTERED | `HELD` | HELD: blocked |
| ni | `ni_articulo66` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| ni | `ni_el_19_digital` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| ni | `ni_la_prensa` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: DOMAIN_CHANGE |
| pa | `pa_panama_24_horas` | registered | REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: ROBOTS_UNREADABLE |
| pa | `pa_tvn_noticias` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| pe | `pe_el_comercio` | registered | TECHNICALLY_QUALIFIED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: LISTING_NEEDS_RULE |
| pe | `pe_expreso` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| pe | `pe_peru21` | registered | REGISTERED | `HELD` | HELD: bot_challenge |
| pr | `pr_centro_de_periodismo_investigativo_cpi` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| pr | `pr_el_vocero` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| pr | `pr_primera_hora` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: IDENTITY_OPEN |
| py | `py_adn_digital` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| py | `py_diario_hoy` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| sv | `sv_diario_el_mundo` | registered | TECHNICALLY_QUALIFIED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: LISTING_NEEDS_RULE |
| sv | `sv_diario_el_salvador` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| sv | `sv_el_faro` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| sv | `sv_la_prensa_grafica` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: NO_EVIDENCED_CHANNEL |
| uy | `uy_busqueda` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| uy | `uy_el_pais` | registered | REGISTERED | `HELD` | HELD: named in the readiness file's holds |
| uy | `uy_el_telegrafo` | not registered | NOT_REGISTERED | `NOT_REGISTERED` | inventory stage NOT_REGISTERED: deferred: no channel from a search result or the publisher; addresses inferred from a content system's usual layout are not requested |
| uy | `uy_larepublica` | proposed | NOT_REGISTERED | `REQUALIFICATION_REQUIRED` | not qualified for an intake: NO_EVIDENCED_CHANNEL |
| ve | `ve_el_impulso` | registered | REGISTERED | `HELD` | HELD: bot_challenge |

Review cases (fetch ids of flagged pages, up to five per outlet) and every channel's counts are in the JSON file beside this one.
