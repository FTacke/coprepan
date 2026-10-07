# COPREPAN 3.0 — Discovery, acquisition readiness, interoperability and offline end-to-end

```text
run_started_at:      2026-10-07T22:05:46+02:00   (first clock reading)
run_ended_at:        2026-10-07T22:38:59+02:00   (last clock reading before this report; the documentation commit and the push followed)
timezone:            Europe/Berlin
wall_clock_seconds:  1993   (between the two readings above)
status:              PASS   — for the offline / readiness scope of §0
kind of run:         decision + implementation, with reproducibility and robustness checks.
                     No scientific validation. No production activation.
EXTERNAL_API_USAGE = NONE   (no model API, no external service, no request to any outlet or other website)
NETWORK USE:         `git fetch` / `git push` to `origin`; one `pip install warcio==1.7.5` from the
                     package index (a test-only dependency, §8). HTTP requests of the tests went to a
                     server on a literal loopback address started by the test itself.
```

## 0. What `PASS` covers, and what it does not

**Covers:** the acquisition pipeline is technically complete offline — discovery, a real HTTP
transport, a policy gate, crawler identity, raw preservation, identity, extraction, replay — and
passes an end-to-end canary with failure injection; the readiness instruments for the open
operator decisions exist; CPD-0004 and CPD-0005 were audited and CPD-0005 amended before any real
acquisition.

**Does not cover, and must not be read into it:** production acquisition is **not** activated; the
registry is **not** released (82 outlets `proposed`, 0 `registered`); **no** real outlet's
compatibility is shown (not one external request was made); **no** scientific quality is
validated; **nothing** is generalisable from synthetic documents on a loopback server. TLS was
not exercised. No gate of `docs/STATUS.md` §5 is passed.

## 1. State at the start (measured 22:05 +02:00)

| Item | State |
|---|---|
| branch, `HEAD`, `origin/main` | `main`, `a54ce05a58af8f0c2d77ab4d9020882bf8be2399`, equal |
| working tree | clean, nothing ignored, no foreign change |
| full suite | 424 passed |
| registry | 82 proposed outlets, 352 proposed channels, 0 registered |

Read against each other: `AGENTS.md`, `CLAUDE.md`, `docs/STATUS.md`, the master plan, both
preceding run reports, the corpus-supply index, CPD-0001 to CPD-0005. No conflict between
authoritative documents. One naming overlap was found and resolved: the brief's "freeze manifest
for an acquisition start" is not the master plan's O-10 (the *legacy* freeze manifest). The new
thing is recorded as O-12; O-10 is untouched (§12).

## 2. Phase A — audit of CPD-0004 and CPD-0005

Full table: [CPD-0006](../decisions/CPD-0006_discovery-transport-policy-gate-and-readiness.md) §0.

| Examined | Outcome |
|---|---|
| CPD-0004, every disposition | **KEEP** — nothing in the discovery or transport work argues for reviving a legacy component |
| identity: tracking parameters, AMP / mobile / print, redirects, missing canonical, same URL / new text, other URL / same body, moved content | **KEEP** — each has a test and behaves as decided |
| identity: canonical on another origin | **KEEP** — ignored for the key, kept as evidence; test added |
| identity: many pages declaring one canonical | **AMEND** — observations keep each fetch's own URL keys; `canonical_collapse_suspects()` lists the case |
| identity: what may become a document | **AMEND** — `fetch_kind`; only an `item` |
| pack model (per outlet and UTC day, append / seal, derived index, crash recovery, promotion, replay) | **KEEP** |
| pack digest semantics | **AMEND** — "the body" defined: the HTTP payload with content coding, without transfer coding |

The amendments were made now because nothing real exists yet: no fetch record, pack, id or
document of corpus material is affected. CPD-0005 got a dated status note pointing to CPD-0006.

## 3. Phase B — registry review package (O-11)

`src/coprepan/registry_review.py` generates, from the tracked proposal:
[`docs/corpus_supply/REGISTRY_REVIEW_PACKAGE.md`](../corpus_supply/REGISTRY_REVIEW_PACKAGE.md)
(to read) and `config/registry_review/outlet_review_package.json` (full data). A test fails if
either differs from what the generator produces from the tracked registry.

- **Nothing was registered and nothing in the registry was changed.** No attribute was invented:
  `outlet_type`, `outlet_group`, seat, `access_model`, `medium`, `timezone` are listed as unknown
  for all 82; `publisher` is `unknown` for all 82. Nothing was looked up outside the repository.
- **Id convention proposed:** `{country_id}_{ASCII slug of the display name}`. It changes 21 of
  the 82 imported ids, leaves 61, produces no collision (measured on the proposal). The legacy
  code stays an alias; the mapping table legacy → imported → recommended is in the package.
- **Channel ids proposed:** `{outlet_id}:ch:{kind}_{slug of the URL path}`; 352 unique.
- **Findings** (measured): 54 routine; 23 outlets without any channel; 5 with channels on hosts
  that are not the outlet's, one of them a real judgement case (`pr_primera_hora`'s three
  channels are on `www.elnuevodia.com`, the origin of `pr_el_nuevo_dia`); 6 with an additional
  origin candidate; 29 without a channel that was active in legacy.
- **Left for a human:** corpus-supply index §17 — five items, none of them fillable by code.

## 4. Phase C/D — discovery

Contract: CPD-0006 §2; code `src/coprepan/discovery.py`; tests `tests/test_discovery.py` (32).

| Requirement of the brief | How it is met |
|---|---|
| RSS, Atom, sitemap `urlset`, sitemap index, HTML listing | five parsers; RSS 1.0 (RDF) and namespace variants included; the bytes decide the format |
| separate from fetch; no article rows, no raw preservation | discovery reads bytes handed to it and writes three evidence tables; a test asserts it writes nothing else and requests no candidate |
| outlet/channel identity, method, input identity, observed URL, time/run, source location, hints, parser version, normalisation, provenance | fields of the event and input rows |
| duplicate URLs in one feed; same URL from several channels | several events, one candidate |
| pagination; index → sitemap; recursion; cycles | breadth-first expansion; a repeat or cycle is recorded and not followed |
| invalid XML; malformed HTML; namespace variants | `UNPARSEABLE` input with a reason, no candidate from half a feed; lenient HTML; local-name matching |
| relative URLs; `<base>`; fragments; query strings | resolved against the document's final URL or its first `<base>`; fragment dropped; query kept |
| entries without link | an event with `no_link`, no candidate |
| canonical and redirect hints | hints are stored as written; a redirect of the channel document changes the base only |
| budgets: depth, documents, candidates, bytes | `DiscoveryBudget`, all four required; each tested; a stop names its limit |

**Recorded discovery corpus.** No real recorded channel document exists: the legacy system stored
no feed, sitemap or page (archaeology F-1), and none may be fetched. Eight synthetic fixtures were
written (`tests/fixtures/discovery/`, hashes pinned), documented as synthetic. They contain the
cases the code must handle; they are not a sample of real outlets.

## 5. Phase E/F/G — transport, crawler identity, policy gate

**Fetcher** (`src/coprepan/fetcher.py`, CPD-0006 §3): `http.client`, no third-party client. One
fetch record per attempt. Tested against a real HTTP server on a loopback address
(`tests/test_fetcher.py`, 35 tests): 200 HTML; RSS/XML; a content type that lies; 301/302 and a
chain across two origins; a redirect loop; a redirect off the outlet; 404 and other 4xx (not
retried); 429 with `Retry-After`; 500/503 with backoff; retry exhaustion; gzip (stored as sent);
chunked (framing removed); empty body; a body at the size limit and one byte over it; a body cut
before its declared length; a chunked body without its end; a timeout; a refused connection;
pacing per origin. Waiting is injected: no test sleeps for a backoff.

One defect of the standard library's behaviour was found and handled: `http.client` does not
raise when a body ends before its declared `Content-Length` if it is read in pieces; the fetcher
checks the remaining length itself. Without that check a truncated page would have been stored as
a complete one.

**Crawler identity** (`src/coprepan/crawler_identity.py`, CPD-0006 §4): software, operator,
`User-Agent` and run are four separate things; the `User-Agent` is derived. No built-in identity;
`config/crawler_identity.json` ships `not_configured`; placeholder and reserved domains are
refused (the legacy system sent `research@university.edu`).
`TECHNICAL_CONTRACT = PASS`, `EXTERNAL_ACTIVATION = BLOCKED`.

**Policy gate** (`src/coprepan/policy.py`, CPD-0006 §5): `ALLOW` / `DENY` / `DEFER`; nothing is
allowed by default; `config/acquisition_policy.json` ships `NOT_DECIDED` and denies everything.
Prepared and tested: outlet registered; URL on a known origin; outlet and channel switches;
explicit opt-outs; temporary suppressions; a configured pace; robots evidence. **No normative
value was chosen.**

**Robots** (`src/coprepan/robots.py`): an RFC 9309 parser and four evidence states. Fetched
through the gate, preserved as a fetch, weighed as the policy says. No robots file of a real site
was requested. No legal reading is made anywhere.

## 6. Phase H — WARC interoperability

Reader: **warcio 1.7.5**, pinned as a test-only dependency (`pyproject.toml`, `dev` extra). It
shares no code with `coprepan.pack`.

**Result, with its exact scope:** packs written by `pack-writer/1` — `warcinfo`, `response`,
`metadata` records, one gzip member each — are read by warcio's `ArchiveIterator` with digest
checking on. Verified: every record found; record types; `WARC-Target-URI` (including non-ASCII);
`WARC-Record-ID`; `WARC-Date`; HTTP status and headers; **payload bytes exact** for text, empty,
binary, content-coded and 300 KB bodies; SHA-256 block and payload digests accepted, and a wrong
digest flagged (so the reader really checks); a sealed pack; the promoted pack of the offline
canary; agreement between the repository's own index and warcio on every body.

Not claimed: general WARC conformance; any other tool.

The writer needed one change to be interoperable in a case the first probe did not contain: a
`Transfer-Encoding: chunked` header rendered as received would make a reader de-chunk stored
bytes that are not chunked. It is now written as `X-Coprepan-Orig-Transfer-Encoding` in the pack
(CPD-0006 §1.2); a regression test covers it.

A finding kept as a test: warcio reads a **truncated** pack without complaint and returns less.
Interoperability is not fixity; the pack's manifest hash and the repository's own scan are.

## 7. Phase I/J/K — preservation readiness, capacity, baseline manifest

**O-3.** No preservation target is named in the repository or its configuration
(`COPREPAN_PRESERVATION_ROOT` is unset; a test asserts the refusal). None was invented and none
was probed. Built: the contract and `check_readiness` (storage index §15) — usable root, identity
marker, free space, writability, the promotion sequence, no silent overwrite, long names, fixity
of what is held. The probe writes a few hundred bytes into its own directory and removes them.

**O-4.** Built: a calculator whose inputs carry `measured` / `estimated` / `assumed` and whose
outputs carry the weakest label beneath them (storage index §16). Evidence gathered, measured
2026-10-07 on a copy of the legacy database and on file sizes: 64,932 legacy fetch rows over 23
crawl days (median 3,112 per active day; 115 per outlet-day; 53 outlets); `ok` text mean 2,854
characters; `json_raw` 127.0 MB, `json_annotated` 17.0 GB; pack overhead about 1.3 KB per fetch
(synthetic). **O-4 cannot be closed:** the size of a real stored page has never been measured —
the legacy system kept none. Missing, exactly: *stored body bytes per fetch and fetches per
outlet-day on real outlets*. The legacy database's source file had the same SHA-256 before and
after (`7fe49907…8ed5b7`); the work copy was removed.

**Baseline manifest.** `src/coprepan/freeze.py` (CPD-0006 §9) hashes registry, policy, crawler
identity, configuration, the six decisions, 26 schema ids, component versions, fixture manifests,
and records code commit, storage target, test baseline, time and operator. As committed the
repository is **`PRE_FREEZE`** with five blockers (O-11, O-1, O-2, O-3, O-4). A freeze is an
operator act that states the manifest's digest and is refused while anything blocks; a test tries
to forge the state and fails. No manifest file is tracked: it names a commit and is built on demand.

## 8. Files

**Created — code:** `src/coprepan/` `discovery.py`, `robots.py`, `policy.py`,
`crawler_identity.py`, `fetcher.py`, `http_acquisition.py`, `preservation_target.py`,
`capacity.py`, `freeze.py`, `registry_review.py`.
**Created — configuration:** `config/acquisition_policy.json` (`NOT_DECIDED`),
`config/crawler_identity.json` (`not_configured`),
`config/registry_review/outlet_review_package.json` (generated).
**Created — tests:** `test_discovery.py`, `test_policy.py`, `test_fetcher.py`,
`test_warc_interoperability.py`, `test_readiness.py`, `test_offline_e2e.py`, `support_http.py`;
`tests/fixtures/discovery/` (eight documents and `MANIFEST.json`).
**Created — documents:** CPD-0006; `docs/corpus_supply/REGISTRY_REVIEW_PACKAGE.md` (generated);
this report.

**Changed — code:** `acquisition.py` (fetch kind, attempt, policy block, content encoding, run
kind `http_fetch`, three failure reasons), `pack.py` (header rendering rule), `extraction.py`
(content decoding as a recorded step), `document_identity.py` (own URL keys, collapse diagnostic,
decoded head scan), `core_pipeline.py` (`record_exchange` factored out; only items become
documents), `layer_store.py` ("already stored" re-reads the bytes), `__init__.py`, `pyproject.toml`
(version 0.3.0; `warcio==1.7.5` in the `dev` extra).
**Changed — tests:** `conftest.py` and `test_test_guards.py` (loopback rule, below),
`test_core_pipeline.py` (+4), `test_preservation.py` (structural check: six named removals over
28 modules), the suite manifest, `tests/fixtures/README.md`.
**Changed — documents:** `AGENTS.md` §7; `docs/STATUS.md`; the master plan (dated notes, O-12);
the architecture index and terminology (§10); the acquisition, storage, corpus-supply, identity
and extraction indexes; the decision registry; CPD-0005 (one dated status-note row); `README.md`.

**A rule was changed, deliberately:** `AGENTS.md` §7 said no test may open a connection at all.
The brief orders a real local HTTP server. The rule now allows a test to connect to a **literal
loopback address** of a server it started; the guard in `tests/conftest.py` enforces exactly that
(a name, including `localhost`, and any non-loopback address are refused before a packet is
sent), and the guard's tests were rewritten to prove both halves. This is a change of a standing
rule on the operator's instruction, recorded here and in `AGENTS.md`.

**Environment change outside the repository:** `warcio 1.7.5` was installed into the workstation's
Python (`pip install`), as the test-only dependency the `dev` extra now names.

**Moved, deleted, overwritten:** nothing in the repository's history or evidence. Earlier run
reports unchanged. `config/outlet_registry.json` unchanged. No reference repository was written
to; the legacy database was read as a copy, and the copy was removed.

## 9. Phase L — the offline end-to-end canary

`tests/test_offline_e2e.py` (18 tests), on the production code path:

```text
registered channel → policy gate → HTTP fetch (loopback) → discovery → candidate → policy gate
   → HTTP fetch (loopback) → fetch record → WARC pack → seal → promotion → RAW_PRESERVED
   → document identity → extraction → document version → replay
```

A scripted HTTP server on `127.0.0.1` plays an invented outlet under its logical `https://…test`
names (the fetcher's connection override dials the loopback port; the policy gate is told the
address really dialled). Two channels: an RSS feed with pagination and a sitemap index with a
nested index, a gzip-encoded sitemap and cycles. Items include a page with a canonical, a
redirected page without content type, a gzip-encoded page, a chunked page behind a 503 with
`Retry-After`, a PDF, two pages differing only in path case, and a page that answers 404.

What actually ran, in one pass (measured in the test run of §11): 1 robots request; 6 channel
documents; 7 candidates discovered and requested; 15 fetch records (6 channel documents, 8 item
attempts, 1 robots file) in one pack; pack sealed and promoted with its index; 15 fetches
`RAW_PRESERVED`; 8 item fetches assigned to 7 documents; extraction of each; replay of each.

| Property | Result |
|---|---|
| deterministic identities | a second, independent pass gives the same run id, summary and results; **every file of the workspace is byte-identical**, and so is the sealed pack |
| acquisition-run semantics | a later run in the same workspace gets a new run id, re-reads the channels, finds no new candidate, requests no item again |
| reproducible discovery | same documents → same rows in the same order; re-reading recorded documents adds nothing |
| same raw bytes; fixity | every preserved body equals what the server sent and hashes to its record; gzip kept as sent, chunk framing removed |
| WARC interoperability | the promoted pack is read by warcio with digests checked; payloads equal |
| replay | every extraction re-derived from the preservation root, with sockets disabled |
| no mutation of preserved artefacts | after the later run, every file of the first day on the preservation root is unchanged; four files were added |
| no workstation dependency | no record contains the directory, the loopback address or the port |
| fail closed as committed | with the tracked policy, both channel requests are denied and no transport call is made |

## 10. Failure injection

| Break | What happens | Test |
|---|---|---|
| discovery parse failure | that channel yields no candidate; the unparseable document is preserved; the other channel proceeds | `test_discovery_parse_failure_stops_that_channel_only` |
| policy deny | no request; a `DENIED` row with the reason; no fetch id is invented for a request never made | `test_policy_deny_makes_no_request…` |
| robots disallow | the disallowed item is never requested; it stays an open candidate | `test_robots_disallow_is_enforced_inside_the_run` |
| HTTP transport failure; truncated response | three `FETCH_FAILED` records, none `RAW_PRESERVED`, no document; the candidate stays open | `test_transport_failure_and_retry_exhaustion…` |
| retry exhaustion | three 503 responses preserved as what they are; `gave_up` recorded | same |
| process killed mid-run | run and request visibly unfinished; nothing derivable; resume completes; the interrupted request stays on record | `test_an_interrupted_run_resumes…` |
| pack failure (torn tail) | not sealed, nothing promoted; tail quarantined, then sealed | `test_a_torn_pack_is_not_sealed…` |
| promotion failure | fetches stay `PRESERVATION_PENDING`; derivation refused; a later promotion completes | `test_pack_and_promotion_failures…` |
| index corruption | the preserved pack is not read at all | `test_a_corrupted_index_or_pack…` |
| damaged master | not read; re-promotion reports `repaired` from the verified workspace copy | same |
| identity-store conflict | a colliding id is refused (`DocumentIdCollision`) | `test_core_pipeline.py` |
| extraction failure | the run stops loudly; no version is invented; a working extractor completes | `test_an_identity_conflict_and_an_extraction_failure…` |
| replay corruption | a stored extraction whose bytes changed is refused on reuse and on replay | same |

The replay case exposed a real gap: `LayerStore.put` answered "already stored" from the manifest
alone. It now re-reads the stored bytes first.

## 11. Tests

`python -m pytest -p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, Python 3.12.10, pytest 9.1.1.
Measured 2026-10-07 22:38 +02:00, before this report existed: **597 collected, 596 passed, 1
failed** — `test_relative_links_resolve`, because five documents link to this report. Final figure:
operator's closing message (expected 597 passed). Start of the run: 424.

| Module | Tests | Kind |
|---|---|---|
| `test_discovery.py` | 32 (new) | reproducibility; robustness (malformed, cyclic, unavailable, budgets) |
| `test_fetcher.py` | 35 (new) | robustness of the real transport; reproducibility (same script, same exchanges) |
| `test_policy.py` | 41 (new) | fail-closed invariants; robots parser |
| `test_warc_interoperability.py` | 8 (new) | interoperability with one independent reader |
| `test_readiness.py` | 28 (new) | reproducibility (generated package, manifest); fail-closed invariants |
| `test_offline_e2e.py` | 18 (new) | reproducibility (two passes); robustness (failure injection) |
| `test_core_pipeline.py` | 25 (+4) | the audit's identity cases |
| `test_test_guards.py` | 9 (was 3) | the loopback rule |
| `test_repository_contract.py` | 22 (+1) | CPD-0006 header |
| unchanged modules | 379 | regression of the earlier guarantees |

Invariants of the brief and where they hold: same canonical input → same key
(`test_same_canonical_input_gives_the_same_candidate`, the URL-key properties); same bytes → same
digest, different bytes → different (`test_raw_bytes…`, fetch-record tests); sealed pack immutable
(`test_a_sealed_pack_is_never_appended_to…`); preserved layer never overwritten
(`test_a_later_run…`, `FingerprintConflict`); registered-only lookup
(`test_an_unregistered_outlet_is_never_fetched`); denied policy → no transport call
(`test_a_denied_intent_makes_no_transport_call`); failed fetch → never `RAW_PRESERVED`
(`test_transport_failure…`); replay → no network (`test_replay_needs_no_network…`).

## 12. Gate assessment

Status language: `docs/STATUS.md` §5 (technical state and gate state are separate columns).

| Gate | Technical state | Gate state | Why not further |
|---|---|---|---|
| **O-1** policy, robots, opt-out | `TECHNICALLY_READY` | **`OPEN`** | the normative decision is the institution's; nothing was chosen |
| **O-2** crawler identity | `TECHNICALLY_READY` (`TECHNICAL_CONTRACT = PASS`) | **`READY_FOR_HUMAN_REVIEW`** (`EXTERNAL_ACTIVATION = BLOCKED`) | four operator values are missing |
| **O-3** preservation target | `TECHNICALLY_READY` | **`OPEN`** | no target is chosen; none was probed |
| **O-4** capacity | `TECHNICALLY_READY` | **`OPEN`** | bytes per real fetched page have never been measured |
| **O-10** legacy freeze manifest | `NOT_BUILT` | **`OPEN`** | not ordered; needs the operator's go-ahead |
| **O-11** registry review | `TECHNICALLY_READY` | **`READY_FOR_HUMAN_REVIEW`** | registration is a human act |
| **O-12** acquisition baseline freeze (new) | `TECHNICALLY_READY`, state `PRE_FREEZE` | **`OPEN`** | five blockers; a freeze is an operator act |

No gate is `PASS`. None is `BLOCKED_EXTERNAL`: nothing waits on a party outside the project.

## 13. Validation classification

| Check | Kind |
|---|---|
| pinned formats and ids; two byte-identical acquisition passes; deterministic discovery, review package, manifest; replay | **reproducibility** |
| failure injection of §10; the transport against scripted bad servers; malformed and cyclic channel documents | **robustness** (failures scripted or injected in-process; no process is killed; no network share) |
| packs read by warcio | **interoperability with one independent reader** for the written subset — an independent *reading* of the same artefact, not a replication of any result |
| — | **replicability: not claimed** (no independent implementation or second environment reproduced anything) |
| — | **generalisability: none** (one invented outlet, synthetic documents, a loopback server) |

## 14. Known limitations and real risks

- **Nothing here has met a real server.** Real feeds, redirects, error pages, encodings and bot
  protection will differ from the scripted ones in ways not yet known.
- **TLS is untested.** Every request in the tests was plain HTTP on loopback.
- **The extractor is still the unvalidated baseline.** An error page "extracts"; deciding it is
  not an article is an admission label that does not exist yet.
- **Every listed URL is a candidate.** An HTML listing lists navigation too; no per-outlet filter
  exists, so a real listing page would plan many non-article fetches.
- **No re-fetch schedule:** an answered candidate is never requested again, so updates are
  observed only when a channel lists a new URL.
- A `503` answer counts as "answered": the candidate is not retried by a later run.
- The canonical-collapse diagnostic lists suspects; it cannot tell a template defect from
  legitimate variants the outlet's rules do not fold yet.
- Robots: product-token matching is exact; `Crawl-delay` is recorded, not applied; `Sitemap:`
  lines are not used for discovery.
- One request at a time; no concurrency across origins; no conditional requests.
- The readiness check has only ever run on a local temporary directory, never on a network share.
- Capacity: no real page size exists anywhere in the evidence.
- The review package's host comparison is lexical (`www.` / `m.` stripped): `feeds.elpais.com` is
  flagged as "not the outlet's host" although it is a subdomain. A flag for review, not an error.
- The loopback rule widens what a test may do. The guard is tested; it remains a rule that could
  be weakened by a later edit.

## 15. Next step

Of the four options of the brief:

- **A) Human registry review — yes, next.** It is the shortest open item, the package reduces it
  to five decisions, and the canary needs only about five registered outlets, not all 82.
- **B) Policy and preservation operator decisions — in parallel with A.** O-1 (policy), O-2 (four
  identity values), O-3 (target). Nothing technical waits in front of them.
- **C) First controlled real acquisition canary — not yet.** It needs A for its outlets and B in
  full. It is also what closes O-4.
- **D) Technical work still needed before A–C — none.** Useful work that can run meanwhile, but
  blocks nothing: admission labels, a re-fetch schedule and channel health, per-outlet candidate
  filters, the legacy freeze manifest once O-10 is given.

**Recommended next run (exactly one), once A and B are answered:** the Phase-2 canary — about five
registered outlets, under the decided policy and identity, onto the chosen target, with the
measurement of bytes per fetch as a required output.

## 16. Operator report

1. **Result:** the acquisition pipeline is technically complete offline and fails closed
   externally.
2. **Status:** `PASS` for the offline / readiness scope. Not an activation, not a registry
   release, not evidence about any real outlet, not a scientific validation.
3. **Consequence:** what separates this state from the first real fetch is operator decisions
   (O-11, O-1, O-2, O-3), not engineering.
4. **Next:** A and B in parallel; then the Phase-2 canary.
5. **Files:** §8. One standing rule changed on instruction (`AGENTS.md` §7, loopback). One package
   installed on the workstation (`warcio 1.7.5`). Nothing moved, deleted or overwritten.
6. **Untouched:** the legacy repositories and data (one database file read as a copy), CO.RA.PAN
   3.0 (not opened in this run), the studies archive, `C:\dev\corapan`,
   `config/outlet_registry.json`. No request to any real website.
