# CPD-0004 — Legacy component dispositions

| Field | Value |
|---|---|
| Date | 2026-10-07 |
| Status | `ACTIVE` |
| Decided by | the operator, in the brief of the foundation, architecture and core-pipeline run (2026-10-07), which ordered an explicit decision per legacy component and authorised that run to take technical and architectural decisions where the evidence suffices. Recorded by that run; the wording and each disposition are subject to the operator's review. |
| Kind | architecture |
| Scope | what COPREPAN 3.0 takes from the legacy system, per component, separately for concept, implementation and data |
| Builds on / amends / supersedes | builds on CPD-0001 §2 (strategy C: selective reuse) and makes it specific; refines the two reuse tables of [`docs/legacy/INDEX.md`](../legacy/INDEX.md) §6 |
| Does not change | the legacy repository, corpus and data (read-only); the standing of the legacy corpus (legacy index §3); the frozen-release plan |
| Run report | [`docs/agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md`](../agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md) |
| Evidence | [`docs/legacy/ARCHAEOLOGY.md`](../legacy/ARCHAEOLOGY.md) (reconstruction and failure mechanisms F-1 … F-22, with their evidence labels) |

## Context

CPD-0001 decided selective reuse without saying, component by component, what "selective" means.
Without that, every later run would decide again whether a piece of legacy code is a template.

## Decision

Vocabulary: `REUSE_AS_IS` · `PORT_WITH_TESTS` (copy with origin recorded, own tests) ·
`REIMPLEMENT_FROM_CONTRACT` (keep the idea, write against the 3.0 contracts) · `DATA_ONLY` (the
data are used, the code is not) · `REFERENCE_ONLY` (consulted, never built on) · `DISCARD` ·
`UNDECIDED`.

No legacy component is `REUSE_AS_IS`: none has both tests and a contract that 3.0 shares.

| Area | Concept | Legacy implementation | Legacy data | Reason |
|---|---|---|---|---|
| Outlet register | `REIMPLEMENT_FROM_CONTRACT` — done: registry schema v1 | `DISCARD` (table without outlet attributes; codes derived from display names) | `DATA_ONLY` — the 82 sources, imported as `proposed` outlets with every legacy code as an alias | F-22; archaeology §1 |
| Feed / channel list | `REIMPLEMENT_FROM_CONTRACT` (channels with URL history; health as ledgered state) | `DISCARD` | `DATA_ONLY` — 352 feeds as proposed channels, legacy score, status and failure reason kept verbatim as observations, **not** as health state | F-9 |
| ASCII slug helper | `REIMPLEMENT_FROM_CONTRACT` — done: `registry.propose_slug`, proposes only | `REFERENCE_ONLY` (the same seven steps; never applied at registration there) | — | archaeology §1 |
| Discovery strategy (robots, standard paths, head links) | `REIMPLEMENT_FROM_CONTRACT`, Phase 2 | `DISCARD` (errors swallowed; image and video entries collected; indexes forced inactive) | `DATA_ONLY` — `discovered_by` kept per channel | F-9 |
| Sitemap-index expansion | `REIMPLEMENT_FROM_CONTRACT`, Phase 2 | `DISCARD` (not implemented) | — | archaeology §1 |
| Output probe (does a channel yield article text?) | `REIMPLEMENT_FROM_CONTRACT` as the channel qualification gate, Phase 2 | `DISCARD` (probe ignored known URLs and so failed healthy feeds) | — | F-9 |
| Feed scoring (0–100) | `DISCARD` — points for the string `202`, for language and stability that always apply | `DISCARD` | `REFERENCE_ONLY` — the stored score is an observation | archaeology §1 |
| Feed feedback loop | `REIMPLEMENT_FROM_CONTRACT` as reversible, ledgered channel health; "no new URL" is not "empty" | `DISCARD` | — | F-9 |
| Crawl loop, run state | `REIMPLEMENT_FROM_CONTRACT` — done for recorded exchanges: run record, ledger, resume | `DISCARD` | `REFERENCE_ONLY` — `crawl_runs`, `discovery_runs` | F-12 |
| HTTP client and politeness | `REIMPLEMENT_FROM_CONTRACT`, Phase 2, behind O-1 / O-2 | `DISCARD` | — | F-10 |
| robots / opt-out handling | `UNDECIDED` — open institutional decision O-1; the legacy heuristic is not a policy | `REFERENCE_ONLY` | — | F-10 |
| Paywall and binary detection | `REIMPLEMENT_FROM_CONTRACT` as admission **labels** on preserved fetches, Phase 3 | `DISCARD` (phrase lists on prose; a byte heuristic that discards) | `REFERENCE_ONLY` — status counts | F-4 |
| Article store (database model) | `DISCARD` — URL-seen set, extraction result and status in one row | `DISCARD` | `DATA_ONLY` for the frozen legacy release; `REFERENCE_ONLY` as the URL list of a later re-fetch canary | F-1, F-13 |
| Article identity (`article_id`) | `DISCARD` — replaced by canonical URL key + document version | `DISCARD` | `DATA_ONLY` — kept as the alias `legacy_article_id` where a legacy URL is re-acquired; never a key | F-7, F-8; ablation in `tests/test_core_pipeline.py` |
| HTML extractor | `REIMPLEMENT_FROM_CONTRACT` — contract done; the extractor to adopt is a Phase-3 decision | `DISCARD` | — | F-2, F-4, F-5, F-14 |
| Per-outlet extraction profiles | `REIMPLEMENT_FROM_CONTRACT` as versioned outlet rule sets, Phase 3 | `DISCARD` (one example profile) | — | archaeology §1 |
| Date extraction | `REIMPLEMENT_FROM_CONTRACT` — value as published plus basis; no fuzzy parsing, no substitute date | `DISCARD` | `REFERENCE_ONLY` | F-6 |
| "Label, don't delete" (`date_published_source`, `policy_fail_reasons`, extended store) | `REIMPLEMENT_FROM_CONTRACT` as the admission-label principle | `DISCARD` | `DATA_ONLY` within the frozen release | archaeology §7 |
| Export policy routing, daily files | `DISCARD` — selection belongs to a release view, never to acquisition | `DISCARD` | `DATA_ONLY` — the files *are* the legacy corpus | F-11, F-13, F-19 |
| Cleaning with offset-carrying report | `REIMPLEMENT_FROM_CONTRACT` as recorded normalisation operations | `DISCARD` — its one wording-changing operation is the lossy repair of a defect 3.0 does not have | — | F-3 |
| Annotation runner design (stage versions, three hashes, atomic write, skip-if-current) | `REIMPLEMENT_FROM_CONTRACT` — realised generically as fingerprint + layer store | `REFERENCE_ONLY` | — | archaeology §4 |
| spaCy annotation | `REIMPLEMENT_FROM_CONTRACT` under the shared instrument contract, Phase 4 | `DISCARD` (unpinned; model version unrecorded) | `DATA_ONLY` within the frozen release | F-14 |
| Tense rules and taxonomy | `UNDECIDED` until the shared verbal-complex layer exists; candidate `PORT_WITH_TESTS` for the rule cases as regression material | `REFERENCE_ONLY` | `DATA_ONLY` within the frozen release | F-16; NLP index |
| Tense labels inside `morph` | `DISCARD` — project labels are separate layers keyed on token ids | `DISCARD` | not mapped (naming §6) | F-16 |
| Section detection and `section_map_v1.yml` | `REIMPLEMENT_FROM_CONTRACT` as a versioned enrichment layer; the value set is a starting point, not validated | `REFERENCE_ONLY` | `DATA_ONLY` within the frozen release | F-18 |
| `is_opinion` as a flag orthogonal to section | `REIMPLEMENT_FROM_CONTRACT`, with the section layer | `REFERENCE_ONLY` | `DATA_ONLY` within the frozen release | archaeology §7 |
| Language guard | `REIMPLEMENT_FROM_CONTRACT` as an admission label from content, Phase 3 | `REFERENCE_ONLY` | — | F-11 |
| Dashboard | `REIMPLEMENT_FROM_CONTRACT`, later, as a read-only view on ledgers | `DISCARD` (owns jobs, mutates without authentication) | — | F-12, F-21 |
| Tests | `DISCARD` as a suite; **never run** | `DISCARD` | — | F-21 |
| Migration and one-off repair scripts | `DISCARD` | `REFERENCE_ONLY` as the record of what was done to the data | — | F-20 |
| `backup/`, `data/sources_seed.json` | — | — | `REFERENCE_ONLY`; origin not reconstructible | archaeology §6 |

Standing rules that follow:

1. **`DATA_ONLY` never means "trusted".** Every imported legacy value is an observation under
   `legacy_observed` or an alias with `mapping_status: hypothesis`.
2. **Nothing legacy enters 3.0 through a default.** A legacy value becomes a 3.0 value only through
   a recorded mapping or a human review step.
3. A disposition of `REIMPLEMENT_FROM_CONTRACT` scheduled for a later phase is **not** an
   implementation and gives that phase no head start in `docs/STATUS.md`.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Port the legacy extractor and fix its two known defects | Its defects are consequences of its design (prose-level substring rules, no versioning, no raw input), not two bugs; and no preserved HTML exists to test a fix against. |
| Port the crawl loop and add a ledger | State lives in a thread and a URL-seen set; a fetch has no record. A ledger around it would ledger nothing that can be replayed. |
| Import the legacy outlets as registered | The import can only see codes and feeds. Whether two codes are one outlet, and what an outlet's type, group and time zone are, is knowledge the database does not hold. |
| Treat the legacy feed status and score as channel health | They were produced by a loop that deactivates healthy feeds (F-9). |

## Consequences

- [`docs/legacy/INDEX.md`](../legacy/INDEX.md) §6 is superseded by this table where the two differ.
- The legacy import is executed: 82 proposed outlets and 352 proposed channels are in
  `config/outlet_registry.json`, none registered.

## Not decided here

- The acquisition policy, including robots and opt-out handling (O-1).
- Which extractor is adopted (Phase 3, on a gold sample).
- The fate of the tense rules (with the shared verbal-complex layer).
- Whether the legacy window is re-fetched (Phase 5).
- Registration of any outlet: human review of the proposal.
