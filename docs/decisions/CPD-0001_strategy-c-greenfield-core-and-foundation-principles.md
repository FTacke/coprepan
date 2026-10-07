# CPD-0001 — Strategy C: greenfield core, selective legacy reuse, and the foundation principles

| Field | Value |
|---|---|
| Date | 2026-10-06 |
| Status | `ACTIVE` |
| Decided by | the operator, in the brief of the repository-foundation bootstrap run (2026-10-06), on the evidence and recommendation of the architecture audit of the same day. Recorded by that bootstrap run; the wording of this record is subject to the operator's review that follows the bootstrap. |
| Kind | architecture · policy |
| Scope | how COPREPAN 3.0 is built, how the legacy system and corpus are treated, and the principles every later stage is built on |
| Builds on / amends / supersedes | — (first decision) |
| Does not change | anything in the legacy repository, the legacy corpus, the cross-corpus studies repository or `corapan_playground` |
| Run report | [`docs/agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md`](../agent-runs/2026-10-06_coprepan3-repository-foundation-bootstrap.md) |
| Evidence | Architecture, Migration, Corpus Supply & Naming Audit, 2026-10-06 — in `corapan_playground`, `docs/agent-runs/2026-10-06_coprepan3-architecture-and-migration-audit.md` ("audit") |

This is a decision about direction and principles. It **implements nothing and activates
nothing**; see [`docs/STATUS.md`](../STATUS.md).

## Context

The audit examined the legacy press system against the current state of CO.RA.PAN 3.0 and the real
use made of both corpora by the cross-corpus studies. Its findings, in short (audit §1.2, §4):

- the legacy system keeps no source bytes, no fetch record and no persistent run state, and its
  identity is a raw feed URL — these properties have no place in its data model, so they cannot be
  added without replacing its core;
- its extracted text is systematically and only partly reversibly damaged;
- its outlet and feed knowledge, section vocabulary and annotation-runner design are real assets;
- no press material is contemporaneous with either radio corpus, and every month without
  preservation-grade crawling is press output that is only partly recoverable later.

## Decision

### §1 Strategy C

COPREPAN 3.0 gets a **new greenfield core in a new repository**. Good legacy components and
curated knowledge are **taken over selectively**. The legacy corpus **stays separate** and is never
silently declared V3 material. *Rebuild the acquisition, preservation, identity and extraction
core; carry over the knowledge, not the architecture.*

The legacy system keeps running unchanged, if the operator runs it at all, until the new one has
passed its own gates. There is no big-bang switch.

### §2 Legacy

1. The legacy repository becomes a **read-only behaviour and data reference**.
2. The legacy corpus is to be **frozen** as one named, hash-manifested release,
   `coprepan-legacy-2026-06`, exactly as the studies read it. It remains scientifically usable and
   remains the reproducibility basis of the existing studies.
3. It is **not `native_v3`**. It is not migrated into 3.0 as corpus, not re-annotated in place and
   not overwritten.
4. Provenance classes `native_v3`, `legacy_refetched`, `legacy_text_reannotated`, `legacy_frozen`
   keep the generations apart in every release.
5. A re-fetch canary and any re-annotation of legacy text are later, optional and separately gated.

Detail: [`docs/legacy/INDEX.md`](../legacy/INDEX.md).

### §3 Preservation-first

The primary raw object is a reconstructable fetch with its exact response bytes — request,
response envelope, body hash, discovery provenance, policy context. Extraction, normalisation and
NLP are derived layers; **no derived layer may be the only copy of a source**. Sealed WARC packs
are the target container. Storage follows roles resolved fail-closed from the environment, with
atomic, idempotent, conflict-refusing promotion.

Detail: [`docs/storage/INDEX.md`](../storage/INDEX.md).

### §4 Separated stages; labels, not deletion; selection at release

Acquisition, preservation, transformation, annotation, enrichment, admission and release are
separate stages with separate, ledgered state. There is no monolithic crawl process. Quality gates
are **admission labels**; nothing is discarded at crawl or extraction time. Selection and balancing
are versioned views at release time.

Detail: [`docs/architecture/TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md).

### §5 Coverage by design; preserve first, balance later

Supply is planned and monitored per `country × outlet × corpus cohort`, with several independent
outlets per country across publisher groups and outlet types, and continuous temporal coverage.
Targets orient acquisition; they are neither quotas nor admission gates.

Detail: [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md).

### §6 One NLP instrument contract with CO.RA.PAN 3.0

COPREPAN 3.0 uses, as far as scientifically sensible, the CO.RA.PAN 3.0 pins, token schema and
verbal-complex layer. A pin change is a joint, forward-only change decision. Modality differences
(sentence segmentation, the unit above the sentence, masking) are declared, not standardised away.

### §7 Classical first; LLM only on demonstrated net benefit

No LLM stage is part of the foundation path. Deterministic or classical methods are the default;
an LLM layer is activated only when it shows a clear, reproducible net benefit against a realistic
baseline on human gold. No external model API in a production path.

Detail for §6–§7: [`docs/nlp/INDEX.md`](../nlp/INDEX.md).

### §8 Methodological governance

Diagnosis, implementation, scientific validation and production activation are four different
acts. Frozen evidence is immutable; negative and historical results are preserved; versions are
forward-only and backfill is a decision; no number is invented; no production activation happens
while a relevant gate is open.

Detail: [`AGENTS.md`](../../AGENTS.md),
[`docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md`](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md).

### §9 Cross-corpus goal

Together with CO.RA.PAN 3.0 the corpus forms one research infrastructure for `spoken + unscripted`,
`spoken + scripted` and `written + edited`. The raw data models stay modality-specific; only a
shared analysis contract is common. The existing studies' workarounds are requirements on that
contract, not its blueprint.

Detail: [`docs/plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md`](../plans/COPREPAN3_FOUNDATION_MASTER_PLAN.md) §9.

## Alternatives considered

| Alternative | Why not (audit §1.2, §1.3) |
|---|---|
| **A — in-place upgrade** of the legacy system | The four properties a V3 press pipeline rests on (source object, fetch record, persistent state, sound identity) have no place in the legacy data model. Adding them replaces the system minus its dashboard, while carrying four export layouts, three URL normalisers and dead exporters — and keeps mutating the directory the studies read. |
| **B — pure greenfield**, discarding the legacy system | The outlet list with its feed-discovery history, the section vocabulary and the annotation runner's provenance design are real assets and expensive to recreate. |

## Consequences

- Build order and gates: master plan §11. Phases 0–2 (decisions, legacy freeze, core,
  acquisition and preservation) have priority over all other legacy work.
- Production crawling is blocked by two institutional answers — acquisition policy and
  preservation target/capacity — not by engineering (master plan §13).
- Results on the legacy corpus carry its documented limitations until a re-fetch canary measures
  their size.

## Not decided here

The acquisition, robots and opt-out policy; crawler identity and contact; the preservation target
and its capacity; the population of admitted press types; the country list shared with CO.RA.PAN;
the name of the shared cross-corpus namespace; release and freeze semantics; the WARC library and
pack parameters; the byte-level serialisation of ids; whether `corapan_playground` storage code is
consumed as a dependency. All are listed with their owner in master plan §13.
