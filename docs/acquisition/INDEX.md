# Acquisition — component index

**Status: BUILT AND TESTED OFFLINE; EXTERNALLY NOT ACTIVATED AND NOT ACTIVATABLE AS COMMITTED.**
Discovery, the HTTP fetcher, the policy gate, crawler identity and the acquisition run exist as
code and pass an end-to-end canary against a server on a loopback address. **Nothing has been
requested from any real site, and nothing can be: the tracked policy is `NOT_DECIDED`, the tracked
crawler identity is `not_configured`, and no outlet is registered** — three independent refusals.
Governing decisions: [CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §2–§3,
[CPD-0006](../decisions/CPD-0006_discovery-transport-policy-gate-and-readiness.md).
Current state: [`docs/STATUS.md`](../STATUS.md).

Entry point for: the acquisition run, discovery, the fetcher, the policy gate, robots evidence,
crawler identity, the fetch record, the pack. Storage roles, promotion, readiness and capacity:
[`docs/storage/INDEX.md`](../storage/INDEX.md).

---

## 1. What exists

| Thing | Code | Test |
|---|---|---|
| Acquisition run: identity, run record, result, unfinished-run listing | `src/coprepan/acquisition.py` | `tests/test_acquisition_pack.py` |
| Fetch record: builder, validator | `src/coprepan/acquisition.py` | same |
| Pack: WARC writer, scan, seal, index, manifest, fixity check, torn-tail quarantine | `src/coprepan/pack.py` | same; `tests/test_warc_interoperability.py` |
| Discovery: channel-document parsers, events, candidates, bounded expansion | `src/coprepan/discovery.py` | `tests/test_discovery.py` |
| Robots: RFC 9309 parser, evidence states | `src/coprepan/robots.py` | `tests/test_policy.py` |
| Policy gate | `src/coprepan/policy.py`, `config/acquisition_policy.json` | `tests/test_policy.py`, `tests/test_fetcher.py` |
| Crawler identity | `src/coprepan/crawler_identity.py`, `config/crawler_identity.json` | `tests/test_policy.py` |
| HTTP fetcher | `src/coprepan/fetcher.py` | `tests/test_fetcher.py` (real HTTP on loopback) |
| HTTP acquisition run, request log | `src/coprepan/http_acquisition.py` | `tests/test_offline_e2e.py` |
| Recorded-exchange acquisition; seal → promotion → `RAW_PRESERVED` | `src/coprepan/core_pipeline.py` | `tests/test_core_pipeline.py` |

## 2. The path of a request

```text
registered channel ──► policy gate ──► fetch channel document ──► discovery ──► candidate
                                                                                    │
                    candidate ──► policy gate ──► fetch item ──► fetch record ──► open pack ──► ledger
```

then seal, promotion, identity and extraction ([storage](../storage/INDEX.md),
[identity](../identity/INDEX.md), [extraction](../extraction/INDEX.md)).

Workspace layout written by a run:

| Path | Content |
|---|---|
| `runs/<run_id>/run.json`, `result.json` | run record and result, each written once |
| `requests/requests.jsonl` | `PLANNED` and `FINISHED` rows per request (`coprepan-request-log/v1`) |
| `discovery/inputs.jsonl`, `events.jsonl`, `candidates.jsonl` | discovery evidence |
| `packs/<pack_id>.warc.gz(.open)`, `.index.jsonl`, `.pack.json` | the pack |
| `ledgers/preservation.jsonl` | state of every fetch |

## 3. Run

`run_id` = `acq1-<UTC start>-<hash12>`. Kinds: `recorded_replay`, `http_fetch`. A run directory
without `result.json` is an interrupted or running run and can be resumed; a planned request
without a `FINISHED` row is an interrupted request and stays on record.

## 4. Fetch record (`coprepan-fetch-record/v1`)

| Field | Content |
|---|---|
| `fetch_id` | CPD-0003: over requested URL, start instant, body hash |
| `run_id`, `outlet_id` | the run and the registered outlet |
| `fetch_kind` | `item` · `channel_document` · `robots_txt` — only an `item` can become a document |
| `request_id`, `attempt_number` | which request, which attempt (one record per attempt) |
| `outcome` | `FETCHED` (a complete response came back, any status) · `FETCH_FAILED` |
| `failure_reason`, `failure_detail` | `timeout` · `connection_error` · `incomplete_response` · `malformed_response` · `body_limit_exceeded` · `redirect_limit_exceeded` · `unknown` |
| `request` | `method`, `requested_url` (as requested), `headers` |
| `response` | `status`, `final_url`, `redirect_chain`, `redirect_not_followed`, `headers` (ordered pairs, repetitions kept), `content_type`, `content_encoding` |
| `fetch_started_at`, `fetch_finished_at` | UTC instants, microseconds |
| `body_sha256`, `body_size_bytes` | of the stored body: the HTTP payload, content coding intact, transfer coding removed |
| `discovery` | `channel_id`, or `unknown` |
| `policy` | `policy_decision`, `policy_version`, `robots_decision`, `robots_txt_sha256`, `access_class_observed`, `crawler_version`, `user_agent` — all required for an HTTP run, all `not_applicable` for a replay |

## 5. Discovery

Formats: RSS, Atom, sitemap `urlset`, sitemap index, HTML listing. Contract and rules:
CPD-0006 §2.

| Table | Row |
|---|---|
| `inputs` (`coprepan-discovery-input/v1`) | run, channel, document URL, input fetch id, depth, parent, format, outcome (`PARSED` · `UNPARSEABLE` · `UNAVAILABLE`), problems, body hash |
| `events` (`coprepan-discovery-event/v1`) | `event_id`, run, channel, outlet, input fetch id, position, relation (`item` · `child_document` · `next_page`), URL as written and as resolved, hints, problem, `url_key`, `candidate_id`, parser |
| `candidates` (`coprepan-discovery-candidate/v1`) | `candidate_id`, outlet, `url_key`, `fetch_url`, first event, first channel |

Budget (`DiscoveryBudget`): `max_depth`, `max_documents`, `max_candidates`, `max_bytes` — all
required. Problems an entry can carry: `no_link`, `not_http`, `invalid_url`, `off_origin`,
`candidate_budget_exhausted`.

## 6. Policy gate, robots, identity

- **Gate** (CPD-0006 §5): `ALLOW` / `DENY` / `DEFER`, never allow-by-default. Refusal reasons
  include `policy_not_decided`, `external_acquisition_disabled`,
  `identity_scope_does_not_match_policy_scope`, `outlet_not_registered`, `off_origin`,
  `channel_not_registered`, `outlet_disabled`, `channel_disabled`, `explicit_opt_out`,
  `temporarily_suppressed` (defer), `rate_limit_not_configured`, `robots_not_consulted` (defer),
  `robots_absent`, `robots_unreachable`, `robots_disallow`.
- **Robots** is evidence: `fetched` / `absent` (4xx) / `unreachable` (5xx, failure) /
  `not_consulted`. The policy says what each means.
- **Identity** (CPD-0006 §4): software, operator, `User-Agent` and run are separate. No default.
- **To activate** (operator, not an agent): decide and commit the policy; fill and commit the
  identity; register outlets. Each is its own reviewed change with its own record.

## 7. Fetcher

`http.client`; `FetchLimits` (timeout, redirects, body bytes, attempts, backoff base and cap) all
required; clock and sleep injected. Retry and redirect semantics: CPD-0006 §3.

## 8. Rules

- No request without an `ALLOW` from the gate, recorded with the fetch. No fetch without a
  registered outlet.
- The ledger is written before a state is claimed; the request log before a request is made.
- A fetch is whole or absent in a pack. Interrupted bytes are quarantined, never dropped.
- A sealed pack is never appended to and never rewritten.
- Everything a server sent is preserved: error pages, robots files, the answers of failed
  attempts. Nothing is discarded at acquisition time.
- Discovery creates no document. A candidate is not an article.
- A test reaches at most a literal loopback address (`AGENTS.md` §7).

## 9. Open

| Item | Kind | Where |
|---|---|---|
| The acquisition policy | institutional | master plan §13, O-1 |
| The crawler's public identity values | operator | O-2 |
| Registration of outlets | operator, scientific | O-11 |
| Behaviour against real outlets: TLS, real redirects, real feeds, bot protection | validation debt | STATUS §6; Phase-2 canary |
| Re-fetch schedule; channel health; conditional requests | technical, Phase 2 | master plan §11 |
| Which listed URLs are worth fetching (per-outlet filters); robots `Sitemap:` lines as a discovery source | technical | CPD-0006, "Not decided here" |
| Pack rollover by size; `revisit` records; another codec | technical | storage §3 |

## 10. Milestones

- 2026-10-07 — run, fetch record and pack contracts decided (CPD-0005), implemented and tested on
  recorded exchanges of synthetic fixtures. No network code.
- 2026-10-07 — discovery, fetcher, policy gate, crawler identity, HTTP acquisition run decided
  (CPD-0006) and built; offline end-to-end canary with failure injection against a loopback
  server; pack read by an independent WARC reader. External acquisition not activated.
