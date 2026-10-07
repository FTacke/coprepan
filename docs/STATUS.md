# COPREPAN 3.0 — Current Status

**This is the one place that says what actually exists.** Every other document describes a target,
a rule or a plan. If a document sounds as if something were built, and this file says it is not,
this file is right and the other document has a defect.

**As of 2026-10-06 (repository bootstrap): there is no pipeline.** Nothing discovers, fetches,
preserves, extracts, annotates or releases. No storage root is configured. No corpus material has
been acquired by COPREPAN 3.0. Nothing is validated. Nothing is activated.

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
| 1 | outlet registry | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 2 | discovery | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 3 | fetch | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 4 | raw preservation | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 5 | document identity | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 6 | extraction | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 7 | admission labels | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 8 | normalisation | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 9 | NLP | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 10 | validated enrichment | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 11 | release | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |
| 12 | cross-corpus contract | `NOT_STARTED` | `NOT_VALIDATED` | `INACTIVE` |

## 3. Foundation

| Item | State | Where |
|---|---|---|
| Agent instructions | in place | `AGENTS.md`, `CLAUDE.md` |
| Document hierarchy and authority index | in place | `docs/architecture/INDEX.md` |
| Decisions | CPD-0001, CPD-0002 `ACTIVE` | `docs/decisions/` |
| Naming contract — lexical rules for corpus, generation, provenance class, `country_id`, `outlet_id`, `release_id`, schema ids | implemented and unit-tested | `src/coprepan/naming.py`, `tests/test_naming.py` |
| Naming contract — serialisation of fetch, document, version, unit, sentence, token ids | **not implemented**; target forms only | naming §5.4 |
| Stage-status self-check | implemented | `tests/test_repository_contract.py` |
| Test guards (no network, no storage root, suite membership) | implemented | `tests/conftest.py` |
| Storage-target configuration | logical roles only; **no root configured, no resolver code** | `config/storage_targets.yml` |
| Release gate suite | scaffold; **contains no test** | `tests/suites/release_gate.txt` |
| Git | initialised 2026-10-07 on operator brief: branch `main`, remote `origin` = `https://github.com/FTacke/coprepan.git`; no history taken over from the legacy repository | [closure run report](agent-runs/2026-10-07_coprepan-repository-migration-closure.md) |
| Legacy freeze `coprepan-legacy-2026-06` | **not executed** | `docs/legacy/INDEX.md` §5 |

## 4. Production stack

None. No model, provider, crawler, extractor or annotator is active. The NLP pins in
`pyproject.toml` `[tool.coprepan.nlp]` are marked `PLANNED`: they are not installed and not used.

No external API is used by any code in this repository.

## 5. Open gates blocking production crawling

| Gate | State | Owner |
|---|---|---|
| Acquisition policy decided, implemented, tested (O-1) | open | operator / institution |
| Crawler identity and contact (O-2) | open | operator / institution |
| Preservation target (O-3) | open | operator / institution |
| Storage capacity (O-4) | open | operator / institution, then measured |
| Phase-1 core gate (promotion, idempotence, conflict, crash recovery) | open — nothing built | engineering |
| Phase-2 canary gate | open — nothing built | engineering |

Full list: [master plan](plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) §13.

## 6. Validation debt

Everything. No extraction, annotation, enrichment or release has been validated, because none
exists. The first validations are defined by the gates of Phases 1–4 (master plan §11).

## 7. Machine-readable assertions

Consumed by `tests/test_repository_contract.py`. The test compares this block with
`src/coprepan/stages.py` and enforces the axis rules of §1. **Update this block, the tables above
and the code in the same run** as any change of state; a state is never raised here without the
run report that carries the evidence.

<!-- status_assertions:begin -->
```json
{
  "schema": "coprepan-status-assertions/v1",
  "as_of": "2026-10-06",
  "production_pipeline_exists": false,
  "external_api_in_production_path": false,
  "git_initialised_by_bootstrap": false,
  "stages": {
    "outlet_registry":       {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "discovery":             {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "fetch":                 {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "raw_preservation":      {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "document_identity":     {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "extraction":            {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "admission_labels":      {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "normalisation":         {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "nlp":                   {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "enrichment":            {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "release":               {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"},
    "cross_corpus_contract": {"implementation": "NOT_STARTED", "validation": "NOT_VALIDATED", "activation": "INACTIVE"}
  },
  "open_production_gates": ["O-1", "O-2", "O-3", "O-4", "PHASE_1_CORE", "PHASE_2_CANARY"]
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
