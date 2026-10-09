# Acquisition — component index

**Status: BUILT AND TESTED OFFLINE; EXTERNALLY NOT ACTIVATED AND NOT ACTIVATABLE AS COMMITTED.**
Discovery, the HTTP fetcher, the policy gate, crawler identity and the acquisition run exist as
code and pass an end-to-end canary against a server on a loopback address. **Nothing has been
requested from any real site, and nothing can be as committed: the tracked policy — decided for
the first canary on 2026-10-08 ([CPD-0013](../decisions/CPD-0013_canary-registration-and-canary-acquisition-policy.md)),
with the schedule policy and five registered outlets — has `external_acquisition: disabled` until
the canary is armed. The crawler identity is configured and its public page is live
([CPD-0014](../decisions/CPD-0014_crawler-identity-and-storage-roles-with-interim-preservation.md)).**
Governing decisions: [CPD-0005](../decisions/CPD-0005_core-pipeline-contracts.md) §2–§3,
[CPD-0006](../decisions/CPD-0006_discovery-transport-policy-gate-and-readiness.md),
[CPD-0007](../decisions/CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md) §2–§7, §11.
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
| HTTP acquisition run, request log | `src/coprepan/http_acquisition.py` | `tests/test_offline_e2e.py`, `tests/test_refetch_e2e.py` |
| Candidate qualification | `src/coprepan/candidate_filter.py`, `config/candidate_rules.json` | `tests/test_schedule.py` |
| Candidate lifecycle and fetch plan | `src/coprepan/schedule.py`, `config/schedule_policy.json` | `tests/test_schedule.py`, `tests/test_refetch_e2e.py` |
| Channel health | `src/coprepan/channel_health.py` | `tests/test_schedule.py`, `tests/test_refetch_e2e.py` |
| Canary planner and preflight | `src/coprepan/canary.py` | `tests/test_canary.py` |
| Recorded-exchange acquisition; seal → promotion → `RAW_PRESERVED` | `src/coprepan/core_pipeline.py` | `tests/test_core_pipeline.py` |

## 2. The path of a request

```text
registered channel ──► policy gate ──► fetch channel document ──► discovery ──► candidate
                                                                                    │
     candidate ──► qualification ──► fetch plan (due?) ──► policy gate ──► fetch item
                                                               ──► fetch record ──► open pack ──► ledger
```

then seal, promotion, identity and extraction ([storage](../storage/INDEX.md),
[identity](../identity/INDEX.md), [extraction](../extraction/INDEX.md)).

Workspace layout written by a run:

| Path | Content |
|---|---|
| `runs/<run_id>/run.json`, `result.json` | run record and result, each written once |
| `requests/requests.jsonl` | `PLANNED` and `FINISHED` rows per request (`coprepan-request-log/v2`, **chained**) |
| `discovery/inputs.jsonl`, `events.jsonl`, `candidates.jsonl` | discovery evidence |
| `discovery/qualifications.jsonl` | one decision per candidate and rule set (`coprepan-candidate-qualification/v2`, **chained**) |
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
| `response` | `status`, `final_url`, `redirect_chain`, `redirect_statuses` *(CPD-0007 §5)*, `redirect_not_followed`, `headers` (ordered pairs, repetitions kept), `content_type`, `content_encoding` |
| `revalidates` *(CPD-0007 §4)* | `{fetch_id, body_sha256}` on an empty 304 that answered a conditional request; otherwise `not_applicable` |
| `fetch_started_at`, `fetch_finished_at` | UTC instants, microseconds |
| `body_sha256`, `body_size_bytes` | of the stored body: the HTTP payload, content coding intact, transfer coding removed |
| `discovery` | `channel_id`, or `unknown` |
| `policy` | `policy_decision`, `policy_version`, `robots_decision`, `robots_txt_sha256`, `access_class_observed`, `crawler_version`, `user_agent` — all required for an HTTP run, all `not_applicable` for a replay |

## 5. Discovery

Formats: RSS, Atom, sitemap `urlset`, sitemap index, HTML listing. Contract and rules:
CPD-0006 §2.

| Table | Row |
|---|---|
| `inputs` (`coprepan-discovery-input/v2`, **chained**) | run, channel, document URL, input fetch id, depth, parent, format, outcome (`PARSED` · `UNPARSEABLE` · `UNAVAILABLE`), problems, body hash |
| `events` (`coprepan-discovery-event/v2`, **chained**) | `event_id`, run, channel, outlet, input fetch id, position, relation (`item` · `child_document` · `next_page`), URL as written and as resolved, hints, problem, `url_key`, `candidate_id`, parser |
| `candidates` (`coprepan-discovery-candidate/v1`, **derived** from events and request log) | `candidate_id`, outlet, `url_key`, `fetch_url`, first event, first channel |

Budget (`DiscoveryBudget`): `max_depth`, `max_documents`, `max_candidates`, `max_bytes` — all
required. Problems an entry can carry: `no_link`, `not_http`, `invalid_url`, `off_origin`,
`candidate_budget_exhausted`.

## 6. Policy gate, robots, identity

- **Gate** (CPD-0006 §5): `ALLOW` / `DENY` / `DEFER`, never allow-by-default. Refusal reasons
  include `policy_not_decided`, `external_acquisition_disabled`,
  `identity_scope_does_not_match_policy_scope`, `outlet_not_registered`, `off_origin`,
  `channel_not_registered`, `outlet_disabled`, `channel_disabled`, `explicit_opt_out`,
  `temporarily_suppressed` (defer), `rate_limit_not_configured`, `robots_not_consulted` (defer),
  `robots_absent`, `robots_unreachable`, `robots_disallow`, `robots_crawl_delay_exceeds_limit`.
- **`Crawl-delay`** (policy schema `v2`, CPD-0013 §5): always recorded as written. Under
  `rate_limit.crawl_delay: binding_minimum` an unambiguous non-negative decimal number is the
  minimum pause for its origin (the crawler's own line wins over `*`; never shorter than the
  policy's own minimum), and an origin that asks for more than `crawl_delay_max_seconds` is not
  fetched. Under `record_only` nothing is applied.
- **The tracked policy** is the canary policy `canary/2026-10-08.1`: robots enforced, absent
  allows, unreachable defers, `Crawl-delay` binding up to 60 s, 10 s per origin, two comment feeds
  disabled. It is for one bounded canary and not for scheduled crawling.
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
- *Added 2026-10-08 (CPD-0009).* **A request is at-least-once; its evidence is never doubled.**
  A process that dies between the intent and the end of a request leaves `PLANNED` without
  `FINISHED`: the request may or may not have been sent, and a response that came back may be
  lost with the process. The candidate is asked again; the second answer is a second fetch.
- *Added 2026-10-08.* One process writes a workspace at a time (`WorkspaceBusy` otherwise). After
  an interruption: `recovery.diagnose`, `recovery.repair`, then the same call again
  ([storage](../storage/INDEX.md) §17).

## 9. Open

| Item | Kind | Where |
|---|---|---|
| The acquisition policy | institutional | master plan §13, O-1 |
| The crawler's public identity values | operator | O-2 |
| Registration of outlets | operator, scientific | O-11 |
| Behaviour against real outlets: TLS, real redirects, real feeds, bot protection | validation debt | STATUS §6; Phase-2 canary |
| The schedule policy: every interval and limit of re-fetching; whether `Crawl-delay` binds | institutional, part of O-1 | §11; CPD-0007 §3, §6 |
| Outlet rules for candidate qualification; whether an outlet's robots sitemaps are read | registry content, by review | §11; O-11 |
| Channel-health thresholds; any consequence of a health state | operator | §11 |
| The canary's outlets, limits and budget | operator | §12 |
| Pack rollover by size; `revisit` records for 304 answers; another codec | technical | storage §3 |

## 10. Milestones

- 2026-10-07 — run, fetch record and pack contracts decided (CPD-0005), implemented and tested on
  recorded exchanges of synthetic fixtures. No network code.
- 2026-10-07 — discovery, fetcher, policy gate, crawler identity, HTTP acquisition run decided
  (CPD-0006) and built; offline end-to-end canary with failure injection against a loopback
  server; pack read by an independent WARC reader. External acquisition not activated.
- 2026-10-07 — candidate qualification, candidate lifecycle and fetch plan, conditional requests,
  permanent-redirect handling, robots sitemaps and crawl-delay evidence, channel health, canary
  planner and preflight decided (CPD-0007) and built; re-fetching exercised end to end against a
  loopback server. External acquisition not activated.

- 2026-10-08 — operation semantics decided and tested with real process kills (CPD-0009): a
  request is at-least-once, a response is recorded under one fetch id or not at all, an intent
  without an end stays on record; a 304 is believed only for a preserved body; a conditional
  request is sent only for a preserved body; one writer per workspace.

## 11. Qualification, schedule, conditional requests, redirects, health (CPD-0007)

**Qualification** — per candidate `QUALIFIED` / `REJECTED` / `DEFERRED` with reasons and rule set.
Generic rule set `candidate-filter-generic/1`: `site_root`, asset and binary-document extensions,
channel-document extensions, a URL that is a registered channel. Outlet rules
(`config/candidate_rules.json`, schema `coprepan-candidate-rules/v1`): `version`,
`reject_path_prefixes`, `reject_path_patterns`, `allow_path_patterns` — **none is tracked**. An
allow and a reject rule on the same URL give `DEFERRED` (`conflicting_rules`). A rejected
candidate stays in the tables; a new rule version adds a decision beside the old one.

**Lifecycle** — derived from the request log, never stored (`schedule.lifecycle`, `schedule.plan`):

| State | Meaning | Due again |
|---|---|---|
| `NEVER_FETCHED` | listed, never requested | at once |
| `FETCHED` | last answer 2xx, or a 304 that revalidated | after the revisit interval (longer for each unchanged answer) |
| `SETTLED` | revisit window closed | never |
| `FAILING` | transport failure, 429, 5xx, a 304 nobody asked for | after the failure backoff; never before a `Retry-After` |
| `SUSPENDED` | *n* failures in a row | after the cooldown |
| `ABSENT` | 404 or 410 | after the recheck interval |
| `RETIRED` | absent on *n* rechecks | never |
| `REFUSED` | other 4xx; a redirect that was not followed | after the recheck interval |
| `DENIED` | the policy gate said `DENY` | at once under a new policy version, otherwise after the recheck interval |
| `DEFERRED` | the policy gate said `DEFER` | when the deferral ends |
| `MOVED` | permanently redirected to another URL of the outlet | never; the target is its own candidate |

Every interval and *n* is a field of the schedule policy (`coprepan-schedule-policy/v1`); the
tracked file is the canary policy `canary/2026-10-08.1` (CPD-0013 §4): a day before any revisit,
an hour after a transient failure, three failures and a week's rest, one recheck of an absent URL. The plan is a pure function
of history, policy and instant: `fetch-planner/1`.

**Request log** — a `FINISHED` row also carries `result` (status, final URL, redirect statuses,
`etag`, `last_modified`, `body_sha256`, `revalidates`, `moved_permanently_to`) and
`policy_hints.robots_crawl_delay`. A permanent redirect adds a second `FINISHED` row for the
target candidate (`attributed_from`).

**Conditional requests** — validators of the last body held are sent on the first hop only. A 304
is a fetch with an empty body and `revalidates`; no body is invented. A 200 is judged by its body
hash whatever its `ETag`. Switchable in the schedule policy.

**Robots** — `use_robots_sitemaps=True` reads the sitemaps a robots file names under the reserved
source `<outlet>:ch:robots_sitemaps`, through the same gate and budget; off by default.
`Crawl-delay` is recorded and applied by nothing.

**Channel health** (`channel-health/1`) — `HEALTHY` · `DEGRADED` · `STALE` · `FAILING` ·
`DISABLED` · `UNKNOWN`, read from the discovery tables with the evidence; thresholds are inputs.
It replaces §8 of the corpus-supply model's stored state. It switches nothing on or off.

## 12. Canary planner and preflight (CPD-0007 §11)

```text
python -m coprepan.canary plan --outlets 5 --seed <seed>     # a proposal for review
python -m coprepan.canary preflight --outlet <id> … --commit <hash> --tests-passed <n> \
       --tests-commit <hash> --approved-baseline <file> --required-free-bytes <n>
```

Neither makes a request. The plan picks registered outlets for diversity of country, outlet type
and channel kind and says why; it does not know which outlet is a sensible first target. The
preflight checks O-11, O-1 (acquisition and schedule policy), O-2, O-3 (target `READY`, runtime
workspace), the suite green on this commit, and no drift against the baseline manifest the
operator approved; exit code 1 until `READY`. O-4 is not a precondition.

On the repository as committed (measured 2026-10-07): the plan selects 0 outlets — all 82 are
ineligible (not registered; placeholder URL rules; no time zone; some without a channel) — and
the preflight is `NOT_READY` on every check.
- 2026-10-08 — the request log and the discovery inputs and events are chained and anchored at run
  close; the candidate table is derived state, checked against them and completable from them
  (CPD-0010). A run refuses to start on a request log or discovery table that does not
  authenticate, before the first request.

## 13. The findings of the first canary, repaired (CPD-0019, 2026-10-09)

What §1–§12 say stands, with these changes. Each is tested in `tests/test_canary_findings.py`; none has met a real server yet.

| Finding | Now |
|---|---|
| F1 robots file served gzip-coded | the content coding is undone for parsing; the preserved bytes and the digest are the bytes as received; an undecodable body is a parse error, on which the policy holds (`robots-parser/3`) |
| F2 Sucuri challenge (307 without `Location`) | recognised as `bot_challenge`; a small body is inspected whatever its status; the origin is held; a canary re-derives holds from the stored answers under the current classifier (`access-control/2`) |
| F3 foreign candidates | a run qualifies, schedules and requests only the candidates of its own outlet |
| F4 budget and sitemap index | requests are counted hop by hop; three of an outlet's eight non-item requests are reserved for the documents a channel names; children of an index are read by `expansion-order/1` (news first, newest `lastmod` first, taxonomies last); `max_documents` bounds the documents asked for; a canary has the budget of its baseline |
| F5 `<!DOCTYPE` in CDATA | the declaration guard reads markup only; a real declaration is refused as before (`channel-parser/2`) |
| F6 404 channel | disabled in the policy (`canary/2026-10-09.1`); no other address of that origin was added |
| F7 candidate budget | measured by `discovery_coverage` (what a pass listed, kept, turned away; the frontier of an index); the limit is unchanged |

- **Discovery budget semantics.** `documents_asked` counts every document the provider was asked for; `not_read` lists what a pass named and did not ask for, with the limit that was the reason.
- **Listing channels.** A channel of kind `archive` or `section_page` is read by a canary only for an outlet whose reviewed candidate rules carry an allow pattern; the driver now passes the outlet rules of `config/candidate_rules.json` to qualification.
- **Three levels, in this order of preference** (the brief of 2026-10-09): generic parsers (RSS, Atom, sitemap, sitemap index, HTML listing); configurable source rules (origins, channels, candidate rules, disabled channels — registry and policy); a source-specific adapter only where a proven structure defeats both. **No adapter exists**: nothing observed so far needs one. An adapter, when one is needed, is a discovery provider — it turns preserved bytes into channel entries, makes no request of its own and extracts no text.
- **Replay.** `scripts/replay_canary_findings.py` reads the preserved answers of a workspace again under the current code and writes what the parsers and the classifier make of them (`config/source_discovery/canary_replay_2026-10-09.json`): reproducibility of a repair, no new observation.
- Run report: [`2026-10-09`](../agent-runs/2026-10-09_discovery-source-recovery-and-acquisition-qualification.md).
