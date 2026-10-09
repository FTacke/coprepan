# Registry review package

**Status: GENERATED — a recommendation for human review. It registers nothing.** Produced by
`python -m coprepan.registry_review` from `config/outlet_registry.json`
(SHA-256 `0c1bd32aa1ea01aae4754b2b82cc416b2e42ec6ce5d3b8d661a3f2a87d9cad4e`); a test fails if this page and the registry drift apart.
What the reviewer decides: [`INDEX.md`](INDEX.md) §16–§17. Full data per outlet and channel:
[`config/registry_review/outlet_review_package.json`](../../config/registry_review/outlet_review_package.json).

## Summary

| Quantity | Value |
|---|---|
| outlets / channels | 126 / 446 |
| ids that change under the proposed convention | 23 |
| cases that need a judgement | 1 |
| action `CHECK_CHANNEL_ATTRIBUTION` | 6 |
| action `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | 112 |
| action `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | 8 |

Id convention proposed: `{country_id}_{ASCII slug of the display name, words separated by '_'}`.

## Warnings

| Warning | Outlets |
|---|---|
| `channels_of_unknown_type` | 5 |
| `channels_on_hosts_that_are_not_the_outlet` | 5 |
| `channels_on_the_origin_of_another_outlet` | 1 |
| `display_name_shared_across_countries` | 25 |
| `id_spelling_differs_from_the_convention` | 23 |
| `legacy_code_is_not_ascii` | 6 |
| `no_channel` | 8 |
| `no_channel_was_active_in_legacy` | 88 |
| `origin_is_plain_http` | 1 |

## Cases that need a judgement

| Case | Outlets | Question |
|---|---|---|
| `channels_on_the_origin_of_another_outlet` | `pr_el_nuevo_dia`, `pr_primera_hora` | Are these one publisher's outlets sharing infrastructure, or were the channels attributed to the wrong outlet? |

## Legacy name → recommended id

| Legacy | Imported id | Recommended id | Changed |
|---|---|---|---|
| `ARG/clarin` | `ar_clarin` | `ar_clarin` |  |
| `ARG/la_nacion` | `ar_la_nacion` | `ar_la_nacion` |  |
| `ARG/pagina12` | `ar_pagina12` | `ar_pagina_12` | yes |
| `BOL/el_deber` | `bo_el_deber` | `bo_el_deber` |  |
| `BOL/eldiario` | `bo_eldiario` | `bo_el_diario` | yes |
| `BOL/la_razon` | `bo_la_razon` | `bo_la_razon` |  |
| `BOL/lostiempos` | `bo_lostiempos` | `bo_los_tiempos` | yes |
| `BOL/pagina_siete` | `bo_pagina_siete` | `bo_pagina_siete` |  |
| `CHL/biobiochile` | `cl_biobiochile` | `cl_biobiochile` |  |
| `CHL/el_mercurio` | `cl_el_mercurio` | `cl_el_mercurio` |  |
| `CHL/la_tercera` | `cl_la_tercera` | `cl_la_tercera` |  |
| `COL/el_espectador` | `co_el_espectador` | `co_el_espectador` |  |
| `COL/el_tiempo` | `co_el_tiempo` | `co_el_tiempo` |  |
| `COL/elcolombiano` | `co_elcolombiano` | `co_el_colombiano` | yes |
| `COL/elpaís` | `co_elpais` | `co_el_pais` | yes |
| `COL/semana` | `co_semana` | `co_semana` |  |
| `CRI/crhoy` | `cr_crhoy` | `cr_crhoy` |  |
| `CRI/diario_extra` | `cr_diario_extra` | `cr_diario_extra` |  |
| `CRI/la_nacion` | `cr_la_nacion` | `cr_la_nacion` |  |
| `CUB/granma` | `cu_granma` | `cu_granma` |  |
| `CUB/havanatimes` | `cu_havanatimes` | `cu_havana_times` | yes |
| `CUB/juventud_rebelde` | `cu_juventud_rebelde` | `cu_juventud_rebelde` |  |
| `CUB/periódico26` | `cu_periodico26` | `cu_periodico_26` | yes |
| `CUB/trabajadores` | `cu_trabajadores` | `cu_trabajadores` |  |
| `DOM/diario_libre` | `do_diario_libre` | `do_diario_libre` |  |
| `DOM/el_caribe` | `do_el_caribe` | `do_el_caribe` |  |
| `DOM/listin_diario` | `do_listin_diario` | `do_listin_diario` |  |
| `ECU/el_comercio` | `ec_el_comercio` | `ec_el_comercio` |  |
| `ECU/el_universo` | `ec_el_universo` | `ec_el_universo` |  |
| `ECU/primicias` | `ec_primicias` | `ec_primicias` |  |
| `ESP/el_mundo` | `es_el_mundo` | `es_el_mundo` |  |
| `ESP/el_pais` | `es_el_pais` | `es_el_pais` |  |
| `ESP/la_vanguardia` | `es_la_vanguardia` | `es_la_vanguardia` |  |
| `GTM/elperiodico` | `gt_elperiodico` | `gt_elperiodico` |  |
| `GTM/elsiglo` | `gt_elsiglo` | `gt_el_siglo` | yes |
| `GTM/lahora` | `gt_lahora` | `gt_la_hora` | yes |
| `GTM/nuestrodiario` | `gt_nuestrodiario` | `gt_nuestro_diario` | yes |
| `GTM/prensa_libre` | `gt_prensa_libre` | `gt_prensa_libre` |  |
| `GTM/publinews` | `gt_publinews` | `gt_publinews` |  |
| `HND/diariotiempo` | `hn_diariotiempo` | `hn_diario_tiempo` | yes |
| `HND/el_heraldo` | `hn_el_heraldo` | `hn_el_heraldo` |  |
| `HND/hondudiario` | `hn_hondudiario` | `hn_hondudiario` |  |
| `HND/la_prensa` | `hn_la_prensa` | `hn_la_prensa` |  |
| `HND/latribuna` | `hn_latribuna` | `hn_la_tribuna` | yes |
| `HND/proceso_digital` | `hn_proceso_digital` | `hn_proceso_digital` |  |
| `MEX/el_universal` | `mx_el_universal` | `mx_el_universal` |  |
| `MEX/la_jornada` | `mx_la_jornada` | `mx_la_jornada` |  |
| `MEX/milenio` | `mx_milenio` | `mx_milenio` |  |
| `NIC/confidencial` | `ni_confidencial` | `ni_confidencial` |  |
| `NIC/el_19_digital` | `ni_el_19_digital` | `ni_el_19_digital` |  |
| `NIC/la_prensa` | `ni_la_prensa` | `ni_la_prensa` |  |
| `PAN/crítica` | `pa_critica` | `pa_critica` |  |
| `PAN/díaadía` | `pa_diaadia` | `pa_dia_a_dia` | yes |
| `PAN/el_siglo` | `pa_el_siglo` | `pa_el_siglo` |  |
| `PAN/la_prensa` | `pa_la_prensa` | `pa_la_prensa` |  |
| `PAN/laestrelladepanamá` | `pa_laestrelladepanama` | `pa_la_estrella_de_panama` | yes |
| `PAN/metro_libre` | `pa_metro_libre` | `pa_metro_libre` |  |
| `PAN/midiario` | `pa_midiario` | `pa_mi_diario` | yes |
| `PER/diariocorreo` | `pe_diariocorreo` | `pe_diario_correo` | yes |
| `PER/el_comercio` | `pe_el_comercio` | `pe_el_comercio` |  |
| `PER/elperuano` | `pe_elperuano` | `pe_el_peruano` | yes |
| `PER/expreso` | `pe_expreso` | `pe_expreso` |  |
| `PER/la_republica` | `pe_la_republica` | `pe_la_republica` |  |
| `PER/peru21` | `pe_peru21` | `pe_peru21` |  |
| `PRI/el_nuevo_dia` | `pr_el_nuevo_dia` | `pr_el_nuevo_dia` |  |
| `PRI/metro_puerto_rico` | `pr_metro_puerto_rico` | `pr_metro_puerto_rico` |  |
| `PRI/primera_hora` | `pr_primera_hora` | `pr_primera_hora` |  |
| `PRY/abc_color` | `py_abc_color` | `py_abc_color` |  |
| `PRY/la_nacion` | `py_la_nacion` | `py_la_nacion` |  |
| `PRY/ultima_hora` | `py_ultima_hora` | `py_ultima_hora` |  |
| `SLV/diario_el_mundo` | `sv_diario_el_mundo` | `sv_diario_el_mundo` |  |
| `SLV/el_diario_de_hoy` | `sv_el_diario_de_hoy` | `sv_el_diario_de_hoy` |  |
| `SLV/la_prensa_grafica` | `sv_la_prensa_grafica` | `sv_la_prensa_grafica` |  |
| `URY/el_observador` | `uy_el_observador` | `uy_el_observador` |  |
| `URY/el_pais` | `uy_el_pais` | `uy_el_pais` |  |
| `URY/ladiaria` | `uy_ladiaria` | `uy_la_diaria` | yes |
| `URY/larepública` | `uy_larepublica` | `uy_la_republica` | yes |
| `VEN/efecto_cocuyo` | `ve_efecto_cocuyo` | `ve_efecto_cocuyo` |  |
| `VEN/el_nacional` | `ve_el_nacional` | `ve_el_nacional` |  |
| `VEN/eldiario` | `ve_eldiario` | `ve_el_diario` | yes |
| `VEN/eluniversal` | `ve_eluniversal` | `ve_el_universal` | yes |
| `VEN/ultimas_noticias` | `ve_ultimas_noticias` | `ve_ultimas_noticias` |  |

## Outlets

| Recommended id | Name | Origins | Channels | Action | Warnings |
|---|---|---|---|---|---|
| `ar_clarin` | Clarín | https://www.clarin.com | 2 rss, 1 sitemap, 3 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `ar_el_tribuno` | El Tribuno | https://www.eltribuno.com | 2 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ar_infobae` | Infobae | https://www.infobae.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ar_la_nacion` | La Nación | https://www.lanacion.com.ar | 2 rss, 3 sitemap, 3 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `ar_pagina_12` | Página/12 | https://www.pagina12.com.ar | 1 rss, 2 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `ar_perfil` | Perfil | https://www.perfil.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ar_rio_negro` | Río Negro | https://www.rionegro.com.ar | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `bo_brujula_digital` | Brújula Digital | https://brujuladigital.net | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `bo_el_deber` | El Deber | https://eldeber.com.bo | 1 rss, 5 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `bo_el_diario` | El Diario | https://www.eldiario.net | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `id_spelling_differs_from_the_convention`<br>`no_channel` |
| `bo_la_razon` | La Razón | https://www.la-razon.com<br>? larazon.bo | 4 rss, 3 sitemap_index | `CHECK_CHANNEL_ATTRIBUTION` | `no_channel_was_active_in_legacy`<br>`channels_on_hosts_that_are_not_the_outlet` |
| `bo_los_tiempos` | Los Tiempos | https://www.lostiempos.com<br>+ https://lostiempos.com | 1 rss, 1 section_page, 1 unknown | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy`<br>`channels_of_unknown_type` |
| `bo_opinion` | Opinión | https://www.opinion.com.bo | 2 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `bo_pagina_siete` | Página Siete | https://www.paginasiete.bo<br>+ https://paginasiete.bo | 6 rss, 1 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cl_biobiochile` | BioBioChile | https://www.biobiochile.cl<br>? feeds.feedburner.com | 1 rss, 1 sitemap, 2 sitemap_index | `CHECK_CHANNEL_ATTRIBUTION` | `channels_on_hosts_that_are_not_the_outlet` |
| `cl_cooperativa` | Cooperativa | https://www.cooperativa.cl | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cl_el_mercurio` | El Mercurio | https://www.emol.com | 3 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cl_la_discusion` | La Discusión | https://ladiscusion.cl | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cl_la_tercera` | La Tercera | https://www.latercera.com | 2 rss, 1 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `cl_the_clinic` | The Clinic | https://www.theclinic.cl | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `co_diario_del_huila` | Diario del Huila | https://diariodelhuila.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `co_el_espectador` | El Espectador | https://www.elespectador.com | 1 rss, 5 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `co_el_nuevo_siglo` | El Nuevo Siglo | https://www.elnuevosiglo.com.co | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `co_el_tiempo` | El Tiempo | https://www.eltiempo.com | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `no_channel` |
| `co_el_colombiano` | El Colombiano | https://www.elcolombiano.com | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `co_el_pais` | El País | https://www.elpais.com.co | 16 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`legacy_code_is_not_ascii` |
| `co_semana` | Semana | https://www.semana.com | 1 rss, 1 sitemap, 4 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cr_crhoy` | CRHoy | https://www.crhoy.com<br>+ https://crhoy.com | 1 rss, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cr_diario_extra` | Diario Extra | https://www.diarioextra.com | 2 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `cr_la_nacion` | La Nación | https://www.nacion.com | 2 rss, 2 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `cu_14ymedio` | 14ymedio | https://www.14ymedio.com | 1 rss, 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cu_5_de_septiembre` | 5 de Septiembre | https://www.5septiembre.cu | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cu_cubanet` | CubaNet | https://www.cubanet.org | 1 archive, 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cu_granma` | Granma | https://www.granma.cu | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `no_channel` |
| `cu_havana_times` | Havana Times | https://havanatimesenespanol.org | 4 rss, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `cu_juventud_rebelde` | Juventud Rebelde | https://www.juventudrebelde.cu | 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `cu_periodico_26` | Periódico 26 | http://www.periodico26.cu | 1 atom, 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`legacy_code_is_not_ascii`<br>`origin_is_plain_http`<br>`no_channel_was_active_in_legacy` |
| `cu_trabajadores` | Trabajadores | https://www.trabajadores.cu<br>+ http://www.trabajadores.cu | 4 rss, 3 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `do_diario_libre` | Diario Libre | https://www.diariolibre.com | 8 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `do_el_caribe` | El Caribe | https://www.elcaribe.com.do | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `do_el_nacional` | El Nacional | https://elnacional.com.do | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `do_hoy` | Hoy | https://hoy.com.do | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `do_listin_diario` | Listín Diario | https://listindiario.com | 1 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `ec_el_comercio` | El Comercio | https://www.elcomercio.com | 3 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `ec_el_mercurio` | El Mercurio | https://elmercurio.com.ec | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ec_el_universo` | El Universo | https://www.eluniverso.com<br>https://eluniverso.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ec_expreso` | Expreso | https://www.expreso.ec | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ec_la_republica_ec` | La Republica (EC) | https://www.larepublica.ec | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ec_primicias` | Primicias | https://www.primicias.ec | 1 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `es_abc` | ABC | https://www.abc.es | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `es_el_correo` | El Correo | https://www.elcorreo.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `es_el_mundo` | El Mundo | https://www.elmundo.es<br>? e00-elmundo.uecdn.es | 1 rss | `CHECK_CHANNEL_ATTRIBUTION` | `no_channel_was_active_in_legacy`<br>`channels_on_hosts_that_are_not_the_outlet` |
| `es_el_pais` | El País | https://elpais.com<br>? feeds.elpais.com | 1 rss | `CHECK_CHANNEL_ATTRIBUTION` | `channels_on_hosts_that_are_not_the_outlet` |
| `es_eldiario_es` | elDiario.es | https://www.eldiario.es | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `es_la_vanguardia` | La Vanguardia | https://www.lavanguardia.com | 2 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `gt_elperiodico` | elPeriódico | https://elperiodico.com.gt | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `no_channel` |
| `gt_el_siglo` | El Siglo | https://elsiglo.com.gt<br>+ https://www.elsiglo.com.gt | 4 rss, 1 section_page, 1 sitemap, 3 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `gt_emisoras_unidas` | Emisoras Unidas | https://emisorasunidas.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `gt_la_hora` | La Hora | https://lahora.gt | 3 rss, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `gt_nuestro_diario` | Nuestro Diario | https://www.nuestrodiario.com | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `gt_prensa_libre` | Prensa Libre | https://www.prensalibre.com | 5 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `gt_publinews` | Publinews | https://www.publinews.gt | 4 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `hn_contracorriente` | Contracorriente | https://contracorriente.red | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `hn_criterio_hn` | Criterio.hn | https://criterio.hn | 1 rss, 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `hn_diario_tiempo` | Diario Tiempo | https://tiempo.hn | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `hn_el_heraldo` | El Heraldo | https://www.elheraldo.hn | 1 section_page, 2 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `hn_hondudiario` | Hondudiario | https://www.hondudiario.com | 5 rss, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `hn_la_prensa` | La Prensa | https://www.laprensa.hn | 1 section_page, 2 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `hn_la_tribuna` | La Tribuna | https://www.latribuna.hn | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `id_spelling_differs_from_the_convention`<br>`no_channel` |
| `hn_proceso_digital` | Proceso Digital | https://proceso.hn | 4 rss, 1 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `hn_radio_progreso` | Radio Progreso | https://radioprogresohn.net | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `mx_animal_politico` | Animal Politico | https://www.animalpolitico.com<br>+ http://www.animalpolitico.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `mx_el_siglo_de_torreon` | El Siglo de Torreon | https://www.elsiglodetorreon.com.mx | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `mx_el_universal` | El Universal | https://www.eluniversal.com.mx | 5 rss, 15 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `mx_la_jornada` | La Jornada | https://www.jornada.com.mx | 2 atom, 3 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `mx_milenio` | Milenio | https://www.milenio.com | 1 rss, 2 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ni_articulo_66` | Artículo 66 | https://www.articulo66.com | 1 archive, 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `ni_confidencial` | Confidencial | https://www.confidencial.digital<br>https://confidencial.digital | 3 rss, 1 sitemap, 1 sitemap_index, 1 unknown | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy`<br>`channels_of_unknown_type` |
| `ni_despacho_505` | Despacho 505 | https://despacho505.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ni_el_19_digital` | El 19 Digital | https://www.el19digital.com | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ni_la_prensa` | La Prensa | https://www.laprensa.com.ni | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `no_channel` |
| `ni_nicaragua_investiga` | Nicaragua Investiga | https://nicaraguainvestiga.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pa_critica` | CRÍTICA | https://www.critica.com.pa | 1 rss, 2 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `legacy_code_is_not_ascii` |
| `pa_dia_a_dia` | Día a Día | https://www.diaadia.com.pa | 1 rss, 1 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`legacy_code_is_not_ascii`<br>`no_channel_was_active_in_legacy` |
| `pa_el_siglo` | El Siglo | https://elsiglo.com.pa | 2 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pa_la_prensa` | La Prensa | https://www.prensa.com | 1 section_page, 3 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `pa_la_estrella_de_panama` | La Estrella de Panamá | https://www.laestrella.com.pa | 2 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`legacy_code_is_not_ascii`<br>`no_channel_was_active_in_legacy` |
| `pa_metro_libre` | Metro Libre | https://www.metrolibre.com | 2 sitemap, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pa_mi_diario` | Mi Diario | https://www.midiario.com | 2 sitemap, 1 unknown | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`channels_of_unknown_type` |
| `pa_panama_24_horas` | Panama 24 Horas | https://www.panama24horas.com.pa | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pa_panama_america` | Panama America | https://www.panamaamerica.com.pa | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_diario_los_andes` | Diario Los Andes | https://losandes.com.pe | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_diario_uno` | Diario UNO | https://diariouno.pe | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_diario_correo` | Diario Correo | https://diariocorreo.pe | 9 rss, 9 sitemap, 1 sitemap_index, 1 unknown | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`channels_of_unknown_type` |
| `pe_el_buho` | El Buho | https://elbuho.pe | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_el_comercio` | El Comercio | https://elcomercio.pe | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_el_peruano` | El Peruano | https://elperuano.pe | 1 section_page, 23 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `pe_expreso` | Expreso | https://www.expreso.com.pe | 3 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_la_republica` | La República | https://larepublica.pe | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pe_peru21` | Perú21 | https://peru21.pe | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pr_el_nuevo_dia` | El Nuevo Día | https://www.elnuevodia.com | 3 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pr_metro_puerto_rico` | Metro Puerto Rico | https://www.metro.pr | 4 rss, 1 section_page, 1 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pr_noticel` | NotiCel | https://noticel.com | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `pr_primera_hora` | Primera Hora | https://www.primerahora.com | 3 sitemap_index | `CHECK_CHANNEL_ATTRIBUTION` | `no_channel_was_active_in_legacy`<br>`channels_on_the_origin_of_another_outlet` |
| `py_abc_color` | ABC Color | https://www.abc.com.py<br>? api.diarioabc.com.py | 8 rss, 10 sitemap, 2 sitemap_index | `CHECK_CHANNEL_ATTRIBUTION` | `channels_on_hosts_that_are_not_the_outlet` |
| `py_adn_digital` | ADN Digital | https://www.adndigital.com.py | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `py_la_nacion` | La Nación | https://www.lanacion.com.py | 1 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `py_noticias_cde` | Noticias CDE | https://noticiascde.com.py | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `py_ultima_hora` | Última Hora | https://www.ultimahora.com | 1 section_page, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `sv_diario_co_latino` | Diario Co Latino | https://www.diariocolatino.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `sv_diario_el_mundo` | Diario El Mundo | https://diario.elmundo.sv | 1 section_page | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `sv_el_diario_de_hoy` | El Diario de Hoy | https://www.elsalvador.com | 3 rss, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `sv_la_prensa_grafica` | La Prensa Gráfica | https://www.laprensagrafica.com | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `no_channel` |
| `uy_el_observador` | El Observador | https://www.elobservador.com.uy | 1 section_page, 3 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `uy_el_pais` | El País | https://www.elpais.com.uy | 1 rss, 2 sitemap_index, 3 unknown | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy`<br>`channels_of_unknown_type` |
| `uy_la_diaria` | La diaria | https://ladiaria.com.uy | 1 rss, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `uy_la_republica` | La República | https://www.lr21.com.uy | none | `FIND_CHANNELS_OR_LEAVE_UNREGISTERED` | `id_spelling_differs_from_the_convention`<br>`legacy_code_is_not_ascii`<br>`no_channel` |
| `uy_montevideo_portal` | Montevideo Portal | https://www.montevideo.com.uy | 2 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ve_analitica` | Analitica | https://www.analitica.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ve_correo_del_caroni` | Correo del Caroni | https://correodelcaroni.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ve_efecto_cocuyo` | Efecto Cocuyo | https://efectococuyo.com | 4 rss, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `ve_el_impulso` | El Impulso | https://www.elimpulso.com | 1 rss | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `no_channel_was_active_in_legacy` |
| `ve_el_nacional` | El Nacional | https://www.elnacional.com | 3 rss, 2 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |
| `ve_el_diario` | El Diario | https://eldiario.com | 17 rss, 1 sitemap, 2 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention` |
| `ve_el_universal` | El Universal | https://www.eluniversal.com | 1 sitemap | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` | `id_spelling_differs_from_the_convention`<br>`no_channel_was_active_in_legacy` |
| `ve_ultimas_noticias` | Últimas Noticias | https://ultimasnoticias.com.ve | 4 rss, 1 sitemap_index | `CONFIRM_ID_AND_COMPLETE_ATTRIBUTES` |  |

`+` an origin seen on the outlet's own channels that is not yet a registered origin; `?` a host of a
channel that is not the outlet's. Unknown for every outlet: `outlet_type`, `outlet_group`, `city`, `region`, `scope`, `access_model`, `medium`, `timezone`, `same_outlet_basis`; URL rules are placeholders.
