# Source discovery inventory — version 2026-10-09.1

**Generated** by `scripts/build_source_discovery_inventory.py` from the JSON beside it; do not edit. A reading aid: the
registry, the request log and the preserved packs stay the records. Prediscovery entries are **hypotheses** from passive
research (search results and third-party pages; no request to any publisher) and are not observations of a server.

Outlets: 82 in 20 countries. Legacy channels: 352. Researched candidate channels: 301.

| Flag | Outlets | Rule |
|---|---|---|
| `IMPORTED` | 82 | the outlet or channel is a row of the legacy import (registry `legacy_observed`) |
| `DISCOVERED` | 79 | at least one possible discovery channel is known: a legacy channel, or a candidate of a prediscovery file. Known is not tested |
| `QUALIFIED` | 2 | COPREPAN 3.0 itself has read a channel document of the outlet from a real server and the current parser finds at least one item entry with a usable address in it (from preserved bytes; a replay counts, a search result does not) |
| `REGISTERED` | 5 | registry `registration_status` is `registered` (a registration record exists) |
| `ACQUISITION_VERIFIED` | 1 | in one bounded run at least 5 item pages of the outlet were answered 2xx, are RAW_PRESERVED with verified fixity, and their extraction was replayed without network. One run: a technical single success, nothing about duration |
| `OPERATIONALLY_STABLE` | 0 | ACQUISITION_VERIFIED in at least three runs on at least three different days within an observation window of at least fourteen days, with no access-control hold in between. No outlet can have it yet |

Route classes: `ACCESS_CONTROL_HOLD` 1, `CLOSED` 2, `INDEX_EXPANSION_CANDIDATE` 3, `LISTING_ONLY` 6, `NO_ROUTE_KNOWN` 3, `STANDARD_CHANNEL_CANDIDATE` 67.

Priority: priority_score = country_need x feasibility x coverage_gain. country_need: 3 when no outlet of the country was LEGACY_PRODUCTIVE_REPEATED, 2 when exactly one was, else 1. feasibility: 3 for a standard channel candidate with search evidence of 2026-10-09 or legacy success evidence, 2 for a standard or index candidate with legacy evidence only, 1 for a listing-only or pattern-inferred route, 0 when the outlet is closed, held by an access control or has no known route. coverage_gain: 2 when the legacy system never got a usable article from the outlet (LEGACY_NEVER_PRODUCTIVE, LEGACY_NO_CHANNEL), else 1. A stated scenario rule for ordering work, not a measurement and not a statement about an outlet's worth.

| Outlet | Legacy class | Legacy `ok` rows | Status (research) | Route class | Flags | Best researched candidate (evidence) | Score |
|---|---|---|---|---|---|---|---|
| `ar_clarin` | PRODUCTIVE_REPEATED | 1758 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.clarin.com/rss/lo-ultimo/` (search_evidence) | 6 |
| `ar_la_nacion` | PRODUCTIVE_SPORADIC | 1 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml` (search_evidence) | 6 |
| `ar_pagina12` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.pagina12.com.ar/rss/portada` (search_evidence) | 12 |
| `bo_el_deber` | PRODUCTIVE_REPEATED | 2556 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED, REGISTERED | rss `https://eldeber.com.bo/feed` (legacy_evidence) | 6 |
| `bo_eldiario` | NO_CHANNEL | 0 | uncertain | NO_ROUTE_KNOWN | IMPORTED | none | 0 |
| `bo_la_razon` | NEVER_PRODUCTIVE | 0 | moved | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://larazon.bo/feed/` (legacy_evidence) | 8 |
| `bo_lostiempos` | PRODUCTIVE_SPORADIC | 1 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.lostiempos.com/rss.xml` (legacy_evidence) | 6 |
| `bo_pagina_siete` | PRODUCTIVE_SPORADIC | 10 | closed | CLOSED | IMPORTED, DISCOVERED | none | 0 |
| `cl_biobiochile` | PRODUCTIVE_REPEATED | 898 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://feeds.feedburner.com/radiobiobio/NNeJ` (search_evidence) | 3 |
| `cl_el_mercurio` | NEVER_PRODUCTIVE | 0 | operating | INDEX_EXPANSION_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.emol.com/sitemap/sitemapIndex.xml` (legacy_evidence) | 4 |
| `cl_la_tercera` | PRODUCTIVE_REPEATED | 1259 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml` (search_evidence) | 3 |
| `co_el_espectador` | PRODUCTIVE_REPEATED | 1408 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | news_sitemap `https://www.elespectador.com/arc/outboundfeeds/news-sitemap/?outputType=xml` (legacy_evidence) | 6 |
| `co_el_tiempo` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.eltiempo.com/rss/colombia.xml` (search_evidence) | 12 |
| `co_elcolombiano` | NO_CHANNEL | 0 | operating | LISTING_ONLY | IMPORTED, DISCOVERED | html_listing `https://www.elcolombiano.com/medellin` (search_evidence) | 4 |
| `co_elpais` | PRODUCTIVE_SPORADIC | 21 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.elpais.com.co/arc/outboundfeeds/rss/?outputType=xml` (legacy_evidence) | 6 |
| `co_semana` | PRODUCTIVE_SPORADIC | 2 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | news_sitemap `https://www.semana.com/arc/outboundfeeds/news-sitemap/?outputType=xml` (search_evidence) | 6 |
| `cr_crhoy` | PRODUCTIVE_REPEATED | 775 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.crhoy.com/sitemap.xml` (search_evidence) | 2 |
| `cr_diario_extra` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.diarioextra.com/feed` (legacy_evidence) | 4 |
| `cr_la_nacion` | PRODUCTIVE_REPEATED | 1198 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.nacion.com/rss/` (search_evidence) | 3 |
| `cu_granma` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://en.granma.cu/feed` (search_evidence) | 6 |
| `cu_havanatimes` | PRODUCTIVE_REPEATED | 51 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://havanatimesenespanol.org/feed/` (legacy_evidence) | 3 |
| `cu_juventud_rebelde` | PRODUCTIVE_REPEATED | 77 | operating | INDEX_EXPANSION_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.juventudrebelde.cu/sitemap.xml` (legacy_evidence) | 2 |
| `cu_periodico26` | NEVER_PRODUCTIVE | 0 | uncertain | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `http://www.periodico26.cu/index.php/es/?format=feed&type=rss` (legacy_evidence) | 4 |
| `cu_trabajadores` | PRODUCTIVE_REPEATED | 207 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.trabajadores.cu/feed` (search_evidence) | 3 |
| `do_diario_libre` | PRODUCTIVE_REPEATED | 2180 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED, QUALIFIED, REGISTERED, ACQ_VERIFIED | rss `https://www.diariolibre.com/rss/portada.xml` (search_evidence) | 3 |
| `do_el_caribe` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.elcaribe.com.do/feed/` (cms_pattern_inference) | 4 |
| `do_listin_diario` | PRODUCTIVE_REPEATED | 1574 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | section_feed `https://listindiario.com/rss/larepublica/` (search_evidence) | 3 |
| `ec_el_comercio` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.elcomercio.com/feed/` (search_evidence) | 18 |
| `ec_el_universo` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.eluniverso.com/arc/outboundfeeds/rss/?outputType=xml` (search_evidence) | 18 |
| `ec_primicias` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.primicias.ec/feed/` (search_evidence) | 18 |
| `es_el_mundo` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://e00-elmundo.uecdn.es/elmundo/rss/portada.xml` (search_evidence) | 12 |
| `es_el_pais` | PRODUCTIVE_REPEATED | 1142 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada` (search_evidence) | 6 |
| `es_la_vanguardia` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.lavanguardia.com/rss/home.xml` (search_evidence) | 12 |
| `gt_elperiodico` | NO_CHANNEL | 0 | closed | CLOSED | IMPORTED, DISCOVERED | rss `https://elperiodico.com.gt/rss` (search_evidence) | 0 |
| `gt_elsiglo` | PRODUCTIVE_REPEATED | 525 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://elsiglo.com.gt/feed/` (legacy_evidence) | 3 |
| `gt_lahora` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://lahora.gt/feed/` (search_evidence) | 6 |
| `gt_nuestrodiario` | NO_CHANNEL | 0 | operating | LISTING_ONLY | IMPORTED, DISCOVERED | html_listing `https://www.nuestrodiario.com/tu-comunidad` (search_evidence) | 2 |
| `gt_prensa_libre` | PRODUCTIVE_REPEATED | 609 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.prensalibre.com/feed/` (search_evidence) | 3 |
| `gt_publinews` | PRODUCTIVE_REPEATED | 736 | uncertain | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.publinews.gt/arc/outboundfeeds/google-news-feed/?outputType=xml` (legacy_evidence) | 3 |
| `hn_diariotiempo` | NO_CHANNEL | 0 | operating | LISTING_ONLY | IMPORTED, DISCOVERED | html_listing `https://tiempo.hn/` (search_evidence) | 2 |
| `hn_el_heraldo` | PRODUCTIVE_SPORADIC | 7 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `http://feeds.feedburner.com/elheraldo_titulares` (search_evidence) | 3 |
| `hn_hondudiario` | PRODUCTIVE_REPEATED | 100 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.hondudiario.com/feed/` (search_evidence) | 3 |
| `hn_la_prensa` | PRODUCTIVE_SPORADIC | 6 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap `https://www.laprensa.hn/sitemap.xml` (legacy_evidence) | 2 |
| `hn_latribuna` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.latribuna.hn/feed/` (cms_pattern_inference) | 2 |
| `hn_proceso_digital` | PRODUCTIVE_REPEATED | 1763 | operating | ACCESS_CONTROL_HOLD | IMPORTED, DISCOVERED, REGISTERED | rss `https://proceso.hn/feed/` (search_evidence) | 0 |
| `mx_el_universal` | PRODUCTIVE_REPEATED | 1889 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | news_sitemap `https://www.eluniversal.com.mx/arc/outboundfeeds/news/?outputType=xml` (legacy_evidence) | 6 |
| `mx_la_jornada` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.jornada.com.mx/rss/edicion.xml?v=1` (search_evidence) | 12 |
| `mx_milenio` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.milenio.com/rss` (search_evidence) | 12 |
| `ni_confidencial` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://confidencial.digital/feed/` (search_evidence) | 18 |
| `ni_el_19_digital` | NO_CHANNEL | 0 | operating | LISTING_ONLY | IMPORTED, DISCOVERED | html_listing `https://www.el19digital.com/` (search_evidence) | 6 |
| `ni_la_prensa` | NO_CHANNEL | 0 | moved | LISTING_ONLY | IMPORTED, DISCOVERED | html_listing `https://www.laprensani.com/deportes` (search_evidence) | 6 |
| `pa_critica` | PRODUCTIVE_REPEATED | 210 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.critica.com.pa/rss.xml` (legacy_evidence) | 3 |
| `pa_diaadia` | NEVER_PRODUCTIVE | 0 | uncertain | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.diaadia.com.pa/rss.xml` (legacy_evidence) | 4 |
| `pa_el_siglo` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://elsiglo.com.pa/megasitemap.xml` (legacy_evidence) | 4 |
| `pa_la_prensa` | PRODUCTIVE_REPEATED | 1350 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | news_sitemap `https://www.prensa.com/arc/outboundfeeds/news-sitemap/?outputType=xml` (legacy_evidence) | 3 |
| `pa_laestrelladepanama` | PRODUCTIVE_SPORADIC | 1 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.laestrella.com.pa/megasitemap.xml` (legacy_evidence) | 3 |
| `pa_metro_libre` | PRODUCTIVE_SPORADIC | 2 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.metrolibre.com/megasitemap.xml` (legacy_evidence) | 3 |
| `pa_midiario` | PRODUCTIVE_REPEATED | 583 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | news_sitemap `https://www.midiario.com/arc/outboundfeeds/news-sitemap/?outputType=xml` (legacy_evidence) | 3 |
| `pe_diariocorreo` | PRODUCTIVE_REPEATED | 3542 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://diariocorreo.pe/arcio/google-news-feed/` (legacy_evidence) | 6 |
| `pe_el_comercio` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://elcomercio.pe/arcio/rss/` (cms_pattern_inference) | 8 |
| `pe_elperuano` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | news_sitemap `https://elperuano.pe/news-sitemap.xml` (legacy_evidence) | 8 |
| `pe_expreso` | NO_CHANNEL | 0 | operating | LISTING_ONLY | IMPORTED, DISCOVERED | html_listing `https://www.expreso.com.pe/categoria/top-de-noticias/` (search_evidence) | 4 |
| `pe_la_republica` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | section_feed `https://larepublica.pe/rss/economia` (search_evidence) | 12 |
| `pe_peru21` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://peru21.pe/arcio/rss/` (cms_pattern_inference) | 12 |
| `pr_el_nuevo_dia` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.elnuevodia.com/arc/outboundfeeds/news-sitemap-index?outputType=xml` (legacy_evidence) | 8 |
| `pr_metro_puerto_rico` | PRODUCTIVE_REPEATED | 1389 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.metro.pr/arc/outboundfeeds/sitemap-index/?outputType=xml` (legacy_evidence) | 6 |
| `pr_primera_hora` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.primerahora.com/arc/outboundfeeds/news-sitemap-index?outputType=xml` (cms_pattern_inference) | 8 |
| `py_abc_color` | PRODUCTIVE_REPEATED | 2367 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.abc.com.py/arc/outboundfeeds/news-sitemap-index/?outputType=xml` (legacy_evidence) | 3 |
| `py_la_nacion` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED, REGISTERED | sitemap `https://www.lanacion.com.py/arc/outboundfeeds/sitemap/?outputType=xml` (legacy_evidence) | 4 |
| `py_ultima_hora` | PRODUCTIVE_REPEATED | 350 | operating | INDEX_EXPANSION_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.ultimahora.com/news-sitemap.xml` (legacy_evidence) | 2 |
| `sv_diario_el_mundo` | NO_CHANNEL | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `http://elmundo.com.sv/feed` (search_evidence) | 12 |
| `sv_el_diario_de_hoy` | PRODUCTIVE_REPEATED | 1321 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.elsalvador.com/rss.xml` (legacy_evidence) | 6 |
| `sv_la_prensa_grafica` | NO_CHANNEL | 0 | operating | NO_ROUTE_KNOWN | IMPORTED | none | 0 |
| `uy_el_observador` | NEVER_PRODUCTIVE | 0 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap_index `https://www.elobservador.com.uy/sitemap/news-full/sitemap-index.xml` (legacy_evidence) | 4 |
| `uy_el_pais` | PRODUCTIVE_REPEATED | 727 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.elpais.com.uy/rss` (legacy_evidence) | 3 |
| `uy_ladiaria` | PRODUCTIVE_REPEATED | 895 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://ladiaria.com.uy/feeds/articulos/` (legacy_evidence) | 3 |
| `uy_larepublica` | NO_CHANNEL | 0 | uncertain | NO_ROUTE_KNOWN | IMPORTED | none | 0 |
| `ve_efecto_cocuyo` | PRODUCTIVE_REPEATED | 443 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED, QUALIFIED, REGISTERED | rss `https://efectococuyo.com/feed/` (legacy_evidence) | 3 |
| `ve_el_nacional` | PRODUCTIVE_REPEATED | 1232 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://www.elnacional.com/feed/` (legacy_evidence) | 3 |
| `ve_eldiario` | PRODUCTIVE_REPEATED | 427 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://eldiario.com/feed/` (legacy_evidence) | 3 |
| `ve_eluniversal` | NEVER_PRODUCTIVE | 0 | uncertain | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | sitemap `https://www.eluniversal.com/sitemap.xml` (legacy_evidence) | 4 |
| `ve_ultimas_noticias` | PRODUCTIVE_REPEATED | 218 | operating | STANDARD_CHANNEL_CANDIDATE | IMPORTED, DISCOVERED | rss `https://ultimasnoticias.com.ve/feed/` (legacy_evidence) | 3 |

## Proposed new outlets (60; proposals only, nothing registered)

| Country | Name | Origin | First candidate (evidence) |
|---|---|---|---|
| ar | Infobae | https://www.infobae.com | section_feed `https://www.infobae.com/arc/outboundfeeds/rss/category/america/mundo/` (search_evidence) |
| ar | Perfil | https://www.perfil.com | rss `https://www.perfil.com/feed` (search_evidence) |
| ar | Río Negro | https://www.rionegro.com.ar | rss `https://www.rionegro.com.ar/feed` (search_evidence) |
| bo | Brújula Digital | https://brujuladigital.net | rss `https://brujuladigital.net/rss.xml` (search_evidence) |
| bo | Correo del Sur | https://correodelsur.com | none found |
| bo | Opinión | https://www.opinion.com.bo | rss `https://www.opinion.com.bo/rss/` (search_evidence) |
| cl | Cooperativa | https://www.cooperativa.cl | rss `https://www.cooperativa.cl/noticias/site/tax/port/all/rss_3___1.xml` (search_evidence) |
| cl | La Discusión | https://ladiscusion.cl | rss `https://ladiscusion.cl/feed/` (search_evidence) |
| cl | The Clinic | https://www.theclinic.cl | rss `https://www.theclinic.cl/feed/` (search_evidence) |
| co | Diario del Huila | https://diariodelhuila.com | rss `https://diariodelhuila.com/feed/` (search_evidence) |
| co | El Nuevo Siglo | https://www.elnuevosiglo.com.co | rss `https://www.elnuevosiglo.com.co/rss.xml` (search_evidence) |
| co | La Silla Vacía | https://www.lasillavacia.com | rss `https://www.lasillavacia.com/feed/` (cms_pattern_inference) |
| cr | Delfino.cr | https://delfino.cr | none found |
| cr | El Observador | https://observador.cr | none found |
| cr | Semanario Universidad | https://semanariouniversidad.com | rss `https://semanariouniversidad.com/feed/` (cms_pattern_inference) |
| cu | 14ymedio | https://www.14ymedio.com | rss `https://www.14ymedio.com/rss` (search_evidence) |
| cu | 5 de Septiembre | https://www.5septiembre.cu | rss `https://www.5septiembre.cu/feed` (search_evidence) |
| cu | CubaNet | https://www.cubanet.org | rss `https://www.cubanet.org/feed` (search_evidence) |
| do | Acento | https://acento.com.do | none found |
| do | El Nacional | https://elnacional.com.do | rss `https://elnacional.com.do/rss/home.xml` (search_evidence) |
| do | Hoy | https://hoy.com.do | rss `https://hoy.com.do/rss/home.xml` (search_evidence) |
| ec | El Mercurio | https://elmercurio.com.ec | rss `https://elmercurio.com.ec/feed/` (search_evidence) |
| ec | Expreso | https://www.expreso.ec | rss `https://www.expreso.ec/rss/home.xml` (search_evidence) |
| ec | La Republica (EC) | https://www.larepublica.ec | rss `https://www.larepublica.ec/feed/` (search_evidence) |
| es | ABC | https://www.abc.es | rss `https://www.abc.es/rss/2.0/portada/` (search_evidence) |
| es | El Correo | https://www.elcorreo.com | rss `https://www.elcorreo.com/rss/2.0/portada` (search_evidence) |
| es | elDiario.es | https://www.eldiario.es | rss `https://www.eldiario.es/rss` (search_evidence) |
| gt | Emisoras Unidas | https://emisorasunidas.com | rss `https://emisorasunidas.com/feed/` (search_evidence) |
| gt | Plaza Publica | https://www.plazapublica.com.gt | rss `http://feeds.feedburner.com/PlazaPublicaRssFeed` (search_evidence) |
| gt | Prensa Comunitaria | https://prensacomunitaria.org | none found |
| hn | Contracorriente | https://contracorriente.red | rss `https://contracorriente.red/feed/` (search_evidence) |
| hn | Criterio.hn | https://criterio.hn | rss `https://criterio.hn/feed/` (search_evidence) |
| hn | Radio Progreso | https://radioprogresohn.net | rss `https://radioprogresohn.net/feed/` (search_evidence) |
| mx | Animal Politico | https://www.animalpolitico.com | rss `http://www.animalpolitico.com/feed/` (search_evidence) |
| mx | El Siglo de Torreon | https://www.elsiglodetorreon.com.mx | rss `https://www.elsiglodetorreon.com.mx/index.xml` (search_evidence) |
| mx | El Sol de Mexico | https://oem.com.mx/elsoldemexico | rss `https://www.elsoldemexico.com.mx/rss.xml` (search_evidence) |
| ni | Articulo 66 | https://www.articulo66.com | rss `https://www.articulo66.com/feed/` (search_evidence) |
| ni | Despacho 505 | https://despacho505.com | rss `https://despacho505.com/feed/` (search_evidence) |
| ni | Nicaragua Investiga | https://nicaraguainvestiga.com | rss `https://nicaraguainvestiga.com/feed/` (search_evidence) |
| pa | Panama 24 Horas | https://www.panama24horas.com.pa | rss `https://www.panama24horas.com.pa/panama/feed/` (search_evidence) |
| pa | Panama America | https://www.panamaamerica.com.pa | rss `https://www.panamaamerica.com.pa/rss/recent/index.xml` (search_evidence) |
| pa | TVN Noticias | https://www.tvn-2.com | none found |
| pe | Diario Los Andes | https://losandes.com.pe | rss `https://losandes.com.pe/feed/` (search_evidence) |
| pe | Diario UNO | https://diariouno.pe | rss `https://diariouno.pe/feed/` (search_evidence) |
| pe | El Buho | https://elbuho.pe | rss `https://elbuho.pe/feed/` (search_evidence) |
| pr | Centro de Periodismo Investigativo (CPI) | https://www.periodismoinvestigativo.com | none found |
| pr | El Vocero | https://www.elvocero.com (domain from background knowledge, unverified) | none found |
| pr | NotiCel | https://www.noticel.com (domain from background knowledge, unverified) | none found |
| py | ADN Digital | https://www.adndigital.com.py | rss `https://www.adndigital.com.py/feed` (search_evidence) |
| py | Diario HOY | https://www.hoy.com.py | none found |
| py | Noticias CDE | https://noticiascde.com.py | rss `https://noticiascde.com.py/feed` (search_evidence) |
| sv | Diario Co Latino | https://www.diariocolatino.com | rss `https://www.diariocolatino.com/feed` (search_evidence) |
| sv | Diario El Salvador | https://diarioelsalvador.com | html_listing `https://diarioelsalvador.com/<slug>/<id>` (search_evidence) |
| sv | El Faro | https://elfaro.net | none found |
| uy | Busqueda | unknown (busqueda.com.uy from background knowledge, unverified) | none found |
| uy | El Telegrafo | unknown (eltelegrafo.com seen in an ahrefs listing; eltelegrafo.com.uy unverified) | none found |
| uy | Montevideo Portal | https://www.montevideo.com.uy | rss `https://www.montevideo.com.uy/anxml.aspx?59` (search_evidence) |
| ve | Analitica | https://www.analitica.com | rss `https://www.analitica.com/feed` (search_evidence) |
| ve | Correo del Caroni | https://correodelcaroni.com | rss `https://correodelcaroni.com/feed` (search_evidence) |
| ve | El Impulso | https://www.elimpulso.com | rss `https://www.elimpulso.com/feed` (search_evidence) |
