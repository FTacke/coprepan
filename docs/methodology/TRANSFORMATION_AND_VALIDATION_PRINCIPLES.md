# Transformation and Validation Principles

**Status: NORMATIVE** — binding for every automated corpus transformation developed in this
repository (extraction, admission labelling, normalisation, annotation, enrichment). Adapted from
CO.RA.PAN 3.0's `CORPUS_TRANSFORMATION_DEVELOPMENT_PRINCIPLES.md` and `EVALUATION_PLAN_CHECKLIST.md`
(read 2026-10-06) to a written press corpus. Governing decision:
[CPD-0001](../decisions/CPD-0001_strategy-c-greenfield-core-and-foundation-principles.md) §8.

---

## 1. Four things that are not the same

| Act | Establishes | Does not establish |
|---|---|---|
| **Diagnosis** | what is the case, with evidence | that anything was changed |
| **Implementation** | that code exists and its tests pass | that its output is correct on real material |
| **Scientific validation** | measured quality against human gold and a realistic baseline | that it runs in production |
| **Production activation** | that it is switched on for corpus material | — it presupposes the three above and an explicit decision |

A report, a decision or a status line names which of the four it is. A `PASS` of one is never read
as a `PASS` of another. [`docs/STATUS.md`](../STATUS.md) tracks them separately for every stage.

## 2. The objective

The objective of automated processing is **not zero error**. It is a faithful, analysable
representation of the *published text*, materially better than the realistic alternative, with the
outlet's actual usage preserved.

## 3. Authenticity: no silent normalisation of the published text

Press analogue of CO.RA.PAN's rule against normalising speech toward written standard:

- The published wording is evidence. Regional and national variants, the outlet's orthography and
  punctuation, headline style, loanwords, nonstandard but authentic forms and typographical errors
  are **not corrected**. A form is not an error merely because it differs from an academy norm.
- A transformation may change *encoding* (Unicode normalisation, whitespace) as a recorded
  operation. It may not change *wording*.
- No lexical repair heuristics. If extraction yields a damaged word, the extractor is fixed and
  re-run on the preserved bytes; the text is not patched downstream. (The legacy pipeline patched
  it, producing 113,119 merges and new false merges.)
- Non-body material (captions, credits, embeds) is typed and excluded from a view, not deleted.
- Unknown stays unknown: no reconstructed date, author or section.

## 4. Evaluate against the realistic baseline

For every transformation, the default questions are: what does it remove; what harm does it
introduce; what is the net benefit for the corpus; is that benefit robust across the units that
matter (countries, outlets, outlet types, cohorts); what harm remains; which downstream analyses
gain; is authenticity preserved; is it reproducible and reversible.

- Precision and recall are diagnostics, not automatically the objective.
- The baseline is the *feasible* alternative (the current deterministic method, a classical
  classifier), not perfect manual annotation.
- **No generic hard floors.** Do not introduce thresholds such as 0.90 / 0.95 / 0.97 / 1.00 — or
  caps such as 10 % / 20 % / 35 % — because the number looks careful. A hard threshold is
  legitimate only with a named harm, a justified metric, a justified number and a reason why a
  continuous net-utility analysis is insufficient. Every number in a plan is labelled
  `DIAGNOSTIC`, `SOFT WARNING` or `HARD GATE`; a gate that cannot state its failure mode and
  rationale is a diagnostic.
- Human gold is the best frozen reference, not certainty. Where several analyses are genuinely
  defensible, predeclare the equivalence set before inference.

## 5. Development and validation are separated

- Development is allowed to mature. Do not spend a one-shot fresh validation on the first
  minimally plausible candidate.
- **Development and fresh (held-out) data are disjoint at the grouping level** — for press, by
  outlet and by document, never merely by sentence.
- Human gold is frozen and committed **before** any prediction is made on it.
- A release selector or gate is frozen before results and never modified afterwards.
- **Frozen evidence is immutable.** Gold sets, freeze inventories, completed reviewer files, frozen
  predictions and evaluation results are never edited to fit a later conclusion. A later
  qualification is added separately, dated, with a link to what motivates it. A `FAIL` may stay
  historically true.
- **Negative and historical results are preserved.** A rejected candidate, a failed run and a
  superseded design stay in the record with their evidence.

## 6. Evaluation-plan checklist

Answer before creating a fresh validation, in the development report of the module:

| Item | Question |
|---|---|
| BASELINE | What realistic baseline is being improved? |
| TARGET FUNCTION | What corpus-scientific problem does the module solve? Which analyses become possible or more reliable? |
| BENEFIT | Which errors or unusable structures does it remove — quantified on the development population? |
| HARM | Which errors or distortions can it introduce? Name the families, not just a rate. |
| AUTHENTICITY | Could it normalise real variation in the published text? What prevents that? |
| UTILITY | How is net benefit assessed, and why does that accounting fit this layer? |
| ROBUSTNESS | Across which units (country, outlet, outlet type, cohort, article type) must the benefit hold? What would non-robustness look like? |
| DOWNSTREAM | Which later analyses should benefit? What evidence is available or planned? |
| HARD GATES | For every number: which tier? For each hard gate: metric, threshold, failure mode, harm, why this threshold, why continuous analysis is insufficient, sensitivity checked, frozen before predictions? |
| DEVELOPMENT MATURITY | Why is this candidate ready? Which alternatives were compared and rejected? |
| POPULATION ADEQUACY | Can the planned fresh population support the robustness requirements — checked on gold before inference? |
| REVERSIBILITY / PROVENANCE | Can outputs be audited and removed without redoing upstream work? What is recorded per applied change? |

## 7. Classical first; LLM only on demonstrated net benefit

> Deterministic or classical methods are the default. An LLM layer is activated only when it shows
> a clear, reproducible net benefit against a realistic baseline on human gold.

The baseline wins ties. An adopted stage must be reversible, fully traced, and qualified on the
serving stack that will run it. Benchmarking a model does not make it production. Task-by-task
verdicts: [`docs/nlp/INDEX.md`](../nlp/INDEX.md) §7.

## 8. Measurement integrity

- **Never invent a number.** No accuracy, error rate, coverage, volume, cost, runtime or
  confidence interval is stated unless it was measured or is explicitly sourced. Every quantity is
  labelled: *measured* (with date and population), *sourced* (with source), *estimated*,
  *scenario assumption* or *unknown*.
- An unmeasured axis is `NOT_YET_MEASURABLE`, never `0`.
- A failed run produces no measurement of what it failed to do — no estimate, no lower bound, no
  "partial". Its artefacts are evidence, written once; a figure is salvageable only when the thing
  it measures completed. A failed run never authorises its own retry.
- When two runs are compared, compare their inputs by a digest verified to be discriminating.
- Scientific measurement infrastructure is reproducible: the script, its inputs by hash, its
  parameters and its output are recorded together.

## 9. Kinds of validity claim

A validation states which claim it supports:

| Claim | Meaning | Example (planned, none performed) |
|---|---|---|
| **reproducibility** | the same data and code give the same result | replay extraction and NLP from preserved bytes and compare hashes; rebuild a release from its manifest on a second machine |
| **robustness** | the finding survives defensible analytic choices | sensitivity to the selection view (outlet caps, section scope, duplicate handling); legacy text against re-extracted text |
| **replicability** | the finding recurs in new data from the same population | existing studies repeated on `native_v3` material of other months |
| **generalisability** | the finding holds for other units | additional outlets and outlet types per country; press contemporaneous with radio |

Technical function is not scientific validation.

## 10. Human review

Human decisions are scientific evidence and are recorded append-only, keyed on stable
content-addressed ids, with an explicit invalidation rule (a decision is invalidated when the
evidence it judged changes, and is then neither silently kept nor silently dropped). No pipeline
stage reads human decisions; they are downstream enrichment consumed at release or export time.
Reviewers see the material and a closed label set, not the machine's decision. An uncertain label
is a legitimate answer and is never recoded. No review infrastructure exists yet; these principles
bind its design.

## 11. Forward-only evolution

**Backfill is a decision, not a consequence.** A new component version applies to new work. An
artefact produced correctly under its recorded version stays valid for that version; a newer
model, a better rule set, a faster stage or a changed fingerprint never by itself makes old
outputs invalid or eligible for reprocessing. Reprocessing needs an explicit, operator-approved
change decision, starts at the earliest stage the decision invalidates, and never touches raw
preservation. A version mix inside a release is admissible when provenance resolves the versions
and analyses can filter by them. Where a change could shift a measured construct, a **bridge
sample** — a small frozen set processed under the old and the new version — measures the
difference on identical input.
