# Source matrix after the weekend qualification (2026-11-14/15)

Built by `scripts/build_weekend_qualification.py` from the evidence of 8 waves (1100 transport requests). Six dimensions, kept apart; no single READY. Coverage: a weekend without new entries is `NO_RECENT_ENTRY_AT_THE_WEEKEND`, not a defect. Content quality: share of the outlet's answered pages that `content-quality/2` (CANDIDATE) accepts on `article_html/0.1.0` (CANDIDATE). Screening thresholds are stated in the JSON; they are choices, not scientific criteria.

| Outlet | Waves | Discovery | Coverage | Raw | Extraction (baseline) | Content quality | Accepted | Next intake | Reason |
|---|---|---|---|---|---|---|---:|---|---|
| `ar_clarin` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ar_el_tribuno` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ar_infobae` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ar_la_nacion` | wq-1, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_SOME | 6/12 | **QUALIFIED** | every dimension holds |
| `ar_pagina12` | wq-1, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_NONE | 0/9 | **NOT_QUALIFIED** | no page accepted by the content-quality gate |
| `ar_perfil` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ar_rio_negro` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `bo_brujula_digital` | wq-1 | FUNCTIONAL | CURRENT | FAILED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | raw acquisition FAILED |
| `bo_el_deber` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 3/4 | **QUALIFIED** | every dimension holds |
| `bo_lostiempos` | wq-1 | FUNCTIONAL | UNDATED | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | raw acquisition NOT_ATTEMPTED |
| `bo_opinion` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `cl_biobiochile` | wq-1, wc-1 | FUNCTIONAL | STALE_CHANNEL | FUNCTIONAL | GOOD | ACCEPTED_SOME | 6/12 | **NOT_QUALIFIED** | coverage STALE_CHANNEL: a current channel is needed (registry amendment) |
| `cl_cooperativa` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `cl_la_discusion` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `cl_la_tercera` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `cl_the_clinic` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `co_diario_del_huila` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `co_el_espectador` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_SOME | 1/6 | **QUALIFIED_WITH_LIMITS** | only 17% of the pages accepted: low yield |
| `co_el_nuevo_siglo` | wq-3 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_SOME | 3/6 | **QUALIFIED** | every dimension holds |
| `co_elcolombiano` | wq-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `co_elpais` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `co_semana` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `cr_crhoy` | wq-1, wc-1 | FAILED | NO_ENTRIES | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | discovery FAILED |
| `cr_diario_extra` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_SOME | 1/6 | **QUALIFIED_WITH_LIMITS** | only 17% of the pages accepted: low yield |
| `cr_la_nacion` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `cu_14ymedio` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `cu_5_de_septiembre` | wq-1 | NOT_REACHED | NO_ENTRIES | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | discovery NOT_REACHED |
| `cu_havanatimes` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `cu_juventud_rebelde` | wq-1, wc-1 | FUNCTIONAL | STALE_CHANNEL | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/5 | **NOT_QUALIFIED** | coverage STALE_CHANNEL: a current channel is needed (registry amendment) |
| `cu_periodico26` | wq-1 | NOT_REACHED | NO_ENTRIES | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | discovery NOT_REACHED |
| `cu_trabajadores` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/5 | **QUALIFIED** | every dimension holds |
| `do_diario_libre` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `do_el_nacional` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `do_hoy` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `do_listin_diario` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ec_el_comercio` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ec_el_mercurio` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ec_el_universo` | wq-4 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 3/3 | **QUALIFIED** | every dimension holds |
| `ec_expreso` | wq-4 | ANSWERED_WITHOUT_ENTRIES | NO_ENTRIES | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **NOT_QUALIFIED** | discovery ANSWERED_WITHOUT_ENTRIES |
| `ec_la_republica_ec` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ec_primicias` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `es_abc` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `es_el_correo` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `es_el_mundo` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `es_eldiario_es` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `es_la_vanguardia` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `gt_elsiglo` | wq-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `gt_emisoras_unidas` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `gt_lahora` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `gt_prensa_libre` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `gt_publinews` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `hn_contracorriente` | wq-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `hn_criterio` | wq-1, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_MOST | 12/12 | **QUALIFIED** | every dimension holds |
| `hn_el_heraldo` | wq-1, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_SOME | 1/11 | **QUALIFIED_WITH_LIMITS** | only 9% of the pages accepted: low yield |
| `hn_hondudiario` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `hn_la_prensa` | wq-1, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_NONE | 0/12 | **NOT_QUALIFIED** | no page accepted by the content-quality gate |
| `hn_proceso_digital` | wq-7 | FUNCTIONAL | CURRENT | FAILED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | raw acquisition FAILED |
| `hn_radio_progreso` | wq-2 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `mx_animal_politico` | wq-2 | NOT_REACHED | NO_ENTRIES | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | discovery NOT_REACHED |
| `mx_el_universal` | wq-2, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_MOST | 12/12 | **QUALIFIED** | every dimension holds |
| `ni_confidencial` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `ni_despacho_505` | wq-5 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ni_nicaragua_investiga` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `pa_critica` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `pa_diaadia` | wq-2 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `pa_el_siglo` | wq-2, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 10/12 | **QUALIFIED** | every dimension holds |
| `pa_la_prensa` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `pa_laestrelladepanama` | wq-2, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_NONE | 0/12 | **NOT_QUALIFIED** | no page accepted by the content-quality gate |
| `pa_metro_libre` | wq-2, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_SOME | 5/12 | **QUALIFIED_WITH_LIMITS** | only 42% of the pages accepted: low yield |
| `pa_midiario` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `pa_panama_24_horas` | wq-2 | NOT_REACHED | NO_ENTRIES | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | discovery NOT_REACHED |
| `pa_panama_america` | wq-6 | FUNCTIONAL | UNDATED | FUNCTIONAL | GOOD | ACCEPTED_MOST | 3/3 | **QUALIFIED_WITH_LIMITS** | the channels state no dates: what is new cannot be told from the channel |
| `pe_diario_los_andes` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |
| `pe_diario_uno` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `pe_diariocorreo` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `pe_el_buho` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `pe_el_comercio` | wq-2 | FUNCTIONAL | UNDATED | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | raw acquisition NOT_ATTEMPTED |
| `pe_elperuano` | wq-2, wc-1 | FUNCTIONAL | CURRENT | FUNCTIONAL | POOR | ACCEPTED_MOST | 12/12 | **QUALIFIED** | every dimension holds |
| `pe_la_republica` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `pr_el_nuevo_dia` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_SOME | 2/6 | **QUALIFIED_WITH_LIMITS** | only 33% of the pages accepted: low yield |
| `pr_metro_puerto_rico` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_SOME | 1/6 | **QUALIFIED_WITH_LIMITS** | only 17% of the pages accepted: low yield |
| `pr_noticel` | wq-6 | FUNCTIONAL | UNDATED | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/5 | **QUALIFIED_WITH_LIMITS** | the channels state no dates: what is new cannot be told from the channel |
| `py_abc_color` | wq-6 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `py_la_nacion` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `py_noticias_cde` | wq-2 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `py_ultima_hora` | wq-2 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `sv_diario_co_latino` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `sv_diario_el_mundo` | wq-2 | FUNCTIONAL | UNDATED | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | raw acquisition NOT_ATTEMPTED |
| `sv_el_diario_de_hoy` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `uy_el_observador` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `uy_el_pais` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_SOME | 2/6 | **QUALIFIED_WITH_LIMITS** | only 33% of the pages accepted: low yield |
| `uy_ladiaria` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `uy_montevideo_portal` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 3/3 | **QUALIFIED** | every dimension holds |
| `ve_analitica` | wq-7 | FAILED | NO_ENTRIES | NOT_ATTEMPTED | NOT_MEASURED | NOT_MEASURED | 0/0 | **NOT_QUALIFIED** | discovery FAILED |
| `ve_correo_del_caroni` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | LIMITED | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ve_el_nacional` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 5/6 | **QUALIFIED** | every dimension holds |
| `ve_eldiario` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 6/6 | **QUALIFIED** | every dimension holds |
| `ve_eluniversal` | wq-2 | FUNCTIONAL | STALE_CHANNEL | FUNCTIONAL | POOR | ACCEPTED_NONE | 0/6 | **NOT_QUALIFIED** | coverage STALE_CHANNEL: a current channel is needed (registry amendment) |
| `ve_ultimas_noticias` | wq-7 | FUNCTIONAL | CURRENT | FUNCTIONAL | GOOD | ACCEPTED_MOST | 4/6 | **QUALIFIED** | every dimension holds |

## Totals

- **DISCOVERY_FUNCTIONAL**: FUNCTIONAL 92, NOT_REACHED 4, FAILED 2, ANSWERED_WITHOUT_ENTRIES 1
- **NEW_ARTICLE_COVERAGE**: CURRENT 84, NO_ENTRIES 7, UNDATED 5, STALE_CHANNEL 3
- **RAW_ACQUISITION_FUNCTIONAL**: FUNCTIONAL 88, NOT_ATTEMPTED 9, FAILED 2
- **TEXT_EXTRACTION_QUALITY**: GOOD 65, LIMITED 14, NOT_MEASURED 11, POOR 9
- **CONTENT_QUALITY_ACCEPTED**: ACCEPTED_MOST 74, NOT_MEASURED 11, ACCEPTED_SOME 10, ACCEPTED_NONE 4
- **QUALIFIED_FOR_NEXT_INTAKE**: QUALIFIED 72, NOT_QUALIFIED 18, QUALIFIED_WITH_LIMITS 9

## Documented outlets without live evidence this weekend (27)

| Outlet | Registration | Prior recommendation | Why not tested |
|---|---|---|---|
| `bo_eldiario` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `bo_la_razon` | proposed | REQUALIFICATION_REQUIRED | URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `bo_pagina_siete` | proposed | REQUALIFICATION_REQUIRED | URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `cl_el_mercurio` | proposed | REQUALIFICATION_REQUIRED | URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `co_el_tiempo` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `cu_cubanet` | registered | HELD | origin held by evidence: ['https://www.cubanet.org'] (bot_challenge) |
| `cu_granma` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `do_el_caribe` | registered | HELD | origin held by evidence: ['https://www.elcaribe.com.do'] (bot_challenge) |
| `es_el_pais` | registered | HELD | origin held by evidence: ['https://elpais.com'] (captcha) |
| `gt_elperiodico` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `gt_nuestrodiario` | registered | HELD | every selected channel is a held URL: ['https://www.nuestrodiario.com/tu-comunidad'] |
| `hn_diariotiempo` | registered | HELD | every selected channel is a held URL: ['https://tiempo.hn/'] |
| `hn_latribuna` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `mx_el_siglo_de_torreon` | registered | HELD | origin held by evidence: ['https://www.elsiglodetorreon.com.mx'] (bot_challenge) |
| `mx_la_jornada` | registered | HELD | origin held by evidence: ['https://www.jornada.com.mx'] (bot_challenge) |
| `mx_milenio` | registered | HELD | origin held by evidence: ['https://www.milenio.com'] (blocked) |
| `ni_articulo66` | registered | HELD | origin held by evidence: ['https://www.articulo66.com'] (bot_challenge) |
| `ni_el_19_digital` | registered | HELD | every selected channel is a held URL: ['https://www.el19digital.com/'] |
| `ni_la_prensa` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `pe_expreso` | registered | HELD | origin held by evidence: ['https://www.expreso.com.pe'] (bot_challenge) |
| `pe_peru21` | registered | HELD | origin held by evidence: ['https://peru21.pe'] (bot_challenge) |
| `pr_primera_hora` | proposed | REQUALIFICATION_REQUIRED | URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `py_adn_digital` | registered | HELD | every selected channel is a held URL: ['https://www.adndigital.com.py/feed'] |
| `sv_la_prensa_grafica` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `uy_larepublica` | proposed | REQUALIFICATION_REQUIRED | no channel; URL rules are a placeholder; no time zone (not registered complete enough for a live request) |
| `ve_efecto_cocuyo` | registered | HELD | CPD-0028 admits it by its feed only, and that feed is a held URL (2026-10-10): not asked |
| `ve_el_impulso` | registered | HELD | origin held by evidence: ['https://www.elimpulso.com'] (bot_challenge) |
