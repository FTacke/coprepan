# Phase-3 review sample — text structure, section mapping, provenance, quality gate (2026-11-15)

**For the operator's scientific acceptance (CPD-0039 § 14).** Real pages, drawn deterministically from the stored
item pages (seed `phase3-review-2026-11-15/<group name>`, one page per outlet in a group). Each row: the outlet, the address, what the
new rules found (verbatim where it is a publisher's note), the content-quality/3 decision, and a fetch id prefix to open
the page locally (`python scripts/study_phase3_metadata.py show --page-cache <cache> --fetch <prefix>`). Enter your
judgement in the last column: `ok`, or what is wrong. The agent's own reading of these groups is in the run report and is
**not** a human gold standard. Nothing here is binding until you decide (CPD-0039 *Not decided here*).

## Subtitle from the page's own statement (alternativeHeadline / description) — 2759 pages, 8 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `pe_diariocorreo` | https://diariocorreo.pe/edicion/arequipa/hospital-honorio-delgado-de-arequipa-joven-requeria-una-protesis-y-termina-amputado-noticia/ | T: Hospital Honorio Delgado de Arequipa: Joven requería una prótesis y te — S: Daniel requiere el factor VII, medicamento que no cuenta el hospital Honorio Delgado; su madre espera que pued | ACCEPT  | `a901e2bef9140eca` | |
| `ar_clarin` | https://www.clarin.com/sociedad/aumenta-preocupacion-escuelas-alumnos-trucan-ia-fotos-companeras_0_S8cmkT7QvD.html | T: Aumenta la preocupación en las escuelas por los alumnos que trucan con — S: El caso del Colegio Modelo de Lomas de Zamora puso en alerta a los establecimientos educativos. | ACCEPT  | `15ae19680c79818e` | |
| `pr_el_nuevo_dia` | https://www.elnuevodia.com/estilos-de-vida/familia/notas/las-casas-embrujadas-y-experiencias-de-halloween/ | T: Halloween 2026 en Puerto Rico: casas embrujadas y experiencias de terr — S: Desde casas embrujadas hasta teatro y actividades familiares convertirán la isla en escenario de terror | ACCEPT  | `7f8395c35b389e74` | |
| `cu_14ymedio` | https://www.14ymedio.com/cartelera/lizt-alfonso-dance-cuba-celebra_1_1131737.html | T: Lizt Alfonso Dance Cuba celebra la Fiesta Nacional de España en el Tea — S: Lugar: Teatro Martí, calle Dragones, esquina a Zulueta, La Habana Vieja, Cuba. | ACCEPT  | `87bceea3aa73f0e6` | |
| `ar_perfil` | https://www.perfil.com/noticias/internacional/trump-esta-en-pie-de-guerra-con-noruega-por-el-nobel-de-la-paz-no-se-ni-quien-es-esa-mujer.phtml | T: Trump "en pie de guerra" con Noruega por el Nobel de la Paz: "Ni sé qu — S: "Yo resolví 8 guerras, estoy cerca de terminar con 2 más, recuperé los rehenes israelíes, gané la guerra en Ve | ACCEPT  | `d7d5219a3ce0d21a` | |
| `es_eldiario_es` | https://www.eldiario.es/euskadi/mertxe-aizpurua-no-ira-listas-eh-bildu-generales-no-continuara-congreso_1_13578124.html | T: Mertxe Aizpurua no irá en las listas de EH Bildu para las generales y  — S: Periodista y exalcaldesa de Usurbil, ha ocupado un escaño desde 2019 y fue la primera de la izquierda abertzal | ACCEPT  | `d83d698e9f8b3068` | |
| `uy_ladiaria` | https://ladiaria.com.uy/deporte/articulo/2026/10/la-lucha-por-el-descenso-al-rojo-vivo-cerro-gano-e-igualo-a-wanderers-que-cayo-en-el-viera/ | T: La lucha por el descenso al rojo vivo: Cerro ganó e igualó a Wanderers — S: El villero le ganó un partido increíble a Defensor Sporting en el Franzini, mientras que Boston River se impus | ACCEPT  | `91e83e6551d7f95d` | |
| `do_diario_libre` | https://www.diariolibre.com/mundo/america-latina/2026/10/07/maltrato-pinguinos-en-mar-del-plata-y-denuncia-de-fundacion-fauna/3681767 | T: ONG denuncia maltrato y comercialización de animales en acuario argent — S: La denuncia incluye el traslado de pingüinos a más de 500 kilómetros del mar, lo que podría poner en riesgo su | ACCEPT  | `a8389be7ea8a2fd0` | |

## Subtitle by markup alone (the weaker path) — 194 pages, 8 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `ve_eldiario` | https://eldiario.com/2026/10/08/resumen-noticias-jueves-8-de-octubre/ | S: Maduro y Cilia Flores enfrentan nuevos cargos en EE UU. Además, Anne Carson ganó el Nobel de Literatura y Salomón Rondón cumplió 20 años com | ACCEPT  | `b322a392f39aef0a` | |
| `es_el_mundo` | https://www.elmundo.es/elecciones/elecciones-generales/2026/10/10/6aca05d5fc6c83c9488b45bf.html | S: Irene Montero y la cúpula morada acusan al sistema de "matar en vida" con los alquileres y reclaman una redistribución de la riqueza frente  | ACCEPT  | `3d2f255f4b2e9bc2` | |
| `cl_the_clinic` | https://www.theclinic.cl/2026/10/09/el-despliegue-por-chiloe-y-rapa-nui-que-mantuvo-a-las-autoridades-de-interior-fuera-de-santiago-al-momento-del-aluvion-en-las-condes/ | S: La ausencia en las primeras horas de la emergencia del ministro Claudio Alvarado y del subsecretario Máximo Pavez no pasó desapercibida, sob | ACCEPT  | `09c6a6f28d1edff6` | |
| `ve_efecto_cocuyo` | https://efectococuyo.com/opinion/la-urgencia-de-un-acuerdo-historico/ | S: “Es hora de asumir la construcción de un gran acuerdo de unidad democrática que responda al mandato de libertad” | ACCEPT  | `29aea817fd1ebb12` | |
| `cr_la_nacion` | https://www.nacion.com/opinion/foros/cuando-la-distancia-tambien-enferma/PNT3DW36NBHR7HMTRS5SXRIJ6Q/story/ | S: Si acceder a un tratamiento exige conseguir dinero para viajar, encontrar dónde dormir o separarse por semanas del trabajo y de la familia,  | ACCEPT  | `33c66d8dcf5e276c` | |
| `ar_infobae` | https://www.infobae.com/america/mundo/2026/10/07/el-avance-eritreo-en-adigrat-eleva-la-tension-y-amenaza-con-extender-la-guerra-del-norte-de-etiopia/ | S: La presencia foránea fue reportada por habitantes, que describieron vehículos militares dirigiéndose hacia Mekelle, después de la retirada i | ACCEPT  | `9b93beb5df6b9906` | |
| `co_el_espectador` | https://www.elespectador.com/deportes/ciclismo/nairo-quintana-en-entrevista/ | S: Lo bueno que es estar informado y de una manera diferente desde tu correo electrónico. | REJECT (too_short, template_body) | `dcf263e57c33ed75` | |
| `do_diario_libre` | https://www.diariolibre.com/deportes/futbol/2026/10/10/cristiano-ronaldo-federacion-portuguesa-abre-proceso-disciplinario/3685084 | S: La Federación ha decidido dar "carácter urgente al procedimiento" que lleva a cabo su Comisión de Instrucción Disciplinaria | ACCEPT  | `71bd4d658fed3f4d` | |

## No subtitle found (recall check: is there one the rules missed?) — 1470 pages, 6 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `hn_hondudiario` | https://www.hondudiario.com/2026/10/09/distribucion-de-agua-podria-cambiar-pero-los-racionamientos-seguiran-hasta-mayo/ | T: Distribución de agua podría cambiar, pero los racionamientos seguirán hasta mayo | ACCEPT  | `888330de0a353be9` | |
| `co_diario_del_huila` | https://diariodelhuila.com/fondo-milagro-ya-tiene-contrato-y-recursos-pero-aun-faltan-las-reglas-para-reconstruir/ | T: Fondo Milagro ya tiene contrato y recursos, pero aún faltan las reglas para reconstruir | ACCEPT  | `cb61728ed735889c` | |
| `cl_biobiochile` | https://www.biobiochile.cl/noticias/nacional/region-de-los-lagos/2025/07/22/convenios-en-agosto-se-define-continuidad-de-investigacion-por-traspaso-de-dineros-a-fundacion-kimun.shtml | T: Convenios: en agosto se define continuidad de investigación por traspaso de dineros a Fundación Kimü | REJECT (incomplete_against_stated_body) | `e4b0510d1df6e745` | |
| `pa_midiario` | https://www.midiario.com/policiales/tremendo-arsenal-oculto-en-portobelo-hallan-mas-de-11-mil-municiones-para-fusiles/ | T: ¡Tremendo arsenal oculto en Portobelo! Hallan más de 11 mil municiones para fusiles | ACCEPT  | `f3a35fe6bc1ec80a` | |
| `gt_prensa_libre` | https://www.prensalibre.com/deportes/futbol-nacional/concacaf-eligio-el-gol-de-matts-evans-como-el-mejor-de-la-fase-de-grupos-de-la-liga-de-naciones-breaking/ | T: Concacaf eligió el gol de Matt Evans como el mejor de la fase de grupos de la Liga de Naciones | REJECT (not_running_prose, template_body) | `642d3ff87236c97a` | |
| `py_la_nacion` | https://www.lanacion.com.py/futboledicion-impresa/2026/10/11/se-sacudio-con-una-goleada/ | T: La Nación | REJECT (not_running_prose) | `52a11ea14f886779` | |

## IPTC mapping known — 1655 pages, 8 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `es_eldiario_es` | https://www.eldiario.es/politica/eh-bildu-erc-reeditan-coalicion-presentan-senado_1_13576976.html | Política → medtop:11000000 Política (closeMatch) | ACCEPT  | `77a2ef02b0f34835` | |
| `es_abc` | https://www.abc.es/deportes/real-madrid/mourinho-entrega-senalados-pide-bernabeu-inteligente-20261010011741-nt.html | deportes → medtop:15000000 Deporte (closeMatch) | ACCEPT  | `1bae15915bc3f89a` | |
| `pr_el_nuevo_dia` | https://www.elnuevodia.com/entretenimiento/farandula/notas/esa-es-una-historia-que-le-pertenece-allegados-de-laura-hernandez-desmienten-versiones-sobre-su-diagnostico-de-cancer/ | Farándula → medtop:01000000 Artes, cultura, entretenimiento y medios (broadMatch) | ACCEPT  | `481df82e6eae0196` | |
| `es_el_mundo` | https://www.elmundo.es/deportes/futbol/primera-division/2026/10/10/6aca8a5dfc6c83537b8b457e.html | Deportes/futbol/primera-division → medtop:15000000 Deporte (closeMatch), medtop:20001065 Fútbol (closeMatch) | ACCEPT  | `819e5fcbcd8c74f6` | |
| `ec_el_universo` | https://eluniverso.com/deportes/campeonato-ecuatoriano/liga-pro-asi-marcha-la-tabla-de-posiciones-del-cuadrangular-por-cupo-a-copa-sudamericana-tras-derrota-de-emelec-ante-guayaquil-city-nota/ | Deportes → medtop:15000000 Deporte (closeMatch) | REJECT (too_short) | `ef2849e65db7d6ab` | |
| `ar_clarin` | https://www.clarin.com/deportes/argentina-brasil-amistosos-alto-voltaje-prueba-mundial-femenino-2027_0_KjumcakLdw.html | Deportes → medtop:15000000 Deporte (closeMatch) | ACCEPT  | `d0febc09324e92f0` | |
| `co_diario_del_huila` | https://diariodelhuila.com/dos-adultas-mayores-fueron-victimas-de-violencia-sexual-en-santander-hay-un-capturado-y-en-narino-aun-esperan-respuestas/ | Judicial → medtop:02000000 Policía y justicia (broadMatch) | ACCEPT  | `26931d37fd3f13b4` | |
| `pe_la_republica` | https://larepublica.pe/economia/precio-del-dolar/2026/10/11/precio-del-dolar-hoy-en-peru-domingo-11-de-octubre-consulta-el-tipo-de-cambio-para-compra-y-venta-397100 | Economía → medtop:04000000 Economía, negocios y finanzas (closeMatch) | REJECT (too_short, template_body) | `734dcfc91b40a005` | |

## IPTC mapping not decided: ambiguous section — 303 pages, 5 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `pa_panama_america` | https://www.panamaamerica.com.pa/sociedad/caja-navidena-del-ima-incluira-nuevos-productos-y-obsequiara-una-rosca-de-pan-1267244 | Sociedad | ACCEPT  | `c9da43766a01f95e` | |
| `ar_clarin` | https://www.clarin.com/astrologia/horoscopo-piscis-hoy-11-octubre-2026-predicciones-salud-amor-dinero_0_RLTeDN1fsT.html | Astrología; astrologia | ACCEPT  | `7d6d4c2668d2e274` | |
| `pa_la_prensa` | https://www.prensa.com/sociedad/que-relacion-tiene-la-delincuencia-con-la-basura-en-san-miguelito/ | Sociedad; Sociedad | ACCEPT  | `fd2005db4aef185b` | |
| `pa_critica` | https://www.critica.com.pa/sucesos/el-dia-que-temblo-panama-tambien-corrio-sangre-en-colon-517846 | Sucesos | ACCEPT  | `380b817186a9b64a` | |
| `ni_confidencial` | https://confidencial.digital/revista-niu/google-lanza-synthid-detector-una-herramienta-para-identificar-contenidos-generados-con-ia/ | Revista Niú | ACCEPT  | `80c11dd7960e69ed` | |

## IPTC mapping unknown: section unmapped — 276 pages, 5 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `cl_the_clinic` | https://www.theclinic.cl/2026/10/09/la-resurreccion-de-un-gigante-el-lancia-gamma-y-la-reconstruccion-de-un-imperio-automotriz/ | AUTO TEST | ACCEPT  | `0fcf7fea22ace1f0` | |
| `es_el_correo` | https://www.elcorreo.com/gente-estilo/maria-patino-vuelve-television-tras-ano-ausencia-20261010122851-nt.html | Gente Estilo; gente-estilo | ACCEPT  | `770a7b12cacc2cdd` | |
| `hn_contracorriente` | https://contracorriente.red/2026/10/03/ese-dia-mis-palabras-no-valian-nada/ | crónica periodística, agresión, Denuncia; derechos sexuales y reproductivos | REJECT (duplicate_of_earlier) | `44b0bb50265a2700` | |
| `es_abc` | https://www.abc.es/bienestar/felicidad-despues-receta-unica-formula-magica-20261008012808-nt.html | bienestar; bienestar | ACCEPT  | `9dd78784ae2d69a7` | |
| `ni_confidencial` | https://confidencial.digital/pxmolina/pxmolina-xl/historieta-semanal-el-que-y-el-como/ | Historieta Semanal | REJECT (too_short, not_running_prose, template_body) | `0041cdecef686736` | |

## AI: article declared generated — 1 pages, 1 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `ar_clarin` | https://www.clarin.com/internacional/juan-roig-empresario-espanol-presidente-mercadona-cajera-valencia-paga-impuestos-madrid-deberiamos-pagar-mismo_0_5VDbBgv2EW.html | Nota generada con inteligencia artificial bajo supervisión y edición humana. | ACCEPT  | `fd671770ce216ebb` | |

## AI: article declared assisted — 23 pages, 4 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `co_elpais` | https://www.elpais.com.co/deportes/seleccion-colombia-femenina-vencio-a-venezuela-y-suma-confianza-antes-del-segundo-amistoso-1029.html | *Este artículo fue creado con ayuda de una inteligencia artificial que utiliza machine learning para producir texto similar al humano, y curado por un periodist | ACCEPT  | `fa9752e56f25fa56` | |
| `ni_nicaragua_investiga` | https://nicaraguainvestiga.com/politica/175639-felix-maradiaga-anuncia-su-disposicion-a-regresar-a-nicaragua-pese-a-los-riesgos-para-impulsar-la-democracia-desde-dentro/ | *Este artículo fue elaborado mediante la colaboración estratégica entre nuestro equipo editorial y herramientas de inteligencia artificial. | ACCEPT  | `cb1f83d2d8402b16` | |
| `ve_eldiario` | https://eldiario.com/2026/10/09/tsj-avalo-prorroga-de-60-dias-del-estado-de-emergencia-economica-en-venezuela/ | Este contenido incluye redacción realizada con la inteligencia artificial de ChatGPT. Supervisado y verificado por el equipo editorial. Conoce nuestra política  | ACCEPT  | `dda7e44068aab39b` | |
| `ar_la_nacion` | https://www.lanacion.com.ar/estados-unidos/de-ser-abandonado-en-un-basurero-a-convertirse-en-un-magnate-tecnologico-la-impresionante-vida-de-nid10102026/ | Este contenido fue producido por un equipo de LA NACION con la asistencia de la IA | ACCEPT  | `b1ed47baeef20bfe` | |

## AI: article declared machine-translated — 10 pages, 4 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `gt_prensa_libre` | https://www.prensalibre.com/internacional/bbc-news-mundo-internacional/christa-pike-sale-del-hospital-y-regresa-a-prision-10-dias-despues-de-sobrevivir-a-su-fallida-ejecucion/ | Este artículo fue escrito originalmente en inglés y usamos una herramienta de inteligencia artificial para traducirlo. Un periodista de la BBC revisó el texto a | ACCEPT  | `9385bc29a130859c` | |
| `pr_el_nuevo_dia` | https://www.elnuevodia.com/entretenimiento/peliculas-series/notas/subastan-el-lightsaber-que-utilizo-darth-vader-en-el-duelo-de-i-am-your-father/ | Esta historia fue traducida del inglés al español con una herramienta de inteligencia artificial y fue revisada por un editor antes de su publicación. | ACCEPT  | `d5c69cf5a21b4464` | |
| `bo_el_deber` | https://eldeber.com.bo/bbc/un-hombre-muere-tras-ser-atacado-por-un-tigre-en-un-parque-de-vida-silvestre-20261010173350 | Este artículo fue escrito originalmente en inglés y usamos una herramienta de inteligencia artificial para traducirlo. Un periodista de la BBC revisó el texto a | ACCEPT  | `137ffb7dd4767795` | |
| `pa_la_prensa` | https://www.prensa.com/mundo/al-menos-12-muertos-y-mas-de-300-heridos-en-un-ataque-contra-el-aeropuerto-de-riad/ | Este artículo fue escrito originalmente en inglés y usamos una herramienta de inteligencia artificial para traducirlo. Periodistas de la BBC revisaron el texto  | ACCEPT  | `a6c76f134d21ccd8` | |

## AI: machine summary beside the article (component) — 103 pages, 3 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `cl_biobiochile` | https://www.biobiochile.cl/noticias/servicios/toma-nota/2025/07/22/se-viene-cambio-de-hora-en-chile-cuando-es-el-hito-que-marcara-el-fin-del-horario-de-invierno.shtml | Resumen generado con una herramienta de Inteligencia Artificial desarrollada por BioBioChile y revisado por el autor de este artículo. | ACCEPT  | `5dc9561f7de0811b` | |
| `co_el_espectador` | https://www.elespectador.com/economia/gobierno-radica-mensaje-de-urgencia-para-sumar-cop-27-billones-al-presupuesto-para-que/ | Resumen generado por IA. Para más detalles, consulte el artículo completo. | ACCEPT  | `d8ad289b1dd723d1` | |
| `cl_the_clinic` | https://www.theclinic.cl/2026/10/10/fernanda-fuentes-jurado-de-masterchef-en-tvn-no-estoy-interpretando-ningun-personaje-estoy-jugando-el-rol-de-mi-vida/ | Estos resúmenes son generados por inteligencia artificial y chequeados por el periodista a cargo. | ACCEPT  | `c593aa376cca6e1d` | |

## AI: audio or image only (component, article text unknown) — 136 pages, 4 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `cl_the_clinic` | https://www.theclinic.cl/2026/11/14/el-dramatico-llamado-de-la-hija-de-gonzalo-ramirez-desde-la-lista-de-espera-por-un-doble-trasplante-despertamos-cada-manana-sin-saber-si-llegara-la-llamada-del-hospital/ | Escucha esta nota Audio generado por IA | ACCEPT  | `84561de1c37c9825` | |
| `es_la_vanguardia` | https://www.lavanguardia.com/cultura/20261010/11656126/ultimo-concierto-oques-grasses.html | Audio generado por IA | ACCEPT  | `117ea7efcfb6854c` | |
| `pa_el_siglo` | https://elsiglo.com.pa/curiosidades/el-rincon-de-la-suerte | Imagen ilustrativa generada con IA( Imagen ilustrativa generada con IA ) | REJECT (too_short) | `78a1a36f7719b3ce` | |
| `es_el_mundo` | https://www.elmundo.es/economia/2026/10/10/6ac8f367fc6c83ce0b8b45a8.html | Audio generado con IA | ACCEPT  | `2d868403e97290dd` | |

## AI mentioned in the text, no disclosure (must stay unknown) — 10 pages, 4 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `ve_el_nacional` | https://www.elnacional.com/2026/10/la-infraestructura-empresarial-se-convierte-en-el-proximo-desafio-de-la-inteligencia-artificial/ | T: La infraestructura empresarial se convierte en el próximo desafío de la inteligencia artificial | ACCEPT  | `fc5f81272de66c35` | |
| `pe_el_buho` | https://elbuho.pe/2026/11/inteligencia-artificial-y-empleo-los-posgrados-clave-para-mantener-la-competitividad-profesional/ | T: Inteligencia artificial y empleo: los posgrados clave para mantener la competitividad profesional | ACCEPT  | `d555280bd142c3d5` | |
| `ec_el_universo` | https://eluniverso.com/entretenimiento/musica/jose-gonzalez-compositor-sueco-argentino-hice-una-colaboracion-con-la-inteligencia-artificial-y-me-termino-gustando-nota/ | T: José González, compositor sueco-argentino: “Hice una colaboración con la inteligencia artificial y me terminó gustando” | ACCEPT  | `7bda67f7c425ece3` | |
| `ar_clarin` | https://www.clarin.com/espectaculos/pelicula-hecha-inteligencia-artificial-llegara-cines-buscara-oscar_0_nIUWXh31Rm.html | T: La película hecha con inteligencia artificial que llegará a los cines y buscará un Oscar | ACCEPT  | `182592584608e886` | |

## Agency: edited material declared — 15 pages, 5 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `pr_metro_puerto_rico` | https://www.metro.pr/noticias/2026/10/10/colapsan-un-hotel-y-una-iglesia-tras-terremoto-de-magnitud-77-en-panama/ | Con información de la Agencia EFE (EFE). | ACCEPT  | `890aae43014f9df7` | |
| `sv_el_diario_de_hoy` | https://www.elsalvador.com/noticias/internacional/christa-pike-ejecucion-fallida/1298019/2026/ | Con información de EFE. | ACCEPT  | `e18e2ecb8b5a0d04` | |
| `ec_el_comercio` | https://www.elcomercio.com/actualidad/mundo/mas-de-cien-replicas-tras-el-fuerte-terremoto-de-magnitud-77-que-sacudio-panama/ | Con información de EFE. | ACCEPT  | `4550ad235df56a25` | |
| `uy_montevideo_portal` | https://www.montevideo.com.uy/auc.aspx?977980 | Con información de EFE. | ACCEPT  | `c6f39c1699e577d0` | |
| `ni_confidencial` | https://confidencial.digital/noticias/familiares-denuncian-pesimas-condiciones-de-ocho-guardabosques-indigenas-presos-politicos/ | Con información de EFE | ACCEPT  | `35ac327bde821b9d` | |

## Agency: credited (author / dateline), take-over not stated — 376 pages, 6 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `ar_clarin` | https://www.clarin.com/estados-unidos/cuba-tacha-de-persecucion-enfermiza-el-informe-de-ee-uu-sobre-trata-de-personas_0_9SqKR7k6lt.html | json_ld_author: Agencia EFE; meta_author: Agencia EFE | ACCEPT  | `9c276ac929df3895` | |
| `do_diario_libre` | https://www.diariolibre.com/economia/energia/2026/10/10/aumentar-la-integracion-energetica-en-america-latina/3685221 | json_ld_author: EFE | ACCEPT  | `37e9a25c4fa15de6` | |
| `ve_efecto_cocuyo` | https://efectococuyo.com/politica/maria-corina-machado-pide-elecciones-en-venezuela-en-julio-de-2027-segun-financial-times/ | byline_block: Por Efe / @EFEnoticias | ACCEPT  | `df39a3e6f0ada464` | |
| `es_la_vanguardia` | https://www.lavanguardia.com/internacional/20261010/11656085/trump-carga-zelenski-pide-ucrania-nuevo-presidente-pactar.html | json_ld_author: Agencias | ACCEPT  | `6b36646d8fa0235b` | |
| `gt_lahora` | https://lahora.gt/internacionales/agenciaefe/2026/10/09/aeropuerto-internacional-de-panama-reanuda-sus-actividades-despues-del-terremoto-now/ | meta_author: Agencia EFE | ACCEPT  | `65c50f2c9da0105d` | |
| `pr_el_nuevo_dia` | https://www.elnuevodia.com/negocios/empresas-comercios/notas/en-el-corazon-de-uber-eats/ | byline_block: Por The Associated Press | REJECT (too_short, template_body) | `ca847abc8fa4b3aa` | |

## Agency and newsroom credited together — 16 pages, 4 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `ec_primicias` | https://www.primicias.ec/deportes/mas-deportes/max-verstappen-pole-position-gran-premio-singapur-formula1-134618/ | json_ld_author: EFE / Redacción Primicias | ACCEPT  | `c0106871339bd4dc` | |
| `cl_cooperativa` | https://www.cooperativa.cl/noticias/pais/policial/indagan-hallazgo-de-cuerpo-en-el-parque-municipal-de-maipu/2026-11-14/172934.html | json_ld_creator: Cooperativa.cl/ATON | REJECT (too_short) | `20c15e42b363d5a2` | |
| `pa_panama_america` | https://www.panamaamerica.com.pa/provincias/la-casita-se-vino-abajo-la-impotencia-de-los-pobladores-de-la-villa-de-los-santos-tras-el | json_ld_author: Panamá / EFE / PanamaAmerica | ACCEPT  | `308c3ebe893122e5` | |
| `gt_lahora` | https://lahora.gt/internacionales/la-hora/2026/10/10/christa-pike-sobreviviente-de-ejecucion-fallida-regresa-al-penal-tras-recibir-alta-medica-en-tennesse/ | meta_author: Redacción La Hora, Agencia EFE; byline_block: Redacción La Hora, Agencia EFE | ACCEPT  | `dc41e2442f37f762` | |

## Agency named only as a quoted source in the text (must stay unknown) — 69 pages, 5 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `gt_prensa_libre` | https://www.prensalibre.com/internacional/bartolito-y-su-escuadra-el-plan-de-perros-robot-que-el-salvador-suma-a-su-aeropuerto/ | …nversión de US$50 millones, según el comunicado oficial citado por la Agencia EFE.  LECTURAS RELACIONADAS  El robot se incorporó para apoyar la gestió… | ACCEPT  | `5d22d10feb2f2877` | |
| `ar_rio_negro` | https://www.rionegro.com.ar/mundo/christa-pike-recibio-el-alta-medica-y-volvio-a-la-prision-tras-sobrevivir-a-una-ejecucion-4754826/ | …ción médica y que seguirán de cerca su recuperación, según detalló la agencia AP.  Pike había sido hospitalizada el 30 de septiembre, cuando las autor… | ACCEPT  | `641828405bbe7fc3` | |
| `ar_infobae` | https://www.infobae.com/america/mundo/2026/10/11/donald-trump-condeno-el-ataque-de-los-rebeldes-huties-contra-el-aeropuerto-de-riad-que-dejo-12-muertos-es-inaceptable/ | …emergencia grave”.  Un testigo que esperaba para embarcar relató a la agencia AFP lo ocurrido en las puertas de embarque del aeropuerto. “Estaba en la… | ACCEPT  | `749212a080db17fc` | |
| `ec_el_universo` | https://eluniverso.com/politica/ejecutivo/cancilleria-confirma-que-por-ahora-no-hay-ecuatorianos-afectados-por-el-terremoto-en-panama-nota/ | …nes en todo el país. No se han registrado víctimas mortales, según la agencia EFE.  El Instituto de Geociencias de la Universidad de Panamá determinó … | ACCEPT  | `d1d1d571dca83352` | |
| `sv_el_diario_de_hoy` | https://www.elsalvador.com/noticias/internacional/panama-declara-estado-emergencia-huracan/1298021/2026/ | …una reunión extraordinaria del Consejo de Ministros, según informó la agencia EFE.  Los recursos estarán destinados a responder a las necesidades deri… | ACCEPT  | `b1eb8712aff78759` | |

## Text reuse across outlets (syndication evidence) — 120 pages, 6 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `ec_el_universo` | https://eluniverso.com/internacional/estados-unidos/el-huracan-isaias-deja-al-menos-cuatro-muertos-en-la-costa-del-golfo-de-mexico-nota/ | identical [0.9287, 0.9352] with `4682ba69daa42811` (ar_clarin + ec_el_universo) | ACCEPT  | `d2bab51c9573dec3` | |
| `bo_el_deber` | https://eldeber.com.bo/mundo/doce-muertos-309-heridos-ataque-aeropuerto-riad-saudi_1791673871 | identical [0.9296, 0.9198] with `8b8757c2e3c2869d` (bo_el_deber + ec_el_universo) | ACCEPT  | `4286d8e0312185ba` | |
| `do_listin_diario` | https://listindiario.com/las-mundiales/20261010/trump-dice-decidira-transmite-directo-ejecucion-militar_925635.html | identical [0.9748, 0.9226] with `c29d13244d0a4680` (do_listin_diario + pa_critica) | ACCEPT  | `a50d400751c50849` | |
| `co_el_nuevo_siglo` | https://www.elnuevosiglo.com.co/internacional/trump-celebra-acuerdo-con-rusia-sobre-diesel-antes-de-elecciones | contained [1.0, 0.5191] with `228770618462b523` (co_el_nuevo_siglo + pa_metro_libre) | ACCEPT  | `5ab92394ad8bc882` | |
| `py_la_nacion` | https://www.lanacion.com.py/mundo/2026/10/09/fuerte-sismo-de-magnitud-77-sacude-panama-y-provoca-panico/ | identical [0.9157, 0.9532] with `dd780e7348f90a1a` (ec_el_mercurio + py_la_nacion) | ACCEPT  | `9aa9a16632657005` | |
| `ve_el_nacional` | https://www.elnacional.com/2026/10/al-menos-27-heridos-leves-y-mas-de-400-edificaciones-afectadas-por-el-terremoto-en-panama-segun-ultimo-balance/ | identical [0.9318, 0.95] with `3b6729d46ddb3e46` (do_listin_diario + ve_el_nacional) | ACCEPT  | `c98331dca05355bd` | |

## Newly accepted by content-quality/3 (rejected by /2) — 49 pages, 7 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `co_el_espectador` | https://www.elespectador.com/especiales/medellin-sera-epicentro-del-debate-iberoamericano-sobre-el-futuro-de-la-educacion-superior/ | before: machine_text | ACCEPT  | `227c3c1e66cd8aeb` | |
| `ni_nicaragua_investiga` | https://nicaraguainvestiga.com/nacion/174941-francesa-suiza-y-nicaraguense-mueren-ahogadas-al-ser-arrastrada-su-camioneta-en-el-rio-nahualapa-el-viejo/ | before: machine_text | ACCEPT  | `d248b4eb21ba708c` | |
| `co_elpais` | https://www.elpais.com.co/cali/concierto-gratuito-de-kapo-en-el-barrio-obrero-por-la-reactivacion-de-cali-asi-puede-asistir-1016.html | before: machine_text | ACCEPT  | `c575c40e2b6a3706` | |
| `do_diario_libre` | https://www.diariolibre.com/revista/musica/2026/10/10/tendencia-dame-hombro-llega-a-netanyahu-con-video-viral/3685380 | before: machine_text | ACCEPT  | `8b045d4500f5d9f1` | |
| `ar_la_nacion` | https://www.lanacion.com.ar/estados-unidos/de-ser-abandonado-en-un-basurero-a-convertirse-en-un-magnate-tecnologico-la-impresionante-vida-de-nid10102026/ | before: machine_text | ACCEPT  | `b1ed47baeef20bfe` | |
| `cl_biobiochile` | https://www.biobiochile.cl/biobiotv/programas/expreso-bio-bio/2025/07/22/la-extension-de-la-frontera-hace-que-sea-100-permeable-fiscal-carrera-por-fuga-de-sicario.shtml | before: machine_text | ACCEPT  | `0e27ae578923eaac` | |
| `ar_clarin` | https://www.clarin.com/internacional/juan-roig-empresario-espanol-presidente-mercadona-cajera-valencia-paga-impuestos-madrid-deberiamos-pagar-mismo_0_5VDbBgv2EW.html | before: machine_text | ACCEPT  | `fd671770ce216ebb` | |

## Newly rejected by content-quality/3 — 0 pages, 0 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|

## Accepted CORE text (control) — 4066 pages, 10 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `gt_lahora` | https://lahora.gt/editorial/editoriallahora/2026/10/10/la-libre-competencia/ | T: La libre competencia | ACCEPT  | `f0d4287090429d7a` | |
| `co_el_espectador` | https://www.elespectador.com/mundo/torre-de-tokio-secretos-revelados/ | T: Torre de Tokio: secretos revelados | ACCEPT  | `795f60d9320694ed` | |
| `hn_criterio` | https://criterio.hn/hondurenos-necesitan-l2000-mas-del-salario-minimo-para-comprar-canasta-basica/ | T: Hondureños necesitan L2,000 más del salario mínimo para comprar canasta básica | ACCEPT  | `56721891c31c19c2` | |
| `ar_rio_negro` | https://www.rionegro.com.ar/politica/tension-diplomatica-entre-argentina-y-chile-por-el-regreso-de-la-ruta-comercial-entre-punta-arenas-y-malvinas-4754562/ | T: Tensión diplomática entre Argentina y Chile por el regreso de la ruta comercial entre Punta Arenas y Malvinas | ACCEPT  | `398f32fddb2f06ec` | |
| `pa_critica` | https://www.critica.com.pa/sucesos/el-sismo-no-fue-impedimento-para-matar-un-hombre-en-puerto-escondido-517823 | T: El sismo no fue impedimento para matar a un hombre en Puerto Escondido | ACCEPT  | `f11cc8e4dced0113` | |
| `ar_infobae` | https://www.infobae.com/america/mundo/2026/10/10/china-anuncio-ejercicios-militares-conjuntos-con-pakistan-en-la-region-de-xinjiang/ | T: China anunció ejercicios militares conjuntos con Pakistán en la región de Xinjiang | ACCEPT  | `b5af57fbf15a5f2c` | |
| `ve_el_nacional` | https://www.elnacional.com/2026/10/trump-reclamo-otra-vez-el-nobel-de-la-paz-y-critico-al-comite-por-premiar-a-la-exjueza-sudafricana-navi-pillay/ | T: Trump reclamó otra vez el Nobel de la Paz y criticó al comité por premiar a la exjueza sudafricana Navi Pillay | ACCEPT  | `10878c7140a459c9` | |
| `pe_diario_uno` | https://diariouno.pe/2026/10/10/castrovirreyna-apuesta-por-el-deporte-para-formar-a-sus-nuevas-generaciones/ | T: Castrovirreyna apuesta por el deporte para formar a sus nuevas generaciones | ACCEPT  | `e1d738bbfc089ed0` | |
| `py_la_nacion` | https://www.lanacion.com.py/futboledicion-impresa/2026/10/11/con-la-obligacion-de-sumar-de-los-lideres/ | T: La Nación | ACCEPT  | `2f1d2b667ad0b3b3` | |
| `es_la_vanguardia` | https://www.lavanguardia.com/politica/20261010/11655919/feijoo-plantea-cambio-total-sereno-frente-sanchez-echar-voto-gente.html | T: Feijóo plantea un cambio “total” y “sereno” frente a Sánchez: “Lo vamos a echar con el voto de la gente” | ACCEPT  | `e5e13b8aaf54d795` | |

## Rejected, borderline (150-220 words or one reason only) — 336 pages, 6 drawn

| Outlet | Address | Found | content-quality/3 | Fetch | Your verdict |
|---|---|---|---|---|---|
| `cl_the_clinic` | https://www.theclinic.cl/2026/10/09/camaras-captaron-el-momento-exacto-en-que-el-aluvion-ingreso-a-las-calles-de-las-condes/ | reason: too_short | REJECT (too_short) | `7fb3288a3d9b0f7c` | |
| `co_el_nuevo_siglo` | https://www.elnuevosiglo.com.co/nacion/programas-del-ministerio-de-igualdad-pasaran-al-del-interior-tras-liquidacion | reason: too_short | REJECT (too_short) | `4821d3f56e90508b` | |
| `pe_la_republica` | https://larepublica.pe/economia/precio-del-dolar/2026/10/10/precio-del-dolar-hoy-en-peru-sabado-10-de-octubre-consulta-el-tipo-de-cambio-para-compra-y-venta-211023 | reason: too_short | REJECT (too_short) | `bc80ffbb444fa274` | |
| `cl_cooperativa` | https://www.cooperativa.cl/noticias/pais/medioambiente/animales/rescatan-a-zorro-culpeo-que-fue-atropellado-en-galvarino/2026-10-10/184058.html | reason: too_short | REJECT (too_short) | `2c1d6be805320ba6` | |
| `ve_eldiario` | https://eldiario.com/2026/10/09/devaluacion-prosperidad/ | reason: not_running_prose | REJECT (not_running_prose) | `9e626afb49da60b1` | |
| `cl_biobiochile` | https://www.biobiochile.cl/noticias/nacional/region-de-la-araucania/2025/07/22/mas-de-20-caballos-han-sido-sacrificados-por-anemia-infecciosa-equina-en-la-araucania.shtml | reason: incomplete_against_stated_body | REJECT (incomplete_against_stated_body) | `3864f4b4e510e344` | |

