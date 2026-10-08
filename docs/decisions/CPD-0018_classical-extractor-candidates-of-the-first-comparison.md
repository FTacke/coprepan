# CPD-0018 — The classical extractor candidates of the first comparison, their pins and wrappers

| Field | Value |
|---|---|
| Date | 2026-10-08 |
| Status | `ACTIVE_WITH_VALIDATION_DEBT` |
| Decided by | the operator, in the briefs of the canary runs of 2026-10-08: where the candidate list is only a survey, the run may select the candidates technically, install, pin and wrap them and run them offline on the preserved bodies, documenting criteria and versions, with no selection by human gold. Recorded by that run; subject to the operator's review |
| Kind | architecture · method |
| Scope | which third-party tools enter the first extractor comparison beside the baseline, in which version, through which wrapper, and where they live |
| Builds on / amends / supersedes | builds on CPD-0001 (classical first), CPD-0005 §5–§6 (extraction record), CPD-0007 §9–§10 (lifecycle, harness). Turns [`EXTRACTOR_CANDIDATES.md`](../extraction/EXTRACTOR_CANDIDATES.md) from a survey into a selection (its §6). Supersedes nothing |
| Does not change | the extraction record schema; `baseline_html/0.1.0` and its lifecycle (`EXPERIMENTAL`); the package's runtime dependencies (none); the gold-sample design; the review codebook |
| Run report | [`docs/agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md`](../agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md) |
| Evidence | `tests/test_extractor_candidates.py`; the package manifest under `docs/extraction/phase3/phase3-pilot-canary-2026-10-08/` |

Validation debt: the wrappers have run on one synthetic page and on thirteen real pages of one outlet. Nothing
about the quality of any candidate is known. No candidate is adopted, validated or even `CANDIDATE` in the sense
of the lifecycle: there is no preregistered comparison yet.

## Context

The candidate list of 2026-10-07 was written from general knowledge: nothing installed, no version confirmed. A
comparison needs named tools in exact versions, each mapped to the extraction record, and a statement of what the
mapping loses.

## Decision

### 1. The candidates

| Arm | Tool, version (from the package index, read 2026-10-08), licence as the distribution states it | Method family |
|---|---|---|
| `baseline_html/0.1.0` | this repository | first-container rule — the floor |
| `trafilatura/2.3.1.w1` | trafilatura 2.3.1, Apache-2.0 | heuristic main-text extraction with metadata and internal fallbacks |
| `readability_lxml/0.9.w1` | readability-lxml 0.9, Apache-2.0 | Readability container scoring |
| `justext/3.0.2.w1` | jusText 3.0.2, BSD 2-Clause | paragraph classification by stop-word and link density, Spanish stop list |

### 2. Why these, and why not the others

Criteria, all technical and all applied before any output was looked at: runs offline on a string with no request of
its own; deterministic for a pinned version (each arm runs twice per case in the harness); a release on the package
index that installs on the project's Python; a licence the distribution states; and — across the set — three
different method families, so that the comparison is not three variants of one idea.

Not entered: goose3 and newspaper (the list's open questions on maintenance and determinism were not answered here, and
newspaper fetches by itself by default); boilerpy3 (the same family of shallow text features as jusText, last release
1.0.7, no metadata); resiliparse / inscriptis (renderers, not extractors); extruct (metadata only; the baseline reads
the same sources); per-outlet rules (they need a template to be studied, which is what a reviewer does first); the
legacy extractor (an operator-ordered task with its own environment, [candidates](../extraction/EXTRACTOR_CANDIDATES.md)
§4). None of these is rejected for good: each can enter a later comparison as a further arm.

### 3. Where the tools live

They are **not runtime dependencies**. `pyproject.toml` names them in an extra, `phase3`, with exact pins; they are
installed in an environment of their own. Only `src/coprepan/extractor_candidates.py` imports them, inside the wrappers,
and a wrapper refuses to run on any version but its pin. What the tools pull in (lxml and others) is not pinned in
the repository: every comparison stores the full list of what was installed beside its results.

### 4. The wrappers (`w1`)

Every wrapper treats the input the same way, so that the arms differ in extraction only: the preserved body is checked
against its digest, its content coding is undone and its characters are decoded by the baseline's own rules, and the
decoding is recorded; the tool gets that text and **no address**; what the baseline refuses as not HTML is refused with
the same reason. The output is an extraction record of the existing schema with one added field, `candidate` (tool,
version, parameters, what the mapping loses). A metadata value a tool reports carries the basis `unknown`: the tools do
not say where on the page they took it from. Parameters are the tools' defaults except: trafilatura without comments,
with tables, XML output, and a fixed latest admissible date (the tool validates dates against "today" by default,
which would make its answer depend on the day it runs); jusText with the Spanish stop list.

What each mapping loses is written in the module (`MAPPING`) and in every record. It counts in a comparison.

### 5. Lifecycle

All three wrappers are `EXPERIMENTAL`, like the baseline, and none is in the registry of extractors of the pipeline
(`extraction.EXTRACTORS`). They become `CANDIDATE` when a comparison is preregistered.

## Alternatives considered

| Alternative | Why not |
|---|---|
| install the tools into the package's dependencies | an unadopted tool would move under every artefact; the foundation has no runtime dependency |
| run the tools elsewhere and import outputs as `PrecomputedArm` | possible, but the harness then cannot check determinism itself |
| give each tool the raw bytes and let it detect the encoding | a second difference between arms that is not extraction; decoding is one recorded step for all |
| more arms now | the first real material is thirteen pages of one outlet; more arms would not make it a comparison |
| tune parameters per tool | tuning on the pages to be judged conditions the comparison; defaults, stated |

## Consequences

- [`EXTRACTOR_CANDIDATES.md`](../extraction/EXTRACTOR_CANDIDATES.md) gains §6 with the selection; its survey stays.
- A review package can be built (`scripts/phase3_review_package.py`); the first one is a **pilot**, not a gold sample
  ([run report](../agent-runs/2026-10-08_real-canary-evaluation-o4-phase3-pilot.md)).
- Known limit of the blinding: the arms differ in shape — one states metadata bases and keeps non-body blocks, one has
  no title. A reviewer who knows the tools could guess. Names, the key, scores and ranks are not shown.

## Not decided here

- The gold sample (sizes, strata crossed, reviewers, adjudication) and the adoption criterion.
- Whether a combination of arms enters as an arm.
- A human-readable rendering of review cases.
