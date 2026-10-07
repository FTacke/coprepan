# COPREPAN 3.0

Development repository of **COPREPAN 3.0**, the preservation-first pipeline for the **CO.PRE.PAN**
press corpus: Spanish-language online press across the Spanish-speaking countries, built to be
analysed together with the radio corpus CO.RA.PAN 3.0.

> **Status: acquisition pipeline built and tested offline; not activated.** This repository holds
> rules, architecture, decisions and the path from channel discovery through HTTP fetch, raw
> preservation, document identity and extraction to replay — exercised end to end against a
> loopback server with synthetic documents. **Nothing has been requested from a real site and
> nothing can be as committed: the acquisition policy is undecided, the crawler identity is not
> configured and no outlet is registered. No corpus material exists; nothing is validated or
> activated.**
> See [`docs/STATUS.md`](docs/STATUS.md).

## Where to start

| Question | Read |
|---|---|
| What are the rules for working here? | [`AGENTS.md`](AGENTS.md) |
| What exists today? | [`docs/STATUS.md`](docs/STATUS.md) |
| Which document is authoritative for what? | [`docs/architecture/INDEX.md`](docs/architecture/INDEX.md) |
| What is being built? | [`docs/architecture/TARGET_ARCHITECTURE.md`](docs/architecture/TARGET_ARCHITECTURE.md) |
| What do the terms and ids mean? | [`docs/architecture/TERMINOLOGY_AND_NAMING.md`](docs/architecture/TERMINOLOGY_AND_NAMING.md) |
| In which order, behind which gates, and what is still undecided? | [`docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md`](docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) |
| What has been decided? | [`docs/decisions/README.md`](docs/decisions/README.md) |
| What about the existing press corpus? | [`docs/legacy/INDEX.md`](docs/legacy/INDEX.md) |

## The idea in five lines

1. **Strategy C** — a new core; good legacy knowledge carried over selectively; the legacy corpus
   frozen and kept separate.
2. **Preservation-first** — the raw object is the fetch with its exact bytes; text is derived.
3. **Label, don't delete; preserve first, balance later** — selection happens in versioned release
   views.
4. **One NLP instrument with CO.RA.PAN 3.0** — modality differences declared, not hidden.
5. **Classical first** — an LLM layer only on demonstrated net benefit against a real baseline.

## Layout

```text
AGENTS.md              agent and developer rules (CLAUDE.md points here)
docs/
  STATUS.md            what exists: planned / implemented / validated / activated
  architecture/        authority index, target architecture, terminology and naming
  decisions/           decision registry, CPD-<nnnn> records
  plans/               the foundation master plan
  methodology/         transformation and validation principles
  storage/             preservation, storage roles, provenance
  corpus_supply/       supply model, registry attributes, monitoring
  nlp/                 NLP instrument contract, enrichment, LLM policy
  legacy/              rules for the legacy system and corpus; its archaeology
  identity/            id serialisation, canonical URL key, identity tables
  acquisition/         run, discovery, fetcher, policy gate, crawler identity, fetch record, pack
  extraction/          extraction record, blocks, metadata, replay
  agent-runs/          one dated report per run
config/                logical configuration (no absolute paths); the outlet registry (a proposal,
                       nothing registered) with its review package; the acquisition policy
                       (undecided) and the crawler identity (not configured)
src/coprepan/          package: naming, stage vocabulary, core primitives (identity, registry,
                       ledger, storage roots, promotion, outage spool, layer store), the pipeline
                       (acquisition, discovery, robots, policy, crawler identity, fetcher, pack,
                       document identity, extraction) and readiness tools (preservation target,
                       capacity, baseline manifest, registry review)
tests/                 contract tests, guards, suite manifests, fixtures, the offline canary
```

Corpus data, raw captures, derived layers and runtime state never live in this
checkout.

## Development

```text
python -m pip install -e ".[dev]"
python -m pytest
```

The tests need no network, no storage root and no model.
