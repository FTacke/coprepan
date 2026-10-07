# CPD-0007 — Re-fetching, candidate qualification, admission labels, channel health, and the instruments for the canary and for Phase 3

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the pre-canary completion run (2026-10-07), which ordered these layers to be decided and built, gave the go-ahead for the legacy freeze manifest (O-10), and authorised that run to take the technical decisions. Recorded by that run; subject to the operator's review. |
| Kind | architecture |
| Scope | the legacy freeze manifest; candidate qualification; the candidate lifecycle and the fetch plan; conditional requests; permanent redirects; robots `Sitemap:` and `Crawl-delay`; channel health; admission labels; the extractor lifecycle; the extraction evaluation harness and review package; the canary planner and preflight |
| Builds on / amends / supersedes | builds on CPD-0001 to CPD-0006. Settles two "Not decided here" items of CPD-0006 (which listed URLs are worth fetching; robots `Sitemap:` lines). Extends the fetch record of CPD-0005 §3 / CPD-0006 §1 by two fields (§4, §5), forward-only: no fetch record of corpus material exists. |
| Does not change | the acquisition policy, the schedule values, the crawler identity values, the preservation target, the registration of any outlet, the adoption of any extractor — all remain operator or scientific decisions (O-1, O-2, O-3, O-11, Phase 3) |
| Run report | [`docs/agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md`](../agent-runs/2026-10-07_pre-canary-completion-legacy-freeze-phase3-readiness.md) |
| Evidence | `tests/test_legacy_freeze.py`, `test_schedule.py`, `test_admission_eval.py`, `test_refetch_e2e.py`, `test_canary.py`; the freeze manifest under `docs/legacy/freeze/coprepan-legacy-2026-06/`; [`docs/legacy/ARCHAEOLOGY.md`](../legacy/ARCHAEOLOGY.md) F-1, F-8, F-9, F-10, F-13, F-16 |

Validation debt: everything except §1 has run against a server on a loopback address and
synthetic documents only. §1 ran on the real legacy tree. Listed in `docs/STATUS.md` §6.

## Context

After CPD-0006 the path from a channel to a document version existed for *one* visit. Everything
that makes acquisition a continuing activity was open: whether a listed URL is worth requesting,
when it is requested again, what an unchanged answer is, what a moved URL becomes, how a channel's
condition is known. So was everything Phase 3 needs before it can measure anything: a label that
says whether a fetch is technically usable, and an instrument that can compare extractors. And the
legacy corpus, the only press data the project has, had no manifest.

The legacy system is the evidence for how these go wrong when they are implicit: a stored feed
rule that switched healthy feeds off for good and never retried a failed URL (F-9), a once-only
fetch that made every later change of a page invisible (F-8), admission decided at crawl time
with the rejected rows never exported (F-13, F-16).

## Decision

### 1. Legacy freeze manifest (`coprepan-legacy-freeze-manifest/v1`)

The manifest of freeze `coprepan-legacy-2026-06` is two files: a listing (`files.jsonl`: relative
POSIX path, size, SHA-256, one row per file, sorted) and a manifest that binds the listing by its
hash and carries freeze id, creation instant, tool version, totals, the legacy git head and the
hash of its `git status`. **Fixity is bytes only**: no modification time enters a hash, so a
timestamp-only change is not a difference. `.git/` is outside the listing — git may rewrite its
own index — and is bound through the head commit and the status hash instead. A symbolic link is
refused, not followed.

State `MANIFEST_ONLY`: a manifest is evidence of what the tree was. It is **not** a preserved
copy and not a restore check; the release is complete only with those (legacy index §5), and they
need O-3.

### 2. Candidate qualification (`coprepan-candidate-qualification/v1`)

Between discovery and fetch stands a decision per candidate: `QUALIFIED` · `REJECTED` ·
`DEFERRED`.

- Rules are versioned. The generic rule set (`candidate-filter-generic/1`) rejects only what is
  not a page by its URL alone: the site root, asset and binary-document extensions, channel
  documents, a URL that is itself a registered channel. Outlet rules
  (`config/candidate_rules.json`) are path prefixes and patterns with their own version; the
  tracked file holds **none** — writing a rule about a real outlet without having seen it would be
  a guess.
- A decision is a row with its reasons and its rule set, appended to a table keyed by candidate
  and rule set. A new rule version is a new decision beside the old one. **A rejected candidate
  stays a candidate**; its discovery events are untouched. Nothing is deleted.
- An allow rule and a reject rule matching the same URL give `DEFERRED` with `conflicting_rules`:
  a contradiction is reported, not resolved by rule order.
- Qualification decides whether a URL is *requested*. It says nothing about what the page is.

### 3. Candidate lifecycle and fetch plan (`fetch-planner/1`)

Four things are kept apart: the **fetch history** (request log and fetch records, append-only),
the **candidate lifecycle** (derived from the history when asked, never stored), the **document
versions** (identity's), and the **schedule** — a pure function `(history, schedule policy, now)
→ plan`. The same history under the same policy at the same instant gives the same plan. No
daemon, no stored score, no adaptive heuristic.

| Last finished request | State | Due again |
|---|---|---|
| none | `NEVER_FETCHED` | at once |
| 2xx; or 304 to a conditional request | `FETCHED` | after the revisit interval, multiplied for each consecutive unchanged answer, capped; `SETTLED` (never) once the revisit window since the first answer has closed |
| transport failure, 429, 5xx, a 304 nobody asked for | `FAILING` | after the failure backoff, never before a `Retry-After`; after *n* in a row `SUSPENDED` until a cooldown has passed |
| 404, 410 | `ABSENT` | after the recheck interval; after *n* rechecks `RETIRED` (never) |
| other 4xx; a redirect that was not followed | `REFUSED` | after the recheck interval |
| policy `DENY` | `DENIED` | at once if the policy version has changed since, otherwise after the recheck interval |
| policy `DEFER` (suppression, robots not consulted) | `DEFERRED` | when the deferral ends |
| permanent redirect to another URL of the outlet | `MOVED` | never: the target is its own candidate |

Every interval and every *n* comes from the schedule policy (`coprepan-schedule-policy/v1`,
`config/schedule_policy.json`). **It has no built-in value and ships `NOT_DECIDED`**: how often a
publisher's pages are asked again is part of the acquisition policy (O-1). No state deletes
anything, and none is final against new evidence: a `RETIRED` or `SETTLED` candidate that a
changed policy makes due is simply due.

The request log's `FINISHED` row carries a `result` block (status, final URL, redirect statuses,
validators, body hash, what was revalidated) so that a plan needs the log alone.

### 4. Conditional requests

A revisit of a body that is held may send `If-None-Match` / `If-Modified-Since` with the
validators the server gave. Then:

- a **304** is recorded as what it is: a fetch with status 304 and an empty body, whose record
  names what it confirms — `revalidates: {fetch_id, body_sha256}`. **No body is invented and none
  is copied.** Identity files the fetch as one more observation of the existing document version
  (`url_key_basis: revalidation`); extraction does not apply.
- Only an empty 304 answering a request that carried validators may revalidate. A 304 to an
  unconditional request is a server fault: recorded, labelled, counted as a failure.
- If the revalidated fetch is unknown to the identity tables, nothing is assigned
  (`revalidation_target_unknown`).
- **A validator is a hint, never an identity.** A 200 is always judged by the hash of its body,
  whatever its `ETag` says.
- Conditional headers are sent on the first hop only, never to a redirect target.
- The schedule policy can switch conditional requests off.

### 5. Redirects

The fetch record gains `response.redirect_statuses`. A chain containing 301 or 308 that ends at a
*different URL key of the same outlet* moves the candidate: the target becomes a candidate
(`discovered_via: permanent_redirect`, `redirected_from`), the answer is attributed to it by a
second `FINISHED` row (`attributed_from`), and the old candidate is `MOVED` and never requested
again. The URL as requested stays in the fetch record. A temporary redirect changes no candidate.
Cross-origin redirects stay under the gate of CPD-0006 §3: a target the policy does not allow is
not followed.

### 6. Robots: `Sitemap:` and `Crawl-delay`

- Sitemaps named by an outlet's robots file can be read as one more discovery source, **only
  when a run asks for it** (`use_robots_sitemaps`), under the reserved source id
  `<outlet>:ch:robots_sitemaps` (no channel may be registered under that slug), through the same
  gate and budget as any channel document. A sitemap that is a registered channel is not read
  twice; one on another origin is refused by the gate and the refusal is on record.
- `Crawl-delay` is recorded as written — in the gate's evidence and in the request log
  (`policy_hints.robots_crawl_delay`). **Nothing applies it.** Whether it binds the pace is O-1.

### 7. Channel health (`channel-health/1`)

Health is a reading of the discovery evidence, computed when asked: `HEALTHY` · `DEGRADED` ·
`STALE` · `FAILING` · `DISABLED` · `UNKNOWN`, with the evidence it rests on. It is not stored and
has no score. `STALE` — readable, nothing new — is information, not a fault. **Health switches
nothing on or off**; `DISABLED` reports a switch set in the policy. Its two thresholds are inputs
without defaults.

### 8. Admission labels (`coprepan-admission-label/v1`, rule set `admission-technical/1`)

One label per item fetch: `TECHNICALLY_USABLE` or `TECHNICALLY_UNUSABLE`, with a closed list of
reasons, each `blocks` or `informs`, each with its evidence, plus rule set, run, labelling
instant, extractor and document version. Labels are an append-only table keyed by fetch and rule
set.

- **A label removes nothing.** The fetch, its bytes and its extraction stay. Selection happens at
  release.
- **Technical only.** A label says whether a fetch yielded a readable body text. It does not say
  that the page is an article, and it is not a judgement of genre, register, section, opinion,
  access class or language. `TECHNICALLY_USABLE` is a necessary condition for use, nowhere a
  sufficient one.
- A label produced with an extractor that is not `ACTIVE` says so (`extractor_not_active`).

### 9. Extractor lifecycle

`EXPERIMENTAL` → `CANDIDATE` → `VALIDATED` → `ACTIVE` → `RETIRED`. `baseline_html/0.1.0` is
`EXPERIMENTAL`. Production code that must not run on an unadopted extractor calls
`require_active()`. A lifecycle step is a decision with evidence; none is taken here.

### 10. Extraction evaluation harness (`extraction-eval/1`)

The instrument, without anything to measure yet:

- a **sample manifest** (`coprepan-extraction-sample/v1`): cases bound to body hashes, strata,
  seed, drawn by hash order within strata;
- **arms**: any extractor, or precomputed outputs (`PrecomputedArm`) — the only form in which the
  legacy extractor could enter, since the legacy system kept no raw HTML;
- every arm runs twice per case; two different answers stop the evaluation
  (`NonDeterministicArm`); an arm that raises or has no output is a recorded state, not a crash
  and not a zero;
- **pairwise disagreement** without any reference, and — against a human reference — token
  retention, added tokens, start and end boundary, title, metadata, and a catastrophic flag
  whose threshold is an input;
- a **review package**: per case the preserved page's visible text and the arms' outputs under
  blinded labels, an empty decision form, the blinding key in a separate file.

**All automatic numbers are diagnostics.** They never replace the reviewer, and they adopt
nothing. The harness holds no gold and simulates none
([gold-sample design](../extraction/GOLD_SAMPLE_DESIGN.md)).

### 11. Canary planner and preflight

`plan_canary` proposes a set of registered outlets that maximises diversity of country, outlet
type and channel kind, with a seeded tie-break and the reason for each pick. It is a proposal for
review and says so; it cannot know whether an outlet is a sensible first target.

`preflight` answers whether the real canary may run, from what is on disk, fail closed: the named
outlets registered and complete (O-11); acquisition and schedule policy decided (O-1); crawler
identity complete (O-2); preservation target `READY` and a runtime workspace (O-3); the full suite
green on exactly this commit; no drift of configuration, decisions, schemas, components or code
against the baseline manifest the operator approved. O-4 is not a precondition — the canary is
what measures it. `READY` permits the operator to start; it starts nothing.

## Alternatives considered

| Alternative | Why not |
|---|---|
| A stored per-channel or per-candidate counter or score, updated by each run, that switches things off | the legacy mechanism (F-9): unauditable, irreversible in effect, and wrong on "nothing new" |
| A stored candidate state column | drifts from the history; a derived state cannot |
| Built-in revisit intervals "to start with" | a pace towards publishers is a policy statement; a default would be an undeclared decision of O-1 |
| Treat a 304 as a copy of the previous fetch (same body hash, same bytes) | invents a body the server did not send; the record would claim bytes that were never received |
| Trust an unchanged `ETag` and skip the hash comparison | servers reuse validators; identity must rest on bytes |
| Follow a permanent redirect silently and keep the old candidate | the old URL is re-requested forever, and the document's URL history is lost |
| Read robots sitemaps always | which sources an outlet is read through is a registration matter; a robots file can name sitemaps of other sites |
| Apply `Crawl-delay` as a fixed rule | binding effect of robots signals is O-1 |
| Delete rejected candidates / unusable fetches | contradicts CPD-0001 (labels, not deletion); makes a rule change irreversible |
| One "is an article" label now | not decidable technically; needs the gold sample |
| A synthetic reference to "try out" the metrics on | a number without a reference population reads like a result |
| Outlet filter rules drafted from the legacy feed list | no page of any outlet has been seen by this pipeline |

## Consequences

- Stage 7 (admission labels) is `PARTIAL`: the technical label exists; nothing about content does.
- External acquisition has a fourth independent refusal: the schedule policy is `NOT_DECIDED`.
- O-10 has its evidence. Phase 0 stays open on the preserved copy and the restore check.
- The baseline manifest covers the schedule policy and the candidate rules.
- Phase 3 can begin the moment preserved real pages exist: sample, review package and metrics are
  ready; the gold itself is human work.

## Not decided here

- Every value of the schedule policy; whether `Crawl-delay` binds; whether robots sitemaps are
  used for an outlet (O-1, O-11).
- Any outlet rule for candidate qualification.
- Thresholds of channel health; any consequence of a health state.
- Content-level admission: article / not article, access class, language from content, length.
- The gold sample: size, strata values, reviewers, agreement procedure (design:
  [`GOLD_SAMPLE_DESIGN.md`](../extraction/GOLD_SAMPLE_DESIGN.md); decision: Phase 3).
- Which extractor candidates enter the comparison; the adoption criterion
  ([candidate survey](../extraction/EXTRACTOR_CANDIDATES.md) is a list, not a choice).
- WARC `revisit` records for 304 answers; pack rollover.
- The canary's outlets, limits and budget.
