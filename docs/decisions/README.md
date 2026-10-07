# Decision Registry

This directory holds **decisions that have actually been made**. Planning ideas, proposals,
examples and open questions belong in `docs/plans/` or in a component index and are never promoted
to a decision implicitly. Do not manufacture a decision record from an open planning note, and do
not record a recommendation of a run report as a decision: a decision needs the operator.

## Namespace

COPREPAN decisions are numbered **`CPD-<nnnn>`** (four digits, sequential, never reused). The
prefix keeps them apart from CO.RA.PAN's `D<nn>` sequence: a bare `D67` in this repository always
means a CO.RA.PAN decision, cited as a reference.

File name: `CPD-<nnnn>_<short-kebab-title>.md`. The date lives inside the record.

## Registry

| ID | Date | Decision (short) | Status | Supersedes / superseded by | Record |
|---|---|---|---|---|---|
| CPD-0001 | 2026-10-06 | Strategy C: greenfield core, selective legacy reuse, legacy corpus frozen and separate; the foundation principles (preservation-first, stage separation, labels not deletion, selection at release, shared NLP instrument, classical-first / LLM on net benefit) | `ACTIVE` · implementation `NOT_STARTED` | — | [CPD-0001](CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) |
| CPD-0002 | 2026-10-06 | Terminology and naming model: levels, human-facing style, machine ids, forward-only legacy naming | `ACTIVE` · implementation `PARTIAL` (lexical rules in `src/coprepan/naming.py`) | — | [CPD-0002](CPD-0002_terminology-and-naming-model.md) |
| CPD-0003 | 2026-10-07 | Id serialisation (SHA-256 over canonical JSON; `ft1:` fetch ids; 16/12-digit document and version hashes; zero-based unit, sentence and token indexes) and the canonical URL key rule set `coprepan-url-key/v1` | `ACTIVE` · implementation: serialisation and key `IMPLEMENTED` in `src/coprepan/identity.py`; no id minted, identity stage `NOT_STARTED` | builds on CPD-0002 | [CPD-0003](CPD-0003_id-serialisation-and-canonical-url-key.md) |
| CPD-0004 | 2026-10-07 | Legacy component dispositions: per component, separately for concept, implementation and data — nothing reused as is; the outlet and feed lists are data only; extractor, crawl loop, article store, export routing and `article_id` discarded | `ACTIVE` | refines CPD-0001 §2 and legacy index §6 | [CPD-0004](CPD-0004_legacy-component-dispositions.md) |
| CPD-0005 | 2026-10-07 | Core pipeline contracts: outlet as source entity; acquisition run; fetch record; WARC pack with derived, bound index; five identities (an article is not its URL); extraction record with typed blocks and basis-carrying metadata; layers RAW / EXTRACTED / ANNOTATED / RELEASE | `ACTIVE_WITH_VALIDATION_DEBT` · implementation `PARTIAL` (recorded exchanges only; baseline extractor not adopted) | builds on CPD-0001 to CPD-0003; amended in three points by CPD-0006 §1 | [CPD-0005](CPD-0005_core-pipeline-contracts.md) |
| CPD-0006 | 2026-10-07 | Discovery (events and candidates as evidence, bounded expansion); HTTP transport (policy before transport, one record per attempt, explicit retries); crawler identity (no default); policy gate (nothing allowed by default; robots as evidence); readiness contracts (preservation target, capacity model, baseline manifest). Amends CPD-0005: `fetch_kind`, the stored body, observation keys. Audit: CPD-0004 kept | `ACTIVE_WITH_VALIDATION_DEBT` · implementation `PARTIAL` (offline only; external acquisition not activatable as committed) | amends CPD-0005 §3–§4 | [CPD-0006](CPD-0006_discovery-transport-policy-gate-and-readiness.md) |
| CPD-0007 | 2026-10-07 | Legacy freeze manifest (bytes only, `MANIFEST_ONLY`); candidate qualification (versioned rules, rejected is not deleted); candidate lifecycle derived from history and a pure fetch plan with no built-in pace; conditional requests (a 304 invents no body; a validator is never an identity); permanent redirects move a candidate; robots `Sitemap:` as an optional source, `Crawl-delay` as evidence; channel health as a derived report that switches nothing; technical admission labels; extractor lifecycle; extraction evaluation harness and review package (diagnostics, no gold); canary planner and fail-closed preflight | `ACTIVE_WITH_VALIDATION_DEBT` · implementation `PARTIAL` (offline only, except the legacy manifest, which ran on the real legacy tree) | builds on CPD-0005, CPD-0006; settles two open items of CPD-0006 | [CPD-0007](CPD-0007_refetch-qualification-admission-labels-and-evaluation-instruments.md) |
| CPD-0008 | 2026-10-07 | Cross-corpus analysis contract `crosscorpus-analysis/v1` as COPREPAN's technical proposal: an analysis layer, not a common data model; namespace `crosscorpus-`; shared field `production_mode` (spoken values of `speech_mode` unchanged, press `written_edited`, never mapped onto each other); five value states, no bare null; typed token schema with id-valued heads and plain-UD `morph`; no unit kind is an utterance; token denominator `crosscorpus-token-denominator/v1`; manifest-pinned releases; compatibility view never canonical. Phase-3 layer architecture: BODY as primary linguistic surface, normalisation never changes wording, language / section / production mode / genre / opinion kept apart | `ACTIVE_WITH_VALIDATION_DEBT` · implementation `PARTIAL` (validator, COPREPAN adapter, synthetic fixtures). **Binds COPREPAN only; for CO.RA.PAN a proposal (O-6 joint decision open)** | builds on CPD-0001 to CPD-0003, CPD-0005, CPD-0007; fixes the namespace CPD-0002 left open | [CPD-0008](CPD-0008_cross-corpus-analysis-contract-and-phase3-layer-architecture.md) |

## Status vocabulary

One vocabulary, used in the registry and in the record header:

| Status | Meaning |
|---|---|
| `ACTIVE` | in force |
| `ACTIVE_WITH_VALIDATION_DEBT` | in force; a named validation is still owed and is listed in `docs/STATUS.md` |
| `DIRECTION_NOT_STARTED` | decided as a direction; nothing built on it yet may assume its details |
| `PARTIALLY_SUPERSEDED` | some clauses replaced by a later decision, named in the registry |
| `SUPERSEDED` | replaced by a later decision; kept as the historical record |
| `REJECTED` | considered and decided against; kept so the alternative is not re-proposed blind |
| `HISTORICAL` | no longer applicable; never deleted |

A decision's **status** says whether it is in force. Whether it is **implemented, validated or
activated** is a different question, answered in [`docs/STATUS.md`](../STATUS.md). The registry
carries an `implementation` note only as a pointer.

## Rules

1. **A record is immutable once `ACTIVE`.** A change is a new decision that supersedes or amends
   the old one; the old record gets a dated status line and a forward link, nothing else. Typos
   and broken links may be fixed.
2. **Allocate the number in the registry table first**, in the same commit as the record. If two
   parallel sessions take the same number, the one that reaches `main` second renumbers and adds a
   `Numbering:` note to its record; artefacts frozen under the working label keep that label as
   provenance and are not rewritten. (CO.RA.PAN's sequence has collided this way more than once.)
3. A decision cites its **evidence** (run report, measurement, audit section) and its **run
   report**. A decision without evidence is an opinion.
4. A decision states **what it does not decide** and what it leaves open.
5. When a decision changes what is authoritative, the same run updates
   [`docs/architecture/INDEX.md`](../architecture/INDEX.md), the affected component index and, if
   it changes the state of a stage, [`docs/STATUS.md`](../STATUS.md).
6. A **change decision** in the sense of forward-only evolution (reprocessing existing artefacts
   under a new version; methodology §11) is a CPD record with the additional fields: affected
   stages and cohort, change class, cause, analytic consequence without reprocessing, cost,
   invalidated and reusable artefacts, bridge validation, operator approval.

## Record template

```markdown
# CPD-<nnnn> — <title>

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Status | `ACTIVE` |
| Decided by | <operator / who approved> |
| Kind | architecture · naming · policy · stack · change decision |
| Scope | <what it governs> |
| Builds on / amends / supersedes | <CPD ids or —> |
| Does not change | <what stays as it is> |
| Run report | <link> |
| Evidence | <links> |

## Context
## Decision
## Alternatives considered
## Consequences
## Not decided here
```
