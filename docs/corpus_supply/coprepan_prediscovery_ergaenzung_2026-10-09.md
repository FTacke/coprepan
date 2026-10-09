# CO.PRE.PAN 3.0 – gezielte Prediscovery-Ergänzung (9. Oktober 2026)

**Status: RESEARCH_ONLY / NOT_REGISTERED / NOT_LIVE_VALIDATED.**

Abgleich mit dem bereitgestellten Register: **82 Outlets / 352 Kanäle**. 19 recherchierte Quelleneinträge: **13 mögliche neue Zeitungen**, **5 zusätzliche Routen bestehender Zeitungen**, **1 bereits identische Registerkanäle**. P0: 11; P1: 6; P2: 2. Länder: ar, bo, co, cu, ec, hn, mx, ni, pr, py, sv, uy.

## Methodik und Evidenzgrenzen

- Aktuelle bzw. zugängliche Publisherseiten über Websuche ausgewertet; URLs und Quelle je Kandidat protokolliert. Die nicht in den hochgeladenen Dateien enthaltenen drei agentischen Prediscovery-JSONs (301 Hypothesen) und die 60 Outlet-Vorschläge konnten **nicht zeilenweise gegengeprüft** werden. Nach Import dieser Ergänzung in den Repo-Zweig muss der Agent erneut auf IDs und URLs deduplizieren.
- `publisher_rss` = Verlag dokumentiert RSS, **nicht**: Endpunkt aktuell abrufbar, Artikel extrahierbar oder rechtlich freigegeben. `publisher_html_*` = redaktionelle Listing-/Archivseite mit publizierten Meldungen, **nicht**: bereits technisch vom CO.PRE.PAN-Parser getestet.
- Kein Publisher wurde durch den CO.PRE.PAN-Crawler abgefragt, kein Gate verändert, kein Kanal registriert oder aktiviert. Vermeintliche Opt-outs, robots, Zugriffskontrollen, Nutzungsrechte und TDM-Policy vor Live-Crawling prüfen.
- Länderzuordnung beschreibt **Redaktions-/Berichtsraum**, nicht automatisch den physischen Redaktionssitz; Syndikation, Gastautoren, Mehrsprachigkeit und Auslandsstandort kennzeichnen.

## Kandidaten zur Agentenübergabe

### P0 – zuerst prüfen

| Quelle | Registry-Abgleich | Discovery-Weg | Evidenz |
|---|---|---|---|
| **EC · El Universo** (`ec_el_universo`) | Bekannte Zeitung, zusätzliche Route | [publisher_rss_hub](https://www.eluniverso.com/rss/) | [Publisher-Evidenz](https://www.eluniverso.com/rss/) |
| **NI · Artículo 66** (`ni_articulo66`) | Neue Zeitung | [publisher_html_archive](https://www.articulo66.com/2026/) | [Publisher-Evidenz](https://www.articulo66.com/2026/) |
| **NI · Nicaragua Investiga** (`ni_nicaragua_investiga`) | Neue Zeitung | [publisher_html_sections](https://nicaraguainvestiga.com/) | [Publisher-Evidenz](https://nicaraguainvestiga.com/) |
| **CU · 14ymedio** (`cu_14ymedio`) | Neue Zeitung | [publisher_html_section](https://www.14ymedio.com/cuba) | [Publisher-Evidenz](https://www.14ymedio.com/cuba) |
| **CU · CubaNet** (`cu_cubanet`) | Neue Zeitung | [publisher_html_archive](https://www.cubanet.org/ultimas-noticias/) | [Publisher-Evidenz](https://www.cubanet.org/ultimas-noticias/) |
| **CU · Diario de Cuba** (`cu_diario_de_cuba`) | Neue Zeitung | [publisher_html_section](https://diariodecuba.com/cuba) | [Publisher-Evidenz](https://diariodecuba.com/cuba) |
| **UY · Montevideo Portal** (`uy_montevideo_portal`) | Neue Zeitung | [publisher_rss](https://www.montevideo.com.uy/anxml.aspx?59) | [Publisher-Evidenz](https://www.montevideo.com.uy/Utiles/Las-noticias-de-Montevideo-Portal-en-formato-RSS-uc27383) |
| **BO · Opinión** (`bo_opinion`) | Neue Zeitung | [publisher_rss](https://www.opinion.com.bo/rss/) | [Publisher-Evidenz](https://www.opinion.com.bo/rss/listado/) |
| **AR · El Tribuno** (`ar_el_tribuno`) | Neue Zeitung | [publisher_rss](https://www.eltribuno.com/rss-new/portada.rss) | [Publisher-Evidenz](https://www.eltribuno.com/page-rss) |
| **PR · NotiCel** (`pr_noticel`) | Neue Zeitung | [publisher_html_section](https://noticel.com/category/ultima-hora/) | [Publisher-Evidenz](https://noticel.com/category/ultima-hora/) |
| **HN · Criterio.hn** (`hn_criterio`) | Neue Zeitung | [publisher_html_section](https://criterio.hn/category/actualidad/) | [Publisher-Evidenz](https://criterio.hn/category/actualidad/) |

### P1 – zweite Welle

| Quelle | Registry-Abgleich | Discovery-Weg | Evidenz |
|---|---|---|---|
| **EC · El Comercio** (`ec_el_comercio`) | Kanal bereits im Register | [publisher_rss](https://www.elcomercio.com/feed/) | [Publisher-Evidenz](https://www.elcomercio.com/feed-rss/) |
| **MX · Expansión México** (`mx_expansion`) | Neue Zeitung | [publisher_rss_hub](https://expansion.mx/canales-rss) | [Publisher-Evidenz](https://expansion.mx/canales-rss) |
| **SV · El Faro** (`sv_el_faro`) | Neue Zeitung | [publisher_html_edition](https://beta.elfaro.net/edicion) | [Publisher-Evidenz](https://beta.elfaro.net/edicion) |
| **PR · El Nuevo Día** (`pr_el_nuevo_dia`) | Bekannte Zeitung, zusätzliche Route | [publisher_rss_hub](https://www.elnuevodia.com/rss/) | [Publisher-Evidenz](https://www.elnuevodia.com/rss/) |
| **UY · El Observador** (`uy_el_observador`) | Bekannte Zeitung, zusätzliche Route | [publisher_rss_hub](https://www.elobservador.com.uy/contenidos/rss.html) | [Publisher-Evidenz](https://www.elobservador.com.uy/contenidos/rss.html) |
| **PY · ABC Color** (`py_abc_color`) | Bekannte Zeitung, zusätzliche Route | [publisher_rss](https://www.abc.com.py/arc/outboundfeeds/rss/nacionales/) | [Publisher-Evidenz](https://www.abc.com.py/articulos/rss-142.html) |

### P2 – nur nach Vorprüfung

| Quelle | Registry-Abgleich | Discovery-Weg | Evidenz |
|---|---|---|---|
| **CO · El Tiempo** (`co_el_tiempo`) | Bekannte Zeitung, zusätzliche Route | [publisher_rss_hub](https://www.eltiempo.com/rss) | [Publisher-Evidenz](https://www.eltiempo.com/rss) |
| **MX · El Siglo de Torreón** (`mx_el_siglo_de_torreon`) | Neue Zeitung | [publisher_rss_historic](http://www.elsiglodetorreon.com.mx/channel/local.xml) | [Publisher-Evidenz](https://www.elsiglodetorreon.com.mx/blogs/2008/rss-en-el-siglo-de-torreon.html) |

## Konkrete Zusatzbefunde

- **Ecuador:** `ec_el_universo` hat im hochgeladenen Registry **keine** Kanäle, der Verlag dokumentiert aber selbst eine umfangreiche RSS-Seite. Die bestehende achtköpfige Canary-Empfehlung enthält diesen Outlet bereits – den neuen Link als Quellenbeleg beifügen statt als neuen Outlet anlegen.
- **Puerto Rico:** `pr_el_nuevo_dia` hat nur Sitemap-Indizes im Registry; RSS-Hub des Publishers ist nachweisbar, mit Nachrichten- und Ressortlinks. `pr_primera_hora` behält die bekannte falsche gemeinsame Origin-Zuordnung; keine stillschweigende Gleichsetzung. NotiCel bietet einen eigenständigen zusätzlichen Verlag, verlangt aber HTML-Qualifikation.
- **Uruguay:** `uy_el_observador` hat nur Sitemap-Einträge; offizieller RSS-Hub eröffnet zusätzliche Kanäle. `Montevideo Portal` ist ein weiterer eigenständiger Kandidat mit zwölf ausdrücklich genannten RSS-Endpunkten.
- **Bolivien/Argentinien:** regionale Varianten erhöhen den regionalen Anteil und reduzieren Nationalhauptstadt-Dominanz. `Opinión` und `El Tribuno` veröffentlichen eigene RSS-Kataloge.
- **Kuba/Nicaragua:** mehrere gegenwärtige Archiv- und Rubrikenrouten, aber keine festgestellten RSS-Endpunkte; für `listing` nur mit getesteten zulässigen Candidate-Allow-Regeln. Auslandsredaktionen und Inhaltsurheberschaft einzeln prüfen.
- **El Tiempo (CO):** Die offizielle RSS-Seite nennt explizite Bedingungen der persönlichen, nichtkommerziellen Nutzung und Verbote im KI-Kontext. Die Quelle daher nicht allein wegen offizieller RSS-Verfügbarkeit zur automatischen Akquisition freigeben: gesonderte Lizenz-/TDM-Prüfung erforderlich.
- **El Faro (SV):** Monatseditionen, nicht mit einer täglichen RSS-Zeitung vergleichen; getrennte Produktionskadenz verwenden.
- **Bestehende 8er-Canary-Welle unverändert lassen.** Keine neue Quelle dem noch ausstehenden zweiten Canary zuschlagen. Nach dessen Abschluss die neuen P0-Kandidaten in ein separates, kleines Registry-/Canary-Review übernehmen.

## Übergabevorgaben

1. `config/source_discovery/source_discovery_inventory_2026-10-09.1.json` und `prediscovery_2026-10-09_group{1,2,3}.json` **im Repository tatsächlich lesen** und die Einträge gegen dieses externe Recherchepaket auf `outlet_id`, URL, Origin und Quellentyp abgleichen.
2. Gefundene Dubletten als zusätzliche Evidenz an bestehenden Datensätzen dokumentieren, nicht neue Outlets/Kanäle doppelt registrieren. Die jetzige Quelle ist eine **proposed evidence layer**, kein kanonisches Registry-Update.
3. Aus Priorität P0 zuerst eine heterogene kleine Auswahl für Offline-Parserchecks und nach den nötigen Gates für einen begrenzten Live-Canary wählen; offizielle Feeds und HTML-Archive bewusst mischen.
4. Je Outlet `channels_seen`, `candidates_yielded`, `item_pages_2xx`, `RAW_PRESERVED`, `replay`, `extraction_suitable`, Rate und unerlaubte/abgelehnte Requests getrennt messen.
5. Bei abweichendem Redaktionsstandort, anderem Publisher, Syndikation oder mehrsprachigen Rubriken nur nachvollziehbare, explizite Attribute festlegen. Keine unkontrollierte Production Activation.

## Maschinenlesbare Quelle

`coprepan_prediscovery_ergaenzung_2026-10-09.json` enthält für jeden Eintrag Evidenz-URL, vorgeschlagene Route, Registry-Match, Priorität, technische Prüfbedingungen und Sonderhinweise.
