# CPD-0019 — Repair of the first canary's findings; hop-wise budgets with a reserved part for index expansion; the source-discovery inventory; second and extended canary

| Field | Value |
|---|---|
| Date | 2026-10-09 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the brief of the integrated discovery, source-recovery and acquisition-qualification run of 2026-10-09, which ordered the findings F1–F7 repaired, a deterministic strategy for budget reservation and sitemap-index exploration chosen by the run, a versioned source-discovery inventory, and a second and an extended canary prepared up to the operator's gates; technical choices were delegated to the run and are recorded here. Subject to the operator's review |
| Kind | architecture · policy (canary scope) |
| Scope | discovery parser, robots evidence, access-control classifier, item planning, canary budgets and accounting, receipt scope, the acquisition policy file of the canary, analytic status vocabulary of source discovery, the two canaries that follow |
| Builds on / amends / supersedes | builds on CPD-0006, CPD-0007, CPD-0010, CPD-0013, CPD-0017. **Amends CPD-0016 §2** (how a fetch is admitted to a budget; whose budget a canary has) and **§1** (channel kinds a canary may read). Amends CPD-0017 only in its classifier version (`access-control/2`). Supersedes nothing |
| Does not change | any identifier or stored artefact; the frozen baselines and the evidence of the first canary; the hard ceiling of 100 item requests; the eight non-item requests per outlet; the pace; the three layers of CPD-0017; the rule that no access control is worked around; the arming protocol (CPD-0016 §4); the registration rule (CPD-0013 §1) |
| Run report | [`docs/agent-runs/2026-10-09_discovery-source-recovery-and-acquisition-qualification.md`](../agent-runs/2026-10-09_discovery-source-recovery-and-acquisition-qualification.md) |
| Evidence | `tests/test_canary_findings.py` (32), `tests/test_source_discovery.py` (10); `config/source_discovery/canary_replay_2026-10-09.json` (the preserved answers of 2026-10-08 read again by the repaired code); the run report |

Validation debt: every repair is validated offline — on synthetic fixtures, a loopback server and the
preserved answers of one evening. None has met a real server. That is what the second canary is for.

## Context

The first real canary (2026-10-08) acquired items from one outlet of five. Its report names three
defects of our own code (F1, F3, F5), one miss of a policy guarantee (F2), one budget consequence
(F4), one dead channel (F6) and one observation (F7). Beyond the canary, 77 of 82 outlets are only
proposed, and what the legacy system's records show about each had never been joined with what can
be known about the outlets today.

## Decision

### 1. F1 — a robots file is decoded for reading, preserved as received (`robots-parser/3`)

`robots.evidence_from_response` takes the content coding of the answer and undoes it before parsing.
The digest it names (`robots_txt_sha256`) stays the digest of the bytes as received, which are the
preserved bytes. A body whose coding cannot be undone, or is not one this project reads, is a file
that cannot be read: `parse_error`, on which the policy holds. Nothing is guessed.

### 2. F2 — the Sucuri JavaScript challenge is an access control (`access-control/2`)

Two changes: the marker of the Sucuri CloudProxy challenge is known, and a small body (at most
32 KiB) is inspected **whatever its status** — the challenge of 2026-10-08 came as a 307 without a
`Location`. A challenge holds its origin for the rest of the run, as before. In addition, a canary
re-derives its holds from the **stored answers** of the workspace under the current classifier
(`access_holds_from_evidence(reclassify=True)`): an origin that challenged this crawler is held
although the classifier of that day recorded `none_observed`. The stored record is not changed.
Consequence, stated: `https://proceso.hn` is held for every later canary on this workspace until a
person lifts the hold. There is no mechanism to lift one yet (not decided here).

Nothing is added that could pass a challenge: no script is run, no cookie is set, the client says
the same thing about itself in every request.

### 3. F3 — an outlet's run sees its own candidates

`run_http_acquisition` qualifies, schedules and requests the candidates of the outlet it runs for
and no other. (The 64 foreign plans of 2026-10-08 were refused by the policy gate; they also left
`DENIED` rows in the history of 64 candidates of `do_diario_libre` (measured 2026-10-09). Those rows
stay. Because the policy version changes with §6, the schedule treats them as denials under an old
policy and the candidates are due again; under the old version they would have waited a week.)

### 4. F4 — budgets are counted hop by hop, and part of the non-item budget is reserved for expansion

Amends CPD-0016 §2. Unchanged: every transport call counts; an outlet is asked at most 8 non-item
requests and at most its item budget; a call over a budget raises.

- **Hop-wise admission.** A fetch starts while one request is left in its group; a redirect is
  followed while one is left. A hop that no longer fits is not requested: the redirect answer is the
  recorded response, with `redirect_not_followed: DENY: canary_budget_exhausted`. (Before: a fetch
  started only when the longest possible chain, four requests, fitted — which left up to three
  requests of every budget unusable and was why no child of a sitemap index was read.)
- **Reservation.** Of the 8 non-item requests, 3 are reserved for the documents a channel names
  (`expansion_requests_reserved_per_outlet`): robots files and registered channel documents can use
  at most 5. A request is an *expansion* request when its channel document lies below the registered
  one (`FetchRequest.expansion_depth > 0`, written to the request log with the plan). No limit is
  raised by this.
- **Priority of what is expanded** (`expansion-order/1`, `discovery.expansion_priority`). The
  children of an index are read: a child whose name marks a news sitemap first; one whose name marks
  a taxonomy, author, page or media sitemap last; within each class the most recently modified first
  (`lastmod`), a child without a readable `lastmod` after those with one; document order breaks
  ties. A name moves a child in the order and never excludes it.
- **Documents asked for.** `max_documents` of a discovery pass bounds the documents *asked for*: one
  that was refused or absent has used its place (before, 92 children were planned and refused one by
  one). The canary's pass asks for 4 (the channel document and three children; before: 3 read).
- **Whose budget.** A canary has the budget of its frozen baseline: the tally is re-derived from the
  fetch records of the runs started under that baseline. A canary started again shares one budget; a
  new canary — a new arming, a new freeze — does not inherit what an earlier one spent.
- **A wider canary** (six to fifteen outlets, `canary_budget`) keeps every per-outlet limit; its item
  budget per outlet is what the ceiling leaves (`min(16, 96 // outlets)`): twelve outlets, eight items each.
- **A receipt is the receipt of one run**: its packs are those that hold a fetch record of the run,
  its candidates those first listed in it; it states the expansion requests beside the unchanged
  `item` / `other` split. `verify` holds a stored receipt against every field it states and re-derives
  the policy version from the fetch records. The receipt of 2026-10-08 still verifies (`PASS`, measured).

### 5. F5 — a declaration is looked for in the markup, not in text (`channel-parser/2`)

The guard against DTD and entity declarations ignores CDATA sections and comments, matched left to
right so that one cannot be used to hide a declaration behind the other; a section that is never
closed is not ignored. A real declaration is refused exactly as before.

### 6. F6 — the channel that answered 404 is disabled; nothing replaces it

`hn_proceso_digital:ch:sitemap_news` is in `disabled_channels` (evidence: one 404 with the site's
own not-found page, 2026-10-08). No other address was added for that origin: the origin challenges
this crawler (§2), and looking for another way into it would be a way around. Research names a
feed a third-party crawler reads there; it is in the inventory as a hypothesis and is not requested.
The policy version is `canary/2026-10-09.1`. Policy values are otherwise those of CPD-0013 / CPD-0017.

### 7. F7 — the candidate budget is measured, not raised

`discovery_coverage.coverage` derives from the discovery tables what a pass listed, kept and turned
away, and `frontier` what a channel named and nobody read. Measured on the first canary: the news
sitemap of `do_diario_libre` listed 534 entries, 231 became candidates, 303 were turned away by the
budget of 200 new candidates per pass; their dates span 2026-10-05 to 2026-10-07, those kept
2026-10-07 to 2026-10-08, and **44 of the 303 are newer than the oldest entry kept** — the listing is
not strictly newest-first. A later pass takes the next entries without a higher limit (tested), as
long as the channel still lists them. The limit stays 200. Whether a pass should order dated entries
before it applies the budget is **not decided here**.

### 8. The source-discovery inventory and its analytic flags

`config/source_discovery/source_discovery_inventory_<version>.json` (page:
`docs/corpus_supply/SOURCE_DISCOVERY_INVENTORY.md`) joins, per outlet, four kinds of evidence that
stay apart: the registry; the legacy discovery audit; prediscovery research files (passive research
of a stated day — hypotheses, never observations of a server); the replay and verification of a
canary. Six analytic flags, a reading aid and **not a state machine**:

| Flag | Rule |
|---|---|
| `IMPORTED` | a row of the legacy import |
| `DISCOVERED` | a possible channel is known (legacy or research). Known is not tested |
| `QUALIFIED` | this project read a channel document of the outlet from a real server and the current parser finds an item entry with a usable address in it |
| `REGISTERED` | a registration record exists |
| `ACQUISITION_VERIFIED` | in one bounded run at least 5 item pages answered 2xx, are `RAW_PRESERVED` with verified fixity, and their extraction was replayed without network |
| `OPERATIONALLY_STABLE` | `ACQUISITION_VERIFIED` in at least three runs on three different days within at least fourteen days, without an access-control hold in between |

An inventory version is written once; new evidence is a new dated file and a new version. A
prediscovery file is never rewritten. The priority score of the inventory is a stated scenario rule
for ordering work, not a measurement.

**Passive research and requests are different acts.** A prediscovery file is made from search
results and third-party pages; no address of a publisher is requested for it, not for a robots file
and not "to see whether it is up". The first request to an outlet is made by the identified crawler,
behind the gate, in an armed canary.

### 9. The two canaries that follow, and where this run stops

- **Second canary:** the five registered outlets under driver `canary-driver/3` and policy
  `canary/2026-10-09.1`. Prepared. Gate: the operator's arming (CPD-0016 §4), unchanged.
- **Extended canary:** twelve outlets of ten countries, in
  `config/registry_review/extended_canary_proposal_2026-10-09.json` — a **proposal**. It adds eight
  channels that come from research, one origin, one candidate rule and two disabled channels; it
  registers nothing. Gate: O-11 — the operator reviews it and applies it
  (`scripts/apply_registration_proposal.py --write`), wholly or in part; then the arming protocol.
- A listing channel (`archive`, `section_page`) is read by a canary only for an outlet whose reviewed
  candidate rules carry an allow pattern; the driver passes the outlet rules to qualification.

## Alternatives considered

| Alternative | Why not |
|---|---|
| raise the non-item budget per outlet | the brief forbids weakening a request limit; reservation and hop-wise counting reach the second level within eight |
| a separate, additional budget for expansion | the same as raising the limit |
| read the children of an index in document order | which children fit a budget would be an accident of the generator; in the index of 2026-10-08 the first and the 86th child carry the newest `lastmod` |
| exclude taxonomy sitemaps by name | a name is a convention of generators, not a fact about an outlet; order, never exclusion |
| strip every `<!DOCTYPE` before parsing | would let a real declaration through |
| replace the 404 channel by another address of the same origin | the origin challenges this client; that would be a way around |
| a higher candidate limit | not shown to be the binding constraint of a canary; the loss is now measured |
| register the twelve outlets in this run | eight channels and one origin come from research, not from the registry: not a routine case (CPD-0013 §1) |
| probe publishers with a plain fetch "for prediscovery" | a request outside the gate and outside the crawler's identity |

## Not decided here

- how and by whom an access-control hold is lifted;
- whether dated entries are ordered before the candidate budget is applied; any change of a discovery limit;
- incremental continuation of a sitemap index across runs (the frontier is derivable; nothing reads it);
- every judgement the proposal lists for the reviewer; whether a state-controlled, an exiled or a paywalled outlet belongs in the corpus;
- thresholds of `OPERATIONALLY_STABLE` are stated above and have never been met by anything: they are a first statement, to be confirmed when there is something to hold against them;
- the acquisition policy of scheduled crawling (O-1), unchanged.
