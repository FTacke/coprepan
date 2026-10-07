# COPREPAN 3.0 — Foundation Master Plan

| Field | Value |
|---|---|
| Status | **ACTIVE PLAN** — the authoritative forward plan. A plan, not a description of what exists. |
| Date | 2026-10-06 |
| Decisions it rests on | [CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md), [CPD-0002](../decisions/CPD-0002_terminology-and-naming-model.md) |
| Evidence base | Architecture, Migration, Corpus Supply & Naming Audit, 2026-10-06 (in `corapan_playground`, `docs/agent-runs/2026-10-06_coprepan3-architecture-and-migration-audit.md`; "audit §n") |
| What exists today | [`docs/STATUS.md`](../STATUS.md) — in short: documents, a naming module and tests. No pipeline. |

This plan turns the audit — a diagnostic run report — into the active plan of this repository. The
audit stays a historical record; where this plan and the audit differ, this plan governs. The plan
is amended by dated additions and by decisions, not by silently rewriting history: a phase that is
re-ordered or dropped gets a dated note saying why.

---

## 1. How to read this plan

It summarises and orders. The normative detail lives in exactly one place each:

| Topic | Authoritative document |
|---|---|
| Agent rules | [`AGENTS.md`](../../AGENTS.md) |
| Which document is authoritative | [`docs/architecture/INDEX.md`](../architecture/INDEX.md) |
| Target architecture | [`docs/architecture/TARGET_ARCHITECTURE.md`](../architecture/TARGET_ARCHITECTURE.md) |
| Terms, names, ids | [`docs/architecture/TERMINOLOGY_AND_NAMING.md`](../architecture/TERMINOLOGY_AND_NAMING.md) |
| Storage, preservation, provenance | [`docs/storage/INDEX.md`](../storage/INDEX.md) |
| Corpus supply | [`docs/corpus_supply/INDEX.md`](../corpus_supply/INDEX.md) |
| NLP, enrichment, LLM policy | [`docs/nlp/INDEX.md`](../nlp/INDEX.md) |
| Legacy | [`docs/legacy/INDEX.md`](../legacy/INDEX.md) |
| Transformation and validation method | [`docs/methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md`](../methodology/TRANSFORMATION_AND_VALIDATION_PRINCIPLES.md) |
| Decisions | [`docs/decisions/README.md`](../decisions/README.md) |

## 2. Goal

Build a long-lived, preservation-grade pipeline for the CO.PRE.PAN press corpus — Spanish-language
press across the Spanish-speaking countries — whose every released text can be traced to preserved
source bytes, re-derived from them, and analysed together with CO.RA.PAN 3.0 under one shared
instrument and one shared analysis contract.

What success looks like:

- a released text answers, from stored records alone, where it came from and how it was made;
- an extraction or annotation improvement is a re-run on preserved bytes, not a re-crawl;
- a study pins a release by id and hash;
- a spoken–written contrast is not an instrument artefact, a house style or a period effect that
  nobody can check.

## 3. Scope and non-goals

**In scope**

- Spanish-language online press, per country, from registered outlets, acquired through their
  public channels (feeds, sitemaps, archives).
- Acquisition, preservation, identity, extraction, admission labelling, normalisation, NLP,
  validated enrichment, releases, and the press side of the cross-corpus analysis contract.
- The frozen legacy release and the mapping layer that keeps existing studies reproducible.

**Not in scope of the foundation** (each is a later, explicit decision, not an omission)

- JavaScript rendering, screenshots, e-paper PDFs, linked media.
- An LLM stage of any kind.
- HPC execution.
- A public distribution service or query interface.
- Rewriting finished studies; migrating the legacy annotation into 3.0.

**Never**

- Bypassing an access control (authentication, paywall, bot challenge, rate limit).
- Machine-labelling linguistic variety.
- Modifying the legacy repository, the legacy corpus, the studies repository or
  `corapan_playground` from this repository's work.
- Normalising the published wording.

**Not claimed**: statistical representativeness of "the press of a country". The aim is a
transparent, controlled, documentable supply.

## 4. Strategy C

A new greenfield core; selective reuse of good legacy components and curated knowledge; the legacy
corpus frozen, separate, never silently promoted. Decided: CPD-0001 §1–§2. Not reopened unless new
hard evidence contradicts it.

Why it is safe: the legacy system stays untouched; the new core is narrow first (registry →
discovery → fetch → preservation for a handful of outlets) and adds extraction, NLP and release
behind explicit gates; CO.RA.PAN 3.0 supplies domain-independent mechanisms already proven in
production.

**The time-critical part.** The legacy corpus covers 2025-12 to 2026-06 only and nothing has been
crawled since 2026-06-15; CO.RA.PAN 1.0 covers 2022-01 to 2025-06 and CO.RA.PAN 3.0 acquires from
2026-Q3. No press material is contemporaneous with either radio corpus, and each month without
preservation-grade crawling is press output only partly recoverable later. Phases 0–2 therefore
have priority over every other piece of work.

## 5. Architecture

```text
OUTLET REGISTRY → DISCOVERY → FETCH → RAW PRESERVATION → DOCUMENT IDENTITY → EXTRACTION →
ADMISSION LABELS → NORMALISATION → NLP → VALIDATED ENRICHMENT → RELEASE →
CROSS-CORPUS ANALYSIS CONTRACT
```

Separate stages with separate ledgered state; preservation-first; labels instead of deletion;
selection at release time; write-once layers addressed by id and hash; forward-only versions.
Sealed WARC packs are the target raw container. Detail: target architecture; storage index.

## 6. Naming

Decided: CPD-0002. `corpus_id` `coprepan`; generation `v3` as an attribute; date-based immutable
`release_id`; schema ids `coprepan-<thing>/v<n>`; `country_id` alpha-2 lower case; registry-assigned
`outlet_id`; content-addressed document versions with token and sentence ids hanging on them;
slugs may evolve, ids may not; legacy names never rewritten. Detail: terminology and naming.

## 7. Legacy

Read-only reference. Frozen release `coprepan-legacy-2026-06` planned. Not `native_v3`. Known
extraction and provenance limitations documented. Detail: legacy index.

## 8. Corpus supply, NLP, LLM

- **Supply:** coverage by design per `country × outlet × corpus cohort`; several independent
  outlets per country across publisher groups and outlet types; continuous temporal coverage;
  channel health; publication date with its basis; syndication awareness; **preserve first, balance
  later**. Detail: corpus-supply index.
- **NLP:** the CO.RA.PAN 3.0 instrument contract (pins, token schema, verbal-complex layer);
  modality differences declared, not standardised away. Detail: NLP index §1–§5.
- **LLM:** none in the foundation path; classical first; an LLM layer only on a clear, reproducible
  net benefit against a realistic baseline on human gold. One evaluation candidate: article type /
  genre. Detail: NLP index §7.

## 9. Cross-corpus goal and contract

**Goal.** With CO.RA.PAN 3.0, one research infrastructure for three conditions:

| Condition | Corpus |
|---|---|
| `spoken + unscripted` | CO.RA.PAN |
| `spoken + scripted` | CO.RA.PAN |
| `written + edited` | CO.PRE.PAN |

**Principle.** The raw data models stay modality-specific. Shared is only one **analysis layer**
that each corpus exports to — a versioned contract with closed vocabularies and explicit value
states instead of nulls.

**What the contract must deliver** (target shape, audit §14.2; not designed in detail here):

| Level | Shared content |
|---|---|
| release | `corpus_id`, `release_id`, contract version, manifest with per-file hashes, annotator-contract version, coverage table (country × register × outlet × cohort), selection policy |
| `outlets` | `outlet_id`, outlet kind, `country_id`, display name, city, region, scope, outlet group |
| `documents` | globally unique `document_id`, `corpus_id`, `release_id`, `outlet_id`, `country_id`, region, `modality`, date with `date_basis`, cohort, section / programme fields, `provenance_class`, language, token counts under the shared denominator, duplicate and syndication relations |
| `units` | declared `unit_kind`; production mode; producer id and role with value states; scope status with reason |
| `sentences`, `tokens` | stable ids, parent ids, order index, the shared token schema, medium-typed anchors (`char_start`/`char_end` or `start_ms`/`end_ms`); sentence neighbours addressable by id |
| derived layers | separate tables keyed on token or unit ids, each with its rule version |
| compatibility view | `register_group` with the legacy study values, alpha-3 labels, legacy slugs — an alias layer, never canonical values |

Per measure family the contract states whether it is comparable across modalities.

**The existing studies are evidence, not a blueprint.** Each workaround they carry is a requirement
on the contract (audit §14.1):

| Workaround observed in the studies | Requirement |
|---|---|
| cluster id built as `source_file|article_id` because 101 ids repeat across daily files | one globally unique document id; explicit duplicate relation |
| region derived by splitting the country code on a hyphen | national code and region as separate delivered fields |
| data facts (sparse cells) hard-coded in library code | a published coverage table per release |
| the daily export file used as "crawl batch"; the file date used as press date | container kept apart from document; dates with declared semantics |
| defensive `morph` parsing (dict, list or delimited string) | one typed token schema |
| `segment_id` meaning utterance in radio and paragraph in press | declared unit kinds |
| asymmetric counting rule because a tense feature is often missing | one rule version, applied consistently in both corpora |
| sentence context re-fetched by rescanning the corpus | sentence-neighbour access by id |
| no study pins its corpus input; corpus paths are absolute | releases pinned by id and manifest hash |
| scope constants duplicated with different names | a closed scope vocabulary delivered with the data |

**Joint design.** CO.RA.PAN 3.0 has neither a token/sentence export table nor a release/freeze
concept yet. Both are designed **once, jointly** — COPREPAN neither waits for them nor invents them
alone. Contract design can start in parallel with Phase 3.

## 10. Gates

A gate is a named condition with evidence, checked before a transition. The transitions that
matter:

```text
PLANNED → IMPLEMENTED → VALIDATED → ACTIVE
```

- *Implemented*: code and tests exist and pass. Says nothing about quality on real material.
- *Validated*: measured against the stated gate on real or gold material, with a run report.
- *Active*: switched on for corpus material by an explicit decision.

Rules:

1. **No production activation while a relevant gate is open.** "Relevant" is stated per phase
   below; an institutional gate (§13) is as binding as a technical one.
2. A gate is passed by evidence, recorded in a run report and reflected in `docs/STATUS.md`. It is
   never passed by argument, by elapsed time or by a later stage working anyway.
3. A gate is not weakened to make something pass. If a gate turns out to be wrong, changing it is a
   decision with its own record.
4. A numeric threshold in a gate follows the hard-gate rule (methodology §4).
5. The release gate is a test suite (`python -m pytest --suite release_gate tests`) that every
   production change must pass. It is empty today because there is nothing to release.

## 11. Phases

Classes: **F** required for the V3 foundation · **C** required before production crawling · **S**
required before scientific use · **O** optional optimisation · **R** future research enhancement.

### Phase 0 — Decisions, naming freeze, legacy freeze

| | |
|---|---|
| Goal | fix what everything else builds on; make the legacy corpus safe |
| Done by the bootstrap (2026-10-06) | repository, instructions, document hierarchy; CPD-0001 (strategy C and principles); CPD-0002 (naming model); decision registry and namespace [F] |
| Open deliverables | legacy freeze `coprepan-legacy-2026-06`: hash manifest, preserved copy, restore check [F]; preservation target and capacity decision [C]; acquisition policy statement — robots and opt-out handling, crawler identity and contact, retention of raw copies [C]; complete legacy-slug → `outlet_id` mapping (delivered with the Phase-1 registry import) [F] |
| Gate | manifest verified against the live legacy tree; a study loader reads the frozen copy with identical results on a sample |
| Blocked by | O-3 (preservation target) for the preserved copy; O-10 (go-ahead) for the manifest |

### Phase 1 — Core infrastructure

| | |
|---|---|
| Goal | the skeleton every stage uses |
| Prerequisite | CPD-0002 (met) |
| Deliverables [all F] | id serialisation and canonical URL key with property tests, frozen by a CPD; outlet registry schema with the legacy outlets imported and aliased; ledger and state-machine primitives; storage-root resolution (fail-closed) and promotion semantics; layer store (write-once, fingerprint / artifact id); runtime-workspace separation; release-gate suite scaffold; stage-status self-check |
| Gate | promotion, idempotence, conflict and crash-recovery tests pass — first on temporary directories, then **on a real preservation target** (needs O-3) |
| Deliberately later | any network access |

### Phase 2 — Acquisition and preservation

| | |
|---|---|
| Goal | preserve press material for a small set of outlets, correctly |
| Deliverables [F/C] | discovery with index expansion and channel-document preservation; polite fetcher with per-outlet policy; sealed packs, promotion, fixity, reconciliation; document identity; supply snapshot |
| Gates | (1) canary on about five outlets from different countries and outlet types: every fetch traceable to a preserved body; restore test passes; **measured bytes per fetch replace the scenario assumptions**; (2) the acquisition policy is decided, implemented and tested; (3) only then scheduled crawling for the qualified outlets |
| Blocked by | O-1, O-2 (policy, crawler identity) before the first live fetch; O-3, O-4 (target, capacity) before scheduled crawling |
| Risks | bot protection and paywalls reduce the reachable set; capacity |
| Deliberately later | extraction quality, JavaScript rendering, PDFs |

### Phase 3 — Extraction and admission labels

| | |
|---|---|
| Goal | text of known quality from preserved bytes |
| Deliverables [S] | extractor with typed blocks; metadata with basis; admission labels; language identification; an extraction gold sample stratified by outlet; a preregistered comparison of extractor candidates |
| Gate | evaluation-plan checklist answered; net-benefit result against the legacy extractor on the same pages; replay determinism |
| Deliberately later | per-outlet rules beyond the outlets in production |

### Phase 4 — NLP and enrichment

| | |
|---|---|
| Goal | annotation under the shared contract |
| Deliverables | annotator with the CO.RA.PAN pins and token schema; verbal-complex layer; columnar token tables; section mapping v2; syndication clusters [S]; the article-type evaluation [S for studies crossing register with genre, otherwise R] |
| Gate | annotation equivalence with CO.RA.PAN 3.0 on a shared text sample; bridge sample relating `tense-v3` to the verbal-complex layer |
| Deliberately later | quotation spans, topic labels, LCP on press [R] |

### Phase 5 — Legacy

| | |
|---|---|
| Goal | settle what the legacy window is worth |
| Prerequisites | Phases 2–4 running |
| Deliverables | re-fetch canary with a reachability and text-drift report and a measured size of the legacy extraction defects [S for anyone still publishing on legacy data]; decision on a full `legacy_refetched` backfill; `legacy_text_reannotated` only on a study's request [O] |
| Never | in-place changes to the legacy tree |

### Phase 6 — Supply expansion

| | |
|---|---|
| Goal | coverage by design |
| Deliverables | outlet attributes completed; orientation targets frozen with their rationale; qualification of additional outlets by priority; archive backfill by census → select → arm → run → reconcile [C per outlet; S for coverage claims] |
| Gate per outlet | qualification evidence, policy check, capacity check |
| Depends on | O-5 (population, country list) |

### Phase 7 — Cross-corpus interface and studies

| | |
|---|---|
| Goal | one analysis layer, pinned inputs |
| Deliverables [S] | the contract, designed jointly with CO.RA.PAN 3.0; first frozen CO.PRE.PAN release of `native_v3` material; contract export; a study template that pins `release_id` and manifest hash; the studies' shared library moved to the contract **for new studies** |
| Deliberately later | rewriting finished studies |
| Depends on | O-6 |

Order note: the contract design of Phase 7 can start in parallel with Phase 3.

## 12. Immediate sequence

1. **Operator review** of this foundation (instructions, CPD-0001, CPD-0002, this plan).
2. **Git initialisation** by the operator. The bootstrap created no git metadata.
   *Done 2026-10-07 on operator brief — see `docs/STATUS.md` §3 and §8.*
3. **Next technical run — Foundation Core I** (Phase 1, no network, no live storage root):
   1. freeze the id serialisation and the canonical URL key — code, property tests, a CPD;
   2. outlet registry schema and a read-only import of the legacy outlets and channels from a
      *copy* of the legacy database, with every observed slug variant as an alias and the
      legacy-slug → `outlet_id` mapping as reviewable output;
   3. ledger and state-machine primitives (ledger before state; illegal transition raises);
   4. storage contracts: fail-closed root resolution and promotion semantics, tested on temporary
      directories;
   5. write-once layer store with fingerprint and artifact id;
   6. release-gate suite scaffold and the stage-status self-check.

   Cut line: if the run is too large, items 5–6 move to a Foundation Core II run; items 1–4 are the
   minimum that later work cannot start without.
4. In parallel, on the operator's side: O-1 to O-4 and O-10 (§13). They gate the legacy freeze and
   Phase 2, not Foundation Core I.

## 13. Open operator and institutional decisions

Only questions that code and data cannot answer. **None is guessed here.** None blocks Foundation
Core I.

| ID | Question | Kind | Blocks | Evidence |
|---|---|---|---|---|
| **O-1** | **Acquisition policy.** Which robots and opt-out signals bind the crawler (CO.RA.PAN 3.0 treats `robots.txt` as recorded advisory evidence under a research policy and never bypasses technical access controls; whether press acquisition follows that is undecided). Whether full raw copies may be retained long-term, and who may access them. | institutional / legal | any live fetch; Phase 2 gate (2) | audit T-7, §21 Q-1: the legacy system configured one robots behaviour and implemented another |
| **O-2** | **Crawler identity and contact.** User agent, contact address, the public statement a publisher can find. The legacy user agent carried a placeholder address. | institutional | any live fetch | audit T-7 |
| **O-3** | **Preservation target.** Own allocation, or shared with CO.RA.PAN. | institutional | legacy freeze (preserved copy); Phase 1 gate on a real target; Phase 2 | audit §8.5, Q-2 |
| **O-4** | **Storage capacity.** No measured rate exists; the scenario range is about 110–550 GB of raw material per year, and the CO.RA.PAN share cannot carry both. | institutional, then measured by the Phase-2 canary | scheduled crawling | audit §8.5 |
| **O-5** | **Corpus population.** (a) Which outlet types count as "press" for the default release — digital-native outlets, broadcaster websites, state and official outlets, agencies. (b) Whether both corpora share one country list — Puerto Rico (press only so far), the United States (radio only), Equatorial Guinea (radio target). | scientific | Phase 6; default release view | audit Q-3, Q-4 |
| **O-6** | **Cross-corpus contract naming and semantics.** Name of the shared namespace (working name `crosscorpus-`); name of the shared register field (working name `production_mode`; CO.RA.PAN calls its dimension `speech_mode`); token denominator; release and freeze semantics. | joint with CO.RA.PAN 3.0 | Phase 7 | audit §14, §16; CO.RA.PAN open items |
| **O-7** | **Publication branding** of the generation: "COPREPAN 3.0" or "CO.PRE.PAN 3.0". Changes no identifier. | operator style | nothing | naming §1 |
| **O-8** | **Code relationship to `corapan_playground`.** Consume its storage / change-decision / accounting modules as a pinned dependency after generalisation there, or keep own implementations against the same on-disk contracts. | technical, operator | nothing now; revisit in Phase 1 | audit §18 |
| **O-9** | **Existing backup of the legacy data.** Whether any copy exists outside the legacy working copy. Changes the urgency of the freeze, not its necessity. | factual, operator knowledge | nothing | audit Q-5 |
| **O-10** | **Go-ahead for the legacy freeze manifest.** The hash manifest reads the legacy tree only and needs no preservation target; it may run before O-3 is answered. | operator | Phase 0 closure | legacy index §5 |

## 14. Validation still owed

Nothing in this repository is validated. The validation plan by kind of claim (reproducibility,
robustness, replicability, generalisability) is in methodology §9; each item becomes real only
with a run report and an entry in `docs/STATUS.md`.
