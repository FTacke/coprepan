# Source coverage report — overview version 2026-10-09.2

**Generated** by `scripts/consolidate_source_discovery.py` from the JSON beside it; do not edit. A reading aid over the
evidence files, not a registry. Research is a hypothesis; only `TECHNICALLY_QUALIFIED` and later rest on this project's own
observation of a server. Coverage of a country is not representativeness: owner, type, region and time are not in this table.

Registry outlets: 82. Outlet candidates outside the registry: 63. Countries: 20.

| Stage | Registry outlets | Rule |
|---|---|---|
| `RESEARCHED` | 82 | named in a research file with a source |
| `CANDIDATE` | 79 | a concrete discovery address is on file with an evidence level other than `unknown` |
| `TECHNICALLY_QUALIFIED` | 2 | this project read a channel document of the outlet from a real server and the current parser finds an item entry in it (the inventory's QUALIFIED) |
| `REGISTERED` | 5 | registry `registration_status` is `registered` |
| `ACQUISITION_VERIFIED` | 1 | the inventory's ACQUISITION_VERIFIED: at least 5 item pages 2xx, preserved, verified and replayed in one bounded run |
| `OPERATIONALLY_STABLE` | 0 | three such runs on three days within at least fourteen days, no hold in between (CPD-0019 §8) |

## Coverage by country

| Country | Registry | Legacy: any accepted | Legacy: repeated | Registered | Qualified | Acquisition verified | In a proposed wave | Candidates outside | Closed or held |
|---|---|---|---|---|---|---|---|---|---|
| ar | 3 | 2 | 1 | 0 | 0 | 0 | 1 | 4 | — |
| bo | 5 | 3 | 1 | 1 | 0 | 0 | 2 | 3 | `bo_pagina_siete` |
| cl | 3 | 2 | 2 | 0 | 0 | 0 | 1 | 3 | — |
| co | 5 | 3 | 1 | 0 | 0 | 0 | 0 | 3 | — |
| cr | 3 | 2 | 2 | 0 | 0 | 0 | 0 | 3 | — |
| cu | 5 | 3 | 3 | 0 | 0 | 0 | 2 | 4 | — |
| do | 3 | 2 | 2 | 1 | 1 | 1 | 0 | 3 | — |
| ec | 3 | 0 | 0 | 0 | 0 | 0 | 2 | 3 | — |
| es | 3 | 1 | 1 | 0 | 0 | 0 | 1 | 3 | — |
| gt | 6 | 3 | 3 | 0 | 0 | 0 | 1 | 3 | `gt_elperiodico` |
| hn | 6 | 4 | 2 | 1 | 0 | 0 | 1 | 3 | `hn_proceso_digital` |
| mx | 3 | 1 | 1 | 0 | 0 | 0 | 1 | 4 | — |
| ni | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 3 | — |
| pa | 7 | 5 | 3 | 0 | 0 | 0 | 1 | 3 | — |
| pe | 6 | 1 | 1 | 0 | 0 | 0 | 2 | 3 | — |
| pr | 3 | 1 | 1 | 0 | 0 | 0 | 1 | 3 | — |
| py | 3 | 2 | 2 | 1 | 0 | 0 | 0 | 3 | — |
| sv | 3 | 1 | 1 | 0 | 0 | 0 | 1 | 3 | — |
| uy | 4 | 2 | 2 | 0 | 0 | 0 | 1 | 3 | — |
| ve | 5 | 4 | 4 | 1 | 1 | 0 | 0 | 3 | — |

## The research supplement (19 entries; RESEARCH_ONLY)

| Entry | Country | Classification | Matches in earlier files | Disposition | Reason |
|---|---|---|---|---|---|
| `ec_el_universo` | ec | KNOWN_ADDITIONAL_EVIDENCE | earlier_research | EVIDENCE_FOR_REVIEWED_WAVE | the publisher's own RSS page corroborates the Arc feed already in the reviewed first wave; the wave is not changed |
| `ec_el_comercio` | ec | KNOWN_IDENTICAL | registry_channel | EVIDENCE_ONLY | the channel is in the registry; first-party corroboration, no new channel |
| `ni_articulo66` | ni | OUTLET_ALREADY_PROPOSED | earlier proposal: Articulo 66 | WAVE_C | independent Nicaraguan outlet; a yearly archive with numbered pages (a structure no wave has) beside a feed named by earlier research |
| `ni_nicaragua_investiga` | ni | OUTLET_ALREADY_PROPOSED | earlier proposal: Nicaragua Investiga | WAVE_C | second independent Nicaraguan outlet; a feed named by earlier research; the supplement shows current sections |
| `cu_14ymedio` | cu | OUTLET_ALREADY_PROPOSED | earlier proposal: 14ymedio | WAVE_C | independent Cuban outlet; a feed named by earlier research and a section listing |
| `cu_cubanet` | cu | OUTLET_ALREADY_PROPOSED | earlier proposal: CubaNet | WAVE_C | independent Cuban outlet; a feed named by earlier research and a news archive |
| `cu_diario_de_cuba` | cu | NEW_OUTLET_CANDIDATE | none | LATER_WAVE | a third independent Cuban outlet known by a section page only: a listing without a feed; after the first listing outlets have run |
| `uy_montevideo_portal` | uy | OUTLET_ALREADY_PROPOSED | earlier_proposal; earlier_proposal; earlier_proposal | WAVE_C | publisher-documented RSS catalogue, named by two independent research files; a feed address that is a query string |
| `bo_opinion` | bo | OUTLET_ALREADY_PROPOSED | earlier_proposal | WAVE_C | publisher-documented RSS catalogue and a third-party crawler reading it; regional daily (Cochabamba) |
| `ar_el_tribuno` | ar | NEW_OUTLET_CANDIDATE | none | WAVE_C | publisher-documented RSS catalogue; regional daily (Salta); not in any earlier file |
| `pr_noticel` | pr | OUTLET_ALREADY_PROPOSED | earlier proposal: NotiCel | WAVE_C | an independent Puerto Rican outlet known by a chronological category page only: a listing read without an allow rule, its candidates waiting |
| `hn_criterio` | hn | OUTLET_ALREADY_PROPOSED | earlier proposal: Criterio.hn | WAVE_C | Honduran outlet while the origin of Proceso Digital is held; a feed a third-party crawler reads and a category listing |
| `mx_expansion` | mx | NEW_OUTLET_CANDIDATE | none | NEEDS_CURRENT_EVIDENCE | the hub page is known, no feed address is: nothing to register yet; a business title, not a general daily |
| `sv_el_faro` | sv | OUTLET_ALREADY_PROPOSED | earlier proposal: El Faro | DIFFERENT_CADENCE | monthly editions on a beta host: not comparable to a daily feed; needs its own schedule and an origin decision |
| `pr_el_nuevo_dia` | pr | KNOWN_ADDITIONAL_EVIDENCE | earlier_research | LATER_WAVE | a publisher-documented Arc feed for an outlet the registry holds only sitemap indexes for; the outlet is paywalled since 2017 by research |
| `uy_el_observador` | uy | NEW_CHANNEL_FOR_EXISTING_OUTLET | none | LATER_WAVE | a publisher-documented latest-news feed for an outlet the registry holds only sitemaps for |
| `py_abc_color` | py | KNOWN_ADDITIONAL_EVIDENCE | registry_channel_variant | EVIDENCE_ONLY | a 2019 page describing feeds the registry already holds with a query suffix: a variant, not a new channel |
| `co_el_tiempo` | co | KNOWN_ADDITIONAL_EVIDENCE | earlier_research | HOLD_LEGAL_REVIEW | the publisher's RSS page states personal, non-commercial use and restricts AI use: a licence and TDM decision of the operator comes before any registration |
| `mx_el_siglo_de_torreon` | mx | OUTLET_ALREADY_PROPOSED | earlier proposal: El Siglo de Torreon | NEEDS_CURRENT_EVIDENCE | documentation of 2008; a feed directory names another address; neither is current evidence |

Classifications: `KNOWN_IDENTICAL` — the address is a channel of the registry already; `KNOWN_ADDITIONAL_EVIDENCE` — the address, a variant of it, or the feed a hub page documents was known from the registry or from earlier research; the supplement adds evidence; `NEW_CHANNEL_FOR_EXISTING_OUTLET` — a registry outlet; no earlier file names this address or the feed it documents; `OUTLET_ALREADY_PROPOSED` — not in the registry; the outlet is among the 60 proposals of the prediscovery files; `NEW_OUTLET_CANDIDATE` — not in the registry and not among the earlier proposals.

## Identity cases

| Case | Finding | Recommendation | Decision |
|---|---|---|---|
| pr_primera_hora | every channel of the outlet is on another outlet's host (elnuevodia.com, the same three addresses as pr_el_nuevo_dia): the outlet has no channel of its own | at registration review: give pr_primera_hora no channel from elnuevodia.com; a channel on primerahora.com is known only by pattern inference; keep both outlets apart (one publisher group, two titles) | OPEN (O-11 review); nothing changed |
| cl_el_mercurio | the registry outlet named El Mercurio has the origin emol.com, the group's free portal; the newspaper's own content is behind a subscription by research | decide whether the outlet is Emol (then name it so, by a new display name with dates, never a new id) or El Mercurio (then emol.com is not its origin) | OPEN (operator, corpus supply); the outlet is NEEDS_VERIFICATION in the review |
| ni_confidencial | third parties read the feed on the apex host; the newsroom works from Costa Rica; the country of the outlet is the country it reports on | register the apex host as a second origin; keep country_id ni; record the seat as an attribute when the registry has one for it, not as the country | OPEN (O-11 review; listed in the proposal) |
| bo_la_razon | research finds current content under larazon.bo and a third party reports the registry origin blocked | an origin change is a dated addition of an origin after review, never a rewrite; the legacy alias stays | OPEN (O-11 review) |
| ni_la_prensa | research finds the outlet at laprensani.com since 2023 and warns of an impersonation site: the origin must be pinned exactly | as bo_la_razon; verify the origin against the outlet's own statement before registering | OPEN (O-11 review) |
| closed outlets | research finds both closed in 2023; the legacy corpus holds 10 accepted articles of bo_pagina_siete and none of gt_elperiodico | keep both in the registry as proposed and never register them for acquisition; historical articles keep their outlet | OPEN (registry attribute for a closed outlet does not exist) |
| same title, different outlets | titles that occur more than once across countries among registry outlets and outlet candidates | the country prefix of the id keeps them apart; never merge by title | no action |
| hosts shared by registry outlets | origin hosts that belong to more than one registry outlet, and outlets with channels on a host that is not one of their origins (a feed on a foreign host is a channel origin, never an outlet origin) | none beyond the cases above | no action |

## Outlet candidates outside the registry

| Country | Name | Proposed id | Stages | Named in | Wave |
|---|---|---|---|---|---|
| ar | El Tribuno | `ar_el_tribuno` | RESEARCHED, CANDIDATE | 1 file(s) | wave C: proposed |
| ar | Infobae | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ar | Perfil | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ar | Río Negro | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| bo | Brújula Digital | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| bo | Correo del Sur | — | RESEARCHED | 1 file(s) | — |
| bo | Opinión | `bo_opinion` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| cl | Cooperativa | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| cl | La Discusión | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| cl | The Clinic | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| co | Diario del Huila | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| co | El Nuevo Siglo | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| co | La Silla Vacía | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| cr | Delfino.cr | — | RESEARCHED | 1 file(s) | — |
| cr | El Observador | — | RESEARCHED | 1 file(s) | — |
| cr | Semanario Universidad | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| cu | 14ymedio | `cu_14ymedio` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| cu | 5 de Septiembre | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| cu | CubaNet | `cu_cubanet` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| cu | Diario de Cuba | `cu_diario_de_cuba` | RESEARCHED, CANDIDATE | 1 file(s) | — |
| do | Acento | — | RESEARCHED | 1 file(s) | — |
| do | El Nacional | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| do | Hoy | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ec | El Mercurio | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ec | Expreso | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ec | La Republica (EC) | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| es | ABC | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| es | El Correo | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| es | elDiario.es | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| gt | Emisoras Unidas | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| gt | Plaza Publica | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| gt | Prensa Comunitaria | — | RESEARCHED | 1 file(s) | — |
| hn | Contracorriente | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| hn | Criterio.hn | `hn_criterio` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| hn | Radio Progreso | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| mx | Animal Politico | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| mx | El Siglo de Torreon | `mx_el_siglo_de_torreon` | RESEARCHED, CANDIDATE | 2 file(s) | — |
| mx | El Sol de Mexico | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| mx | Expansión México | `mx_expansion` | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ni | Articulo 66 | `ni_articulo66` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| ni | Despacho 505 | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ni | Nicaragua Investiga | `ni_nicaragua_investiga` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| pa | Panama 24 Horas | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| pa | Panama America | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| pa | TVN Noticias | — | RESEARCHED | 1 file(s) | — |
| pe | Diario Los Andes | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| pe | Diario UNO | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| pe | El Buho | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| pr | Centro de Periodismo Investigativo (CPI) | — | RESEARCHED | 1 file(s) | — |
| pr | El Vocero | — | RESEARCHED | 1 file(s) | — |
| pr | NotiCel | `pr_noticel` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| py | ADN Digital | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| py | Diario HOY | — | RESEARCHED | 1 file(s) | — |
| py | Noticias CDE | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| sv | Diario Co Latino | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| sv | Diario El Salvador | — | RESEARCHED | 1 file(s) | — |
| sv | El Faro | `sv_el_faro` | RESEARCHED, CANDIDATE | 2 file(s) | — |
| uy | Busqueda | — | RESEARCHED | 1 file(s) | — |
| uy | El Telegrafo | — | RESEARCHED | 1 file(s) | — |
| uy | Montevideo Portal | `uy_montevideo_portal` | RESEARCHED, CANDIDATE | 2 file(s) | wave C: proposed |
| ve | Analitica | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ve | Correo del Caroni | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
| ve | El Impulso | — | RESEARCHED, CANDIDATE | 1 file(s) | — |
