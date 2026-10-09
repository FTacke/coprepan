# Access policy: holds with a scope, the robots address by RFC 9309, and a bounded recovery wave

```text
run_started_at:      2026-10-09T23:43:00+02:00 (first clock reading of the run)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

This report was written in stages; this is its final state.

| Part | Status | In one line |
|---|---|---|
| Policy implementation | `PASS` | holds have a scope, the robots address is read by RFC 9309 §2.3.1, preserved answers are re-read in both directions; tested, versioned, one general rule |
| Fresh validation | `PARTIAL` | one wave, eight outlets, 53 requests of 150 allowed: three outlets yield articles (25 pages), five do not, each for a reason the server gave |
| Intake readiness | `PASS` as a prepared file | 87 outlets, 121 channels, 20 countries; it starts nothing |

**The three priority cases.** **El País (Spain): reachable, five full articles preserved, verified and replayed — and then
a CAPTCHA** (DataDome) on the sixth article request; its origin is held again, this time by a real control on the thing
itself. **Efecto Cocuyo: recovered** — ten articles through its feed; the challenged sitemap stays held as that one address.
**La Jornada: not recovered** — the misreading that had held it is repaired, and the first article request then met a real
Cloudflare challenge; the origin is held, correctly now.

**What the status does not claim.** No outlet is operationally stable. Nothing is activated; no intake was started;
`external_acquisition` is `disabled`. A released hold is not a working source: of the four outlets the new policy released,
two yielded articles and one of those two is held again. Nothing here is a statement that a request is lawful — for El País
in particular §8 names what is open.

`EXTERNAL_API_USAGE = NONE`.

## 1. Starting state, verified

`HEAD` = `origin/main` = `504129f`; tree clean; `external_acquisition` `disabled`; no canary running. The reported numbers
hold: 145 hypotheses, 114 registered, 83 verified in 20 countries, 85 outlets and 119 channels in the readiness file of
2026-10-09, 18 outlets held, 1518 tests passed and 14 skipped.

## 2. What was unnecessarily restrictive

Read from the code as it stood (`fetcher._attempt`, `canary_driver.access_holds_from_evidence`, CPD-0017 §4): **any** class of
access control observed on **any** answer — a robots address, a feed, a sitemap, an article — put the whole origin on hold for
the run, and, because holds are derived again from preserved answers at every start, for every later run. A 401 or 403 for a
robots address counted as such a control, although the same policy already read a 404 there as "no robots file". And a
stored class was only ever re-read in one direction: an answer once called a control stayed one.

Against the eighteen holds of 2026-10-09 that meant: five of them were not a refusal of what the project wanted to read.

## 3. The change

Decision: [CPD-0027](../decisions/CPD-0027_access-holds-have-a-scope-and-a-refused-robots-address-is-not-a-refused-origin.md).
Policy file version `canary/2026-10-10.1`.

| Rule | Before | Now |
|---|---|---|
| a control on an **item page** | holds the origin | unchanged |
| a control on a **channel document** | holds the origin | holds **that URL**; the outlet's other channels answer for themselves |
| a challenge, CAPTCHA, block page or 451 on a **robots address** | holds the origin | unchanged |
| a plain **401/403 on a robots address** | holds the origin | the robots file is **unavailable** (RFC 9309 §2.3.1.3): the resource is asked and answers for itself |
| a **429** on a robots address | "absent" robots file and a hold | **unreachable** (nothing is asked) and a rate-limit hold of the origin |
| 5xx or no answer for a robots address | unreachable, deferred | unchanged (RFC 9309 §2.3.1.4) |
| an explicit `Disallow`; the research-TDM override | CPD-0017 | **unchanged** |
| re-reading preserved answers | only to add a hold | in both directions |
| a firewall's block page | `forbidden` | its own class `blocked`, which holds the origin also on a robots address |

Components: `access-control/4`, `access-hold-scope/1`, `robots-decision/3`. One small general rule
(`access_control.hold_scope`), no per-publisher exception.

## 4. The eighteen holds under the old and the new rule (from preserved answers; no request)

| Outlet | Preserved answer | Old | New |
|---|---|---|---|
| `es_el_pais` | 403 (Varnish) for `feeds.elpais.com/robots.txt` | origin held | **released**: robots unavailable on the feed host |
| `gt_nuestrodiario` | bare 403 (load balancer, 118 bytes) for `robots.txt` | origin held | **released**: robots unavailable |
| `mx_la_jornada` | 410 Gone of a retired Atom feed, detection script | origin held (misread as a challenge) | **released**: no control; that channel disabled |
| `ve_efecto_cocuyo` | browser check (403) on `/sitemap.xml`; the feed answered | origin held | **that URL held**; the feed and its articles may be asked |
| `py_adn_digital` | 403 on its feed | origin held (misnamed a challenge) | that URL held; it has no other channel |
| `cr_diario_extra`, `uy_el_pais` | Cloudflare managed challenge on a feed | origin held | that URL held; no other channel of theirs has answered — **not in the recovery wave**, nothing is tried |
| `hn_diariotiempo`, `ni_el_19_digital` | block page / managed challenge on the front page (their only channel) | origin held | that URL held; no other channel |
| `hn_proceso_digital` | Sucuri JavaScript challenge on its feed (2026-10-08) | origin held | that URL held; its sitemap answered 404; no other channel |
| `mx_milenio` | CloudFront "Request blocked" (403) for `robots.txt` | origin held (`forbidden`) | **origin held** (`blocked`) — a block page is not a missing robots file |
| `cu_cubanet`, `do_el_caribe`, `mx_el_siglo_de_torreon`, `ni_articulo66`, `pe_expreso`, `pe_peru21`, `ve_el_impulso` | Cloudflare managed challenge for `robots.txt` | origin held | **origin held** |

Derived mechanically from every pack of the workspace: 17 origins held by stored class before; **8 origins and 7 URLs** held
now. Four outlets are released to be asked (`es_el_pais`, `gt_nuestrodiario`, `mx_la_jornada`, `ve_efecto_cocuyo`). No outlet
outside the eighteen was held by the old rule: the list of 2026-10-09 was complete.

Six outlets whose only known channels are held or challenged are **not** freed for anything: a URL hold on every route is, in
effect, still the outlet's hold, and none of them is in the recovery wave.

## 5. The recovery wave — scope

Authorisation record `config/operator_authorizations/2026-10-10_recovery.json` (`DOA-2026-10-10-1`, wave `recovery`): eight
outlets, ten item requests and eight other requests each, at most 144 requests (the brief: 150) — the four released above
and the four whose origin was amended from the redirect of their own robots address on 2026-10-09 (`cu_5_de_septiembre`,
`cu_periodico26`, `hn_radio_progreso`, `mx_animal_politico`).

## 6. The recovery wave

### A first start that stopped at a gate (no request)

`bdaaade` armed shortly after midnight local on 2026-10-10 under the record issued that day; the suite passed on the arming commit; the
driver then refused to build the baseline: "the authorisation is valid from 2026-10-10 to 2026-10-11". It read the day in UTC
(still the 9th), the tool in local time. Disarmed (`bfeada1`; read back). No baseline, no request; the wave was not used. An
inconsistency of my own code, repaired: one clock, the local day, as the baseline file is named (`22762f3`; a regression test
that fails without it; full suite 1527 passed).

### The run

| | |
|---|---|
| Authorisation | `DOA-2026-10-10-1`, wave `recovery`, mode `DELEGATED_OPERATOR_AUTHORIZATION`; nothing typed, nothing simulated |
| Arming commit | `e9575b2778d2be2db3cb38cf029344537c87ac81` — tests on it: **1527 passed** |
| Baseline | `docs/canary/BASELINE_FROZEN_2026-10-10_recovery.json`, digest `b4117d8b22e5d47dcfe42b72f7c4d8241de753dfe5519e4e4efb45c6e5457e37`, commit `68e1828`; it pins policy `canary/2026-10-10.1` |
| Run | `acq1-20261009T224004943025Z-0ee53f4006f3`, 00:40:04–00:49:30 local; receipt `COMPLETE` |
| Evidence | commit `269989d`, `docs/canary/evidence/acq1-20261009T224004943025Z-0ee53f4006f3/` (with `evaluation.json`) |
| Disarming | commit `b1c7c1b`; read independently: `disabled` in the file, in `HEAD`, on `origin/main`; tree clean; tests on the disarmed tree 1527 passed |

**Requests: 53** of 144 allowed (the brief: 150) — 27 item, 26 other. Answers: 36 × 200, 2 × 301, 6 × 403, one timeout.
Refused before transport: 14 by a hold that arose in the run or was in force, 3 by the robots layer. **No request went to a
held origin or a held URL** (the Cocuyo sitemap was refused before transport). No request under the research override.
**Verification `PASS`** on all eight checks: 847 bodies read back and verified; 44 `RAW_PRESERVED` = 44 verified = 44
expected; 27 extractions replayed without network, 0 differ; receipt re-derived; 53 transport calls = 53 derived; nothing
pending; budget respected; workspace `CLEAN`.

| Outlet | Old → new finding | Asked (hosts) | Answers | Candidates | Item requests | Full article pages | Extraction (median characters) | Result |
|---|---|---|---|---|---|---|---|---|
| `es_el_pais` | origin held for a robots 403 → robots unavailable on the feed host | `feeds.elpais.com` (robots, feed), `elpais.com` (robots, 6 articles) | robots 403 (Varnish) → read as unavailable; feed **200**, 153 entries; `elpais.com/robots.txt` 200; 5 articles 200; the 6th **403, DataDome CAPTCHA** | 150 | 6 (4 more refused after the CAPTCHA) | **5** | 7 085 (2 998–24 521) | **`ACQUISITION_VERIFIED`**, and **held again**: a CAPTCHA on an article holds the origin |
| `ve_efecto_cocuyo` | origin held for a challenged sitemap → that URL held | `efectococuyo.com` (robots, feed, 10 articles); the sitemap **not asked** | all 200 | 10 | 10 | **10** | 3 394 (2 670–10 935) | **`ACQUISITION_VERIFIED`**, ready |
| `hn_radio_progreso` | robots redirect off the registered host → origin amended | `radioprogresohn.net` → `www.radioprogresohn.net` | all 200 | 10 | 10 | **10** | 3 277 (898–13 623) | **`ACQUISITION_VERIFIED`**, ready |
| `mx_la_jornada` | origin held by a misread 410 → released | `www.jornada.com.mx` (robots, RSS, one Atom feed, 1 article) | RSS 200 (106 entries); `feeds/mundo.atom.xml` **403 managed challenge**; the first article **403 managed challenge** | 105 | 1 (9 more refused) | 0 | — | **not recovered**: the articles themselves are behind a Cloudflare challenge. Origin held, correctly |
| `gt_nuestrodiario` | origin held for a robots 403 → robots unavailable | `www.nuestrodiario.com` (robots, its one listing) | both **403**, the same 118 bytes from a load balancer | 0 | 0 | 0 | — | not recovered: this client is refused everything it asked; the listing URL is held |
| `mx_animal_politico` | origin amended (apex) | `http://www`, `https://www`, apex (robots redirects), the feed | the feed address answered **301** to its `https://www` form; the redirect chains of the robots addresses of three host forms used the other-request budget before the feed could be followed | 0 | 0 | 0 | — | not recovered: a registration and budget matter — the feed should be registered at the address the server names |
| `cu_5_de_septiembre` | origin amended (apex) | `www.5septiembre.cu/robots.txt` → apex | the robots address redirects to the **home page** (HTML, 200): not a robots file | 0 | 0 | 0 | — | not recovered: unreadable robots address, held by `on_parse_error` |
| `cu_periodico26` | origin amended (apex) | `periodico26.cu` (robots) | timeout | 0 | 0 | 0 | — | not recovered: unreachable (RFC 9309 §2.3.1.4: restraint) |

**Recovered with articles: three outlets, 25 full article pages.** Two of them are ready for an intake; El País is not.

## 7. Efecto Cocuyo and La Jornada

**Efecto Cocuyo** is the case the scoped hold was made for: one route challenged, one route open, and the publisher's own
feed leading to articles that are served. Ten of ten. The sitemap address that answered with a browser check on 2026-10-09
was not requested again and is held as that address in every later run.

**La Jornada** is the case that shows what the change does not do. The classifier error is real and repaired; under the
repaired classifier the origin was rightly released; and the server then answered the first article with a managed
challenge. Nothing was retried, the other nine candidates were not requested, and the origin is held for what was actually
observed. The outcome for the corpus is the same as yesterday — Mexico has one verified outlet — and the reason is now the
right one.

## 8. El País, concretely

- **Legacy:** 1 142 accepted full articles until 2026-02-21, through one RSS feed on `feeds.elpais.com`.
- **Yesterday:** never asked for its feed: the feed host's robots address answered 403 and the origin was held.
- **Now:** the same 403 for the robots address (425 bytes from a Varnish cache, no challenge) is read as "robots file not
  available" on that host. The feed answered **200 with 153 entries**, 150 of them on `elpais.com`. `elpais.com` has its own
  robots file (200; it names 201 user agents, those read carry `Disallow: /`, and this project's agent is not among them; the general rules allow
  the article paths; no `tdm-reservation` header was sent). Five articles were requested ten seconds apart and answered 200
  with full pages (326 to 443 kB of HTML, 8 to 36 paragraphs; 2 998 to 24 521 characters of body text under the baseline
  extractor — **full articles, not teasers**). The sixth request, an article of the travel section, answered **403 with a
  DataDome CAPTCHA page** (`x-datadome: protected`, script from `captcha-delivery.com`). The policy held `https://elpais.com`
  at once; four further candidates were refused before transport; nothing was retried.
- **So:** El País is technically a working source for a handful of requests and then answers this client with a CAPTCHA.
  That is a real access control on the thing itself. It is **not** intake-ready, and nothing permitted makes it so: no CAPTCHA
  is solved, no pace or identity is varied to find out what triggers it. What could release it is the publisher (a research
  access agreement or an allowance for the crawler's identity) — an explicit authorisation under CPD-0027 §7(b).
- **Open and not decided here:**
  1. *Paywall.* One of the five pages declares itself not free (`"isAccessibleForFree": false` in its metadata) and was
     nevertheless served in full to an unauthenticated plain request. Nothing was circumvented — but whether such a page may
     be used is a question of the publisher's terms and of the TDM basis, not of HTTP. Nothing labels such pages yet; an
     intake should record that field before any of them is used.
  2. *TDM.* The robots file's long list of excluded agents (AI and archive crawlers among them, "Bloque bots global
     confirmado 20260505") is evidence of the publisher's stance towards automated collection even though it does not name
     this agent. Under CPD-0017 that is evidence for the legal layer, which the operator and the institution hold.
  3. *Why the CAPTCHA came at the sixth request* — a count, the section, the pace — is not shown by one run and is not probed.

## 9. The holds now

`config/source_discovery/access_holds_2026-10-10.json` (`scripts/derive_access_holds.py`): every preserved answer that was
or is read as a control, with its class then, its class now and what it holds — the full table of old and new
classifications, 24 answers.

| | Before the change (2026-10-09) | After the change, before the wave | After the wave |
|---|---|---|---|
| origins held | 17 by stored class (18 outlets, with `hn_proceso_digital` by re-reading) | 8 | **10** |
| single URLs held | — | 7 | **9** |
| outlets with nothing usable because of a control | 18 | 14 | **17** |

Held origins (10): the seven whose robots address is challenged (`cu_cubanet`, `do_el_caribe`, `mx_el_siglo_de_torreon`,
`ni_articulo66`, `pe_expreso`, `pe_peru21`, `ve_el_impulso`), `mx_milenio` (block page), and — new, from this wave's own
answers — `es_el_pais` (CAPTCHA on an article) and `mx_la_jornada` (challenge on an article). Held URLs (9): the challenged
or refused routes of `cr_diario_extra`, `hn_diariotiempo`, `hn_proceso_digital`, `ni_el_19_digital`, `py_adn_digital`,
`uy_el_pais`, `gt_nuestrodiario`, one Atom feed of La Jornada, and Cocuyo's sitemap.

**Correctly released and working: 1 outlet** (`ve_efecto_cocuyo`: an origin hold became a URL hold, and the outlet yields
articles). **Released and then held for a real control: 2** (`es_el_pais` after five articles, `mx_la_jornada` at once).
**Released and refused on its only route: 1** (`gt_nuestrodiario`). **Unchanged: 14.** Plus, outside the eighteen:
`hn_radio_progreso` recovered by its amended origin.

## 10. Countries and the legacy stock

| | Verified and usable before | Now |
|---|---|---|
| Mexico | 1 | **1** — no change: La Jornada and Animal Político did not yield; three outlets held |
| Spain | 5 | **5 usable**; El País verified (five articles) and held |
| Venezuela | 6 | **7** (Efecto Cocuyo) |
| Honduras | 5 | **6** (Radio Progreso) |
| all 20 countries | 83 outlets | **85 usable**, 86 verified |

Of the 42 outlets the legacy system took accepted articles from, **37 now have verified acquisition here** (35 before), 36 of
them usable. The five that do not: `bo_pagina_siete` (closed), `hn_proceso_digital` and `uy_el_pais` (challenged),
`cr_crhoy` (dead feed), `bo_lostiempos` (a listing without a rule).

## 11. Intake readiness

`config/intake/intake_readiness_2026-10-10.1.json`, from `config/source_discovery/source_inventory_2026-10-10.1.json`
(page: [`SOURCE_QUALIFICATION_2026-10-10.1`](../corpus_supply/SOURCE_QUALIFICATION_2026-10-10.1.md)). The files of
2026-10-09 are unchanged.

**87 outlets — 85 in tier A, 2 in tier B — with 121 usable channels in 20 countries.** New in tier A: `ve_efecto_cocuyo`,
`hn_radio_progreso`. Not in it although verified: `es_el_pais` (origin held). The file now carries the held origins and
held URLs as derived, names each outlet's held routes, and no listed channel is a held URL (tested). 17 outlets are listed
as held, 31 as excluded hypotheses, 10 as registered and not ready.

It starts nothing. A 12- or 24-hour intake remains a separate, separately authorised run with a driver of its own.

## 12. Does the change reduce selection bias?

- **Reproducibility:** the three cases of 2026-10-09 are replayed in the test suite on their preserved answers, and the
  holds are derived from the packs by a script whose output is tracked. Shown.
- **Robustness:** the robots address now has a tested reading for 200, 301/302 (off-origin), 401, 403, 404, 410, 429, 5xx,
  a block page and a challenge; a channel's failure no longer decides for the outlet. Shown offline; on real servers for a
  robots 403 (twice), a challenged route beside a working one, and a control arriving mid-run.
- **Replicability:** two legacy-productive outlets the project had lost (Efecto Cocuyo, El País) answered again with full
  articles on a new day — one of them for five requests only.
- **Generalisability:** modest, and the wave says so itself. The rule released four outlets and one of them works. It
  removed the holds this project had imposed on itself; it does not, and must not, remove the publishers' own. **Fourteen of
  the eighteen holds were real, and two more became real when asked.** The technical selection effect that remains is the
  publishers' bot management — Cloudflare, DataDome, Sucuri — and it falls on large national titles (El País, La Jornada,
  Milenio, El País Uruguay) as on small independent ones.

A feed that is read is not an article that is taken; one wave is not stability; better reach is not representativeness.

## 13. Tests, files, git

Suite: 1526 passed after the policy change, 1527 on the arming commit and on the disarmed tree; **1529 passed, 14 skipped** on
the final tree. New or changed: the scope table; robots 401/403/404/410/429/5xx; the three cases on their
preserved answers; feed host and article host apart; a challenged channel beside a working one, also across runs; a block
page; the local-day validity; the readiness file against the holds snapshot. Seven tests that encoded the origin-wide hold
were moved to the scoped one, each by name and with the reason in its docstring — none was loosened about a control on an
item page or a challenged robots address.

Created: CPD-0027; `scripts/derive_access_holds.py`; `config/source_discovery/access_holds_2026-10-10.json`,
`source_inventory_2026-10-10.1.json`; `config/intake/intake_readiness_2026-10-10.1.json`;
`docs/corpus_supply/SOURCE_QUALIFICATION_2026-10-10.1.md`; `config/operator_authorizations/2026-10-10_recovery.json`; four
fixtures (preserved answers); a baseline and an evidence directory (by the tool) with its `evaluation.json`; this report.
Changed: `access_control.py`, `robots.py`, `fetcher.py`, `policy.py`, `canary_driver.py`; `config/acquisition_policy.json`
(version, note, one disabled channel); `scripts/build_intake_readiness.py`; tests; `docs/STATUS.md`, the decision registry,
the architecture index, the terminology table; forward links in CPD-0017 and CPD-0026.
Not changed: any earlier authorisation record, baseline, receipt, inventory, readiness file or access review; CO.RA.PAN; the
legacy repository.

**Slips of this run.** The UTC/local date inconsistency, above. CPD-0026 §3 had said that La Jornada's origin would be
released by re-derivation; the code re-read stored answers in one direction only, so that sentence was not true until this
run — CPD-0026 carries a dated note. Twice an inline shell command with backticks damaged text I was writing into a test;
both were caught by the next test run and corrected before any commit.

## 14. Open gates

- **El País:** the publisher. And two questions that need the operator and the institution, not a crawler: pages that
  declare themselves not free; the publisher's stance on automated collection.
- **Mexico:** one verified outlet. Animal Político needs its feed registered at the address the server names and a robots
  budget that survives three host forms; El Sol de México and Expansión have no evidenced channel or origin; three are held.
- The operator's review of CPD-0025, CPD-0026 (identity adoption, the threshold of three) and CPD-0027.
- A robots address that redirects to a home page (`cu_5_de_septiembre`): held as unreadable; whether that is "no robots
  file" is a further, smaller policy question.
- Four listings without a rule; 22 hypotheses without an evidenced channel.
- Every production gate of `docs/STATUS.md` §5.

## Operator report

**Ergebnis.** Durch die korrigierte Zugriffspolitik wurden **zwei** wissenschaftlich wichtige Quellen mit Artikeln
zurückgewonnen – **Efecto Cocuyo** (10 Artikel, intake-bereit) und **El País** (5 vollständige Artikel, danach CAPTCHA, nicht
intake-bereit) – und über eine Origin-Korrektur **Radio Progreso** (10 Artikel). 25 Artikelseiten, konserviert, verifiziert,
replayt.

**Status.** Policy-Implementierung: `PASS`. Fresh Validation: `PARTIAL` (3 von 8 Outlets liefern; 53 von 150 erlaubten
Requests; Verifikation `PASS`; disarmt). Ein erster Start stoppte ohne Request an einer Datums-Inkonsistenz meines Codes.

**El País.** Technisch wieder erreichbar: Der 403 auf die `robots.txt` des Feed-Hosts gilt jetzt als „robots nicht
verfügbar“, der Feed antwortete mit 153 Einträgen, fünf Artikel kamen vollständig. **Beim sechsten Artikel antwortete
`elpais.com` mit einem DataDome-CAPTCHA** – eine echte Zugriffskontrolle auf dem Inhalt selbst; der Origin ist seitdem
gehalten, nichts wurde wiederholt oder umgangen. Für den Intake ist El País damit **nicht** einsatzfähig. Was es freigeben
kann, ist der Verlag. Zusätzlich offen: Einer der fünf Artikel ist als nicht frei zugänglich ausgezeichnet und wurde trotzdem
vollständig ausgeliefert – eine Rechts-, keine Technikfrage.

**Andere Medien.** *Efecto Cocuyo:* zurückgewonnen; die Sitemap bleibt als einzelne Adresse gesperrt. *La Jornada:* Der
Klassifikationsfehler ist behoben, aber die Artikelseiten selbst liegen hinter einer Cloudflare-Challenge – echte Sperre,
Mexiko bleibt bei einer Zeitung. *Nuestro Diario:* verweigert diesem Client alles (403). *Animal Político, 5 de Septiembre,
Periódico 26:* nicht erreicht (Redirect-Ketten bzw. unlesbare/unerreichbare `robots.txt`). *Proceso Digital, El País Uruguay,
Milenio* und die übrigen: unverändert gehalten.

**Wissenschaftliche Konsequenz.** Die selbst auferlegte Verzerrung ist beseitigt: Vier Sperren beruhten nur auf unserer
Regel, keine davon besteht mehr. Der Ertrag ist ehrlich klein – eine dauerhaft nutzbare Quelle mehr aus den achtzehn –, weil
vierzehn Sperren echt waren und zwei weitere es wurden, sobald wir fragten. Die verbleibende Verzerrung liegt beim
Bot-Schutz der Verlage und trifft gerade große Titel (El País, La Jornada, Milenio, El País Uruguay).

**Nächster Schritt.** Für den 24-Stunden-Intake stehen **87 Outlets mit 121 Kanälen in 20 Ländern** bereit. Notwendig sind
nur noch: (1) Ihre Bestätigung der offenen Entscheidungen aus CPD-0025 bis CPD-0027, (2) ein Intake-Treiber mit eigener
Autorisierung. El País und die mexikanische Lücke lassen sich nicht technisch, sondern nur über die Verlage schließen.
