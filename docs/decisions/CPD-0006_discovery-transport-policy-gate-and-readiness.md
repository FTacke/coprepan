# CPD-0006 — Discovery, HTTP transport, policy gate, crawler identity and readiness contracts; amendments to CPD-0005

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the discovery and acquisition-readiness run (2026-10-07), which ordered CPD-0004 and CPD-0005 to be audited and amended forward-only where evidence requires, the discovery, transport, policy and readiness layers to be decided and built, and authorised that run to take the technical decisions. Recorded by that run; subject to the operator's review. |
| Kind | architecture |
| Scope | the fetch-record amendments; discovery; the HTTP fetcher; crawler identity; the policy gate and robots evidence; the HTTP acquisition run; preservation-target readiness; the capacity model; the acquisition baseline manifest |
| Builds on / amends / supersedes | builds on CPD-0001 to CPD-0005. **Amends CPD-0005** in three points (§1 below); settles its "Not decided here" item on stored body bytes. Confirms CPD-0004 unchanged. |
| Does not change | the acquisition policy itself, the crawler's public identity values, the preservation target, the registration of any outlet — all remain operator decisions (master plan O-1, O-2, O-3, O-11) |
| Run report | [`docs/agent-runs/2026-10-07_discovery-acquisition-readiness-offline-e2e.md`](../agent-runs/2026-10-07_discovery-acquisition-readiness-offline-e2e.md) |
| Evidence | the audit of §0; `tests/test_discovery.py`, `test_fetcher.py`, `test_policy.py`, `test_warc_interoperability.py`, `test_readiness.py`, `test_offline_e2e.py`; the registry proposal of 2026-10-07 (channel hosts off the outlet's origin); [`docs/legacy/ARCHAEOLOGY.md`](../legacy/ARCHAEOLOGY.md) F-9, F-10, F-12 |

Validation debt: everything here has run against a server on a loopback address and synthetic
documents only. No real outlet, no TLS connection, no real preservation target. Listed in
`docs/STATUS.md` §6.

## 0. Audit of CPD-0004 and CPD-0005

Before anything was built on them, both decisions were held against the code, the tests, the
legacy archaeology, the real registry proposal and the CO.RA.PAN 3.0 principles.

| Examined | Finding | Outcome |
|---|---|---|
| CPD-0004, all dispositions | no disposition contradicted by the discovery or transport work; the feed score, crawl loop and `article_id` stay discarded | **KEEP**, unchanged |
| identity: tracking parameters, AMP / mobile / print, redirects, missing canonical, same URL / new text, other URL / same body, moved content | each case is covered by a test and behaves as CPD-0005 §4 says | **KEEP** |
| identity: canonical across origins | an off-origin canonical is ignored for the key and kept in the observation — right for syndicated copy; now covered by a test | **KEEP** |
| identity: **many pages declaring one canonical** (a section or home page) | a real template defect class. The rule files them as one document with many "versions", and nothing recorded made that visible | **AMEND** (§1.3): each observation keeps the fetch's own URL keys; a collapse can be listed |
| identity: what may become a document | a feed or a robots file would have become a "document" | **AMEND** (§1.1): `fetch_kind` |
| pack: one per outlet and UTC day; append / seal; derived index; crash recovery; promotion; replay | no evidence against any of it; channel documents and robots files go into the same pack as the outlet's items of that day | **KEEP** |
| pack: digest semantics | "the body" was not pinned down for a real transport (CPD-0005 left it open) | **AMEND** (§1.2): what the body is |
| pack: interoperability | unverified until this run | verified for the written subset with warcio 1.7.5; one header-rendering rule added (§1.2) |

No fetch record, pack, id or document existed for corpus material, so the amendments rewrite
nothing.

## Context

CPD-0005 fixed the records from fetch to document version for *recorded* exchanges. Missing were
the two stages in front of them, and everything that decides whether a request may be made at
all. The legacy system shows the cost of leaving that implicit: a robots setting that was
configured and never enforced (F-10), a placeholder contact address sent for months, feeds
deactivated by a loop nobody could audit (F-9).

## Decision

### 1. Amendments to the fetch record and to identity (CPD-0005 §3–§4)

1. **`fetch_kind`**: `item` · `channel_document` · `robots_txt`. Only an `item` can become a
   document. A channel document is the preserved evidence of discovery; a robots file the
   preserved evidence of a policy decision. The record also carries `request_id`,
   `attempt_number`, `failure_detail`, `response.redirect_not_followed`,
   `response.content_encoding`, and a complete `policy` block (`policy_decision`,
   `policy_version`, `robots_decision`, `robots_txt_sha256`, `access_class_observed`,
   `crawler_version`, `user_agent`). **A fetch record of an HTTP run without a complete policy
   block cannot be built**; for a replay every policy field is `not_applicable`.
2. **The stored body is the HTTP payload as the server sent it: content coding intact, transfer
   coding removed.** `body_sha256` covers exactly those bytes. Undoing `gzip` / `deflate` is a
   recorded step of the stages that read a body (identity's head scan, discovery, extraction);
   an unknown or undecodable coding is a label (`NOT_EXTRACTABLE`), not an error and not a guess.
   In a pack's rendered HTTP header block a `Transfer-Encoding` header is written as
   `X-Coprepan-Orig-Transfer-Encoding`, because the stored bytes are not chunked; the fetch
   record keeps the header as received.
3. **Each identity observation keeps `requested_url_key` and `final_url_key`** beside the chosen
   key. `canonical_collapse_suspects()` lists documents whose key came from `rel=canonical` while
   their fetches were answered at several different final URLs. It is a diagnosis for review: it
   changes no id. Correcting a collapse is an outlet rule with a new version.

### 2. Discovery

- Discovery turns a **channel document** into evidence and nothing else: it fetches nothing,
  preserves nothing, creates no document.
- Three append-only tables: **inputs** (one row per channel document read, or not readable, with
  its parse outcome), **discovery events** (one row per listed URL: channel, input document,
  position, the URL as written and as resolved, hints, parser version), **candidates** (one row
  per canonical URL key that has been listed).
- `event_id` = `de1:` + 32 hex over (channel, input fetch id, position, URL as written).
  `candidate_id` = `{outlet_id}:cand:` + 16 hex over the canonical URL key.
- A candidate is a URL worth planning a fetch for. It is not an article. The same URL listed
  twice, in one document or by two channels, is several events and one candidate.
- Formats: RSS 0.9x / 1.0 / 2.0, Atom, sitemap `urlset`, sitemap index, HTML listing. **The bytes
  decide the format, not the declared content type.** In a sitemap only `<loc>` directly under
  `<url>` / `<sitemap>` counts: image and video locations are not candidates. XML with a DTD or
  an entity declaration is refused.
- A hint (title, dates, guid) is stored as written and interpreted by nobody. A redirect of the
  channel document changes what relative links resolve against and rewrites no listed URL.
- **Expansion is bounded.** A sitemap index and `rel=next` pagination are followed breadth-first
  under a budget of depth, documents, candidates and bytes — all four required, none with a
  default. A cycle or a repeat is recorded and not followed. A stop names the limit that caused it.
- An unparseable or unavailable channel document is a recorded input with its reason and yields
  no candidate: half a feed is not a feed.

### 3. HTTP transport

- Standard library `http.client`; no hidden retry, redirect or decoding. One request at a time.
- **Policy before transport**: every request — each redirect hop and the robots file included —
  is put to the policy gate before a connection is opened. A denied intent makes no transport
  call. A redirect to a place the gate does not allow is not followed; the redirect answer itself
  is the fetched response, with the reason recorded.
- One fetch record **per attempt**. An error page is evidence and is preserved.
- A body cut short, or longer than the limit, is a failed fetch, never a shorter body.
- **Retry semantics.** Retried: `timeout`, `connection_error`, `incomplete_response`, and the
  statuses 429, 500, 502, 503, 504. Not retried: every other status, a malformed response, an
  exceeded limit. Wait = max(base · 2^(n−1) capped, `Retry-After`); no jitter. A `Retry-After`
  beyond the cap ends the attempts and records when a later run may try. All limits (timeout,
  redirects, body size, attempts, backoff) are required inputs with no built-in value. Clock and
  sleep are injected.
- Pace: the policy's minimum interval per origin.
- `request_id` = `rq1:` + 32 hex over (URL, outlet, kind, channel, planned-at).

### 4. Crawler identity (the technical side of O-2)

- Four things kept apart: **software identity** (package and fetcher version), **operator
  identity** (crawler name, organisation, contact URL, contact e-mail), the **`User-Agent`**
  (derived: `<crawler_name>/<package version> (+<contact_url>; <contact_email>)`), and the
  **acquisition run** (recorded per fetch, never sent).
- The operator identity is tracked configuration (`config/crawler_identity.json`): it is public
  by nature and belongs to the baseline. It ships `not_configured`. **There is no built-in
  identity**; reserved and placeholder domains are refused.
- A loopback test identity exists, says what it is, and can reach literal loopback addresses only.

### 5. Policy gate (the technical side of O-1)

- `fetch intent → ALLOW | DENY | DEFER` with reasons and evidence. **Nothing is allowed by
  default.** The first refusal ends the evaluation.
- The policy is tracked configuration (`config/acquisition_policy.json`). It ships `NOT_DECIDED`
  with every normative value `not_decided`; under it every external request is denied. A policy
  marked `DECIDED` must have decided everything it will be asked, or it does not load.
- Order of evaluation: policy decided and scope matching the identity → outlet registered and
  the URL on an origin the registry knows (an item on the outlet's web origins; a channel
  document or robots file also on the host of a registered channel) → operator switches
  (disabled outlets and channels) → explicit opt-outs → temporary suppressions (`DEFER` until
  they end) → a configured pace → robots evidence.
- **robots.txt is evidence, not the policy.** It is parsed as RFC 9309 says, fetched through the
  same gate, preserved as a fetch, and weighed as the policy states (`enforce` / `record_only`;
  what an absent or unreachable file means). The answer and the file's hash are recorded with
  every fetch. Nothing here is a legal reading, and robots alone settles no text-and-data-mining
  question. `Crawl-delay` is recorded and not interpreted.

### 6. HTTP acquisition run

- `registered channel → gate → channel document → discovery → candidate → gate → item fetch →
  fetch record → pack → ledger`, then the existing seal, promotion, identity and extraction.
- A **request log** row is written before each request and another when it has ended; a planned
  request without an end is an interrupted one — visible, kept, and repeatable.
- A candidate that has been answered is not requested again until a re-fetch schedule exists.
- Run kind `http_fetch`; the run identity covers the crawler identity and the limits.

### 7. Preservation-target readiness (the technical side of O-3)

A target is ready when it is a usable, reachable root; has an **identity** (a marker written once
when the operator takes it into service); is writable; supports the promotion sequence (stage,
flush, hash, atomic rename, re-read; no silent overwrite); has at least the required free space;
and what it holds verifies against its manifests. The check writes a few hundred bytes into a
directory of its own and removes exactly those.

### 8. Capacity model (the technical side of O-4)

A calculator in which every input is labelled `measured`, `estimated` or `assumed` with its
source, and every output carries the weakest label beneath it. No built-in values.

### 9. Acquisition baseline manifest

One hashed manifest of what an acquisition start rests on: registry, policy, crawler identity,
configuration, code commit, decisions, schema ids, component versions, storage target, test
baseline. States `PRE_FREEZE` (with the list of what blocks) → `READY_TO_FREEZE` → `FROZEN`; the
last only by an operator act that states the manifest's digest, and never while anything blocks.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Store the body decoded | The digest would cover bytes the server never sent; a decoder change would change the "raw" object. |
| Store wire bytes including chunk framing | The framing is a property of one connection, not of the representation; two fetches of the same page would differ byte-wise for no reason. |
| A third-party HTTP client | Its retry, redirect and decoding defaults would be behaviour nobody decided. The legacy client retried and followed redirects silently and recorded neither. |
| Trusting the declared content type in discovery | A feed served as `text/html` would be read as a page with no links, and a page served as XML refused as invalid XML — both silently yielding nothing. The bytes are unambiguous where the header is not. (How often real outlets do this is not measured.) |
| Treating `rel=canonical` as untrusted and keying on the final URL only | It would split one article into its tracking and platform variants on outlets that declare canonicals correctly — the larger and better-evidenced problem. The collapse case is made detectable instead. |
| Allowing requests when no policy is decided, "for testing" | That is how a configured-but-unenforced policy comes about. Tests have their own, visibly different, loopback-only policy. |
| A default `User-Agent` | Any default is an identity somebody did not choose. |
| Retrying every failure a fixed number of times | A 404 or a 403 is an answer, not a transient condition. |
| Unbounded sitemap expansion with a visited-set only | A visited set stops cycles, not a very large or adversarial index. |

## Consequences

- Stages 2 (discovery) and 3 (fetch) are `PARTIAL` in `docs/STATUS.md`: built and tested offline,
  never run against a real outlet.
- External acquisition is impossible by construction until O-1, O-2 and O-11 are answered by the
  operator — three independent refusals, each tested.
- `warcio` is pinned as a test-only dependency.

## Not decided here

- **The policy**: which robots mode binds, what an absent or unreachable robots file means, the
  pace per origin, opt-out handling, retention of raw copies (O-1).
- **The identity values** (O-2), **the preservation target** (O-3), **registration** (O-11).
- A re-fetch schedule; channel health; conditional requests; concurrency across origins.
- TLS behaviour (certificate failures, protocol versions): not exercised offline.
- Per-outlet filters on which listed URLs are worth fetching; admission labels.
- Whether robots `Sitemap:` lines feed discovery.
