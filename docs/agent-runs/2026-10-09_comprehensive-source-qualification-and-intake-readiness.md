# Comprehensive source qualification, registry expansion and intake readiness

```text
run_started_at:      2026-10-09T19:05:00+02:00 (first clock reading of the run, approximate to the minute)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

This report is written in stages, one commit after each phase. A section exists only for what has happened.

**Status at this commit: the stock is counted, every hypothesis has a disposition, the registrations and repairs are in; no
qualification wave has run yet.**

`EXTERNAL_API_USAGE = NONE`.

## 1. Starting state, read at the start

`HEAD` = `origin/main` = `d71e9c9`; tree clean; `external_acquisition` `disabled`; no canary or operator process running.
Registry: 91 outlets, 22 registered, 69 proposed. Outlets with verified acquisition: 14, in 11 countries.

## 2. The stock, counted and deduplicated (phase A1)

`scripts/build_qualification_proposal.py` reads the registry, the inventory of 2026-10-09 and the qualification overview and
gives every outlet hypothesis exactly one disposition by rules stated in the script. Result:
`config/source_discovery/qualification_dispositions_2026-10-09.json`.

| | Count |
|---|---|
| hypotheses in the registry | 91 |
| hypotheses from research alone (the overview lists 63; 9 of them entered the registry as wave C and are counted once, as registry rows) | 54 |
| **distinct outlet hypotheses** | **145** |

| Disposition | Count | Meaning |
|---|---|---|
| `ALREADY_REGISTERED` | 22 | registered by an earlier record |
| `REGISTER` | 92 | identity, country and origin known, at least one evidenced channel: 57 proposed rows of the registry, 35 new to it |
| `NO_EVIDENCED_CHANNEL` | 22 | no channel from the legacy system, a search result or the publisher. Addresses inferred from how a content system usually looks were not registered: a guess is not requested |
| `CLOSED` | 2 | `bo_pagina_siete` (last edition 2023-06-29), `gt_elperiodico` (2023-05-15), by research |
| `DOMAIN_CHANGE` | 2 | `bo_la_razon` (now `larazon.bo`), `ni_la_prensa` (now `laprensani.com`): the registry's origin is the dead one, and an amendment can add an origin, not replace the canonical one — this needs a decision on the id's origin |
| `IDENTITY_OPEN` | 2 | `pr_primera_hora` (every channel held for it is on the host of `pr_el_nuevo_dia`), `cl_el_mercurio` (the origin is `emol.com`; Emol or El Mercurio is an open corpus-supply decision) |
| `NO_ORIGIN` | 2 | `cu_diario_de_cuba`, `mx_expansion`: research names the outlet and no origin |
| `LEGAL_HOLD` | 1 | `co_el_tiempo`, excluded by the brief until a licence / TDM decision |

No two hypotheses share an id or an origin host; titles of one owner are kept apart (no merge was made). The registry after
the registration: **126 outlets, 114 registered, 12 proposed, 446 channels**
(`config/registry_review/qualification_registration_2026-10-09.json`). The 19 deferred hypotheses from research alone are not
in the registry.

**What a registration here is.** The policy gate requests nothing of an unregistered outlet, so a hypothesis can be tested
only once it is registered. These 92 registrations are the precondition of a test, not its result; kind of outlet, owner,
city and access model are left `unknown` for all of them.

## 3. Repairs before the waves (phase A2)

| | Repair | Shown offline by |
|---|---|---|
| F11 `ec_el_universo` | amendment record: `https://eluniverso.com` added as a second origin (the canonical one stays `www`); nothing else of that domain | the preserved feed: 100 of 100 item links on the apex host |
| F12 `uy_montevideo_portal` | the URL key keeps a **nameless** query component for an outlet that declares it (`uy_montevideo_portal-url-rules/v2`); named parameters are dropped as before; no key of any other outlet changes | test: `auc.aspx?978027` and `?978024` are two keys; tracking parameters beside them are dropped; order does not matter; an ordinary address is unchanged |
| F13 tracking parameters | `utm_` parameters are not part of the requested URL (`channel-parser/6`); the event keeps the listed URL and says what was removed; nothing else is touched | test; cause measured on 2026-10-09: ten requests for five pages of `ni_nicaragua_investiga` |
| allow-rule scope | an allow pattern applies to what a **listing** names and no longer narrows a feed of the same outlet (`candidate-filter-generic/3`) | test |
| registry amendments | `scripts/amend_registration.py`: adds an origin, a URL-rule version or a channel by a dated record; removes nothing | test: nine refused forms |
| F8, F9, F10, F14 | repaired in the previous run; their regression tests are in the suite | to be confirmed live by the waves (`py_la_nacion`, `ec_primicias`, `gt_lahora`; every wave is a second run on a sealed day for no outlet but `ec_primicias`, `ec_el_universo`, `gt_lahora`, `py_la_nacion`, `uy_montevideo_portal`) |

Decision record: [CPD-0025](../decisions/CPD-0025_comprehensive-source-qualification.md).

## 4. The qualification waves — scope

Authorisation record `config/operator_authorizations/2026-10-09_qualification.json` (`DOA-2026-10-09-4`): five waves over the
**97** registered outlets that have neither verified acquisition without an open finding nor a hold — four item requests and
eight other requests per outlet, at most 1 164 requests in all (the brief's ceiling: 1 800). The thirteen outlets with clean
verified acquisition and the four held origins are in no wave.
