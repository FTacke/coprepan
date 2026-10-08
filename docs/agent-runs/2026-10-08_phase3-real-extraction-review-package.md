# Phase-3 real extraction review package: not begun — there is no real material

```text
run_started_at:      2026-10-08T15:53:41+02:00 (the run this report belongs to)
run_ended_at:        see the closing commit of the run
timezone:            Europe/Berlin
```

**Status: BLOCKED.** `PHASE3_GOLD_PACKAGE = NOT_BUILT`. The package is drawn from the preserved bodies
of the canary, and the canary did not run
([second report](2026-10-08_real-acquisition-canary-o4.md)).

**What the status does not claim.** No sample was drawn, no extractor was run on real pages, no
candidate was compared, no review package and no hidden key exist. No gold exists and none was
invented. `PHASE3_SAMPLE` is not `INSUFFICIENT_FROM_CANARY` either: that value would describe a canary
that ran and yielded too little.

**Kind of run:** none took place for this part.

`EXTERNAL_API_USAGE = NONE`. No LLM was used for anything.

## What exists for it

- the sample design, [`docs/extraction/GOLD_SAMPLE_DESIGN.md`](../extraction/GOLD_SAMPLE_DESIGN.md);
- the review codebook, written before any page was seen,
  [`docs/extraction/REVIEW_CODEBOOK_v1.md`](../extraction/REVIEW_CODEBOOK_v1.md);
- the candidate list, [`docs/extraction/EXTRACTOR_CANDIDATES.md`](../extraction/EXTRACTOR_CANDIDATES.md);
- `baseline_html/0.1.0`, lifecycle `EXPERIMENTAL`.

## Recommended next step

After a canary: the sample, the baseline and the classical candidates on byte-identical preserved
bodies, the blinded package with its frozen, hashed key, and the stop at
`PHASE3_GOLD_PACKAGE = READY_FOR_HUMAN_REVIEW`.
