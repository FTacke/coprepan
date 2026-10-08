# CPD-0016 — The staged canary driver, budgets of real requests, the canary-scope baseline and the arming protocol

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the canary run of 2026-10-08, which ordered a single integrated driver with hard budgets, a baseline frozen on the exact commit, an acquisition switch armed only afterwards and only for the canary, and disarmed after it. Recorded by that run; subject to the operator's review |
| Kind | policy · architecture |
| Scope | how the first real acquisition canary is orchestrated, bounded, pinned, started and verified |
| Builds on / amends / supersedes | builds on CPD-0006, CPD-0007, CPD-0009, CPD-0013, CPD-0014, CPD-0015. Amends the acquisition baseline manifest (CPD-0006 §9): a `scope` (`acquisition` · `canary`) and a `canary` block. Supersedes nothing |
| Does not change | any identifier or stored artefact; the acquisition and schedule policy values (CPD-0013); the storage contract; the extractor lifecycle (`baseline_html/0.1.0` stays `EXPERIMENTAL`) |
| Run report | [`docs/agent-runs/2026-10-08_canary-driver-and-arming-prepared.md`](../agent-runs/2026-10-08_canary-driver-and-arming-prepared.md) |
| Evidence | `tests/test_canary_driver.py` (27), `tests/test_canary_evidence.py` (11); the run report |

Validation debt: the driver has run against a scripted loopback outlet only. No real server has been
asked anything.

## Context

All the parts of an acquisition existed and were tested; nothing ran them in order, nothing counted
real requests across them, and the acquisition baseline of the previous design could not be frozen
for a canary: it required O-4 to be measured, which is the canary's own job, and the policy switch to
be on before the freeze that is supposed to authorise it.

## Decision

### 1. One driver, orchestration only

`canary_driver` runs five stages and adds no pipeline of its own: **A probe** (robots evidence and the first
selected channel document, no item request) and **B discovery** (the second channel) over all outlets, then per
outlet **C item fetch**, **D preserve** (`preserve_pack`: direct, or kept pending in the outage spool, then drain)
and **E derive** (identity, baseline extraction and technical admission of `RAW_PRESERVED` input only). Recovery is
diagnosed after every stage. Channels per outlet: at most two, one of each kind first
(`rss`, `atom`, `sitemap`, `sitemap_index`), registry order, never a disabled channel.

### 2. Budgets count real requests

Every transport call counts — a redirect hop, a robots file, a request that failed. Item requests: at most 80 in all
(a ceiling of 100 that no configuration may exceed), 16 per outlet; robots files and channel documents: 8 per outlet.
One attempt per request (a retry is the schedule's decision, an hour or a day later), one request at a time, the policy's pace
(10 s, or an origin's longer `Crawl-delay`). A fetch is started only when a whole fetch — the longest redirect chain
the limits allow — fits into what is left, otherwise it is a recorded refusal (`canary_budget_exhausted`); a call
that would still exceed a budget raises and is an integrity failure of the run. After a restart the budget is the budget
of the evidence: the counts are re-derived from the fetch records. The abort case of CPD-0009 (the request in flight
may be asked again) is covered by that rule: it can cost at most the headroom of one fetch per outlet.

### 3. The canary-scope baseline

A baseline built with `scope = canary` does not wait for O-4 — the canary is what measures it — and carries a `canary`
block: the driver (version, stages, budgets, transport limits, spool bounds, the channels it would read, the extractor and
its lifecycle), the five outlets as registered (digest of each record, URL rules), the digest of the storage contract and the
identity of the preservation target (its marker, not a disk). Every other precondition is the same as for an acquisition
baseline. The freeze is the operator's act: stating the manifest's digest.

### 4. Arming protocol

The switch `external_acquisition` is on only while the canary is armed. The sequence: the arming commit `P` (switch on, nothing else);
the full tests on `P`; the baseline built on `P` and frozen; the baseline committed as evidence (only `docs/canary/` and
`docs/agent-runs/` may differ between `P` and `HEAD`); the preflight `READY` with the frozen baseline; the run. The
driver itself refuses to make a request without a frozen baseline that verifies, a `READY` preflight, a clean tree, `HEAD`
equal to the last fetched `origin/main`, an empty spool and a baseline that still describes the driver, the outlets and the
storage identity — and it writes a start-state record before the first request. After the canary the switch is set back to `disabled`.

### 5. Receipt, verification, measurement

The run receipt is built from evidence only (fetch records of the packs, the request log, the ledger, the manifests, the spool);
no in-memory counter is read, and the fetcher's own counter is compared with the derived count. `verify` re-derives it and
adds the read-back and fixity of every preserved body, the identity rebuild, the recovery diagnosis and a replay of every
extraction **with the network made unavailable**. `measure` reports the sizes O-4 needs with their labels (`MEASURED`,
`DERIVED`, `ASSUMED`, `PROJECTED`), LOW / CENTRAL / UPPER projections per 1,000 and 100,000 fetches, and annual figures
only as conditional statements on stated, sourced volumes. A canary measures sizes, not a crawl rate.

## Alternatives considered

| Alternative | Why not |
|---|---|
| a new pipeline for the canary | the pieces exist and are tested; a second one would drift |
| count successful responses only | the budget protects servers from requests, not from answers |
| retries inside a call | the schedule policy decides when a thing is asked again |
| a baseline that waits for O-4 | O-4 is measured by the canary |
| arming before the baseline | a switch that is on with nothing pinned authorises nothing |
| a frozen baseline stored in the pinned commit | a file cannot contain the digest of the commit that contains it |

## Consequences

- The previous report's "no driver exists" is closed.
- The canary has not run: arming is a person's step ([run report](../agent-runs/2026-10-08_canary-driver-and-arming-prepared.md) §3).

## Not decided here

- The registration of further outlets; scheduled crawling; any change of the policy values.
- Phase 3: the sample sizes, the candidates and the adoption criterion are not fixed here.
- The institutional file system and the move to it.
