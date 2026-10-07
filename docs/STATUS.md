# COPREPAN 3.0 — Current Status

**This is the one place that says what actually exists.** Every other document describes a target,
a rule or a plan. If a document sounds as if something were built, and this file says it is not,
this file is right and the other document has a defect.

**As of 2026-10-07 (foundation, architecture and core-pipeline run): there is no production
pipeline.** Nothing discovers or fetches: there is no network code. No outlet is registered. No
storage root is configured. No corpus material has been acquired, preserved or extracted by
COPREPAN 3.0. Nothing is validated. Nothing is activated.

What exists beyond documents: the core primitives of Foundation Core I, and one core section of
the pipeline — fetch record → sealed pack → preservation → document identity → extraction →
document version — that runs end to end **on recorded exchanges of synthetic fixtures, on
temporary directories** (§3). It has never seen a real outlet, a real page or a real storage root.

---

## 1. Three separate axes

| Axis | Values | Meaning |
|---|---|---|
| implementation | `NOT_STARTED` · `PARTIAL` · `IMPLEMENTED` | code and tests exist |
| validation | `NOT_VALIDATED` · `VALIDATED` | measured against its gate on real or gold material, with a run report |
| activation | `INACTIVE` · `ACTIVE` | switched on for corpus material by an explicit decision |

`ACTIVE` requires `IMPLEMENTED` and `VALIDATED`. A stage that is planned and nothing else is
`NOT_STARTED` / `NOT_VALIDATED` / `INACTIVE`. The self-check enforces these rules.

## 2. Pipeline stages

| # | Stage | Implementation | Validation | Activation |
|---|---|---|---|---|
| 1 | outlet registry | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 2 | discovery | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 3 | fetch | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 4 | raw preservation | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 5 | document identity | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 6 | extraction | `PARTIAL` | `NOT_VALIDATED` | `INACTIVE` |
| 7 | admission labels | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 8 | normalisation | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 9 | NLP | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 10 | validated enrichment | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 11 | release | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 12 | cross-corpus contract | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |

What `PARTIAL` means for the four stages, exactly:

| Stage | Exists | Does not exist |
|---|---|---|
| outlet registry | schema `coprepan-outlet-registry/v1`, validator, lookup; the legacy import, executed on a copy of the legacy database: **82 proposed outlets, 352 proposed channels** | **any registered outlet**; any attribute beyond what the legacy database held (type, group, time zone, URL rules); the human review of the proposal |
| raw preservation | fetch record; WARC pack writer, seal, derived and bound index, fixity check, torn-tail quarantine; state machine and ledger; fail-closed root resolution; promotion; outage spool — on temporary directories, with recorded exchanges | a fetcher (stages 2–3); channel documents; scheduled fixity, reconciliation, backup; conformance of the pack against an independent WARC reader; a run against a real target; a configured root |
| document identity | id serialisation and canonical URL key (CPD-0003); document and version assignment, append-only identity tables, collision refusal, `duplicate_of` and `moved_to` relations (CPD-0005 §4) — on recorded exchanges | syndication clusters; URL-key aliases after a rule change; a durable home for the tables; any id minted for corpus material |
| extraction | the extraction record and its digests; storage by fingerprint; replay from the preservation root; a **baseline** extractor (`baseline_html/0.1.0`) | an adopted extractor; a gold sample; any quality measurement; per-outlet rules; admission labels; date parsing |

Stages 2 and 3 are `NOT_STARTED` although acquisition *records* exist: the only run kind is the
replay of recorded exchanges. Replaying fixtures is not discovery and not fetching.

## 3. Foundation

| Item | State | Where |
|---|---|---|
| Agent instructions | in place | `AGENTS.md`, `CLAUDE.md` |
| Document hierarchy and authority index | in place | `docs/architecture/INDEX.md` |
| Decisions | CPD-0001 to CPD-0004 `ACTIVE`; CPD-0005 `ACTIVE_WITH_VALIDATION_DEBT` (§6) | `docs/decisions/` |
| **Foundation Core I** (master plan §12 item 3) | **complete** as infrastructure: all six items implemented and tested; the legacy import executed and repeatable; CPD-0003 reviewed. Reproducibility / infrastructure integrity only | run report of 2026-10-07 (core pipeline) §2 |
| Naming contract — lexical rules for corpus, generation, provenance class, `country_id`, `outlet_id`, `release_id`, schema ids | implemented and unit-tested | `src/coprepan/naming.py`, `tests/test_naming.py` |
| Naming contract — serialisation of fetch, channel, document, version, unit, sentence, token ids; canonical URL key | implemented and unit-tested (CPD-0003); **no id minted** | `src/coprepan/identity.py`, `tests/test_identity.py`, [`docs/identity/INDEX.md`](identity/INDEX.md) |
| Outlet registry | schema, validator, lookup implemented and unit-tested; holds **82 proposed outlets, none registered** | `config/outlet_registry.json`, `src/coprepan/registry.py`, `tests/test_registry.py` |
| Legacy outlet import | executed 2026-10-07 on a copy of the legacy database; deterministic on repetition; real schema equal to the assumed one; legacy-name → `outlet_id` table produced as `hypothesis`. **Not reviewed by a human** | `src/coprepan/legacy_registry_import.py`, `config/registry_review/`, corpus supply §16 |
| Legacy archaeology and component dispositions | recorded | [`docs/legacy/ARCHAEOLOGY.md`](legacy/ARCHAEOLOGY.md), CPD-0004 |
| Acquisition run and fetch record | implemented and unit-tested for recorded exchanges; **no fetcher** | `src/coprepan/acquisition.py`, [`docs/acquisition/INDEX.md`](acquisition/INDEX.md) |
| Sealed WARC pack | implemented and unit-tested (own writer, standard library); **not read by an independent WARC reader** | `src/coprepan/pack.py`, `tests/test_acquisition_pack.py` |
| Document identity tables | implemented and tested on recorded exchanges | `src/coprepan/document_identity.py`, [`docs/identity/INDEX.md`](identity/INDEX.md) §7 |
| Extraction contract and baseline extractor | implemented; behaviour of the contract tested; **quality unknown, extractor not adopted** | `src/coprepan/extraction.py`, [`docs/extraction/INDEX.md`](extraction/INDEX.md) |
| Vertical canary (fixture → fetch record → pack → preservation → identity → extraction → version → replay) | passes on four synthetic pages, on temporary directories | `src/coprepan/core_pipeline.py`, `tests/test_core_pipeline.py` |
| State machine and ledger primitives | implemented and unit-tested | `src/coprepan/ledger.py`, `tests/test_ledger.py` |
| Stage-status self-check | implemented | `tests/test_repository_contract.py` |
| Test guards (no network, no storage root, suite membership) | implemented | `tests/conftest.py` |
| Storage-target configuration and root resolution | fail-closed resolver implemented and unit-tested; **no root configured** | `config/storage_targets.yml`, `src/coprepan/storage_roots.py`, `tests/test_storage_roots.py` |
| Promotion semantics and outage spool | implemented; tested **on temporary directories only** (first half of the Phase-1 gate) | `src/coprepan/preservation.py`, `src/coprepan/outage_spool.py`, `tests/test_preservation.py` |
| Write-once layer store | implemented and unit-tested; its durable location (role) is undecided | `src/coprepan/layer_store.py`, `tests/test_layer_store.py` |
| Release gate suite | scaffold; **contains no test** | `tests/suites/release_gate.txt` |
| Git | initialised 2026-10-07 on operator brief: branch `main`, remote `origin` = `https://github.com/FTacke/coprepan.git`; no history taken over from the legacy repository | [closure run report](agent-runs/2026-10-07_coprepan-repository-migration-closure.md) |
| Legacy freeze `coprepan-legacy-2026-06` | **not executed** | `docs/legacy/INDEX.md` §5 |

## 4. Production stack

None. No model, provider, crawler, extractor or annotator is active. The NLP pins in
`pyproject.toml` `[tool.coprepan.nlp]` are marked `PLANNED`: they are not installed and not used.
The package has no runtime dependency. `baseline_html/0.1.0` and `pack-writer/1` are component
versions recorded in artefacts; neither is an adopted production component.

No external API is used by any code in this repository.

## 5. Open gates blocking production crawling

| Gate | State | Owner |
|---|---|---|
| Acquisition policy decided, implemented, tested (O-1) | open | operator / institution |
| Crawler identity and contact (O-2) | open | operator / institution |
| Preservation target (O-3) | open | operator / institution |
| Storage capacity (O-4) | open | operator / institution, then measured |
| Phase-1 core gate (promotion, idempotence, conflict, crash recovery) | open — tests pass on temporary directories (2026-10-07); the half on a real preservation target needs O-3 | engineering, then operator |
| Phase-2 canary gate | open — no fetcher; the fixture canary of 2026-10-07 is not this gate (it fetches nothing and measures no bytes per fetch) | engineering |
| **Registry review**: human review of the proposed outlets; registration of the outlets to acquire for | open — proposal delivered 2026-10-07 | operator |

Full list: [master plan](plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) §13.

## 6. Validation debt

Everything scientific. No extraction, annotation, enrichment or release has been validated. The
first validations are defined by the gates of Phases 1–4 (master plan §11).

What the tests of 2026-10-07 establish is **reproducibility** (same inputs, same ids and bytes;
replay from preserved bytes) and **robustness** against injected failures (interrupted append,
crash between steps, damaged stores) — on synthetic fixtures. They establish nothing about
replicability or generalisability, and nothing about any real outlet.

Named debts of CPD-0005 (`ACTIVE_WITH_VALIDATION_DEBT`):

| Debt | Closed by |
|---|---|
| `pack-writer/1` output read by an independent WARC reader | a conformance check with a pinned third-party reader |
| Promotion, idempotence, conflict and crash recovery on a real preservation target | second half of the Phase-1 gate; needs O-3 |
| The legacy importer's proposal reviewed | the registry-review gate (§5) |
| Baseline extractor against real pages; an adopted extractor | Phase 3: gold sample, preregistered comparison |
| Identity policy on real URLs (per-outlet rules; collision behaviour at scale) | Phase-2 canary |
| Process-kill crash tests (today: failures injected in-process) | Phase 1 on a real target |

## 7. Machine-readable assertions

Consumed by `tests/test_repository_contract.py`. The test compares this block with
`src/coprepan/stages.py` and enforces the axis rules of §1. **Update this block, the tables above
and the code in the same run** as any change of state; a state is never raised here without the
run report that carries the evidence.

<!-- status_assertions:begin -->
```json
{
  "schema": "coprepan-status-assertions/v1",
  "as_of": "2026-10-07",
  "production_pipeline_exists": false,
  "external_api_in_production_path": false,
  "git_initialised_by_bootstrap": false,
  "stages": {
    "outlet_registry":       {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "discovery":             {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "fetch":                 {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "raw_preservation":      {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "document_identity":     {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "extraction":            {"implementation": "PARTIAL",     "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "admission_labels":      {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "normalisation":         {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "nlp":                   {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "enrichment":            {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "release":               {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "cross_corpus_contract": {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"}
  },
  "open_production_gates": ["O-1", "O-2", "O-3", "O-4", "PHASE_1_CORE", "PHASE_2_CANARY", "REGISTRY_REVIEW"]
}
```
<!-- status_assertions:end -->

## 8. History

- 2026-10-06 — repository bootstrap: foundation documents, naming module, tests. No pipeline.
  Run report: [`docs/agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md`](agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md).
- 2026-10-07 — repository and path migration (infrastructure only; no stage state changed). The
  legacy repository and the studies repository were archived unchanged; the rename of this
  repository to its new place is handed to the operator. Git is still not initialised.
  Run report: [`docs/agent-runs/2026-10-07_repository-and-path-migration.md`](agent-runs/2026-10-07_repository-and-path-migration.md).
- 2026-10-07 — migration closure (infrastructure only; no stage state changed). The operator
  renamed this repository to `C:\dev\panhispanic_media_corpora\coprepan`; the suite was confirmed
  from the new place; git was initialised (`main`) with the foundation as its first commit and
  `origin` set to `https://github.com/FTacke/coprepan.git`. This entry supersedes the two
  "handed to the operator" / "not initialised" statements of the entry above.
  Run report: [`docs/agent-runs/2026-10-07_coprepan-repository-migration-closure.md`](agent-runs/2026-10-07_coprepan-repository-migration-closure.md).
- 2026-10-07 — Foundation Core I (implementation; reproducibility / infrastructure integrity
  only). Id serialisation and canonical URL key frozen (CPD-0003); outlet registry schema;
  ledger and state machine; fail-closed root resolution, promotion and outage spool; write-once
  layer store. Stages 1, 4 and 5 move to `PARTIAL`. **Not done: the legacy import was built but not
  run on the legacy database**, so the registry is empty and no legacy-name mapping exists. No
  validation, no activation, no gate closed.
  Run report: [`docs/agent-runs/2026-10-07_foundation-core-i.md`](agent-runs/2026-10-07_foundation-core-i.md).
- 2026-10-07 — foundation, architecture and core-pipeline run (implementation; reproducibility and
  robustness only). Foundation Core I closed: the legacy import ran on a copy of the legacy
  database (82 proposed outlets, 352 proposed channels, nothing registered) and CPD-0003 was
  reviewed (kept). This supersedes the "not run" statement of the entry above. Legacy archaeology
  recorded; CPD-0004 (legacy dispositions) and CPD-0005 (core pipeline contracts) decided.
  Implemented on recorded exchanges: acquisition run, fetch record, sealed pack, raw preservation
  wiring, document identity, extraction contract with a baseline extractor, replay; vertical
  canary on synthetic fixtures. Stage 6 moves to `PARTIAL`. No network code, no registered outlet,
  no validation, no activation, no gate closed; one gate added (registry review).
  Run report: [`docs/agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md`](agent-runs/2026-10-07_foundation-architecture-and-core-pipeline.md).
