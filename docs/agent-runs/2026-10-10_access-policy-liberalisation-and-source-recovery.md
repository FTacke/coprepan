# Access policy: holds with a scope, the robots address by RFC 9309, and a bounded recovery wave

```text
run_started_at:      2026-10-09T23:43:00+02:00 (first clock reading of the run)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

This report is written in stages. A section exists only for what has happened.

**Status at this commit: the policy change is implemented and tested offline; no request has been made under it.**

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
